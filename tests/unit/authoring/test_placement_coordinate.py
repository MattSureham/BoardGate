"""Constrained placement anchor-coordinate patch and semantic postconditions."""

from __future__ import annotations

import dataclasses
import hashlib
from decimal import Decimal
from typing import Literal

import pytest

from boardgate.application.modification_registry import (
    OperationExecutionError,
    OperationRegistryError,
    PlacementAnchorCoordinateExecutor,
)
from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
    parse_job,
)
from boardgate.authoring.excellon import AuthoringOperationError
from boardgate.authoring.models import (
    SetExcellonToolDiameter,
    SetPlacementAnchorCoordinate,
)
from boardgate.authoring.placement import (
    PlacementPatchCandidate,
    prepare_placement_anchor_coordinate_patch,
    scan_placement_coordinates,
    verify_placement_anchor_coordinate_patch,
)
from boardgate.domain.enums import FileType
from boardgate.domain.geometry import Point, Unit
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.source import SourceFile
from boardgate.parsers.errors import ParserError
from boardgate.parsers.placement import PlacementParseResult, parse_placement_csv

SUBJECT = "component-placement.csv"
PAYLOAD = (
    b"Reference,X,Y,Rotation,Side,Unit,DNP\n"
    b"R1,5,5,0,Top,mm,no\n"
    b"C1,25,5,90,Top,mm,no\n"
    b"R9,9,5,0,Top,mm,yes\n"
)
FRACTIONAL_PAYLOAD = PAYLOAD.replace(b"C1,25,5,90", b"C1,25.5,5,90")


def parse_payload(
    payload: bytes,
    *,
    logical_path: str = SUBJECT,
) -> PlacementParseResult:
    digest = hashlib.sha256(payload).hexdigest()
    return parse_placement_csv(
        payload,
        logical_path=logical_path,
        source_file_id=source_file_id(logical_path, digest),
    )


def operation(
    payload: bytes = PAYLOAD,
    *,
    coordinate: Literal["x", "y"] = "x",
    reference: str = "C1",
    expected: float = 25.0,
    new: float = 10.0,
) -> SetPlacementAnchorCoordinate:
    digest = hashlib.sha256(payload).hexdigest()
    return SetPlacementAnchorCoordinate(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path=SUBJECT,
        source_file_id=source_file_id(SUBJECT, digest),
        source_sha256=digest,
        reference=reference,
        coordinate=coordinate,
        expected_position_mm=expected,
        new_position_mm=new,
        instruction="Move the explicitly selected placement anchor.",
    )


def prepared_patch(
    payload: bytes = PAYLOAD,
    *,
    request: SetPlacementAnchorCoordinate | None = None,
) -> tuple[PlacementParseResult, PlacementPatchCandidate, PlacementParseResult]:
    selected = request or operation(payload)
    before = parse_payload(payload)
    candidate = prepare_placement_anchor_coordinate_patch(
        payload,
        before,
        selected,
    )
    after = parse_placement_csv(
        candidate.payload,
        logical_path=SUBJECT,
        source_file_id=candidate.output_source_file_id,
    )
    return before, candidate, after


def inline_executor(job: ParserJob) -> ParserExecution:
    try:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            result=parse_job(job),
        )
    except ParserError as error:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            failure=ParserFailure(code=error.code, detail=error.detail),
        )


def source(payload: bytes = PAYLOAD) -> SourceFile:
    digest = hashlib.sha256(payload).hexdigest()
    return SourceFile(
        source_file_id=source_file_id(SUBJECT, digest),
        logical_path=SUBJECT,
        sha256=digest,
        size_bytes=len(payload),
        file_type=FileType.PLACEMENT_CSV,
    )


def test_scanner_returns_row_coordinates_and_exact_byte_spans() -> None:
    witnesses = scan_placement_coordinates(PAYLOAD, coordinate="x", subject=SUBJECT)

    assert [(item.row_index, item.reference) for item in witnesses] == [
        (0, "R1"),
        (1, "C1"),
        (2, "R9"),
    ]
    target = witnesses[1]
    assert target.coordinate_lexeme == "25"
    assert target.value_mm == Decimal("25")
    assert target.value_span.start_line == target.value_span.end_line == 3
    start = PAYLOAD.index(b"25")
    assert (target.value_span.start_byte, target.value_span.end_byte) == (
        start,
        start + len(b"25"),
    )


def test_scanner_reads_the_requested_axis_only() -> None:
    witnesses = scan_placement_coordinates(PAYLOAD, coordinate="y", subject=SUBJECT)

    assert [item.coordinate_lexeme for item in witnesses] == ["5", "5", "5"]
    target = witnesses[1]
    start = PAYLOAD.index(b",5,90") + 1
    assert (target.value_span.start_byte, target.value_span.end_byte) == (
        start,
        start + 1,
    )


