"""Bounded public contracts for deterministic two-layer coupon generation."""

from __future__ import annotations

import json

import jsonschema
import pytest
from pydantic import ValidationError

from boardgate.authoring.generation_models import (
    GENERATION_DISCLAIMER,
    MAX_COUPON_HOLES,
    MAX_COUPON_TRACES,
    AppliedTwoLayerCouponGeneration,
    GeneratedFileEvidence,
    GenerateTwoLayerCoupon,
    GenerationRequest,
    GenerationResult,
)
from boardgate.authoring.identifiers import (
    generation_id,
    generation_operation_sha256,
    generation_request_sha256,
)
from boardgate.authoring.models import RevisionValidationEvidence
from boardgate.domain.enums import ReviewStatus
from boardgate.schemas import schema_document


def operation_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "kind": "generate_two_layer_coupon",
        "operation_version": "1.0",
        "board_width_mm": 20.0,
        "board_height_mm": 15.0,
        "holes": [
            {
                "schema_version": "1.0",
                "x_mm": 5.0,
                "y_mm": 5.0,
                "drill_diameter_mm": 0.3,
                "pad_diameter_mm": 0.8,
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
            },
        ],
        "instruction": "Generate the bounded coupon.",
    }


def admit(payload: dict[str, object]) -> GenerateTwoLayerCoupon:
    return GenerateTwoLayerCoupon.model_validate_json(json.dumps(payload))


def operation() -> GenerateTwoLayerCoupon:
    return admit(operation_payload())


def request() -> GenerationRequest:
    return GenerationRequest.model_validate_json(
        json.dumps({"schema_version": "1.0", "operation": operation_payload()})
    )


def applied_generation() -> AppliedTwoLayerCouponGeneration:
    return AppliedTwoLayerCouponGeneration(
        board_width_mm=20.0,
        board_height_mm=15.0,
        hole_count=1,
        tool_count=1,
        trace_count=1,
        drill_ids=("drill-0123456789abcdef",),
    )


def validation_evidence() -> RevisionValidationEvidence:
    return RevisionValidationEvidence(
        project_id="prj-1111111111111111",
        profile_id="default",
        profile_sha256="a" * 64,
        overall_status=ReviewStatus.READY_FOR_REVIEW,
        finding_ids=(),
    )


def generation_result() -> GenerationResult:
    return GenerationResult(
        generation_id="gen-0123456789abcdef",
        output_project_id="prj-1111111111111111",
        request_sha256="b" * 64,
        operation_sha256="c" * 64,
        implementation_version="0.1.0",
        operation=applied_generation(),
        payload_files=(
            GeneratedFileEvidence(
                logical_path="coupon-top-copper.gtl",
                sha256="d" * 64,
                size_bytes=1,
            ),
        ),
        validation=validation_evidence(),
    )


def test_valid_request_is_admitted() -> None:
    admitted = request()

    assert admitted.operation.kind == "generate_two_layer_coupon"
    assert admitted.operation.holes[0].drill_diameter_mm == 0.3
    assert admitted.operation.traces[0].copper_layers == "both"


def test_legacy_defaulted_kind_remains_schema_and_runtime_compatible() -> None:
    request_payload = {
        "schema_version": "1.0",
        "operation": operation_payload(),
    }
    operation = request_payload["operation"]
    assert isinstance(operation, dict)
    del operation["kind"]
    jsonschema.Draft202012Validator(schema_document(GenerationRequest)).validate(
        request_payload
    )

    admitted_request = GenerationRequest.model_validate_json(
        json.dumps(request_payload)
    )

    assert admitted_request.operation.kind == "generate_two_layer_coupon"

    result_payload = generation_result().model_dump(mode="json")
    applied = result_payload["operation"]
    assert isinstance(applied, dict)
    del applied["kind"]
    jsonschema.Draft202012Validator(schema_document(GenerationResult)).validate(
        result_payload
    )

    admitted_result = GenerationResult.model_validate_json(json.dumps(result_payload))

    assert admitted_result.operation.kind == "generate_two_layer_coupon"


def test_extra_keys_are_rejected() -> None:
    payload = operation_payload()
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        admit(payload)


