"""Deterministic manufacturing rules for normalized drill features."""

from __future__ import annotations

import math
from dataclasses import dataclass

from boardgate import __version__
from boardgate.config.models import RuleId
from boardgate.domain.drill import DrillHit
from boardgate.domain.enums import (
    ApertureShape,
    LayerRole,
    Plating,
    Polarity,
    RiskMode,
)
from boardgate.domain.finding import FindingEvidence, Measurement
from boardgate.domain.geometry import BoundingBox, Point, Unit
from boardgate.domain.layer import FlashPrimitive, PCBLayer
from boardgate.domain.provenance import Provenance
from boardgate.rules.common import make_finding
from boardgate.rules.derived_geometry import derive_primitive
from boardgate.rules.engine import RuleContext
from boardgate.rules.models import (
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    ThresholdDisposition,
    evaluate_minimum_threshold,
)

_COPPER_ROLES = {
    LayerRole.TOP_COPPER,
    LayerRole.BOTTOM_COPPER,
    LayerRole.INNER_COPPER,
}


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


def _drill_evidence(drill: DrillHit) -> FindingEvidence:
    radius = drill.diameter_mm / 2.0
    return FindingEvidence(
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
        note="Confirmed plated circular drill hit witness.",
    )


def _layer_evidence(layer: PCBLayer) -> FindingEvidence:
    return FindingEvidence(
        provenance=Provenance(
            source_file_id=layer.source_file_id,
            object_id=layer.layer_id,
            parser="boardgate-annular-match",
            parser_version=__version__,
        ),
        layer_id=layer.layer_id,
        witness_bounds=layer.bounding_box,
        note="Trusted copper layer searched for one matching pad flash.",
    )


def _flash_distance(drill: DrillHit, flash: FlashPrimitive) -> float:
    return math.dist(
        (drill.position.x, drill.position.y),
        (flash.position.x, flash.position.y),
    )


def _standard_round_pad(flash: FlashPrimitive) -> bool:
    aperture = flash.aperture
    return (
        flash.polarity is Polarity.DARK
        and aperture.shape is ApertureShape.CIRCLE
        and aperture.hole_diameter_mm in {None, 0.0}
    )


def _flash_evidence(
    flash: FlashPrimitive,
    *,
    layer: PCBLayer,
    note: str,
) -> FindingEvidence:
    radius = flash.aperture.width_mm / 2.0
    return FindingEvidence(
        provenance=flash.provenance,
        layer_id=layer.layer_id,
        witness_bounds=BoundingBox(
            minimum=Point(
                x=flash.position.x - radius,
                y=flash.position.y - radius,
            ),
            maximum=Point(
                x=flash.position.x + radius,
                y=flash.position.y + radius,
            ),
        ),
        note=note,
    )


def _interfering_clear_primitives(
    context: RuleContext,
    layer: PCBLayer,
    pad: FlashPrimitive,
) -> tuple[FindingEvidence, ...]:
    pad_geometry = derive_primitive(
        pad,
        arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
        geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
    ).geometry
    evidence = []
    for primitive in layer.primitives:
        if primitive.polarity is Polarity.DARK:
            continue
        derived = derive_primitive(
            primitive,
            arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
            geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
        )
        if derived.geometry.intersects(pad_geometry):
            evidence.append(
                FindingEvidence(
                    provenance=primitive.provenance,
                    layer_id=layer.layer_id,
                    witness_bounds=BoundingBox(
                        minimum=Point(
                            x=derived.geometry.bounds[0], y=derived.geometry.bounds[1]
                        ),
                        maximum=Point(
                            x=derived.geometry.bounds[2], y=derived.geometry.bounds[3]
                        ),
                    ),
                    note=(
                        "Clear or unknown-polarity geometry intersects the "
                        "candidate pad."
                    ),
                )
            )
    return tuple(evidence)


