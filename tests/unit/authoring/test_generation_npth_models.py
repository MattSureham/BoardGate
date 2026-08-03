"""Public contract tests for the mixed plated/NPTH coupon operation."""

from __future__ import annotations

import json

import jsonschema
import pytest
from pydantic import ValidationError

from boardgate.authoring.generation_models import (
    MAX_COUPON_HOLES,
    AppliedTwoLayerCouponWithNpthGeneration,
    CouponNpthHole,
    GenerateTwoLayerCouponWithNpth,
    GenerationRequest,
    GenerationResult,
)
from boardgate.authoring.generation_request import (
    GenerationRequestError,
    load_generation_request_bytes,
)
from boardgate.schemas import schema_document


def _plated_hole(
    *,
    x_mm: float = 5.0,
    y_mm: float = 5.0,
    drill_diameter_mm: float = 0.4,
    pad_diameter_mm: float = 1.0,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "x_mm": x_mm,
        "y_mm": y_mm,
        "drill_diameter_mm": drill_diameter_mm,
        "pad_diameter_mm": pad_diameter_mm,
    }


def _non_plated_hole(
    *,
    x_mm: float = 10.0,
    y_mm: float = 5.0,
    drill_diameter_mm: float = 0.6,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "x_mm": x_mm,
        "y_mm": y_mm,
        "drill_diameter_mm": drill_diameter_mm,
    }


def _trace() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "x1_mm": 1.0,
        "y1_mm": 1.0,
        "x2_mm": 19.0,
        "y2_mm": 1.0,
        "width_mm": 0.25,
        "copper_layers": "both",
    }


def _operation_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "kind": "generate_two_layer_coupon_with_npth",
        "operation_version": "1.0",
        "board_width_mm": 20.0,
        "board_height_mm": 15.0,
        "plated_holes": [_plated_hole()],
        "non_plated_holes": [_non_plated_hole()],
        "traces": [_trace()],
        "instruction": "Generate a bounded coupon with one NPTH hole.",
    }


def _request_payload() -> dict[str, object]:
    return {"schema_version": "1.0", "operation": _operation_payload()}


def _admit_operation(
    payload: dict[str, object],
) -> GenerateTwoLayerCouponWithNpth:
    return GenerateTwoLayerCouponWithNpth.model_validate_json(json.dumps(payload))


def _admit_request(payload: dict[str, object]) -> GenerationRequest:
    return GenerationRequest.model_validate_json(json.dumps(payload))


def _applied_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "kind": "generate_two_layer_coupon_with_npth",
        "operation_version": "1.0",
        "adapter_id": "boardgate-two-layer-coupon-writer",
        "adapter_policy_version": "1.1",
        "board_width_mm": 20.0,
        "board_height_mm": 15.0,
        "plated_hole_count": 2,
        "plated_tool_count": 1,
        "non_plated_hole_count": 1,
        "non_plated_tool_count": 1,
        "trace_count": 1,
        "plated_drill_ids": [
            "drill-0000000000000001",
            "drill-0000000000000002",
        ],
        "non_plated_drill_ids": ["drill-0000000000000003"],
    }


def _admit_applied(
    payload: dict[str, object],
) -> AppliedTwoLayerCouponWithNpthGeneration:
    return AppliedTwoLayerCouponWithNpthGeneration.model_validate_json(
        json.dumps(payload)
    )


def _result_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "generation_id": "gen-0123456789abcdef",
        "output_project_id": "prj-1111111111111111",
        "request_sha256": "a" * 64,
        "operation_sha256": "b" * 64,
        "implementation_version": "0.1.0",
        "operation": _applied_payload(),
        "payload_files": [
            {
                "schema_version": "1.0",
                "logical_path": "coupon-non-plated.drl",
                "sha256": "c" * 64,
                "size_bytes": 1,
            }
        ],
        "validation": {
            "schema_version": "1.0",
            "review_artifact_directory": "validation",
            "project_id": "prj-1111111111111111",
            "profile_id": "default",
            "profile_sha256": "d" * 64,
            "overall_status": "READY_FOR_REVIEW",
            "finding_ids": [],
        },
    }