def test_scanner_locates_the_token_inside_a_padded_cell() -> None:
    payload = PAYLOAD.replace(b"C1,25,5,90", b"C1, 25 ,5,90")
    witnesses = scan_placement_coordinates(payload, coordinate="x", subject=SUBJECT)

    target = witnesses[1]
    assert target.coordinate_lexeme == "25"
    assert target.value_mm == Decimal("25")
    start = payload.index(b"25")
    assert (target.value_span.start_byte, target.value_span.end_byte) == (
        start,
        start + len(b"25"),
    )


@pytest.mark.parametrize("token", (b"1e2", b".5", b"+5", b"05", b"5.", b"-"))
def test_scanner_marks_non_plain_decimal_tokens_as_unsupported(token: bytes) -> None:
    payload = PAYLOAD.replace(b"C1,25,5,90", b"C1," + token + b",5,90")
    witnesses = scan_placement_coordinates(payload, coordinate="x", subject=SUBJECT)

    assert witnesses[1].coordinate_lexeme == token.decode("ascii")
    assert witnesses[1].value_mm is None


@pytest.mark.parametrize(
    ("token", "expected"),
    ((b"-5", Decimal("-5")), (b"25.5", Decimal("25.5")), (b"-0.25", Decimal("-0.25"))),
)
def test_scanner_accepts_signed_and_fractional_plain_tokens(
    token: bytes,
    expected: Decimal,
) -> None:
    payload = PAYLOAD.replace(b"C1,25,5,90", b"C1," + token + b",5,90")
    witnesses = scan_placement_coordinates(payload, coordinate="x", subject=SUBJECT)

    assert witnesses[1].value_mm == expected


def test_prepare_replaces_exactly_one_same_width_token() -> None:
    before, candidate, after = prepared_patch()

    assert candidate.payload == PAYLOAD.replace(b"C1,25,5,90", b"C1,10,5,90")
    assert len(candidate.payload) == len(PAYLOAD)
    assert candidate.input_value_span == candidate.output_value_span
    assert candidate.target_row_index == 1
    assert candidate.affected_input_placement_ids == (
        before.placements[1].provenance.object_id,
    )
    assert [placement.position for placement in after.placements] == [
        Point(x=5.0, y=5.0),
        Point(x=10.0, y=5.0),
        Point(x=9.0, y=5.0),
    ]


def test_prepare_patches_the_y_coordinate() -> None:
    before, candidate, after = prepared_patch(
        request=operation(coordinate="y", expected=5.0, new=7.0)
    )

    assert candidate.payload == PAYLOAD.replace(b"C1,25,5,90", b"C1,25,7,90")
    assert after.placements[1].position == Point(x=25.0, y=7.0)
    assert candidate.affected_input_placement_ids == (
        before.placements[1].provenance.object_id,
    )


def test_prepare_replaces_a_fractional_same_width_token() -> None:
    _, candidate, after = prepared_patch(
        FRACTIONAL_PAYLOAD,
        request=operation(FRACTIONAL_PAYLOAD, expected=25.5, new=10.5),
    )

    assert candidate.payload == FRACTIONAL_PAYLOAD.replace(b"25.5", b"10.5")
    assert after.placements[1].position == Point(x=10.5, y=5.0)


def test_prepare_rejects_stale_identity_and_missing_or_ambiguous_targets() -> None:
    stale = operation().model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises(AuthoringOperationError) as sha_error:
        prepare_placement_anchor_coordinate_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            stale,
        )
    assert sha_error.value.code == "AUTHORING_SOURCE_SHA_MISMATCH"

    stale_id = operation().model_copy(update={"source_file_id": "src-" + "0" * 16})
    with pytest.raises(AuthoringOperationError) as id_error:
        prepare_placement_anchor_coordinate_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            stale_id,
        )
    assert id_error.value.code == "AUTHORING_SOURCE_ID_MISMATCH"

    with pytest.raises(AuthoringOperationError) as not_found:
        prepare_placement_anchor_coordinate_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            operation(reference="R7"),
        )
    assert not_found.value.code == "AUTHORING_PLACEMENT_REFERENCE_NOT_FOUND"

    duplicated = PAYLOAD.replace(b"R1,5,5", b"C1,5,5")
    with pytest.raises(AuthoringOperationError) as ambiguous:
        prepare_placement_anchor_coordinate_patch(
            duplicated,
            parse_payload(duplicated),
            operation(duplicated),
        )
    assert ambiguous.value.code == "AUTHORING_PLACEMENT_REFERENCE_AMBIGUOUS"


