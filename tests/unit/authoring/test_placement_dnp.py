"""Constrained placement DNP-state patch and semantic postconditions."""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from boardgate.application.modification_registry import (
    OperationExecutionError,
    OperationRegistryError,
    PlacementDnpStateExecutor,
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
    SetPlacementDnpState,
)
from boardgate.authoring.placement import (
    PlacementPatchCandidate,
    prepare_placement_dnp_state_patch,
    scan_placement_dnp_states,
    verify_placement_dnp_state_patch,
)
from boardgate.domain.enums import FileType
from boardgate.domain.geometry import Unit
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.source import SourceFile
from boardgate.parsers.errors import ParserError
from boardgate.parsers.placement import PlacementParseResult, parse_placement_csv

SUBJECT = "component-placement.csv"
PAYLOAD = (
    b"Reference,X,Y,Rotation,Side,Unit,DNP\n"
    b"R1,5,5,0,Top,mm,0\n"
    b"C1,10,5,90,Top,mm,0\n"
    b"U1,12,10,0,Top,mm,1\n"
)


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
    reference: str = "C1",
    expected: bool = False,
    new: bool = True,
) -> SetPlacementDnpState:
    digest = hashlib.sha256(payload).hexdigest()
    return SetPlacementDnpState(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path=SUBJECT,
        source_file_id=source_file_id(SUBJECT, digest),
        source_sha256=digest,
        reference=reference,
        expected_dnp=expected,
        new_dnp=new,
        instruction="Set the explicitly selected placement DNP state.",
    )


