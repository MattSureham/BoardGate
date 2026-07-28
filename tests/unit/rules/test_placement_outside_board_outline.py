"""placement_outside_board_outline v1 anchor-point semantics."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Literal

from boardgate.config import load_rule_profile, profile_hash
from boardgate.config.models import RuleProfile
from boardgate.domain.component import ComponentPlacement
from boardgate.domain.diagnostic import (
    SourceDiagnostic,
    SourceDiagnosticLevel,
)
from boardgate.domain.enums import BoardSide, FileType, RiskMode
from boardgate.domain.geometry import BoundingBox, CoordinateSystem, Point
from boardgate.domain.layer import BoardOutline, OutlineContour, RegionLineSegment
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import JsonScalar, Provenance, SourceSpan
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty
from boardgate.rules import (
    ReviewResult,
    RuleContext,
    RuleCoverage,
    RuleEngine,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    RuleResult,
)
from boardgate.rules.assembly_rules import PlacementOutsideBoardOutlineRule
from boardgate.rules.builtin import build_builtin_registry

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
OUTLINE_SOURCE = "src-1111111111111111"
PLACEMENT_SOURCE = "src-2222222222222222"


def _provenance(
    identifier: str,
    source_id: str,
    *,
    line: int,
    parser: str,
) -> Provenance:
    return Provenance(
        source_file_id=source_id,
        object_id=identifier,
        parser=parser,
        parser_version="1.0",
        source_span=SourceSpan(start_line=line, end_line=line),
    )


def _source(source_id: str) -> SourceFile:
    if source_id == OUTLINE_SOURCE:
        return SourceFile(
            source_file_id=source_id,
            logical_path="board.gko",
            sha256="1" * 64,
            size_bytes=1,
            file_type=FileType.GERBER,
        )
    return SourceFile(
        source_file_id=source_id,
        logical_path="placement.csv",
        sha256="2" * 64,
        size_bytes=1,
        file_type=FileType.PLACEMENT_CSV,
    )


def _contour(
    identifier: str,
    *,
    minimum: float,
    maximum: float,
    kind: Literal["outer", "cutout"],
    closed: bool = True,
) -> OutlineContour:
    points = (
        Point(x=minimum, y=minimum),
        Point(x=maximum, y=minimum),
        Point(x=maximum, y=maximum),
        Point(x=minimum, y=maximum),
        *((Point(x=minimum, y=minimum),) if closed else ()),
    )
    return OutlineContour(
        contour_id=identifier,
        kind=kind,
        segments=tuple(
            RegionLineSegment(start=start, end=end) for start, end in pairwise(points)
        ),
        points=points,
        closed=closed,
        approximation_error_mm=0.001,
        source_primitive_ids=tuple(
            f"{identifier}-segment-{index}" for index in range(len(points) - 1)
        ),
    )


def _outline(
    *,
    cutout: bool = False,
    closed: bool = True,
) -> BoardOutline:
    contours = [
        _contour(
            "outer-contour",
            minimum=0.0,
            maximum=10.0,
            kind="outer",
            closed=closed,
        )
    ]
    if cutout:
        contours.append(
            _contour(
                "cutout-contour",
                minimum=4.0,
                maximum=6.0,
                kind="cutout",
            )
        )
    return BoardOutline(
        contours=tuple(contours),
        bounding_box=BoundingBox(
            minimum=Point(x=0.0, y=0.0),
            maximum=Point(x=10.0, y=10.0),
        ),
        outer_contour_count=1,
        measurement_error_mm=0.001,
        provenance=(
            _provenance(
                "outline-source",
                OUTLINE_SOURCE,
                line=1,
                parser="test-outline",
            ),
        ),
    )


def _placement(  # noqa: PLR0913
    identifier: str,
    reference: str,
    *,
    x: float,
    y: float,
    side: BoardSide = BoardSide.TOP,
    dnp: bool = False,
    value: str | None = None,
    footprint: str | None = None,
    metadata: dict[str, JsonScalar] | None = None,
    line: int = 2,
) -> ComponentPlacement:
    return ComponentPlacement(
        reference=reference,
        position=Point(x=x, y=y),
        rotation_degrees=0.0,
        side=side,
        value=value,
        footprint=footprint,
        dnp=dnp,
        provenance=_provenance(
            identifier,
            PLACEMENT_SOURCE,
            line=line,
            parser="test-placement",
        ),
        metadata=metadata or {},
    )


def _project(  # noqa: PLR0913
    *,
    placements: tuple[ComponentPlacement, ...] = (),
    outline: BoardOutline | None = None,
    include_outline_source: bool | None = None,
    include_placement_source: bool | None = None,
    review_requested: bool = True,
    uncertainties: tuple[Uncertainty, ...] = (),
    diagnostics: tuple[SourceDiagnostic, ...] = (),
) -> PCBProject:
    has_outline_source = (
        outline is not None
        if include_outline_source is None
        else include_outline_source
    )
    has_placement_source = (
        bool(placements)
        if include_placement_source is None
        else include_placement_source
    )
    sources = (
        *((_source(OUTLINE_SOURCE),) if has_outline_source else ()),
        *((_source(PLACEMENT_SOURCE),) if has_placement_source else ()),
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=sources,
        manifest=ProjectManifest(project_id=PROJECT_ID, source_files=sources),
        coordinate_system=CoordinateSystem(),
        board_outline=outline,
        components=placements,
        source_diagnostics=diagnostics,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="a" * 64,
        ),
        assembly_requirements=AssemblyRequirements(
            review_requested=review_requested,
        ),
        uncertainties=uncertainties,
    )


def _profile(
    *,
    ignored_references: tuple[str, ...] = (),
    dnp_markers: tuple[str, ...] | None = None,
) -> RuleProfile:
    profile = load_rule_profile(PROFILE_PATH)
    return profile.model_copy(
        update={
            "policy": profile.policy.model_copy(
                update={
                    "ignored_references": ignored_references,
                    "dnp_markers": (
                        profile.policy.dnp_markers
                        if dnp_markers is None
                        else dnp_markers
                    ),
                }
            )
        }
    )


def _evaluate(
    project: PCBProject,
    *,
    profile: RuleProfile | None = None,
) -> RuleEvaluation:
    selected_profile = profile or _profile()
    return PlacementOutsideBoardOutlineRule().evaluate(
        RuleContext(
            project=project,
            profile=selected_profile,
            profile_sha256=profile_hash(selected_profile),
            prior_results=(),
        )
    )


def _target_result(review: ReviewResult) -> RuleResult:
    return next(
        result
        for result in review.rule_results
        if result.rule_id.value == "placement_outside_board_outline"
    )


def test_inactive_assembly_scope_is_not_applicable() -> None:
    result = _evaluate(
        _project(
            placements=(_placement("cpl-r1", "R1", x=11.0, y=5.0),),
            outline=_outline(),
            review_requested=False,
        )
    )

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_missing_empty_and_failed_placement_inputs_are_distinguished() -> None:
    missing = _evaluate(_project(outline=_outline()))
    empty = _evaluate(
        _project(
            outline=_outline(),
            include_placement_source=True,
        )
    )
    diagnostic = SourceDiagnostic(
        diagnostic_id="diagnostic-0123456789abcdef",
        source_file_id=PLACEMENT_SOURCE,
        code="PLACEMENT_PARSE_FAILED",
        level=SourceDiagnosticLevel.ERROR,
        message="The placement source could not be parsed.",
    )
    failed = _evaluate(
        _project(
            outline=_outline(),
            include_placement_source=True,
            diagnostics=(diagnostic,),
        )
    )

    assert missing.outcome is RuleOutcome.SKIPPED
    assert missing.coverage is RuleCoverage.NONE
    assert missing.reason is RuleReason.NOT_APPLICABLE
    assert empty.outcome is RuleOutcome.SKIPPED
    assert empty.reason is RuleReason.NOT_APPLICABLE
    assert failed.outcome is RuleOutcome.SKIPPED
    assert failed.coverage is RuleCoverage.NONE
    assert failed.reason is RuleReason.INPUT_UNCERTAIN


def test_missing_or_open_outline_cannot_support_containment() -> None:
    placement = _placement("cpl-r1", "R1", x=11.0, y=5.0)

    missing = _evaluate(_project(placements=(placement,)))
    open_outline = _evaluate(
        _project(
            placements=(placement,),
            outline=_outline(closed=False),
        )
    )

    assert missing.outcome is RuleOutcome.SKIPPED
    assert missing.coverage is RuleCoverage.NONE
    assert missing.reason is RuleReason.INPUT_UNCERTAIN
    assert open_outline.outcome is RuleOutcome.SKIPPED
    assert open_outline.coverage is RuleCoverage.NONE
    assert open_outline.reason is RuleReason.INPUT_UNCERTAIN


def test_anchor_inside_outer_contour_passes_fully() -> None:
    result = _evaluate(
        _project(
            placements=(_placement("cpl-u1", "U1", x=2.0, y=3.0),),
            outline=_outline(),
        )
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.findings == ()
    assert result.evaluated_object_count == 1
    assert result.applicable_object_count == 1


def test_strictly_outside_anchor_has_row_and_outline_witnesses() -> None:
    placement = _placement(
        "cpl-r1",
        "R1",
        x=11.0,
        y=5.0,
        line=17,
    )
    outline = _outline()

    first = _evaluate(_project(placements=(placement,), outline=outline))
    second = _evaluate(_project(placements=(placement,), outline=outline))

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    assert len(first.findings) == 1
    finding = first.findings[0]
    assert finding.category is RiskMode.GEOMETRY_VIOLATION
    assert finding.config_path == "rules.placement_outside_board_outline"
    assert finding.location == placement.position
    assert not finding.requires_human_confirmation
    evidence_by_id = {
        evidence.provenance.object_id: evidence for evidence in finding.evidence
    }
    assert {"cpl-r1", "outline-source"} <= evidence_by_id.keys()
    assert evidence_by_id["cpl-r1"].provenance.source_span == SourceSpan(
        start_line=17,
        end_line=17,
    )
    assert evidence_by_id["outline-source"].witness_bounds == outline.bounding_box


def test_exact_external_boundary_is_not_outside() -> None:
    result = _evaluate(
        _project(
            placements=(
                _placement("left-edge", "R1", x=0.0, y=5.0),
                _placement("top-edge", "R2", x=5.0, y=10.0, line=3),
            ),
            outline=_outline(),
        )
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings == ()
    assert result.evaluated_object_count == 2


def test_cutout_interior_is_outside_but_exact_boundary_is_not() -> None:
    inside_cutout = _evaluate(
        _project(
            placements=(_placement("cutout-center", "U1", x=5.0, y=5.0),),
            outline=_outline(cutout=True),
        )
    )
    on_cutout_boundary = _evaluate(
        _project(
            placements=(_placement("cutout-edge", "U1", x=4.0, y=5.0),),
            outline=_outline(cutout=True),
        )
    )

    assert inside_cutout.outcome is RuleOutcome.FINDINGS
    assert inside_cutout.coverage is RuleCoverage.FULL
    assert inside_cutout.findings[0].location == Point(x=5.0, y=5.0)
    assert on_cutout_boundary.outcome is RuleOutcome.PASS
    assert on_cutout_boundary.coverage is RuleCoverage.PARTIAL
    assert on_cutout_boundary.findings == ()


def test_top_and_bottom_placements_use_the_same_anchor_point_semantics() -> None:
    result = _evaluate(
        _project(
            placements=(
                _placement(
                    "top-outside",
                    "R1",
                    x=11.0,
                    y=5.0,
                    side=BoardSide.TOP,
                ),
                _placement(
                    "bottom-outside",
                    "R2",
                    x=-1.0,
                    y=5.0,
                    side=BoardSide.BOTTOM,
                    line=3,
                ),
            ),
            outline=_outline(),
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == 2
    assert result.applicable_object_count == 2
    assert {finding.location for finding in result.findings} == {
        Point(x=11.0, y=5.0),
        Point(x=-1.0, y=5.0),
    }
    placement_evidence_ids = {
        evidence.provenance.object_id
        for finding in result.findings
        for evidence in finding.evidence
        if evidence.provenance.source_file_id == PLACEMENT_SOURCE
    }
    assert placement_evidence_ids == {"top-outside", "bottom-outside"}


def test_dnp_markers_and_ignored_references_are_excluded() -> None:
    result = _evaluate(
        _project(
            placements=(
                _placement("active", "U1", x=5.0, y=2.0),
                _placement("explicit-dnp", "R1", x=11.0, y=5.0, dnp=True),
                _placement(
                    "marker-dnp",
                    "R2",
                    x=11.0,
                    y=5.0,
                    metadata={"Population": "No Fit"},
                ),
                _placement("ignored", " FID1 ", x=-1.0, y=5.0),
            ),
            outline=_outline(),
        ),
        profile=_profile(
            ignored_references=("fid1",),
            dnp_markers=("no fit",),
        ),
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.findings == ()
    assert result.evaluated_object_count == 1
    assert result.applicable_object_count == 1


def test_relevant_placement_and_outline_uncertainty_downgrades_finding() -> None:
    placement = _placement("cpl-u1", "U1", x=11.0, y=5.0)
    placement_uncertainty = _provenance(
        "placement-uncertainty",
        PLACEMENT_SOURCE,
        line=9,
        parser="test-classifier",
    )
    outline_uncertainty = _provenance(
        "outline-uncertainty",
        OUTLINE_SOURCE,
        line=2,
        parser="test-outline",
    )
    result = _evaluate(
        _project(
            placements=(placement,),
            outline=_outline(),
            uncertainties=(
                Uncertainty(
                    risk_mode=RiskMode.PARSER_LIMITATION,
                    subject="Placement row limitation",
                    summary="A placement row requires confirmation.",
                    evidence=(placement_uncertainty,),
                ),
                Uncertainty(
                    risk_mode=RiskMode.OUTLINE_UNCERTAIN,
                    subject="Outline geometry approximation",
                    summary="Outline source geometry requires confirmation.",
                    evidence=(outline_uncertainty,),
                ),
            ),
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.requires_human_confirmation
    assert finding.confidence == 0.5
    assert {
        "placement-uncertainty",
        "outline-uncertainty",
    } <= {evidence.provenance.object_id for evidence in finding.evidence}


def test_review_is_stable_and_json_round_trips() -> None:
    profile = _profile()
    project = _project(
        placements=(
            _placement("cpl-r1", "R1", x=11.0, y=5.0),
            _placement(
                "cpl-r2",
                "R2",
                x=5.0,
                y=5.0,
                side=BoardSide.BOTTOM,
                line=3,
            ),
        ),
        outline=_outline(cutout=True),
    )
    engine = RuleEngine(build_builtin_registry(require_complete=False))

    first = engine.evaluate(project, profile)
    second = engine.evaluate(project, profile)
    restored = ReviewResult.model_validate_json(first.model_dump_json())

    assert first == second
    assert restored.model_dump_json() == first.model_dump_json()
    target = _target_result(first)
    assert target.outcome is RuleOutcome.FINDINGS
    assert len(target.findings) == 2
    finding_ids = [finding.finding_id for finding in target.findings]
    assert len(finding_ids) == len(set(finding_ids)) == 2
