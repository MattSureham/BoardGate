"""Deterministic PCB coordinate and manufacturing geometry rules."""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from boardgate.config.models import RuleId
from boardgate.domain.drill import DrillHit, DrillSlot
from boardgate.domain.enums import ApertureShape, LayerRole, Polarity, RiskMode
from boardgate.domain.finding import FindingEvidence, Measurement
from boardgate.domain.geometry import BoundingBox, Point, Unit
from boardgate.domain.layer import ArcPrimitive, GraphicPrimitive, LinePrimitive
from boardgate.rules.common import make_finding
from boardgate.rules.derived_geometry import (
    DerivedGeometry,
    IntersectionCandidateScope,
    shapely_bounds,
)
from boardgate.rules.engine import RuleContext
from boardgate.rules.models import (
    RuleCoverage,
    RuleCoverageGap,
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

    def evaluate(  # noqa: PLR0911, PLR0912, PLR0915
        self,
        context: RuleContext,
    ) -> RuleEvaluation:
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
        coverage_gaps: list[RuleCoverageGap] = []
        unsafe_layer_count = 0
        unsupported_layer_count = 0
        for layer in trusted_layers:
            composite = context.derived_geometry.composite_layer(
                layer,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
            )
            coverage_gaps.extend(composite.coverage_gaps)
            coverage_partial = coverage_partial or not composite.coverage_complete
            if not composite.polarity_complete:
                unsafe_layer_count += 1
                continue
            if not composite.geometry_supported:
                unsupported_layer_count += 1
                continue
            evaluated_ids = frozenset(composite.evaluated_primitive_ids)
            if not evaluated_ids:
                continue
            dark_items = tuple(
                (primitive, derived)
                for primitive, derived in composite.primitive_geometries
                if primitive.polarity is Polarity.DARK
                and primitive.primitive_id in evaluated_ids
            )
            coverage_partial = coverage_partial or any(
                isinstance(primitive, LinePrimitive | ArcPrimitive)
                and primitive.aperture.shape is not ApertureShape.CIRCLE
                for primitive, _ in dark_items
            )
            trace_items = tuple(
                (primitive, derived)
                for primitive, derived in dark_items
                if isinstance(primitive, LinePrimitive | ArcPrimitive)
                and primitive.aperture.shape is ApertureShape.CIRCLE
            )
            neighbor_query = context.derived_geometry.query_primitives(
                layer,
                tuple(derived.geometry for _, derived in trace_items),
                scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
                witness_buffer_mm=0.0,
            )
            if neighbor_query.coverage_gaps:
                coverage_gaps.extend(neighbor_query.coverage_gaps)
                coverage_partial = True
                continue
            for (primitive, derived), indexed_items in zip(
                trace_items,
                neighbor_query.matches,
                strict=True,
            ):
                clear_geometries = tuple(
                    item.geometry
                    for candidate, item in indexed_items
                    if candidate.polarity is Polarity.CLEAR
                    and candidate.primitive_id in evaluated_ids
                )
                if clear_geometries:
                    coverage_partial = True
                    excluded_supported += 1
                    continue
                local_dark = tuple(
                    item.geometry
                    for candidate, item in indexed_items
                    if candidate.polarity is Polarity.DARK
                    and candidate.primitive_id in evaluated_ids
                    and candidate.primitive_id != primitive.primitive_id
                )
                other_dark = context.derived_geometry.bounded_union(local_dark)
                exposed = (
                    derived.geometry
                    if other_dark.is_empty
                    else derived.geometry.difference(other_dark)
                )
                if exposed.is_empty or exposed.area == 0.0:
                    excluded_supported += 1
                    continue
                if exposed.area <= context.profile.tolerances.geometry_epsilon**2:
                    coverage_partial = True
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
            if coverage_gaps:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.COMPUTATION_LIMIT,
                    coverage_gaps=tuple(coverage_gaps),
                    summary=(
                        "All trusted copper layers exceeded deterministic geometry "
                        "resource limits."
                    ),
                    applicable_object_count=sum(
                        len(layer.primitives) for layer in trusted_layers
                    ),
                )
            if unsafe_layer_count:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.INPUT_UNCERTAIN,
                    summary=(
                        "Copper polarity is unknown for every remaining trace-width "
                        "scope."
                    ),
                )
            if unsupported_layer_count:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.UNSUPPORTED_GEOMETRY,
                    summary=(
                        "Copper geometry is outside the exact trace-width "
                        "composition scope."
                    ),
                )
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=(
                    RuleReason.UNSUPPORTED_GEOMETRY
                    if coverage_partial or excluded_supported
                    else RuleReason.NOT_APPLICABLE
                ),
                coverage_gaps=tuple(coverage_gaps),
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
                coverage_gaps=tuple(coverage_gaps),
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
            coverage_gaps=tuple(coverage_gaps),
        )


