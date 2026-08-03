"""Bounded deterministic coupon writer emission and reparse postconditions."""

from __future__ import annotations

import pytest

import boardgate.authoring.coupon as coupon_module
from boardgate.application.parser_runner import ParserJob, run_parser
from boardgate.authoring.coupon import (
    GENERATION_PAYLOAD_PATHS,
    OUTLINE_PATH,
    PLATED_DRILL_PATH,
    GenerationOperationError,
    emit_coupon_payloads,
    verify_coupon_drills,
    verify_coupon_outline,
)
from boardgate.domain.enums import FileType
from boardgate.parsers.excellon import ExcellonParseResult
from boardgate.parsers.gerber import GerberParseResult

from .test_generation_models import operation


def _reparse(
    logical_path: str,
    file_type: FileType,
) -> ExcellonParseResult | GerberParseResult:
    payloads = {item.logical_path: item for item in emit_coupon_payloads(operation())}
    payload = payloads[logical_path]
    execution = run_parser(
        ParserJob(
            source_file_id=payload.source_file_id,
            logical_path=payload.logical_path,
            file_type=file_type,
            payload=payload.payload,
        )
    )
    assert execution.failure is None
    assert execution.result is not None
    result = execution.result
    assert isinstance(result, (ExcellonParseResult, GerberParseResult))
    return result


def test_emission_is_byte_deterministic_with_the_fixed_payload_set() -> None:
    first = emit_coupon_payloads(operation())
    second = emit_coupon_payloads(operation())

    assert tuple(sorted(item.logical_path for item in first)) == (
        GENERATION_PAYLOAD_PATHS
    )
    assert first == second
    assert all(item.sha256 for item in first)
    assert all(item.source_file_id for item in first)


def test_version_one_payload_hashes_remain_frozen() -> None:
    payloads = {
        item.logical_path: item.sha256 for item in emit_coupon_payloads(operation())
    }

    assert payloads == {
        "coupon-bottom-copper.gbl": (
            "d379ba3ff07139a5943b1c182ba69c778840d8d0b4818ef73c4d1007926847f8"
        ),
        "coupon-outline.gko": (
            "61ea46b5bf4bd829155771d806ce6566e8627e576432d2df55003493de1b5ee2"
        ),
        "coupon-plated.drl": (
            "efa7acf2aa79b361c14e09130af056437ce6115f3b284acdf482717894c11e25"
        ),
        "coupon-top-copper.gtl": (
            "0f767e78fc5b0a0a0cb519ab25467b74dcf1e82d2b344a7b978e30c6f148a41a"
        ),
    }


def test_emission_payload_size_guard_is_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(coupon_module, "MAX_GENERATED_PAYLOAD_BYTES", 16)

    with pytest.raises(GenerationOperationError) as caught:
        emit_coupon_payloads(operation())

    assert caught.value.code == "GENERATION_PAYLOAD_SIZE_LIMIT"


def test_drill_postcondition_accepts_the_exact_requested_holes() -> None:
    parsed = _reparse(PLATED_DRILL_PATH, FileType.EXCELLON)
    assert isinstance(parsed, ExcellonParseResult)
    payloads = {item.logical_path: item for item in emit_coupon_payloads(operation())}

    drill_ids = verify_coupon_drills(
        operation(),
        parsed,
        expected_source_file_id=payloads[PLATED_DRILL_PATH].source_file_id,
    )

    assert drill_ids == tuple(sorted(drill_ids))
    assert len(drill_ids) == len(operation().holes)


def test_drill_postcondition_rejects_source_identity_mismatch() -> None:
    parsed = _reparse(PLATED_DRILL_PATH, FileType.EXCELLON)
    assert isinstance(parsed, ExcellonParseResult)

    with pytest.raises(GenerationOperationError) as caught:
        verify_coupon_drills(
            operation(),
            parsed,
            expected_source_file_id="src-0000000000000000",
        )

    assert caught.value.code == "GENERATION_POSTCONDITION_SOURCE_MISMATCH"


def test_drill_postcondition_rejects_parser_diagnostics() -> None:
    parsed = _reparse(PLATED_DRILL_PATH, FileType.EXCELLON)
    assert isinstance(parsed, ExcellonParseResult)
    tampered = parsed.model_copy(update={"warnings": ("simulated warning",)})
    payloads = {item.logical_path: item for item in emit_coupon_payloads(operation())}

    with pytest.raises(GenerationOperationError) as caught:
        verify_coupon_drills(
            operation(),
            tampered,
            expected_source_file_id=payloads[PLATED_DRILL_PATH].source_file_id,
        )

    assert caught.value.code == "GENERATION_POSTCONDITION_DIAGNOSTICS"


def test_outline_postcondition_rejects_parser_limitations() -> None:
    parsed = _reparse(OUTLINE_PATH, FileType.GERBER)
    assert isinstance(parsed, GerberParseResult)
    tampered = parsed.model_copy(update={"limitations": ("simulated limitation",)})
    payloads = {item.logical_path: item for item in emit_coupon_payloads(operation())}

    with pytest.raises(GenerationOperationError) as caught:
        verify_coupon_outline(
            operation(),
            tampered,
            expected_source_file_id=payloads[OUTLINE_PATH].source_file_id,
        )

    assert caught.value.code == "GENERATION_POSTCONDITION_DIAGNOSTICS"
