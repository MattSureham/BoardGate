"""Constrained placement reference-designator patch and semantic postconditions."""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

import boardgate.authoring.placement as placement_module
from boardgate.application.modification_registry import (
    OperationExecutionError,
    OperationRegistryError,
    PlacementReferenceDesignatorExecutor,
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
    SetPlacementReferenceDesignator,
)
from boardgate.authoring.placement import (
    PlacementPatchCandidate,
    prepare_placement_reference_designator_patch,
    scan_placement_references,
    verify_placement_reference_designator_patch,
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
    b"C1,7,5,90,Top,mm,no\n"
    b"R9,9,5,0,Top,mm,yes\n"
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
    expected: str = "C1",
    new: str = "R2",
) -> SetPlacementReferenceDesignator:
    digest = hashlib.sha256(payload).hexdigest()
    return SetPlacementReferenceDesignator(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path=SUBJECT,
        source_file_id=source_file_id(SUBJECT, digest),
        source_sha256=digest,
        expected_reference=expected,
        new_reference=new,
        instruction="Rename the explicitly selected placement reference.",
    )


def prepared_patch(
    payload: bytes = PAYLOAD,
    *,
    request: SetPlacementReferenceDesignator | None = None,
) -> tuple[PlacementParseResult, PlacementPatchCandidate, PlacementParseResult]:
    selected = request or operation(payload)
    before = parse_payload(payload)
    candidate = prepare_placement_reference_designator_patch(
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


def test_scanner_returns_row_references_and_exact_byte_spans() -> None:
    witnesses = scan_placement_references(PAYLOAD, subject=SUBJECT)

    assert [(item.row_index, item.reference) for item in witnesses] == [
        (0, "R1"),
        (1, "C1"),
        (2, "R9"),
    ]
    target = witnesses[1]
    assert target.value_span.start_line == target.value_span.end_line == 3
    start = PAYLOAD.index(b"C1")
    assert (target.value_span.start_byte, target.value_span.end_byte) == (
        start,
        start + len(b"C1"),
    )


def test_scanner_locates_the_token_inside_a_padded_cell() -> None:
    payload = PAYLOAD.replace(b"C1,7,5,90", b" C1 ,7,5,90")
    witnesses = scan_placement_references(payload, subject=SUBJECT)

    target = witnesses[1]
    assert target.reference == "C1"
    start = payload.index(b"C1")
    assert (target.value_span.start_byte, target.value_span.end_byte) == (
        start,
        start + len(b"C1"),
    )


def test_scanner_rejects_multiline_and_embedded_delimiter_rows() -> None:
    multiline = PAYLOAD.replace(b"C1,7,5,90", b'"C\n1",7,5,90')
    with pytest.raises(AuthoringOperationError) as multiline_error:
        scan_placement_references(multiline, subject=SUBJECT)
    assert multiline_error.value.code == "AUTHORING_PLACEMENT_ROW_UNSUPPORTED"

    embedded = PAYLOAD.replace(b"C1,7,5,90", b'"C,1",7,5,90')
    with pytest.raises(AuthoringOperationError) as embedded_error:
        scan_placement_references(embedded, subject=SUBJECT)
    assert embedded_error.value.code == "AUTHORING_PLACEMENT_ROW_UNSUPPORTED"

    with pytest.raises(AuthoringOperationError) as table_error:
        scan_placement_references(b"", subject=SUBJECT)
    assert table_error.value.code == "AUTHORING_PLACEMENT_TABLE_UNSUPPORTED"


def test_scanner_limits_are_inclusive_and_reject_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(placement_module, "MAX_PLACEMENT_PATCH_BYTES", len(PAYLOAD))
    assert len(scan_placement_references(PAYLOAD, subject=SUBJECT)) == 3
    monkeypatch.setattr(
        placement_module,
        "MAX_PLACEMENT_PATCH_BYTES",
        len(PAYLOAD) - 1,
    )
    with pytest.raises(AuthoringOperationError) as source_limit:
        scan_placement_references(PAYLOAD, subject=SUBJECT)
    assert source_limit.value.code == "AUTHORING_SOURCE_SIZE_LIMIT"

    monkeypatch.setattr(
        placement_module,
        "MAX_PLACEMENT_PATCH_BYTES",
        50 * 1024 * 1024,
    )
    longest_row = max(
        (len(line) for line in PAYLOAD.split(b"\n")[1:]),
        default=0,
    )
    monkeypatch.setattr(placement_module, "MAX_PLACEMENT_LINE_BYTES", longest_row)
    assert len(scan_placement_references(PAYLOAD, subject=SUBJECT)) == 3
    monkeypatch.setattr(
        placement_module,
        "MAX_PLACEMENT_LINE_BYTES",
        longest_row - 1,
    )
    with pytest.raises(AuthoringOperationError) as line_limit:
        scan_placement_references(PAYLOAD, subject=SUBJECT)
    assert line_limit.value.code == "AUTHORING_PLACEMENT_LINE_LIMIT"

    monkeypatch.setattr(
        placement_module,
        "MAX_PLACEMENT_LINE_BYTES",
        1024 * 1024,
    )
    monkeypatch.setattr(placement_module, "MAX_PLACEMENT_LINES", 4)
    assert len(scan_placement_references(PAYLOAD, subject=SUBJECT)) == 3
    monkeypatch.setattr(placement_module, "MAX_PLACEMENT_LINES", 3)
    with pytest.raises(AuthoringOperationError) as line_count_limit:
        scan_placement_references(PAYLOAD, subject=SUBJECT)
    assert line_count_limit.value.code == "AUTHORING_PLACEMENT_LINE_COUNT_LIMIT"


def test_prepare_replaces_exactly_one_same_width_token() -> None:
    before, candidate, after = prepared_patch()

    assert candidate.payload == PAYLOAD.replace(b"C1,", b"R2,")
    assert len(candidate.payload) == len(PAYLOAD)
    assert candidate.input_value_span == candidate.output_value_span
    assert candidate.target_row_index == 1
    assert candidate.affected_input_placement_ids == (
        before.placements[1].provenance.object_id,
    )
    assert [placement.reference for placement in after.placements] == [
        "R1",
        "R2",
        "R9",
    ]


def test_prepare_rejects_stale_identity_and_missing_or_ambiguous_targets() -> None:
    stale = operation().model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises(AuthoringOperationError) as sha_error:
        prepare_placement_reference_designator_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            stale,
        )
    assert sha_error.value.code == "AUTHORING_SOURCE_SHA_MISMATCH"

    stale_id = operation().model_copy(update={"source_file_id": "src-" + "0" * 16})
    with pytest.raises(AuthoringOperationError) as id_error:
        prepare_placement_reference_designator_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            stale_id,
        )
    assert id_error.value.code == "AUTHORING_SOURCE_ID_MISMATCH"

    with pytest.raises(AuthoringOperationError) as not_found:
        prepare_placement_reference_designator_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            operation(expected="R7"),
        )
    assert not_found.value.code == "AUTHORING_PLACEMENT_REFERENCE_NOT_FOUND"

    duplicated = PAYLOAD.replace(b"R1,5,5", b"C1,5,5")
    with pytest.raises(AuthoringOperationError) as ambiguous:
        prepare_placement_reference_designator_patch(
            duplicated,
            parse_payload(duplicated),
            operation(duplicated),
        )
    assert ambiguous.value.code == "AUTHORING_PLACEMENT_REFERENCE_AMBIGUOUS"