def test_public_request_and_loader_admit_the_exact_npth_operation() -> None:
    payload = _request_payload()

    direct = _admit_request(payload)
    loaded = load_generation_request_bytes(
        json.dumps(payload).encode(),
        source="coupon.json",
    )

    assert isinstance(direct.operation, GenerateTwoLayerCouponWithNpth)
    assert isinstance(loaded.operation, GenerateTwoLayerCouponWithNpth)
    assert loaded == direct
    assert direct.operation.kind == "generate_two_layer_coupon_with_npth"
    assert direct.operation.operation_version == "1.0"


@pytest.mark.parametrize("field", ("plated_holes", "non_plated_holes"))
def test_each_drill_population_requires_at_least_one_hole(field: str) -> None:
    payload = _operation_payload()
    payload[field] = []

    with pytest.raises(ValidationError):
        _admit_operation(payload)


def _grid_plated_holes(count: int) -> list[dict[str, object]]:
    return [
        _plated_hole(
            x_mm=1.0 + float(index % 32),
            y_mm=1.0 + float(index // 32),
            drill_diameter_mm=0.2,
            pad_diameter_mm=0.5,
        )
        for index in range(count)
    ]


def _grid_non_plated_holes(count: int) -> list[dict[str, object]]:
    return [
        _non_plated_hole(
            x_mm=1.0 + float(index % 32),
            y_mm=1.0 + float(index // 32),
            drill_diameter_mm=0.2,
        )
        for index in range(count)
    ]


def test_combined_hole_limit_is_inclusive_and_rejects_n_plus_one() -> None:
    payload = _operation_payload()
    payload["board_width_mm"] = 500.0
    payload["board_height_mm"] = 500.0
    payload["traces"] = []
    payload["plated_holes"] = _grid_plated_holes(MAX_COUPON_HOLES - 1)
    payload["non_plated_holes"] = [
        _non_plated_hole(x_mm=100.0, y_mm=100.0, drill_diameter_mm=0.2)
    ]

    admitted = _admit_operation(payload)
    assert (
        len(admitted.plated_holes) + len(admitted.non_plated_holes) == MAX_COUPON_HOLES
    )

    payload["plated_holes"] = _grid_plated_holes(MAX_COUPON_HOLES)
    with pytest.raises(ValidationError, match="combined plated and non-plated"):
        _admit_operation(payload)


def test_combined_hole_limit_is_inclusive_with_npth_as_larger_population() -> None:
    payload = _operation_payload()
    payload["board_width_mm"] = 500.0
    payload["board_height_mm"] = 500.0
    payload["traces"] = []
    payload["plated_holes"] = [
        _plated_hole(
            x_mm=100.0,
            y_mm=100.0,
            drill_diameter_mm=0.2,
            pad_diameter_mm=0.5,
        )
    ]
    payload["non_plated_holes"] = _grid_non_plated_holes(MAX_COUPON_HOLES - 1)

    admitted = _admit_operation(payload)

    assert (
        len(admitted.plated_holes) + len(admitted.non_plated_holes) == MAX_COUPON_HOLES
    )


@pytest.mark.parametrize(
    ("field", "holes"),
    (
        ("plated_holes", _grid_plated_holes(MAX_COUPON_HOLES + 1)),
        ("non_plated_holes", _grid_non_plated_holes(MAX_COUPON_HOLES + 1)),
    ),
)
def test_each_hole_population_rejects_its_field_n_plus_one(
    field: str,
    holes: list[dict[str, object]],
) -> None:
    payload = _operation_payload()
    payload["board_width_mm"] = 500.0
    payload["board_height_mm"] = 500.0
    payload["traces"] = []
    payload[field] = holes

    with pytest.raises(ValidationError):
        _admit_operation(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("x_mm", 10.0000001),
        ("y_mm", 5.0000001),
        ("drill_diameter_mm", 0.6000001),
    ),
)
def test_npth_coordinates_and_diameter_require_the_exact_emission_quantum(
    field: str,
    value: float,
) -> None:
    payload = _non_plated_hole()
    payload[field] = value

    with pytest.raises(ValidationError, match="emission quantum"):
        CouponNpthHole.model_validate_json(json.dumps(payload))


def test_npth_hole_admits_an_exact_one_quantum_increment() -> None:
    payload = _non_plated_hole(drill_diameter_mm=0.600001)

    admitted = CouponNpthHole.model_validate_json(json.dumps(payload))

    assert admitted.drill_diameter_mm == 0.600001


@pytest.mark.parametrize(
    ("x_mm", "y_mm"),
    (
        (0.5, 5.0),
        (19.5, 5.0),
        (5.0, 0.5),
        (5.0, 14.5),
    ),
)
def test_plated_pad_containment_boundary_is_inclusive(
    x_mm: float,
    y_mm: float,
) -> None:
    payload = _operation_payload()
    payload["plated_holes"] = [_plated_hole(x_mm=x_mm, y_mm=y_mm)]

    assert _admit_operation(payload).plated_holes[0].pad_diameter_mm == 1.0


@pytest.mark.parametrize(
    ("x_mm", "y_mm"),
    (
        (0.499999, 5.0),
        (19.500001, 5.0),
        (5.0, 0.499999),
        (5.0, 14.500001),
    ),
)
def test_plated_pad_containment_rejects_one_quantum_outside(
    x_mm: float,
    y_mm: float,
) -> None:
    payload = _operation_payload()
    payload["plated_holes"] = [_plated_hole(x_mm=x_mm, y_mm=y_mm)]

    with pytest.raises(ValidationError, match="plated-hole pad circle"):
        _admit_operation(payload)


@pytest.mark.parametrize(
    ("x_mm", "y_mm"),
    (
        (0.3, 5.0),
        (19.7, 5.0),
        (10.0, 0.3),
        (10.0, 14.7),
    ),
)
def test_npth_drill_containment_boundary_is_inclusive(
    x_mm: float,
    y_mm: float,
) -> None:
    payload = _operation_payload()
    payload["non_plated_holes"] = [_non_plated_hole(x_mm=x_mm, y_mm=y_mm)]

    assert _admit_operation(payload).non_plated_holes[0].drill_diameter_mm == 0.6


@pytest.mark.parametrize(
    ("x_mm", "y_mm"),
    (
        (0.299999, 5.0),
        (19.700001, 5.0),
        (10.0, 0.299999),
        (10.0, 14.700001),
    ),
)
def test_npth_drill_containment_rejects_one_quantum_outside(
    x_mm: float,
    y_mm: float,
) -> None:
    payload = _operation_payload()
    payload["non_plated_holes"] = [_non_plated_hole(x_mm=x_mm, y_mm=y_mm)]

    with pytest.raises(ValidationError, match="non-plated drill circle"):
        _admit_operation(payload)


def test_cross_population_tangent_drills_are_admitted() -> None:
    payload = _operation_payload()
    payload["plated_holes"] = [_plated_hole(drill_diameter_mm=0.4)]
    payload["non_plated_holes"] = [
        _non_plated_hole(x_mm=5.5, y_mm=5.0, drill_diameter_mm=0.6)
    ]

    assert len(_admit_operation(payload).non_plated_holes) == 1


def test_cross_population_overlap_by_one_quantum_is_rejected() -> None:
    payload = _operation_payload()
    payload["plated_holes"] = [_plated_hole(drill_diameter_mm=0.4)]
    payload["non_plated_holes"] = [
        _non_plated_hole(x_mm=5.499999, y_mm=5.0, drill_diameter_mm=0.6)
    ]

    with pytest.raises(ValidationError, match="drill circles must not overlap"):
        _admit_operation(payload)


@pytest.mark.parametrize(
    ("field", "first", "second"),
    (
        (
            "plated_holes",
            _plated_hole(x_mm=5.0, drill_diameter_mm=0.4),
            _plated_hole(x_mm=5.4, drill_diameter_mm=0.4),
        ),
        (
            "non_plated_holes",
            _non_plated_hole(x_mm=10.0, drill_diameter_mm=0.6),
            _non_plated_hole(x_mm=10.6, drill_diameter_mm=0.6),
        ),
    ),
)
def test_same_population_tangent_drills_are_admitted(
    field: str,
    first: dict[str, object],
    second: dict[str, object],
) -> None:
    payload = _operation_payload()
    payload[field] = [first, second]

    assert len(getattr(_admit_operation(payload), field)) == 2


@pytest.mark.parametrize(
    ("field", "first", "second"),
    (
        (
            "plated_holes",
            _plated_hole(x_mm=5.0, drill_diameter_mm=0.4),
            _plated_hole(x_mm=5.399999, drill_diameter_mm=0.4),
        ),
        (
            "non_plated_holes",
            _non_plated_hole(x_mm=10.0, drill_diameter_mm=0.6),
            _non_plated_hole(x_mm=10.599999, drill_diameter_mm=0.6),
        ),
    ),
)
def test_same_population_overlap_by_one_quantum_is_rejected(
    field: str,
    first: dict[str, object],
    second: dict[str, object],
) -> None:
    payload = _operation_payload()
    payload[field] = [first, second]

    with pytest.raises(ValidationError, match="drill circles must not overlap"):
        _admit_operation(payload)


def test_npth_operation_trace_footprint_boundary_is_inclusive() -> None:
    payload = _operation_payload()
    payload["traces"] = [
        {
            "schema_version": "1.0",
            "x1_mm": 0.125,
            "y1_mm": 0.125,
            "x2_mm": 19.875,
            "y2_mm": 14.875,
            "width_mm": 0.25,
            "copper_layers": "bottom",
        }
    ]

    assert _admit_operation(payload).traces[0].width_mm == 0.25


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("x1_mm", 0.124999),
        ("x2_mm", 19.875001),
        ("y1_mm", 0.124999),
        ("y2_mm", 14.875001),
    ),
)
def test_npth_operation_rejects_trace_footprint_one_quantum_outside(
    field: str,
    value: float,
) -> None:
    trace = {
        "schema_version": "1.0",
        "x1_mm": 0.125,
        "y1_mm": 0.125,
        "x2_mm": 19.875,
        "y2_mm": 14.875,
        "width_mm": 0.25,
        "copper_layers": "bottom",
    }
    trace[field] = value
    payload = _operation_payload()
    payload["traces"] = [trace]

    with pytest.raises(ValidationError, match="trace footprint"):
        _admit_operation(payload)


