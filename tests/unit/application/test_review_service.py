"""End-to-end application-service publication and recovery tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Never

import pytest

import boardgate.application.review_service as review_service_module
from boardgate.application.artifacts import (
    COMPLETE_ARTIFACT_PATHS,
    DETERMINISTIC_ARTIFACT_PATHS,
    RUN_LOG_PATH,
    CompleteArtifactBundle,
    parse_run_log,
    validate_artifact_bundle,
)
from boardgate.application.output import OutputError
from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
    parse_job,
)
from boardgate.application.project_builder import (
    build_evidence_only_project,
    build_project,
)
from boardgate.application.review_service import (
    FailOn,
    ReviewExitCode,
    ReviewPublicationError,
    ReviewService,
)
from boardgate.config import load_rule_profile, profile_hash
from boardgate.config.models import RuleProfile
from boardgate.domain.diagnostic import AnalysisDiagnosticCategory, AnalysisStage
from boardgate.domain.enums import ReviewStatus, Severity
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.ingestion.discovery import DiscoveredProject
from boardgate.parsers import ParserError
from boardgate.reporting import compose_markdown_report
from boardgate.rules import ReviewResult, RuleEngine
from boardgate.rules.builtin import build_builtin_registry

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
PROFILE_PATH = Path("rules/default.yaml")
VALID_PROJECT = FIXTURES / "valid_minimal_board"
FIRST_RUN_ID = "run-0123456789abcdef"
SECOND_RUN_ID = "run-fedcba9876543210"
FIXED_TIME = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


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


def _inline_project_builder(
    discovered: DiscoveredProject,
    manifest: ProjectManifest,
    profile: RuleProfile,
) -> PCBProject:
    return build_project(
        discovered,
        manifest,
        profile,
        parser_executor=_inline_executor,
    )


def _evidence_project_builder(
    discovered: DiscoveredProject,
    manifest: ProjectManifest,
    profile: RuleProfile,
) -> PCBProject:
    del discovered
    return build_evidence_only_project(manifest, profile)


def _evaluate_rules(project: PCBProject, profile: RuleProfile) -> ReviewResult:
    return RuleEngine(build_builtin_registry(require_complete=True)).evaluate(
        project,
        profile,
    )


def _artifact_files(output: Path) -> dict[str, bytes]:
    return {
        logical_path: (output / logical_path).read_bytes()
        for logical_path in COMPLETE_ARTIFACT_PATHS
    }


def _artifact_bundle(output: Path) -> CompleteArtifactBundle:
    return CompleteArtifactBundle.from_files(
        {
            logical_path: (output / logical_path).read_text(encoding="utf-8")
            for logical_path in COMPLETE_ARTIFACT_PATHS
        }
    )


def _published_inventory(output: Path) -> tuple[str, ...]:
    return tuple(
        sorted(
            path.relative_to(output).as_posix()
            for path in output.rglob("*")
            if path.is_file()
        )
    )


def _fixed_service(
    *,
    run_id_factory: Callable[[], str],
    profile_builder: Callable[
        [DiscoveredProject, ProjectManifest, RuleProfile],
        PCBProject,
    ] = _inline_project_builder,
) -> ReviewService:
    return ReviewService(
        project_builder=profile_builder,
        clock=lambda: FIXED_TIME,
        monotonic_clock=lambda: 100.0,
        run_id_factory=run_id_factory,
    )


def _raise_secret_error(*args: object, **kwargs: object) -> Never:
    del args, kwargs
    raise RuntimeError(
        "RuntimeError: failed at /private/boardgate/customer-secret.gbr "
        "with object at 0x12345678"
    )


def _fixed_clock() -> datetime:
    return FIXED_TIME


def _fixed_monotonic_clock() -> float:
    return 100.0


def _first_run_id() -> str:
    return FIRST_RUN_ID


def test_review_service_publishes_exact_six_artifacts_with_stable_review_bytes(
    tmp_path: Path,
) -> None:
    run_ids = iter((FIRST_RUN_ID, SECOND_RUN_ID))
    service = _fixed_service(run_id_factory=lambda: next(run_ids))
    profile = load_rule_profile(PROFILE_PATH)
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"

    first = service.inspect((VALID_PROJECT,), profile, first_output)
    second = service.inspect((VALID_PROJECT,), profile, second_output)

    assert first.exit_code is ReviewExitCode.SUCCESS
    assert second.exit_code is ReviewExitCode.SUCCESS
    assert first.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert second.overall_status is ReviewStatus.READY_FOR_REVIEW
    assert not first.fallback_used
    assert not second.fallback_used
    assert first.artifact_paths == COMPLETE_ARTIFACT_PATHS
    assert _published_inventory(first_output) == tuple(sorted(COMPLETE_ARTIFACT_PATHS))
    assert _published_inventory(second_output) == tuple(sorted(COMPLETE_ARTIFACT_PATHS))

    first_files = _artifact_files(first_output)
    second_files = _artifact_files(second_output)
    assert {path: first_files[path] for path in DETERMINISTIC_ARTIFACT_PATHS} == {
        path: second_files[path] for path in DETERMINISTIC_ARTIFACT_PATHS
    }
    assert first_files[RUN_LOG_PATH] != second_files[RUN_LOG_PATH]

    first_validation = validate_artifact_bundle(_artifact_bundle(first_output))
    second_validation = validate_artifact_bundle(_artifact_bundle(second_output))
    assert {event.run_id for event in first_validation.run_events} == {FIRST_RUN_ID}
    assert {event.run_id for event in second_validation.run_events} == {SECOND_RUN_ID}
    assert tuple(event.sequence for event in first_validation.run_events) == tuple(
        range(1, len(first_validation.run_events) + 1)
    )
    assert all(
        event.project_id == first_validation.project.project_id
        for event in first_validation.run_events
    )
    ingestion_event = first_validation.run_events[0]
    assert ingestion_event.code == "INGESTION_COMPLETED"
    assert ingestion_event.input_file_count == 4
    assert ingestion_event.file_classification_counts == {
        "excellon": 1,
        "gerber": 3,
    }
    assert ingestion_event.selected_parsers == ("excellon", "gerber")
    rule_event = next(
        event
        for event in first_validation.run_events
        if event.code == "RULE_EXECUTION_COMPLETED"
    )
    assert rule_event.finding_count == 0
    assert "minimum_trace_width" in rule_event.executed_rules
    assert (
        rule_event.skipped_rule_reasons["silkscreen_over_exposed_pad"]
        == "NOT_APPLICABLE"
    )


def test_fail_on_blocker_changes_only_exit_code_not_review_artifacts(
    tmp_path: Path,
) -> None:
    base_profile = load_rule_profile(PROFILE_PATH)
    profile = base_profile.model_copy(
        update={
            "fabrication": base_profile.fabrication.model_copy(
                update={"min_trace_width": 0.4}
            )
        }
    )
    run_ids = iter((FIRST_RUN_ID, SECOND_RUN_ID))
    service = _fixed_service(run_id_factory=lambda: next(run_ids))
    none_output = tmp_path / "none"
    blocker_output = tmp_path / "blocker"

    none_result = service.inspect(
        (VALID_PROJECT,),
        profile,
        none_output,
        fail_on=FailOn.NONE,
    )
    blocker_result = service.inspect(
        (VALID_PROJECT,),
        profile,
        blocker_output,
        fail_on=FailOn.BLOCKER,
    )

    review = validate_artifact_bundle(_artifact_bundle(blocker_output)).review
    assert review.overall_status is ReviewStatus.NOT_READY_FOR_FABRICATION
    assert any(
        finding.severity is Severity.BLOCKER and not finding.requires_human_confirmation
        for finding in review.findings
    )
    assert none_result.exit_code is ReviewExitCode.SUCCESS
    assert blocker_result.exit_code is ReviewExitCode.BLOCKER
    assert {
        path: _artifact_files(none_output)[path]
        for path in DETERMINISTIC_ARTIFACT_PATHS
    } == {
        path: _artifact_files(blocker_output)[path]
        for path in DETERMINISTIC_ARTIFACT_PATHS
    }


@pytest.mark.parametrize(
    ("failed_stage", "expected_stage", "expected_code"),
    (
        (
            "project",
            AnalysisStage.PROJECT_CONSTRUCTION,
            "PROJECT_CONSTRUCTION_FAILED",
        ),
        ("rules", AnalysisStage.RULE_EXECUTION, "RULE_EXECUTION_FAILED"),
        (
            "report",
            AnalysisStage.REPORT_COMPOSITION,
            "REPORT_COMPOSITION_FAILED",
        ),
        ("svg", AnalysisStage.SVG_RENDERING, "SVG_RENDERING_FAILED"),
        (
            "artifact",
            AnalysisStage.ARTIFACT_VALIDATION,
            "ARTIFACT_VALIDATION_FAILED",
        ),
    ),
)
def test_stage_failures_publish_sanitized_analysis_failed_bundle(
    tmp_path: Path,
    failed_stage: str,
    expected_stage: AnalysisStage,
    expected_code: str,
) -> None:
    profile = load_rule_profile(PROFILE_PATH)
    if failed_stage == "project":

        def failing_builder(
            discovered: DiscoveredProject,
            manifest: ProjectManifest,
            selected_profile: RuleProfile,
        ) -> PCBProject:
            return _raise_secret_error(discovered, manifest, selected_profile)

        service = ReviewService(
            project_builder=failing_builder,
            clock=_fixed_clock,
            monotonic_clock=_fixed_monotonic_clock,
            run_id_factory=_first_run_id,
        )
    elif failed_stage == "rules":

        def failing_evaluator(
            project: PCBProject,
            selected_profile: RuleProfile,
        ) -> ReviewResult:
            return _raise_secret_error(project, selected_profile)

        service = ReviewService(
            project_builder=_inline_project_builder,
            rule_evaluator=failing_evaluator,
            clock=_fixed_clock,
            monotonic_clock=_fixed_monotonic_clock,
            run_id_factory=_first_run_id,
        )
    elif failed_stage == "report":

        def failing_report(
            project: PCBProject,
            review: ReviewResult,
        ) -> str:
            return _raise_secret_error(project, review)

        service = ReviewService(
            project_builder=_inline_project_builder,
            rule_evaluator=_evaluate_rules,
            report_composer=failing_report,
            clock=_fixed_clock,
            monotonic_clock=_fixed_monotonic_clock,
            run_id_factory=_first_run_id,
        )
    elif failed_stage == "svg":

        def failing_svg(
            project: PCBProject,
            review: ReviewResult,
        ) -> str:
            return _raise_secret_error(project, review)

        service = ReviewService(
            project_builder=_inline_project_builder,
            rule_evaluator=_evaluate_rules,
            report_composer=compose_markdown_report,
            svg_renderer=failing_svg,
            clock=_fixed_clock,
            monotonic_clock=_fixed_monotonic_clock,
            run_id_factory=_first_run_id,
        )
    else:

        def unsafe_svg(project: PCBProject, review: ReviewResult) -> str:
            del project, review
            return (
                '<svg xmlns="http://www.w3.org/2000/svg">'
                "<script>unsafe()</script></svg>\n"
            )

        service = ReviewService(
            project_builder=_inline_project_builder,
            rule_evaluator=_evaluate_rules,
            report_composer=compose_markdown_report,
            svg_renderer=unsafe_svg,
            clock=_fixed_clock,
            monotonic_clock=_fixed_monotonic_clock,
            run_id_factory=_first_run_id,
        )

    output = tmp_path / failed_stage
    result = service.inspect((VALID_PROJECT,), profile, output)
    validated = validate_artifact_bundle(_artifact_bundle(output))

    assert result.exit_code is ReviewExitCode.PIPELINE
    assert result.overall_status is ReviewStatus.ANALYSIS_FAILED
    assert result.fallback_used
    assert _published_inventory(output) == tuple(sorted(COMPLETE_ARTIFACT_PATHS))
    assert validated.review.overall_status is ReviewStatus.ANALYSIS_FAILED
    assert not validated.review.findings
    assert not validated.review.rule_results
    assert not validated.review.risk_modes
    assert len(validated.review.analysis_diagnostics) == 1
    diagnostic = validated.review.analysis_diagnostics[0]
    assert diagnostic.stage is expected_stage
    assert diagnostic.code == expected_code
    if failed_stage == "project":
        assert validated.project.metadata["analysis_state"] == "unavailable"
        assert not validated.project.layers
        assert not validated.project.drills
    else:
        assert validated.project.layers

    persisted_text = "\n".join(
        payload.decode("utf-8") for payload in _artifact_files(output).values()
    )
    assert "/private/boardgate/customer-secret.gbr" not in persisted_text
    assert "0x12345678" not in persisted_text
    assert "RuntimeError" not in persisted_text
    assert expected_code in persisted_text


def test_unexpected_post_manifest_error_publishes_internal_fallback(
    tmp_path: Path,
) -> None:
    calls = 0

    def fail_first_journal_timestamp() -> datetime:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _raise_secret_error()
        return FIXED_TIME

    output = tmp_path / "internal"
    result = ReviewService(
        project_builder=_inline_project_builder,
        clock=fail_first_journal_timestamp,
        monotonic_clock=_fixed_monotonic_clock,
        run_id_factory=_first_run_id,
    ).inspect((VALID_PROJECT,), load_rule_profile(PROFILE_PATH), output)
    validated = validate_artifact_bundle(_artifact_bundle(output))

    assert result.exit_code is ReviewExitCode.INTERNAL
    assert result.overall_status is ReviewStatus.ANALYSIS_FAILED
    assert result.fallback_used
    assert not validated.review.findings
    assert not validated.review.rule_results
    assert len(validated.review.analysis_diagnostics) == 1
    diagnostic = validated.review.analysis_diagnostics[0]
    assert diagnostic.category is AnalysisDiagnosticCategory.INTERNAL
    assert diagnostic.code == "INTERNAL_REVIEW_ERROR"
    persisted_text = "\n".join(
        payload.decode("utf-8") for payload in _artifact_files(output).values()
    )
    assert "/private/boardgate/customer-secret.gbr" not in persisted_text
    assert "RuntimeError" not in persisted_text


def test_overwrite_policy_and_validation_failure_preserve_prior_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "review"
    service = _fixed_service(run_id_factory=lambda: FIRST_RUN_ID)
    profile = load_rule_profile(PROFILE_PATH)
    service.inspect((VALID_PROJECT,), profile, output)
    original = _artifact_files(output)

    with pytest.raises(OutputError) as policy_error:
        service.inspect((VALID_PROJECT,), profile, output)

    assert policy_error.value.code == "OUTPUT_NOT_EMPTY"
    assert _artifact_files(output) == original

    def reject_staging(staging: Path) -> None:
        del staging
        raise ValueError("host detail /private/secret should not escape")

    monkeypatch.setattr(
        review_service_module,
        "_validate_staged_bundle",
        reject_staging,
    )
    with pytest.raises(ReviewPublicationError) as publication_error:
        service.inspect(
            (VALID_PROJECT,),
            profile,
            output,
            overwrite=True,
        )

    assert publication_error.value.code == "REVIEW_PUBLICATION_FAILED"
    assert publication_error.value.summary == (
        "The complete review bundle could not be published."
    )
    assert "/private/secret" not in str(publication_error.value)
    assert _artifact_files(output) == original
    assert not tuple(tmp_path.glob(".review.staging-*"))
    assert not tuple(tmp_path.glob(".review.backup-*"))


def test_publication_rejects_an_extra_staged_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_as_files = CompleteArtifactBundle.as_files

    def with_unexpected_file(bundle: CompleteArtifactBundle) -> dict[str, str]:
        files = original_as_files(bundle)
        files["unexpected.txt"] = "must not be published\n"
        return files

    monkeypatch.setattr(CompleteArtifactBundle, "as_files", with_unexpected_file)
    output = tmp_path / "review"
    service = _fixed_service(run_id_factory=lambda: FIRST_RUN_ID)

    with pytest.raises(ReviewPublicationError) as caught:
        service.inspect(
            (VALID_PROJECT,),
            load_rule_profile(PROFILE_PATH),
            output,
        )

    assert caught.value.code == "REVIEW_PUBLICATION_FAILED"
    assert not output.exists()
    assert not tuple(tmp_path.glob(".review.staging-*"))


def test_output_nested_under_input_is_rejected_without_mutating_input(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    original = source / "board.gtl"
    original.write_text("M02*\n", encoding="utf-8")
    service = _fixed_service(
        run_id_factory=lambda: FIRST_RUN_ID,
        profile_builder=_evidence_project_builder,
    )

    with pytest.raises(OutputError) as caught:
        service.inspect(
            (source,),
            load_rule_profile(PROFILE_PATH),
            source / "review",
        )

    assert caught.value.code == "OUTPUT_OVERLAPS_INPUT"
    assert original.read_text(encoding="utf-8") == "M02*\n"
    assert not (source / "review").exists()


def test_build_evidence_only_project_preserves_manifest_and_profile_evidence(
    tmp_path: Path,
) -> None:
    bom = tmp_path / "bom.csv"
    bom.write_text(
        "Reference,Quantity,Value\nR1,1,10k\n",
        encoding="utf-8",
    )
    profile = load_rule_profile(PROFILE_PATH)

    with discover_inputs((bom,)) as discovered:
        manifest = build_manifest(discovered)

    first = build_evidence_only_project(manifest, profile)
    second = build_evidence_only_project(manifest, profile)

    assert first == second
    assert first.project_id == manifest.project_id
    assert first.manifest == manifest
    assert first.source_files == manifest.source_files
    assert first.uncertainties == manifest.uncertainties
    assert first.metadata["analysis_state"] == "unavailable"
    assert first.fabrication_requirements.profile_id == profile.profile.id
    assert first.fabrication_requirements.profile_sha256 == profile_hash(profile)
    assert first.fabrication_requirements.min_trace_width_mm == (
        profile.fabrication.min_trace_width
    )
    assert first.assembly_requirements.review_requested
    assert first.assembly_requirements.ignored_references == (
        profile.policy.ignored_references
    )
    assert first.assembly_requirements.dnp_markers == profile.policy.dnp_markers
    assert not first.layers
    assert first.board_outline is None
    assert not first.drills
    assert not first.drill_slots
    assert not first.components
    assert not first.bom_items
    assert not first.source_diagnostics
    assert PCBProject.model_validate_json(first.model_dump_json()) == first


def test_fallback_run_log_is_ordered_and_contains_only_sanitized_events(
    tmp_path: Path,
) -> None:
    def failing_builder(
        discovered: DiscoveredProject,
        manifest: ProjectManifest,
        profile: RuleProfile,
    ) -> PCBProject:
        return _raise_secret_error(discovered, manifest, profile)

    output = tmp_path / "fallback"
    ReviewService(
        project_builder=failing_builder,
        clock=lambda: FIXED_TIME,
        monotonic_clock=lambda: 100.0,
        run_id_factory=lambda: FIRST_RUN_ID,
    ).inspect((VALID_PROJECT,), load_rule_profile(PROFILE_PATH), output)

    events = parse_run_log((output / RUN_LOG_PATH).read_text(encoding="utf-8"))
    assert tuple(event.sequence for event in events) == (1, 2, 3, 4)
    assert tuple(event.code for event in events) == (
        "INGESTION_COMPLETED",
        "REVIEW_PLAN_COMPLETED",
        "PROJECT_CONSTRUCTION_FAILED",
        "ANALYSIS_FALLBACK_READY",
    )
    serialized = json.dumps(
        [event.model_dump(mode="json") for event in events],
        sort_keys=True,
    )
    assert "/private/" not in serialized
    assert "RuntimeError" not in serialized
