"""Public deterministic rule-result and review contracts."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from boardgate.config.models import RuleId
from boardgate.domain.base import StrictModel, VersionedModel
from boardgate.domain.enums import ReviewStatus, RiskMode
from boardgate.domain.finding import Finding


class RuleOutcome(StrEnum):
    """What a rule concluded independently of how much it covered."""

    PASS = "PASS"  # noqa: S105
    FINDINGS = "FINDINGS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class RuleCoverage(StrEnum):
    """How much of the intended rule scope was evaluated."""

    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


class RuleReason(StrEnum):
    """Typed reason for a non-evaluated or failed rule."""

    DISABLED = "DISABLED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    INPUT_UNCERTAIN = "INPUT_UNCERTAIN"
    UNSUPPORTED_GEOMETRY = "UNSUPPORTED_GEOMETRY"
    RULE_EXCEPTION = "RULE_EXCEPTION"


class ThresholdDisposition(StrEnum):
    """Conservative result of comparing a minimum against an error band."""

    SATISFIED = "SATISFIED"
    CONFIRMED_VIOLATION = "CONFIRMED_VIOLATION"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"


class RuleEvaluation(StrictModel):
    """Atomic evaluator return value before profile behavior is attached."""

    outcome: RuleOutcome
    coverage: RuleCoverage
    findings: tuple[Finding, ...] = ()
    reason: RuleReason | None = None
    summary: str = Field(min_length=1, max_length=500)
    evaluated_object_count: int = Field(default=0, ge=0)
    applicable_object_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_result_shape(self) -> Self:
        """Keep outcome, findings, and reason semantically orthogonal."""
        has_findings = bool(self.findings)
        if (self.outcome is RuleOutcome.FINDINGS) != has_findings:
            msg = "FINDINGS outcome must contain findings and no other outcome may"
            raise ValueError(msg)
        needs_reason = self.outcome in {RuleOutcome.SKIPPED, RuleOutcome.FAILED}
        if needs_reason != (self.reason is not None):
            msg = "SKIPPED/FAILED require a reason; PASS/FINDINGS forbid one"
            raise ValueError(msg)
        if (
            self.outcome is RuleOutcome.SKIPPED
            and self.coverage is not RuleCoverage.NONE
        ):
            msg = "SKIPPED rules must have NONE coverage"
            raise ValueError(msg)
        if (
            self.applicable_object_count is not None
            and self.evaluated_object_count > self.applicable_object_count
        ):
            msg = "evaluated object count cannot exceed applicable object count"
            raise ValueError(msg)
        return self


class RuleResult(VersionedModel):
    """Persisted result for one configured deterministic rule."""

    rule_id: RuleId
    rule_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    outcome: RuleOutcome
    coverage: RuleCoverage
    required: bool
    affects_readiness: bool
    findings: tuple[Finding, ...] = ()
    reason: RuleReason | None = None
    summary: str = Field(min_length=1, max_length=500)
    evaluated_object_count: int = Field(default=0, ge=0)
    applicable_object_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_result_shape(self) -> Self:
        """Reuse atomic semantics and bind every finding to this rule."""
        RuleEvaluation(
            outcome=self.outcome,
            coverage=self.coverage,
            findings=self.findings,
            reason=self.reason,
            summary=self.summary,
            evaluated_object_count=self.evaluated_object_count,
            applicable_object_count=self.applicable_object_count,
        )
        if any(
            finding.rule_id != self.rule_id.value
            or finding.rule_version != self.rule_version
            for finding in self.findings
        ):
            msg = "all findings must match the enclosing rule id and version"
            raise ValueError(msg)
        return self


class ReviewResult(VersionedModel):
    """Complete findings.json root contract."""

    project_id: str = Field(pattern=r"^prj-[0-9a-f]{16}$")
    profile_id: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    overall_status: ReviewStatus
    rule_results: tuple[RuleResult, ...]
    findings: tuple[Finding, ...] = ()
    risk_modes: tuple[RiskMode, ...] = ()
    disclaimer: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_aggregate(self) -> Self:
        """Require unique rules/findings and exact flattened aggregate order."""
        rule_ids = [result.rule_id for result in self.rule_results]
        if len(rule_ids) != len(set(rule_ids)):
            msg = "review result contains duplicate rule results"
            raise ValueError(msg)
        flattened = tuple(
            finding for result in self.rule_results for finding in result.findings
        )
        if self.findings != flattened:
            msg = "review findings must exactly flatten rule-result findings"
            raise ValueError(msg)
        finding_ids = [finding.finding_id for finding in self.findings]
        if len(finding_ids) != len(set(finding_ids)):
            msg = "review result contains duplicate finding identifiers"
            raise ValueError(msg)
        if self.risk_modes != tuple(sorted(set(self.risk_modes), key=str)):
            msg = "risk modes must be unique and sorted"
            raise ValueError(msg)
        return self


def evaluate_minimum_threshold(
    *,
    actual: float,
    required: float,
    error_bound: float,
) -> ThresholdDisposition:
    """Apply the v1 conservative minimum/error-band boundary semantics."""
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (actual, required, error_bound)
    ):
        raise ValueError("threshold inputs must be finite and non-negative")
    if math.isclose(actual, required, rel_tol=1e-12, abs_tol=1e-12):
        return ThresholdDisposition.SATISFIED
    upper_bound = actual + error_bound
    lower_bound = actual - error_bound
    upper_is_less = upper_bound < required and not math.isclose(
        upper_bound,
        required,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    lower_is_less = lower_bound < required and not math.isclose(
        lower_bound,
        required,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    if upper_is_less:
        return ThresholdDisposition.CONFIRMED_VIOLATION
    if lower_is_less:
        return ThresholdDisposition.REQUIRES_CONFIRMATION
    return ThresholdDisposition.SATISFIED


def evaluate_maximum_threshold(
    *,
    actual: float,
    required: float,
    error_bound: float,
) -> ThresholdDisposition:
    """Apply the v1 conservative maximum/error-band boundary semantics."""
    if not all(
        math.isfinite(value) and value >= 0.0
        for value in (actual, required, error_bound)
    ):
        raise ValueError("threshold inputs must be finite and non-negative")
    if math.isclose(actual, required, rel_tol=1e-12, abs_tol=1e-12):
        return ThresholdDisposition.SATISFIED
    upper_bound = actual + error_bound
    lower_bound = actual - error_bound
    upper_exceeds = upper_bound > required and not math.isclose(
        upper_bound,
        required,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    lower_exceeds = lower_bound > required and not math.isclose(
        lower_bound,
        required,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
    if lower_exceeds:
        return ThresholdDisposition.CONFIRMED_VIOLATION
    if upper_exceeds:
        return ThresholdDisposition.REQUIRES_CONFIRMATION
    return ThresholdDisposition.SATISFIED
