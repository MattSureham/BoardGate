"""Deterministic PCB review rule contracts and engine."""

from boardgate.rules.engine import RuleContext, RuleEngine, determine_review_status
from boardgate.rules.models import (
    ReviewResult,
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    RuleResult,
    ThresholdDisposition,
    evaluate_maximum_threshold,
    evaluate_minimum_threshold,
)
from boardgate.rules.registry import Rule, RuleRegistry, RuleRegistryError

__all__ = [
    "ReviewResult",
    "Rule",
    "RuleContext",
    "RuleCoverage",
    "RuleEngine",
    "RuleEvaluation",
    "RuleOutcome",
    "RuleReason",
    "RuleRegistry",
    "RuleRegistryError",
    "RuleResult",
    "ThresholdDisposition",
    "determine_review_status",
    "evaluate_maximum_threshold",
    "evaluate_minimum_threshold",
]
