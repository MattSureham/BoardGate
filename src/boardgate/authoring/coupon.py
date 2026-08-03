"""Bounded deterministic two-layer coupon writer with reparse postconditions."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass

from boardgate.authoring.generation_models import (
    GenerateTwoLayerCoupon,
    to_emission_nanometres,
)
from boardgate.domain.enums import ApertureShape, Plating, Polarity
from boardgate.domain.geometry import Unit
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.layer import FlashPrimitive, LinePrimitive
from boardgate.parsers.excellon import ExcellonParseResult
from boardgate.parsers.gerber import GerberParseResult

GENERATION_ADAPTER_POLICY_VERSION = "1.0"
MAX_GENERATED_PAYLOAD_BYTES = 1024 * 1024
OUTLINE_APERTURE_MM = 0.1
SAME_COORDINATES_NAME = "boardgate-two-layer-coupon"
TOP_COPPER_PATH = "coupon-top-copper.gtl"
BOTTOM_COPPER_PATH = "coupon-bottom-copper.gbl"
OUTLINE_PATH = "coupon-outline.gko"
PLATED_DRILL_PATH = "coupon-plated.drl"
GENERATION_PAYLOAD_PATHS = tuple(
    sorted(
        (
            TOP_COPPER_PATH,
            BOTTOM_COPPER_PATH,
            OUTLINE_PATH,
            PLATED_DRILL_PATH,
        )
    )
)


class GenerationOperationError(ValueError):
    """Typed, deterministic generation emission or postcondition failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


@dataclass(frozen=True, slots=True)
class GeneratedPayload:
    """One emitted design payload with its content-derived identity."""

    logical_path: str
    payload: bytes
    sha256: str
    source_file_id: str


def _gerber_coordinate(value_nm: int) -> str:
    return f"{value_nm:08d}"


def _fixed_mm(value_nm: int) -> str:
    return f"{value_nm / 1_000_000:.6f}"


def _guard_payload(logical_path: str, lines: list[str]) -> bytes:
    payload = ("\n".join([*lines, ""])).encode("ascii")
    if len(payload) > MAX_GENERATED_PAYLOAD_BYTES:
        raise GenerationOperationError(
            "GENERATION_PAYLOAD_SIZE_LIMIT",
            logical_path,
            f"emitted payload exceeds {MAX_GENERATED_PAYLOAD_BYTES} bytes",
        )
    return payload


def _gerber_header(comment: str, file_function: str) -> list[str]:
    return [
        f"G04 {comment}*",
        "%FSLAX46Y46*%",
        "%MOMM*%",
        f"%TF.FileFunction,{file_function}*%",
        f"%TF.SameCoordinates,{SAME_COORDINATES_NAME}*%",
    ]


def _sorted_pads(operation: GenerateTwoLayerCoupon) -> list[tuple[int, int, int]]:
    pads = [
        (
            to_emission_nanometres(hole.pad_diameter_mm),
            to_emission_nanometres(hole.x_mm),
            to_emission_nanometres(hole.y_mm),
        )
        for hole in operation.holes
    ]
    return sorted(pads)


def _sorted_traces(
    operation: GenerateTwoLayerCoupon,
    layer: str,
) -> list[tuple[int, int, int, int, int]]:
    traces = [
        (
            to_emission_nanometres(trace.width_mm),
            to_emission_nanometres(trace.x1_mm),
            to_emission_nanometres(trace.y1_mm),
            to_emission_nanometres(trace.x2_mm),
            to_emission_nanometres(trace.y2_mm),
        )
        for trace in operation.traces
        if trace.copper_layers in {layer, "both"}
    ]
    return sorted(traces)


