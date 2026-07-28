"""Golden evidence for the original minimal Phase 9 PCB projects."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
    parse_job,
)
from boardgate.application.project_builder import build_project
from boardgate.config import load_rule_profile
from boardgate.config.models import RuleId
from boardgate.domain.enums import FileType, LayerRole, Plating, ReviewStatus
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.parsers import ParserError
from boardgate.rules import RuleCoverage, RuleEngine, RuleOutcome
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.models import ReviewResult, RuleResult

FIXTURES = Path(__file__).parents[1] / "fixtures"
PROFILE_PATH = Path("rules/default.yaml")
SAME_COORDINATES = ("x2:same-coordinates:boardgate-phase9",)


def _inline_executor(
    job: ParserJob,
    *,
    timeout_seconds: float,
) -> ParserExecution:
    del timeout_seconds
    try:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            result=parse_job(job),
        )
    except ParserError as error:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            failure=ParserFailure(code=error.code, detail=error.detail),
        )


def _review_fixture(name: str) -> tuple[ProjectManifest, PCBProject, ReviewResult]:
    profile = load_rule_profile(PROFILE_PATH)
    with discover_inputs((FIXTURES / name,)) as discovered:
        manifest = build_manifest(discovered)
        project = build_project(
            discovered,
            manifest,
            profile,
            parser_executor=_inline_executor,
        )
    review = RuleEngine(build_builtin_registry()).evaluate(project, profile)
    return manifest, project, review


def _result(review: ReviewResult, rule_id: RuleId) -> RuleResult:
    return next(result for result in review.rule_results if result.rule_id is rule_id)


def test_valid_minimal_board_has_complete_supported_evidence() -> None:
    manifest, project, review = _review_fixture("valid_minimal_board")

    assert not manifest.uncertainties
    assert {source.file_type for source in manifest.source_files} == {
        FileType.GERBER,
        FileType.EXCELLON,
    }
    assert not project.source_diagnostics
    assert not project.uncertainties
    assert {layer.role for layer in project.layers} == {
        LayerRole.TOP_COPPER,
        LayerRole.BOTTOM_COPPER,
        LayerRole.BOARD_OUTLINE,
    }
    assert all(
        layer.coordinate_evidence == SAME_COORDINATES for layer in project.layers
    )
    assert project.board_outline is not None
    assert project.board_outline.outer_contour_count == 1
    assert all(contour.closed for contour in project.board_outline.contours)
    assert len(project.drills) == 1
    assert project.drills[0].plating is Plating.PLATED
    assert review.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert not review.findings

    required_results = tuple(
        result for result in review.rule_results if result.required
    )
    assert required_results
    assert all(result.outcome is RuleOutcome.PASS for result in required_results)
    assert _result(review, RuleId.MINIMUM_TRACE_WIDTH).evaluated_object_count == 2
    assert _result(review, RuleId.MINIMUM_COPPER_SPACING).evaluated_object_count == 2
    assert _result(review, RuleId.MINIMUM_ANNULAR_RING).evaluated_object_count == 2


def test_edge_fixture_only_adds_confirmed_copper_edge_findings() -> None:
    valid_manifest, valid_project, valid_review = _review_fixture("valid_minimal_board")
    edge_manifest, edge_project, edge_review = _review_fixture(
        "copper_too_close_to_edge"
    )

    assert len(valid_manifest.source_files) == len(edge_manifest.source_files) == 4
    assert len(valid_project.layers) == len(edge_project.layers) == 3
    assert len(valid_project.drills) == len(edge_project.drills) == 1
    assert not valid_review.findings

    edge_result = _result(edge_review, RuleId.MINIMUM_COPPER_TO_EDGE)
    assert edge_review.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert edge_result.outcome is RuleOutcome.FINDINGS
    assert edge_result.coverage is RuleCoverage.FULL
    assert len(edge_result.findings) == 2
    assert all(
        not finding.requires_human_confirmation for finding in edge_result.findings
    )
    assert tuple(
        finding.measurement.actual
        for finding in edge_result.findings
        if finding.measurement is not None
    ) == pytest.approx((0.15, 0.15))
    assert all(
        result.outcome is RuleOutcome.PASS
        for result in edge_review.rule_results
        if result.required and result.rule_id is not RuleId.MINIMUM_COPPER_TO_EDGE
    )