def _component_evidence(
    contributors: tuple[tuple[GraphicPrimitive, DerivedGeometry], ...],
    layer_id: str,
    component: BaseGeometry,
) -> tuple[FindingEvidence, ...]:
    bounds = shapely_bounds(component)
    return tuple(
        FindingEvidence(
            provenance=primitive.provenance,
            layer_id=layer_id,
            witness_bounds=bounds,
            note="Primitive contributes to this final connected copper component.",
        )
        for primitive, derived in contributors
        if primitive.polarity is Polarity.DARK
    )


@dataclass(frozen=True, slots=True)
class MinimumCopperSpacingRule:
    """Compare distinct connected components of final composite copper."""

    rule_id: RuleId = RuleId.MINIMUM_COPPER_SPACING
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (RuleId.REQUIRED_LAYERS_PRESENT,)

    def evaluate(  # noqa: PLR0911, PLR0912, PLR0915
        self,
        context: RuleContext,
    ) -> RuleEvaluation:
        """Use per-layer STRtrees without inferring electrical nets."""
        trusted_layers = tuple(
            layer
            for layer in context.project.layers
            if layer.role in _COPPER_ROLES and not layer.uncertainties
        )
        if not trusted_layers:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary="No trusted copper layer is available for spacing checks.",
            )
        required = context.profile.fabrication.min_copper_spacing
        epsilon = context.profile.tolerances.geometry_epsilon
        findings = []
        applicable_pairs = 0
        evaluated_pairs = 0
        coverage_partial = False
        coverage_gaps: list[RuleCoverageGap] = []
        unsafe_layer_count = 0
        unsupported_layer_count = 0
        for layer in trusted_layers:
            composite = context.derived_geometry.composite_layer(
                layer,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=epsilon,
            )
            coverage_gaps.extend(composite.coverage_gaps)
            coverage_partial = coverage_partial or not composite.coverage_complete
            if not composite.polarity_complete:
                unsafe_layer_count += 1
                continue
            if not composite.geometry_supported:
                unsupported_layer_count += 1
                continue
            components = context.derived_geometry.geometry_components(
                composite.geometry
            )
            applicable_pairs += len(components) * (len(components) - 1) // 2
            contributor_query = context.derived_geometry.query_primitives(
                layer,
                components,
                scope=IntersectionCandidateScope.COPPER_SPACING_CONTRIBUTORS,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=epsilon,
                witness_buffer_mm=epsilon,
            )
            if contributor_query.coverage_gaps:
                coverage_gaps.extend(contributor_query.coverage_gaps)
                coverage_partial = True
                continue
            error = 2.0 * composite.error_bound_mm + epsilon
            pair_query = context.derived_geometry.component_pairs_within(
                components,
                maximum_distance=required + error,
                layer=layer,
            )
            coverage_gaps.extend(pair_query.coverage_gaps)
            coverage_partial = coverage_partial or bool(pair_query.coverage_gaps)
            evaluated_pairs += pair_query.evaluated_pair_count
            for first_index, second_index, distance in pair_query.pairs:
                disposition = evaluate_minimum_threshold(
                    actual=distance,
                    required=required,
                    error_bound=error,
                )
                if disposition is ThresholdDisposition.SATISFIED:
                    continue
                confirmation = disposition is ThresholdDisposition.REQUIRES_CONFIRMATION
                coverage_partial = coverage_partial or confirmation
                first = components[first_index]
                second = components[second_index]
                nearest_first, nearest_second = nearest_points(first, second)
                location = Point(
                    x=(nearest_first.x + nearest_second.x) / 2.0,
                    y=(nearest_first.y + nearest_second.y) / 2.0,
                )
                evidence = (
                    *_component_evidence(
                        contributor_query.matches[first_index],
                        layer.layer_id,
                        first,
                    ),
                    *_component_evidence(
                        contributor_query.matches[second_index],
                        layer.layer_id,
                        second,
                    ),
                )
                measurement = Measurement(
                    actual=distance,
                    required=required,
                    operator=">=",
                    unit=Unit.MILLIMETRE,
                    error_bound=error,
                    config_path="fabrication.min_copper_spacing",
                )
                findings.append(
                    make_finding(
                        context,
                        rule_id=self.rule_id,
                        category=RiskMode.GEOMETRY_VIOLATION,
                        config_path="fabrication.min_copper_spacing",
                        title=(
                            "Copper spacing requires confirmation"
                            if confirmation
                            else "Copper components are too close"
                        ),
                        summary=(
                            "The derived component spacing overlaps the "
                            "configured minimum after geometry error."
                            if confirmation
                            else (
                                "Two distinct connected copper components remain "
                                "closer than the configured minimum after error."
                            )
                        ),
                        facts=(
                            f"Component spacing is {distance:.6f} mm.",
                            "Components are geometric; no electrical net was inferred.",
                        ),
                        evidence=tuple(evidence),
                        confidence=(0.5 if confirmation else 1.0),
                        location=location,
                        measurement=measurement,
                        suggested_action=(
                            f"Increase geometric copper spacing to {required:.6f} mm."
                        ),
                        requires_human_confirmation=confirmation,
                    )
                )
        if applicable_pairs == 0:
            if coverage_gaps:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.COMPUTATION_LIMIT,
                    coverage_gaps=tuple(coverage_gaps),
                    summary=(
                        "All applicable copper spacing scope exceeded deterministic "
                        "geometry resource limits."
                    ),
                )
            if unsafe_layer_count:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.INPUT_UNCERTAIN,
                    summary=(
                        "Copper polarity is unknown for the unevaluated spacing scope."
                    ),
                )
            if unsupported_layer_count:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.UNSUPPORTED_GEOMETRY,
                    summary=(
                        "Copper geometry is outside the exact spacing composition "
                        "scope."
                    ),
                )
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary=(
                    "Fewer than two final connected copper components exist on "
                    "each trusted layer."
                ),
            )
        if evaluated_pairs == 0 and coverage_gaps and not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.COMPUTATION_LIMIT,
                coverage_gaps=tuple(coverage_gaps),
                summary=(
                    "All applicable copper spacing pairs exceeded deterministic "
                    "geometry resource limits."
                ),
                applicable_object_count=applicable_pairs,
            )
        if not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=(
                    RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL
                ),
                summary=(
                    "No spacing issue was found in the supported component scope."
                    if coverage_partial
                    else (
                        "All distinct final copper components meet the "
                        "configured spacing."
                    )
                ),
                evaluated_object_count=evaluated_pairs,
                applicable_object_count=applicable_pairs,
                coverage_gaps=tuple(coverage_gaps),
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary=(
                "One or more distinct geometric copper components do not "
                "clearly meet spacing."
            ),
            evaluated_object_count=evaluated_pairs,
            applicable_object_count=applicable_pairs,
            coverage_gaps=tuple(coverage_gaps),
        )


