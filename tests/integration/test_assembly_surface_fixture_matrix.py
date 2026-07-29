"""Golden integration evidence for assembly, surface, and archive boundaries."""

from __future__ import annotations

import zipfile
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
from boardgate.domain.enums import FileType, LayerRole, ReviewStatus
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.ingestion.errors import IngestionError
from boardgate.parsers import ParserError
from boardgate.rules import RuleCoverage, RuleEngine, RuleOutcome
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.models import ReviewResult, RuleResult

FIXTURES = Path(__file__).parents[1] / "fixtures"
PROFILE_PATH = Path("rules/default.yaml")


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


def test_bom_cpl_mismatch_preserves_directional_row_evidence() -> None:
    manifest, project, review = _review_fixture("bom_cpl_mismatch")

    assert not manifest.uncertainties
    assert {source.file_type for source in manifest.source_files} == {
        FileType.BOM_CSV,
        FileType.PLACEMENT_CSV,
    }
    assert len(project.bom_items) == len(project.components) == 3
    assert not project.source_diagnostics
    assert review.overall_status is not ReviewStatus.ANALYSIS_FAILED

    result = _result(review, RuleId.BOM_PLACEMENT_REFERENCE_MATCH)
    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == 3
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.facts[:2] == (
        "BOM-only references: R2.",
        "Placement-only references: C1.",
    )
    assert not finding.requires_human_confirmation
    row_spans = tuple(
        evidence.provenance.source_span
        for evidence in finding.evidence
        if evidence.provenance.source_span is not None
    )
    assert len(row_spans) == 2
    assert {span.start_line for span in row_spans} == {3}


def test_mask_silk_fixture_checks_overlap_and_nonoverlap_on_one_side() -> None:
    manifest, project, review = _review_fixture("mask_silk_overlap")

    assert not manifest.uncertainties
    assert not project.uncertainties
    assert {layer.role for layer in project.layers} == {
        LayerRole.TOP_COPPER,
        LayerRole.TOP_SOLDER_MASK,
        LayerRole.TOP_SILKSCREEN,
        LayerRole.BOARD_OUTLINE,
    }

    result = _result(review, RuleId.SILKSCREEN_OVER_EXPOSED_PAD)
    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == result.applicable_object_count == 2
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert not finding.requires_human_confirmation
    assert finding.location is not None
    assert finding.location.x == pytest.approx(5.0, abs=0.05)
    assert finding.measurement is not None
    assert finding.measurement.actual > finding.measurement.error_bound

    source_paths = {
        source.source_file_id: source.logical_path for source in project.source_files
    }
    contributor_paths = {
        source_paths[evidence.provenance.source_file_id]
        for evidence in finding.evidence
    }
    assert contributor_paths == {
        "board-top-copper.gtl",
        "board-top-mask.gts",
        "board-top-silk.gto",
    }
    assert all(
        evidence.provenance.source_span is not None for evidence in finding.evidence
    )


def test_outer_and_cutout_boundaries_are_contained_but_voids_are_not() -> None:
    manifest, project, review = _review_fixture("placement_boundary")

    assert not manifest.uncertainties
    assert not project.uncertainties
    assert project.board_outline is not None
    assert tuple(contour.kind for contour in project.board_outline.contours) == (
        "outer",
        "cutout",
    )

    reference_match = _result(review, RuleId.BOM_PLACEMENT_REFERENCE_MATCH)
    assert reference_match.outcome is RuleOutcome.PASS
    assert reference_match.coverage is RuleCoverage.FULL

    result = _result(review, RuleId.PLACEMENT_OUTSIDE_BOARD_OUTLINE)
    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.evaluated_object_count == result.applicable_object_count == 4
    assert len(result.findings) == 2
    assert {finding.facts[0] for finding in result.findings} == {
        "Reference is U3.",
        "Reference is U4.",
    }
    assert tuple(
        finding.measurement.actual
        for finding in result.findings
        if finding.measurement is not None
    ) == pytest.approx((1.0, 2.0))
    assert all(not finding.requires_human_confirmation for finding in result.findings)
    assert all(
        evidence.provenance.source_span is not None
        for finding in result.findings
        for evidence in finding.evidence
    )


@pytest.mark.parametrize(
    ("case_name", "expected_code"),
    (
        ("traversal", "UNSAFE_PATH"),
        ("duplicate", "DUPLICATE_LOGICAL_PATH"),
        ("compression-ratio", "COMPRESSION_RATIO_LIMIT"),
    ),
)
def test_generated_zip_security_cases_are_rejected_before_parsing(
    tmp_path: Path,
    case_name: str,
    expected_code: str,
) -> None:
    seed = (FIXTURES / "zip_security_cases" / "payload.txt").read_bytes()
    archive_path = tmp_path / f"{case_name}.zip"
    compression = (
        zipfile.ZIP_DEFLATED if case_name == "compression-ratio" else zipfile.ZIP_STORED
    )
    with zipfile.ZipFile(archive_path, "w", compression=compression) as archive:
        if case_name == "traversal":
            archive.writestr("../escaped.txt", seed)
        elif case_name == "duplicate":
            archive.writestr("Board.GTL", seed)
            archive.writestr("board.gtl", seed)
        else:
            archive.writestr("highly-compressible.txt", seed * 4096)

    with pytest.raises(IngestionError) as captured:
        with discover_inputs((archive_path,)):
            pass

    assert captured.value.code == expected_code
