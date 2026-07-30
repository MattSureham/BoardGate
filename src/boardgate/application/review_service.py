"""Complete deterministic review pipeline and atomic artifact publication."""

from __future__ import annotations

import math
import secrets
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from pathlib import Path

from boardgate.agent import (
    DeterministicNarrativeProvider,
    DeterministicOrchestrator,
    NarrativeProvider,
    PresentationView,
    ReviewPlan,
    RulePlanDisposition,
    compose_narrative_report,
)
from boardgate.application.artifacts import (
    COMPLETE_ARTIFACT_PATHS,
    CompleteArtifactBundle,
    RunLogEvent,
    RunLogLevel,
    build_analysis_unavailable_review,
    build_complete_artifact_bundle,
    validate_artifact_bundle,
)
from boardgate.application.output import (
    OutputError,
    OutputTransaction,
    preflight_output,
)
from boardgate.application.project_builder import (
    ProjectBuildError,
    build_evidence_only_project,
    build_project,
)
from boardgate.application.rule_runner import run_rule_evaluation
from boardgate.config.models import RuleProfile
from boardgate.domain.diagnostic import (
    AnalysisDiagnostic,
    AnalysisDiagnosticCategory,
    AnalysisStage,
)
from boardgate.domain.enums import ReviewStatus, Severity
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.ingestion.discovery import DiscoveredProject
from boardgate.rendering import render_svg
from boardgate.rules import ReviewResult
from boardgate.rules.builtin import build_builtin_registry

type ProjectBuilder = Callable[
    [DiscoveredProject, ProjectManifest, RuleProfile],
    PCBProject,
]
type RuleEvaluator = Callable[[PCBProject, RuleProfile], ReviewResult]
type ReportComposer = Callable[[PCBProject, ReviewResult], str]
type SvgRenderer = Callable[[PCBProject, ReviewResult], str]
type Clock = Callable[[], datetime]
type MonotonicClock = Callable[[], float]
type RunIdFactory = Callable[[], str]

_PARSER_FILE_TYPES = frozenset(
    {"gerber", "excellon", "bom_csv", "bom_xlsx", "placement_csv"}
)
_DEFAULT_NARRATIVE_PROVIDER: NarrativeProvider = DeterministicNarrativeProvider()


class ReviewExitCode(IntEnum):
    """Normative process result after application-layer review handling."""

    SUCCESS = 0
    BLOCKER = 1
    USER_INPUT = 2
    PIPELINE = 3
    INTERNAL = 4


class FailOn(StrEnum):
    """Completed-review threshold requested by the CLI caller."""

    NONE = "none"
    BLOCKER = "blocker"


@dataclass(frozen=True, slots=True)
class ReviewRun:
    """Published review outcome returned to transport adapters."""

    project_id: str
    overall_status: ReviewStatus
    exit_code: ReviewExitCode
    output_path: Path
    fallback_used: bool
    artifact_paths: tuple[str, ...] = COMPLETE_ARTIFACT_PATHS


class ReviewPublicationError(ValueError):
    """Sanitized terminal failure when no new trustworthy bundle was published."""

    def __init__(self, code: str, summary: str) -> None:
        self.code = code
        self.summary = summary
        super().__init__(f"{code}: {summary}")


@dataclass(frozen=True, slots=True)
class _PipelineUnavailableError(Exception):
    diagnostic: AnalysisDiagnostic