@dataclass(frozen=True, slots=True)
class MinimumCopperToEdgeRule:
    """Measure final copper to outer and cutout board boundaries."""

    rule_id: RuleId = RuleId.MINIMUM_COPPER_TO_EDGE
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (
        RuleId.REQUIRED_LAYERS_PRESENT,
        RuleId.BOARD_OUTLINE_CLOSED,
    )

    def evaluate(  # noqa: PLR0911, PLR0912, PLR0915
        self,
        context: RuleContext,
    ) -> RuleEvaluation:
        """Apply containment, edge-touch policy, and propagated geometry error."""
        outline = context.project.board_outline
        trusted_layers = tuple(
            layer
            for layer in context.project.layers
            if layer.role in _COPPER_ROLES and not layer.uncertainties
        )
        if outline is None or not trusted_layers:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary="A trusted outline and copper layer are required.",
            )
        material = context.derived_geometry.board_material_geometry(outline)
        boundary = material.boundary
        required = context.profile.fabrication.min_copper_to_edge
        epsilon = context.profile.tolerances.geometry_epsilon
        findings = []
        component_count = 0
        coverage_partial = False
        coverage_gaps: list[RuleCoverageGap] = []
        unsafe_layer_count = 0
        unsupported_layer_count = 0
        for layer in trusted_layers:
            composite = context.derived_geometry.composite_layer(
                layer,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=epsilon,
            )
            coverage_gaps.extend(composite.coverage_gaps)
            coverage_partial = coverage_partial or not composite.coverage_complete
            if not composite.polarity_complete:
                unsafe_layer_count += 1
                continue
            if not composite.geometry_supported:
                unsupported_layer_count += 1
                continue
            error = composite.error_bound_mm + outline.measurement_error_mm + epsilon
            components = context.derived_geometry.geometry_components(
                composite.geometry
            )
            contributor_query = context.derived_geometry.query_primitives(
                layer,
                components,
                scope=IntersectionCandidateScope.COPPER_EDGE_CONTRIBUTORS,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=epsilon,
                witness_buffer_mm=epsilon,
            )
            if contributor_query.coverage_gaps:
                coverage_gaps.extend(contributor_query.coverage_gaps)
                coverage_partial = True
                continue
            for component, contributors in zip(
                components,
                contributor_query.matches,
                strict=True,
            ):
                component_count += 1
                contained = material.covers(component)
                contained_with_error = material.buffer(error).covers(component)
                distance = component.distance(boundary)
                clearance = distance if contained else -component.distance(material)
                touching = math.isclose(
                    distance,
                    0.0,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                if contained and not touching:
                    disposition = evaluate_minimum_threshold(
                        actual=distance,
                        required=required,
                        error_bound=error,
                    )
                    if disposition is ThresholdDisposition.SATISFIED:
                        continue
                    confirmation = (
                        disposition is ThresholdDisposition.REQUIRES_CONFIRMATION
                    )
                    title = (
                        "Copper-to-edge clearance requires confirmation"
                        if confirmation
                        else "Copper is too close to a board edge"
                    )
                elif not contained:
                    confirmation = contained_with_error
                    title = (
                        "Copper containment requires confirmation"
                        if confirmation
                        else "Copper extends outside board material"
                    )
                else:
                    confirmation = context.profile.policy.copper_edge_touch == "confirm"
                    title = (
                        "Copper touching board edge requires confirmation"
                        if confirmation
                        else "Copper touches a board edge"
                    )
                coverage_partial = coverage_partial or confirmation
                nearest_copper, nearest_edge = nearest_points(component, boundary)
                location = Point(
                    x=(nearest_copper.x + nearest_edge.x) / 2.0,
                    y=(nearest_copper.y + nearest_edge.y) / 2.0,
                )
                evidence = (
                    *_component_evidence(
                        contributors,
                        layer.layer_id,
                        component,
                    ),
                    *(
                        FindingEvidence(
                            provenance=provenance,
                            witness_bounds=outline.bounding_box,
                            note="Outer/cutout board boundary witness.",
                        )
                        for provenance in outline.provenance
                    ),
                )
                measurement = Measurement(
                    actual=clearance,
                    required=required,
                    operator=">=",
                    unit=Unit.MILLIMETRE,
                    error_bound=error,
                    config_path="fabrication.min_copper_to_edge",
                )
                findings.append(
                    make_finding(
                        context,
                        rule_id=self.rule_id,
                        category=RiskMode.GEOMETRY_VIOLATION,
                        config_path="fabrication.min_copper_to_edge",
                        title=title,
                        summary=(
                            "Final copper containment or clearance does not "
                            "clearly satisfy the configured edge policy."
                        ),
                        facts=(
                            f"Signed copper edge clearance is {clearance:.6f} mm.",
                            f"Copper contained by board material: {contained}.",
                            (
                                "Edge-touch policy is "
                                f"{context.profile.policy.copper_edge_touch}."
                            ),
                        ),
                        evidence=tuple(evidence),
                        confidence=(0.5 if confirmation else 1.0),
                        location=location,
                        measurement=measurement,
                        suggested_action=(
                            f"Move copper at least {required:.6f} mm from all "
                            "outer and cutout boundaries."
                        ),
                        requires_human_confirmation=confirmation,
                    )
                )
        if component_count == 0:
            if coverage_gaps:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.COMPUTATION_LIMIT,
                    coverage_gaps=tuple(coverage_gaps),
                    summary=(
                        "All applicable copper-to-edge scope exceeded deterministic "
                        "geometry resource limits."
                    ),
                )
            if unsafe_layer_count:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.INPUT_UNCERTAIN,
                    summary=(
                        "Copper polarity is unknown for the unevaluated edge-clearance "
                        "scope."
                    ),
                )
            if unsupported_layer_count:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.UNSUPPORTED_GEOMETRY,
                    summary=(
                        "Copper geometry is outside the exact edge-clearance "
                        "composition scope."
                    ),
                )
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary="No final copper component exists to measure.",
            )
        if not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=(
                    RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL
                ),
                summary=(
                    "All supported final copper components meet outer and "
                    "cutout edge clearance."
                ),
                evaluated_object_count=component_count,
                applicable_object_count=component_count,
                coverage_gaps=tuple(coverage_gaps),
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary="Copper containment or edge clearance needs attention.",
            evaluated_object_count=component_count,
            applicable_object_count=component_count,
            coverage_gaps=tuple(coverage_gaps),
        )
