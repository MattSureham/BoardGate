"""Stable source diagnostics retained on normalized PCB projects."""

from enum import StrEnum

from pydantic import Field

from boardgate.domain.base import VersionedModel
from boardgate.domain.provenance import SourceSpan


class SourceDiagnosticLevel(StrEnum):
    """Effect of a source parser diagnostic."""

    WARNING = "WARNING"
    LIMITATION = "LIMITATION"
    ERROR = "ERROR"


class SourceDiagnostic(VersionedModel):
    """A stable parser warning, limitation, or failure tied to one source."""

    diagnostic_id: str = Field(pattern=r"^diagnostic-[0-9a-f]{16}$")
    source_file_id: str = Field(pattern=r"^src-[0-9a-f]{16}$")
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    level: SourceDiagnosticLevel
    message: str = Field(min_length=1, max_length=500)
    source_span: SourceSpan | None = None