@dataclass(slots=True)
class _RunJournal:
    run_id: str
    project_id: str
    clock: Clock
    monotonic_clock: MonotonicClock
    started_at: float
    events: list[RunLogEvent] = field(default_factory=list)

    def record(  # noqa: PLR0913
        self,
        *,
        level: RunLogLevel,
        category: AnalysisDiagnosticCategory,
        stage: AnalysisStage,
        code: str,
        summary: str,
        input_file_count: int | None = None,
        file_classification_counts: dict[str, int] | None = None,
        selected_parsers: tuple[str, ...] = (),
        primitive_count: int | None = None,
        drill_count: int | None = None,
        executed_rules: tuple[str, ...] = (),
        skipped_rule_reasons: dict[str, str] | None = None,
        finding_count: int | None = None,
        error_type: str | None = None,
    ) -> None:
        occurred_at = self.clock()
        elapsed_ms = max(
            0,
            round((self.monotonic_clock() - self.started_at) * 1000.0),
        )
        self.events.append(
            RunLogEvent(
                run_id=self.run_id,
                project_id=self.project_id,
                sequence=len(self.events) + 1,
                occurred_at=occurred_at,
                elapsed_ms=elapsed_ms,
                level=level,
                category=category,
                stage=stage,
                code=code,
                summary=summary,
                input_file_count=input_file_count,
                file_classification_counts=file_classification_counts or {},
                selected_parsers=selected_parsers,
                primitive_count=primitive_count,
                drill_count=drill_count,
                executed_rules=executed_rules,
                skipped_rule_reasons=skipped_rule_reasons or {},
                finding_count=finding_count,
                error_type=error_type,
            )
        )


def _default_run_id() -> str:
    return f"run-{secrets.token_hex(8)}"


def _classification_counts(manifest: ProjectManifest) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in manifest.source_files:
        key = source.file_type.value
        counts[key] = counts.get(key, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def _selected_parsers(manifest: ProjectManifest) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                source.file_type.value
                for source in manifest.source_files
                if source.file_type.value in _PARSER_FILE_TYPES
            }
        )
    )


def reject_output_input_overlap(inputs: Sequence[Path], output: Path) -> None:
    """Reject publication that could consume or replace a protected input."""
    output_resolved = output.resolve()
    for input_path in inputs:
        try:
            input_resolved = input_path.resolve()
        except OSError:
            continue
        output_inside_directory_input = input_path.is_dir() and (
            output_resolved == input_resolved
            or output_resolved.is_relative_to(input_resolved)
        )
        input_inside_output = input_resolved == output_resolved or (
            input_resolved.is_relative_to(output_resolved)
        )
        if output_inside_directory_input or input_inside_output:
            raise OutputError(
                "OUTPUT_OVERLAPS_INPUT",
                output.name or "<output>",
                "output and protected input paths must not contain one another",
            )


def _pipeline_failure(
    *,
    stage: AnalysisStage,
    code: str,
    summary: str,
    category: AnalysisDiagnosticCategory = AnalysisDiagnosticCategory.ANALYSIS,
) -> _PipelineUnavailableError:
    return _PipelineUnavailableError(
        AnalysisDiagnostic(
            category=category,
            stage=stage,
            code=code,
            summary=summary,
        )
    )


def _emergency_report(project: PCBProject, review: ReviewResult) -> str:
    diagnostics = "\n".join(
        (
            f"- {diagnostic.category.value}/{diagnostic.stage.value}/"
            f"{diagnostic.code}: {diagnostic.summary}"
        )
        for diagnostic in review.analysis_diagnostics
    )
    sections = (
        "# PCB Manufacturing Review",
        f"<!-- boardgate-project-id: {project.project_id} -->",
        f"<!-- boardgate-profile-sha256: {review.profile_sha256} -->",
        "## Executive Summary",
        f"- Overall status: **{review.overall_status.value}**",
        f"- Project ID: {project.project_id}",
        diagnostics or "- No analysis diagnostic was available.",
        "## Input Files",
        f"- Safely ingested files: {len(project.source_files)}",
        "## Project Interpretation",
        "- Normalized project analysis is unavailable.",
        "## Blockers",
        "No normal rule Findings were published.",
        "## High-Risk Findings",
        "No normal rule Findings were published.",
        "## Requires Human Confirmation",
        "- Review the analysis diagnostics before using this project.",
        "## Optimization Suggestions",
        "No optimization suggestion is available.",
        "## Rules Executed",
        "No rule result was published.",
        "## Rules Not Executed",
        "Normal rule execution is unavailable.",
        "## Parser and Analysis Limitations",
        diagnostics or "- Analysis is unavailable.",
        "## Evidence Index",
        "The manifest and project envelope retain the safely ingested inventory.",
        "## Disclaimer",
        review.disclaimer,
        "",
    )
    return "\n\n".join(sections)