@dataclass(frozen=True, slots=True)
class MinimumAnnularRingRule:
    """Measure only unique standard pads around confirmed plated round hits."""

    rule_id: RuleId = RuleId.MINIMUM_ANNULAR_RING
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (
        RuleId.MINIMUM_DRILL_DIAMETER,
        RuleId.REQUIRED_LAYERS_PRESENT,
    )

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Match pad flashes per layer and account for center eccentricity."""
        drills = tuple(
            drill for drill in context.project.drills if drill.plating is Plating.PLATED
        )
        if not drills:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary=(
                    "No confirmed plated round drill hit is available; NPTH, "
                    "unknown-plating hits, and slots are outside v1 scope."
                ),
            )
        layers = tuple(
            layer
            for layer in context.project.layers
            if layer.role in _COPPER_ROLES and not layer.uncertainties
        )
        if not layers:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.INPUT_UNCERTAIN,
                summary="No trusted copper layer is available for pad matching.",
            )

        required = context.profile.fabrication.min_annular_ring
        epsilon = context.profile.tolerances.geometry_epsilon
        source_uncertainties = _uncertainty_evidence(context)
        findings = []
        evaluated_count = 0
        applicable_count = len(drills) * len(layers)
        coverage_partial = False
        for drill in drills:
            for layer in layers:
                nearby = tuple(
                    primitive
                    for primitive in layer.primitives
                    if isinstance(primitive, FlashPrimitive)
                    and _flash_distance(drill, primitive) <= epsilon
                )
                standard = tuple(
                    flash for flash in nearby if _standard_round_pad(flash)
                )
                match = standard[0] if len(nearby) == len(standard) == 1 else None
                interference = (
                    ()
                    if match is None
                    else _interfering_clear_primitives(context, layer, match)
                )
                if match is None or interference:
                    coverage_partial = True
                    candidate_evidence = tuple(
                        _flash_evidence(
                            flash,
                            layer=layer,
                            note=(
                                "Flash lies within pad-matching tolerance but "
                                "does not form one unique supported match."
                            ),
                        )
                        for flash in nearby
                    )
                    findings.append(
                        make_finding(
                            context,
                            rule_id=self.rule_id,
                            category=RiskMode.DESIGN_INTENT_UNKNOWN,
                            config_path="fabrication.min_annular_ring",
                            title="Annular ring cannot be established",
                            summary=(
                                "The confirmed plated hit does not have one "
                                "unambiguous, unaffected standard circular pad "
                                "flash on this trusted copper layer."
                            ),
                            facts=(
                                f"Layer is {layer.layer_id}.",
                                f"Nearby flash count is {len(nearby)}.",
                                f"Supported round-pad count is {len(standard)}.",
                                (
                                    "Intersecting clear/unknown geometry count "
                                    f"is {len(interference)}."
                                ),
                            ),
                            evidence=(
                                _drill_evidence(drill),
                                _layer_evidence(layer),
                                *candidate_evidence,
                                *interference,
                            ),
                            confidence=0.5,
                            location=drill.position,
                            suggested_action=(
                                "Confirm pad/drill pairing and inspect the final "
                                "copper geometry on this layer."
                            ),
                            requires_human_confirmation=True,
                        )
                    )
                    continue

                evaluated_count += 1
                offset = _flash_distance(drill, match)
                actual = (match.aperture.width_mm - drill.diameter_mm) / 2.0 - offset
                disposition = (
                    ThresholdDisposition.CONFIRMED_VIOLATION
                    if actual < 0.0
                    else evaluate_minimum_threshold(
                        actual=actual,
                        required=required,
                        error_bound=epsilon,
                    )
                )
                drill_uncertainty = source_uncertainties.get(
                    drill.provenance.source_file_id,
                    (),
                )
                pad_uncertainty = source_uncertainties.get(
                    match.provenance.source_file_id,
                    (),
                )
                uncertainty = (*drill_uncertainty, *pad_uncertainty)
                coverage_partial = coverage_partial or bool(uncertainty)
                if disposition is ThresholdDisposition.SATISFIED:
                    continue
                confirmation = (
                    bool(uncertainty)
                    or disposition is ThresholdDisposition.REQUIRES_CONFIRMATION
                )
                coverage_partial = coverage_partial or confirmation
                findings.append(
                    make_finding(
                        context,
                        rule_id=self.rule_id,
                        category=RiskMode.GEOMETRY_VIOLATION,
                        config_path="fabrication.min_annular_ring",
                        title=(
                            "Annular ring requires confirmation"
                            if confirmation
                            else "Annular ring is below the minimum"
                        ),
                        summary=(
                            "The minimum radial copper remaining around the "
                            "matched plated drill does not clearly meet the "
                            "configured requirement."
                        ),
                        facts=(
                            f"Pad diameter is {match.aperture.width_mm:.6f} mm.",
                            f"Drill diameter is {drill.diameter_mm:.6f} mm.",
                            f"Pad/drill center offset is {offset:.6f} mm.",
                            f"Minimum radial ring is {actual:.6f} mm.",
                        ),
                        evidence=(
                            _drill_evidence(drill),
                            _flash_evidence(
                                match,
                                layer=layer,
                                note="Unique matched standard circular pad flash.",
                            ),
                            *(
                                FindingEvidence(
                                    provenance=provenance,
                                    note=(
                                        "Project uncertainty witness affecting "
                                        "the matched source."
                                    ),
                                )
                                for provenance in uncertainty
                            ),
                        ),
                        confidence=(0.5 if confirmation else 1.0),
                        location=drill.position,
                        measurement=Measurement(
                            actual=actual,
                            required=required,
                            operator=">=",
                            unit=Unit.MILLIMETRE,
                            error_bound=epsilon,
                            config_path="fabrication.min_annular_ring",
                        ),
                        suggested_action=(
                            f"Increase the minimum radial annular ring to "
                            f"{required:.6f} mm after center offset."
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
                    "No issue was found in uniquely matched supported rings, "
                    "but source uncertainty prevents a complete pass claim."
                    if coverage_partial
                    else (
                        "All uniquely matched supported annular rings meet the "
                        "configured minimum."
                    )
                ),
                evaluated_object_count=evaluated_count,
                applicable_object_count=applicable_count,
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary=(
                "One or more annular rings violate the minimum or cannot be "
                "established from the supported evidence."
            ),
            evaluated_object_count=evaluated_count,
            applicable_object_count=applicable_count,
        )
