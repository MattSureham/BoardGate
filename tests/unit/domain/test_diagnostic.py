"""Stable source-diagnostic domain tests."""

import pytest
from pydantic import ValidationError

from boardgate.domain.diagnostic import SourceDiagnostic, SourceDiagnosticLevel
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
