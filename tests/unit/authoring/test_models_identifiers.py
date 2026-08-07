"""Strict authoring evidence contracts and content-derived identifiers."""

from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from boardgate.authoring.identifiers import (
    operation_sha256,
    request_sha256,
    revision_id,
)
from boardgate.authoring.models import (
    MODIFICATION_DISCLAIMER,
    AppliedExcellonToolDiameterChange,
    AppliedGerberStandardApertureDiameterChange,
    AppliedPlacementAnchorCoordinateChange,
    AppliedPlacementDnpStateChange,
    AppliedPlacementReferenceDesignatorChange,
    ModificationRequest,
    ModificationResult,
    PayloadFileEvidence,
    RevisionValidationEvidence,
    SetExcellonToolDiameter,
    SetGerberStandardApertureDiameter,
    SetPlacementAnchorCoordinate,
    SetPlacementDnpState,
    SetPlacementReferenceDesignator,
)
from boardgate.domain.enums import ReviewStatus
from boardgate.domain.provenance import SourceSpan
from boardgate.domain.serialization import canonical_json

BASE_PROJECT_ID = "prj-1111111111111111"
OUTPUT_PROJECT_ID = "prj-2222222222222222"
INPUT_SOURCE_ID = "src-3333333333333333"
OUTPUT_SOURCE_ID = "src-4444444444444444"
INPUT_SHA = "5" * 64
OUTPUT_SHA = "6" * 64


def operation() -> SetExcellonToolDiameter:
    return SetExcellonToolDiameter(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path="fab/board-plated.drl",
        source_file_id=INPUT_SOURCE_ID,
        source_sha256=INPUT_SHA,
        tool_code="T01",
        expected_diameter_mm=0.15,
        new_diameter_mm=0.3,
        instruction="Increase the explicitly selected plated drill tool.",
    )


def request() -> ModificationRequest:
    return ModificationRequest(
        schema_version="1.0",
        base_project_id=BASE_PROJECT_ID,
        operation=operation(),
    )


def applied_change() -> AppliedExcellonToolDiameterChange:
    span = SourceSpan(
        start_line=4,
        end_line=4,
        start_byte=42,
        end_byte=47,
    )
    return AppliedExcellonToolDiameterChange(
        source_logical_path="fab/board-plated.drl",
        input_source_file_id=INPUT_SOURCE_ID,
        output_source_file_id=OUTPUT_SOURCE_ID,
        input_sha256=INPUT_SHA,
        output_sha256=OUTPUT_SHA,
        tool_code="T01",
        old_diameter_mm=0.15,
        new_diameter_mm=0.3,
        input_value_span=span,
        output_value_span=span,
        affected_input_drill_ids=("drh-input",),
        affected_output_drill_ids=("drh-output",),
    )


def validation() -> RevisionValidationEvidence:
    return RevisionValidationEvidence(
        project_id=OUTPUT_PROJECT_ID,
        profile_id="default-prototype-2layer",
        profile_sha256="7" * 64,
        overall_status=ReviewStatus.READY_FOR_REVIEW,
        finding_ids=("fnd-1111111111111111", "fnd-2222222222222222"),
    )


def result() -> ModificationResult:
    digest = request_sha256(request())
    operation_digest = operation_sha256(operation())
    return ModificationResult(
        revision_id=revision_id(
            base_project_id=BASE_PROJECT_ID,
            operation_digest=operation_digest,
            output_project_id=OUTPUT_PROJECT_ID,
        ),
        base_project_id=BASE_PROJECT_ID,
        output_project_id=OUTPUT_PROJECT_ID,
        request_sha256=digest,
        operation_sha256=operation_digest,
        implementation_version="0.1.0",
        operation=applied_change(),
        payload_files=(
            PayloadFileEvidence(
                logical_path="fab/board-plated.drl",
                before_sha256=INPUT_SHA,
                after_sha256=OUTPUT_SHA,
                before_size_bytes=68,
                after_size_bytes=68,
                changed=True,
            ),
            PayloadFileEvidence(
                logical_path="fab/board-top.gtl",
                before_sha256="8" * 64,
                after_sha256="8" * 64,
                before_size_bytes=100,
                after_size_bytes=100,
                changed=False,
            ),
        ),
        validation=validation(),
        disclaimer=MODIFICATION_DISCLAIMER,
    )


