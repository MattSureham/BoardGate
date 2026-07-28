"""Stable source and pipeline diagnostics exposed at public boundaries."""

import re
from collections.abc import Iterable
from enum import StrEnum

from pydantic import Field, field_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.provenance import SourceSpan

_ABSOLUTE_POSIX_PATH = re.compile(
    r"""(?:^|[\s("'=:])/(?!/)[^/\s"'():]+(?:/[^/\s"'():]+)*"""
)
_ABSOLUTE_WINDOWS_PATH = re.compile(r"(?i)(?:^|[\s(\"'=])(?:[a-z]:[\\/]|\\\\)")
_EXCEPTION_REPR = re.compile(
    r"(?:Traceback \(most recent call last\)|"
    r"\b[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception)\s*(?:\(|:)|"
    r"<[^>\r\n]*\bobject at 0x[0-9a-fA-F]+>)"
)
_MEMORY_ADDRESS = re.compile(r"\b0x[0-9a-fA-F]{6,}\b")


def validate_safe_diagnostic_summary(value: str) -> str:
    """Reject unstable exception rendering, control text, and host paths."""
    if value != value.strip():
        raise ValueError("diagnostic summary must not have surrounding whitespace")
    if any(character in value for character in ("\r", "\n", "\t", "\x00")):
        raise ValueError("diagnostic summary must be a single printable line")
    if (
        "file://" in value.casefold()
        or _ABSOLUTE_POSIX_PATH.search(value)
        or _ABSOLUTE_WINDOWS_PATH.search(value)
    ):
        raise ValueError("diagnostic summary must not expose an absolute host path")
    if _EXCEPTION_REPR.search(value) or _MEMORY_ADDRESS.search(value):
        raise ValueError("diagnostic summary must not contain an exception repr")
    return value


class AnalysisDiagnosticCategory(StrEnum):
    """Stable fault taxonomy independent of exception implementation details."""

    INPUT = "INPUT"
    CONFIGURATION = "CONFIGURATION"
    SECURITY = "SECURITY"
    PARSER = "PARSER"
    ANALYSIS = "ANALYSIS"
    OUTPUT = "OUTPUT"
    INTERNAL = "INTERNAL"


class AnalysisStage(StrEnum):
    """Stable pipeline stage associated with an analysis diagnostic."""

    DISCOVERY = "DISCOVERY"
    CONFIGURATION = "CONFIGURATION"
    INGESTION = "INGESTION"
    PARSING = "PARSING"
    NORMALIZATION = "NORMALIZATION"
    PROJECT_CONSTRUCTION = "PROJECT_CONSTRUCTION"
    RULE_EXECUTION = "RULE_EXECUTION"
    REPORT_COMPOSITION = "REPORT_COMPOSITION"
    SVG_RENDERING = "SVG_RENDERING"
    ARTIFACT_VALIDATION = "ARTIFACT_VALIDATION"
    PUBLICATION = "PUBLICATION"


class AnalysisDiagnostic(VersionedModel):
    """Sanitized run-level explanation retained in ``findings.json``."""

    category: AnalysisDiagnosticCategory
    stage: AnalysisStage
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    summary: str = Field(min_length=1, max_length=500)

    @field_validator("summary")
    @classmethod
    def require_sanitized_summary(cls, value: str) -> str:
        """Prevent persistence of host-specific or exception-derived text."""
        return validate_safe_diagnostic_summary(value)


def ordered_analysis_diagnostics(
    diagnostics: Iterable[AnalysisDiagnostic],
) -> tuple[AnalysisDiagnostic, ...]:
    """Deduplicate and order run-level diagnostics deterministically."""
    by_key = {
        (
            diagnostic.category.value,
            diagnostic.stage.value,
            diagnostic.code,
            diagnostic.summary,
        ): diagnostic
        for diagnostic in diagnostics
    }
    return tuple(by_key[key] for key in sorted(by_key))


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