def test_prepare_rejects_non_metric_sources() -> None:
    imperial = PAYLOAD.replace(b",mm,", b",in,")
    with pytest.raises(AuthoringOperationError) as caught:
        prepare_placement_anchor_coordinate_patch(
            imperial,
            parse_payload(imperial),
            operation(imperial),
        )
    assert caught.value.code == "AUTHORING_PLACEMENT_UNIT_UNSUPPORTED"


def test_prepare_rejects_unsupported_token_forms() -> None:
    exponential = PAYLOAD.replace(b"C1,25,5,90", b"C1,1e2,5,90")
    with pytest.raises(AuthoringOperationError) as token_error:
        prepare_placement_anchor_coordinate_patch(
            exponential,
            parse_payload(exponential),
            operation(exponential, expected=100.0),
        )
    assert token_error.value.code == "AUTHORING_PLACEMENT_COORDINATE_UNSUPPORTED"

    lowercase = PAYLOAD.replace(b"C1,25,5,90", b"c1,25,5,90")
    with pytest.raises(AuthoringOperationError) as reference_error:
        prepare_placement_anchor_coordinate_patch(
            lowercase,
            parse_payload(lowercase),
            operation(lowercase),
        )
    assert reference_error.value.code == "AUTHORING_PLACEMENT_REFERENCE_UNSUPPORTED"


def test_prepare_rejects_a_mismatched_expected_position() -> None:
    with pytest.raises(AuthoringOperationError) as caught:
        prepare_placement_anchor_coordinate_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            operation(expected=24.0),
        )
    assert caught.value.code == "AUTHORING_PRECONDITION_MISMATCH"


@pytest.mark.parametrize(
    ("payload", "new"),
    (
        (PAYLOAD, 10.5),
        (FRACTIONAL_PAYLOAD, 10.75),
    ),
)
def test_prepare_rejects_unrepresentable_new_positions(
    payload: bytes,
    new: float,
) -> None:
    expected = 25.0 if payload is PAYLOAD else 25.5
    with pytest.raises(AuthoringOperationError) as caught:
        prepare_placement_anchor_coordinate_patch(
            payload,
            parse_payload(payload),
            operation(payload, expected=expected, new=new),
        )
    assert caught.value.code == "AUTHORING_PLACEMENT_NEW_COORDINATE_PRECISION"


@pytest.mark.parametrize(
    ("payload", "expected", "new"),
    (
        (PAYLOAD, 25.0, 100.0),
        (PAYLOAD, 25.0, -10.0),
        (FRACTIONAL_PAYLOAD, 25.5, 100.5),
    ),
)
def test_prepare_rejects_width_mismatched_new_positions(
    payload: bytes,
    expected: float,
    new: float,
) -> None:
    with pytest.raises(AuthoringOperationError) as caught:
        prepare_placement_anchor_coordinate_patch(
            payload,
            parse_payload(payload),
            operation(payload, expected=expected, new=new),
        )
    assert caught.value.code == "AUTHORING_PLACEMENT_NEW_COORDINATE_WIDTH"


def test_verify_proves_the_exact_requested_change() -> None:
    before, candidate, after = prepared_patch()
    applied = verify_placement_anchor_coordinate_patch(
        before,
        after,
        operation(),
        candidate,
    )

    assert applied.reference == "C1"
    assert applied.coordinate == "x"
    assert applied.old_position_mm == 25.0
    assert applied.new_position_mm == 10.0
    assert applied.affected_input_placement_ids == (
        before.placements[1].provenance.object_id,
    )
    assert applied.affected_output_placement_ids == (
        after.placements[1].provenance.object_id,
    )
    assert applied.input_value_span == applied.output_value_span