def test_request_round_trip_and_hash_are_canonical_and_content_derived() -> None:
    value = request()

    assert ModificationRequest.model_validate_json(value.model_dump_json()) == value
    assert (
        request_sha256(value)
        == hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    )
    assert request_sha256(value) == request_sha256(request())

    changed_instruction = value.model_copy(
        update={
            "operation": value.operation.model_copy(
                update={"instruction": "A different explicit instruction."}
            )
        }
    )
    assert request_sha256(changed_instruction) != request_sha256(value)
    assert operation_sha256(changed_instruction.operation) == operation_sha256(
        value.operation
    )


def test_revision_id_uses_the_documented_canonical_identity_tuple() -> None:
    digest = operation_sha256(operation())
    expected_payload = json.dumps(
        {
            "base_project_id": BASE_PROJECT_ID,
            "operation_sha256": digest,
            "output_project_id": OUTPUT_PROJECT_ID,
        },
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    expected = "rev-" + hashlib.sha256(expected_payload.encode()).hexdigest()[:16]

    assert (
        revision_id(
            base_project_id=BASE_PROJECT_ID,
            operation_digest=digest,
            output_project_id=OUTPUT_PROJECT_ID,
        )
        == expected
    )


@pytest.mark.parametrize(
    "logical_path",
    (
        "/absolute.drl",
        "../escape.drl",
        "fab/../escape.drl",
        "fab//board.drl",
        "fab/./board.drl",
        r"fab\board.drl",
        "C:board.drl",
        "fab/control\x01.drl",
        "fab/trailing.",
        "fab/NUL.drl",
        "fab/e\u0301.drl",
        "fab/\x00board.drl",
    ),
)
def test_operation_rejects_unsafe_logical_paths(logical_path: str) -> None:
    with pytest.raises(ValidationError, match="normalized relative POSIX path"):
        operation().model_copy(
            update={"source_logical_path": logical_path}
        ).__class__.model_validate(
            {
                **operation().model_dump(),
                "source_logical_path": logical_path,
            }
        )


def test_operation_rejects_noop_and_unregistered_shapes() -> None:
    payload = operation().model_dump()
    payload["new_diameter_mm"] = payload["expected_diameter_mm"]
    with pytest.raises(ValidationError, match="must differ"):
        SetExcellonToolDiameter.model_validate(payload)

    request_payload = request().model_dump()
    request_payload["operation"]["kind"] = "raw_text_patch"
    with pytest.raises(ValidationError, match="does not match any"):
        ModificationRequest.model_validate(request_payload)


def test_payload_change_marker_must_match_byte_evidence() -> None:
    with pytest.raises(ValidationError, match="changed must match"):
        PayloadFileEvidence(
            logical_path="board.drl",
            before_sha256=INPUT_SHA,
            after_sha256=OUTPUT_SHA,
            before_size_bytes=10,
            after_size_bytes=10,
            changed=False,
        )


def test_validation_requires_completed_review_and_sorted_unique_findings() -> None:
    with pytest.raises(ValidationError, match="completed review"):
        validation().model_copy(
            update={"overall_status": ReviewStatus.ANALYSIS_FAILED}
        ).__class__.model_validate(
            {
                **validation().model_dump(),
                "overall_status": ReviewStatus.ANALYSIS_FAILED,
            }
        )

    for finding_ids in (
        ("fnd-2222222222222222", "fnd-1111111111111111"),
        ("fnd-1111111111111111", "fnd-1111111111111111"),
        ("not-a-finding",),
    ):
        with pytest.raises(ValidationError, match="finding_ids"):
            RevisionValidationEvidence.model_validate(
                {**validation().model_dump(), "finding_ids": finding_ids}
            )


def test_result_round_trip_binds_one_changed_target_and_validation_project() -> None:
    value = result()

    assert ModificationResult.model_validate_json(value.model_dump_json()) == value
    assert tuple(item.logical_path for item in value.payload_files) == tuple(
        sorted(item.logical_path for item in value.payload_files)
    )

    with pytest.raises(ValidationError, match="validation project_id"):
        ModificationResult.model_validate(
            {
                **value.model_dump(),
                "validation": {
                    **value.validation.model_dump(),
                    "project_id": "prj-9999999999999999",
                },
            }
        )

    with pytest.raises(ValidationError, match="normative non-guarantee"):
        ModificationResult.model_validate(
            {
                **value.model_dump(),
                "disclaimer": "This revision is guaranteed ready for fabrication.",
            }
        )


def test_applied_change_requires_the_exact_nonempty_same_width_token_span() -> None:
    value = applied_change()
    shifted = value.output_value_span.model_copy(
        update={"start_byte": 43, "end_byte": 48}
    )
    with pytest.raises(ValidationError, match="preserve the value source span"):
        AppliedExcellonToolDiameterChange.model_validate(
            {**value.model_dump(), "output_value_span": shifted.model_dump()}
        )

    empty = value.input_value_span.model_copy(update={"start_byte": 42, "end_byte": 42})
    with pytest.raises(ValidationError, match="non-empty source token span"):
        AppliedExcellonToolDiameterChange.model_validate(
            {
                **value.model_dump(),
                "input_value_span": empty.model_dump(),
                "output_value_span": empty.model_dump(),
            }
        )


def test_result_rejects_unsorted_inventory_and_multiple_changed_files() -> None:
    value = result()
    payloads = tuple(item.model_dump() for item in value.payload_files)

    with pytest.raises(ValidationError, match="unique and sorted"):
        ModificationResult.model_validate(
            {**value.model_dump(), "payload_files": tuple(reversed(payloads))}
        )

    second_changed = {
        **payloads[1],
        "after_sha256": "9" * 64,
        "changed": True,
    }
    with pytest.raises(ValidationError, match="exactly one changed file"):
        ModificationResult.model_validate(
            {
                **value.model_dump(),
                "payload_files": (payloads[0], second_changed),
            }
        )


def gerber_operation() -> SetGerberStandardApertureDiameter:
    return SetGerberStandardApertureDiameter(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path="fab/board-top-copper.gtl",
        source_file_id=INPUT_SOURCE_ID,
        source_sha256=INPUT_SHA,
        aperture_code="D11",
        expected_diameter_mm=0.05,
        new_diameter_mm=0.3,
        instruction="Increase the explicitly selected standard round aperture.",
    )


def gerber_applied_change() -> AppliedGerberStandardApertureDiameterChange:
    span = SourceSpan(
        start_line=5,
        end_line=5,
        start_byte=42,
        end_byte=47,
    )
    return AppliedGerberStandardApertureDiameterChange(
        source_logical_path="fab/board-top-copper.gtl",
        input_source_file_id=INPUT_SOURCE_ID,
        output_source_file_id=OUTPUT_SOURCE_ID,
        input_sha256=INPUT_SHA,
        output_sha256=OUTPUT_SHA,
        aperture_code="D11",
        old_diameter_mm=0.05,
        new_diameter_mm=0.3,
        input_value_span=span,
        output_value_span=span,
        affected_input_primitive_ids=("prm-input",),
        affected_output_primitive_ids=("prm-output",),
    )


def test_gerber_request_round_trip_and_hash_is_content_derived() -> None:
    value = ModificationRequest(
        schema_version="1.0",
        base_project_id=BASE_PROJECT_ID,
        operation=gerber_operation(),
    )

    admitted = ModificationRequest.model_validate_json(value.model_dump_json())
    assert admitted == value
    assert isinstance(admitted.operation, SetGerberStandardApertureDiameter)
    assert admitted.operation.kind == "set_gerber_standard_aperture_diameter"

    changed_instruction = value.model_copy(
        update={
            "operation": value.operation.model_copy(
                update={"instruction": "A different explicit instruction."}
            )
        }
    )
    assert request_sha256(changed_instruction) != request_sha256(value)
    assert operation_sha256(changed_instruction.operation) == operation_sha256(
        value.operation
    )


def test_gerber_operation_rejects_noop_and_bad_aperture_codes() -> None:
    payload = gerber_operation().model_dump()
    payload["new_diameter_mm"] = payload["expected_diameter_mm"]
    with pytest.raises(ValidationError, match="must differ"):
        SetGerberStandardApertureDiameter.model_validate(payload)

    for aperture_code in ("T01", "d10", "D", "D1234567"):
        with pytest.raises(ValidationError, match="aperture_code"):
            SetGerberStandardApertureDiameter.model_validate(
                {**gerber_operation().model_dump(), "aperture_code": aperture_code}
            )
    for aperture_code in ("D1", "D10", "D123456"):
        admitted = SetGerberStandardApertureDiameter.model_validate(
            {**gerber_operation().model_dump(), "aperture_code": aperture_code}
        )
        assert admitted.aperture_code == aperture_code


def test_gerber_applied_change_requires_new_identity_and_one_to_one_targets() -> None:
    value = gerber_applied_change()

    with pytest.raises(ValidationError, match="must change the source digest"):
        AppliedGerberStandardApertureDiameterChange.model_validate(
            {**value.model_dump(), "output_sha256": INPUT_SHA}
        )
    with pytest.raises(ValidationError, match="new source_file_id"):
        AppliedGerberStandardApertureDiameterChange.model_validate(
            {**value.model_dump(), "output_source_file_id": INPUT_SOURCE_ID}
        )
    with pytest.raises(ValidationError, match="must change the aperture diameter"):
        AppliedGerberStandardApertureDiameterChange.model_validate(
            {**value.model_dump(), "new_diameter_mm": value.old_diameter_mm}
        )
    with pytest.raises(ValidationError, match="one-to-one"):
        AppliedGerberStandardApertureDiameterChange.model_validate(
            {
                **value.model_dump(),
                "affected_output_primitive_ids": ("prm-output-a", "prm-output-b"),
            }
        )
    with pytest.raises(ValidationError, match="must be unique"):
        AppliedGerberStandardApertureDiameterChange.model_validate(
            {
                **value.model_dump(),
                "affected_input_primitive_ids": ("prm-input", "prm-input"),
                "affected_output_primitive_ids": ("prm-output-a", "prm-output-b"),
            }
        )


def test_gerber_applied_change_requires_the_exact_same_width_token_span() -> None:
    value = gerber_applied_change()
    shifted = value.output_value_span.model_copy(
        update={"start_byte": 43, "end_byte": 48}
    )
    with pytest.raises(ValidationError, match="preserve the value source span"):
        AppliedGerberStandardApertureDiameterChange.model_validate(
            {**value.model_dump(), "output_value_span": shifted.model_dump()}
        )

    empty = value.input_value_span.model_copy(update={"start_byte": 42, "end_byte": 42})
    with pytest.raises(ValidationError, match="non-empty source token span"):
        AppliedGerberStandardApertureDiameterChange.model_validate(
            {
                **value.model_dump(),
                "input_value_span": empty.model_dump(),
                "output_value_span": empty.model_dump(),
            }
        )


def test_gerber_applied_change_round_trips_inside_result() -> None:
    evidence = result()
    payload_files = tuple(
        item.model_copy(
            update={
                "logical_path": "fab/board-top-copper.gtl"
                if item.changed
                else item.logical_path
            }
        )
        for item in evidence.payload_files
    )
    gerber_result = evidence.model_copy(
        update={"operation": gerber_applied_change(), "payload_files": payload_files}
    )
    admitted = ModificationResult.model_validate_json(gerber_result.model_dump_json())
    assert isinstance(admitted.operation, AppliedGerberStandardApertureDiameterChange)
    assert admitted.operation.aperture_code == "D11"
    assert admitted.operation.adapter_id == "boardgate-gerber-aperture-diameter-patch"


def placement_operation() -> SetPlacementReferenceDesignator:
    return SetPlacementReferenceDesignator(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path="assembly/component-placement.csv",
        source_file_id=INPUT_SOURCE_ID,
        source_sha256=INPUT_SHA,
        expected_reference="C1",
        new_reference="R2",
        instruction="Rename the explicitly selected placement reference.",
    )


def placement_applied_change() -> AppliedPlacementReferenceDesignatorChange:
    span = SourceSpan(
        start_line=3,
        end_line=3,
        start_byte=42,
        end_byte=44,
    )
    return AppliedPlacementReferenceDesignatorChange(
        source_logical_path="assembly/component-placement.csv",
        input_source_file_id=INPUT_SOURCE_ID,
        output_source_file_id=OUTPUT_SOURCE_ID,
        input_sha256=INPUT_SHA,
        output_sha256=OUTPUT_SHA,
        old_reference="C1",
        new_reference="R2",
        input_value_span=span,
        output_value_span=span,
        affected_input_placement_ids=("plc-input",),
        affected_output_placement_ids=("plc-output",),
    )


def test_placement_request_round_trip_and_hash_is_content_derived() -> None:
    value = ModificationRequest(
        schema_version="1.0",
        base_project_id=BASE_PROJECT_ID,
        operation=placement_operation(),
    )

    admitted = ModificationRequest.model_validate_json(value.model_dump_json())
    assert admitted == value
    assert isinstance(admitted.operation, SetPlacementReferenceDesignator)
    assert admitted.operation.kind == "set_placement_reference_designator"

    changed_instruction = value.model_copy(
        update={
            "operation": value.operation.model_copy(
                update={"instruction": "A different explicit instruction."}
            )
        }
    )
    assert request_sha256(changed_instruction) != request_sha256(value)
    assert operation_sha256(changed_instruction.operation) == operation_sha256(
        value.operation
    )


def test_placement_operation_rejects_noop_and_bad_references() -> None:
    payload = placement_operation().model_dump()
    payload["new_reference"] = payload["expected_reference"]
    with pytest.raises(ValidationError, match="must differ"):
        SetPlacementReferenceDesignator.model_validate(payload)

    for reference in ("c1", "R 2", "", "-R2", "R2" * 17):
        with pytest.raises(ValidationError, match="new_reference"):
            SetPlacementReferenceDesignator.model_validate(
                {**placement_operation().model_dump(), "new_reference": reference}
            )
    for reference in ("R2", "TP10", "J1A", "X1_2", "A"):
        admitted = SetPlacementReferenceDesignator.model_validate(
            {**placement_operation().model_dump(), "new_reference": reference}
        )
        assert admitted.new_reference == reference


def test_placement_applied_change_requires_new_identity_and_one_to_one_targets() -> (
    None
):
    value = placement_applied_change()

    with pytest.raises(ValidationError, match="must change the source digest"):
        AppliedPlacementReferenceDesignatorChange.model_validate(
            {**value.model_dump(), "output_sha256": INPUT_SHA}
        )
    with pytest.raises(ValidationError, match="new source_file_id"):
        AppliedPlacementReferenceDesignatorChange.model_validate(
            {**value.model_dump(), "output_source_file_id": INPUT_SOURCE_ID}
        )
    with pytest.raises(ValidationError, match="must change the reference designator"):
        AppliedPlacementReferenceDesignatorChange.model_validate(
            {**value.model_dump(), "new_reference": value.old_reference}
        )
    with pytest.raises(ValidationError, match="one-to-one"):
        AppliedPlacementReferenceDesignatorChange.model_validate(
            {
                **value.model_dump(),
                "affected_output_placement_ids": ("plc-output-a", "plc-output-b"),
            }
        )
    with pytest.raises(ValidationError, match="must be unique"):
        AppliedPlacementReferenceDesignatorChange.model_validate(
            {
                **value.model_dump(),
                "affected_input_placement_ids": ("plc-input", "plc-input"),
                "affected_output_placement_ids": ("plc-output-a", "plc-output-b"),
            }
        )


def test_placement_applied_change_requires_the_exact_same_width_token_span() -> None:
    value = placement_applied_change()
    shifted = value.output_value_span.model_copy(
        update={"start_byte": 43, "end_byte": 45}
    )
    with pytest.raises(ValidationError, match="preserve the value source span"):
        AppliedPlacementReferenceDesignatorChange.model_validate(
            {**value.model_dump(), "output_value_span": shifted.model_dump()}
        )

    empty = value.input_value_span.model_copy(update={"start_byte": 42, "end_byte": 42})
    with pytest.raises(ValidationError, match="non-empty source token span"):
        AppliedPlacementReferenceDesignatorChange.model_validate(
            {
                **value.model_dump(),
                "input_value_span": empty.model_dump(),
                "output_value_span": empty.model_dump(),
            }
        )


def test_placement_applied_change_round_trips_inside_result() -> None:
    evidence = result()
    payload_files = tuple(
        item.model_copy(
            update={
                "logical_path": "assembly/component-placement.csv"
                if item.changed
                else item.logical_path
            }
        )
        for item in evidence.payload_files
    )
    placement_result = evidence.model_copy(
        update={"operation": placement_applied_change(), "payload_files": payload_files}
    )
    admitted = ModificationResult.model_validate_json(
        placement_result.model_dump_json()
    )
    assert isinstance(admitted.operation, AppliedPlacementReferenceDesignatorChange)
    assert admitted.operation.new_reference == "R2"
    assert admitted.operation.adapter_id == (
        "boardgate-placement-reference-designator-patch"
    )


def coordinate_operation() -> SetPlacementAnchorCoordinate:
    return SetPlacementAnchorCoordinate(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path="assembly/component-placement.csv",
        source_file_id=INPUT_SOURCE_ID,
        source_sha256=INPUT_SHA,
        reference="C1",
        coordinate="x",
        expected_position_mm=25.0,
        new_position_mm=10.0,
        instruction="Move the explicitly selected placement anchor.",
    )


def coordinate_applied_change() -> AppliedPlacementAnchorCoordinateChange:
    span = SourceSpan(
        start_line=3,
        end_line=3,
        start_byte=42,
        end_byte=44,
    )
    return AppliedPlacementAnchorCoordinateChange(
        source_logical_path="assembly/component-placement.csv",
        input_source_file_id=INPUT_SOURCE_ID,
        output_source_file_id=OUTPUT_SOURCE_ID,
        input_sha256=INPUT_SHA,
        output_sha256=OUTPUT_SHA,
        reference="C1",
        coordinate="x",
        old_position_mm=25.0,
        new_position_mm=10.0,
        input_value_span=span,
        output_value_span=span,
        affected_input_placement_ids=("plc-input",),
        affected_output_placement_ids=("plc-output",),
    )


def test_coordinate_request_round_trip_and_hash_is_content_derived() -> None:
    value = ModificationRequest(
        schema_version="1.0",
        base_project_id=BASE_PROJECT_ID,
        operation=coordinate_operation(),
    )

    admitted = ModificationRequest.model_validate_json(value.model_dump_json())
    assert admitted == value
    assert isinstance(admitted.operation, SetPlacementAnchorCoordinate)
    assert admitted.operation.kind == "set_placement_anchor_coordinate"

    changed_instruction = value.model_copy(
        update={
            "operation": value.operation.model_copy(
                update={"instruction": "A different explicit instruction."}
            )
        }
    )
    assert request_sha256(changed_instruction) != request_sha256(value)
    assert operation_sha256(changed_instruction.operation) == operation_sha256(
        value.operation
    )


def test_coordinate_operation_rejects_noop_bad_axis_and_unbounded_positions() -> None:
    payload = coordinate_operation().model_dump()
    payload["new_position_mm"] = payload["expected_position_mm"]
    with pytest.raises(ValidationError, match="must differ"):
        SetPlacementAnchorCoordinate.model_validate(payload)

    with pytest.raises(ValidationError, match="coordinate"):
        SetPlacementAnchorCoordinate.model_validate(
            {**coordinate_operation().model_dump(), "coordinate": "z"}
        )
    for axis in ("x", "y"):
        admitted = SetPlacementAnchorCoordinate.model_validate(
            {**coordinate_operation().model_dump(), "coordinate": axis}
        )
        assert admitted.coordinate == axis

    with pytest.raises(ValidationError, match="reference"):
        SetPlacementAnchorCoordinate.model_validate(
            {**coordinate_operation().model_dump(), "reference": "c1"}
        )

    for field in ("expected_position_mm", "new_position_mm"):
        with pytest.raises(ValidationError, match=field):
            SetPlacementAnchorCoordinate.model_validate(
                {**coordinate_operation().model_dump(), field: 1000.5}
            )
        with pytest.raises(ValidationError, match=field):
            SetPlacementAnchorCoordinate.model_validate(
                {**coordinate_operation().model_dump(), field: -1000.5}
            )
        admitted = SetPlacementAnchorCoordinate.model_validate(
            {**coordinate_operation().model_dump(), field: -250.0}
        )
        assert getattr(admitted, field) == -250.0


def test_coordinate_applied_change_requires_new_identity_and_one_to_one_targets() -> (
    None
):
    value = coordinate_applied_change()

    with pytest.raises(ValidationError, match="must change the source digest"):
        AppliedPlacementAnchorCoordinateChange.model_validate(
            {**value.model_dump(), "output_sha256": INPUT_SHA}
        )
    with pytest.raises(ValidationError, match="new source_file_id"):
        AppliedPlacementAnchorCoordinateChange.model_validate(
            {**value.model_dump(), "output_source_file_id": INPUT_SOURCE_ID}
        )
    with pytest.raises(ValidationError, match="must change the anchor coordinate"):
        AppliedPlacementAnchorCoordinateChange.model_validate(
            {**value.model_dump(), "new_position_mm": value.old_position_mm}
        )
    with pytest.raises(ValidationError, match="one-to-one"):
        AppliedPlacementAnchorCoordinateChange.model_validate(
            {
                **value.model_dump(),
                "affected_output_placement_ids": ("plc-output-a", "plc-output-b"),
            }
        )
    with pytest.raises(ValidationError, match="must be unique"):
        AppliedPlacementAnchorCoordinateChange.model_validate(
            {
                **value.model_dump(),
                "affected_input_placement_ids": ("plc-input", "plc-input"),
                "affected_output_placement_ids": ("plc-output-a", "plc-output-b"),
            }
        )


def test_coordinate_applied_change_requires_the_exact_same_width_token_span() -> None:
    value = coordinate_applied_change()
    shifted = value.output_value_span.model_copy(
        update={"start_byte": 43, "end_byte": 45}
    )
    with pytest.raises(ValidationError, match="preserve the value source span"):
        AppliedPlacementAnchorCoordinateChange.model_validate(
            {**value.model_dump(), "output_value_span": shifted.model_dump()}
        )

    empty = value.input_value_span.model_copy(update={"start_byte": 42, "end_byte": 42})
    with pytest.raises(ValidationError, match="non-empty source token span"):
        AppliedPlacementAnchorCoordinateChange.model_validate(
            {
                **value.model_dump(),
                "input_value_span": empty.model_dump(),
                "output_value_span": empty.model_dump(),
            }
        )


def test_coordinate_applied_change_round_trips_inside_result() -> None:
    evidence = result()
    payload_files = tuple(
        item.model_copy(
            update={
                "logical_path": "assembly/component-placement.csv"
                if item.changed
                else item.logical_path
            }
        )
        for item in evidence.payload_files
    )
    coordinate_result = evidence.model_copy(
        update={
            "operation": coordinate_applied_change(),
            "payload_files": payload_files,
        }
    )
    admitted = ModificationResult.model_validate_json(
        coordinate_result.model_dump_json()
    )
    assert isinstance(admitted.operation, AppliedPlacementAnchorCoordinateChange)
    assert admitted.operation.coordinate == "x"
    assert admitted.operation.new_position_mm == 10.0
    assert admitted.operation.adapter_id == (
        "boardgate-placement-anchor-coordinate-patch"
    )


def dnp_operation() -> SetPlacementDnpState:
    return SetPlacementDnpState(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path="assembly/component-placement.csv",
        source_file_id=INPUT_SOURCE_ID,
        source_sha256=INPUT_SHA,
        reference="U1",
        expected_dnp=False,
        new_dnp=True,
        instruction="Mark the explicitly selected placement reference DNP.",
    )


def dnp_applied_change() -> AppliedPlacementDnpStateChange:
    span = SourceSpan(
        start_line=3,
        end_line=3,
        start_byte=42,
        end_byte=43,
    )
    return AppliedPlacementDnpStateChange(
        source_logical_path="assembly/component-placement.csv",
        input_source_file_id=INPUT_SOURCE_ID,
        output_source_file_id=OUTPUT_SOURCE_ID,
        input_sha256=INPUT_SHA,
        output_sha256=OUTPUT_SHA,
        reference="U1",
        old_dnp=False,
        new_dnp=True,
        input_value_span=span,
        output_value_span=span,
        affected_input_placement_ids=("plc-input",),
        affected_output_placement_ids=("plc-output",),
    )


def test_dnp_request_round_trip_and_hash_is_content_derived() -> None:
    value = ModificationRequest(
        schema_version="1.0",
        base_project_id=BASE_PROJECT_ID,
        operation=dnp_operation(),
    )

    admitted = ModificationRequest.model_validate_json(value.model_dump_json())
    assert admitted == value
    assert isinstance(admitted.operation, SetPlacementDnpState)
    assert admitted.operation.kind == "set_placement_dnp_state"

    changed_instruction = value.model_copy(
        update={
            "operation": value.operation.model_copy(
                update={"instruction": "A different explicit instruction."}
            )
        }
    )
    assert request_sha256(changed_instruction) != request_sha256(value)
    assert operation_sha256(changed_instruction.operation) == operation_sha256(
        value.operation
    )


def test_dnp_operation_rejects_noop_and_bad_references() -> None:
    payload = dnp_operation().model_dump()
    payload["new_dnp"] = payload["expected_dnp"]
    with pytest.raises(ValidationError, match="must differ"):
        SetPlacementDnpState.model_validate(payload)

    with pytest.raises(ValidationError, match="reference"):
        SetPlacementDnpState.model_validate(
            {**dnp_operation().model_dump(), "reference": "u1"}
        )
    for field in ("expected_dnp", "new_dnp"):
        with pytest.raises(ValidationError, match=field):
            SetPlacementDnpState.model_validate(
                {**dnp_operation().model_dump(), field: "maybe"}
            )


def test_dnp_applied_change_requires_new_identity_and_one_to_one_targets() -> None:
    value = dnp_applied_change()

    with pytest.raises(ValidationError, match="must change the source digest"):
        AppliedPlacementDnpStateChange.model_validate(
            {**value.model_dump(), "output_sha256": INPUT_SHA}
        )
    with pytest.raises(ValidationError, match="new source_file_id"):
        AppliedPlacementDnpStateChange.model_validate(
            {**value.model_dump(), "output_source_file_id": INPUT_SOURCE_ID}
        )
    with pytest.raises(ValidationError, match="must change the DNP state"):
        AppliedPlacementDnpStateChange.model_validate(
            {**value.model_dump(), "new_dnp": value.old_dnp}
        )
    with pytest.raises(ValidationError, match="one-to-one"):
        AppliedPlacementDnpStateChange.model_validate(
            {
                **value.model_dump(),
                "affected_output_placement_ids": ("plc-output-a", "plc-output-b"),
            }
        )
    with pytest.raises(ValidationError, match="must be unique"):
        AppliedPlacementDnpStateChange.model_validate(
            {
                **value.model_dump(),
                "affected_input_placement_ids": ("plc-input", "plc-input"),
                "affected_output_placement_ids": ("plc-output-a", "plc-output-b"),
            }
        )


def test_dnp_applied_change_requires_the_exact_same_width_token_span() -> None:
    value = dnp_applied_change()
    shifted = value.output_value_span.model_copy(
        update={"start_byte": 43, "end_byte": 44}
    )
    with pytest.raises(ValidationError, match="preserve the value source span"):
        AppliedPlacementDnpStateChange.model_validate(
            {**value.model_dump(), "output_value_span": shifted.model_dump()}
        )

    empty = value.input_value_span.model_copy(update={"start_byte": 42, "end_byte": 42})
    with pytest.raises(ValidationError, match="non-empty source token span"):
        AppliedPlacementDnpStateChange.model_validate(
            {
                **value.model_dump(),
                "input_value_span": empty.model_dump(),
                "output_value_span": empty.model_dump(),
            }
        )


def test_dnp_applied_change_round_trips_inside_result() -> None:
    evidence = result()
    payload_files = tuple(
        item.model_copy(
            update={
                "logical_path": "assembly/component-placement.csv"
                if item.changed
                else item.logical_path
            }
        )
        for item in evidence.payload_files
    )
    dnp_result = evidence.model_copy(
        update={
            "operation": dnp_applied_change(),
            "payload_files": payload_files,
        }
    )
    admitted = ModificationResult.model_validate_json(dnp_result.model_dump_json())
    assert isinstance(admitted.operation, AppliedPlacementDnpStateChange)
    assert admitted.operation.reference == "U1"
    assert admitted.operation.new_dnp is True
    assert admitted.operation.adapter_id == "boardgate-placement-dnp-state-patch"
