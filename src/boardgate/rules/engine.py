"""Deterministic, exception-contained rule orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from boardgate.config.models import RuleId, RuleProfile, profile_hash
from boardgate.domain.enums import ReviewStatus, Severity
from boardgate.domain.project import PCBProject
from boardgate.rules.assembly_data import assembly_data_inventory
from boardgate.rules.models import (
    ReviewResult,
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    RuleResult,
)
from boardgate.rules.registry import RuleRegistry

_DISCLAIMER = (
    "BoardGate provides deterministic evidence for engineer review; it does not "
    "guarantee manufacturability or replace fabricator approval."
)


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Immutable inputs visible to one rule evaluator."""

    project: PCBProject
    profile: RuleProfile
    profile_sha256: str
    prior_results: tuple[RuleResult, ...]


def _synthetic_result(
    *,
    rule_id: RuleId,
    version: str,
    profile: RuleProfile,
    evaluation: RuleEvaluation,
) -> RuleResult:
    return _bind_evaluation(
        rule_id=rule_id,
        version=version,
        profile=profile,
        evaluation=evaluation,
    )


def _bind_evaluation(
    *,
    rule_id: RuleId,
    version: str,
    profile: RuleProfile,
    evaluation: RuleEvaluation,
) -> RuleResult:
    setting = profile.rules.by_id(rule_id)
    return RuleResult(
        rule_id=rule_id,
        rule_version=version,
        outcome=evaluation.outcome,
        coverage=evaluation.coverage,
        required=setting.required,
        affects_readiness=setting.affects_readiness,
        findings=evaluation.findings,
        reason=evaluation.reason,
        summary=evaluation.summary,
        evaluated_object_count=evaluation.evaluated_object_count,
        applicable_object_count=evaluation.applicable_object_count,
    )


def determine_review_status(
    *,
    project: PCBProject,
    rule_results: tuple[RuleResult, ...],
    analysis_failed: bool,
) -> ReviewStatus:
    """Apply the normative overall-status precedence exactly once."""
    if analysis_failed:
        return ReviewStatus.ANALYSIS_FAILED
    findings = tuple(finding for result in rule_results for finding in result.findings)
    if any(
        finding.severity is Severity.BLOCKER and not finding.requires_human_confirmation
        for finding in findings
    ):
        return ReviewStatus.NOT_READY_FOR_FABRICATION
    assembly_inventory = assembly_data_inventory(project)
    assembly_input_missing = project.assembly_requirements.review_requested and not (
        assembly_inventory.bom_usable and assembly_inventory.placement_usable
    )
    if (
        any(
            result.required
            and result.outcome in {RuleOutcome.FAILED, RuleOutcome.SKIPPED}
            for result in rule_results
        )
        or assembly_input_missing
    ):
        return ReviewStatus.INSUFFICIENT_INFORMATION
    if (
        any(finding.requires_human_confirmation for finding in findings)
        or any(
            uncertainty.requires_human_confirmation
            for uncertainty in project.uncertainties
        )
        or any(
            result.required and result.coverage is RuleCoverage.PARTIAL
            for result in rule_results
        )
    ):
        return ReviewStatus.READY_WITH_CONFIRMATIONS
    return ReviewStatus.READY_FOR_REVIEW


class RuleEngine:
    """Evaluate a validated registry without allowing one rule to abort others."""

    def __init__(self, registry: RuleRegistry) -> None:
        self._registry = registry

    def evaluate(
        self,
        project: PCBProject,
        profile: RuleProfile,
        *,
        analysis_failed: bool = False,
    ) -> ReviewResult:
        """Evaluate configured rules and aggregate a strict findings root."""
        digest = profile_hash(profile)
        results: list[RuleResult] = []
        by_id: dict[RuleId, RuleResult] = {}
        for rule in self._registry.ordered_rules:
            setting = profile.rules.by_id(rule.rule_id)
            if setting.version != rule.version:
                result = _synthetic_result(
                    rule_id=rule.rule_id,
                    version=rule.version,
                    profile=profile,
                    evaluation=RuleEvaluation(
                        outcome=RuleOutcome.FAILED,
                        coverage=RuleCoverage.NONE,
                        reason=RuleReason.RULE_EXCEPTION,
                        summary=(
                            "Configured rule version does not match the registry."
                        ),
                    ),
                )
            elif not setting.enabled:
                result = _synthetic_result(
                    rule_id=rule.rule_id,
                    version=rule.version,
                    profile=profile,
                    evaluation=RuleEvaluation(
                        outcome=RuleOutcome.SKIPPED,
                        coverage=RuleCoverage.NONE,
                        reason=RuleReason.DISABLED,
                        summary=(
                            "Rule is explicitly disabled by the selected profile."
                        ),
                    ),
                )
            elif any(
                by_id[dependency].outcome in {RuleOutcome.FAILED, RuleOutcome.SKIPPED}
                for dependency in rule.dependencies
            ):
                result = _synthetic_result(
                    rule_id=rule.rule_id,
                    version=rule.version,
                    profile=profile,
                    evaluation=RuleEvaluation(
                        outcome=RuleOutcome.SKIPPED,
                        coverage=RuleCoverage.NONE,
                        reason=RuleReason.DEPENDENCY_UNAVAILABLE,
                        summary=(
                            "A required upstream rule did not produce usable evidence."
                        ),
                    ),
                )
            else:
                context = RuleContext(
                    project=project,
                    profile=profile,
                    profile_sha256=digest,
                    prior_results=tuple(results),
                )
                try:
                    evaluation = rule.evaluate(context)
                    result = _bind_evaluation(
                        rule_id=rule.rule_id,
                        version=rule.version,
                        profile=profile,
                        evaluation=evaluation,
                    )
                except Exception as error:
                    result = _synthetic_result(
                        rule_id=rule.rule_id,
                        version=rule.version,
                        profile=profile,
                        evaluation=RuleEvaluation(
                            outcome=RuleOutcome.FAILED,
                            coverage=RuleCoverage.NONE,
                            reason=RuleReason.RULE_EXCEPTION,
                            summary=(
                                f"Rule execution failed with {type(error).__name__}."
                            ),
                        ),
                    )
            results.append(result)
            by_id[rule.rule_id] = result
        ordered_results = tuple(results)
        findings = tuple(
            finding for result in ordered_results for finding in result.findings
        )
        risk_modes = tuple(
            sorted(
                {
                    *(finding.category for finding in findings),
                    *(uncertainty.risk_mode for uncertainty in project.uncertainties),
                },
                key=str,
            )
        )
        return ReviewResult(
            project_id=project.project_id,
            profile_id=profile.profile.id,
            profile_sha256=digest,
            overall_status=determine_review_status(
                project=project,
                rule_results=ordered_results,
                analysis_failed=analysis_failed,
            ),
            rule_results=ordered_results,
            findings=findings,
            risk_modes=risk_modes,
            disclaimer=_DISCLAIMER,
        )