def test_verify_rejects_any_unrequested_semantic_delta() -> None:
    before, candidate, after = prepared_patch()

    wrong_identity = after.model_copy(update={"source_file_id": "src-" + "0" * 16})
    with pytest.raises(AuthoringOperationError) as identity:
        verify_placement_anchor_coordinate_patch(
            before,
            wrong_identity,
            operation(),
            candidate,
        )
    assert identity.value.code == "AUTHORING_POSTCONDITION_SOURCE_MISMATCH"

    wrong_unit = after.model_copy(update={"source_unit": Unit.INCH})
    with pytest.raises(AuthoringOperationError) as metadata:
        verify_placement_anchor_coordinate_patch(
            before,
            wrong_unit,
            operation(),
            candidate,
        )
    assert metadata.value.code == "AUTHORING_POSTCONDITION_METADATA_CHANGED"

    fewer_rows = after.model_copy(update={"placements": after.placements[:2]})
    with pytest.raises(AuthoringOperationError) as count:
        verify_placement_anchor_coordinate_patch(
            before,
            fewer_rows,
            operation(),
            candidate,
        )
    assert count.value.code == "AUTHORING_POSTCONDITION_FEATURE_COUNT_CHANGED"

    moved_row = after.placements[0].model_copy(update={"position": Point(x=6.0, y=5.0)})
    moved = after.model_copy(update={"placements": (moved_row, *after.placements[1:])})
    with pytest.raises(AuthoringOperationError) as protected:
        verify_placement_anchor_coordinate_patch(
            before,
            moved,
            operation(),
            candidate,
        )
    assert protected.value.code == "AUTHORING_POSTCONDITION_PLACEMENT_CHANGED"

    wrong_targets = dataclasses.replace(
        candidate,
        affected_input_placement_ids=("plc-a", "plc-b"),
    )
    with pytest.raises(AuthoringOperationError) as target_count:
        verify_placement_anchor_coordinate_patch(
            before,
            after,
            operation(),
            wrong_targets,
        )
    assert target_count.value.code == "AUTHORING_POSTCONDITION_TARGET_COUNT_CHANGED"


def test_verify_rejects_protected_target_facts_and_coordinate_mismatch() -> None:
    before, candidate, after = prepared_patch()

    shifted_axis = after.placements[1].model_copy(
        update={"position": Point(x=10.0, y=6.0)}
    )
    tampered = after.model_copy(
        update={
            "placements": (after.placements[0], shifted_axis, *after.placements[2:])
        }
    )
    with pytest.raises(AuthoringOperationError) as axis_error:
        verify_placement_anchor_coordinate_patch(
            before,
            tampered,
            operation(),
            candidate,
        )
    assert axis_error.value.code == "AUTHORING_POSTCONDITION_PLACEMENT_CHANGED"

    renamed = after.placements[1].model_copy(update={"reference": "C9"})
    tampered_reference = after.model_copy(
        update={"placements": (after.placements[0], renamed, *after.placements[2:])}
    )
    with pytest.raises(AuthoringOperationError) as reference_error:
        verify_placement_anchor_coordinate_patch(
            before,
            tampered_reference,
            operation(),
            candidate,
        )
    assert reference_error.value.code == "AUTHORING_POSTCONDITION_PLACEMENT_CHANGED"

    wrong_value = after.placements[1].model_copy(
        update={"position": Point(x=11.0, y=5.0)}
    )
    tampered_value = after.model_copy(
        update={"placements": (after.placements[0], wrong_value, *after.placements[2:])}
    )
    with pytest.raises(AuthoringOperationError) as mismatch:
        verify_placement_anchor_coordinate_patch(
            before,
            tampered_value,
            operation(),
            candidate,
        )
    assert mismatch.value.code == "AUTHORING_POSTCONDITION_COORDINATE_MISMATCH"


def test_executor_patches_reparses_and_proves_the_delta() -> None:
    execution = PlacementAnchorCoordinateExecutor().execute(
        source(),
        PAYLOAD,
        operation(),
        parser_executor=inline_executor,
    )

    assert execution.payload == PAYLOAD.replace(b"C1,25,5,90", b"C1,10,5,90")
    assert execution.applied.kind == "set_placement_anchor_coordinate"
    assert execution.applied.new_position_mm == 10.0


def test_executor_rejects_a_mismatched_operation_model() -> None:
    mismatched = SetExcellonToolDiameter(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path=SUBJECT,
        source_file_id=source().source_file_id,
        source_sha256=source().sha256,
        tool_code="T01",
        expected_diameter_mm=0.15,
        new_diameter_mm=0.3,
        instruction="Mismatched operation model.",
    )
    with pytest.raises(OperationRegistryError) as caught:
        PlacementAnchorCoordinateExecutor().execute(
            source(),
            PAYLOAD,
            mismatched,
            parser_executor=inline_executor,
        )
    assert caught.value.code == "MODIFICATION_EXECUTOR_TYPE_MISMATCH"


def test_executor_surfaces_bounded_parser_failures() -> None:
    def fail_parser(job: ParserJob) -> ParserExecution:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            failure=ParserFailure(
                code="PARSER_TEST_FAILURE",
                detail="simulated bounded parser failure",
            ),
        )

    with pytest.raises(OperationExecutionError) as caught:
        PlacementAnchorCoordinateExecutor().execute(
            source(),
            PAYLOAD,
            operation(),
            parser_executor=fail_parser,
        )
    assert caught.value.code == "MODIFICATION_SOURCE_PARSE_FAILED"
