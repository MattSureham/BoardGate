"""Constrained placement-CSV authoring operations with semantic postconditions."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from boardgate.authoring.excellon import AuthoringOperationError
from boardgate.authoring.models import (
    AppliedPlacementAnchorCoordinateChange,
    AppliedPlacementReferenceDesignatorChange,
    SetPlacementAnchorCoordinate,
    SetPlacementReferenceDesignator,
)
from boardgate.domain.component import ComponentPlacement
from boardgate.domain.geometry import Unit
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.provenance import Provenance, SourceSpan
from boardgate.parsers.errors import ParserError
from boardgate.parsers.placement import (
    _ALIASES as _PLACEMENT_ALIASES,
)
from boardgate.parsers.placement import (
    PlacementParseResult,
)
from boardgate.parsers.tabular import TabularData, parse_csv, resolve_columns

AUTHORING_ADAPTER_POLICY_VERSION = "1.0"
MAX_PLACEMENT_PATCH_BYTES = 50 * 1024 * 1024
MAX_PLACEMENT_LINES = 1_000_000
MAX_PLACEMENT_LINE_BYTES = 1024 * 1024

_PLAIN_COORDINATE_TOKEN = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?\Z")


@dataclass(frozen=True, slots=True)
class PlacementReferenceWitness:
    """One exact, supported reference token and its source location."""

    row_index: int
    reference: str
    value_span: SourceSpan


@dataclass(frozen=True, slots=True)
class PlacementCoordinateWitness:
    """One exact, supported coordinate token and its source location."""

    row_index: int
    reference: str
    coordinate_lexeme: str
    value_mm: Decimal | None
    value_span: SourceSpan


@dataclass(frozen=True, slots=True)
class PlacementPatchCandidate:
    """Patched bytes awaiting an isolated reparse and semantic comparison."""

    payload: bytes
    input_sha256: str
    output_sha256: str
    output_source_file_id: str
    input_value_span: SourceSpan
    output_value_span: SourceSpan
    target_row_index: int
    affected_input_placement_ids: tuple[str, ...]


def _line_offsets(payload: bytes) -> tuple[int, ...]:
    offsets = [0]
    for raw_line in payload.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(raw_line))
    if offsets[-1] < len(payload):
        offsets.append(len(payload))
    return tuple(offsets)


@dataclass(frozen=True, slots=True)
class _RowCells:
    row_index: int
    line_number: int
    line_start: int
    fields: tuple[bytes, ...]


def _row_cells(
    payload: bytes,
    table: TabularData,
    *,
    subject: str,
) -> tuple[bytes, tuple[_RowCells, ...]]:
    delimiter = table.delimiter
    if delimiter is None:  # pragma: no cover - parse_csv always resolves one
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_TABLE_UNSUPPORTED",
            subject,
            "placement table has no resolved delimiter",
        )
    delimiter_bytes = delimiter.encode("utf-8")
    offsets = _line_offsets(payload)
    if len(offsets) - 1 > MAX_PLACEMENT_LINES:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_LINE_COUNT_LIMIT",
            subject,
            f"source exceeds {MAX_PLACEMENT_LINES} lines",
        )
    rows: list[_RowCells] = []
    for row_index, row in enumerate(table.rows):
        span = row.source_span
        if (
            span is None
            or span.start_line is None
            or span.end_line is None
            or span.start_line != span.end_line
        ):
            raise AuthoringOperationError(
                "AUTHORING_PLACEMENT_ROW_UNSUPPORTED",
                subject,
                "v1 requires each placement row to occupy exactly one source line",
            )
        line_start = offsets[span.start_line - 1]
        line_end = (
            offsets[span.start_line] if span.start_line < len(offsets) else len(payload)
        )
        content = payload[line_start:line_end].rstrip(b"\r\n")
        if len(content) > MAX_PLACEMENT_LINE_BYTES:
            raise AuthoringOperationError(
                "AUTHORING_PLACEMENT_LINE_LIMIT",
                subject,
                f"line exceeds {MAX_PLACEMENT_LINE_BYTES} bytes",
            )
        fields = tuple(content.split(delimiter_bytes))
        if len(fields) != len(table.headers):
            raise AuthoringOperationError(
                "AUTHORING_PLACEMENT_ROW_UNSUPPORTED",
                subject,
                "v1 requires plain rows without quoted or embedded delimiters",
            )
        rows.append(
            _RowCells(
                row_index=row_index,
                line_number=span.start_line,
                line_start=line_start,
                fields=fields,
            )
        )
    return delimiter_bytes, tuple(rows)


def _cell_token(
    row: _RowCells,
    column_index: int,
    delimiter_bytes: bytes,
) -> tuple[str, int, int]:
    field_offset = 0
    for field in row.fields[:column_index]:
        field_offset += len(field) + len(delimiter_bytes)
    cell = row.fields[column_index]
    token = cell.strip(b" \t")
    try:
        lexeme = token.decode("ascii")
    except UnicodeDecodeError:
        lexeme = ""
    token_offset = field_offset + (len(cell) - len(cell.lstrip(b" \t")))
    return lexeme, row.line_start + token_offset, len(token)


def _require_source_size(payload: bytes, *, subject: str) -> None:
    if len(payload) > MAX_PLACEMENT_PATCH_BYTES:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_SIZE_LIMIT",
            subject,
            f"source exceeds {MAX_PLACEMENT_PATCH_BYTES} bytes",
        )


def scan_placement_references(
    payload: bytes,
    *,
    subject: str,
) -> tuple[PlacementReferenceWitness, ...]:
    """Scan only the strict single-line, unquoted reference-cell subset."""
    _require_source_size(payload, subject=subject)
    try:
        table = parse_csv(payload, logical_path=subject)
        columns = resolve_columns(
            table,
            aliases={"reference": _PLACEMENT_ALIASES["reference"]},
            required=frozenset({"reference"}),
            logical_path=subject,
        )
    except ParserError as error:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_TABLE_UNSUPPORTED",
            subject,
            f"placement table is outside the supported subset ({error.code})",
        ) from error
    delimiter_bytes, rows = _row_cells(payload, table, subject=subject)
    reference_index = columns["reference"]
    witnesses: list[PlacementReferenceWitness] = []
    for row in rows:
        reference, token_start, token_length = _cell_token(
            row, reference_index, delimiter_bytes
        )
        witnesses.append(
            PlacementReferenceWitness(
                row_index=row.row_index,
                reference=reference,
                value_span=SourceSpan(
                    start_line=row.line_number,
                    end_line=row.line_number,
                    start_byte=token_start,
                    end_byte=token_start + token_length,
                ),
            )
        )
    return tuple(witnesses)


def scan_placement_coordinates(
    payload: bytes,
    *,
    coordinate: Literal["x", "y"],
    subject: str,
) -> tuple[PlacementCoordinateWitness, ...]:
    """Scan only the strict single-line, unquoted coordinate-cell subset."""
    _require_source_size(payload, subject=subject)
    try:
        table = parse_csv(payload, logical_path=subject)
        columns = resolve_columns(
            table,
            aliases={
                "reference": _PLACEMENT_ALIASES["reference"],
                coordinate: _PLACEMENT_ALIASES[coordinate],
            },
            required=frozenset({"reference", coordinate}),
            logical_path=subject,
        )
    except ParserError as error:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_TABLE_UNSUPPORTED",
            subject,
            f"placement table is outside the supported subset ({error.code})",
        ) from error
    delimiter_bytes, rows = _row_cells(payload, table, subject=subject)
    reference_index = columns["reference"]
    coordinate_index = columns[coordinate]
    witnesses: list[PlacementCoordinateWitness] = []
    for row in rows:
        reference, _, _ = _cell_token(row, reference_index, delimiter_bytes)
        lexeme, token_start, token_length = _cell_token(
            row, coordinate_index, delimiter_bytes
        )
        value: Decimal | None = None
        if _PLAIN_COORDINATE_TOKEN.fullmatch(lexeme) is not None:
            value = Decimal(lexeme)
        witnesses.append(
            PlacementCoordinateWitness(
                row_index=row.row_index,
                reference=reference,
                coordinate_lexeme=lexeme,
                value_mm=value,
                value_span=SourceSpan(
                    start_line=row.line_number,
                    end_line=row.line_number,
                    start_byte=token_start,
                    end_byte=token_start + token_length,
                ),
            )
        )
    return tuple(witnesses)


def _target_row(
    payload: bytes,
    parsed: PlacementParseResult,
    operation: SetPlacementReferenceDesignator,
) -> tuple[PlacementReferenceWitness, ComponentPlacement]:
    subject = operation.source_logical_path
    parsed_matches = tuple(
        (index, placement)
        for index, placement in enumerate(parsed.placements)
        if placement.reference == operation.expected_reference
    )
    if not parsed_matches:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_REFERENCE_NOT_FOUND",
            subject,
            f"reference {operation.expected_reference} has no parsed placement row",
        )
    if len(parsed_matches) != 1:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_REFERENCE_AMBIGUOUS",
            subject,
            f"reference {operation.expected_reference} does not resolve uniquely",
        )
    witnesses = scan_placement_references(payload, subject=subject)
    token_matches = tuple(
        witness
        for witness in witnesses
        if witness.reference == operation.expected_reference
    )
    if len(token_matches) != 1:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_REFERENCE_UNSUPPORTED",
            subject,
            "v1 requires one plain unquoted uppercase reference token",
        )
    witness = token_matches[0]
    row_index, target = parsed_matches[0]
    if witness.row_index != row_index:  # pragma: no cover - scanner/parse invariant
        raise RuntimeError("placement witness and parsed target rows diverged")
    return witness, target


def prepare_placement_reference_designator_patch(
    payload: bytes,
    parsed: PlacementParseResult,
    operation: SetPlacementReferenceDesignator,
) -> PlacementPatchCandidate:
    """Validate preconditions and replace exactly one same-width reference token."""
    subject = operation.source_logical_path
    input_digest = hashlib.sha256(payload).hexdigest()
    if input_digest != operation.source_sha256:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_SHA_MISMATCH",
            subject,
            "source bytes do not match the request digest",
        )
    if parsed.source_file_id != operation.source_file_id:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_ID_MISMATCH",
            subject,
            "parsed source identity does not match the request",
        )
    witness, target = _target_row(payload, parsed, operation)
    if any(
        placement.reference == operation.new_reference
        for placement in parsed.placements
    ):
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_NEW_REFERENCE_COLLISION",
            subject,
            f"reference {operation.new_reference} already exists in the source",
        )
    if len(operation.new_reference.encode("ascii")) != len(
        witness.reference.encode("ascii")
    ):
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_NEW_REFERENCE_WIDTH",
            subject,
            "new reference must fit the existing fixed-width token",
        )
    start = witness.value_span.start_byte
    end = witness.value_span.end_byte
    if start is None or end is None:  # pragma: no cover - witness invariant
        raise RuntimeError("placement reference witness omitted byte offsets")
    output = payload[:start] + operation.new_reference.encode("ascii") + payload[end:]
    if len(output) != len(payload):  # pragma: no cover - width-check invariant
        raise RuntimeError("same-width placement patch changed source length")
    output_digest = hashlib.sha256(output).hexdigest()
    if output_digest == input_digest:  # pragma: no cover - request rejects no-op
        raise RuntimeError("placement patch did not change source bytes")
    target_id = target.provenance.object_id
    if target_id is None:  # pragma: no cover - parser invariant
        raise RuntimeError("parsed target placement omitted its object_id")
    return PlacementPatchCandidate(
        payload=output,
        input_sha256=input_digest,
        output_sha256=output_digest,
        output_source_file_id=source_file_id(
            operation.source_logical_path,
            output_digest,
        ),
        input_value_span=witness.value_span,
        output_value_span=witness.value_span,
        target_row_index=witness.row_index,
        affected_input_placement_ids=(target_id,),
    )


def _provenance_signature(provenance: Provenance) -> tuple[object, ...]:
    span = provenance.source_span
    return (
        None if span is None else span.start_line,
        None if span is None else span.end_line,
        None if span is None else span.start_byte,
        None if span is None else span.end_byte,
        tuple(sorted(provenance.raw_coordinates.items())),
        tuple(sorted(provenance.metadata.items())),
    )


def _placement_signature(
    placement: ComponentPlacement,
    *,
    include_reference: bool,
) -> tuple[object, ...]:
    return (
        placement.reference if include_reference else None,
        placement.position,
        placement.rotation_degrees,
        placement.side,
        placement.value,
        placement.footprint,
        placement.dnp,
        tuple(sorted(placement.metadata.items())),
        _provenance_signature(placement.provenance),
    )


def verify_placement_reference_designator_patch(
    before: PlacementParseResult,
    after: PlacementParseResult,
    operation: SetPlacementReferenceDesignator,
    candidate: PlacementPatchCandidate,
) -> AppliedPlacementReferenceDesignatorChange:
    """Prove the reparsed delta is exactly the requested reference rename."""
    subject = operation.source_logical_path
    if after.source_file_id != candidate.output_source_file_id:
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_SOURCE_MISMATCH",
            subject,
            "reparsed output source identity is inconsistent",
        )
    if before.source_unit != after.source_unit:
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_METADATA_CHANGED",
            subject,
            "reparsed source metadata changed outside the requested operation",
        )
    if len(before.placements) != len(after.placements):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_FEATURE_COUNT_CHANGED",
            subject,
            "reparsed placement count changed",
        )
    affected_output: list[str] = []
    for index, (original, emitted) in enumerate(
        zip(before.placements, after.placements, strict=True)
    ):
        target = index == candidate.target_row_index
        if _placement_signature(
            original, include_reference=False
        ) != _placement_signature(emitted, include_reference=False):
            raise AuthoringOperationError(
                "AUTHORING_POSTCONDITION_PLACEMENT_CHANGED",
                subject,
                "a protected placement fact changed",
            )
        required_reference = operation.new_reference if target else original.reference
        if emitted.reference != required_reference:
            raise AuthoringOperationError(
                "AUTHORING_POSTCONDITION_REFERENCE_MISMATCH",
                subject,
                "reparsed references do not match the requested delta",
            )
        if target:
            emitted_id = emitted.provenance.object_id
            if emitted_id is None:  # pragma: no cover - parser invariant
                raise RuntimeError("reparsed target placement omitted its object_id")
            affected_output.append(emitted_id)
    if len(affected_output) != len(candidate.affected_input_placement_ids):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_TARGET_COUNT_CHANGED",
            subject,
            "the target placement set changed during emission",
        )
    return AppliedPlacementReferenceDesignatorChange(
        source_logical_path=operation.source_logical_path,
        input_source_file_id=operation.source_file_id,
        output_source_file_id=candidate.output_source_file_id,
        input_sha256=candidate.input_sha256,
        output_sha256=candidate.output_sha256,
        old_reference=operation.expected_reference,
        new_reference=operation.new_reference,
        input_value_span=candidate.input_value_span,
        output_value_span=candidate.output_value_span,
        affected_input_placement_ids=candidate.affected_input_placement_ids,
        affected_output_placement_ids=tuple(affected_output),
    )


def _target_coordinate_row(
    payload: bytes,
    parsed: PlacementParseResult,
    operation: SetPlacementAnchorCoordinate,
) -> tuple[PlacementCoordinateWitness, ComponentPlacement]:
    subject = operation.source_logical_path
    parsed_matches = tuple(
        (index, placement)
        for index, placement in enumerate(parsed.placements)
        if placement.reference == operation.reference
    )
    if not parsed_matches:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_REFERENCE_NOT_FOUND",
            subject,
            f"reference {operation.reference} has no parsed placement row",
        )
    if len(parsed_matches) != 1:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_REFERENCE_AMBIGUOUS",
            subject,
            f"reference {operation.reference} does not resolve uniquely",
        )
    witnesses = scan_placement_coordinates(
        payload,
        coordinate=operation.coordinate,
        subject=subject,
    )
    token_matches = tuple(
        witness for witness in witnesses if witness.reference == operation.reference
    )
    if len(token_matches) != 1:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_REFERENCE_UNSUPPORTED",
            subject,
            "v1 requires one plain unquoted uppercase reference token",
        )
    witness = token_matches[0]
    row_index, target = parsed_matches[0]
    if witness.row_index != row_index:  # pragma: no cover - scanner/parse invariant
        raise RuntimeError("placement witness and parsed target rows diverged")
    if witness.value_mm is None:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_COORDINATE_UNSUPPORTED",
            subject,
            "v1 requires a plain decimal coordinate token",
        )
    return witness, target


def _replacement_coordinate_lexeme(
    witness: PlacementCoordinateWitness,
    operation: SetPlacementAnchorCoordinate,
) -> bytes:
    old_lexeme = witness.coordinate_lexeme
    fractional_digits = len(old_lexeme.partition(".")[2])
    requested = Decimal(str(operation.new_position_mm))
    quantum = Decimal(1).scaleb(-fractional_digits)
    try:
        quantized = requested.quantize(quantum)
    except InvalidOperation as error:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_NEW_COORDINATE_PRECISION",
            operation.source_logical_path,
            "new coordinate cannot be represented by the existing token precision",
        ) from error
    if quantized != requested:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_NEW_COORDINATE_PRECISION",
            operation.source_logical_path,
            "new coordinate cannot be represented by the existing token precision",
        )
    replacement = format(quantized, f".{fractional_digits}f")
    if len(replacement) != len(old_lexeme):
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_NEW_COORDINATE_WIDTH",
            operation.source_logical_path,
            "new coordinate must fit the existing fixed-width decimal token",
        )
    return replacement.encode("ascii")


def prepare_placement_anchor_coordinate_patch(
    payload: bytes,
    parsed: PlacementParseResult,
    operation: SetPlacementAnchorCoordinate,
) -> PlacementPatchCandidate:
    """Validate preconditions and replace exactly one same-width coordinate token."""
    subject = operation.source_logical_path
    input_digest = hashlib.sha256(payload).hexdigest()
    if input_digest != operation.source_sha256:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_SHA_MISMATCH",
            subject,
            "source bytes do not match the request digest",
        )
    if parsed.source_file_id != operation.source_file_id:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_ID_MISMATCH",
            subject,
            "parsed source identity does not match the request",
        )
    if parsed.source_unit is not Unit.MILLIMETRE:
        raise AuthoringOperationError(
            "AUTHORING_PLACEMENT_UNIT_UNSUPPORTED",
            subject,
            "v1 coordinate modification requires an explicit metric source",
        )
    witness, target = _target_coordinate_row(payload, parsed, operation)
    if witness.value_mm != Decimal(str(operation.expected_position_mm)):
        raise AuthoringOperationError(
            "AUTHORING_PRECONDITION_MISMATCH",
            subject,
            "coordinate token does not match expected_position_mm",
        )
    parsed_value = (
        target.position.x if operation.coordinate == "x" else target.position.y
    )
    if not math.isclose(
        parsed_value,
        operation.expected_position_mm,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise AuthoringOperationError(
            "AUTHORING_PRECONDITION_MISMATCH",
            subject,
            "parsed anchor coordinate does not match expected_position_mm",
        )
    replacement = _replacement_coordinate_lexeme(witness, operation)
    start = witness.value_span.start_byte
    end = witness.value_span.end_byte
    if start is None or end is None:  # pragma: no cover - witness invariant
        raise RuntimeError("placement coordinate witness omitted byte offsets")
    output = payload[:start] + replacement + payload[end:]
    if len(output) != len(payload):  # pragma: no cover - width-check invariant
        raise RuntimeError("same-width placement patch changed source length")
    output_digest = hashlib.sha256(output).hexdigest()
    if output_digest == input_digest:  # pragma: no cover - request rejects no-op
        raise RuntimeError("placement patch did not change source bytes")
    target_id = target.provenance.object_id
    if target_id is None:  # pragma: no cover - parser invariant
        raise RuntimeError("parsed target placement omitted its object_id")
    return PlacementPatchCandidate(
        payload=output,
        input_sha256=input_digest,
        output_sha256=output_digest,
        output_source_file_id=source_file_id(
            operation.source_logical_path,
            output_digest,
        ),
        input_value_span=witness.value_span,
        output_value_span=witness.value_span,
        target_row_index=witness.row_index,
        affected_input_placement_ids=(target_id,),
    )


def _coordinate_provenance_signature(
    provenance: Provenance,
    *,
    coordinate: str,
) -> tuple[object, ...]:
    span = provenance.source_span
    return (
        None if span is None else span.start_line,
        None if span is None else span.end_line,
        None if span is None else span.start_byte,
        None if span is None else span.end_byte,
        tuple(
            sorted(
                (key, value)
                for key, value in provenance.raw_coordinates.items()
                if key != coordinate
            )
        ),
        tuple(sorted(provenance.metadata.items())),
    )


def _coordinate_placement_signature(
    placement: ComponentPlacement,
    *,
    coordinate: Literal["x", "y"],
) -> tuple[object, ...]:
    kept_position = placement.position.y if coordinate == "x" else placement.position.x
    return (
        placement.reference,
        kept_position,
        placement.rotation_degrees,
        placement.side,
        placement.value,
        placement.footprint,
        placement.dnp,
        tuple(sorted(placement.metadata.items())),
        _coordinate_provenance_signature(placement.provenance, coordinate=coordinate),
    )


def verify_placement_anchor_coordinate_patch(
    before: PlacementParseResult,
    after: PlacementParseResult,
    operation: SetPlacementAnchorCoordinate,
    candidate: PlacementPatchCandidate,
) -> AppliedPlacementAnchorCoordinateChange:
    """Prove the reparsed delta is exactly the requested coordinate change."""
    subject = operation.source_logical_path
    if after.source_file_id != candidate.output_source_file_id:
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_SOURCE_MISMATCH",
            subject,
            "reparsed output source identity is inconsistent",
        )
    if before.source_unit != after.source_unit:
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_METADATA_CHANGED",
            subject,
            "reparsed source metadata changed outside the requested operation",
        )
    if len(before.placements) != len(after.placements):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_FEATURE_COUNT_CHANGED",
            subject,
            "reparsed placement count changed",
        )
    affected_output: list[str] = []
    for index, (original, emitted) in enumerate(
        zip(before.placements, after.placements, strict=True)
    ):
        target = index == candidate.target_row_index
        if target:
            if _coordinate_placement_signature(
                original, coordinate=operation.coordinate
            ) != _coordinate_placement_signature(
                emitted, coordinate=operation.coordinate
            ):
                raise AuthoringOperationError(
                    "AUTHORING_POSTCONDITION_PLACEMENT_CHANGED",
                    subject,
                    "a protected placement fact changed",
                )
        elif _placement_signature(
            original, include_reference=True
        ) != _placement_signature(emitted, include_reference=True):
            raise AuthoringOperationError(
                "AUTHORING_POSTCONDITION_PLACEMENT_CHANGED",
                subject,
                "a protected placement fact changed",
            )
        if target:
            emitted_value = (
                emitted.position.x
                if operation.coordinate == "x"
                else emitted.position.y
            )
            if not math.isclose(
                emitted_value,
                operation.new_position_mm,
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                raise AuthoringOperationError(
                    "AUTHORING_POSTCONDITION_COORDINATE_MISMATCH",
                    subject,
                    "reparsed coordinates do not match the requested delta",
                )
            emitted_id = emitted.provenance.object_id
            if emitted_id is None:  # pragma: no cover - parser invariant
                raise RuntimeError("reparsed target placement omitted its object_id")
            affected_output.append(emitted_id)
    if len(affected_output) != len(candidate.affected_input_placement_ids):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_TARGET_COUNT_CHANGED",
            subject,
            "the target placement set changed during emission",
        )
    return AppliedPlacementAnchorCoordinateChange(
        source_logical_path=operation.source_logical_path,
        input_source_file_id=operation.source_file_id,
        output_source_file_id=candidate.output_source_file_id,
        input_sha256=candidate.input_sha256,
        output_sha256=candidate.output_sha256,
        reference=operation.reference,
        coordinate=operation.coordinate,
        old_position_mm=operation.expected_position_mm,
        new_position_mm=operation.new_position_mm,
        input_value_span=candidate.input_value_span,
        output_value_span=candidate.output_value_span,
        affected_input_placement_ids=candidate.affected_input_placement_ids,
        affected_output_placement_ids=tuple(affected_output),
    )