def _emit_copper(
    logical_path: str,
    comment: str,
    file_function: str,
    pads: list[tuple[int, int, int]],
    traces: list[tuple[int, int, int, int, int]],
) -> bytes:
    lines = _gerber_header(comment, file_function)
    diameters = sorted(
        {pad_nm for pad_nm, _, _ in pads} | {width_nm for width_nm, *_ in traces}
    )
    aperture_codes = {pad_nm: 10 + index for index, pad_nm in enumerate(diameters)}
    for pad_nm in diameters:
        lines.append(f"%ADD{aperture_codes[pad_nm]}C,{_fixed_mm(pad_nm)}*%")
    current_code: int | None = None

    def select(aperture_nm: int) -> None:
        nonlocal current_code
        code = aperture_codes[aperture_nm]
        if code != current_code:
            lines.append(f"D{code}*")
            current_code = code

    for pad_nm, x_nm, y_nm in pads:
        select(pad_nm)
        lines.append(f"X{_gerber_coordinate(x_nm)}Y{_gerber_coordinate(y_nm)}D03*")
    for width_nm, x1_nm, y1_nm, x2_nm, y2_nm in traces:
        select(width_nm)
        lines.append(f"X{_gerber_coordinate(x1_nm)}Y{_gerber_coordinate(y1_nm)}D02*")
        lines.append(f"X{_gerber_coordinate(x2_nm)}Y{_gerber_coordinate(y2_nm)}D01*")
    lines.append("M02*")
    return _guard_payload(logical_path, lines)


def _emit_outline(operation: GenerateTwoLayerCoupon) -> bytes:
    width_nm = to_emission_nanometres(operation.board_width_mm)
    height_nm = to_emission_nanometres(operation.board_height_mm)
    zero = _gerber_coordinate(0)
    width = _gerber_coordinate(width_nm)
    height = _gerber_coordinate(height_nm)
    lines = _gerber_header(
        "BoardGate generated two-layer coupon outline",
        "Profile,NP",
    )
    lines.extend(
        (
            f"%ADD10C,{OUTLINE_APERTURE_MM:.3f}*%",
            "D10*",
            f"X{zero}Y{zero}D02*",
            f"X{width}Y{zero}D01*",
            f"X{width}Y{height}D01*",
            f"X{zero}Y{height}D01*",
            f"X{zero}Y{zero}D01*",
            "M02*",
        )
    )
    return _guard_payload(OUTLINE_PATH, lines)


def _emit_plated_drill(operation: GenerateTwoLayerCoupon) -> bytes:
    holes = sorted(
        (
            to_emission_nanometres(hole.drill_diameter_mm),
            to_emission_nanometres(hole.x_mm),
            to_emission_nanometres(hole.y_mm),
        )
        for hole in operation.holes
    )
    diameters = sorted({drill_nm for drill_nm, _, _ in holes})
    tool_codes = {drill_nm: index + 1 for index, drill_nm in enumerate(diameters)}
    lines = ["M48", "METRIC,TZ,0000.000000", ";TYPE=PLATED"]
    lines.extend(
        f"T{tool_codes[drill_nm]:02d}C{_fixed_mm(drill_nm)}" for drill_nm in diameters
    )
    lines.append("%")
    current_tool: int | None = None
    for drill_nm, x_nm, y_nm in holes:
        tool = tool_codes[drill_nm]
        if tool != current_tool:
            lines.append(f"T{tool:02d}")
            current_tool = tool
        lines.append(f"X{_fixed_mm(x_nm)}Y{_fixed_mm(y_nm)}")
    lines.append("M30")
    return _guard_payload(PLATED_DRILL_PATH, lines)


def emit_coupon_payloads(
    operation: GenerateTwoLayerCoupon,
) -> tuple[GeneratedPayload, ...]:
    """Emit the complete deterministic four-file coupon design payload."""
    pads = _sorted_pads(operation)
    payloads = (
        (
            TOP_COPPER_PATH,
            _emit_copper(
                TOP_COPPER_PATH,
                "BoardGate generated two-layer coupon top copper",
                "Copper,L1,Top",
                pads,
                _sorted_traces(operation, "top"),
            ),
        ),
        (
            BOTTOM_COPPER_PATH,
            _emit_copper(
                BOTTOM_COPPER_PATH,
                "BoardGate generated two-layer coupon bottom copper",
                "Copper,L2,Bot",
                pads,
                _sorted_traces(operation, "bottom"),
            ),
        ),
        (OUTLINE_PATH, _emit_outline(operation)),
        (PLATED_DRILL_PATH, _emit_plated_drill(operation)),
    )
    result = []
    for logical_path, payload in payloads:
        digest = hashlib.sha256(payload).hexdigest()
        result.append(
            GeneratedPayload(
                logical_path=logical_path,
                payload=payload,
                sha256=digest,
                source_file_id=source_file_id(logical_path, digest),
            )
        )
    return tuple(result)