def test_prepare_rejects_unsupported_token_forms() -> None:
    lowercase = PAYLOAD.replace(b"C1,7,5,90", b"c1,7,5,90")
    with pytest.raises(AuthoringOperationError) as lowercase_error:
        prepare_placement_reference_designator_patch(
            lowercase,
            parse_payload(lowercase),
            operation(lowercase),
        )
    assert lowercase_error.value.code == "AUTHORING_PLACEMENT_REFERENCE_UNSUPPORTED"

    quoted = PAYLOAD.replace(b"C1,7,5,90", b'"C1",7,5,90')
    with pytest.raises(AuthoringOperationError) as quoted_error:
        prepare_placement_reference_designator_patch(
            quoted,
            parse_payload(quoted),
            operation(quoted),
        )
    assert quoted_error.value.code == "AUTHORING_PLACEMENT_REFERENCE_UNSUPPORTED"


def test_prepare_rejects_colliding_and_mismatched_width_new_references() -> None:
    with pytest.raises(AuthoringOperationError) as collision:
        prepare_placement_reference_designator_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            operation(new="R1"),
        )
    assert collision.value.code == "AUTHORING_PLACEMENT_NEW_REFERENCE_COLLISION"

    with pytest.raises(AuthoringOperationError) as width:
        prepare_placement_reference_designator_patch(
            PAYLOAD,
            parse_payload(PAYLOAD),
            operation(new="R22"),
        )
    assert width.value.code == "AUTHORING_PLACEMENT_NEW_REFERENCE_WIDTH"


