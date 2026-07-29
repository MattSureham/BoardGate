"""Deterministic agent planning and presentation tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.agent import (
    DeterministicOrchestrator,
    ParserId,
    PresentationGroupKind,
    RulePlanDisposition,
    directives_for,
    identify_risk_modes,
    supported_risk_modes,
)
from boardgate.config.loader import load_rule_profile
from boardgate.config.models import RuleId, RuleProfile, profile_hash
from boardgate.domain.enums import (
    FileType,
    ReviewStatus,
    RiskMode,
    Severity,
)
from boardgate.domain.finding import Finding, FindingEvidence
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import (
    ProjectManifest,
    SourceFile,
    Uncertainty,
)
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.models import (
    ReviewResult,
    RuleCoverage,
    RuleOutcome,
    RuleResult,
)

PROJECT_ID = "prj-0123456789abcdef"


def _profile() -> RuleProfile:
    return load_rule_profile(Path("rules/default.yaml"))


def _source(
    suffix: str,
    *,
    path: str,
    file_type: FileType,
) -> SourceFile:
    return SourceFile(
        source_file_id=f"src-{suffix * 16}",
        logical_path=path,
        sha256=suffix * 64,
        size_bytes=10,
        file_type=file_type,
    )


def _manifest() -> ProjectManifest:
    sources = (
        _source("1", path="board.gtl", file_type=FileType.GERBER),
        _source("2", path="board.gbl", file_type=FileType.GERBER),
        _source("3", path="board.drl", file_type=FileType.EXCELLON),
        _source("4", path="bom.csv", file_type=FileType.BOM_CSV),
        _source("5", path="bom.xlsx", file_type=FileType.BOM_XLSX),
        _source("6", path="placement.csv", file_type=FileType.PLACEMENT_CSV),
        _source("7", path="notes.txt", file_type=FileType.UNKNOWN),
        _source("8", path="rules.yaml", file_type=FileType.RULES_YAML),
    )
    return ProjectManifest(
        project_id=PROJECT_ID,
        source_files=sources,
        uncertainties=(
            Uncertainty(
                risk_mode=RiskMode.FILE_TYPE_UNKNOWN,
                subject="notes.txt",
                summary="No supported file type was confirmed.",
            ),
        ),
    )


def _finding(
    suffix: str,
    rule_id: RuleId,
    severity: Severity,
    *,
    confirmation: bool = False,
) -> Finding:
    source_id = "src-" + "1" * 16
    category = (
        RiskMode.DESIGN_INTENT_UNKNOWN if confirmation else RiskMode.GEOMETRY_VIOLATION
    )
    return Finding(
        finding_id=f"fnd-{suffix * 16}",
        rule_id=rule_id.value,
        rule_version="1.0",
        category=category,
        severity=severity,
        confidence=0.9,
        config_path=f"rules.{rule_id.value}",
        title=f"Finding {suffix}",
        summary=f"Summary {suffix}.",
        facts=(f"Fact {suffix}.",),
        evidence=(
            FindingEvidence(
                provenance=Provenance(
                    source_file_id=source_id,
                    parser="test",
                    parser_version="1.0",
                ),
            ),
        ),
        requires_human_confirmation=confirmation,
    )


def _rule_result(rule_id: RuleId, finding: Finding) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_version="1.0",
        outcome=RuleOutcome.FINDINGS,
        coverage=RuleCoverage.FULL,
        required=True,
        affects_readiness=True,
        findings=(finding,),
        summary="One finding was produced.",
        evaluated_object_count=1,
        applicable_object_count=1,
    )


def _review() -> ReviewResult:
    findings = (
        _finding("4", RuleId.MINIMUM_DRILL_DIAMETER, Severity.INFO),
        _finding(
            "3",
            RuleId.MINIMUM_COPPER_TO_EDGE,
            Severity.BLOCKER,
            confirmation=True,
        ),
        _finding("2", RuleId.MINIMUM_COPPER_SPACING, Severity.WARNING),
        _finding("1", RuleId.MINIMUM_TRACE_WIDTH, Severity.BLOCKER),
    )
    results = tuple(
        _rule_result(RuleId(finding.rule_id), finding) for finding in findings
    )
    return ReviewResult(
        project_id=PROJECT_ID,
        profile_id="default-prototype-2layer",
        profile_sha256=profile_hash(_profile()),
        overall_status=ReviewStatus.NOT_READY_FOR_FABRICATION,
        rule_results=results,
        findings=findings,
        risk_modes=(
            RiskMode.DESIGN_INTENT_UNKNOWN,
            RiskMode.GEOMETRY_VIOLATION,
        ),
        disclaimer="Engineer review required.",
    )


def test_plan_is_stable_and_selects_only_supported_source_parsers() -> None:
    orchestrator = DeterministicOrchestrator(build_builtin_registry())
    profile = _profile()

    first = orchestrator.plan(
        _manifest(),
        profile,
        risk_modes=(RiskMode.PARSER_LIMITATION,),
    )
    second = orchestrator.plan(
        _manifest(),
        profile,
        risk_modes=(RiskMode.PARSER_LIMITATION,),
    )

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.profile_sha256 == profile_hash(profile)
    assert tuple(task.parser_id for task in first.parser_tasks) == (
        ParserId.BOM,
        ParserId.EXCELLON,
        ParserId.GERBER,
        ParserId.PLACEMENT,
    )
    assert first.parser_tasks[0].source_file_ids == (
        "src-4444444444444444",
        "src-5555555555555555",
    )
    assert len(first.rule_tasks) == len(RuleId)
    assert all(
        task.disposition is RulePlanDisposition.EXECUTE for task in first.rule_tasks
    )
    assert tuple(item.risk_mode for item in first.risk_directives) == (
        RiskMode.FILE_TYPE_UNKNOWN,
        RiskMode.PARSER_LIMITATION,
    )


def test_plan_marks_profile_disabled_rule_without_deciding_applicability() -> None:
    profile = _profile()
    disabled_setting = profile.rules.minimum_trace_width.model_copy(
        update={"enabled": False}
    )
    settings = profile.rules.model_copy(
        update={"minimum_trace_width": disabled_setting}
    )
    disabled_profile = profile.model_copy(update={"rules": settings})
    orchestrator = DeterministicOrchestrator(build_builtin_registry())

    plan = orchestrator.plan(_manifest(), disabled_profile)
    task = next(
        item for item in plan.rule_tasks if item.rule_id is RuleId.MINIMUM_TRACE_WIDTH
    )

    assert task.disposition is RulePlanDisposition.PROFILE_DISABLED
    assert {item.disposition for item in plan.rule_tasks} == {
        RulePlanDisposition.EXECUTE,
        RulePlanDisposition.PROFILE_DISABLED,
    }


def test_organization_is_a_stable_partition_and_preserves_raw_identity() -> None:
    orchestrator = DeterministicOrchestrator(build_builtin_registry())
    plan = orchestrator.plan(_manifest(), _profile())
    review = _review()

    first = orchestrator.organize(plan, review)
    second = orchestrator.organize(plan, review)

    assert first.raw_review is review
    assert second.raw_review is review
    assert first.presentation == second.presentation
    groups = {group.kind: group.finding_ids for group in first.presentation.groups}
    assert groups == {
        PresentationGroupKind.BLOCKERS: ("fnd-1111111111111111",),
        PresentationGroupKind.HIGH_RISK: ("fnd-2222222222222222",),
        PresentationGroupKind.REQUIRES_HUMAN_CONFIRMATION: ("fnd-3333333333333333",),
        PresentationGroupKind.OPTIMIZATION_SUGGESTIONS: ("fnd-4444444444444444",),
    }
    assert tuple(finding.finding_id for finding in first.raw_review.findings) == tuple(
        finding.finding_id for finding in review.findings
    )
    assert tuple(item.risk_mode for item in first.presentation.risk_directives) == (
        RiskMode.DESIGN_INTENT_UNKNOWN,
        RiskMode.FILE_TYPE_UNKNOWN,
        RiskMode.GEOMETRY_VIOLATION,
    )


def test_organization_rejects_mismatched_project() -> None:
    orchestrator = DeterministicOrchestrator(build_builtin_registry())
    plan = orchestrator.plan(_manifest(), _profile())
    review = _review().model_copy(update={"project_id": "prj-fedcba9876543210"})

    with pytest.raises(ValueError, match="identifiers do not match"):
        orchestrator.organize(plan, review)


def test_organization_rejects_mismatched_profile() -> None:
    orchestrator = DeterministicOrchestrator(build_builtin_registry())
    plan = orchestrator.plan(_manifest(), _profile())
    review = _review().model_copy(update={"profile_id": "different-profile"})

    with pytest.raises(ValueError, match="profiles do not match"):
        orchestrator.organize(plan, review)

    review = _review().model_copy(update={"profile_sha256": "f" * 64})
    with pytest.raises(ValueError, match="profiles do not match"):
        orchestrator.organize(plan, review)


def test_every_risk_mode_has_an_explicit_behavior() -> None:
    assert supported_risk_modes() == tuple(sorted(RiskMode, key=str))
    directives = directives_for(RiskMode)
    assert tuple(item.risk_mode for item in directives) == tuple(
        sorted(RiskMode, key=str)
    )
    assert all(item.action for item in directives)
    assert all(item.continue_independent_checks for item in directives)
    assert next(
        item for item in directives if item.risk_mode is RiskMode.UNIT_AMBIGUITY
    ).suppress_unconditional_ready
    modes = identify_risk_modes(
        _manifest(),
        (RiskMode.UNIT_AMBIGUITY, RiskMode.FILE_TYPE_UNKNOWN),
    )

    assert modes == (
        RiskMode.FILE_TYPE_UNKNOWN,
        RiskMode.UNIT_AMBIGUITY,
    )
