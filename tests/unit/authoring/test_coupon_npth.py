"""Mixed plated/NPTH coupon emission and reparse postconditions."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

import boardgate.authoring.coupon as coupon_module
from boardgate.application.parser_runner import ParserJob, parse_job
from boardgate.authoring.coupon import (
    BOTTOM_COPPER_PATH,
    NON_PLATED_DRILL_PATH,
    NPTH_GENERATION_ADAPTER_POLICY_VERSION,
    NPTH_GENERATION_PAYLOAD_PATHS,
    PLATED_DRILL_PATH,
    TOP_COPPER_PATH,
    GeneratedPayload,
    GenerationOperationError,
    emit_coupon_with_npth_payloads,
    verify_coupon_with_npth_copper,
    verify_coupon_with_npth_drills,
)
from boardgate.authoring.generation_models import (
    CouponHole,
    CouponNpthHole,
    GenerateTwoLayerCouponWithNpth,
)
from boardgate.domain.drill import DrillSlot
from boardgate.domain.enums import FileType, Plating
from boardgate.domain.geometry import Point, Unit
from boardgate.domain.layer import FlashPrimitive
from boardgate.parsers.excellon import ExcellonParseResult
from boardgate.parsers.gerber import GerberParseResult
from boardgate.parsers.models import DiagnosticLevel, ParserDiagnostic


def operation_payload() -> dict[str, object]:
    """Return one representative public mixed-drill operation payload."""
    return {
        "schema_version": "1.0",
        "kind": "generate_two_layer_coupon_with_npth",
        "operation_version": "1.0",
        "board_width_mm": 20.0,
        "board_height_mm": 15.0,
        "plated_holes": [
            {
                "schema_version": "1.0",
                "x_mm": 5.0,
                "y_mm": 5.0,
                "drill_diameter_mm": 0.4,
                "pad_diameter_mm": 1.0,
            },
            {
                "schema_version": "1.0",
                "x_mm": 7.0,
                "y_mm": 8.0,
                "drill_diameter_mm": 0.5,
                "pad_diameter_mm": 1.2,
            },
        ],
        "non_plated_holes": [
            {
                "schema_version": "1.0",
                "x_mm": 10.0,
                "y_mm": 5.0,
                "drill_diameter_mm": 0.6,
            },
            {
                "schema_version": "1.0",
                "x_mm": 12.0,
                "y_mm": 8.0,
                "drill_diameter_mm": 0.8,
            },
        ],
        "traces": [
            {
                "schema_version": "1.0",
                "x1_mm": 1.0,
                "y1_mm": 1.0,
                "x2_mm": 19.0,
                "y2_mm": 1.0,
                "width_mm": 0.25,
                "copper_layers": "both",
            }
        ],
        "instruction": "Generate a bounded coupon with explicit NPTH evidence.",
    }


def operation() -> GenerateTwoLayerCouponWithNpth:
    """Admit the representative payload through the public strict model."""
    return GenerateTwoLayerCouponWithNpth.model_validate_json(
        json.dumps(operation_payload())
    )


def _payloads() -> dict[str, GeneratedPayload]:
    return {
        payload.logical_path: payload
        for payload in emit_coupon_with_npth_payloads(operation())
    }


def _reparse(
    logical_path: str,
    file_type: FileType,
) -> ExcellonParseResult | GerberParseResult:
    payload = _payloads()[logical_path]
    parsed = parse_job(
        ParserJob(
            source_file_id=payload.source_file_id,
            logical_path=payload.logical_path,
            file_type=file_type,
            payload=payload.payload,
        )
    )
    assert isinstance(parsed, (ExcellonParseResult, GerberParseResult))
    return parsed


def _drill_case(
    logical_path: str,
) -> tuple[Sequence[CouponHole | CouponNpthHole], Plating]:
    admitted = operation()
    if logical_path == PLATED_DRILL_PATH:
        return admitted.plated_holes, Plating.PLATED
    assert logical_path == NON_PLATED_DRILL_PATH
    return admitted.non_plated_holes, Plating.NON_PLATED


def _verify_drills(
    logical_path: str,
    parsed: ExcellonParseResult,
) -> tuple[str, ...]:
    holes, expected_plating = _drill_case(logical_path)
    payload = _payloads()[logical_path]
    return verify_coupon_with_npth_drills(
        holes,
        parsed,
        expected_source_file_id=payload.source_file_id,
        logical_path=logical_path,
        expected_plating=expected_plating,
    )


def test_npth_emission_is_deterministic_with_exact_five_path_inventory() -> None:
    first = emit_coupon_with_npth_payloads(operation())
    second = emit_coupon_with_npth_payloads(operation())

    assert first == second
    assert len(first) == 5
    assert len({payload.logical_path for payload in first}) == 5
    assert tuple(sorted(payload.logical_path for payload in first)) == (
        NPTH_GENERATION_PAYLOAD_PATHS
    )
    assert all(payload.sha256 for payload in first)
    assert all(payload.source_file_id for payload in first)
    assert NPTH_GENERATION_ADAPTER_POLICY_VERSION == "1.1"


def test_npth_emission_uses_explicit_distinct_plating_markers() -> None:
    payloads = _payloads()
    plated = payloads[PLATED_DRILL_PATH].payload
    non_plated = payloads[NON_PLATED_DRILL_PATH].payload

    assert b";TYPE=PLATED\n" in plated
    assert b";TYPE=NON_PLATED\n" not in plated
    assert b";TYPE=NON_PLATED\n" in non_plated
    assert b";TYPE=PLATED\n" not in non_plated


@pytest.mark.parametrize(
    ("logical_path", "layer"),
    (
        (TOP_COPPER_PATH, "top"),
        (BOTTOM_COPPER_PATH, "bottom"),
    ),
)
def test_npth_copper_contains_only_plated_hole_pads(
    logical_path: str,
    layer: str,
) -> None:
    parsed = _reparse(logical_path, FileType.GERBER)
    assert isinstance(parsed, GerberParseResult)
    admitted = operation()
    payload = _payloads()[logical_path]

    verify_coupon_with_npth_copper(
        admitted,
        parsed,
        expected_source_file_id=payload.source_file_id,
        logical_path=logical_path,
        layer=layer,
    )
    flashes = tuple(
        primitive
        for primitive in parsed.primitives
        if isinstance(primitive, FlashPrimitive)
    )
    actual = sorted(
        (
            flash.position.x,
            flash.position.y,
            flash.aperture.width_mm,
        )
        for flash in flashes
    )
    expected = sorted(
        (hole.x_mm, hole.y_mm, hole.pad_diameter_mm) for hole in admitted.plated_holes
    )
    npth_positions = {(hole.x_mm, hole.y_mm) for hole in admitted.non_plated_holes}

    assert actual == expected
    assert all(
        (flash.position.x, flash.position.y) not in npth_positions for flash in flashes
    )


@pytest.mark.parametrize(
    ("logical_path", "expected_plating"),
    (
        (PLATED_DRILL_PATH, Plating.PLATED),
        (NON_PLATED_DRILL_PATH, Plating.NON_PLATED),
    ),
)
def test_both_drill_payloads_reparse_without_hints_with_exact_semantics(
    logical_path: str,
    expected_plating: Plating,
) -> None:
    parsed = _reparse(logical_path, FileType.EXCELLON)
    assert isinstance(parsed, ExcellonParseResult)
    holes, _ = _drill_case(logical_path)

    drill_ids = _verify_drills(logical_path, parsed)

    assert parsed.original_unit is Unit.MILLIMETRE
    assert parsed.notation == "absolute"
    assert parsed.generator_hints == ()
    assert parsed.warnings == ()
    assert parsed.limitations == ()
    assert parsed.slots == ()
    assert tuple(sorted(drill.drill_id for drill in parsed.drills)) == drill_ids
    assert sorted(
        (
            drill.position.x,
            drill.position.y,
            drill.diameter_mm,
            drill.plating,
        )
        for drill in parsed.drills
    ) == sorted(
        (
            hole.x_mm,
            hole.y_mm,
            hole.drill_diameter_mm,
            expected_plating,
        )
        for hole in holes
    )


@pytest.mark.parametrize(
    "logical_path",
    (PLATED_DRILL_PATH, NON_PLATED_DRILL_PATH),
)
def test_mixed_drill_postcondition_rejects_source_identity_mismatch(
    logical_path: str,
) -> None:
    parsed = _reparse(logical_path, FileType.EXCELLON)
    assert isinstance(parsed, ExcellonParseResult)
    holes, expected_plating = _drill_case(logical_path)

    with pytest.raises(GenerationOperationError) as caught:
        verify_coupon_with_npth_drills(
            holes,
            parsed,
            expected_source_file_id="src-0000000000000000",
            logical_path=logical_path,
            expected_plating=expected_plating,
        )

    assert caught.value.code == "GENERATION_POSTCONDITION_SOURCE_MISMATCH"
    assert caught.value.subject == logical_path


@pytest.mark.parametrize("field", ("warnings", "limitations"))
def test_mixed_drill_postcondition_rejects_parser_diagnostics(field: str) -> None:
    parsed = _reparse(NON_PLATED_DRILL_PATH, FileType.EXCELLON)
    assert isinstance(parsed, ExcellonParseResult)
    diagnostic = ParserDiagnostic(
        code="EXCELLON_TEST_DIAGNOSTIC",
        level=(
            DiagnosticLevel.WARNING
            if field == "warnings"
            else DiagnosticLevel.LIMITATION
        ),
        message="simulated generated-payload diagnostic",
    )
    tampered = parsed.model_copy(update={field: (diagnostic,)})

    with pytest.raises(GenerationOperationError) as caught:
        _verify_drills(NON_PLATED_DRILL_PATH, tampered)

    assert caught.value.code == "GENERATION_POSTCONDITION_DIAGNOSTICS"
    assert caught.value.subject == NON_PLATED_DRILL_PATH


def test_mixed_drill_postcondition_rejects_slots() -> None:
    parsed = _reparse(NON_PLATED_DRILL_PATH, FileType.EXCELLON)
    assert isinstance(parsed, ExcellonParseResult)
    drill = parsed.drills[0]
    slot = DrillSlot(
        slot_id="slot-generated-postcondition-test",
        start=drill.position,
        end=Point(x=drill.position.x + 1.0, y=drill.position.y),
        width_mm=drill.diameter_mm,
        tool_code=drill.tool_code,
        plating=drill.plating,
        provenance=drill.provenance,
    )
    tampered = parsed.model_copy(update={"slots": (slot,)})

    with pytest.raises(GenerationOperationError) as caught:
        _verify_drills(NON_PLATED_DRILL_PATH, tampered)

    assert caught.value.code == "GENERATION_POSTCONDITION_SLOT_PRESENT"
    assert caught.value.subject == NON_PLATED_DRILL_PATH


@pytest.mark.parametrize(
    ("logical_path", "replacement"),
    (
        (PLATED_DRILL_PATH, Plating.NON_PLATED),
        (NON_PLATED_DRILL_PATH, Plating.PLATED),
        (PLATED_DRILL_PATH, Plating.UNKNOWN),
        (NON_PLATED_DRILL_PATH, Plating.UNKNOWN),
    ),
)
def test_mixed_drill_postcondition_rejects_swapped_or_unknown_plating(
    logical_path: str,
    replacement: Plating,
) -> None:
    parsed = _reparse(logical_path, FileType.EXCELLON)
    assert isinstance(parsed, ExcellonParseResult)
    tampered = parsed.model_copy(
        update={
            "drills": tuple(
                drill.model_copy(update={"plating": replacement})
                for drill in parsed.drills
            )
        }
    )

    with pytest.raises(GenerationOperationError) as caught:
        _verify_drills(logical_path, tampered)

    assert caught.value.code == "GENERATION_POSTCONDITION_PLATING_MISMATCH"
    assert caught.value.subject == logical_path


def test_npth_payload_size_limit_is_inclusive_and_rejects_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = emit_coupon_with_npth_payloads(operation())
    largest_size = max(len(payload.payload) for payload in expected)

    monkeypatch.setattr(
        coupon_module,
        "MAX_GENERATED_PAYLOAD_BYTES",
        largest_size,
    )
    assert emit_coupon_with_npth_payloads(operation()) == expected

    monkeypatch.setattr(
        coupon_module,
        "MAX_GENERATED_PAYLOAD_BYTES",
        largest_size - 1,
    )
    with pytest.raises(GenerationOperationError) as caught:
        emit_coupon_with_npth_payloads(operation())

    assert caught.value.code == "GENERATION_PAYLOAD_SIZE_LIMIT"
