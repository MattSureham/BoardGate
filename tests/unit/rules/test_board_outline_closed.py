"""board_outline_closed v1 semantics."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.enums import BoardSide, FileType, LayerRole, RiskMode
from boardgate.domain.geometry import BoundingBox, CoordinateSystem, Point
from boardgate.domain.layer import (
    BoardOutline,
    OutlineContour,
    PCBLayer,
    RegionLineSegment,
)
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
from boardgate.rules.file_rules import BoardOutlineClosedRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _outline(
    *,
    endpoint_gap: float = 0.0,
    closed: bool = True,
    error: float = 0.001,
) -> BoardOutline:
    points = (
        Point(x=0, y=0),
        Point(x=10, y=0),
        Point(x=10, y=10),
        Point(x=0, y=10),
        Point(x=endpoint_gap, y=0),
    )
    segments = tuple(
        RegionLineSegment(start=start, end=end) for start, end in pairwise(points)
    )
    return BoardOutline(
        contours=(
            OutlineContour(
                contour_id="contour-0123456789abcdef",
                kind="outer",
                segments=segments,
                points=points,
                closed=closed,
                approximation_error_mm=error,
                source_primitive_ids=("a", "b", "c", "d"),
            ),
        ),
        bounding_box=BoundingBox(
            minimum=Point(x=0, y=0),
            maximum=Point(x=10, y=10),
        ),
        outer_contour_count=1,
        measurement_error_mm=error,
        provenance=(
            Provenance(
                source_file_id=SOURCE_ID,
                object_id="layer-0123456789abcdef",
                parser="test-outline",
                parser_version="1.0",
            ),
        ),
    )


def _project(
    *,
    outline: BoardOutline | None,
    layers: tuple[PCBLayer, ...] = (),
) -> PCBProject:
    source = SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.gko",
        sha256="a" * 64,
        size_bytes=1,
        file_type=FileType.GERBER,
    )
    manifest = ProjectManifest(project_id=PROJECT_ID, source_files=(source,))
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=(source,),
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        layers=layers,
        board_outline=outline,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="b" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return BoardOutlineClosedRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_closed_outline_passes_at_exact_error_boundary() -> None:
    result = _evaluate(_project(outline=_outline(error=0.01)))

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL


def test_open_gap_above_error_band_is_confirmed_violation() -> None:
    result = _evaluate(
        _project(outline=_outline(endpoint_gap=0.02, closed=False, error=0.001))
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    finding = result.findings[0]
    assert finding.category is RiskMode.GEOMETRY_VIOLATION
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.actual == 0.02
    assert finding.measurement.required == 0.01


def test_closure_error_band_overlap_requires_confirmation() -> None:
    result = _evaluate(
        _project(outline=_outline(endpoint_gap=0.009, closed=False, error=0.002))
    )

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].category is RiskMode.OUTLINE_UNCERTAIN
    assert result.findings[0].requires_human_confirmation


def test_outline_candidate_without_topology_is_partial() -> None:
    layer = PCBLayer(
        layer_id="layer-0123456789abcdef",
        source_file_id=SOURCE_ID,
        role=LayerRole.BOARD_OUTLINE,
        side=BoardSide.NOT_APPLICABLE,
        mapping_confidence=0.99,
    )

    result = _evaluate(_project(outline=None, layers=(layer,)))

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation


def test_absent_outline_is_not_mislabeled_open() -> None:
    result = _evaluate(_project(outline=None))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_closed_rule_engine_dependency_and_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(outline=_outline(endpoint_gap=0.02, closed=False)),
        profile,
    )
    closed_result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "board_outline_closed"
    )

    assert closed_result.outcome is RuleOutcome.FINDINGS
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
