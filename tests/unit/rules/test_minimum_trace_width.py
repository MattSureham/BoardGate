"""minimum_trace_width v1 eligibility and error-band semantics."""

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
from boardgate.domain.geometry import CoordinateSystem, Point
from boardgate.domain.layer import Aperture, LinePrimitive, PCBLayer
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
from boardgate.rules.geometry_rules import MinimumTraceWidthRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _line(
    identifier: str,
    width: float,
    *,
    y: float = 0.0,
    polarity: Polarity = Polarity.DARK,
    shape: ApertureShape = ApertureShape.CIRCLE,
) -> LinePrimitive:
    return LinePrimitive(
        primitive_id=identifier,
        start=Point(x=0, y=y),
        end=Point(x=10, y=y),
        aperture=Aperture(
            shape=shape,
            width_mm=width,
            height_mm=(width if shape is ApertureShape.CIRCLE else width * 2),
        ),
        polarity=polarity,
        provenance=Provenance(
            source_file_id=SOURCE_ID,
            object_id=identifier,
            parser="test-gerber",
            parser_version="1.0",
        ),
    )


def _project(*primitives: LinePrimitive) -> PCBProject:
    source = SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.gtl",
        sha256="a" * 64,
        size_bytes=1,
        file_type=FileType.GERBER,
    )
    manifest = ProjectManifest(project_id=PROJECT_ID, source_files=(source,))
    layer = PCBLayer(
        layer_id="layer-0123456789abcdef",
        source_file_id=SOURCE_ID,
        role=LayerRole.TOP_COPPER,
        side=BoardSide.TOP,
        mapping_confidence=0.99,
        primitives=primitives,
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=(source,),
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        layers=(layer,),
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="b" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return MinimumTraceWidthRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_wide_trace_passes() -> None:
    result = _evaluate(_project(_line("line-wide", 0.12)))

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL


def test_width_equal_to_threshold_passes_despite_geometry_epsilon() -> None:
    result = _evaluate(_project(_line("line-equal", 0.1)))

    assert result.outcome is RuleOutcome.PASS


def test_narrow_trace_is_confirmed_after_error() -> None:
    project = _project(_line("line-narrow", 0.098))

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert finding.category is RiskMode.GEOMETRY_VIOLATION
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.actual == 0.098
    assert finding.evidence[0].layer_id == "layer-0123456789abcdef"


def test_trace_width_error_band_requires_confirmation() -> None:
    result = _evaluate(_project(_line("line-band", 0.0995)))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation


def test_fully_widened_narrow_draw_is_excluded() -> None:
    result = _evaluate(
        _project(
            _line("line-narrow", 0.05),
            _line("line-wide", 0.2),
        )
    )

    assert result.outcome is RuleOutcome.PASS
    assert not result.findings
    assert result.evaluated_object_count == 1


def test_positive_tolerance_sliver_forces_partial_without_hard_finding() -> None:
    result = _evaluate(
        _project(
            _line("line-narrow", 0.05),
            _line("line-wide", 0.2, y=0.075000001),
        )
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.PARTIAL
    assert not result.findings
    assert result.evaluated_object_count == 1
    assert result.applicable_object_count == 2


def test_non_circular_and_clear_cut_geometry_is_explicitly_unsupported() -> None:
    non_circular = _evaluate(
        _project(
            _line(
                "line-rectangular",
                0.08,
                shape=ApertureShape.RECTANGLE,
            )
        )
    )
    clear_cut = _evaluate(
        _project(
            _line("line-dark", 0.08),
            _line("line-clear", 0.04, polarity=Polarity.CLEAR),
        )
    )

    assert non_circular.outcome is RuleOutcome.SKIPPED
    assert non_circular.reason is RuleReason.UNSUPPORTED_GEOMETRY
    assert clear_cut.outcome is RuleOutcome.SKIPPED
    assert clear_cut.reason is RuleReason.UNSUPPORTED_GEOMETRY


def test_unknown_polarity_suppresses_trace_measurements() -> None:
    result = _evaluate(
        _project(
            _line("line-narrow", 0.05),
            _line("unknown-wide", 0.2, polarity=Polarity.UNKNOWN),
        )
    )

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.INPUT_UNCERTAIN
    assert not result.findings


def test_trace_rule_review_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(_line("line-narrow", 0.098)),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "minimum_trace_width"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