def test_npth_trace_limit_is_inclusive_and_rejects_n_plus_one() -> None:
    payload = _operation_payload()
    trace = _trace()
    payload["traces"] = [trace] * 4096

    assert len(_admit_operation(payload).traces) == 4096

    payload["traces"] = [trace] * 4097
    with pytest.raises(ValidationError):
        _admit_operation(payload)


def test_applied_npth_evidence_admits_sorted_disjoint_populations() -> None:
    admitted = _admit_applied(_applied_payload())

    assert admitted.kind == "generate_two_layer_coupon_with_npth"
    assert admitted.operation_version == "1.0"
    assert admitted.adapter_policy_version == "1.1"
    assert admitted.plated_hole_count == 2
    assert admitted.non_plated_hole_count == 1


@pytest.mark.parametrize(
    "field",
    (
        "plated_hole_count",
        "plated_tool_count",
        "non_plated_hole_count",
        "non_plated_tool_count",
    ),
)
def test_applied_npth_population_counts_require_at_least_one(field: str) -> None:
    payload = _applied_payload()
    payload[field] = 0

    with pytest.raises(ValidationError):
        _admit_applied(payload)


@pytest.mark.parametrize("population", ("plated", "non_plated"))
def test_applied_npth_evidence_requires_one_id_per_hole(population: str) -> None:
    payload = _applied_payload()
    payload[f"{population}_drill_ids"] = []

    with pytest.raises(ValidationError, match=f"{population}_drill_ids"):
        _admit_applied(payload)