@pytest.mark.parametrize("value", (0.400001, 5.000001, 19.599999))
def test_emission_quantum_admits_exact_multiples(value: float) -> None:
    hole = {
        "schema_version": "1.0",
        "x_mm": value,
        "y_mm": 5.0,
        "drill_diameter_mm": 0.3,
        "pad_diameter_mm": 0.8,
    }
    payload = operation_payload()
    payload["holes"] = [hole]

    assert admit(payload).holes[0].x_mm == value


@pytest.mark.parametrize("value", (0.3000001, 5.0000005))
def test_emission_quantum_rejects_sub_quantum_values(value: float) -> None:
    hole = {
        "schema_version": "1.0",
        "x_mm": value,
        "y_mm": 5.0,
        "drill_diameter_mm": 0.3,
        "pad_diameter_mm": 0.8,
    }
    payload = operation_payload()
    payload["holes"] = [hole]

    with pytest.raises(ValidationError, match="emission quantum"):
        admit(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("board_width_mm", 0.999999),
        ("board_width_mm", 500.000001),
        ("board_height_mm", 0.999999),
        ("board_height_mm", 500.000001),
    ),
)
def test_board_dimensions_are_bounded(field: str, value: float) -> None:
    payload = operation_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        admit(payload)


def test_board_dimension_bounds_are_inclusive() -> None:
    payload = operation_payload()
    payload["board_width_mm"] = 1.0
    payload["board_height_mm"] = 500.0
    payload["holes"] = []
    payload["traces"] = []

    admitted = admit(payload)
    assert admitted.board_width_mm == 1.0
    assert admitted.board_height_mm == 500.0


def _grid_holes(count: int) -> list[dict[str, object]]:
    return [
        {
            "schema_version": "1.0",
            "x_mm": 1.0 + float(index % 32),
            "y_mm": 1.0 + float(index // 32),
            "drill_diameter_mm": 0.3,
            "pad_diameter_mm": 0.8,
        }
        for index in range(count)
    ]


def test_hole_count_bound_is_inclusive() -> None:
    payload = operation_payload()
    payload["board_width_mm"] = 500.0
    payload["board_height_mm"] = 500.0
    payload["traces"] = []
    payload["holes"] = _grid_holes(MAX_COUPON_HOLES)

    assert len(admit(payload).holes) == (MAX_COUPON_HOLES)

    payload["holes"] = _grid_holes(MAX_COUPON_HOLES + 1)
    with pytest.raises(ValidationError):
        admit(payload)


def test_trace_count_bound_is_inclusive() -> None:
    trace = operation_payload()["traces"]
    assert isinstance(trace, list)
    payload = operation_payload()
    payload["traces"] = trace * MAX_COUPON_TRACES

    assert len(admit(payload).traces) == (MAX_COUPON_TRACES)

    payload["traces"] = trace * (MAX_COUPON_TRACES + 1)
    with pytest.raises(ValidationError):
        admit(payload)


def test_pad_must_exceed_drill_by_at_least_one_quantum() -> None:
    hole = {
        "schema_version": "1.0",
        "x_mm": 5.0,
        "y_mm": 5.0,
        "drill_diameter_mm": 0.3,
        "pad_diameter_mm": 0.3,
    }
    payload = operation_payload()
    payload["holes"] = [hole]

    with pytest.raises(ValidationError, match="pad_diameter_mm must be larger"):
        admit(payload)

    hole["pad_diameter_mm"] = 0.300001
    assert admit(payload).holes[0].pad_diameter_mm


def test_degenerate_traces_are_rejected() -> None:
    payload = operation_payload()
    payload["traces"] = [
        {
            "schema_version": "1.0",
            "x1_mm": 5.0,
            "y1_mm": 5.0,
            "x2_mm": 5.0,
            "y2_mm": 5.0,
            "width_mm": 0.25,
            "copper_layers": "top",
        },
    ]

    with pytest.raises(ValidationError, match="trace endpoints must differ"):
        admit(payload)


def test_overlapping_drills_are_rejected_but_tangent_drills_are_admitted() -> None:
    first = {
        "schema_version": "1.0",
        "x_mm": 5.0,
        "y_mm": 5.0,
        "drill_diameter_mm": 0.3,
        "pad_diameter_mm": 0.8,
    }
    overlapping = dict(first, x_mm=5.1)
    payload = operation_payload()
    payload["holes"] = [first, overlapping]

    with pytest.raises(ValidationError, match="drill circles must not overlap"):
        admit(payload)

    tangent = dict(first, x_mm=5.4, drill_diameter_mm=0.5, pad_diameter_mm=1.0)
    payload["holes"] = [first, tangent]
    assert len(admit(payload).holes) == 2


@pytest.mark.parametrize(
    ("x_mm", "y_mm"),
    (
        (0.3, 5.0),
        (19.7, 5.0),
        (5.0, 0.3),
        (5.0, 14.7),
    ),
)
def test_pad_circles_must_fit_inside_the_outline(x_mm: float, y_mm: float) -> None:
    payload = operation_payload()
    payload["holes"] = [
        {
            "schema_version": "1.0",
            "x_mm": x_mm,
            "y_mm": y_mm,
            "drill_diameter_mm": 0.3,
            "pad_diameter_mm": 0.8,
        },
    ]

    with pytest.raises(ValidationError, match="pad circle must fit"):
        admit(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("x1_mm", -0.000001),
        ("x2_mm", 20.000001),
        ("y1_mm", -0.000001),
        ("y2_mm", 15.000001),
    ),
)
def test_trace_footprint_must_lie_inside_the_outline(
    field: str,
    value: float,
) -> None:
    payload = operation_payload()
    traces = payload["traces"]
    assert isinstance(traces, list)
    trace = dict(traces[0])
    assert isinstance(trace, dict)
    trace[field] = value
    payload["traces"] = [trace]

    with pytest.raises(ValidationError):
        admit(payload)


