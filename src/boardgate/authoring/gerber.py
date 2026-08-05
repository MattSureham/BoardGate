"""Constrained Gerber authoring operations with semantic postconditions."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from boardgate.authoring.excellon import AuthoringOperationError
from boardgate.authoring.models import (
    AppliedGerberStandardApertureDiameterChange,
    SetGerberStandardApertureDiameter,
)
from boardgate.domain.enums import ApertureShape, FileType
from boardgate.domain.geometry import Unit
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.layer import (
    Aperture,
    ArcPrimitive,
    FlashPrimitive,
    GraphicPrimitive,
    LinePrimitive,
    RegionPrimitive,
)
from boardgate.domain.provenance import Provenance, SourceSpan
from boardgate.parsers.gerber import GerberParseResult

AUTHORING_GERBER_ADAPTER_POLICY_VERSION = "1.0"
MAX_GERBER_PATCH_BYTES = 50 * 1024 * 1024
MAX_GERBER_LINE_BYTES = 4096
MAX_GERBER_LINES = 1_000_000
MAX_GERBER_APERTURE_DEFINITIONS = 1024

_STRICT_APERTURE_DEFINITION = re.compile(
    rb"^%ADD(?P<number>[0-9]{1,6})C,"
    rb"(?P<diameter>(?:0|[1-9][0-9]*)\.[0-9]{1,6})\*%$"
)
_APERTURE_DEFINITION_PREFIX = re.compile(rb"^[ \t]*%ADD[0-9]{1,6}C[ \t]*,")


@dataclass(frozen=True, slots=True)
class GerberApertureDefinitionWitness:
    """One exact, supported aperture-diameter token and its source location."""

    aperture_code: str
    diameter_lexeme: str
    diameter_mm: Decimal
    value_span: SourceSpan


@dataclass(frozen=True, slots=True)
class GerberPatchCandidate:
    """Patched bytes awaiting an isolated reparse and semantic comparison."""

    payload: bytes
    input_sha256: str
    output_sha256: str
    output_source_file_id: str
    input_value_span: SourceSpan
    output_value_span: SourceSpan
    affected_input_primitive_ids: tuple[str, ...]


def scan_gerber_aperture_definitions(
    payload: bytes,
    *,
    subject: str,
) -> tuple[GerberApertureDefinitionWitness, ...]:
    """Scan only the strict circle-aperture definition subset of v1."""
    if len(payload) > MAX_GERBER_PATCH_BYTES:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_SIZE_LIMIT",
            subject,
            f"source exceeds {MAX_GERBER_PATCH_BYTES} bytes",
        )
    witnesses: list[GerberApertureDefinitionWitness] = []
    seen: set[str] = set()
    byte_offset = 0
    for line_number, raw_line in enumerate(payload.splitlines(keepends=True), start=1):
        if line_number > MAX_GERBER_LINES:
            raise AuthoringOperationError(
                "AUTHORING_GERBER_LINE_COUNT_LIMIT",
                subject,
                f"source exceeds {MAX_GERBER_LINES} lines",
            )
        content = raw_line.rstrip(b"\r\n")
        if len(content) > MAX_GERBER_LINE_BYTES:
            raise AuthoringOperationError(
                "AUTHORING_GERBER_LINE_LIMIT",
                subject,
                f"line exceeds {MAX_GERBER_LINE_BYTES} bytes",
            )
        match = _STRICT_APERTURE_DEFINITION.fullmatch(content)
        if match is None:
            if _APERTURE_DEFINITION_PREFIX.match(content):
                raise AuthoringOperationError(
                    "AUTHORING_GERBER_APERTURE_DEFINITION_UNSUPPORTED",
                    subject,
                    "circle aperture definitions must use a plain %ADDnnC,d*% form",
                )
            byte_offset += len(raw_line)
            continue
        if len(witnesses) >= MAX_GERBER_APERTURE_DEFINITIONS:
            raise AuthoringOperationError(
                "AUTHORING_GERBER_APERTURE_LIMIT",
                subject,
                "source exceeds "
                f"{MAX_GERBER_APERTURE_DEFINITIONS} aperture definitions",
            )
        number = int(match.group("number"))
        aperture_code = f"D{number}"
        if aperture_code in seen:
            raise AuthoringOperationError(
                "AUTHORING_GERBER_APERTURE_DUPLICATE",
                subject,
                f"aperture {aperture_code} is defined more than once",
            )
        seen.add(aperture_code)
        diameter_bytes = match.group("diameter")
        try:
            diameter = Decimal(diameter_bytes.decode("ascii"))
        except (InvalidOperation, UnicodeDecodeError) as error:
            raise AuthoringOperationError(
                "AUTHORING_GERBER_APERTURE_DIAMETER_INVALID",
                subject,
                f"aperture {aperture_code} has an invalid diameter",
            ) from error
        start_byte = byte_offset + match.start("diameter")
        end_byte = byte_offset + match.end("diameter")
        witnesses.append(
            GerberApertureDefinitionWitness(
                aperture_code=aperture_code,
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
    operation: SetGerberStandardApertureDiameter,
) -> GerberApertureDefinitionWitness:
    witnesses = scan_gerber_aperture_definitions(
        payload,
        subject=operation.source_logical_path,
    )
    matching = tuple(
        witness
        for witness in witnesses
        if witness.aperture_code == operation.aperture_code
    )
    if not matching:
        raise AuthoringOperationError(
            "AUTHORING_GERBER_APERTURE_NOT_FOUND",
            operation.source_logical_path,
            f"aperture {operation.aperture_code} has no supported definition",
        )
    if len(matching) != 1:  # pragma: no cover - scanner rejects duplicates
        raise AuthoringOperationError(
            "AUTHORING_GERBER_APERTURE_AMBIGUOUS",
            operation.source_logical_path,
            f"aperture {operation.aperture_code} does not resolve uniquely",
        )
    return matching[0]


def _replacement_lexeme(
    witness: GerberApertureDefinitionWitness,
    operation: SetGerberStandardApertureDiameter,
) -> bytes:
    old_lexeme = witness.diameter_lexeme
    fractional_digits = len(old_lexeme.partition(".")[2])
    requested = Decimal(str(operation.new_diameter_mm))
    quantum = Decimal(1).scaleb(-fractional_digits)
    try:
        quantized = requested.quantize(quantum)
    except InvalidOperation as error:
        raise AuthoringOperationError(
            "AUTHORING_GERBER_NEW_DIAMETER_PRECISION",
            operation.source_logical_path,
            "new diameter cannot be represented by the existing token precision",
        ) from error
    if quantized != requested:
        raise AuthoringOperationError(
            "AUTHORING_GERBER_NEW_DIAMETER_PRECISION",
            operation.source_logical_path,
            "new diameter cannot be represented by the existing token precision",
        )
    replacement = format(quantized, f".{fractional_digits}f")
    if len(replacement) != len(old_lexeme):
        raise AuthoringOperationError(
            "AUTHORING_GERBER_NEW_DIAMETER_WIDTH",
            operation.source_logical_path,
            "new diameter must fit the existing fixed-width decimal token",
        )
    return replacement.encode("ascii")


def _primitive_aperture_code(primitive: GraphicPrimitive) -> str | None:
    value = primitive.provenance.metadata.get("aperture_code")
    return value if isinstance(value, str) else None


def _require_plain_round_targets(
    affected: tuple[LinePrimitive | ArcPrimitive | FlashPrimitive, ...],
    operation: SetGerberStandardApertureDiameter,
) -> None:
    subject = operation.source_logical_path
    for primitive in affected:
        aperture = primitive.aperture
        if aperture.shape is not ApertureShape.CIRCLE:
            raise AuthoringOperationError(
                "AUTHORING_GERBER_APERTURE_SCOPE_UNSUPPORTED",
                subject,
                "v1 can only change a standard round aperture",
            )
        if aperture.hole_diameter_mm is not None:
            raise AuthoringOperationError(
                "AUTHORING_GERBER_APERTURE_SCOPE_UNSUPPORTED",
                subject,
                "v1 can only change a plain round aperture without a hole",
            )
        if not math.isclose(
            aperture.width_mm,
            operation.expected_diameter_mm,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise AuthoringOperationError(
                "AUTHORING_PRECONDITION_MISMATCH",
                subject,
                "parsed target primitives do not match expected_diameter_mm",
            )


def _require_supported_source(
    parsed: GerberParseResult,
    operation: SetGerberStandardApertureDiameter,
    witness: GerberApertureDefinitionWitness,
) -> tuple[LinePrimitive | ArcPrimitive | FlashPrimitive, ...]:
    subject = operation.source_logical_path
    if parsed.source_file_id != operation.source_file_id:
        raise AuthoringOperationError(
            "AUTHORING_SOURCE_ID_MISMATCH",
            subject,
            "parsed source identity does not match the request",
        )
    if parsed.original_unit is not Unit.MILLIMETRE:
        raise AuthoringOperationError(
            "AUTHORING_GERBER_UNIT_UNSUPPORTED",
            subject,
            "v1 aperture-diameter modification requires an explicit metric source",
        )
    if parsed.notation != "absolute":
        raise AuthoringOperationError(
            "AUTHORING_GERBER_NOTATION_UNSUPPORTED",
            subject,
            "v1 aperture-diameter modification requires absolute notation",
        )
    if parsed.warnings or parsed.limitations:
        raise AuthoringOperationError(
            "AUTHORING_GERBER_DIAGNOSTIC_UNSUPPORTED",
            subject,
            "v1 modification rejects sources with parser warnings or limitations",
        )
    expected = Decimal(str(operation.expected_diameter_mm))
    if witness.diameter_mm != expected:
        raise AuthoringOperationError(
            "AUTHORING_PRECONDITION_MISMATCH",
            subject,
            "aperture definition does not match expected_diameter_mm",
        )
    affected: list[LinePrimitive | ArcPrimitive | FlashPrimitive] = []
    for primitive in parsed.primitives:
        if isinstance(primitive, RegionPrimitive):
            continue
        if _primitive_aperture_code(primitive) == operation.aperture_code:
            affected.append(primitive)
    if not affected:
        raise AuthoringOperationError(
            "AUTHORING_GERBER_APERTURE_UNUSED",
            subject,
            f"aperture {operation.aperture_code} is not used by any primitive",
        )
    targets = tuple(affected)
    _require_plain_round_targets(targets, operation)
    return targets


def prepare_gerber_aperture_diameter_patch(
    payload: bytes,
    parsed: GerberParseResult,
    operation: SetGerberStandardApertureDiameter,
) -> GerberPatchCandidate:
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
        raise RuntimeError("aperture definition witness omitted byte offsets")
    output = payload[:start] + replacement + payload[end:]
    if len(output) != len(payload):  # pragma: no cover - formatter invariant
        raise RuntimeError("same-width Gerber patch changed source length")
    output_digest = hashlib.sha256(output).hexdigest()
    if output_digest == input_digest:  # pragma: no cover - request rejects no-op
        raise RuntimeError("Gerber patch did not change source bytes")
    return GerberPatchCandidate(
        payload=output,
        input_sha256=input_digest,
        output_sha256=output_digest,
        output_source_file_id=source_file_id(
            operation.source_logical_path,
            output_digest,
        ),
        input_value_span=witness.value_span,
        output_value_span=witness.value_span,
        affected_input_primitive_ids=tuple(
            primitive.primitive_id for primitive in affected
        ),
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


def _aperture_signature(
    aperture: Aperture, *, include_width: bool
) -> tuple[object, ...]:
    height = aperture.height_mm
    if aperture.shape is ApertureShape.CIRCLE:
        height = None  # normalized circles derive height from width
    return (
        aperture.shape,
        aperture.width_mm if include_width else None,
        height,
        aperture.hole_diameter_mm,
        aperture.rotation_degrees,
        aperture.vertices,
        aperture.macro_name,
    )


def _primitive_signature(
    primitive: GraphicPrimitive,
) -> tuple[object, ...]:
    if isinstance(primitive, LinePrimitive):
        geometry: tuple[object, ...] = (primitive.start, primitive.end)
    elif isinstance(primitive, ArcPrimitive):
        geometry = (
            primitive.start,
            primitive.end,
            primitive.center,
            primitive.clockwise,
        )
    elif isinstance(primitive, FlashPrimitive):
        geometry = (primitive.position,)
    else:
        geometry = (primitive.contours,)
    aperture = (
        None
        if isinstance(primitive, RegionPrimitive)
        else _aperture_signature(primitive.aperture, include_width=False)
    )
    return (
        primitive.kind,
        geometry,
        aperture,
        primitive.polarity,
        _provenance_signature(primitive.provenance),
    )


def verify_gerber_aperture_diameter_patch(
    before: GerberParseResult,
    after: GerberParseResult,
    operation: SetGerberStandardApertureDiameter,
    candidate: GerberPatchCandidate,
) -> AppliedGerberStandardApertureDiameterChange:
    """Prove the reparsed delta is exactly the requested aperture diameter."""
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
        before.file_attributes,
        before.layer_hints,
        before.generator_hints,
        before.warnings,
        before.limitations,
    )
    metadata_after = (
        after.original_unit,
        after.notation,
        after.zero_suppression,
        after.coordinate_format,
        after.file_attributes,
        after.layer_hints,
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
    if len(before.primitives) != len(after.primitives):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_FEATURE_COUNT_CHANGED",
            subject,
            "reparsed primitive count changed",
        )
    affected_after: list[str] = []
    for original, emitted in zip(before.primitives, after.primitives, strict=True):
        if _primitive_signature(original) != _primitive_signature(emitted):
            raise AuthoringOperationError(
                "AUTHORING_POSTCONDITION_PRIMITIVE_CHANGED",
                subject,
                "a protected primitive fact changed",
            )
        target = (
            not isinstance(original, RegionPrimitive)
            and _primitive_aperture_code(original) == operation.aperture_code
        )
        if isinstance(original, RegionPrimitive) or isinstance(
            emitted,
            RegionPrimitive,
        ):
            continue
        required_diameter = (
            operation.new_diameter_mm if target else original.aperture.width_mm
        )
        if not math.isclose(
            emitted.aperture.width_mm,
            required_diameter,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise AuthoringOperationError(
                "AUTHORING_POSTCONDITION_DIAMETER_MISMATCH",
                subject,
                "reparsed aperture diameters do not match the requested delta",
            )
        if target:
            affected_after.append(emitted.primitive_id)
    if len(affected_after) != len(candidate.affected_input_primitive_ids):
        raise AuthoringOperationError(
            "AUTHORING_POSTCONDITION_TARGET_COUNT_CHANGED",
            subject,
            "the target primitive set changed during emission",
        )
    return AppliedGerberStandardApertureDiameterChange(
        source_logical_path=operation.source_logical_path,
        input_source_file_id=operation.source_file_id,
        output_source_file_id=candidate.output_source_file_id,
        input_sha256=candidate.input_sha256,
        output_sha256=candidate.output_sha256,
        aperture_code=operation.aperture_code,
        old_diameter_mm=operation.expected_diameter_mm,
        new_diameter_mm=operation.new_diameter_mm,
        input_value_span=candidate.input_value_span,
        output_value_span=candidate.output_value_span,
        affected_input_primitive_ids=candidate.affected_input_primitive_ids,
        affected_output_primitive_ids=tuple(affected_after),
    )


def require_gerber_file_type(file_type: FileType, *, subject: str) -> None:
    """Keep request/source classification mismatch failures explicit."""
    if file_type is not FileType.GERBER:
        raise AuthoringOperationError(
            "AUTHORING_TARGET_TYPE_MISMATCH",
            subject,
            "set_gerber_standard_aperture_diameter requires a confirmed Gerber source",
        )
