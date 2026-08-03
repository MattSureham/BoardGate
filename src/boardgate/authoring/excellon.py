"""Constrained Excellon authoring operations with semantic postconditions."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from boardgate.authoring.models import (
    AppliedExcellonToolDiameterChange,
    SetExcellonToolDiameter,
)
from boardgate.domain.drill import DrillHit, DrillSlot
from boardgate.domain.enums import FileType
from boardgate.domain.geometry import Unit
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.provenance import Provenance, SourceSpan
from boardgate.parsers.excellon import ExcellonParseResult

AUTHORING_ADAPTER_POLICY_VERSION = "1.0"
MAX_EXCELLON_PATCH_BYTES = 50 * 1024 * 1024
MAX_EXCELLON_LINE_BYTES = 4096
MAX_EXCELLON_LINES = 1_000_000
MAX_EXCELLON_TOOL_DEFINITIONS = 1024

_STRICT_TOOL_DEFINITION = re.compile(
    rb"^[ \t]*T(?P<number>[0-9]{1,6})C"
    rb"(?P<diameter>(?:0|[1-9][0-9]*)\.[0-9]{1,6})[ \t]*$"
)
_TOOL_DEFINITION_PREFIX = re.compile(rb"^[ \t]*T[0-9]{1,6}C")


class AuthoringOperationError(ValueError):
    """Typed, source-safe deterministic operation failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


@dataclass(frozen=True, slots=True)
class ExcellonToolDefinitionWitness:
    """One exact, supported tool-diameter token and its source location."""

    tool_code: str
    diameter_lexeme: str
    diameter_mm: Decimal
    value_span: SourceSpan


@dataclass(frozen=True, slots=True)
class ExcellonPatchCandidate:
    """Patched bytes awaiting an isolated reparse and semantic comparison."""

    payload: bytes
    input_sha256: str
    output_sha256: str
    output_source_file_id: str
    input_value_span: SourceSpan
    output_value_span: SourceSpan
    affected_input_drill_ids: tuple[str, ...]


def scan_excellon_tool_definitions(
    payload: bytes,
    *,
    subject: str,
) -> tuple[ExcellonToolDefinitionWitness, ...]:
    """Scan only the strict tool-definition subset used by the v1 operation."""
    if len(payload) > MAX_EXCELLON_PATCH_BYTES:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_SIZE_LIMIT",
            subject,
            f"source exceeds {MAX_EXCELLON_PATCH_BYTES} bytes",
        )
    witnesses: list[ExcellonToolDefinitionWitness] = []
    seen: set[str] = set()
    byte_offset = 0
    for line_number, raw_line in enumerate(payload.splitlines(keepends=True), start=1):
        if line_number > MAX_EXCELLON_LINES:
            raise AuthoringOperationError(
                "AUTHORING_EXCELLON_LINE_COUNT_LIMIT",
                subject,
                f"source exceeds {MAX_EXCELLON_LINES} lines",
            )
        content = raw_line.rstrip(b"\r\n")
        if len(content) > MAX_EXCELLON_LINE_BYTES:
            raise AuthoringOperationError(
                "AUTHORING_EXCELLON_LINE_LIMIT",
                subject,
                f"line exceeds {MAX_EXCELLON_LINE_BYTES} bytes",
            )
        match = _STRICT_TOOL_DEFINITION.fullmatch(content)
        if match is None:
            if _TOOL_DEFINITION_PREFIX.match(content):
                raise AuthoringOperationError(
                    "AUTHORING_EXCELLON_TOOL_DEFINITION_UNSUPPORTED",
                    subject,
                    "tool definitions must use a plain TnnC decimal form",
                )
            byte_offset += len(raw_line)
            continue
        if len(witnesses) >= MAX_EXCELLON_TOOL_DEFINITIONS:
            raise AuthoringOperationError(
                "AUTHORING_EXCELLON_TOOL_LIMIT",
                subject,
                f"source exceeds {MAX_EXCELLON_TOOL_DEFINITIONS} tool definitions",
            )
        number = int(match.group("number"))
        tool_code = f"T{number:02d}"
        if tool_code in seen:
            raise AuthoringOperationError(
                "AUTHORING_EXCELLON_TOOL_DUPLICATE",
                subject,
                f"tool {tool_code} is defined more than once",
            )
        seen.add(tool_code)
        diameter_bytes = match.group("diameter")
        try:
            diameter = Decimal(diameter_bytes.decode("ascii"))
        except (InvalidOperation, UnicodeDecodeError) as error:
            raise AuthoringOperationError(
                "AUTHORING_EXCELLON_TOOL_DIAMETER_INVALID",
                subject,
                f"tool {tool_code} has an invalid diameter",
            ) from error
        start_byte = byte_offset + match.start("diameter")
        end_byte = byte_offset + match.end("diameter")
        witnesses.append(
            ExcellonToolDefinitionWitness(
                tool_code=tool_code,
                diameter_lexeme=diameter_bytes.decode("ascii"),
                diameter_mm=diameter,
                value_span=SourceSpan(
                    start_line=line_number,
                    end_line=line_number,
                    start_byte=start_byte,
                    end_byte=end_byte,
                ),
            )
        )
        byte_offset += len(raw_line)
    return tuple(witnesses)


