"""Deterministic PCB coordinate and manufacturing geometry rules."""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.ops import unary_union

from boardgate.config.models import RuleId
from boardgate.domain.drill import DrillHit, DrillSlot
from boardgate.domain.enums import ApertureShape, LayerRole, Polarity, RiskMode
from boardgate.domain.finding import FindingEvidence, Measurement
from boardgate.domain.geometry import BoundingBox, Point, Unit
from boardgate.domain.layer import ArcPrimitive, LinePrimitive
from boardgate.rules.common import make_finding
from boardgate.rules.derived_geometry import (
    DerivedGeometry,
    composite_layer,
    shapely_bounds,
)
from boardgate.rules.engine import RuleContext
from boardgate.rules.models import (
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    ThresholdDisposition,
    evaluate_maximum_threshold,
    evaluate_minimum_threshold,
)


def _drill_feature_bounds(
    feature: DrillHit | DrillSlot,
) -> tuple[float, float, float, float]:
    if isinstance(feature, DrillHit):
        radius = feature.diameter_mm / 2.0
        return (
            feature.position.x - radius,
            feature.position.y - radius,
            feature.position.x + radius,
            feature.position.y + radius,
        )
    radius = feature.width_mm / 2.0
    points = [feature.start, feature.end]
    if feature.center is not None:
        arc_radius = math.dist(
            (feature.start.x, feature.start.y),
            (feature.center.x, feature.center.y),
        )
        return (
            feature.center.x - arc_radius - radius,
            feature.center.y - arc_radius - radius,
            feature.center.x + arc_radius + radius,
            feature.center.y + arc_radius + radius,
        )
    return (
        min(point.x for point in points) - radius,
        min(point.y for point in points) - radius,
        max(point.x for point in points) + radius,
        max(point.y for point in points) + radius,
    )


def _drill_bounds(context: RuleContext) -> BoundingBox | None:
    features: tuple[DrillHit | DrillSlot, ...] = (
        *context.project.drills,
        *context.project.drill_slots,
    )
    if not features:
        return None
    bounds = tuple(_drill_feature_bounds(feature) for feature in features)
    return BoundingBox(
        minimum=Point(
            x=min(bound[0] for bound in bounds),
            y=min(bound[1] for bound in bounds),
        ),
        maximum=Point(
            x=max(bound[2] for bound in bounds),
            y=max(bound[3] for bound in bounds),
        ),
    )


def _bbox_distance(first: BoundingBox, second: BoundingBox) -> float:
    x_gap = max(
        first.minimum.x - second.maximum.x,
        second.minimum.x - first.maximum.x,
        0.0,
    )
    y_gap = max(
        first.minimum.y - second.maximum.y,
        second.minimum.y - first.maximum.y,
        0.0,
    )
    return math.hypot(x_gap, y_gap)