@pytest.mark.parametrize("population", ("plated", "non_plated"))
def test_applied_npth_evidence_requires_unique_ids(population: str) -> None:
    payload = _applied_payload()
    duplicate = "drill-0000000000000004"
    payload[f"{population}_hole_count"] = 2
    payload[f"{population}_drill_ids"] = [duplicate, duplicate]

    with pytest.raises(ValidationError, match=f"{population}_drill_ids must be unique"):
        _admit_applied(payload)


@pytest.mark.parametrize("population", ("plated", "non_plated"))
def test_applied_npth_evidence_requires_sorted_ids(population: str) -> None:
    payload = _applied_payload()
    payload[f"{population}_hole_count"] = 2
    payload[f"{population}_drill_ids"] = [
        "drill-ffffffffffffffff",
        "drill-0000000000000004",
    ]

    with pytest.raises(ValidationError, match=f"{population}_drill_ids must be sorted"):
        _admit_applied(payload)


@pytest.mark.parametrize("population", ("plated", "non_plated"))
def test_applied_npth_evidence_requires_stable_drill_ids(population: str) -> None:
    payload = _applied_payload()
    payload[f"{population}_hole_count"] = 1
    payload[f"{population}_drill_ids"] = ["drill-not-a-stable-id"]

    with pytest.raises(
        ValidationError,
        match=f"{population}_drill_ids must be stable BoardGate drill IDs",
    ):
        _admit_applied(payload)


