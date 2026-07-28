"""Stable source and analysis diagnostic domain tests."""

import pytest
from pydantic import ValidationError

from boardgate.domain.diagnostic import (
    AnalysisDiagnostic,
    AnalysisDiagnosticCategory,
    AnalysisStage,
    SourceDiagnostic,
    SourceDiagnosticLevel,
    ordered_analysis_diagnostics,
)
from boardgate.domain.provenance import SourceSpan


def test_source_diagnostic_round_trip() -> None:
    diagnostic = SourceDiagnostic(
        diagnostic_id="diagnostic-0123456789abcdef",
        source_file_id="src-fedcba9876543210",
        code="PARSER_LIMITATION",
        level=SourceDiagnosticLevel.LIMITATION,
        message="An unsupported command was retained as a limitation.",
        source_span=SourceSpan(start_line=4, end_line=4),
    )

    assert (
        SourceDiagnostic.model_validate_json(diagnostic.model_dump_json()) == diagnostic
    )


def test_source_diagnostic_rejects_unstable_identifiers() -> None:
    with pytest.raises(ValidationError):
        SourceDiagnostic(
            diagnostic_id="diagnostic-random",
            source_file_id="src-fedcba9876543210",
            code="PARSER_LIMITATION",
            level=SourceDiagnosticLevel.LIMITATION,
            message="invalid",
        )


def _analysis_diagnostic(
    code: str = "PROJECT_BUILD_UNAVAILABLE",
) -> AnalysisDiagnostic:
    return AnalysisDiagnostic(
        category=AnalysisDiagnosticCategory.ANALYSIS,
        stage=AnalysisStage.PROJECT_CONSTRUCTION,
        code=code,
        summary="The normalized project could not be constructed.",
    )


def test_analysis_diagnostic_is_strict_versioned_and_round_trips() -> None:
    diagnostic = _analysis_diagnostic()

    restored = AnalysisDiagnostic.model_validate_json(diagnostic.model_dump_json())

    assert restored == diagnostic
    assert restored.schema_version == "1.0"
    with pytest.raises(ValidationError, match="Extra inputs"):
        AnalysisDiagnostic.model_validate(
            {**diagnostic.model_dump(), "exception": "hidden"}
        )


@pytest.mark.parametrize(
    "summary",
    [
        "Parser failed at /Users/operator/private/board.gbr.",
        "Parser failed at /tmp.",
        r"Parser failed at C:\Users\operator\board.gbr.",
        "ValueError('raw parser payload')",
        "RuntimeError: raw parser payload",
        "Traceback (most recent call last): details",
        "Parser object at 0x7ffee0123456 failed.",
        "Parser failed.\nsecret detail",
        " file could not be parsed.",
    ],
)
def test_analysis_diagnostic_rejects_host_or_exception_details(
    summary: str,
) -> None:
    with pytest.raises(ValidationError):
        AnalysisDiagnostic(
            category=AnalysisDiagnosticCategory.PARSER,
            stage=AnalysisStage.PARSING,
            code="PARSER_UNAVAILABLE",
            summary=summary,
        )


def test_analysis_diagnostics_have_canonical_unique_order() -> None:
    later = _analysis_diagnostic("PROJECT_SOURCE_CHANGED")
    earlier = _analysis_diagnostic("PROJECT_BUILD_UNAVAILABLE")

    ordered = ordered_analysis_diagnostics((later, earlier, later))

    assert ordered == (earlier, later)