def _require_clean_gerber(
    parsed: GerberParseResult,
    expected_source_file_id: str,
) -> None:
    subject = "<generated-gerber>"
    if parsed.source_file_id != expected_source_file_id:
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_SOURCE_MISMATCH",
            subject,
            "reparsed generated source identity is inconsistent",
        )
    if parsed.original_unit is not Unit.MILLIMETRE or parsed.notation != "absolute":
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_METADATA_MISMATCH",
            subject,
            "reparsed generated Gerber is not metric/absolute",
        )
    if parsed.warnings or parsed.limitations:
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_DIAGNOSTICS",
            subject,
            "reparsed generated Gerber produced warnings or limitations",
        )


def _close_mm(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-9)


def _expected_segments(
    operation: GenerateTwoLayerCoupon,
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    width = operation.board_width_mm
    height = operation.board_height_mm
    segments = (
        ((0.0, 0.0), (width, 0.0)),
        ((width, 0.0), (width, height)),
        ((width, height), (0.0, height)),
        ((0.0, height), (0.0, 0.0)),
    )
    return tuple(sorted(segments))


def verify_coupon_outline(
    operation: GenerateTwoLayerCoupon,
    parsed: GerberParseResult,
    *,
    expected_source_file_id: str,
) -> None:
    """Prove the reparsed outline is exactly the requested rectangle."""
    _require_clean_gerber(parsed, expected_source_file_id)
    subject = OUTLINE_PATH
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for primitive in parsed.primitives:
        if not isinstance(primitive, LinePrimitive):
            raise GenerationOperationError(
                "GENERATION_POSTCONDITION_OUTLINE_PRIMITIVE",
                subject,
                "reparsed outline contains an unexpected primitive",
            )
        if (
            primitive.polarity is not Polarity.DARK
            or primitive.aperture.shape is not ApertureShape.CIRCLE
            or not _close_mm(primitive.aperture.width_mm, OUTLINE_APERTURE_MM)
        ):
            raise GenerationOperationError(
                "GENERATION_POSTCONDITION_OUTLINE_PRIMITIVE",
                subject,
                "reparsed outline contains an unexpected primitive",
            )
        segments.append(
            (
                (primitive.start.x, primitive.start.y),
                (primitive.end.x, primitive.end.y),
            )
        )
    expected = _expected_segments(operation)
    if len(segments) != len(expected) or any(
        not (
            _close_mm(actual[0][0], wanted[0][0])
            and _close_mm(actual[0][1], wanted[0][1])
            and _close_mm(actual[1][0], wanted[1][0])
            and _close_mm(actual[1][1], wanted[1][1])
        )
        for actual, wanted in zip(sorted(segments), expected, strict=True)
    ):
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_OUTLINE_GEOMETRY",
            subject,
            "reparsed outline segments do not match the requested rectangle",
        )


