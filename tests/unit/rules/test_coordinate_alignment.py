"""gerber_drill_coordinate_alignment v1 gross-bbox semantics."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.drill import DrillHit
from boardgate.domain.enums import FileType, Plating, RiskMode
from boardgate.domain.geometry import BoundingBox, CoordinateSystem, Point
from boardgate.domain.layer import (
    BoardOutline,
    OutlineContour,
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
from boardgate.rules.geometry_rules import GerberDrillCoordinateAlignmentRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
GERBER_ID = "src-0123456789abcdef"
DRILL_ID = "src-fedcba9876543210"


def _outline(error: float = 0.001) -> BoardOutline:
    points = (
        Point(x=0, y=0),
        Point(x=10, y=0),
        Point(x=10, y=10),
        Point(x=0, y=10),
        Point(x=0, y=0),
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
                closed=True,
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
                source_file_id=GERBER_ID,
                object_id="layer-0123456789abcdef",
                parser="test-outline",
                parser_version="1.0",
            ),
        ),
    )


def _drill(x: float, y: float = 5.0, diameter: float = 0.3) -> DrillHit:
    return DrillHit(
        drill_id="drill-0123456789abcdef",
        position=Point(x=x, y=y),
        diameter_mm=diameter,
        plating=Plating.PLATED,
        provenance=Provenance(
            source_file_id=DRILL_ID,
            object_id="drill-0123456789abcdef",
            parser="test-drill",
            parser_version="1.0",
        ),
    )


def _project(
    *,
    drill: DrillHit | None,
    outline: BoardOutline | None = None,
) -> PCBProject:
    sources = (
        SourceFile(
            source_file_id=GERBER_ID,
            logical_path="board.gko",
            sha256="a" * 64,
            size_bytes=1,
            file_type=FileType.GERBER,
        ),
        SourceFile(
            source_file_id=DRILL_ID,
            logical_path="board.drl",
            sha256="b" * 64,
            size_bytes=1,
            file_type=FileType.EXCELLON,
        ),
    )
    manifest = ProjectManifest(project_id=PROJECT_ID, source_files=sources)
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=sources,
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        board_outline=outline if outline is not None else _outline(),
        drills=(() if drill is None else (drill,)),
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="c" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return GerberDrillCoordinateAlignmentRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_overlapping_aggregate_bounds_pass_without_exact_alignment_claim() -> None:
    result = _evaluate(_project(drill=_drill(5)))

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert "exact pad registration was not evaluated" in result.summary


def test_exact_gross_tolerance_is_satisfied() -> None:
    result = _evaluate(_project(drill=_drill(10.65), outline=_outline(error=0)))

    assert result.outcome is RuleOutcome.PASS


def test_completely_disjoint_bounds_are_stable_mismatch() -> None:
    project = _project(drill=_drill(20))

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert finding.category is RiskMode.COORDINATE_MISMATCH
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.config_path == "tolerances.gross_alignment"
    assert "does not evaluate individual" in finding.facts[1]


def test_tolerance_error_overlap_is_partial_confirmation() -> None:
    result = _evaluate(_project(drill=_drill(10.66), outline=_outline(error=0.02)))

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation


def test_no_drill_features_is_not_applicable() -> None:
    result = _evaluate(_project(drill=None))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_alignment_rule_dependency_and_review_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(drill=_drill(20)),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "gerber_drill_coordinate_alignment"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
