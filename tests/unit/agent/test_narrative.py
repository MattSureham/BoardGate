"""Typed optional narrative-provider tests."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from boardgate.agent import (
    DeterministicNarrativeProvider,
    DeterministicOrchestrator,
    NarrativeItem,
    NarrativeRequest,
    NarrativeResponse,
    NarrativeSection,
    PresentationView,
    compose_narrative_report,
)
from boardgate.config.loader import load_rule_profile
from boardgate.config.models import RuleId, profile_hash
from boardgate.domain.enums import FileType, ReviewStatus, RiskMode, Severity
from boardgate.domain.finding import Finding, FindingEvidence
from boardgate.domain.geometry import CoordinateSystem
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile
from boardgate.reporting import compose_markdown_report
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.models import (
    ReviewResult,
    RuleCoverage,
    RuleOutcome,
    RuleResult,
)

PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _source() -> SourceFile:
    return SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.gtl",
        sha256="b" * 64,
        size_bytes=10,
        file_type=FileType.GERBER,
    )


def _project() -> PCBProject:
    source = _source()
    digest = profile_hash(load_rule_profile(Path("rules/default.yaml")))
    manifest = ProjectManifest(
        project_id=PROJECT_ID,
        source_files=(source,),
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=(source,),
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        fabrication_requirements=FabricationRequirements(
            profile_id="default-prototype-2layer",
            profile_sha256=digest,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _review() -> ReviewResult:
    digest = profile_hash(load_rule_profile(Path("rules/default.yaml")))
    finding = Finding(
        finding_id="fnd-0123456789abcdef",
        rule_id=RuleId.MINIMUM_TRACE_WIDTH.value,
        rule_version="1.0",
        category=RiskMode.GEOMETRY_VIOLATION,
        severity=Severity.BLOCKER,
        confidence=1.0,
        config_path="fabrication.min_trace_width",
        title="Trace < minimum",
        summary="A deterministic width measurement is below the profile.",
        facts=("Measured width is 0.08 mm.", "# This remains a fact."),
        evidence=(
            FindingEvidence(
                provenance=Provenance(
                    source_file_id=SOURCE_ID,
                    parser="test",
                    parser_version="1.0",
                )
            ),
        ),
        suggested_action="Increase the trace width.",
    )
    result = RuleResult(
        rule_id=RuleId.MINIMUM_TRACE_WIDTH,
        rule_version="1.0",
        outcome=RuleOutcome.FINDINGS,
        coverage=RuleCoverage.FULL,
        required=True,
        affects_readiness=True,
        findings=(finding,),
        summary="One narrow trace was found.",
        evaluated_object_count=1,
        applicable_object_count=1,
    )
    return ReviewResult(
        project_id=PROJECT_ID,
        profile_id="default-prototype-2layer",
        profile_sha256=digest,
        overall_status=ReviewStatus.NOT_READY_FOR_FABRICATION,
        rule_results=(result,),
        findings=(finding,),
        risk_modes=(RiskMode.GEOMETRY_VIOLATION,),
        disclaimer="Engineer review required.",
    )


def _presentation() -> tuple[PCBProject, ReviewResult, PresentationView]:
    project = _project()
    review = _review()
    profile = load_rule_profile(Path("rules/default.yaml"))
    orchestrator = DeterministicOrchestrator(build_builtin_registry())
    plan = orchestrator.plan(project.manifest, profile)
    return project, review, orchestrator.organize(plan, review).presentation


class _CallableProvider:
    def __init__(
        self,
        callback: Callable[[NarrativeRequest], Any],
    ) -> None:
        self._callback = callback

    def __call__(self, request: NarrativeRequest) -> NarrativeResponse:
        return cast(NarrativeResponse, self._callback(request))


def test_deterministic_provider_adds_only_existing_evidence() -> None:
    project, review, presentation = _presentation()
    provider = DeterministicNarrativeProvider()

    first = compose_narrative_report(project, review, presentation, provider)
    second = compose_narrative_report(project, review, presentation, provider)
    baseline = compose_markdown_report(project, review)

    assert first == second
    assert first != baseline
    assert "## Agent Evidence Narrative" in first
    assert "fnd-0123456789abcdef" in first
    assert "Measured width is 0\\.08 mm\\." in first
    assert "\\# This remains a fact\\." in first
    assert first.count("## Disclaimer") == 1


def test_none_provider_and_empty_review_return_exact_baseline() -> None:
    project, review, presentation = _presentation()
    baseline = compose_markdown_report(project, review)

    assert compose_narrative_report(project, review, presentation, None) == baseline

    empty_review = ReviewResult(
        project_id=PROJECT_ID,
        profile_id=review.profile_id,
        profile_sha256=review.profile_sha256,
        overall_status=ReviewStatus.READY_FOR_REVIEW,
        rule_results=(),
        disclaimer=review.disclaimer,
    )
    orchestrator = DeterministicOrchestrator(build_builtin_registry())
    plan = orchestrator.plan(
        project.manifest,
        load_rule_profile(Path("rules/default.yaml")),
    )
    empty_presentation = orchestrator.organize(
        plan,
        empty_review,
    ).presentation

    assert compose_narrative_report(
        project,
        empty_review,
        empty_presentation,
        DeterministicNarrativeProvider(),
    ) == compose_markdown_report(project, empty_review)


def test_unknown_finding_id_falls_back_byte_for_byte() -> None:
    project, review, presentation = _presentation()
    baseline = compose_markdown_report(project, review)

    def unknown_finding(request: NarrativeRequest) -> NarrativeResponse:
        valid = DeterministicNarrativeProvider()(request)
        sections = list(valid.sections)
        sections[0] = NarrativeSection(
            kind=sections[0].kind,
            items=(
                NarrativeItem(
                    finding_id="fnd-ffffffffffffffff",
                    fact_indices=(0,),
                ),
            ),
        )
        return valid.model_copy(update={"sections": tuple(sections)})

    report = compose_narrative_report(
        project,
        review,
        presentation,
        _CallableProvider(unknown_finding),
    )

    assert report == baseline
    assert report.encode("utf-8") == baseline.encode("utf-8")


def test_unknown_fact_and_invalid_output_fall_back_exactly() -> None:
    project, review, presentation = _presentation()
    baseline = compose_markdown_report(project, review)

    def unknown_fact(request: NarrativeRequest) -> NarrativeResponse:
        valid = DeterministicNarrativeProvider()(request)
        sections = list(valid.sections)
        sections[0] = NarrativeSection(
            kind=sections[0].kind,
            items=(
                NarrativeItem(
                    finding_id=request.findings[0].finding_id,
                    fact_indices=(99,),
                ),
            ),
        )
        return valid.model_copy(update={"sections": tuple(sections)})

    invalid_provider = _CallableProvider(lambda _request: {"unexpected": True})

    assert (
        compose_narrative_report(
            project,
            review,
            presentation,
            _CallableProvider(unknown_fact),
        )
        == baseline
    )
    assert (
        compose_narrative_report(
            project,
            review,
            presentation,
            invalid_provider,
        )
        == baseline
    )


def test_exception_and_nondeterminism_indicator_fall_back_exactly() -> None:
    project, review, presentation = _presentation()
    baseline = compose_markdown_report(project, review)

    def explode(_request: NarrativeRequest) -> NarrativeResponse:
        raise RuntimeError("provider unavailable")

    def nondeterministic(request: NarrativeRequest) -> NarrativeResponse:
        valid = DeterministicNarrativeProvider()(request)
        return valid.model_copy(update={"deterministic": False})

    for provider in (
        _CallableProvider(explode),
        _CallableProvider(nondeterministic),
    ):
        assert (
            compose_narrative_report(
                project,
                review,
                presentation,
                provider,
            )
            == baseline
        )


def test_request_is_bound_to_exact_baseline_and_existing_facts() -> None:
    project, review, presentation = _presentation()
    baseline = compose_markdown_report(project, review)
    captured: list[NarrativeRequest] = []

    def capture(request: NarrativeRequest) -> NarrativeResponse:
        captured.append(request)
        return DeterministicNarrativeProvider()(request)

    compose_narrative_report(
        project,
        review,
        presentation,
        _CallableProvider(capture),
    )

    assert len(captured) == 1
    request = captured[0]
    assert request.baseline_sha256 == sha256(baseline.encode("utf-8")).hexdigest()
    assert request.findings[0].facts == review.findings[0].facts
    assert request.findings[0].finding_id == review.findings[0].finding_id
