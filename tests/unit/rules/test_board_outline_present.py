"""board_outline_present v1 semantics."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.enums import BoardSide, FileType, LayerRole, RiskMode
from boardgate.domain.geometry import BoundingBox, CoordinateSystem, Point
from boardgate.domain.layer import (
    BoardOutline,
    LayerMappingCandidate,
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
)
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.file_rules import BoardOutlinePresentRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _source(file_type: FileType = FileType.GERBER) -> SourceFile:
    return SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.gko",
        sha256="a" * 64,
        size_bytes=1,
        file_type=file_type,
    )


def _outline() -> BoardOutline:
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
    provenance = Provenance(
        source_file_id=SOURCE_ID,
        object_id="layer-0123456789abcdef",
        parser="test-outline",
        parser_version="1.0",
    )
    return BoardOutline(
        contours=(
            OutlineContour(
                contour_id="contour-0123456789abcdef",
                kind="outer",
                segments=segments,
                points=points,
                closed=True,
                approximation_error_mm=0.001,
                source_primitive_ids=("a", "b", "c", "d"),
            ),
        ),
        bounding_box=BoundingBox(
            minimum=Point(x=0, y=0),
            maximum=Point(x=10, y=10),
        ),
        outer_contour_count=1,
        measurement_error_mm=0.001,
        provenance=(provenance,),
    )


def _project(
    *,
    outline: BoardOutline | None = None,
    layers: tuple[PCBLayer, ...] = (),
    source: SourceFile | None = None,
) -> PCBProject:
    selected_source = source or _source()
    manifest = ProjectManifest(
        project_id=PROJECT_ID,
        source_files=(selected_source,),
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=(selected_source,),
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
    return BoardOutlinePresentRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_reconstructed_outline_passes_fully() -> None:
    result = _evaluate(_project(outline=_outline()))

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL


def test_outline_layer_without_reconstruction_is_partial_confirmation() -> None:
    layer = PCBLayer(
        layer_id="layer-0123456789abcdef",
        source_file_id=SOURCE_ID,
        role=LayerRole.BOARD_OUTLINE,
        side=BoardSide.NOT_APPLICABLE,
        mapping_confidence=0.99,
    )

    result = _evaluate(_project(layers=(layer,)))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].category is RiskMode.OUTLINE_UNCERTAIN
    assert result.findings[0].requires_human_confirmation
    assert result.findings[0].evidence[0].layer_id == layer.layer_id


def test_mapping_candidate_is_partial_confirmation() -> None:
    layer = PCBLayer(
        layer_id="layer-0123456789abcdef",
        source_file_id=SOURCE_ID,
        role=LayerRole.UNKNOWN,
        side=BoardSide.UNKNOWN,
        mapping_confidence=0.0,
        mapping_candidates=(
            LayerMappingCandidate(
                role=LayerRole.BOARD_OUTLINE,
                side=BoardSide.NOT_APPLICABLE,
                confidence=0.8,
                evidence=("filename:profile",),
            ),
        ),
    )

    assert _evaluate(_project(layers=(layer,))).coverage is RuleCoverage.PARTIAL


def test_confirmed_absence_is_stable_full_finding() -> None:
    project = _project()

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.coverage is RuleCoverage.FULL
    assert first.findings[0].category is RiskMode.FILE_INCOMPLETE
    assert first.findings[0].config_path == "rules.board_outline_present"
    assert not first.findings[0].requires_human_confirmation


def test_outline_rule_review_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(outline=_outline()),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "board_outline_present"
    )

    assert result.outcome is RuleOutcome.PASS
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
