"""Rule contracts, registry, engine, thresholds, and status tests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError

from boardgate.config import load_rule_profile
from boardgate.config.models import RuleId, RuleProfile
from boardgate.domain.enums import (
    FileType,
    ReviewStatus,
    RiskMode,
    Severity,
)
from boardgate.domain.finding import Finding, FindingEvidence
from boardgate.domain.geometry import CoordinateSystem
from boardgate.domain.identifiers import finding_id
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty
from boardgate.rules import (
    ReviewResult,
    RuleContext,
    RuleCoverage,
    RuleEngine,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    RuleRegistry,
    RuleRegistryError,
    RuleResult,
    ThresholdDisposition,
    determine_review_status,
    evaluate_minimum_threshold,
)

PROFILE_PATH = Path("rules/default.yaml")
SOURCE_ID = "src-0123456789abcdef"
PROJECT_ID = "prj-0123456789abcdef"
PROFILE_SHA = "d" * 64


def _project(*, uncertainties: tuple[Uncertainty, ...] = ()) -> PCBProject:
    source = SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.gtl",
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
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256=PROFILE_SHA,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
        uncertainties=uncertainties,
    )


def _finding(
    rule_id: RuleId,
    *,
    severity: Severity = Severity.WARNING,
    confirmation: bool = False,
) -> Finding:
    provenance = Provenance(
        source_file_id=SOURCE_ID,
        object_id="line-0123456789abcdef",
        parser="test",
        parser_version="1.0",
    )
    identifier = finding_id(
        rule_id=rule_id.value,
        rule_version="1.0",
        profile_sha256=PROFILE_SHA,
        evidence_ids=(provenance.object_id or "",),
        location=None,
        measurement=None,
    )
    return Finding(
        finding_id=identifier,
        rule_id=rule_id.value,
        rule_version="1.0",
        category=RiskMode.GEOMETRY_VIOLATION,
        severity=severity,
        confidence=1.0,
        title="Deterministic test finding",
        summary="A test witness violates the configured requirement.",
        facts=("The witness was evaluated deterministically.",),
        evidence=(FindingEvidence(provenance=provenance),),
        requires_human_confirmation=confirmation,
    )


def _pass() -> RuleEvaluation:
    return RuleEvaluation(
        outcome=RuleOutcome.PASS,
        coverage=RuleCoverage.FULL,
        summary="No issue was found in the fully evaluated scope.",
        evaluated_object_count=1,
        applicable_object_count=1,
    )


@dataclass(frozen=True)
class DummyRule:
    rule_id: RuleId
    evaluation: RuleEvaluation
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = ()
    raises: bool = False

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        assert isinstance(context, RuleContext)
        if self.raises:
            raise RuntimeError("unpublished partial state")
        return self.evaluation


def _with_disabled(profile: RuleProfile, rule_id: RuleId) -> RuleProfile:
    setting = profile.rules.by_id(rule_id).model_copy(update={"enabled": False})
    settings = profile.rules.model_copy(update={rule_id.value: setting})
    return profile.model_copy(update={"rules": settings})


def _result(  # noqa: PLR0913
    rule_id: RuleId,
    *,
    outcome: RuleOutcome = RuleOutcome.PASS,
    coverage: RuleCoverage = RuleCoverage.FULL,
    required: bool = True,
    findings: tuple[Finding, ...] = (),
    reason: RuleReason | None = None,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_version="1.0",
        outcome=outcome,
        coverage=coverage,
        required=required,
        affects_readiness=True,
        findings=findings,
        reason=reason,
        summary="Deterministic test result.",
    )


def test_registry_requires_all_unique_v1_bindings() -> None:
    complete = RuleRegistry.build(DummyRule(rule_id, _pass()) for rule_id in RuleId)

    assert {rule.rule_id for rule in complete.ordered_rules} == set(RuleId)

    with pytest.raises(RuleRegistryError, match="duplicate"):
        RuleRegistry.build(
            (
                DummyRule(RuleId.DRILL_FILE_PRESENT, _pass()),
                DummyRule(RuleId.DRILL_FILE_PRESENT, _pass()),
            ),
            require_complete=False,
        )
    with pytest.raises(RuleRegistryError, match="unsupported rule version"):
        RuleRegistry.build(
            (
                DummyRule(
                    RuleId.DRILL_FILE_PRESENT,
                    _pass(),
                    version="2.0",
                ),
            ),
            require_complete=False,
        )
    with pytest.raises(RuleRegistryError, match="incomplete"):
        RuleRegistry.build((DummyRule(RuleId.DRILL_FILE_PRESENT, _pass()),))


def test_registry_rejects_unknown_self_and_cyclic_dependencies() -> None:
    with pytest.raises(RuleRegistryError, match="unknown dependencies"):
        RuleRegistry.build(
            (
                DummyRule(
                    RuleId.BOARD_OUTLINE_CLOSED,
                    _pass(),
                    dependencies=(RuleId.BOARD_OUTLINE_PRESENT,),
                ),
            ),
            require_complete=False,
        )
    with pytest.raises(RuleRegistryError, match="depend on itself"):
        RuleRegistry.build(
            (
                DummyRule(
                    RuleId.BOARD_OUTLINE_CLOSED,
                    _pass(),
                    dependencies=(RuleId.BOARD_OUTLINE_CLOSED,),
                ),
            ),
            require_complete=False,
        )
    with pytest.raises(RuleRegistryError, match="cycle"):
        RuleRegistry.build(
            (
                DummyRule(
                    RuleId.BOARD_OUTLINE_CLOSED,
                    _pass(),
                    dependencies=(RuleId.BOARD_OUTLINE_PRESENT,),
                ),
                DummyRule(
                    RuleId.BOARD_OUTLINE_PRESENT,
                    _pass(),
                    dependencies=(RuleId.BOARD_OUTLINE_CLOSED,),
                ),
            ),
            require_complete=False,
        )


def test_engine_contains_exceptions_and_skips_only_dependents() -> None:
    failing_id = RuleId.BOARD_OUTLINE_PRESENT
    dependent_id = RuleId.BOARD_OUTLINE_CLOSED
    independent_id = RuleId.DRILL_FILE_PRESENT
    registry = RuleRegistry.build(
        (
            DummyRule(failing_id, _pass(), raises=True),
            DummyRule(
                dependent_id,
                _pass(),
                dependencies=(failing_id,),
            ),
            DummyRule(independent_id, _pass()),
        ),
        require_complete=False,
    )

    review = RuleEngine(registry).evaluate(_project(), load_rule_profile(PROFILE_PATH))
    by_id = {result.rule_id: result for result in review.rule_results}

    assert by_id[failing_id].outcome is RuleOutcome.FAILED
    assert by_id[failing_id].reason is RuleReason.RULE_EXCEPTION
    assert not by_id[failing_id].findings
    assert by_id[dependent_id].outcome is RuleOutcome.SKIPPED
    assert by_id[dependent_id].reason is RuleReason.DEPENDENCY_UNAVAILABLE
    assert by_id[independent_id].outcome is RuleOutcome.PASS
    assert review.overall_status is ReviewStatus.INSUFFICIENT_INFORMATION
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review


def test_engine_records_disabled_rule_without_calling_it() -> None:
    rule_id = RuleId.MINIMUM_TRACE_WIDTH
    profile = _with_disabled(load_rule_profile(PROFILE_PATH), rule_id)
    registry = RuleRegistry.build(
        (DummyRule(rule_id, _pass(), raises=True),),
        require_complete=False,
    )

    result = RuleEngine(registry).evaluate(_project(), profile).rule_results[0]

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.DISABLED


@pytest.mark.parametrize(
    ("actual", "required", "error", "expected"),
    [
        (0.10, 0.10, 0.0, ThresholdDisposition.SATISFIED),
        (0.11, 0.10, 0.01, ThresholdDisposition.SATISFIED),
        (0.08, 0.10, 0.01, ThresholdDisposition.CONFIRMED_VIOLATION),
        (0.09, 0.10, 0.01, ThresholdDisposition.REQUIRES_CONFIRMATION),
        (0.105, 0.10, 0.01, ThresholdDisposition.REQUIRES_CONFIRMATION),
    ],
)
def test_minimum_threshold_error_band_semantics(
    actual: float,
    required: float,
    error: float,
    expected: ThresholdDisposition,
) -> None:
    assert (
        evaluate_minimum_threshold(
            actual=actual,
            required=required,
            error_bound=error,
        )
        is expected
    )


@pytest.mark.parametrize("value", [-1.0, math.nan, math.inf])
def test_minimum_threshold_rejects_invalid_values(value: float) -> None:
    with pytest.raises(ValueError):
        evaluate_minimum_threshold(actual=value, required=0.1, error_bound=0.0)


def test_rule_result_shape_is_strict_and_partial_pass_is_explicit() -> None:
    partial = _result(
        RuleId.MINIMUM_TRACE_WIDTH,
        coverage=RuleCoverage.PARTIAL,
    )
    assert partial.outcome is RuleOutcome.PASS

    with pytest.raises(ValidationError, match="must contain findings"):
        _result(
            RuleId.MINIMUM_TRACE_WIDTH,
            outcome=RuleOutcome.FINDINGS,
        )
    with pytest.raises(ValidationError, match="require a reason"):
        _result(
            RuleId.MINIMUM_TRACE_WIDTH,
            outcome=RuleOutcome.SKIPPED,
            coverage=RuleCoverage.NONE,
        )


def test_overall_status_precedence() -> None:
    project = _project()
    blocker = _finding(
        RuleId.MINIMUM_TRACE_WIDTH,
        severity=Severity.BLOCKER,
    )
    confirmation = _finding(
        RuleId.MINIMUM_TRACE_WIDTH,
        confirmation=True,
    )
    passed = (_result(RuleId.MINIMUM_TRACE_WIDTH),)

    assert (
        determine_review_status(
            project=project,
            rule_results=passed,
            analysis_failed=True,
        )
        is ReviewStatus.ANALYSIS_FAILED
    )
    assert (
        determine_review_status(
            project=project,
            rule_results=(
                _result(
                    RuleId.MINIMUM_TRACE_WIDTH,
                    outcome=RuleOutcome.FINDINGS,
                    findings=(blocker,),
                ),
            ),
            analysis_failed=False,
        )
        is ReviewStatus.NOT_READY_FOR_FABRICATION
    )
    assert (
        determine_review_status(
            project=project,
            rule_results=(
                _result(
                    RuleId.MINIMUM_TRACE_WIDTH,
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.INPUT_UNCERTAIN,
                ),
            ),
            analysis_failed=False,
        )
        is ReviewStatus.INSUFFICIENT_INFORMATION
    )
    assert (
        determine_review_status(
            project=project,
            rule_results=(
                _result(
                    RuleId.MINIMUM_TRACE_WIDTH,
                    outcome=RuleOutcome.FINDINGS,
                    findings=(confirmation,),
                ),
            ),
            analysis_failed=False,
        )
        is ReviewStatus.READY_WITH_CONFIRMATIONS
    )
    assert (
        determine_review_status(
            project=project,
            rule_results=(
                _result(
                    RuleId.MINIMUM_TRACE_WIDTH,
                    coverage=RuleCoverage.PARTIAL,
                ),
            ),
            analysis_failed=False,
        )
        is ReviewStatus.READY_WITH_CONFIRMATIONS
    )
    assert (
        determine_review_status(
            project=project,
            rule_results=passed,
            analysis_failed=False,
        )
        is ReviewStatus.READY_FOR_REVIEW
    )
