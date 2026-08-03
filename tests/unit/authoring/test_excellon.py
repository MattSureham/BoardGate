"""Constrained Excellon tool-diameter patch and semantic postconditions."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import boardgate.authoring.excellon as excellon_module
from boardgate.authoring.excellon import (
    AuthoringOperationError,
    ExcellonPatchCandidate,
    prepare_excellon_tool_diameter_patch,
    require_excellon_file_type,
    scan_excellon_tool_definitions,
    verify_excellon_tool_diameter_patch,
)
from boardgate.authoring.models import SetExcellonToolDiameter
from boardgate.domain.enums import FileType, Plating
from boardgate.domain.geometry import Point
from boardgate.domain.identifiers import source_file_id
from boardgate.parsers.excellon import ExcellonParseResult, parse_excellon

SUBJECT = "board-plated.drl"
PAYLOAD = (
    b"M48\r\n"
    b"METRIC,TZ,000.000\r\n"
    b";TYPE=PLATED\r\n"
    b"T01C0.150\r\n"
    b"T02C0.800\r\n"
    b"%\r\n"
    b"T01\r\n"
    b"X5.000Y5.000\r\n"
    b"T02\r\n"
    b"X8.000Y8.000\r\n"
    b"M30\r\n"
)


def parse_payload(
    payload: bytes, *, logical_path: str = SUBJECT
) -> ExcellonParseResult:
    digest = hashlib.sha256(payload).hexdigest()
    return parse_excellon(
        payload,
        logical_path=logical_path,
        source_file_id=source_file_id(logical_path, digest),
    )


def operation(
    payload: bytes = PAYLOAD,
    *,
    expected: float = 0.15,
    new: float = 0.3,
    tool_code: str = "T01",
) -> SetExcellonToolDiameter:
    digest = hashlib.sha256(payload).hexdigest()
    return SetExcellonToolDiameter(
        schema_version="1.0",
        operation_version="1.0",
        source_logical_path=SUBJECT,
        source_file_id=source_file_id(SUBJECT, digest),
        source_sha256=digest,
        tool_code=tool_code,
        expected_diameter_mm=expected,
        new_diameter_mm=new,
        instruction="Increase the selected round drill tool.",
    )


def prepared_patch(
    payload: bytes = PAYLOAD,
    *,
    request: SetExcellonToolDiameter | None = None,
) -> tuple[ExcellonParseResult, ExcellonPatchCandidate, ExcellonParseResult]:
    selected = request or operation(payload)
    before = parse_payload(payload)
    candidate = prepare_excellon_tool_diameter_patch(payload, before, selected)
    after = parse_excellon(
        candidate.payload,
        logical_path=SUBJECT,
        source_file_id=candidate.output_source_file_id,
    )
    return before, candidate, after


def test_scanner_returns_normalized_tools_and_exact_crlf_byte_spans() -> None:
    witnesses = scan_excellon_tool_definitions(PAYLOAD, subject=SUBJECT)

    assert [(item.tool_code, item.diameter_lexeme) for item in witnesses] == [
        ("T01", "0.150"),
        ("T02", "0.800"),
    ]
    first = witnesses[0]
    assert first.value_span.start_line == first.value_span.end_line == 4
    start = PAYLOAD.index(b"0.150")
    assert (first.value_span.start_byte, first.value_span.end_byte) == (
        start,
        start + len(b"0.150"),
    )


def test_scanner_limits_are_inclusive_and_reject_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(excellon_module, "MAX_EXCELLON_PATCH_BYTES", 8)
    assert scan_excellon_tool_definitions(b";123456\n", subject=SUBJECT) == ()
    with pytest.raises(AuthoringOperationError) as source_limit:
        scan_excellon_tool_definitions(b";1234567\n", subject=SUBJECT)
    assert source_limit.value.code == "AUTHORING_SOURCE_SIZE_LIMIT"

    monkeypatch.setattr(excellon_module, "MAX_EXCELLON_PATCH_BYTES", 1024)
    monkeypatch.setattr(excellon_module, "MAX_EXCELLON_LINE_BYTES", 8)
    assert scan_excellon_tool_definitions(b";1234567\n", subject=SUBJECT) == ()
    with pytest.raises(AuthoringOperationError) as line_limit:
        scan_excellon_tool_definitions(b";12345678\n", subject=SUBJECT)
    assert line_limit.value.code == "AUTHORING_EXCELLON_LINE_LIMIT"

    monkeypatch.setattr(excellon_module, "MAX_EXCELLON_LINE_BYTES", 4096)
    monkeypatch.setattr(excellon_module, "MAX_EXCELLON_LINES", 2)
    assert scan_excellon_tool_definitions(b"; one\n; two\n", subject=SUBJECT) == ()
    with pytest.raises(AuthoringOperationError) as line_count_limit:
        scan_excellon_tool_definitions(
            b"; one\n; two\n; three\n",
            subject=SUBJECT,
        )
    assert line_count_limit.value.code == "AUTHORING_EXCELLON_LINE_COUNT_LIMIT"

    monkeypatch.setattr(excellon_module, "MAX_EXCELLON_LINES", 1_000_000)
    monkeypatch.setattr(excellon_module, "MAX_EXCELLON_TOOL_DEFINITIONS", 2)
    assert (
        len(
            scan_excellon_tool_definitions(
                b"T01C0.100\nT02C0.200\n",
                subject=SUBJECT,
            )
        )
        == 2
    )
    with pytest.raises(AuthoringOperationError) as tool_limit:
        scan_excellon_tool_definitions(
            b"T01C0.100\nT02C0.200\nT03C0.300\n",
            subject=SUBJECT,
        )
    assert tool_limit.value.code == "AUTHORING_EXCELLON_TOOL_LIMIT"


def test_patch_changes_only_the_target_token_and_preserves_plating() -> None:
    selected = operation()
    before, candidate, after = prepared_patch(request=selected)

    expected = PAYLOAD.replace(b"T01C0.150", b"T01C0.300")
    assert candidate.payload == expected
    assert len(candidate.payload) == len(PAYLOAD)
    assert candidate.input_sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert candidate.output_sha256 == hashlib.sha256(expected).hexdigest()
    assert candidate.affected_input_drill_ids == (before.drills[0].drill_id,)
    assert [drill.diameter_mm for drill in after.drills] == [0.3, 0.8]
    assert all(drill.plating is Plating.PLATED for drill in after.drills)

    applied = verify_excellon_tool_diameter_patch(
        before,
        after,
        selected,
        candidate,
    )
    assert applied.input_value_span == applied.output_value_span
    assert applied.output_sha256 == candidate.output_sha256
    assert applied.affected_input_drill_ids == candidate.affected_input_drill_ids
    assert applied.affected_output_drill_ids == (after.drills[0].drill_id,)


@pytest.mark.parametrize(
    ("payload", "code"),
    (
        (
            b"M48\nMETRIC\nT01C.150\n%\nM30\n",
            "AUTHORING_EXCELLON_TOOL_DEFINITION_UNSUPPORTED",
        ),
        (
            b"M48\nMETRIC\nT01C0.150F10\n%\nM30\n",
            "AUTHORING_EXCELLON_TOOL_DEFINITION_UNSUPPORTED",
        ),
        (b"T1C0.150\nT01C0.150\n", "AUTHORING_EXCELLON_TOOL_DUPLICATE"),
    ),
)
def test_scanner_rejects_unsupported_or_duplicate_tool_definitions(
    payload: bytes,
    code: str,
) -> None:
    with pytest.raises(AuthoringOperationError) as caught:
        scan_excellon_tool_definitions(payload, subject=SUBJECT)
    assert caught.value.code == code


def test_patch_rejects_stale_digest_source_id_and_old_value() -> None:
    parsed = parse_payload(PAYLOAD)
    stale_digest = operation().model_copy(update={"source_sha256": "f" * 64})
    with pytest.raises(AuthoringOperationError) as digest_error:
        prepare_excellon_tool_diameter_patch(PAYLOAD, parsed, stale_digest)
    assert digest_error.value.code == "AUTHORING_SOURCE_SHA_MISMATCH"

    stale_id = operation().model_copy(update={"source_file_id": "src-ffffffffffffffff"})
    with pytest.raises(AuthoringOperationError) as id_error:
        prepare_excellon_tool_diameter_patch(PAYLOAD, parsed, stale_id)
    assert id_error.value.code == "AUTHORING_SOURCE_ID_MISMATCH"

    wrong_old_value = operation(expected=0.2)
    with pytest.raises(AuthoringOperationError) as old_value_error:
        prepare_excellon_tool_diameter_patch(PAYLOAD, parsed, wrong_old_value)
    assert old_value_error.value.code == "AUTHORING_PRECONDITION_MISMATCH"


def test_patch_rejects_missing_unused_and_unrepresentable_targets() -> None:
    parsed = parse_payload(PAYLOAD)
    missing = operation(tool_code="T03")
    with pytest.raises(AuthoringOperationError) as missing_error:
        prepare_excellon_tool_diameter_patch(PAYLOAD, parsed, missing)
    assert missing_error.value.code == "AUTHORING_EXCELLON_TOOL_NOT_FOUND"

    unused_payload = b"M48\nMETRIC,TZ,000.000\nT01C0.150\n%\nM30\n"
    with pytest.raises(AuthoringOperationError) as unused_error:
        prepare_excellon_tool_diameter_patch(
            unused_payload,
            parse_payload(unused_payload),
            operation(unused_payload),
        )
    assert unused_error.value.code == "AUTHORING_EXCELLON_TOOL_UNUSED"

    too_precise = operation(new=0.1555)
    with pytest.raises(AuthoringOperationError) as precision_error:
        prepare_excellon_tool_diameter_patch(PAYLOAD, parsed, too_precise)
    assert precision_error.value.code == "AUTHORING_EXCELLON_NEW_DIAMETER_PRECISION"

    too_wide = operation(new=10.0)
    with pytest.raises(AuthoringOperationError) as width_error:
        prepare_excellon_tool_diameter_patch(PAYLOAD, parsed, too_wide)
    assert width_error.value.code == "AUTHORING_EXCELLON_NEW_DIAMETER_WIDTH"


def test_patch_rejects_non_metric_incremental_and_diagnostic_sources() -> None:
    fixture_root = Path("tests/fixtures/parser/excellon")
    cases = (
        ("inch_hits.drl", 0.01, "AUTHORING_EXCELLON_UNIT_UNSUPPORTED"),
        ("incremental.drl", 0.3, "AUTHORING_EXCELLON_NOTATION_UNSUPPORTED"),
        ("warning.drl", 0.3, "AUTHORING_EXCELLON_DIAGNOSTIC_UNSUPPORTED"),
    )
    for filename, expected, code in cases:
        payload = (fixture_root / filename).read_bytes()
        parsed = parse_payload(payload)
        selected = operation(payload, expected=expected, new=expected + 0.1)
        with pytest.raises(AuthoringOperationError) as caught:
            prepare_excellon_tool_diameter_patch(payload, parsed, selected)
        assert caught.value.code == code


def test_patch_rejects_tool_shared_by_round_hit_and_slot() -> None:
    payload = (
        b"M48\nMETRIC,TZ,000.000\nT01C0.500\n%\nT01\n"
        b"X1.000Y1.000\nG00X2.000Y1.000\nM15\nG01X3.000Y1.000\nM16\nM30\n"
    )
    parsed = parse_payload(payload)
    assert parsed.drills and parsed.slots

    with pytest.raises(AuthoringOperationError) as caught:
        prepare_excellon_tool_diameter_patch(
            payload,
            parsed,
            operation(payload, expected=0.5, new=0.6),
        )
    assert caught.value.code == "AUTHORING_EXCELLON_SLOT_SCOPE_UNSUPPORTED"


def test_semantic_verification_rejects_unrelated_drill_change() -> None:
    selected = operation()
    before, candidate, after = prepared_patch(request=selected)
    changed_drill = after.drills[1].model_copy(update={"position": Point(x=9.0, y=8.0)})
    tampered = after.model_copy(update={"drills": (after.drills[0], changed_drill)})

    with pytest.raises(AuthoringOperationError) as caught:
        verify_excellon_tool_diameter_patch(before, tampered, selected, candidate)
    assert caught.value.code == "AUTHORING_POSTCONDITION_DRILL_CHANGED"


def test_target_type_check_is_explicit() -> None:
    require_excellon_file_type(FileType.EXCELLON, subject=SUBJECT)
    with pytest.raises(AuthoringOperationError) as caught:
        require_excellon_file_type(FileType.GERBER, subject=SUBJECT)
    assert caught.value.code == "AUTHORING_TARGET_TYPE_MISMATCH"