def prepared_patch(
    payload: bytes = PAYLOAD,
    *,
    request: SetPlacementDnpState | None = None,
) -> tuple[PlacementParseResult, PlacementPatchCandidate, PlacementParseResult]:
    selected = request or operation(payload)
    before = parse_payload(payload)
    candidate = prepare_placement_dnp_state_patch(
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


def test_scanner_returns_row_states_and_exact_byte_spans() -> None:
    witnesses = scan_placement_dnp_states(PAYLOAD, subject=SUBJECT)

    assert [(item.row_index, item.reference) for item in witnesses] == [
        (0, "R1"),
        (1, "C1"),
        (2, "U1"),
    ]
    assert [item.value for item in witnesses] == [False, False, True]
    target = witnesses[1]
    assert target.dnp_lexeme == "0"
    assert target.value_span.start_line == target.value_span.end_line == 3
    start = PAYLOAD.index(b"C1,10,5,90,Top,mm,") + len(b"C1,10,5,90,Top,mm,")
    assert (target.value_span.start_byte, target.value_span.end_byte) == (
        start,
        start + 1,
    )


def test_scanner_locates_the_token_inside_a_padded_cell() -> None:
    payload = PAYLOAD.replace(b"C1,10,5,90,Top,mm,0", b"C1,10,5,90,Top,mm, 0 ")
    witnesses = scan_placement_dnp_states(payload, subject=SUBJECT)

    target = witnesses[1]
    assert target.dnp_lexeme == "0"
    assert target.value is False
    start = payload.index(b"Top,mm, 0") + len(b"Top,mm, ")
    assert (target.value_span.start_byte, target.value_span.end_byte) == (
        start,
        start + 1,
    )


@pytest.mark.parametrize("token", (b"yes", b"no", b"true", b"false", b"2", b""))
def test_scanner_marks_non_plain_tokens_as_unsupported(token: bytes) -> None:
    payload = PAYLOAD.replace(b"C1,10,5,90,Top,mm,0", b"C1,10,5,90,Top,mm," + token)
    witnesses = scan_placement_dnp_states(payload, subject=SUBJECT)

    assert witnesses[1].dnp_lexeme == token.decode("ascii")
    assert witnesses[1].value is None


@pytest.mark.parametrize("header", (b"Fitted", b"Populate"))
def test_scanner_rejects_inverted_dnp_columns(header: bytes) -> None:
    payload = PAYLOAD.replace(b",DNP\n", b"," + header + b"\n")
    with pytest.raises(AuthoringOperationError) as caught:
        scan_placement_dnp_states(payload, subject=SUBJECT)
    assert caught.value.code == "AUTHORING_PLACEMENT_DNP_COLUMN_UNSUPPORTED"


def test_scanner_rejects_sources_without_a_dnp_column() -> None:
    payload = (
        PAYLOAD.replace(b",DNP\n", b"\n")
        .replace(b",0\n", b"\n")
        .replace(b",1\n", b"\n")
    )
    with pytest.raises(AuthoringOperationError) as caught:
        scan_placement_dnp_states(payload, subject=SUBJECT)
    assert caught.value.code == "AUTHORING_PLACEMENT_TABLE_UNSUPPORTED"


def test_prepare_replaces_exactly_one_same_width_token() -> None:
    before, candidate, after = prepared_patch()

    assert candidate.payload == PAYLOAD.replace(
        b"C1,10,5,90,Top,mm,0", b"C1,10,5,90,Top,mm,1"
    )
    assert len(candidate.payload) == len(PAYLOAD)
    assert candidate.input_value_span == candidate.output_value_span
    assert candidate.target_row_index == 1
    assert candidate.affected_input_placement_ids == (
        before.placements[1].provenance.object_id,
    )
    assert [placement.dnp for placement in after.placements] == [False, True, True]


def test_prepare_clears_a_set_dnp_token() -> None:
    before, candidate, after = prepared_patch(
        request=operation(reference="U1", expected=True, new=False)
    )

    assert candidate.payload == PAYLOAD.replace(
        b"U1,12,10,0,Top,mm,1", b"U1,12,10,0,Top,mm,0"
    )
    assert after.placements[2].dnp is False
    assert candidate.affected_input_placement_ids == (
        before.placements[2].provenance.object_id,
    )


def test_prepare_rejects_stale_identity_and_missing_or_ambiguous_targets() -> None:
    stale = operation().model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises(AuthoringOperationError) as sha_error:
        prepare_placement_dnp_state_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            stale,
        )
    assert sha_error.value.code == "AUTHORING_SOURCE_SHA_MISMATCH"

    stale_id = operation().model_copy(update={"source_file_id": "src-" + "0" * 16})
    with pytest.raises(AuthoringOperationError) as id_error:
        prepare_placement_dnp_state_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            stale_id,
        )
    assert id_error.value.code == "AUTHORING_SOURCE_ID_MISMATCH"

    with pytest.raises(AuthoringOperationError) as not_found:
        prepare_placement_dnp_state_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            operation(reference="R7"),
        )
    assert not_found.value.code == "AUTHORING_PLACEMENT_REFERENCE_NOT_FOUND"

    duplicated = PAYLOAD.replace(b"R1,5,5", b"C1,5,5")
    with pytest.raises(AuthoringOperationError) as ambiguous:
        prepare_placement_dnp_state_patch(
            duplicated,
            parse_payload(duplicated),
            operation(duplicated),
        )
    assert ambiguous.value.code == "AUTHORING_PLACEMENT_REFERENCE_AMBIGUOUS"


def test_prepare_rejects_unsupported_token_forms() -> None:
    worded = PAYLOAD.replace(b"C1,10,5,90,Top,mm,0", b"C1,10,5,90,Top,mm,no")
    with pytest.raises(AuthoringOperationError) as token_error:
        prepare_placement_dnp_state_patch(
            worded,
            parse_payload(worded),
            operation(worded),
        )
    assert token_error.value.code == "AUTHORING_PLACEMENT_DNP_UNSUPPORTED"

    lowercase = PAYLOAD.replace(b"C1,10,5,90", b"c1,10,5,90")
    with pytest.raises(AuthoringOperationError) as reference_error:
        prepare_placement_dnp_state_patch(
            lowercase,
            parse_payload(lowercase),
            operation(lowercase),
        )
    assert reference_error.value.code == "AUTHORING_PLACEMENT_REFERENCE_UNSUPPORTED"


