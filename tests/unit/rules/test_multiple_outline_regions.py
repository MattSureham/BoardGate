"""multiple_outline_regions v1 semantics."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Literal

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.enums import FileType, RiskMode
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
from boardgate.rules.file_rules import MultipleOutlineRegionsRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _contour(
    identifier: str,
    *,
    minimum: float,
    maximum: float,
    kind: Literal["outer", "cutout"],
) -> OutlineContour:
    points = (
        Point(x=minimum, y=minimum),
        Point(x=maximum, y=minimum),
        Point(x=maximum, y=maximum),
        Point(x=minimum, y=maximum),
        Point(x=minimum, y=minimum),
    )
    segments = tuple(
        RegionLineSegment(start=start, end=end) for start, end in pairwise(points)
    )
    return OutlineContour(
        contour_id=identifier,
        kind=kind,
        segments=segments,
        points=points,
        closed=True,
        approximation_error_mm=0.001,
        source_primitive_ids=tuple(
            f"{identifier}-segment-{index}" for index in range(4)
        ),
    )


def _outline(*contours: OutlineContour) -> BoardOutline:
    all_points = tuple(point for contour in contours for point in contour.points)
    provenance = tuple(
        Provenance(
            source_file_id=SOURCE_ID,
            object_id=identifier,
            parser="test-outline",
            parser_version="1.0",
        )
        for contour in contours
        for identifier in contour.source_primitive_ids
    )
    return BoardOutline(
        contours=contours,
        bounding_box=BoundingBox(
            minimum=Point(
                x=min(point.x for point in all_points),
                y=min(point.y for point in all_points),
            ),
            maximum=Point(
                x=max(point.x for point in all_points),
                y=max(point.y for point in all_points),
            ),
        ),
        outer_contour_count=sum(contour.kind == "outer" for contour in contours),
        measurement_error_mm=0.001,
        provenance=provenance,
    )


def _project(outline: BoardOutline | None) -> PCBProject:
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
        board_outline=outline,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="b" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return MultipleOutlineRegionsRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_one_outer_with_nested_cutout_passes() -> None:
    result = _evaluate(
        _project(
            _outline(
                _contour("outer-a", minimum=0, maximum=10, kind="outer"),
                _contour("cutout-a", minimum=3, maximum=4, kind="cutout"),
            )
        )
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL


def test_two_outer_regions_produce_one_stable_confirmation() -> None:
    project = _project(
        _outline(
            _contour("outer-a", minimum=0, maximum=10, kind="outer"),
            _contour("outer-b", minimum=20, maximum=30, kind="outer"),
        )
    )

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert finding.category is RiskMode.DESIGN_INTENT_UNKNOWN
    assert finding.requires_human_confirmation
    assert len({item.witness_bounds for item in finding.evidence}) == 2


def test_missing_outline_is_not_applicable_directly() -> None:
    result = _evaluate(_project(None))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_multiple_region_rule_round_trip_through_dependencies() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    project = _project(
        _outline(
            _contour("outer-a", minimum=0, maximum=10, kind="outer"),
            _contour("outer-b", minimum=20, maximum=30, kind="outer"),
        )
    )
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        project,
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "multiple_outline_regions"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