def test_verify_proves_the_exact_requested_rename() -> None:
    before, candidate, after = prepared_patch()
    applied = verify_placement_reference_designator_patch(
        before,
        after,
        operation(),
        candidate,
    )

    assert applied.old_reference == "C1"
    assert applied.new_reference == "R2"
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
        verify_placement_reference_designator_patch(
            before,
            wrong_identity,
            operation(),
            candidate,
        )
    assert identity.value.code == "AUTHORING_POSTCONDITION_SOURCE_MISMATCH"

    wrong_unit = after.model_copy(update={"source_unit": Unit.INCH})
    with pytest.raises(AuthoringOperationError) as metadata:
        verify_placement_reference_designator_patch(
            before,
            wrong_unit,
            operation(),
            candidate,
        )
    assert metadata.value.code == "AUTHORING_POSTCONDITION_METADATA_CHANGED"

    fewer_rows = after.model_copy(update={"placements": after.placements[:2]})
    with pytest.raises(AuthoringOperationError) as count:
        verify_placement_reference_designator_patch(
            before,
            fewer_rows,
            operation(),
            candidate,
        )
    assert count.value.code == "AUTHORING_POSTCONDITION_FEATURE_COUNT_CHANGED"

    moved_row = after.placements[0].model_copy(update={"position": Point(x=6.0, y=5.0)})
    moved = after.model_copy(update={"placements": (moved_row, *after.placements[1:])})
    with pytest.raises(AuthoringOperationError) as protected:
        verify_placement_reference_designator_patch(
            before,
            moved,
            operation(),
            candidate,
        )
    assert protected.value.code == "AUTHORING_POSTCONDITION_PLACEMENT_CHANGED"

    renamed_elsewhere = after.placements[0].model_copy(update={"reference": "C9"})
    renamed = after.model_copy(
        update={"placements": (renamed_elsewhere, *after.placements[1:])}
    )
    with pytest.raises(AuthoringOperationError) as reference:
        verify_placement_reference_designator_patch(
            before,
            renamed,
            operation(),
            candidate,
        )
    assert reference.value.code == "AUTHORING_POSTCONDITION_REFERENCE_MISMATCH"

    wrong_targets = dataclasses.replace(
        candidate,
        affected_input_placement_ids=("plc-a", "plc-b"),
    )
    with pytest.raises(AuthoringOperationError) as target_count:
        verify_placement_reference_designator_patch(
            before,
            after,
            operation(),
            wrong_targets,
        )
    assert target_count.value.code == "AUTHORING_POSTCONDITION_TARGET_COUNT_CHANGED"


def test_executor_patches_reparses_and_proves_the_delta() -> None:
    execution = PlacementReferenceDesignatorExecutor().execute(
        source(),
        PAYLOAD,
        operation(),
        parser_executor=inline_executor,
    )

    assert execution.payload == PAYLOAD.replace(b"C1,", b"R2,")
    assert execution.applied.kind == "set_placement_reference_designator"
    assert execution.applied.new_reference == "R2"


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
        PlacementReferenceDesignatorExecutor().execute(
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
        PlacementReferenceDesignatorExecutor().execute(
            source(),
            PAYLOAD,
            operation(),
            parser_executor=fail_parser,
        )
    assert caught.value.code == "MODIFICATION_SOURCE_PARSE_FAILED"