def _target_witness(
    payload: bytes,
    operation: SetExcellonToolDiameter,
) -> ExcellonToolDefinitionWitness:
    witnesses = scan_excellon_tool_definitions(
        payload,
        subject=operation.source_logical_path,
    )
    matching = tuple(
        witness for witness in witnesses if witness.tool_code == operation.tool_code
    )
    if not matching:
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_TOOL_NOT_FOUND",
            operation.source_logical_path,
            f"tool {operation.tool_code} has no supported definition",
        )
    if len(matching) != 1:  # pragma: no cover - scanner rejects duplicates
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_TOOL_AMBIGUOUS",
            operation.source_logical_path,
            f"tool {operation.tool_code} does not resolve uniquely",
        )
    return matching[0]


def _replacement_lexeme(
    witness: ExcellonToolDefinitionWitness,
    operation: SetExcellonToolDiameter,
) -> bytes:
    old_lexeme = witness.diameter_lexeme
    fractional_digits = len(old_lexeme.partition(".")[2])
    requested = Decimal(str(operation.new_diameter_mm))
    quantum = Decimal(1).scaleb(-fractional_digits)
    try:
        quantized = requested.quantize(quantum)
    except InvalidOperation as error:
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_NEW_DIAMETER_PRECISION",
            operation.source_logical_path,
            "new diameter cannot be represented by the existing token precision",
        ) from error
    if quantized != requested:
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_NEW_DIAMETER_PRECISION",
            operation.source_logical_path,
            "new diameter cannot be represented by the existing token precision",
        )
    replacement = format(quantized, f".{fractional_digits}f")
    if len(replacement) != len(old_lexeme):
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_NEW_DIAMETER_WIDTH",
            operation.source_logical_path,
            "new diameter must fit the existing fixed-width decimal token",
        )
    return replacement.encode("ascii")


