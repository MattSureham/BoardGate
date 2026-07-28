"""drill_file_present v1 semantics."""

from __future__ import annotations

from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.diagnostic import SourceDiagnostic, SourceDiagnosticLevel
from boardgate.domain.enums import FileType, RiskMode
from boardgate.domain.geometry import CoordinateSystem
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.source import (
    ClassificationCandidate,
    ProjectManifest,
    SourceFile,
)
from boardgate.rules import (
    ReviewResult,
    RuleContext,
    RuleCoverage,
    RuleEngine,
    RuleEvaluation,
    RuleOutcome,
)
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.file_rules import DrillFilePresentRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _source(
    file_type: FileType,
    *,
    candidates: tuple[ClassificationCandidate, ...] = (),
) -> SourceFile:
    suffix = "drl" if file_type is FileType.EXCELLON else "dat"
    return SourceFile(
        source_file_id=SOURCE_ID,
        logical_path=f"board.{suffix}",
        sha256="a" * 64,
        size_bytes=1,
        file_type=file_type,
        candidates=candidates,
    )


def _project(
    source: SourceFile,
    *,
    diagnostics: tuple[SourceDiagnostic, ...] = (),
) -> PCBProject:
    manifest = ProjectManifest(project_id=PROJECT_ID, source_files=(source,))
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=(source,),
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        source_diagnostics=diagnostics,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="b" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return DrillFilePresentRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_successfully_parsed_empty_excellon_file_passes() -> None:
    result = _evaluate(_project(_source(FileType.EXCELLON)))

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == 1


def test_confirmed_absence_is_stable_full_finding() -> None:
    project = _project(_source(FileType.GERBER))

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    assert first.findings[0].category is RiskMode.FILE_INCOMPLETE
    assert first.findings[0].config_path == "rules.drill_file_present"
    assert not first.findings[0].requires_human_confirmation


def test_unknown_candidate_produces_partial_confirmation() -> None:
    source = _source(
        FileType.UNKNOWN,
        candidates=(
            ClassificationCandidate(
                file_type=FileType.EXCELLON,
                confidence=0.6,
                evidence=("extension:.drl",),
            ),
        ),
    )

    result = _evaluate(_project(source))

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].category is RiskMode.FILE_TYPE_UNKNOWN
    assert result.findings[0].requires_human_confirmation


def test_parser_failure_is_partial_not_absence() -> None:
    source = _source(FileType.EXCELLON)
    diagnostic = SourceDiagnostic(
        diagnostic_id="diagnostic-0123456789abcdef",
        source_file_id=SOURCE_ID,
        code="PARSER_TIMEOUT",
        level=SourceDiagnosticLevel.ERROR,
        message="Parser timed out.",
    )

    result = _evaluate(_project(source, diagnostics=(diagnostic,)))

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].category is RiskMode.PARSER_LIMITATION
    assert result.findings[0].requires_human_confirmation
    assert (
        result.findings[0].evidence[0].provenance.object_id == diagnostic.diagnostic_id
    )


def test_drill_rule_review_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(_source(FileType.EXCELLON)),
        profile,
    )

    drill_result = next(
        result
        for result in review.rule_results
        if result.rule_id.value == "drill_file_present"
    )
    assert drill_result.outcome is RuleOutcome.PASS
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