def test_trace_footprint_boundary_is_inclusive() -> None:
    payload = operation_payload()
    payload["traces"] = [
        {
            "schema_version": "1.0",
            "x1_mm": 0.125,
            "y1_mm": 0.125,
            "x2_mm": 19.875,
            "y2_mm": 14.875,
            "width_mm": 0.25,
            "copper_layers": "bottom",
        },
    ]

    assert admit(payload).traces[0].x2_mm == 19.875


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("x1_mm", 0.124999),
        ("x2_mm", 19.875001),
        ("y1_mm", 0.124999),
        ("y2_mm", 14.875001),
    ),
)
def test_trace_footprint_rejects_one_quantum_beyond_the_boundary(
    field: str,
    value: float,
) -> None:
    payload = operation_payload()
    traces = payload["traces"]
    assert isinstance(traces, list)
    trace = dict(traces[0])
    assert isinstance(trace, dict)
    trace.update(
        {
            "x1_mm": 0.125,
            "y1_mm": 0.125,
            "x2_mm": 19.875,
            "y2_mm": 14.875,
            "width_mm": 0.25,
        }
    )
    trace[field] = value
    payload["traces"] = [trace]

    with pytest.raises(ValidationError, match="trace footprint"):
        admit(payload)


@pytest.mark.parametrize(
    ("drill_ids", "match"),
    (
        ((), "exactly one ID per generated hole"),
        (("drill-0123456789abcdef", "drill-0123456789abcdef"), None),
        (("drill-zzzzzzzzzzzzzzzz",), "stable BoardGate drill IDs"),
    ),
)
def test_applied_generation_drill_id_invariants(
    drill_ids: tuple[str, ...],
    match: str | None,
) -> None:
    hole_count = 2 if match is None else 1
    with pytest.raises(ValidationError):
        AppliedTwoLayerCouponGeneration(
            board_width_mm=20.0,
            board_height_mm=15.0,
            hole_count=hole_count,
            tool_count=1,
            trace_count=1,
            drill_ids=drill_ids,
        )


def test_applied_generation_requires_sorted_unique_drill_ids() -> None:
    with pytest.raises(ValidationError, match="must be sorted"):
        AppliedTwoLayerCouponGeneration(
            board_width_mm=20.0,
            board_height_mm=15.0,
            hole_count=2,
            tool_count=2,
            trace_count=1,
            drill_ids=("drill-ffffffffffffffff", "drill-0000000000000000"),
        )


