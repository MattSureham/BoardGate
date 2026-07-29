"""Strict contracts for deterministic review orchestration and presentation."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from boardgate.config.models import RuleId
from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import ReviewStatus, RiskMode, Severity


class ParserId(StrEnum):
    """Parser adapters that may be selected from a project manifest."""

    GERBER = "gerber"
    EXCELLON = "excellon"
    BOM = "bom"
    PLACEMENT = "placement"


class ParserTask(VersionedModel):
    """One parser invocation over deterministically ordered source files."""

    parser_id: ParserId
    source_file_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_source_ids(self) -> Self:
        """Require stable, unique source identifiers."""
        if self.source_file_ids != tuple(sorted(set(self.source_file_ids))):
            msg = "parser source identifiers must be unique and sorted"
            raise ValueError(msg)
        return self


class RulePlanDisposition(StrEnum):
    """Profile-level decision made before the rule engine evaluates inputs."""

    EXECUTE = "EXECUTE"
    PROFILE_DISABLED = "PROFILE_DISABLED"


class RuleTask(VersionedModel):
    """A rule-engine delegation without duplicating rule applicability logic."""

    rule_id: RuleId
    disposition: RulePlanDisposition


class RiskDirective(VersionedModel):
    """Fixed behavior that the agent applies to one explicit risk mode."""

    risk_mode: RiskMode
    continue_independent_checks: bool
    suppress_unconditional_ready: bool
    require_human_confirmation: bool
    action: str = Field(min_length=1, max_length=500)


class ReviewPlan(VersionedModel):
    """Stable parser/rule execution plan derived before deterministic analysis."""

    project_id: str = Field(pattern=r"^prj-[0-9a-f]{16}$")
    profile_id: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_tasks: tuple[ParserTask, ...] = ()
    rule_tasks: tuple[RuleTask, ...]
    risk_directives: tuple[RiskDirective, ...] = ()

    @model_validator(mode="after")
    def validate_plan_order(self) -> Self:
        """Keep every execution decision unique and canonically ordered."""
        parser_ids = tuple(task.parser_id for task in self.parser_tasks)
        if parser_ids != tuple(sorted(set(parser_ids), key=str)):
            msg = "parser tasks must be unique and sorted"
            raise ValueError(msg)
        rule_ids = tuple(task.rule_id for task in self.rule_tasks)
        if len(rule_ids) != len(set(rule_ids)):
            msg = "rule tasks must be unique"
            raise ValueError(msg)
        risk_modes = tuple(item.risk_mode for item in self.risk_directives)
        if risk_modes != tuple(sorted(set(risk_modes), key=str)):
            msg = "risk directives must be unique and sorted"
            raise ValueError(msg)
        return self


class PresentationGroupKind(StrEnum):
    """Non-overlapping display groups for raw deterministic findings."""

    BLOCKERS = "BLOCKERS"
    HIGH_RISK = "HIGH_RISK"
    REQUIRES_HUMAN_CONFIRMATION = "REQUIRES_HUMAN_CONFIRMATION"
    OPTIMIZATION_SUGGESTIONS = "OPTIMIZATION_SUGGESTIONS"


PRESENTATION_GROUP_ORDER = (
    PresentationGroupKind.BLOCKERS,
    PresentationGroupKind.HIGH_RISK,
    PresentationGroupKind.REQUIRES_HUMAN_CONFIRMATION,
    PresentationGroupKind.OPTIMIZATION_SUGGESTIONS,
)


class PresentationGroup(VersionedModel):
    """A display-only collection of stable finding identifiers."""

    kind: PresentationGroupKind
    finding_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_finding_ids(self) -> Self:
        """Require stable ordering and prevent duplicate display references."""
        if self.finding_ids != tuple(sorted(set(self.finding_ids))):
            msg = "presentation finding identifiers must be unique and sorted"
            raise ValueError(msg)
        return self


class PresentationView(VersionedModel):
    """A deterministic grouping view that never replaces the raw review."""

    project_id: str = Field(pattern=r"^prj-[0-9a-f]{16}$")
    groups: tuple[PresentationGroup, ...]
    risk_directives: tuple[RiskDirective, ...] = ()

    @model_validator(mode="after")
    def validate_view(self) -> Self:
        """Require all four groups in fixed order with no repeated findings."""
        kinds = tuple(group.kind for group in self.groups)
        if kinds != PRESENTATION_GROUP_ORDER:
            msg = "presentation groups must use the complete canonical order"
            raise ValueError(msg)
        finding_ids = tuple(
            finding_id for group in self.groups for finding_id in group.finding_ids
        )
        if len(finding_ids) != len(set(finding_ids)):
            msg = "a finding may appear in only one presentation group"
            raise ValueError(msg)
        risk_modes = tuple(item.risk_mode for item in self.risk_directives)
        if risk_modes != tuple(sorted(set(risk_modes), key=str)):
            msg = "presentation risk directives must be unique and sorted"
            raise ValueError(msg)
        return self


class NarrativeFinding(VersionedModel):
    """Provider-visible finding facts copied from the deterministic result."""

    finding_id: str = Field(pattern=r"^fnd-[0-9a-f]{16}$")
    group: PresentationGroupKind
    severity: Severity
    risk_mode: RiskMode
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    facts: tuple[str, ...] = Field(min_length=1)
    suggested_action: str | None = Field(default=None, min_length=1)
    requires_human_confirmation: bool


class NarrativeRequest(VersionedModel):
    """Typed, evidence-only input passed to a narrative provider."""

    project_id: str = Field(pattern=r"^prj-[0-9a-f]{16}$")
    overall_status: ReviewStatus
    baseline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    findings: tuple[NarrativeFinding, ...]
    groups: tuple[PresentationGroup, ...]

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        """Require the request inventory to match its presentation groups."""
        finding_ids = tuple(finding.finding_id for finding in self.findings)
        if finding_ids != tuple(sorted(set(finding_ids))):
            msg = "narrative findings must be unique and sorted"
            raise ValueError(msg)
        grouped_ids = tuple(
            finding_id for group in self.groups for finding_id in group.finding_ids
        )
        if set(grouped_ids) != set(finding_ids):
            msg = "narrative groups must cover exactly the request findings"
            raise ValueError(msg)
        return self


class NarrativeItem(VersionedModel):
    """Provider selection of immutable facts by zero-based index."""

    finding_id: str = Field(pattern=r"^fnd-[0-9a-f]{16}$")
    fact_indices: tuple[int, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_fact_indices(self) -> Self:
        """Reject negative, duplicated, or unstable fact references."""
        if any(index < 0 for index in self.fact_indices) or self.fact_indices != tuple(
            sorted(set(self.fact_indices))
        ):
            msg = "fact indices must be non-negative, unique, and sorted"
            raise ValueError(msg)
        return self


class NarrativeSection(VersionedModel):
    """Provider-selected evidence for one fixed presentation group."""

    kind: PresentationGroupKind
    items: tuple[NarrativeItem, ...] = ()


class NarrativeResponse(VersionedModel):
    """Typed provider output that can only reference deterministic evidence."""

    project_id: str = Field(pattern=r"^prj-[0-9a-f]{16}$")
    baseline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    deterministic: bool
    sections: tuple[NarrativeSection, ...]
