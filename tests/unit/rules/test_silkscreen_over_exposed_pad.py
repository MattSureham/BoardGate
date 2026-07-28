"""silkscreen_over_exposed_pad v1 same-side composite semantics."""

from __future__ import annotations

from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    FileType,
    LayerRole,
    Polarity,
    RiskMode,
)
from boardgate.domain.geometry import CoordinateSystem, Point, Unit
from boardgate.domain.layer import Aperture, FlashPrimitive, PCBLayer
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty
from boardgate.rules import (
    ReviewResult,
    RuleContext,
    RuleCoverage,
    RuleEngine,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
)
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.surface_rules import SilkscreenOverExposedPadRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
COPPER_SOURCE = "src-1111111111111111"
MASK_SOURCE = "src-2222222222222222"
SILK_SOURCE = "src-3333333333333333"


def _provenance(identifier: str, source_id: str) -> Provenance:
    return Provenance(
        source_file_id=source_id,
        object_id=identifier,
        parser="test-gerber",
        parser_version="1.0",
    )


def _flash(  # noqa: PLR0913
    identifier: str,
    *,
    source_id: str,
    x: float = 0.0,
    diameter: float = 1.0,
    polarity: Polarity = Polarity.DARK,
    shape: ApertureShape = ApertureShape.CIRCLE,
) -> FlashPrimitive:
    return FlashPrimitive(
        primitive_id=identifier,
        position=Point(x=x, y=0.0),
        aperture=Aperture(
            shape=shape,
            width_mm=diameter,
            height_mm=diameter,
            macro_name=("TEST" if shape is ApertureShape.MACRO else None),
        ),
        polarity=polarity,
        provenance=_provenance(identifier, source_id),
    )


def _layer(
    role: LayerRole,
    source_id: str,
    *primitives: FlashPrimitive,
    confidence: float = 0.99,
) -> PCBLayer:
    side = (
        BoardSide.TOP
        if role
        in {
            LayerRole.TOP_COPPER,
            LayerRole.TOP_SOLDER_MASK,
            LayerRole.TOP_SILKSCREEN,
        }
        else BoardSide.BOTTOM
    )
    return PCBLayer(
        layer_id=f"layer-{role.value}",
        source_file_id=source_id,
        role=role,
        side=side,
        mapping_confidence=confidence,
        primitives=primitives,
    )


def _top_layers(
    silk: FlashPrimitive,
    *,
    mask: FlashPrimitive | None = None,
) -> tuple[PCBLayer, ...]:
    mask_opening = mask or _flash(
        "mask-opening",
        source_id=MASK_SOURCE,
        diameter=1.2,
    )
    return (
        _layer(
            LayerRole.TOP_COPPER,
            COPPER_SOURCE,
            _flash("copper-pad", source_id=COPPER_SOURCE),
        ),
        _layer(
            LayerRole.TOP_SOLDER_MASK,
            MASK_SOURCE,
            mask_opening,
        ),
        _layer(LayerRole.TOP_SILKSCREEN, SILK_SOURCE, silk),
    )


