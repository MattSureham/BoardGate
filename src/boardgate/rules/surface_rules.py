"""Same-side solder-mask and silkscreen geometry rules."""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry

from boardgate.config.models import RuleId
from boardgate.domain.enums import BoardSide, LayerRole, Polarity, RiskMode
from boardgate.domain.finding import FindingEvidence, Measurement
from boardgate.domain.geometry import Point, Unit
from boardgate.domain.layer import PCBLayer
from boardgate.rules.common import make_finding, project_uncertainty_evidence
from boardgate.rules.derived_geometry import (
    LayerComposite,
    composite_layer,
    geometry_components,
    shapely_bounds,
)
from boardgate.rules.engine import RuleContext
from boardgate.rules.models import (
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
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
        composite_layer(
            layer,
            arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
            geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
        )
        for layer in layers
    )
    if not all(composite.coverage_complete for composite in composites):
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
    layer: PCBLayer,
    composite: LayerComposite,
    witness: BaseGeometry,
    *,
    epsilon: float,
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
        for primitive, derived in composite.primitive_geometries
        if derived.geometry.intersects(witness.buffer(epsilon))
    )


@dataclass(frozen=True, slots=True)
class SilkscreenOverExposedPadRule:
    """Detect same-side silkscreen over exposed final copper."""

    rule_id: RuleId = RuleId.SILKSCREEN_OVER_EXPOSED_PAD
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (RuleId.REQUIRED_LAYERS_PRESENT,)

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
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
        exposed_component_count = 0
        for side_geometry in derived_sides:
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
            exposed_components = geometry_components(exposed)
            exposed_component_count += len(exposed_components)
            overlap = exposed.intersection(side_geometry.silkscreen.geometry)
            error_length = (
                side_geometry.copper.error_bound_mm
                + side_geometry.mask_openings.error_bound_mm
                + side_geometry.silkscreen.error_bound_mm
                + epsilon
            )
            robust_overlap = exposed.buffer(-error_length).intersection(
                side_geometry.silkscreen.geometry.buffer(-error_length)
            )
            for component in geometry_components(overlap):
                robust_component = robust_overlap.intersection(component)
                confirmation = robust_component.is_empty or bool(uncertainty)
                coverage_partial = coverage_partial or confirmation
                representative = component.representative_point()
                actual_area = component.area
                robust_area = robust_component.area
                area_error = max(0.0, actual_area - robust_area)
                evidence = (
                    *_geometry_evidence(
                        side_geometry.copper_layer,
                        side_geometry.copper,
                        component,
                        epsilon=epsilon,
                        note="Final copper contributing to the exposed area.",
                    ),
                    *_geometry_evidence(
                        side_geometry.mask_layer,
                        side_geometry.mask_openings,
                        component,
                        epsilon=epsilon,
                        note="Same-side solder-mask opening exposing copper.",
                    ),
                    *_geometry_evidence(
                        side_geometry.silk_layer,
                        side_geometry.silkscreen,
                        component,
                        epsilon=epsilon,
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
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary="Same-side silkscreen overlap with exposed copper was found.",
            evaluated_object_count=exposed_component_count,
            applicable_object_count=exposed_component_count,
        )