@pytest.mark.parametrize("population", ("plated", "non_plated"))
def test_applied_npth_tool_count_cannot_exceed_population(population: str) -> None:
    payload = _applied_payload()
    payload[f"{population}_tool_count"] = 3

    with pytest.raises(ValidationError, match=f"{population}_tool_count cannot exceed"):
        _admit_applied(payload)


def _stable_drill_ids(count: int, *, offset: int) -> list[str]:
    return [f"drill-{index + offset:016x}" for index in range(count)]


def test_applied_combined_hole_count_is_inclusive() -> None:
    payload = _applied_payload()
    payload["plated_hole_count"] = MAX_COUPON_HOLES // 2
    payload["plated_drill_ids"] = _stable_drill_ids(
        MAX_COUPON_HOLES // 2,
        offset=0,
    )
    payload["non_plated_hole_count"] = MAX_COUPON_HOLES // 2
    payload["non_plated_drill_ids"] = _stable_drill_ids(
        MAX_COUPON_HOLES // 2,
        offset=MAX_COUPON_HOLES,
    )

    admitted = _admit_applied(payload)

    assert admitted.plated_hole_count + admitted.non_plated_hole_count == 1024


def test_applied_combined_hole_count_rejects_n_plus_one() -> None:
    payload = _applied_payload()
    payload["plated_hole_count"] = (MAX_COUPON_HOLES // 2) + 1
    payload["plated_drill_ids"] = _stable_drill_ids(
        (MAX_COUPON_HOLES // 2) + 1,
        offset=0,
    )
    payload["non_plated_hole_count"] = MAX_COUPON_HOLES // 2
    payload["non_plated_drill_ids"] = _stable_drill_ids(
        MAX_COUPON_HOLES // 2,
        offset=MAX_COUPON_HOLES,
    )

    with pytest.raises(ValidationError, match="combined applied hole count"):
        _admit_applied(payload)


def test_applied_drill_populations_must_be_disjoint() -> None:
    payload = _applied_payload()
    payload["non_plated_drill_ids"] = ["drill-0000000000000001"]

    with pytest.raises(ValidationError, match="drill IDs must be disjoint"):
        _admit_applied(payload)


def test_generation_result_union_admits_applied_npth_evidence() -> None:
    payload = _result_payload()

    result = GenerationResult.model_validate_json(json.dumps(payload))

    assert isinstance(result.operation, AppliedTwoLayerCouponWithNpthGeneration)
    assert result.operation.non_plated_drill_ids == ("drill-0000000000000003",)


def test_npth_kind_is_required_consistently_by_schema_and_runtime() -> None:
    request_payload = _request_payload()
    request_operation = request_payload["operation"]
    assert isinstance(request_operation, dict)
    del request_operation["kind"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema_document(GenerationRequest)).validate(
            request_payload
        )
    with pytest.raises(ValidationError):
        GenerationRequest.model_validate_json(json.dumps(request_payload))

    result_payload = _result_payload()
    result_operation = result_payload["operation"]
    assert isinstance(result_operation, dict)
    del result_operation["kind"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema_document(GenerationResult)).validate(
            result_payload
        )
    with pytest.raises(ValidationError):
        GenerationResult.model_validate_json(json.dumps(result_payload))


def test_frozen_v1_operation_rejects_npth_fields() -> None:
    old_operation = {
        "schema_version": "1.0",
        "kind": "generate_two_layer_coupon",
        "operation_version": "1.0",
        "board_width_mm": 20.0,
        "board_height_mm": 15.0,
        "holes": [_plated_hole()],
        "non_plated_holes": [_non_plated_hole()],
        "traces": [_trace()],
        "instruction": "Keep the frozen v1 operation separate.",
    }

    with pytest.raises(ValidationError):
        _admit_request({"schema_version": "1.0", "operation": old_operation})


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("kind", "generate_unregistered_coupon"),
        ("operation_version", "1.1"),
    ),
)
def test_public_admission_rejects_unknown_kind_or_version(
    field: str,
    value: str,
) -> None:
    payload = _request_payload()
    operation = payload["operation"]
    assert isinstance(operation, dict)
    operation[field] = value

    with pytest.raises(GenerationRequestError) as caught:
        load_generation_request_bytes(
            json.dumps(payload).encode(),
            source="coupon.json",
        )

    assert caught.value.code == "GENERATION_REQUEST_VALIDATION_ERROR"