@pytest.mark.parametrize(
    ("hole_count", "tool_count", "match"),
    (
        (0, 1, "zero exactly when no holes"),
        (1, 0, "zero exactly when no holes"),
        (1, 2, "cannot exceed hole_count"),
    ),
)
def test_applied_generation_tool_count_invariants(
    hole_count: int,
    tool_count: int,
    match: str,
) -> None:
    drill_ids = tuple(f"drill-{index:016x}" for index in range(hole_count))
    with pytest.raises(ValidationError, match=match):
        AppliedTwoLayerCouponGeneration(
            board_width_mm=20.0,
            board_height_mm=15.0,
            hole_count=hole_count,
            tool_count=tool_count,
            trace_count=0,
            drill_ids=drill_ids,
        )


def test_result_disclaimer_is_pinned_to_normative_text() -> None:
    result = generation_result()
    assert result.disclaimer == GENERATION_DISCLAIMER

    with pytest.raises(ValidationError, match="normative non-guarantee text"):
        GenerationResult(
            generation_id="gen-0123456789abcdef",
            output_project_id="prj-1111111111111111",
            request_sha256="b" * 64,
            operation_sha256="c" * 64,
            implementation_version="0.1.0",
            operation=applied_generation(),
            payload_files=result.payload_files,
            validation=result.validation,
            disclaimer="Manufacturability guaranteed.",
        )


def test_result_validation_project_must_match_output_project() -> None:
    with pytest.raises(ValidationError, match="must match output_project_id"):
        GenerationResult(
            generation_id="gen-0123456789abcdef",
            output_project_id="prj-2222222222222222",
            request_sha256="b" * 64,
            operation_sha256="c" * 64,
            implementation_version="0.1.0",
            operation=applied_generation(),
            payload_files=(
                GeneratedFileEvidence(
                    logical_path="coupon-top-copper.gtl",
                    sha256="d" * 64,
                    size_bytes=1,
                ),
            ),
            validation=validation_evidence(),
        )


def test_result_payload_files_must_be_unique_and_sorted() -> None:
    evidence = (
        GeneratedFileEvidence(
            logical_path="coupon-top-copper.gtl",
            sha256="d" * 64,
            size_bytes=1,
        ),
        GeneratedFileEvidence(
            logical_path="coupon-outline.gko",
            sha256="e" * 64,
            size_bytes=1,
        ),
    )
    with pytest.raises(ValidationError, match="unique and sorted"):
        GenerationResult(
            generation_id="gen-0123456789abcdef",
            output_project_id="prj-1111111111111111",
            request_sha256="b" * 64,
            operation_sha256="c" * 64,
            implementation_version="0.1.0",
            operation=applied_generation(),
            payload_files=evidence,
            validation=validation_evidence(),
        )


def test_generated_file_evidence_rejects_unsafe_logical_paths() -> None:
    with pytest.raises(ValidationError, match="normalized relative POSIX path"):
        GeneratedFileEvidence(
            logical_path="../escape.gtl",
            sha256="d" * 64,
            size_bytes=1,
        )


def test_instruction_prose_is_excluded_from_operation_identity() -> None:
    first = operation()
    second = first.model_copy(update={"instruction": "Different prose entirely."})

    assert generation_operation_sha256(first) == generation_operation_sha256(second)
    first_request = GenerationRequest(schema_version="1.0", operation=first)
    second_request = GenerationRequest(schema_version="1.0", operation=second)
    assert generation_request_sha256(first_request) != generation_request_sha256(
        second_request
    )


def test_identifier_derivation_is_stable_and_well_formed() -> None:
    admitted = request()
    operation_digest = generation_operation_sha256(admitted.operation)

    assert generation_request_sha256(admitted) == (
        "318d659c1b8edfa3303068bd8f6e43e4a891f577783a2e01601aecd474d911b7"
    )
    assert operation_digest == (
        "080c066b6b0443719695fe4b230621527ff45832c748a7d5d266b79570cac610"
    )
    assert generation_request_sha256(admitted) == generation_request_sha256(request())
    derived = generation_id(
        operation_digest=operation_digest,
        output_project_id="prj-1111111111111111",
    )
    assert derived == generation_id(
        operation_digest=operation_digest,
        output_project_id="prj-1111111111111111",
    )
    assert derived.startswith("gen-")
    assert len(derived) == 20