def test_prepare_rejects_a_mismatched_expected_state() -> None:
    with pytest.raises(AuthoringOperationError) as caught:
        prepare_placement_dnp_state_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            operation(expected=True, new=False),
        )
    assert caught.value.code == "AUTHORING_PRECONDITION_MISMATCH"


def test_verify_proves_the_exact_requested_change() -> None:
    before, candidate, after = prepared_patch()
    applied = verify_placement_dnp_state_patch(
        before,
        after,
        operation(),
        candidate,
    )

    assert applied.kind == "set_placement_dnp_state"
    assert applied.adapter_id == "boardgate-placement-dnp-state-patch"
    assert applied.reference == "C1"
    assert applied.old_dnp is False
    assert applied.new_dnp is True
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
        verify_placement_dnp_state_patch(
            before,
            wrong_identity,
            operation(),
            candidate,
        )
    assert identity.value.code == "AUTHORING_POSTCONDITION_SOURCE_MISMATCH"

    wrong_unit = after.model_copy(update={"source_unit": Unit.INCH})
    with pytest.raises(AuthoringOperationError) as metadata:
        verify_placement_dnp_state_patch(
            before,
            wrong_unit,
            operation(),
            candidate,
        )
    assert metadata.value.code == "AUTHORING_POSTCONDITION_METADATA_CHANGED"

    fewer_rows = after.model_copy(update={"placements": after.placements[:2]})
    with pytest.raises(AuthoringOperationError) as count:
        verify_placement_dnp_state_patch(
            before,
            fewer_rows,
            operation(),
            candidate,
        )
    assert count.value.code == "AUTHORING_POSTCONDITION_FEATURE_COUNT_CHANGED"

    moved_row = after.placements[0].model_copy(update={"dnp": True})
    moved = after.model_copy(update={"placements": (moved_row, *after.placements[1:])})
    with pytest.raises(AuthoringOperationError) as protected:
        verify_placement_dnp_state_patch(
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
        verify_placement_dnp_state_patch(
            before,
            after,
            operation(),
            wrong_targets,
        )
    assert target_count.value.code == "AUTHORING_POSTCONDITION_TARGET_COUNT_CHANGED"


def test_verify_rejects_protected_target_facts_and_state_mismatch() -> None:
    before, candidate, after = prepared_patch()

    renamed = after.placements[1].model_copy(update={"reference": "C9"})
    tampered_reference = after.model_copy(
        update={"placements": (after.placements[0], renamed, *after.placements[2:])}
    )
    with pytest.raises(AuthoringOperationError) as reference_error:
        verify_placement_dnp_state_patch(
            before,
            tampered_reference,
            operation(),
            candidate,
        )
    assert reference_error.value.code == "AUTHORING_POSTCONDITION_PLACEMENT_CHANGED"

    wrong_state = after.placements[1].model_copy(update={"dnp": False})
    tampered_state = after.model_copy(
        update={"placements": (after.placements[0], wrong_state, *after.placements[2:])}
    )
    with pytest.raises(AuthoringOperationError) as mismatch:
        verify_placement_dnp_state_patch(
            before,
            tampered_state,
            operation(),
            candidate,
        )
    assert mismatch.value.code == "AUTHORING_POSTCONDITION_DNP_MISMATCH"


def test_executor_patches_reparses_and_proves_the_delta() -> None:
    execution = PlacementDnpStateExecutor().execute(
        source(),
        PAYLOAD,
        operation(),
        parser_executor=inline_executor,
    )

    assert execution.payload == PAYLOAD.replace(
        b"C1,10,5,90,Top,mm,0", b"C1,10,5,90,Top,mm,1"
    )
    assert execution.applied.kind == "set_placement_dnp_state"
    assert execution.applied.new_dnp is True


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
        PlacementDnpStateExecutor().execute(
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
        PlacementDnpStateExecutor().execute(
            source(),
            PAYLOAD,
            operation(),
            parser_executor=fail_parser,
        )
    assert caught.value.code == "MODIFICATION_SOURCE_PARSE_FAILED"
