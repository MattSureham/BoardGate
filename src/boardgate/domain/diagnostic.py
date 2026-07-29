"""Stable source and pipeline diagnostics exposed at public boundaries."""

import re
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

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
    AGENT_ORCHESTRATION = "AGENT_ORCHESTRATION"
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


class RunLogLevel(StrEnum):
    """Structured run-log severity independent of transport logging."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class RunLogEvent(VersionedModel):
    """One sanitized event in the public ``logs/run.jsonl`` stream."""

    run_id: str = Field(pattern=r"^run-[0-9a-f]{16}$")
    project_id: str = Field(pattern=r"^prj-[0-9a-f]{16}$")
    sequence: int = Field(ge=1)
    occurred_at: datetime
    elapsed_ms: int = Field(ge=0)
    level: RunLogLevel
    category: AnalysisDiagnosticCategory
    stage: AnalysisStage
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    summary: str = Field(min_length=1, max_length=500)
    input_file_count: int | None = Field(default=None, ge=0)
    file_classification_counts: dict[str, int] = Field(default_factory=dict)
    selected_parsers: tuple[str, ...] = ()
    primitive_count: int | None = Field(default=None, ge=0)
    drill_count: int | None = Field(default=None, ge=0)
    executed_rules: tuple[str, ...] = ()
    skipped_rule_reasons: dict[str, str] = Field(default_factory=dict)
    finding_count: int | None = Field(default=None, ge=0)
    error_type: str | None = Field(
        default=None,
        pattern=r"^[A-Z][A-Z0-9_]+$",
    )

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Keep timestamps unambiguous across execution environments."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run-log timestamps must include a UTC offset")
        return value

    @field_validator("summary")
    @classmethod
    def require_sanitized_summary(cls, value: str) -> str:
        """Apply the same safe-text contract as persisted diagnostics."""
        return validate_safe_diagnostic_summary(value)

    @model_validator(mode="after")
    def require_deterministic_collections(self) -> Self:
        """Keep metric maps and identifier sequences canonical and bounded."""
        if any(
            not key or count < 0
            for key, count in self.file_classification_counts.items()
        ):
            raise ValueError("classification counts require non-empty keys and counts")
        if list(self.file_classification_counts) != sorted(
            self.file_classification_counts
        ):
            raise ValueError("classification counts must be key-sorted")
        for label, values in (
            ("selected parsers", self.selected_parsers),
            ("executed rules", self.executed_rules),
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{label} must be unique and sorted")
        if list(self.skipped_rule_reasons) != sorted(self.skipped_rule_reasons):
            raise ValueError("skipped rule reasons must be key-sorted")
        if any(
            not rule_id or not reason
            for rule_id, reason in self.skipped_rule_reasons.items()
        ):
            raise ValueError("skipped rule reasons require non-empty keys and values")
        return self


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