def _project(
    *layers: PCBLayer,
    uncertain_source: str | None = None,
) -> PCBProject:
    source_ids = tuple(dict.fromkeys(layer.source_file_id for layer in layers))
    sources = tuple(
        SourceFile(
            source_file_id=source_id,
            logical_path=f"layer-{index}.gbr",
            sha256=f"{index + 1:x}" * 64,
            size_bytes=1,
            file_type=FileType.GERBER,
        )
        for index, source_id in enumerate(source_ids)
    )
    uncertainties = (
        (
            Uncertainty(
                risk_mode=RiskMode.PARSER_LIMITATION,
                subject="surface source limitation",
                summary="A relevant source limitation requires confirmation.",
                candidates=("SOURCE_LIMITATION",),
                evidence=(_provenance("diagnostic-a", uncertain_source),),
            ),
        )
        if uncertain_source is not None
        else ()
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=sources,
        manifest=ProjectManifest(project_id=PROJECT_ID, source_files=sources),
        coordinate_system=CoordinateSystem(),
        layers=layers,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="a" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
        uncertainties=uncertainties,
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return SilkscreenOverExposedPadRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_no_overlap_and_exact_boundary_touch_pass() -> None:
    separated = _evaluate(
        _project(
            *_top_layers(
                _flash(
                    "silk-far",
                    source_id=SILK_SOURCE,
                    x=1.0,
                    diameter=0.1,
                )
            )
        )
    )
    touching = _evaluate(
        _project(
            *_top_layers(
                _flash(
                    "silk-touch",
                    source_id=SILK_SOURCE,
                    x=0.55,
                    diameter=0.1,
                )
            )
        )
    )

    assert separated.outcome is RuleOutcome.PASS
    assert separated.coverage is RuleCoverage.FULL
    assert touching.outcome is RuleOutcome.PASS


def test_confirmed_same_side_overlap_has_three_layer_evidence() -> None:
    project = _project(
        *_top_layers(
            _flash(
                "silk-overlap",
                source_id=SILK_SOURCE,
                diameter=0.2,
            )
        )
    )

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.actual > 0.0
    assert finding.measurement.required == 0.0
    assert finding.measurement.unit is Unit.SQUARE_MILLIMETRE
    assert {item.provenance.object_id for item in finding.evidence} == {
        "copper-pad",
        "mask-opening",
        "silk-overlap",
    }


def test_shallow_overlap_inside_error_band_requires_confirmation() -> None:
    result = _evaluate(
        _project(
            *_top_layers(
                _flash(
                    "silk-band",
                    source_id=SILK_SOURCE,
                    x=0.549,
                    diameter=0.1,
                )
            )
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation


def test_opposite_side_silkscreen_is_never_compared() -> None:
    layers = (
        _layer(
            LayerRole.TOP_COPPER,
            COPPER_SOURCE,
            _flash("top-copper", source_id=COPPER_SOURCE),
        ),
        _layer(
            LayerRole.TOP_SOLDER_MASK,
            MASK_SOURCE,
            _flash("top-mask", source_id=MASK_SOURCE, diameter=1.2),
        ),
        _layer(
            LayerRole.BOTTOM_SILKSCREEN,
            SILK_SOURCE,
            _flash("bottom-silk", source_id=SILK_SOURCE, diameter=0.2),
        ),
    )

    result = _evaluate(_project(*layers))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_missing_optional_mask_is_not_applicable() -> None:
    layers = (
        _layer(
            LayerRole.TOP_COPPER,
            COPPER_SOURCE,
            _flash("top-copper", source_id=COPPER_SOURCE),
        ),
        _layer(
            LayerRole.TOP_SILKSCREEN,
            SILK_SOURCE,
            _flash("top-silk", source_id=SILK_SOURCE),
        ),
    )

    result = _evaluate(_project(*layers))

    assert result.reason is RuleReason.NOT_APPLICABLE


def test_unknown_polarity_or_weak_mapping_is_input_uncertain() -> None:
    unknown_layers = _top_layers(
        _flash(
            "silk-unknown",
            source_id=SILK_SOURCE,
            polarity=Polarity.UNKNOWN,
        )
    )
    weak_layers = (
        *unknown_layers[:2],
        unknown_layers[2].model_copy(update={"mapping_confidence": 0.5}),
    )

    unknown = _evaluate(_project(*unknown_layers))
    weak = _evaluate(_project(*weak_layers))

    assert unknown.reason is RuleReason.INPUT_UNCERTAIN
    assert weak.reason is RuleReason.INPUT_UNCERTAIN


def test_macro_geometry_is_explicitly_unsupported() -> None:
    result = _evaluate(
        _project(
            *_top_layers(
                _flash(
                    "silk-macro",
                    source_id=SILK_SOURCE,
                    shape=ApertureShape.MACRO,
                )
            )
        )
    )

    assert result.reason is RuleReason.UNSUPPORTED_GEOMETRY


def test_source_uncertainty_downgrades_overlap_to_confirmation() -> None:
    result = _evaluate(
        _project(
            *_top_layers(
                _flash(
                    "silk-overlap",
                    source_id=SILK_SOURCE,
                    diameter=0.2,
                )
            ),
            uncertain_source=MASK_SOURCE,
        )
    )

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation
    assert "diagnostic-a" in {
        item.provenance.object_id for item in result.findings[0].evidence
    }


def test_bottom_side_complete_set_is_evaluated() -> None:
    layers = (
        _layer(
            LayerRole.BOTTOM_COPPER,
            COPPER_SOURCE,
            _flash("bottom-copper", source_id=COPPER_SOURCE),
        ),
        _layer(
            LayerRole.BOTTOM_SOLDER_MASK,
            MASK_SOURCE,
            _flash("bottom-mask", source_id=MASK_SOURCE, diameter=1.2),
        ),
        _layer(
            LayerRole.BOTTOM_SILKSCREEN,
            SILK_SOURCE,
            _flash("bottom-silk", source_id=SILK_SOURCE, diameter=0.2),
        ),
    )

    result = _evaluate(_project(*layers))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.findings[0].facts[0] == "Board side is bottom."


def test_silkscreen_review_json_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(
            *_top_layers(
                _flash(
                    "silk-overlap",
                    source_id=SILK_SOURCE,
                    diameter=0.2,
                )
            )
        ),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "silkscreen_over_exposed_pad"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    restored = ReviewResult.model_validate_json(review.model_dump_json())
    assert restored.model_dump_json() == review.model_dump_json()
