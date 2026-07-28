"""minimum_copper_spacing v1 final-component semantics."""

from __future__ import annotations

from pathlib import Path

from shapely.geometry import box

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    FileType,
    LayerRole,
    Polarity,
)
from boardgate.domain.geometry import CoordinateSystem, Point
from boardgate.domain.layer import Aperture, FlashPrimitive, PCBLayer
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile
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
from boardgate.rules.derived_geometry import component_pairs_within
from boardgate.rules.geometry_rules import MinimumCopperSpacingRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _flash(  # noqa: PLR0913
    identifier: str,
    x: float,
    *,
    y: float = 0.0,
    width: float = 0.1,
    height: float | None = None,
    shape: ApertureShape = ApertureShape.CIRCLE,
    polarity: Polarity = Polarity.DARK,
    source_id: str = SOURCE_ID,
) -> FlashPrimitive:
    return FlashPrimitive(
        primitive_id=identifier,
        position=Point(x=x, y=y),
        aperture=Aperture(
            shape=shape,
            width_mm=width,
            height_mm=height or width,
        ),
        polarity=polarity,
        provenance=Provenance(
            source_file_id=source_id,
            object_id=identifier,
            parser="test-gerber",
            parser_version="1.0",
        ),
    )


def _project(*layers: PCBLayer) -> PCBProject:
    source_ids = tuple(dict.fromkeys(layer.source_file_id for layer in layers))
    sources = tuple(
        SourceFile(
            source_file_id=source_id,
            logical_path=f"copper-{index}.g{index + 1}",
            sha256=f"{index + 1:x}" * 64,
            size_bytes=1,
            file_type=FileType.GERBER,
        )
        for index, source_id in enumerate(source_ids)
    )
    manifest = ProjectManifest(project_id=PROJECT_ID, source_files=sources)
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=sources,
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        layers=layers,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="c" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _layer(
    *primitives: FlashPrimitive,
    source_id: str = SOURCE_ID,
    layer_id: str = "layer-0123456789abcdef",
    role: LayerRole = LayerRole.TOP_COPPER,
) -> PCBLayer:
    return PCBLayer(
        layer_id=layer_id,
        source_file_id=source_id,
        role=role,
        side=(BoardSide.TOP if role is LayerRole.TOP_COPPER else BoardSide.BOTTOM),
        mapping_confidence=0.99,
        primitives=primitives,
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return MinimumCopperSpacingRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_separated_components_pass_and_exact_threshold_passes() -> None:
    wide = _evaluate(_project(_layer(_flash("a", 0), _flash("b", 0.25))))
    equal = _evaluate(_project(_layer(_flash("a", 0), _flash("b", 0.2))))

    assert wide.outcome is RuleOutcome.PASS
    assert equal.outcome is RuleOutcome.PASS


def test_confirmed_spacing_violation_has_two_component_witnesses() -> None:
    project = _project(_layer(_flash("a", 0), _flash("b", 0.19)))

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert len({item.provenance.object_id for item in finding.evidence}) == 2
    assert "no electrical net was inferred" in finding.facts[1]


def test_spacing_error_band_is_partial_confirmation() -> None:
    result = _evaluate(_project(_layer(_flash("a", 0), _flash("b", 0.198))))

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation


def test_same_connected_component_is_never_compared_with_itself() -> None:
    result = _evaluate(
        _project(_layer(_flash("a", 0, width=0.2), _flash("b", 0.1, width=0.2)))
    )

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_clear_polarity_can_split_final_copper_into_components() -> None:
    result = _evaluate(
        _project(
            _layer(
                _flash("dark", 0, width=1.0),
                _flash(
                    "clear",
                    0,
                    width=0.05,
                    height=2.0,
                    shape=ApertureShape.RECTANGLE,
                    polarity=Polarity.CLEAR,
                ),
            )
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.applicable_object_count == 1


def test_components_are_not_compared_across_layers() -> None:
    second_source = "src-fedcba9876543210"
    result = _evaluate(
        _project(
            _layer(_flash("top", 0), source_id=SOURCE_ID),
            _layer(
                _flash("bottom", 0, source_id=second_source),
                source_id=second_source,
                layer_id="layer-fedcba9876543210",
                role=LayerRole.BOTTOM_COPPER,
            ),
        )
    )

    assert result.outcome is RuleOutcome.SKIPPED


def test_strtree_pairs_match_brute_force_baseline() -> None:
    components = (
        box(0, 0, 1, 1),
        box(1.05, 0, 2.05, 1),
        box(4, 0, 5, 1),
        box(4, 1.08, 5, 2.08),
    )
    maximum = 0.1
    indexed = component_pairs_within(components, maximum_distance=maximum)
    brute = tuple(
        (first, second, components[first].distance(components[second]))
        for first in range(len(components))
        for second in range(first + 1, len(components))
        if components[first].distance(components[second]) <= maximum
    )

    assert indexed == brute


def test_spacing_rule_review_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(_layer(_flash("a", 0), _flash("b", 0.19))),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "minimum_copper_spacing"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
