"""Deterministic manufacturing rules for normalized drill features."""

from __future__ import annotations

from dataclasses import dataclass

from boardgate.config.models import RuleId
from boardgate.domain.enums import RiskMode
from boardgate.domain.finding import FindingEvidence, Measurement
from boardgate.domain.geometry import BoundingBox, Point, Unit
from boardgate.domain.provenance import Provenance
from boardgate.rules.common import make_finding
from boardgate.rules.engine import RuleContext
from boardgate.rules.models import (
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    ThresholdDisposition,
    evaluate_minimum_threshold,
)


def _uncertainty_evidence(
    context: RuleContext,
) -> dict[str, tuple[Provenance, ...]]:
    """Group explicit project-uncertainty witnesses by source."""
    grouped: dict[str, list[Provenance]] = {}
    for uncertainty in context.project.uncertainties:
        for provenance in uncertainty.evidence:
            grouped.setdefault(provenance.source_file_id, []).append(provenance)
    return {
        source_file_id: tuple(provenance)
        for source_file_id, provenance in grouped.items()
    }


@dataclass(frozen=True, slots=True)
class MinimumDrillDiameterRule:
    """Measure known round drill hits while excluding routed slots."""

    rule_id: RuleId = RuleId.MINIMUM_DRILL_DIAMETER
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (RuleId.DRILL_FILE_PRESENT,)

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Apply the configured minimum and geometry error to round hits."""
        drills = context.project.drills
        if not drills:
            summary = (
                "Only routed slots are present; v1 does not treat them as "
                "circular drill hits."
                if context.project.drill_slots
                else "No circular drill hit is available to measure."
            )
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary=summary,
            )

        required = context.profile.fabrication.min_drill_diameter
        error = context.profile.tolerances.geometry_epsilon
        source_uncertainties = _uncertainty_evidence(context)
        findings = []
        coverage_partial = False
        for drill in drills:
            uncertainty_evidence = source_uncertainties.get(
                drill.provenance.source_file_id,
                (),
            )
            source_uncertain = bool(uncertainty_evidence)
            coverage_partial = coverage_partial or source_uncertain
            disposition = evaluate_minimum_threshold(
                actual=drill.diameter_mm,
                required=required,
                error_bound=error,
            )
            if disposition is ThresholdDisposition.SATISFIED:
                continue
            confirmation = (
                source_uncertain
                or disposition is ThresholdDisposition.REQUIRES_CONFIRMATION
            )
            coverage_partial = coverage_partial or confirmation
            radius = drill.diameter_mm / 2.0
            evidence = (
                FindingEvidence(
                    provenance=drill.provenance,
                    witness_bounds=BoundingBox(
                        minimum=Point(
                            x=drill.position.x - radius,
                            y=drill.position.y - radius,
                        ),
                        maximum=Point(
                            x=drill.position.x + radius,
                            y=drill.position.y + radius,
                        ),
                    ),
                    note="Parsed circular drill hit and tool diameter witness.",
                ),
                *(
                    FindingEvidence(
                        provenance=provenance,
                        note=(
                            "Project uncertainty witness affecting this drill source."
                        ),
                    )
                    for provenance in uncertainty_evidence
                ),
            )
            findings.append(
                make_finding(
                    context,
                    rule_id=self.rule_id,
                    category=RiskMode.GEOMETRY_VIOLATION,
                    config_path="fabrication.min_drill_diameter",
                    title=(
                        "Drill diameter requires confirmation"
                        if confirmation
                        else "Drill diameter is below the minimum"
                    ),
                    summary=(
                        "The parsed circular drill diameter does not clearly "
                        "meet the configured minimum."
                    ),
                    facts=(
                        f"Drill diameter is {drill.diameter_mm:.6f} mm.",
                        (
                            f"Tool code is {drill.tool_code}."
                            if drill.tool_code is not None
                            else "Tool code is unavailable; diameter is parsed."
                        ),
                        "Plating is not used by this diameter rule.",
                        f"Drill source has explicit uncertainty: {source_uncertain}.",
                    ),
                    evidence=evidence,
                    confidence=(0.5 if confirmation else 1.0),
                    location=drill.position,
                    measurement=Measurement(
                        actual=drill.diameter_mm,
                        required=required,
                        operator=">=",
                        unit=Unit.MILLIMETRE,
                        error_bound=error,
                        config_path="fabrication.min_drill_diameter",
                    ),
                    suggested_action=(
                        f"Use a circular drill diameter of at least {required:.6f} mm."
                    ),
                    requires_human_confirmation=confirmation,
                )
            )

        if not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=(
                    RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL
                ),
                summary=(
                    "No issue was found in measured round hits, but a source "
                    "limitation prevents a complete pass claim."
                    if coverage_partial
                    else "All parsed circular drill hits meet the minimum diameter."
                ),
                evaluated_object_count=len(drills),
                applicable_object_count=len(drills),
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary="One or more circular drill diameters need attention.",
            evaluated_object_count=len(drills),
            applicable_object_count=len(drills),
        )
