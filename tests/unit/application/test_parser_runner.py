"""Spawn-isolated parser runner tests."""

import pytest
from pydantic import ValidationError

from boardgate.application.parser_runner import (
    ParserExecution,
    ParserJob,
    run_parser,
)
from boardgate.domain.enums import FileType
from boardgate.parsers import BOMParseResult

SOURCE_ID = "src-0123456789abcdef"


def _job(payload: bytes) -> ParserJob:
    return ParserJob(
        source_file_id=SOURCE_ID,
        logical_path="bom.csv",
        file_type=FileType.BOM_CSV,
        payload=payload,
    )


def test_isolated_parser_returns_only_normalized_boardgate_model() -> None:
    execution = run_parser(
        _job(b"Reference,Qty,Value\nR1,1,10k\n"),
        timeout_seconds=10.0,
    )

    assert execution.failure is None
    assert isinstance(execution.result, BOMParseResult)
    assert execution.result.items[0].references == ("R1",)


def test_isolated_parser_returns_typed_adapter_failure() -> None:
    execution = run_parser(
        _job(b"Value,Qty\n10k,1\n"),
        timeout_seconds=10.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "TABULAR_REQUIRED_COLUMN"
    assert "references" in execution.failure.detail


def test_isolated_parser_timeout_is_typed_and_cleanup_completes() -> None:
    execution = run_parser(
        _job(b"Reference\nR1\n"),
        timeout_seconds=1e-9,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "PARSER_TIMEOUT"


def test_parser_job_and_execution_invariants_are_strict() -> None:
    with pytest.raises(ValidationError):
        ParserJob(
            source_file_id=SOURCE_ID,
            logical_path="unknown.bin",
            file_type=FileType.UNKNOWN,
            payload=b"",
        )
    with pytest.raises(ValueError, match="exactly one"):
        ParserExecution(
            file_type=FileType.BOM_CSV,
            source_file_id=SOURCE_ID,
        )
    with pytest.raises(ValueError, match="positive finite"):
        run_parser(_job(b"Reference\nR1\n"), timeout_seconds=0.0)