def verify_coupon_copper(
    operation: GenerateTwoLayerCoupon,
    parsed: GerberParseResult,
    *,
    expected_source_file_id: str,
    logical_path: str,
    layer: str,
) -> None:
    """Prove the reparsed copper layer contains exactly the requested geometry."""
    _require_clean_gerber(parsed, expected_source_file_id)
    expected_flashes = sorted(
        (hole.x_mm, hole.y_mm, hole.pad_diameter_mm) for hole in operation.holes
    )
    expected_traces = sorted(
        (trace.x1_mm, trace.y1_mm, trace.x2_mm, trace.y2_mm, trace.width_mm)
        for trace in operation.traces
        if trace.copper_layers in {layer, "both"}
    )
    actual_flashes: list[tuple[float, float, float]] = []
    actual_traces: list[tuple[float, float, float, float, float]] = []
    for primitive in parsed.primitives:
        if not isinstance(primitive, (FlashPrimitive, LinePrimitive)):
            raise GenerationOperationError(
                "GENERATION_POSTCONDITION_COPPER_PRIMITIVE",
                logical_path,
                "reparsed copper layer contains an unexpected primitive",
            )
        if (
            primitive.polarity is not Polarity.DARK
            or primitive.aperture.shape is not ApertureShape.CIRCLE
        ):
            raise GenerationOperationError(
                "GENERATION_POSTCONDITION_COPPER_PRIMITIVE",
                logical_path,
                "reparsed copper layer contains an unexpected primitive",
            )
        if isinstance(primitive, FlashPrimitive):
            actual_flashes.append(
                (
                    primitive.position.x,
                    primitive.position.y,
                    primitive.aperture.width_mm,
                )
            )
        elif isinstance(primitive, LinePrimitive):
            actual_traces.append(
                (
                    primitive.start.x,
                    primitive.start.y,
                    primitive.end.x,
                    primitive.end.y,
                    primitive.aperture.width_mm,
                )
            )
        else:
            raise GenerationOperationError(
                "GENERATION_POSTCONDITION_COPPER_PRIMITIVE",
                logical_path,
                "reparsed copper layer contains an unexpected primitive",
            )

    def _matches(
        actual: Sequence[tuple[float, ...]],
        expected: Sequence[tuple[float, ...]],
    ) -> bool:
        return len(actual) == len(expected) and all(
            len(seen) == len(wanted)
            and all(
                _close_mm(observed, required)
                for observed, required in zip(seen, wanted, strict=True)
            )
            for seen, wanted in zip(sorted(actual), expected, strict=True)
        )

    if not _matches(actual_flashes, expected_flashes):
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_COPPER_GEOMETRY",
            logical_path,
            "reparsed copper pads do not match the requested holes",
        )
    if not _matches(actual_traces, expected_traces):
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_COPPER_GEOMETRY",
            logical_path,
            "reparsed copper traces do not match the requested traces",
        )


def verify_coupon_drills(
    operation: GenerateTwoLayerCoupon,
    parsed: ExcellonParseResult,
    *,
    expected_source_file_id: str,
) -> tuple[str, ...]:
    """Prove the reparsed drill file contains exactly the requested holes."""
    subject = PLATED_DRILL_PATH
    if parsed.source_file_id != expected_source_file_id:
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_SOURCE_MISMATCH",
            subject,
            "reparsed generated source identity is inconsistent",
        )
    if parsed.original_unit is not Unit.MILLIMETRE or parsed.notation != "absolute":
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_METADATA_MISMATCH",
            subject,
            "reparsed generated Excellon is not metric/absolute",
        )
    if parsed.warnings or parsed.limitations:
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_DIAGNOSTICS",
            subject,
            "reparsed generated Excellon produced warnings or limitations",
        )
    if parsed.slots:
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_SLOT_PRESENT",
            subject,
            "reparsed generated Excellon contains an unexpected slot",
        )
    expected = sorted(
        (hole.x_mm, hole.y_mm, hole.drill_diameter_mm) for hole in operation.holes
    )
    actual = sorted(
        (drill.position.x, drill.position.y, drill.diameter_mm)
        for drill in parsed.drills
    )
    if len(actual) != len(expected) or any(
        not (
            _close_mm(seen[0], wanted[0])
            and _close_mm(seen[1], wanted[1])
            and _close_mm(seen[2], wanted[2])
        )
        for seen, wanted in zip(actual, expected, strict=True)
    ):
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_DRILL_GEOMETRY",
            subject,
            "reparsed drills do not match the requested holes",
        )
    if any(drill.plating is not Plating.PLATED for drill in parsed.drills):
        raise GenerationOperationError(
            "GENERATION_POSTCONDITION_PLATING_MISMATCH",
            subject,
            "reparsed drills lost the explicit plated evidence",
        )
    return tuple(sorted(drill.drill_id for drill in parsed.drills))
