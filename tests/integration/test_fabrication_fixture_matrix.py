"""Original golden projects for fabrication uncertainty and failure boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
    parse_job,
)
from boardgate.application.project_builder import build_project
from boardgate.config import load_rule_profile
from boardgate.config.models import RuleId
from boardgate.domain.diagnostic import SourceDiagnosticLevel
from boardgate.domain.enums import (
    FileType,
    LayerRole,
    Plating,
    ReviewStatus,
    RiskMode,
)
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.parsers import ParserError
from boardgate.rules import RuleCoverage, RuleEngine, RuleOutcome, RuleReason
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.models import ReviewResult, RuleResult

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PROFILE_PATH = Path("rules/default.yaml")


@dataclass(frozen=True, slots=True)
class FixtureReview:
    """Real manifest, normalized project, and deterministic rule result."""

    manifest: ProjectManifest
    project: PCBProject
    review: ReviewResult


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


def _review_fixture(name: str) -> FixtureReview:
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
    return FixtureReview(manifest=manifest, project=project, review=review)


def _result(review: ReviewResult, rule_id: RuleId) -> RuleResult:
    return next(result for result in review.rule_results if result.rule_id is rule_id)


def test_missing_drill_is_a_confirmed_inventory_blocker() -> None:
    fixture = _review_fixture("missing_drill")
    result = _result(fixture.review, RuleId.DRILL_FILE_PRESENT)

    assert all(
        source.file_type is not FileType.EXCELLON
        for source in fixture.manifest.source_files
    )
    assert not fixture.manifest.uncertainties
    assert not fixture.project.drills
    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert len(result.findings) == 1
    assert result.findings[0].category is RiskMode.FILE_INCOMPLETE
    assert not result.findings[0].requires_human_confirmation
    assert fixture.review.overall_status is ReviewStatus.NOT_READY_FOR_FABRICATION


def test_open_outline_remains_uncertain_without_invented_topology() -> None:
    fixture = _review_fixture("open_outline")
    present = _result(fixture.review, RuleId.BOARD_OUTLINE_PRESENT)
    closed = _result(fixture.review, RuleId.BOARD_OUTLINE_CLOSED)
    multiple = _result(fixture.review, RuleId.MULTIPLE_OUTLINE_REGIONS)

    assert fixture.project.board_outline is None
    assert any(
        uncertainty.risk_mode is RiskMode.OUTLINE_UNCERTAIN
        for uncertainty in fixture.project.uncertainties
    )
    assert present.outcome is RuleOutcome.FINDINGS
    assert present.coverage is RuleCoverage.PARTIAL
    assert present.findings[0].requires_human_confirmation
    assert closed.outcome is RuleOutcome.FINDINGS
    assert closed.coverage is RuleCoverage.PARTIAL
    assert closed.findings[0].measurement is None
    assert closed.findings[0].requires_human_confirmation
    assert multiple.outcome is RuleOutcome.SKIPPED
    assert multiple.reason is RuleReason.NOT_APPLICABLE
    assert fixture.review.overall_status is ReviewStatus.INSUFFICIENT_INFORMATION


def test_multiple_disjoint_outer_regions_require_confirmation() -> None:
    fixture = _review_fixture("multiple_outline_regions")
    result = _result(fixture.review, RuleId.MULTIPLE_OUTLINE_REGIONS)

    assert fixture.project.board_outline is not None
    assert fixture.project.board_outline.outer_contour_count == 2
    assert [contour.kind for contour in fixture.project.board_outline.contours] == [
        "outer",
        "outer",
    ]
    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert len(result.findings) == 1
    assert result.findings[0].category is RiskMode.DESIGN_INTENT_UNKNOWN
    assert result.findings[0].requires_human_confirmation
    assert fixture.review.overall_status is ReviewStatus.READY_WITH_CONFIRMATIONS


def test_gross_coordinate_mismatch_is_a_confirmed_blocker() -> None:
    fixture = _review_fixture("coordinate_mismatch")
    result = _result(
        fixture.review,
        RuleId.GERBER_DRILL_COORDINATE_ALIGNMENT,
    )

    assert fixture.project.board_outline is not None
    assert len(fixture.project.drills) == 1
    assert fixture.project.drills[0].position.x == 100.0
    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.category is RiskMode.COORDINATE_MISMATCH
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.actual > finding.measurement.required
    assert fixture.review.overall_status is ReviewStatus.NOT_READY_FOR_FABRICATION


def test_conflicting_x2_and_extension_evidence_preserves_layer_ambiguity() -> None:
    fixture = _review_fixture("ambiguous_layer_names")
    result = _result(fixture.review, RuleId.REQUIRED_LAYERS_PRESENT)
    uncertain_layers = tuple(
        layer for layer in fixture.project.layers if layer.role is LayerRole.UNKNOWN
    )

    assert len(uncertain_layers) == 1
    assert {candidate.role for candidate in uncertain_layers[0].mapping_candidates} == {
        LayerRole.TOP_COPPER,
        LayerRole.BOTTOM_COPPER,
    }
    assert any(
        uncertainty.risk_mode is RiskMode.LAYER_MAPPING_UNCERTAIN
        for uncertainty in fixture.project.uncertainties
    )
    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert len(result.findings) == 1
    assert result.findings[0].category is RiskMode.LAYER_MAPPING_UNCERTAIN
    assert result.findings[0].requires_human_confirmation
    assert fixture.review.overall_status is ReviewStatus.READY_WITH_CONFIRMATIONS


def test_malformed_gerber_is_source_safe_and_not_treated_as_parsed() -> None:
    fixture = _review_fixture("malformed_gerber")
    result = _result(fixture.review, RuleId.REQUIRED_LAYERS_PRESENT)

    assert len(fixture.project.source_diagnostics) == 1
    diagnostic = fixture.project.source_diagnostics[0]
    assert diagnostic.code == "GERBER_PARSE_ERROR"
    assert diagnostic.level is SourceDiagnosticLevel.ERROR
    assert "<source>" in diagnostic.message
    assert str(FIXTURES) not in diagnostic.message
    assert LayerRole.TOP_COPPER not in {layer.role for layer in fixture.project.layers}
    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert result.findings[0].category is RiskMode.FILE_INCOMPLETE
    assert not result.findings[0].requires_human_confirmation
    assert fixture.review.overall_status is ReviewStatus.NOT_READY_FOR_FABRICATION


def test_missing_excellon_unit_is_a_typed_partial_parse_failure() -> None:
    fixture = _review_fixture("unit_ambiguity")
    presence = _result(fixture.review, RuleId.DRILL_FILE_PRESENT)
    diameter = _result(fixture.review, RuleId.MINIMUM_DRILL_DIAMETER)

    assert len(fixture.project.source_diagnostics) == 1
    diagnostic = fixture.project.source_diagnostics[0]
    assert diagnostic.code == "EXCELLON_UNIT_UNKNOWN"
    assert diagnostic.level is SourceDiagnosticLevel.ERROR
    assert not fixture.project.drills
    assert presence.outcome is RuleOutcome.FINDINGS
    assert presence.coverage is RuleCoverage.PARTIAL
    assert presence.findings[0].category is RiskMode.PARSER_LIMITATION
    assert presence.findings[0].requires_human_confirmation
    assert diameter.outcome is RuleOutcome.SKIPPED
    assert diameter.reason is RuleReason.NOT_APPLICABLE
    assert fixture.review.overall_status is ReviewStatus.INSUFFICIENT_INFORMATION


def test_npth_is_excluded_from_annular_ring_measurement() -> None:
    fixture = _review_fixture("npth_annular")
    annular = _result(fixture.review, RuleId.MINIMUM_ANNULAR_RING)

    assert len(fixture.project.drills) == 1
    assert fixture.project.drills[0].plating is Plating.NON_PLATED
    assert annular.outcome is RuleOutcome.SKIPPED
    assert annular.coverage is RuleCoverage.NONE
    assert annular.reason is RuleReason.NOT_APPLICABLE
    assert not annular.findings
    assert fixture.review.overall_status is ReviewStatus.INSUFFICIENT_INFORMATION
