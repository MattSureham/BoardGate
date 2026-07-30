"""Bounded shared derived-geometry workspace contracts."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

import boardgate.rules.derived_geometry as derived_geometry_module
from boardgate.config import load_rule_profile, profile_hash
from boardgate.config.models import RuleId
from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    FileType,
    LayerRole,
    Polarity,
    RiskMode,
    Severity,
)
from boardgate.domain.finding import Finding, FindingEvidence
from boardgate.domain.geometry import CoordinateSystem, Point
from boardgate.domain.layer import (
    Aperture,
    ArcPrimitive,
    FlashPrimitive,
    GraphicPrimitive,
    LinePrimitive,
    PCBLayer,
)
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile
from boardgate.rules.derived_geometry import (
    DerivedGeometryWorkspace,
    IntersectionCandidateScope,
    LayerComposite,
    derive_primitive,
    geometry_components,
)
from boardgate.rules.engine import RuleContext, RuleEngine
from boardgate.rules.geometry_rules import MinimumTraceWidthRule
from boardgate.rules.models import (
    GeometryResourcePolicy,
    RuleCoverage,
    RuleCoverageGap,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
)
from boardgate.rules.registry import RuleRegistry

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_TOP = "src-1111111111111111"
SOURCE_BOTTOM = "src-2222222222222222"


def _flash(
    identifier: str,
    x: float,
    *,
    source_id: str = SOURCE_TOP,
    polarity: Polarity = Polarity.DARK,
    width: float = 0.1,
) -> FlashPrimitive:
    return FlashPrimitive(
        primitive_id=identifier,
        position=Point(x=x, y=0.0),
        aperture=Aperture(shape=ApertureShape.CIRCLE, width_mm=width),
        polarity=polarity,
        provenance=Provenance(
            source_file_id=source_id,
            object_id=identifier,
            parser="test-gerber",
            parser_version="1.0",
        ),
    )


def _line(identifier: str, *, source_id: str = SOURCE_TOP) -> LinePrimitive:
    return LinePrimitive(
        primitive_id=identifier,
        start=Point(x=0.0, y=0.0),
        end=Point(x=1.0, y=0.0),
        aperture=Aperture(shape=ApertureShape.CIRCLE, width_mm=0.05),
        polarity=Polarity.DARK,
        provenance=Provenance(
            source_file_id=source_id,
            object_id=identifier,
            parser="test-gerber",
            parser_version="1.0",
        ),
    )


def _layer(
    *primitives: GraphicPrimitive,
    source_id: str = SOURCE_TOP,
    layer_id: str = "layer-top",
    role: LayerRole = LayerRole.TOP_COPPER,
) -> PCBLayer:
    return PCBLayer(
        layer_id=layer_id,
        source_file_id=source_id,
        role=role,
        side=BoardSide.TOP if role is LayerRole.TOP_COPPER else BoardSide.BOTTOM,
        mapping_confidence=0.99,
        primitives=primitives,
    )


def _project(*layers: PCBLayer) -> PCBProject:
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
    )


def _compose(
    workspace: DerivedGeometryWorkspace,
    layer: PCBLayer,
) -> LayerComposite:
    return workspace.composite_layer(
        layer,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
    )


def test_fixed_policy_defaults_and_gap_require_n_plus_one() -> None:
    policy = GeometryResourcePolicy()

    assert policy.policy_version == "1.0"
    assert policy.max_primitives_per_layer == 50_000
    assert policy.max_primitives_per_review == 150_000
    assert policy.max_derived_coordinates_per_layer == 1_500_000
    assert policy.max_intersection_candidates_per_layer == 1_000_000
    assert policy.max_primitives_per_connected_subset == 4_096
    assert policy.max_union_inputs_per_batch == 128
    assert policy.max_component_pair_candidates == 250_000

    with pytest.raises(ValidationError, match="must exceed"):
        RuleCoverageGap(
            source_file_id=SOURCE_TOP,
            layer_id="layer-top",
            metric="layer_primitive_count",
            unit="primitives",
            observed=1,
            limit=1,
            summary="Equality is allowed and therefore is not a gap.",
        )


def _test_gap() -> RuleCoverageGap:
    return RuleCoverageGap(
        source_file_id=SOURCE_TOP,
        layer_id="layer-top",
        metric="layer_primitive_count",
        unit="primitives",
        observed=2,
        limit=1,
        summary="The layer exceeds the deterministic primitive limit.",
    )


def _test_finding() -> Finding:
    provenance = Provenance(
        source_file_id=SOURCE_TOP,
        object_id="test-object",
        parser="test",
        parser_version="1.0",
    )
    return Finding(
        finding_id="fnd-0123456789abcdef",
        rule_id=RuleId.MINIMUM_TRACE_WIDTH.value,
        rule_version="1.0",
        category=RiskMode.GEOMETRY_VIOLATION,
        severity=Severity.WARNING,
        confidence=1.0,
        config_path="fabrication.min_trace_width",
        title="Test geometry finding",
        summary="A deterministic test finding.",
        facts=("The test fact is deterministic.",),
        evidence=(FindingEvidence(provenance=provenance),),
    )


def test_rule_evaluation_rejects_untruthful_gap_shapes() -> None:
    gap = _test_gap()
    with pytest.raises(ValidationError, match="require PARTIAL"):
        RuleEvaluation(
            outcome=RuleOutcome.PASS,
            coverage=RuleCoverage.NONE,
            coverage_gaps=(gap,),
            summary="A pass cannot publish a gap without partial coverage.",
        )
    with pytest.raises(ValidationError, match="require PARTIAL"):
        RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=RuleCoverage.NONE,
            findings=(_test_finding(),),
            coverage_gaps=(gap,),
            summary="Findings cannot publish a gap without partial coverage.",
        )
    with pytest.raises(ValidationError, match="must not publish"):
        RuleEvaluation(
            outcome=RuleOutcome.FAILED,
            coverage=RuleCoverage.NONE,
            coverage_gaps=(gap,),
            reason=RuleReason.RULE_EXCEPTION,
            summary="Failed rules cannot publish partial geometry evidence.",
        )


@dataclass(frozen=True)
class _LimitedProbeRule:
    workspaces: list[DerivedGeometryWorkspace]
    rule_id: RuleId = RuleId.MINIMUM_TRACE_WIDTH
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = ()

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        self.workspaces.append(context.derived_geometry)
        composites = tuple(
            context.derived_geometry.composite_layer(
                layer,
                arc_chord_error_mm=context.profile.tolerances.arc_chord_error,
                geometry_epsilon_mm=context.profile.tolerances.geometry_epsilon,
            )
            for layer in reversed(context.project.layers)
        )
        gaps = tuple(gap for composite in composites for gap in composite.coverage_gaps)
        return RuleEvaluation(
            outcome=RuleOutcome.SKIPPED,
            coverage=RuleCoverage.NONE,
            reason=RuleReason.COMPUTATION_LIMIT,
            coverage_gaps=gaps,
            summary="The probe scope exceeded deterministic geometry limits.",
        )


def test_engine_persists_policy_orders_gaps_and_isolates_review_workspaces() -> None:
    top = _layer(_flash("top-a", 0.0), _flash("top-b", 1.0))
    bottom = _layer(
        _flash("bottom-a", 0.0, source_id=SOURCE_BOTTOM),
        _flash("bottom-b", 1.0, source_id=SOURCE_BOTTOM),
        source_id=SOURCE_BOTTOM,
        layer_id="layer-bottom",
        role=LayerRole.BOTTOM_COPPER,
    )
    project = _project(top, bottom)
    policy = GeometryResourcePolicy(
        max_primitives_per_layer=1,
        max_primitives_per_review=10,
    )
    workspaces: list[DerivedGeometryWorkspace] = []
    registry = RuleRegistry.build(
        (_LimitedProbeRule(workspaces),),
        require_complete=False,
    )
    engine = RuleEngine(registry)
    profile = load_rule_profile(PROFILE_PATH)

    first = engine.evaluate(project, profile, resource_policy=policy)
    second = engine.evaluate(project, profile, resource_policy=policy)

    assert first == second
    assert first.geometry_resource_policy == policy
    assert first.coverage_gaps == first.rule_results[0].coverage_gaps
    assert first.coverage_gaps == tuple(
        sorted(first.coverage_gaps, key=lambda gap: gap.model_dump_json())
    )
    assert first.risk_modes == (RiskMode.ANALYSIS_LIMITATION,)
    assert len(workspaces) == 2
    assert workspaces[0] is not workspaces[1]


def test_coordinate_preflight_allows_equality_and_blocks_n_plus_one_before_geos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    layer = _layer(_flash("one", 0.0))
    equality_policy = GeometryResourcePolicy(max_derived_coordinates_per_layer=17)
    equality = _compose(DerivedGeometryWorkspace(policy=equality_policy), layer)
    assert not equality.coverage_gaps

    calls = 0

    def _unexpected_derivation(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise AssertionError("GEOS derivation must not run after failed preflight")

    monkeypatch.setattr(
        "boardgate.rules.derived_geometry.derive_primitive",
        _unexpected_derivation,
    )
    limited_policy = GeometryResourcePolicy(max_derived_coordinates_per_layer=16)
    limited = _compose(DerivedGeometryWorkspace(policy=limited_policy), layer)

    assert calls == 0
    assert limited.evaluated_primitive_count == 0
    assert limited.coverage_gaps[0].observed == 17
    assert limited.coverage_gaps[0].limit == 16


def test_coordinate_preflight_is_constant_space_for_extreme_finite_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    huge_flash = _flash("huge-flash", 0.0, width=1e300)
    huge_arc = ArcPrimitive(
        primitive_id="huge-arc",
        start=Point(x=1e300, y=0.0),
        end=Point(x=0.0, y=1e300),
        center=Point(x=0.0, y=0.0),
        clockwise=False,
        aperture=Aperture(shape=ApertureShape.CIRCLE, width_mm=0.1),
        polarity=Polarity.DARK,
        provenance=Provenance(
            source_file_id=SOURCE_TOP,
            object_id="huge-arc",
            parser="test-gerber",
            parser_version="1.0",
        ),
    )

    def _unexpected_allocation(*args: object, **kwargs: object) -> object:
        raise AssertionError("preflight must not allocate derived arc/buffer points")

    monkeypatch.setattr(
        "boardgate.rules.derived_geometry.derive_primitive",
        _unexpected_allocation,
    )
    monkeypatch.setattr(
        "boardgate.rules.derived_geometry.approximate_arc",
        _unexpected_allocation,
    )

    arc_result = _compose(DerivedGeometryWorkspace(), _layer(huge_arc))
    flash_result = _compose(DerivedGeometryWorkspace(), _layer(huge_flash))

    for result in (arc_result, flash_result):
        assert result.geometry.is_empty
        assert result.coverage_gaps
        assert result.coverage_gaps[0].metric == "derived_coordinate_upper_bound"
        assert result.coverage_gaps[0].observed == 1_500_001


def test_layer_and_review_primitive_limits_allow_equality_and_preflight_n_plus_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    one = _layer(_flash("one", 0.0))
    layer_equality = _compose(
        DerivedGeometryWorkspace(
            policy=GeometryResourcePolicy(max_primitives_per_layer=1)
        ),
        one,
    )
    assert not layer_equality.coverage_gaps

    two = _layer(_flash("one", 0.0), _flash("two", 1.0))
    review = _project(two)
    review_equality = _compose(
        DerivedGeometryWorkspace(
            project=review,
            policy=GeometryResourcePolicy(max_primitives_per_review=2),
        ),
        two,
    )
    assert not review_equality.coverage_gaps

    def _unexpected_derivation(*args: object, **kwargs: object) -> object:
        raise AssertionError("primitive-limit preflight must run before GEOS")

    monkeypatch.setattr(
        "boardgate.rules.derived_geometry.derive_primitive",
        _unexpected_derivation,
    )
    layer_limited = _compose(
        DerivedGeometryWorkspace(
            policy=GeometryResourcePolicy(max_primitives_per_layer=1)
        ),
        two,
    )
    review_limited = _compose(
        DerivedGeometryWorkspace(
            project=review,
            policy=GeometryResourcePolicy(max_primitives_per_review=1),
        ),
        two,
    )

    assert layer_limited.coverage_gaps[0].observed == 2
    assert layer_limited.coverage_gaps[0].limit == 1
    assert review_limited.coverage_gaps[0].observed == 2
    assert review_limited.coverage_gaps[0].limit == 1


def test_intersection_candidate_limit_allows_equality_and_stops_before_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    two = _layer(_flash("one", 0.0), _flash("two", 0.0))
    equality = _compose(
        DerivedGeometryWorkspace(
            policy=GeometryResourcePolicy(max_intersection_candidates_per_layer=1)
        ),
        two,
    )
    assert not equality.coverage_gaps

    def _unexpected_union(*args: object, **kwargs: object) -> object:
        raise AssertionError("candidate N+1 must stop before union")

    monkeypatch.setattr(
        "boardgate.rules.derived_geometry._bounded_union",
        _unexpected_union,
    )
    three = _layer(
        _flash("one", 0.0),
        _flash("two", 0.0),
        _flash("three", 0.0),
    )
    first = _compose(
        DerivedGeometryWorkspace(
            policy=GeometryResourcePolicy(max_intersection_candidates_per_layer=1)
        ),
        three,
    )
    second = _compose(
        DerivedGeometryWorkspace(
            policy=GeometryResourcePolicy(max_intersection_candidates_per_layer=1)
        ),
        three,
    )

    assert first == second
    assert first.coverage_gaps[0].observed == 2
    assert first.coverage_gaps[0].limit == 1
    assert first.geometry.is_empty


def test_bounded_primitive_query_allows_equality_and_caches_n_plus_one() -> None:
    layer = _layer(
        _flash("first", 0.0),
        _flash("second", 10.0),
        _flash("third", 20.0),
    )
    witness = box(-1.0, -1.0, 21.0, 1.0)
    equality = DerivedGeometryWorkspace(
        policy=GeometryResourcePolicy(max_intersection_candidates_per_layer=15)
    ).query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.0,
    )
    limited_workspace = DerivedGeometryWorkspace(
        policy=GeometryResourcePolicy(max_intersection_candidates_per_layer=10)
    )
    limited = limited_workspace.query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.0,
    )
    cached = limited_workspace.query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.0,
    )

    assert equality.complete
    assert len(equality.matches[0]) == 3
    assert not equality.coverage_gaps
    assert not limited.complete
    assert limited.matches == ()
    assert limited.coverage_gaps[0].observed == 3
    assert limited.coverage_gaps[0].limit == 2
    assert cached is limited


def test_intersection_candidate_partitions_are_total_and_order_independent() -> None:
    layer = _layer(
        _flash("first", 0.0),
        _flash("second", 10.0),
        _flash("third", 20.0),
    )
    witness = box(-1.0, -1.0, 21.0, 1.0)
    policy = GeometryResourcePolicy(max_intersection_candidates_per_layer=15)
    first_workspace = DerivedGeometryWorkspace(policy=policy)
    second_workspace = DerivedGeometryWorkspace(policy=policy)

    limits = tuple(
        first_workspace.intersection_candidate_limit(scope)
        for scope in IntersectionCandidateScope
    )
    first_trace = first_workspace.query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.0,
    )
    first_spacing = first_workspace.query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.COPPER_SPACING_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.0,
    )
    second_spacing = second_workspace.query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.COPPER_SPACING_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.0,
    )
    second_trace = second_workspace.query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.0,
    )

    assert sum(limits) == policy.max_intersection_candidates_per_layer
    assert first_trace == second_trace
    assert first_spacing == second_spacing
    assert first_trace.complete
    assert not first_spacing.complete
    assert first_spacing.coverage_gaps[0].limit == 2


def test_intersection_candidate_scope_cannot_reset_with_a_second_batch() -> None:
    layer = _layer(_flash("first", 0.0), _flash("second", 10.0))
    workspace = DerivedGeometryWorkspace()
    first_witness = box(-1.0, -1.0, 1.0, 1.0)
    second_witness = box(9.0, -1.0, 11.0, 1.0)

    workspace.query_primitives(
        layer,
        (first_witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.0,
    )

    with pytest.raises(ValueError, match="one deterministic witness batch"):
        workspace.query_primitives(
            layer,
            (second_witness,),
            scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
            arc_chord_error_mm=0.001,
            geometry_epsilon_mm=0.001,
            witness_buffer_mm=0.0,
        )


def test_connected_subset_limit_allows_equality_and_omits_n_plus_one() -> None:
    layer = _layer(_flash("one", 0.0), _flash("two", 0.0))
    equality = _compose(
        DerivedGeometryWorkspace(
            policy=GeometryResourcePolicy(max_primitives_per_connected_subset=2)
        ),
        layer,
    )
    limited_workspace = DerivedGeometryWorkspace(
        policy=GeometryResourcePolicy(max_primitives_per_connected_subset=1)
    )
    limited = _compose(limited_workspace, layer)
    cached = _compose(limited_workspace, layer)
    fresh = _compose(
        DerivedGeometryWorkspace(
            policy=GeometryResourcePolicy(max_primitives_per_connected_subset=1)
        ),
        layer,
    )

    assert not equality.coverage_gaps
    assert limited.coverage_gaps[0].observed == 2
    assert limited.coverage_gaps[0].limit == 1
    assert limited.geometry.is_empty
    assert cached is limited
    assert fresh == limited
    assert fresh is not limited


def test_union_never_exceeds_fixed_batch_fan_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    original = unary_union

    def _record_union(geometries: Iterable[BaseGeometry]) -> BaseGeometry:
        materialized = tuple(geometries)
        calls.append(len(materialized))
        return original(materialized)

    monkeypatch.setattr(derived_geometry_module, "unary_union", _record_union)
    layer = _layer(*(_flash(f"flash-{index}", 0.0) for index in range(5)))
    composite = _compose(
        DerivedGeometryWorkspace(
            policy=GeometryResourcePolicy(max_union_inputs_per_batch=2)
        ),
        layer,
    )

    assert not composite.coverage_gaps
    assert calls
    assert max(calls) <= 2


def test_component_pair_candidate_limit_allows_equality_and_returns_stable_prefix() -> (
    None
):
    layer = _layer(_flash("source", 0.0))
    two_components = (box(0, 0, 1, 1), box(1.1, 0, 2.1, 1))
    equality_workspace = DerivedGeometryWorkspace(
        policy=GeometryResourcePolicy(max_component_pair_candidates=1)
    )
    equality = equality_workspace.component_pairs_within(
        two_components,
        maximum_distance=10.0,
        layer=layer,
    )
    assert len(equality.pairs) == 1
    assert not equality.coverage_gaps
    assert equality.complete
    assert equality.evaluated_pair_count == 1

    three_components = (*two_components, box(2.2, 0, 3.2, 1))
    first = DerivedGeometryWorkspace(
        policy=GeometryResourcePolicy(max_component_pair_candidates=1)
    ).component_pairs_within(
        three_components,
        maximum_distance=10.0,
        layer=layer,
    )
    second = DerivedGeometryWorkspace(
        policy=GeometryResourcePolicy(max_component_pair_candidates=1)
    ).component_pairs_within(
        three_components,
        maximum_distance=10.0,
        layer=layer,
    )

    assert first == second
    assert first.pairs[0][:2] == (0, 1)
    assert first.pairs[0][2] == pytest.approx(0.1)
    assert first.coverage_gaps[0].observed == 2
    assert first.coverage_gaps[0].limit == 1
    assert not first.complete
    assert first.evaluated_pair_count == 1


def test_grouped_composition_matches_global_union_and_clear_subtraction() -> None:
    dark_a = _flash("dark-a", 0.0, width=0.2)
    dark_b = _flash("dark-b", 0.1, width=0.2)
    clear = _flash("clear", 0.05, polarity=Polarity.CLEAR, width=0.04)
    layer = _layer(dark_a, dark_b, clear)
    workspace = DerivedGeometryWorkspace()

    composite = _compose(workspace, layer)
    expected_dark = unary_union(
        [
            derive_primitive(
                primitive,
                arc_chord_error_mm=0.001,
                geometry_epsilon_mm=0.001,
            ).geometry
            for primitive in (dark_a, dark_b)
        ]
    )
    expected_clear = derive_primitive(
        clear,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
    ).geometry

    assert composite.geometry.symmetric_difference(
        expected_dark.difference(expected_clear)
    ).area == pytest.approx(0.0, abs=1e-12)
    assert len(geometry_components(composite.geometry)) == 1


def test_contributor_queries_hit_cache_and_do_not_cross_reviews() -> None:
    layer = _layer(_flash("one", 0.0))
    witness = derive_primitive(
        layer.primitives[0],
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
    ).geometry
    first_workspace = DerivedGeometryWorkspace()
    first = first_workspace.query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.001,
    )
    cached = first_workspace.query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.001,
    )
    second = DerivedGeometryWorkspace().query_primitives(
        layer,
        (witness,),
        scope=IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS,
        arc_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
        witness_buffer_mm=0.001,
    )

    assert cached is first
    assert second == first
    assert second is not first


def test_final_component_cache_is_shared_only_within_one_review() -> None:
    layer = _layer(_flash("first", 0.0), _flash("second", 1.0))
    workspace = DerivedGeometryWorkspace()
    composite = _compose(workspace, layer)

    first = workspace.geometry_components(composite.geometry)
    cached = workspace.geometry_components(composite.geometry)
    fresh = DerivedGeometryWorkspace().geometry_components(composite.geometry)

    assert cached is first
    assert fresh == first
    assert fresh is not first


def test_unknown_polarity_never_claims_complete_composition() -> None:
    composite = _compose(
        DerivedGeometryWorkspace(),
        _layer(_flash("unknown", 0.0, polarity=Polarity.UNKNOWN)),
    )

    assert not composite.coverage_complete
    assert composite.geometry.is_empty


def test_trace_rule_mixed_and_all_limited_scope_semantics() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    supported = _layer(_line("supported"))
    limited = _layer(
        _flash("limited-a", 1.0, source_id=SOURCE_BOTTOM, width=0.05),
        _flash("limited-b", 2.0, source_id=SOURCE_BOTTOM, width=0.05),
        source_id=SOURCE_BOTTOM,
        layer_id="layer-bottom",
        role=LayerRole.BOTTOM_COPPER,
    )
    project = _project(supported, limited)
    policy = GeometryResourcePolicy(
        max_primitives_per_layer=1,
        max_primitives_per_review=10,
    )
    mixed = MinimumTraceWidthRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
            derived_geometry=DerivedGeometryWorkspace(
                project=project,
                policy=policy,
            ),
        )
    )

    assert mixed.outcome is RuleOutcome.FINDINGS
    assert mixed.coverage is RuleCoverage.PARTIAL
    assert mixed.reason is None
    assert mixed.coverage_gaps

    all_limited_project = _project(limited)
    all_limited = MinimumTraceWidthRule().evaluate(
        RuleContext(
            project=all_limited_project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
            derived_geometry=DerivedGeometryWorkspace(
                project=all_limited_project,
                policy=policy,
            ),
        )
    )
    assert all_limited.outcome is RuleOutcome.SKIPPED
    assert all_limited.coverage is RuleCoverage.NONE
    assert all_limited.reason is RuleReason.COMPUTATION_LIMIT
    assert all_limited.coverage_gaps
    assert RiskMode.ANALYSIS_LIMITATION.value == "ANALYSIS_LIMITATION"