def _emergency_svg(project: PCBProject) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        'viewBox="0 0 640 120" role="img" '
        f'data-project-id="{project.project_id}" '
        f'data-profile-sha256="{project.fabrication_requirements.profile_sha256}" '
        'aria-labelledby="boardgate-title boardgate-description">\n'
        '  <title id="boardgate-title">BoardGate analysis unavailable</title>\n'
        '  <desc id="boardgate-description">No trustworthy geometry preview '
        f"is available for project {project.project_id}.</desc>\n"
        '  <rect x="0" y="0" width="640" height="120" fill="#ffffff"/>\n'
        '  <text x="24" y="54" font-family="sans-serif" font-size="18" '
        'fill="#7a271a">Analysis unavailable</text>\n'
        '  <text x="24" y="84" font-family="monospace" font-size="12" '
        f'fill="#344054">{project.project_id}</text>\n'
        "</svg>\n"
    )


def _staged_bundle(staging: Path) -> CompleteArtifactBundle:
    files: dict[str, str] = {}
    actual_files = tuple(
        sorted(
            path.relative_to(staging).as_posix()
            for path in staging.rglob("*")
            if path.is_file()
        )
    )
    if actual_files != tuple(sorted(COMPLETE_ARTIFACT_PATHS)):
        raise OutputError(
            "OUTPUT_INVENTORY_MISMATCH",
            staging.name,
            "staged output does not contain exactly the six required artifacts",
        )
    for logical_path in COMPLETE_ARTIFACT_PATHS:
        files[logical_path] = (staging / logical_path).read_text(encoding="utf-8")
    return CompleteArtifactBundle.from_files(files)


def _validate_staged_bundle(staging: Path) -> None:
    validate_artifact_bundle(_staged_bundle(staging))


def _publish_bundle(
    bundle: CompleteArtifactBundle,
    output_path: Path,
    *,
    overwrite: bool,
) -> None:
    try:
        with OutputTransaction(output_path, overwrite=overwrite) as transaction:
            staging = transaction.staging_directory
            for logical_path, payload in bundle.as_files().items():
                destination = staging / logical_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(payload, encoding="utf-8", newline="\n")
            transaction.commit(
                required_files=COMPLETE_ARTIFACT_PATHS,
                validator=_validate_staged_bundle,
            )
    except (OSError, OutputError) as error:
        raise ReviewPublicationError(
            "REVIEW_PUBLICATION_FAILED",
            "The complete review bundle could not be published.",
        ) from error


