"""Shared parser diagnostics and result metadata."""

from enum import StrEnum

from pydantic import Field

from boardgate.domain.base import VersionedModel
from boardgate.domain.provenance import SourceSpan


class DiagnosticLevel(StrEnum):
    """Parser diagnostic effect."""

    WARNING = "WARNING"
    LIMITATION = "LIMITATION"


class ParserDiagnostic(VersionedModel):
    """Evidence-backed warning or explicit parser limitation."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    level: DiagnosticLevel
    message: str = Field(min_length=1, max_length=500)
    source_span: SourceSpan | None = None
