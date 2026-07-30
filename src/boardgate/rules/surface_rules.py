"""Same-side solder-mask and silkscreen geometry rules."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points

from boardgate.config.models import RuleId
from boardgate.domain.enums import BoardSide, LayerRole, Polarity, RiskMode
from boardgate.domain.finding import FindingEvidence, Measurement
from boardgate.domain.geometry import Point, Unit
from boardgate.domain.layer import GraphicPrimitive, PCBLayer
from boardgate.rules.common import make_finding, project_uncertainty_evidence
from boardgate.rules.derived_geometry import (
    DerivedGeometry,
    IntersectionCandidateScope,
    LayerComposite,
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
    evaluate_minimum_threshold,
)

_SIDE_ROLES = {
    BoardSide.TOP: (
        LayerRole.TOP_COPPER,
        LayerRole.TOP_SOLDER_MASK,
        LayerRole.TOP_SILKSCREEN,
    ),
    BoardSide.BOTTOM: (
        LayerRole.BOTTOM_COPPER,
        LayerRole.BOTTOM_SOLDER_MASK,
        LayerRole.BOTTOM_SILKSCREEN,
    ),
}
_STRONG_MAPPING_CONFIDENCE = 0.75


@dataclass(frozen=True, slots=True)
class _SideGeometry:
    side: BoardSide
    copper_layer: PCBLayer
    mask_layer: PCBLayer
    silk_layer: PCBLayer
    copper: LayerComposite
    mask_openings: LayerComposite
    silkscreen: LayerComposite


def _known_polarity(layer: PCBLayer) -> bool:
    return all(
        primitive.polarity in {Polarity.DARK, Polarity.CLEAR}
        for primitive in layer.primitives
    )


def _derive_side(
    context: RuleContext,
    side: BoardSide,
) -> tuple[_SideGeometry | None, RuleReason | None]:
    roles = _SIDE_ROLES[side]
    matches = tuple(
        tuple(layer for layer in context.project.layers if layer.role is role)
        for role in roles
    )
    if not any(matches[1:]):
        return None, None
    if any(not candidates for candidates in matches):
        return None, None
    if any(len(candidates) > 1 for candidates in matches):
        return None, RuleReason.INPUT_UNCERTAIN
    copper_layer, mask_layer, silk_layer = (candidates[0] for candidates in matches)
    layers = (copper_layer, mask_layer, silk_layer)
    if any(
        layer.side is not side
        or layer.mapping_confidence < _STRONG_MAPPING_CONFIDENCE
        or layer.uncertainties
        or not _known_polarity(layer)
        for layer in layers
    ):
        return None, RuleReason.INPUT_UNCERTAIN
    composites = tuple(
        context.derived_geometry.composite_layer(
            layer,
            arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
            geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
        )
        for layer in layers
    )
    if any(not composite.geometry_supported for composite in composites) or any(
        not composite.coverage_complete and not composite.coverage_gaps
        for composite in composites
    ):
        return None, RuleReason.UNSUPPORTED_GEOMETRY
    return (
        _SideGeometry(
            side=side,
            copper_layer=copper_layer,
            mask_layer=mask_layer,
            silk_layer=silk_layer,
            copper=composites[0],
            mask_openings=composites[1],
            silkscreen=composites[2],
        ),
        None,
    )


def _geometry_evidence(
    contributors: tuple[tuple[GraphicPrimitive, DerivedGeometry], ...],
    layer: PCBLayer,
    witness: BaseGeometry,
    *,
    note: str,
) -> tuple[FindingEvidence, ...]:
    bounds = shapely_bounds(witness)
    return tuple(
        FindingEvidence(
            provenance=primitive.provenance,
            layer_id=layer.layer_id,
            witness_bounds=bounds,
            note=note,
        )
        for primitive, derived in contributors
    )


@dataclass(frozen=True, slots=True)
class SilkscreenOverExposedPadRule:
    """Detect same-side silkscreen over exposed final copper."""

    rule_id: RuleId = RuleId.SILKSCREEN_OVER_EXPOSED_PAD
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (RuleId.REQUIRED_LAYERS_PRESENT,)

    def evaluate(  # noqa: PLR0912, PLR0915
        self,
        context: RuleContext,
    ) -> RuleEvaluation:
        """Intersect final copper, mask openings, and silkscreen per side."""
        derived_sides: list[_SideGeometry] = []
        invalid_reasons: list[RuleReason] = []
        for board_side in (BoardSide.TOP, BoardSide.BOTTOM):
            derived, reason = _derive_side(context, board_side)
            if derived is not None:
                derived_sides.append(derived)
            elif reason is not None:
                invalid_reasons.append(reason)
        if not derived_sides:
            if RuleReason.UNSUPPORTED_GEOMETRY in invalid_reasons:
                reason = RuleReason.UNSUPPORTED_GEOMETRY
                summary = (
                    "Related surface layers use geometry outside the exact v1 "
                    "composition scope."
                )
            elif RuleReason.INPUT_UNCERTAIN in invalid_reasons:
                reason = RuleReason.INPUT_UNCERTAIN
                summary = (
                    "Related surface layers are incomplete, duplicated, "
                    "mis-sided, or have uncertain polarity."
                )
            else:
                reason = RuleReason.NOT_APPLICABLE
                summary = (
                    "No side has the optional copper, solder-mask, and "
                    "silkscreen layer set required by this rule."
                )
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=reason,
                summary=summary,
            )

        epsilon = context.profile.tolerances.geometry_epsilon
        uncertainty_by_source = project_uncertainty_evidence(context)
        findings = []
        coverage_partial = bool(invalid_reasons)
        coverage_gaps: list[RuleCoverageGap] = []
        evaluated_side_count = 0
        exposed_component_count = 0
        for side_geometry in derived_sides:
            side_composites = (
                side_geometry.copper,
                side_geometry.mask_openings,
                side_geometry.silkscreen,
            )
            coverage_gaps.extend(
                gap for composite in side_composites for gap in composite.coverage_gaps
            )
            coverage_partial = coverage_partial or any(
                not composite.coverage_complete for composite in side_composites
            )
            if any(
                composite.coverage_gaps
                and composite.evaluated_dark_primitive_count == 0
                for composite in side_composites
            ):
                continue
            evaluated_side_count += 1
            source_ids = {
                side_geometry.copper_layer.source_file_id,
                side_geometry.mask_layer.source_file_id,
                side_geometry.silk_layer.source_file_id,
            }
            uncertainty = tuple(
                provenance
                for source_id in sorted(source_ids)
                for provenance in uncertainty_by_source.get(source_id, ())
            )
            coverage_partial = coverage_partial or bool(uncertainty)
            exposed = side_geometry.copper.geometry.intersection(
                side_geometry.mask_openings.geometry
            )
            exposed_components = context.derived_geometry.geometry_components(exposed)
            exposed_component_count += len(exposed_components)
            overlap = exposed.intersection(side_geometry.silkscreen.geometry)
            overlap_components = context.derived_geometry.geometry_components(overlap)
            contributor_queries = tuple(
                context.derived_geometry.query_primitives(
                    layer,
                    overlap_components,
                    scope=scope,
                    arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                    geometry_epsilon_mm=epsilon,
                    witness_buffer_mm=epsilon,
                )
                for layer, scope in (
                    (
                        side_geometry.copper_layer,
                        IntersectionCandidateScope.SILK_COPPER_CONTRIBUTORS,
                    ),
                    (
                        side_geometry.mask_layer,
                        IntersectionCandidateScope.SILK_MASK_CONTRIBUTORS,
                    ),
                    (
                        side_geometry.silk_layer,
                        IntersectionCandidateScope.SILKSCREEN_CONTRIBUTORS,
                    ),
                )
            )
            query_gaps = tuple(
                gap for query in contributor_queries for gap in query.coverage_gaps
            )
            if query_gaps:
                coverage_gaps.extend(query_gaps)
                coverage_partial = True
                evaluated_side_count -= 1
                exposed_component_count -= len(exposed_components)
                continue
            error_length = (
                side_geometry.copper.error_bound_mm
                + side_geometry.mask_openings.error_bound_mm
                + side_geometry.silkscreen.error_bound_mm
                + epsilon
            )
            robust_overlap = exposed.buffer(-error_length).intersection(
                side_geometry.silkscreen.geometry.buffer(-error_length)
            )
            for component_index, component in enumerate(overlap_components):
                robust_component = robust_overlap.intersection(component)
                confirmation = robust_component.is_empty or bool(uncertainty)
                coverage_partial = coverage_partial or confirmation
                representative = component.representative_point()
                actual_area = component.area
                robust_area = robust_component.area
                area_error = max(0.0, actual_area - robust_area)
                evidence = (
                    *_geometry_evidence(
                        contributor_queries[0].matches[component_index],
                        side_geometry.copper_layer,
                        component,
                        note="Final copper contributing to the exposed area.",
                    ),
                    *_geometry_evidence(
                        contributor_queries[1].matches[component_index],
                        side_geometry.mask_layer,
                        component,
                        note="Same-side solder-mask opening exposing copper.",
                    ),
                    *_geometry_evidence(
                        contributor_queries[2].matches[component_index],
                        side_geometry.silk_layer,
                        component,
                        note="Same-side silkscreen contributing to overlap.",
                    ),
                    *(
                        FindingEvidence(
                            provenance=provenance,
                            note=(
                                "Project uncertainty witness affecting a "
                                "surface source."
                            ),
                        )
                        for provenance in uncertainty
                    ),
                )
                findings.append(
                    make_finding(
                        context,
                        rule_id=self.rule_id,
                        category=RiskMode.GEOMETRY_VIOLATION,
                        config_path="rules.silkscreen_over_exposed_pad",
                        title=(
                            "Silkscreen overlap requires confirmation"
                            if confirmation
                            else "Silkscreen overlaps exposed copper"
                        ),
                        summary=(
                            "Final same-side silkscreen intersects copper that "
                            "is exposed by the solder-mask opening."
                        ),
                        facts=(
                            f"Board side is {side_geometry.side.value}.",
                            f"Nominal overlap area is {actual_area:.6f} mm2.",
                            (
                                "Propagated boundary uncertainty is "
                                f"{error_length:.6f} mm."
                            ),
                            (
                                "The mask image is interpreted as opening "
                                "geometry after polarity composition."
                            ),
                        ),
                        evidence=tuple(evidence),
                        confidence=(0.5 if confirmation else 1.0),
                        location=Point(
                            x=representative.x,
                            y=representative.y,
                        ),
                        measurement=Measurement(
                            actual=actual_area,
                            required=0.0,
                            operator="<=",
                            unit=Unit.SQUARE_MILLIMETRE,
                            error_bound=area_error,
                            config_path="rules.silkscreen_over_exposed_pad",
                        ),
                        suggested_action=(
                            "Clip or move same-side silkscreen outside the "
                            "exposed copper opening."
                        ),
                        requires_human_confirmation=confirmation,
                    )
                )

        if not findings:
            if coverage_gaps and evaluated_side_count == 0:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.COMPUTATION_LIMIT,
                    coverage_gaps=tuple(coverage_gaps),
                    summary=(
                        "All applicable surface-overlap scope exceeded deterministic "
                        "geometry resource limits."
                    ),
                )
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=(
                    RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL
                ),
                summary=(
                    "No overlap was found in the supported same-side surface "
                    "scope, but coverage is partial."
                    if coverage_partial
                    else (
                        "No final silkscreen overlaps exposed copper in the "
                        "supported same-side surface scope."
                    )
                ),
                evaluated_object_count=exposed_component_count,
                applicable_object_count=exposed_component_count,
                coverage_gaps=tuple(coverage_gaps),
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary="Same-side silkscreen overlap with exposed copper was found.",
            evaluated_object_count=exposed_component_count,
            applicable_object_count=exposed_component_count,
            coverage_gaps=tuple(coverage_gaps),
        )


@dataclass(frozen=True, slots=True)
class _MaskGeometry:
    side: BoardSide
    layer: PCBLayer
    openings: LayerComposite


def _derive_mask(
    context: RuleContext,
    side: BoardSide,
) -> tuple[_MaskGeometry | None, RuleReason | None]:
    role = (
        LayerRole.TOP_SOLDER_MASK
        if side is BoardSide.TOP
        else LayerRole.BOTTOM_SOLDER_MASK
    )
    matches = tuple(layer for layer in context.project.layers if layer.role is role)
    if not matches:
        return None, None
    if len(matches) > 1:
        return None, RuleReason.INPUT_UNCERTAIN
    layer = matches[0]
    if (
        layer.side is not side
        or layer.mapping_confidence < _STRONG_MAPPING_CONFIDENCE
        or layer.uncertainties
        or not _known_polarity(layer)
    ):
        return None, RuleReason.INPUT_UNCERTAIN
    composite = context.derived_geometry.composite_layer(
        layer,
        arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
        geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
    )
    if not composite.geometry_supported or (
        not composite.coverage_complete and not composite.coverage_gaps
    ):
        return None, RuleReason.UNSUPPORTED_GEOMETRY
    return _MaskGeometry(side=side, layer=layer, openings=composite), None


@dataclass(frozen=True, slots=True)
class MinimumSolderMaskDamRule:
    """Measure gaps only between distinct final mask-opening components."""

    rule_id: RuleId = RuleId.MINIMUM_SOLDER_MASK_DAM
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (RuleId.REQUIRED_LAYERS_PRESENT,)

    def evaluate(  # noqa: PLR0911, PLR0912, PLR0915
        self,
        context: RuleContext,
    ) -> RuleEvaluation:
        """Compare mask-opening components per side using an STRtree."""
        masks: list[_MaskGeometry] = []
        invalid_reasons: list[RuleReason] = []
        for side in (BoardSide.TOP, BoardSide.BOTTOM):
            derived, reason = _derive_mask(context, side)
            if derived is not None:
                masks.append(derived)
            elif reason is not None:
                invalid_reasons.append(reason)
        if not masks:
            if RuleReason.UNSUPPORTED_GEOMETRY in invalid_reasons:
                reason = RuleReason.UNSUPPORTED_GEOMETRY
                summary = (
                    "Solder-mask geometry is outside the exact v1 composition scope."
                )
            elif RuleReason.INPUT_UNCERTAIN in invalid_reasons:
                reason = RuleReason.INPUT_UNCERTAIN
                summary = "Solder-mask mapping, side, or polarity is uncertain."
            else:
                reason = RuleReason.NOT_APPLICABLE
                summary = "No optional solder-mask layer is available."
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=reason,
                summary=summary,
            )

        required = context.profile.fabrication.min_solder_mask_dam
        epsilon = context.profile.tolerances.geometry_epsilon
        uncertainty_by_source = project_uncertainty_evidence(context)
        findings = []
        applicable_pairs = 0
        evaluated_pairs = 0
        coverage_partial = bool(invalid_reasons)
        coverage_gaps: list[RuleCoverageGap] = []
        for mask in masks:
            coverage_gaps.extend(mask.openings.coverage_gaps)
            coverage_partial = coverage_partial or not mask.openings.coverage_complete
            if (
                mask.openings.coverage_gaps
                and mask.openings.evaluated_dark_primitive_count == 0
            ):
                continue
            uncertainty = uncertainty_by_source.get(
                mask.layer.source_file_id,
                (),
            )
            coverage_partial = coverage_partial or bool(uncertainty)
            components = context.derived_geometry.geometry_components(
                mask.openings.geometry
            )
            applicable_pairs += len(components) * (len(components) - 1) // 2
            contributor_query = context.derived_geometry.query_primitives(
                mask.layer,
                components,
                scope=IntersectionCandidateScope.SOLDER_MASK_DAM_CONTRIBUTORS,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=epsilon,
                witness_buffer_mm=epsilon,
            )
            if contributor_query.coverage_gaps:
                coverage_gaps.extend(contributor_query.coverage_gaps)
                coverage_partial = True
                continue
            error = 2.0 * mask.openings.error_bound_mm + epsilon
            pair_query = context.derived_geometry.component_pairs_within(
                components,
                maximum_distance=required + error,
                layer=mask.layer,
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
                confirmation = (
                    bool(uncertainty)
                    or disposition is ThresholdDisposition.REQUIRES_CONFIRMATION
                )
                coverage_partial = coverage_partial or confirmation
                first = components[first_index]
                second = components[second_index]
                nearest_first, nearest_second = nearest_points(first, second)
                location = Point(
                    x=(nearest_first.x + nearest_second.x) / 2.0,
                    y=(nearest_first.y + nearest_second.y) / 2.0,
                )
                evidence = (
                    *_geometry_evidence(
                        contributor_query.matches[first_index],
                        mask.layer,
                        first,
                        note="Primitive contributes to the first final opening.",
                    ),
                    *_geometry_evidence(
                        contributor_query.matches[second_index],
                        mask.layer,
                        second,
                        note="Primitive contributes to the second final opening.",
                    ),
                    *(
                        FindingEvidence(
                            provenance=provenance,
                            note=(
                                "Project uncertainty witness affecting the "
                                "solder-mask source."
                            ),
                        )
                        for provenance in uncertainty
                    ),
                )
                findings.append(
                    make_finding(
                        context,
                        rule_id=self.rule_id,
                        category=RiskMode.GEOMETRY_VIOLATION,
                        config_path="fabrication.min_solder_mask_dam",
                        title=(
                            "Solder-mask dam requires confirmation"
                            if confirmation
                            else "Solder-mask dam is below the minimum"
                        ),
                        summary=(
                            "Two distinct final solder-mask opening components "
                            "do not clearly leave the configured mask dam."
                        ),
                        facts=(
                            f"Board side is {mask.side.value}.",
                            f"Opening separation is {distance:.6f} mm.",
                            (
                                "Connected/gang openings are represented as one "
                                "component and are not compared with themselves."
                            ),
                        ),
                        evidence=tuple(evidence),
                        confidence=(0.5 if confirmation else 1.0),
                        location=location,
                        measurement=Measurement(
                            actual=distance,
                            required=required,
                            operator=">=",
                            unit=Unit.MILLIMETRE,
                            error_bound=error,
                            config_path="fabrication.min_solder_mask_dam",
                        ),
                        suggested_action=(
                            f"Leave at least {required:.6f} mm of mask between "
                            "distinct openings, or confirm a deliberate gang "
                            "opening."
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
                        "All applicable solder-mask scope exceeded deterministic "
                        "geometry resource limits."
                    ),
                )
            if invalid_reasons:
                reason = (
                    RuleReason.UNSUPPORTED_GEOMETRY
                    if RuleReason.UNSUPPORTED_GEOMETRY in invalid_reasons
                    else RuleReason.INPUT_UNCERTAIN
                )
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=reason,
                    summary=(
                        "No trusted side has two distinct openings, and another "
                        "solder-mask side could not be evaluated reliably."
                    ),
                )
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary=(
                    "Each trusted solder-mask side has fewer than two distinct "
                    "final openings; connected/gang openings are not dams."
                ),
            )
        if evaluated_pairs == 0 and coverage_gaps and not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.COMPUTATION_LIMIT,
                coverage_gaps=tuple(coverage_gaps),
                summary=(
                    "All applicable solder-mask pairs exceeded deterministic "
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
                    "No undersized dam was found between distinct supported "
                    "openings, but coverage is partial."
                    if coverage_partial
                    else (
                        "All distinct supported mask-opening components meet "
                        "the configured dam."
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
            summary="One or more distinct mask openings leave too little dam.",
            evaluated_object_count=evaluated_pairs,
            applicable_object_count=applicable_pairs,
            coverage_gaps=tuple(coverage_gaps),
        )