@dataclass(frozen=True, slots=True)
class GerberDrillCoordinateAlignmentRule:
    """Detect only gross aggregate drill/board coordinate disjointness."""

    rule_id: RuleId = RuleId.GERBER_DRILL_COORDINATE_ALIGNMENT
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (
        RuleId.DRILL_FILE_PRESENT,
        RuleId.BOARD_OUTLINE_CLOSED,
    )

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Compare board and aggregate drill bounds conservatively."""
        outline = context.project.board_outline
        drill_bounds = _drill_bounds(context)
        if outline is None or drill_bounds is None:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary=(
                    "A trusted outline and at least one drill/slot are required "
                    "for gross coordinate comparison."
                ),
            )
        distance = _bbox_distance(outline.bounding_box, drill_bounds)
        tolerance = context.profile.tolerances.gross_alignment
        disposition = evaluate_maximum_threshold(
            actual=distance,
            required=tolerance,
            error_bound=outline.measurement_error_mm,
        )
        feature_count = len(context.project.drills) + len(context.project.drill_slots)
        if disposition is ThresholdDisposition.SATISFIED:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=RuleCoverage.FULL,
                summary=(
                    "Aggregate drill bounds are not grossly disjoint from the "
                    "board bounds; exact pad registration was not evaluated."
                ),
                evaluated_object_count=feature_count,
                applicable_object_count=feature_count,
            )
        confirmation = disposition is ThresholdDisposition.REQUIRES_CONFIRMATION
        features: tuple[DrillHit | DrillSlot, ...] = (
            *context.project.drills,
            *context.project.drill_slots,
        )
        drill_evidence = tuple(
            FindingEvidence(
                provenance=feature.provenance,
                witness_bounds=drill_bounds,
                note="Drill/slot included in the aggregate drill bounds.",
            )
            for feature in features
        )
        outline_evidence = tuple(
            FindingEvidence(
                provenance=provenance,
                witness_bounds=outline.bounding_box,
                note="Board material bounds used for gross comparison.",
            )
            for provenance in outline.provenance
        )
        measurement = Measurement(
            actual=distance,
            required=tolerance,
            operator="<=",
            unit=Unit.MILLIMETRE,
            error_bound=outline.measurement_error_mm,
            config_path="tolerances.gross_alignment",
        )
        location = Point(
            x=(drill_bounds.minimum.x + drill_bounds.maximum.x) / 2.0,
            y=(drill_bounds.minimum.y + drill_bounds.maximum.y) / 2.0,
        )
        finding = make_finding(
            context,
            rule_id=self.rule_id,
            category=RiskMode.COORDINATE_MISMATCH,
            config_path="tolerances.gross_alignment",
            title=(
                "Gross drill/board alignment requires confirmation"
                if confirmation
                else "Gross drill/board coordinate mismatch"
            ),
            summary=(
                "The aggregate bounding-box separation overlaps the gross "
                "alignment tolerance after propagated outline error."
                if confirmation
                else (
                    "The aggregate drill and board bounding boxes are completely "
                    "disjoint beyond the configured gross tolerance."
                )
            ),
            facts=(
                f"Aggregate bbox separation is {distance:.6f} mm.",
                "This rule does not evaluate individual pad-to-drill registration.",
            ),
            evidence=(*drill_evidence, *outline_evidence),
            confidence=(0.5 if confirmation else 1.0),
            location=location,
            measurement=measurement,
            suggested_action=(
                "Verify the Excellon/Gerber origin and coordinate export settings."
            ),
            requires_human_confirmation=confirmation,
        )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if confirmation else RuleCoverage.FULL),
            findings=(finding,),
            summary="Gross drill/board coordinate alignment is not confirmed.",
            evaluated_object_count=(0 if confirmation else feature_count),
            applicable_object_count=feature_count,
        )


_COPPER_ROLES = frozenset(
    {
        LayerRole.TOP_COPPER,
        LayerRole.BOTTOM_COPPER,
        LayerRole.INNER_COPPER,
    }
)


@dataclass(frozen=True, slots=True)
class MinimumTraceWidthRule:
    """Measure only exposed standard round-aperture copper draws."""

    rule_id: RuleId = RuleId.MINIMUM_TRACE_WIDTH
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (RuleId.REQUIRED_LAYERS_PRESENT,)

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Exclude widened, clear-cut, non-circular, and untrusted traces."""
        trusted_layers = tuple(
            layer
            for layer in context.project.layers
            if layer.role in _COPPER_ROLES and not layer.uncertainties
        )
        uncertain_copper = any(
            layer.role is LayerRole.UNKNOWN
            and any(
                candidate.role in _COPPER_ROLES
                for candidate in layer.mapping_candidates
            )
            for layer in context.project.layers
        )
        if not trusted_layers:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=(
                    RuleReason.INPUT_UNCERTAIN
                    if uncertain_copper
                    else RuleReason.NOT_APPLICABLE
                ),
                summary="No trusted copper layer is available for trace-width checks.",
            )

        eligible: list[tuple[str, LinePrimitive | ArcPrimitive, DerivedGeometry]] = []
        coverage_partial = uncertain_copper
        excluded_supported = 0
        for layer in trusted_layers:
            composite = composite_layer(
                layer,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
            )
            coverage_partial = coverage_partial or not composite.coverage_complete
            dark_items = tuple(
                (primitive, derived)
                for primitive, derived in composite.primitive_geometries
                if primitive.polarity is Polarity.DARK
            )
            clear_geometries = tuple(
                derived.geometry
                for primitive, derived in composite.primitive_geometries
                if primitive.polarity is Polarity.CLEAR
            )
            for primitive, derived in dark_items:
                if not isinstance(primitive, LinePrimitive | ArcPrimitive):
                    continue
                if primitive.aperture.shape is not ApertureShape.CIRCLE:
                    coverage_partial = True
                    continue
                if any(
                    clear_geometry.intersects(derived.geometry)
                    for clear_geometry in clear_geometries
                ):
                    coverage_partial = True
                    excluded_supported += 1
                    continue
                other_dark = unary_union(
                    [
                        other.geometry
                        for other_primitive, other in dark_items
                        if other_primitive.primitive_id != primitive.primitive_id
                    ]
                )
                exposed = (
                    derived.geometry
                    if other_dark.is_empty
                    else derived.geometry.difference(other_dark)
                )
                if exposed.area <= context.profile.tolerances.geometry_epsilon**2:
                    excluded_supported += 1
                    continue
                eligible.append(
                    (
                        layer.layer_id,
                        primitive,
                        derived,
                    )
                )

        if not eligible:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=(
                    RuleReason.UNSUPPORTED_GEOMETRY
                    if coverage_partial or excluded_supported
                    else RuleReason.NOT_APPLICABLE
                ),
                summary=(
                    "No unwidened standard circular-aperture copper draw is "
                    "eligible for width measurement."
                ),
            )

        findings = []
        for layer_id, primitive, derived in eligible:
            actual = primitive.aperture.width_mm
            error = context.profile.tolerances.geometry_epsilon
            required = context.profile.fabrication.min_trace_width
            disposition = evaluate_minimum_threshold(
                actual=actual,
                required=required,
                error_bound=error,
            )
            if disposition is ThresholdDisposition.SATISFIED:
                continue
            confirmation = disposition is ThresholdDisposition.REQUIRES_CONFIRMATION
            bounds = shapely_bounds(derived.geometry)
            measurement = Measurement(
                actual=actual,
                required=required,
                operator=">=",
                unit=Unit.MILLIMETRE,
                error_bound=error,
                config_path="fabrication.min_trace_width",
            )
            location = Point(
                x=(primitive.start.x + primitive.end.x) / 2.0,
                y=(primitive.start.y + primitive.end.y) / 2.0,
            )
            findings.append(
                make_finding(
                    context,
                    rule_id=self.rule_id,
                    category=RiskMode.GEOMETRY_VIOLATION,
                    config_path="fabrication.min_trace_width",
                    title=(
                        "Trace width requires confirmation"
                        if confirmation
                        else "Trace is narrower than the configured minimum"
                    ),
                    summary=(
                        "The exact aperture width overlaps the configured "
                        "minimum after computational tolerance."
                        if confirmation
                        else (
                            "The standard circular aperture remains narrower "
                            "than the configured minimum after tolerance."
                        )
                    ),
                    facts=(
                        f"Round aperture width is {actual:.6f} mm.",
                        "The measured draw has final copper exposed outside all "
                        "other dark copper geometry.",
                    ),
                    evidence=(
                        FindingEvidence(
                            provenance=primitive.provenance,
                            layer_id=layer_id,
                            witness_bounds=bounds,
                        ),
                    ),
                    confidence=(0.5 if confirmation else 1.0),
                    location=location,
                    measurement=measurement,
                    suggested_action=(
                        f"Increase the trace to at least {required:.6f} mm."
                    ),
                    requires_human_confirmation=confirmation,
                )
            )
            coverage_partial = coverage_partial or confirmation
        if not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=(
                    RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL
                ),
                summary=(
                    "No narrow trace was found in the eligible scope."
                    if coverage_partial
                    else (
                        "All eligible unwidened round-aperture traces meet the minimum."
                    )
                ),
                evaluated_object_count=len(eligible),
                applicable_object_count=len(eligible) + excluded_supported,
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary=(
                "One or more eligible trace widths do not clearly meet the minimum."
            ),
            evaluated_object_count=len(eligible),
            applicable_object_count=len(eligible) + excluded_supported,
        )