def _require_supported_source(
    parsed: ExcellonParseResult,
    operation: SetExcellonToolDiameter,
    witness: ExcellonToolDefinitionWitness,
) -> tuple[DrillHit, ...]:
    subject = operation.source_logical_path
    if parsed.source_file_id != operation.source_file_id:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_ID_MISMATCH",
            subject,
            "parsed source identity does not match the request",
        )
    if parsed.original_unit is not Unit.MILLIMETRE:
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_UNIT_UNSUPPORTED",
            subject,
            "v1 tool-diameter modification requires an explicit metric source",
        )
    if parsed.notation != "absolute":
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_NOTATION_UNSUPPORTED",
            subject,
            "v1 tool-diameter modification requires absolute notation",
        )
    if parsed.warnings or parsed.limitations:
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_DIAGNOSTIC_UNSUPPORTED",
            subject,
            "v1 modification rejects sources with parser warnings or limitations",
        )
    expected = Decimal(str(operation.expected_diameter_mm))
    if witness.diameter_mm != expected:
        raise AuthoringOperationError(
            "AUTHORING_PRECONDITION_MISMATCH",
            subject,
            "tool definition does not match expected_diameter_mm",
        )
    affected = tuple(
        drill for drill in parsed.drills if drill.tool_code == operation.tool_code
    )
    if not affected:
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_TOOL_UNUSED",
            subject,
            f"tool {operation.tool_code} has no round drill hits",
        )
    if any(
        not math.isclose(
            drill.diameter_mm,
            operation.expected_diameter_mm,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for drill in affected
    ):
        raise AuthoringOperationError(
            "AUTHORING_PRECONDITION_MISMATCH",
            subject,
            "parsed target drills do not match expected_diameter_mm",
        )
    if any(slot.tool_code == operation.tool_code for slot in parsed.slots):
        raise AuthoringOperationError(
            "AUTHORING_EXCELLON_SLOT_SCOPE_UNSUPPORTED",
            subject,
            "v1 cannot change a tool that is also used by a routed slot",
        )
    return affected


def prepare_excellon_tool_diameter_patch(
    payload: bytes,
    parsed: ExcellonParseResult,
    operation: SetExcellonToolDiameter,
) -> ExcellonPatchCandidate:
    """Validate preconditions and replace exactly one same-width diameter token."""
    input_digest = hashlib.sha256(payload).hexdigest()
    if input_digest != operation.source_sha256:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_SHA_MISMATCH",
            operation.source_logical_path,
            "source bytes do not match the request digest",
        )
    witness = _target_witness(payload, operation)
    affected = _require_supported_source(parsed, operation, witness)
    replacement = _replacement_lexeme(witness, operation)
    start = witness.value_span.start_byte
    end = witness.value_span.end_byte
    if start is None or end is None:  # pragma: no cover - witness invariant
        raise RuntimeError("tool definition witness omitted byte offsets")
    output = payload[:start] + replacement + payload[end:]
    if len(output) != len(payload):  # pragma: no cover - formatter invariant
        raise RuntimeError("same-width Excellon patch changed source length")
    output_digest = hashlib.sha256(output).hexdigest()
    if output_digest == input_digest:  # pragma: no cover - request rejects no-op
        raise RuntimeError("Excellon patch did not change source bytes")
    return ExcellonPatchCandidate(
        payload=output,
        input_sha256=input_digest,
        output_sha256=output_digest,
        output_source_file_id=source_file_id(
            operation.source_logical_path,
            output_digest,
        ),
        input_value_span=witness.value_span,
        output_value_span=witness.value_span,
        affected_input_drill_ids=tuple(drill.drill_id for drill in affected),
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


def _drill_signature(drill: DrillHit, *, include_diameter: bool) -> tuple[object, ...]:
    return (
        drill.position,
        drill.diameter_mm if include_diameter else None,
        drill.tool_code,
        drill.plating,
        _provenance_signature(drill.provenance),
    )


def _slot_signature(slot: DrillSlot) -> tuple[object, ...]:
    return (
        slot.kind,
        slot.start,
        slot.end,
        slot.center,
        slot.clockwise,
        slot.width_mm,
        slot.tool_code,
        slot.plating,
        _provenance_signature(slot.provenance),
    )


def verify_excellon_tool_diameter_patch(
    before: ExcellonParseResult,
    after: ExcellonParseResult,
    operation: SetExcellonToolDiameter,
    candidate: ExcellonPatchCandidate,
) -> AppliedExcellonToolDiameterChange:
    """Prove the reparsed delta is exactly the requested round-tool diameter."""
    subject = operation.source_logical_path
    if after.source_file_id != candidate.output_source_file_id:
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_SOURCE_MISMATCH",
            subject,
            "reparsed output source identity is inconsistent",
        )
    metadata_before = (
        before.original_unit,
        before.notation,
        before.zero_suppression,
        before.coordinate_format,
        before.generator_hints,
        before.warnings,
        before.limitations,
    )
    metadata_after = (
        after.original_unit,
        after.notation,
        after.zero_suppression,
        after.coordinate_format,
        after.generator_hints,
        after.warnings,
        after.limitations,
    )
    if metadata_before != metadata_after:
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_METADATA_CHANGED",
            subject,
            "reparsed source metadata changed outside the requested operation",
        )
    if len(before.drills) != len(after.drills) or len(before.slots) != len(after.slots):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_FEATURE_COUNT_CHANGED",
            subject,
            "reparsed drill or slot count changed",
        )
    affected_after: list[str] = []
    for original, emitted in zip(before.drills, after.drills, strict=True):
        target = original.tool_code == operation.tool_code
        if _drill_signature(original, include_diameter=False) != _drill_signature(
            emitted,
            include_diameter=False,
        ):
            raise AuthoringOperationError(
                "AUTHORING_POSTCONDITION_DRILL_CHANGED",
                subject,
                "a protected drill fact changed",
            )
        required_diameter = (
            operation.new_diameter_mm if target else original.diameter_mm
        )
        if not math.isclose(
            emitted.diameter_mm,
            required_diameter,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise AuthoringOperationError(
                "AUTHORING_POSTCONDITION_DIAMETER_MISMATCH",
                subject,
                "reparsed drill diameters do not match the requested delta",
            )
        if target:
            affected_after.append(emitted.drill_id)
    if tuple(_slot_signature(slot) for slot in before.slots) != tuple(
        _slot_signature(slot) for slot in after.slots
    ):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_SLOT_CHANGED",
            subject,
            "a protected routed-slot fact changed",
        )
    if len(affected_after) != len(candidate.affected_input_drill_ids):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_TARGET_COUNT_CHANGED",
            subject,
            "the target drill set changed during emission",
        )
    return AppliedExcellonToolDiameterChange(
        source_logical_path=operation.source_logical_path,
        input_source_file_id=operation.source_file_id,
        output_source_file_id=candidate.output_source_file_id,
        input_sha256=candidate.input_sha256,
        output_sha256=candidate.output_sha256,
        tool_code=operation.tool_code,
        old_diameter_mm=operation.expected_diameter_mm,
        new_diameter_mm=operation.new_diameter_mm,
        input_value_span=candidate.input_value_span,
        output_value_span=candidate.output_value_span,
        affected_input_drill_ids=candidate.affected_input_drill_ids,
        affected_output_drill_ids=tuple(affected_after),
    )


def require_excellon_file_type(file_type: FileType, *, subject: str) -> None:
    """Keep request/source classification mismatch failures explicit."""
    if file_type is not FileType.EXCELLON:
        raise AuthoringOperationError(
            "AUTHORING_TARGET_TYPE_MISMATCH",
            subject,
            "set_excellon_tool_diameter requires a confirmed Excellon source",
        )