class ReviewService:
    """Connect safe ingestion, deterministic analysis, and artifact publication."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        project_builder: ProjectBuilder | None = None,
        rule_evaluator: RuleEvaluator | None = None,
        report_composer: ReportComposer | None = None,
        narrative_provider: NarrativeProvider | None = _DEFAULT_NARRATIVE_PROVIDER,
        svg_renderer: SvgRenderer = render_svg,
        clock: Clock = lambda: datetime.now(UTC),
        monotonic_clock: MonotonicClock = time.monotonic,
        deadline_clock: MonotonicClock = time.monotonic,
        run_id_factory: RunIdFactory = _default_run_id,
        total_timeout_seconds: float = 300.0,
    ) -> None:
        if not math.isfinite(total_timeout_seconds) or total_timeout_seconds <= 0.0:
            raise ValueError("total timeout must be a positive finite number")
        self._project_builder = project_builder
        self._rule_evaluator = rule_evaluator
        self._report_composer = report_composer
        self._narrative_provider = narrative_provider
        self._svg_renderer = svg_renderer
        self._registry = build_builtin_registry(require_complete=True)
        self._orchestrator = DeterministicOrchestrator(self._registry)
        self._clock = clock
        self._monotonic_clock = monotonic_clock
        self._deadline_clock = deadline_clock
        self._run_id_factory = run_id_factory
        self._total_timeout_seconds = total_timeout_seconds

    def inspect(
        self,
        inputs: Sequence[Path],
        profile: RuleProfile,
        output_path: Path,
        *,
        overwrite: bool = False,
        fail_on: FailOn = FailOn.NONE,
    ) -> ReviewRun:
        """Run and publish one complete review, including post-ingestion fallback."""
        deadline = self._deadline_clock() + self._total_timeout_seconds
        preflight_output(output_path, overwrite=overwrite)
        reject_output_input_overlap(inputs, output_path)
        with discover_inputs(inputs) as discovered:
            manifest = build_manifest(discovered)
            journal_creation_failed = False
            try:
                journal = _RunJournal(
                    run_id=self._run_id_factory(),
                    project_id=manifest.project_id,
                    clock=self._clock,
                    monotonic_clock=self._monotonic_clock,
                    started_at=self._monotonic_clock(),
                )
            except Exception:
                journal = _RunJournal(
                    run_id=_default_run_id(),
                    project_id=manifest.project_id,
                    clock=lambda: datetime.now(UTC),
                    monotonic_clock=time.monotonic,
                    started_at=time.monotonic(),
                )
                journal_creation_failed = True
            project: PCBProject | None = None
            try:
                if journal_creation_failed:
                    raise RuntimeError
                journal.record(
                    level=RunLogLevel.INFO,
                    category=AnalysisDiagnosticCategory.INPUT,
                    stage=AnalysisStage.INGESTION,
                    code="INGESTION_COMPLETED",
                    summary="Safe ingestion and manifest construction completed.",
                    input_file_count=len(manifest.source_files),
                    file_classification_counts=_classification_counts(manifest),
                    selected_parsers=_selected_parsers(manifest),
                )
                plan = self._plan_review(manifest, profile)
                selected_parsers = tuple(
                    task.parser_id.value for task in plan.parser_tasks
                )
                journal.record(
                    level=RunLogLevel.INFO,
                    category=AnalysisDiagnosticCategory.ANALYSIS,
                    stage=AnalysisStage.AGENT_ORCHESTRATION,
                    code="REVIEW_PLAN_COMPLETED",
                    summary="The deterministic parser and rule plan was created.",
                    selected_parsers=selected_parsers,
                )
                project = self._build_project(
                    discovered,
                    manifest,
                    profile,
                    plan=plan,
                    deadline=deadline,
                )
                self._require_time(deadline, AnalysisStage.PROJECT_CONSTRUCTION)
                journal.record(
                    level=RunLogLevel.INFO,
                    category=AnalysisDiagnosticCategory.ANALYSIS,
                    stage=AnalysisStage.PROJECT_CONSTRUCTION,
                    code="PROJECT_CONSTRUCTION_COMPLETED",
                    summary="Project parsing and normalization completed.",
                    selected_parsers=selected_parsers,
                    primitive_count=sum(
                        len(layer.primitives) for layer in project.layers
                    ),
                    drill_count=len(project.drills) + len(project.drill_slots),
                )
                review = self._evaluate_rules(
                    project,
                    profile,
                    plan,
                    deadline=deadline,
                )
                self._require_time(deadline, AnalysisStage.RULE_EXECUTION)
                journal.record(
                    level=RunLogLevel.INFO,
                    category=AnalysisDiagnosticCategory.ANALYSIS,
                    stage=AnalysisStage.RULE_EXECUTION,
                    code="RULE_EXECUTION_COMPLETED",
                    summary="Deterministic rule execution completed.",
                    executed_rules=tuple(
                        sorted(
                            result.rule_id.value
                            for result in review.rule_results
                            if result.outcome.value in {"PASS", "FINDINGS"}
                        )
                    ),
                    skipped_rule_reasons={
                        result.rule_id.value: result.reason.value
                        for result in sorted(
                            review.rule_results,
                            key=lambda item: item.rule_id.value,
                        )
                        if result.reason is not None
                    },
                    finding_count=len(review.findings),
                )
                presentation = self._organize_review(plan, review)
                report = self._compose_report(project, review, presentation)
                self._require_time(deadline, AnalysisStage.REPORT_COMPOSITION)
                journal.record(
                    level=RunLogLevel.INFO,
                    category=AnalysisDiagnosticCategory.OUTPUT,
                    stage=AnalysisStage.REPORT_COMPOSITION,
                    code="REPORT_COMPOSITION_COMPLETED",
                    summary="The deterministic Markdown report was composed.",
                    finding_count=len(review.findings),
                )
                preview = self._render_preview(project, review)
                self._require_time(deadline, AnalysisStage.SVG_RENDERING)
                journal.record(
                    level=RunLogLevel.INFO,
                    category=AnalysisDiagnosticCategory.OUTPUT,
                    stage=AnalysisStage.SVG_RENDERING,
                    code="SVG_RENDERING_COMPLETED",
                    summary="The deterministic SVG preview was rendered.",
                    finding_count=len(review.findings),
                )
                journal.record(
                    level=RunLogLevel.INFO,
                    category=AnalysisDiagnosticCategory.OUTPUT,
                    stage=AnalysisStage.ARTIFACT_VALIDATION,
                    code="REVIEW_ARTIFACTS_READY",
                    summary="The complete review bundle is ready for validation.",
                    finding_count=len(review.findings),
                )
                bundle = self._build_bundle(
                    manifest=manifest,
                    project=project,
                    review=review,
                    report=report,
                    preview=preview,
                    journal=journal,
                )
                fallback_used = False
                exit_code = self._completed_exit_code(review, fail_on)
            except _PipelineUnavailableError as error:
                project, review, bundle = self._fallback_bundle(
                    manifest=manifest,
                    profile=profile,
                    last_project=project,
                    failure=error,
                    journal=journal,
                )
                fallback_used = True
                exit_code = ReviewExitCode.PIPELINE
            except Exception:
                internal_failure = _pipeline_failure(
                    stage=AnalysisStage.ARTIFACT_VALIDATION,
                    code="INTERNAL_REVIEW_ERROR",
                    summary="An unexpected internal review error occurred.",
                    category=AnalysisDiagnosticCategory.INTERNAL,
                )
                project, review, bundle = self._fallback_bundle(
                    manifest=manifest,
                    profile=profile,
                    last_project=project,
                    failure=internal_failure,
                    journal=journal,
                )
                fallback_used = True
                exit_code = ReviewExitCode.INTERNAL

            _publish_bundle(bundle, output_path, overwrite=overwrite)
            return ReviewRun(
                project_id=project.project_id,
                overall_status=review.overall_status,
                exit_code=exit_code,
                output_path=output_path,
                fallback_used=fallback_used,
            )

    def _build_project(
        self,
        discovered: DiscoveredProject,
        manifest: ProjectManifest,
        profile: RuleProfile,
        *,
        plan: ReviewPlan,
        deadline: float,
    ) -> PCBProject:
        try:
            remaining = deadline - self._deadline_clock()
            if remaining <= 0.0:
                raise _pipeline_failure(
                    stage=AnalysisStage.PROJECT_CONSTRUCTION,
                    code="REVIEW_TIMEOUT",
                    summary="The review exceeded the total runtime limit.",
                )
            if self._project_builder is not None:
                return self._project_builder(discovered, manifest, profile)
            return build_project(
                discovered,
                manifest,
                profile,
                total_timeout_seconds=remaining,
                monotonic_clock=self._deadline_clock,
                selected_source_file_ids=frozenset(
                    source_file_id
                    for task in plan.parser_tasks
                    for source_file_id in task.source_file_ids
                ),
            )
        except _PipelineUnavailableError:
            raise
        except ProjectBuildError as error:
            if error.code == "PROJECT_TIMEOUT":
                raise _pipeline_failure(
                    stage=AnalysisStage.PROJECT_CONSTRUCTION,
                    code="REVIEW_TIMEOUT",
                    summary="The review exceeded the total runtime limit.",
                ) from error
            raise _pipeline_failure(
                stage=AnalysisStage.PROJECT_CONSTRUCTION,
                code="PROJECT_CONSTRUCTION_FAILED",
                summary="Project parsing or normalization did not complete.",
            ) from error
        except Exception as error:
            raise _pipeline_failure(
                stage=AnalysisStage.PROJECT_CONSTRUCTION,
                code="PROJECT_CONSTRUCTION_FAILED",
                summary="Project parsing or normalization did not complete.",
            ) from error

    def _require_time(
        self,
        deadline: float,
        stage: AnalysisStage,
    ) -> None:
        if self._deadline_clock() >= deadline:
            raise _pipeline_failure(
                stage=stage,
                code="REVIEW_TIMEOUT",
                summary="The review exceeded the total runtime limit.",
            )

    def _evaluate_rules(
        self,
        project: PCBProject,
        profile: RuleProfile,
        plan: ReviewPlan,
        *,
        deadline: float,
    ) -> ReviewResult:
        try:
            if self._rule_evaluator is not None:
                return self._rule_evaluator(project, profile)
            selected_rule_ids = frozenset(
                task.rule_id
                for task in plan.rule_tasks
                if task.disposition is RulePlanDisposition.EXECUTE
            )
            execution = run_rule_evaluation(
                project,
                profile,
                selected_rule_ids=selected_rule_ids,
                deadline=deadline,
                monotonic_clock=self._deadline_clock,
            )
            if execution.failure is not None:
                raise _pipeline_failure(
                    stage=AnalysisStage.RULE_EXECUTION,
                    code=execution.failure.code,
                    summary=("The isolated deterministic rule stage did not complete."),
                )
            if execution.result is None:  # pragma: no cover - dataclass invariant
                raise RuntimeError("isolated rule stage omitted its result")
            return execution.result
        except _PipelineUnavailableError:
            raise
        except Exception as error:
            raise _pipeline_failure(
                stage=AnalysisStage.RULE_EXECUTION,
                code="RULE_EXECUTION_FAILED",
                summary="Deterministic rule execution did not complete.",
            ) from error

    def _plan_review(
        self,
        manifest: ProjectManifest,
        profile: RuleProfile,
    ) -> ReviewPlan:
        try:
            return self._orchestrator.plan(manifest, profile)
        except Exception as error:
            raise _pipeline_failure(
                stage=AnalysisStage.AGENT_ORCHESTRATION,
                code="AGENT_PLAN_FAILED",
                summary="The deterministic review plan could not be created.",
            ) from error

    def _organize_review(
        self,
        plan: ReviewPlan,
        review: ReviewResult,
    ) -> PresentationView:
        try:
            orchestrated = self._orchestrator.organize(plan, review)
            if orchestrated.raw_review is not review:
                raise ValueError("orchestrator replaced the raw review")
            return orchestrated.presentation
        except Exception as error:
            raise _pipeline_failure(
                stage=AnalysisStage.AGENT_ORCHESTRATION,
                code="AGENT_PRESENTATION_FAILED",
                summary="The deterministic review presentation could not be organized.",
            ) from error

    def _compose_report(
        self,
        project: PCBProject,
        review: ReviewResult,
        presentation: PresentationView,
    ) -> str:
        try:
            if self._report_composer is not None:
                return self._report_composer(project, review)
            return compose_narrative_report(
                project,
                review,
                presentation,
                self._narrative_provider,
            )
        except Exception as error:
            raise _pipeline_failure(
                stage=AnalysisStage.REPORT_COMPOSITION,
                code="REPORT_COMPOSITION_FAILED",
                summary="The deterministic Markdown report could not be composed.",
                category=AnalysisDiagnosticCategory.OUTPUT,
            ) from error

    def _render_preview(
        self,
        project: PCBProject,
        review: ReviewResult,
    ) -> str:
        try:
            return self._svg_renderer(project, review)
        except Exception as error:
            raise _pipeline_failure(
                stage=AnalysisStage.SVG_RENDERING,
                code="SVG_RENDERING_FAILED",
                summary="The deterministic SVG preview could not be rendered.",
                category=AnalysisDiagnosticCategory.OUTPUT,
            ) from error

    @staticmethod
    def _build_bundle(  # noqa: PLR0913
        *,
        manifest: ProjectManifest,
        project: PCBProject,
        review: ReviewResult,
        report: str,
        preview: str,
        journal: _RunJournal,
    ) -> CompleteArtifactBundle:
        try:
            return build_complete_artifact_bundle(
                manifest=manifest,
                project=project,
                review=review,
                report_markdown=report,
                preview_svg=preview,
                run_events=journal.events,
            )
        except Exception as error:
            raise _pipeline_failure(
                stage=AnalysisStage.ARTIFACT_VALIDATION,
                code="ARTIFACT_VALIDATION_FAILED",
                summary="The complete review bundle did not pass validation.",
                category=AnalysisDiagnosticCategory.OUTPUT,
            ) from error

    @staticmethod
    def _fallback_bundle(
        *,
        manifest: ProjectManifest,
        profile: RuleProfile,
        last_project: PCBProject | None,
        failure: _PipelineUnavailableError,
        journal: _RunJournal,
    ) -> tuple[PCBProject, ReviewResult, CompleteArtifactBundle]:
        try:
            project = last_project or build_evidence_only_project(manifest, profile)
            review = build_analysis_unavailable_review(
                project_id=project.project_id,
                profile_id=project.fabrication_requirements.profile_id,
                profile_sha256=project.fabrication_requirements.profile_sha256,
                diagnostics=(failure.diagnostic,),
            )
            journal.record(
                level=RunLogLevel.ERROR,
                category=failure.diagnostic.category,
                stage=failure.diagnostic.stage,
                code=failure.diagnostic.code,
                summary=failure.diagnostic.summary,
                error_type=failure.diagnostic.code,
            )
            journal.record(
                level=RunLogLevel.WARNING,
                category=AnalysisDiagnosticCategory.OUTPUT,
                stage=AnalysisStage.ARTIFACT_VALIDATION,
                code="ANALYSIS_FALLBACK_READY",
                summary="A diagnostic analysis-unavailable bundle is ready.",
            )
            bundle = build_complete_artifact_bundle(
                manifest=manifest,
                project=project,
                review=review,
                report_markdown=_emergency_report(project, review),
                preview_svg=_emergency_svg(project),
                run_events=journal.events,
            )
        except Exception as error:
            raise ReviewPublicationError(
                "ANALYSIS_FALLBACK_FAILED",
                "A trustworthy diagnostic fallback bundle could not be built.",
            ) from error
        return project, review, bundle

    @staticmethod
    def _completed_exit_code(
        review: ReviewResult,
        fail_on: FailOn,
    ) -> ReviewExitCode:
        if fail_on is FailOn.BLOCKER and any(
            result.affects_readiness
            and finding.severity is Severity.BLOCKER
            and not finding.requires_human_confirmation
            for result in review.rule_results
            for finding in result.findings
        ):
            return ReviewExitCode.BLOCKER
        return ReviewExitCode.SUCCESS
