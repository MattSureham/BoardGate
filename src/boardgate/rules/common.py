"""Shared deterministic finding construction for built-in rules."""

from __future__ import annotations

from boardgate.config.models import RuleId, RuleSeverity
from boardgate.domain.enums import RiskMode, Severity
from boardgate.domain.finding import Finding, FindingEvidence, Measurement
from boardgate.domain.geometry import Point
from boardgate.domain.identifiers import finding_id
from boardgate.rules.engine import RuleContext

_SEVERITY = {
    RuleSeverity.BLOCKER: Severity.BLOCKER,
    RuleSeverity.HIGH: Severity.HIGH,
    RuleSeverity.WARNING: Severity.WARNING,
    RuleSeverity.INFO: Severity.INFO,
}


def configured_severity(context: RuleContext, rule_id: RuleId) -> Severity:
    """Map a validated profile severity onto the public Finding enum."""
    return _SEVERITY[context.profile.rules.by_id(rule_id).severity]


def evidence_identifier(evidence: FindingEvidence) -> str:
    """Return a stable evidence address even when a parser span is unavailable."""
    provenance = evidence.provenance
    if provenance.object_id is not None:
        return provenance.object_id
    span = provenance.source_span
    span_label = (
        "none"
        if span is None
        else (f"{span.start_line}:{span.end_line}:{span.start_byte}:{span.end_byte}")
    )
    return f"{provenance.source_file_id}:{span_label}"


def make_finding(  # noqa: PLR0913
    context: RuleContext,
    *,
    rule_id: RuleId,
    category: RiskMode,
    config_path: str,
    title: str,
    summary: str,
    facts: tuple[str, ...],
    evidence: tuple[FindingEvidence, ...],
    confidence: float,
    location: Point | None = None,
    measurement: Measurement | None = None,
    inference: str | None = None,
    suggested_action: str | None = None,
    requires_human_confirmation: bool = False,
) -> Finding:
    """Build one profile-bound Finding with a canonical identifier."""
    rule_version = "1.0"
    return Finding(
        finding_id=finding_id(
            rule_id=rule_id.value,
            rule_version=rule_version,
            profile_sha256=context.profile_sha256,
            evidence_ids=(
                f"profile-config:{config_path}",
                *(evidence_identifier(item) for item in evidence),
            ),
            location=location,
            measurement=measurement,
        ),
        rule_id=rule_id.value,
        rule_version=rule_version,
        category=category,
        severity=configured_severity(context, rule_id),
        confidence=confidence,
        config_path=config_path,
        title=title,
        summary=summary,
        facts=facts,
        inference=inference,
        location=location,
        measurement=measurement,
        evidence=evidence,
        suggested_action=suggested_action,
        requires_human_confirmation=requires_human_confirmation,
    )
