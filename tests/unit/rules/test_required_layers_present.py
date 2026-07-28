"""required_layers_present v1 semantics."""

from __future__ import annotations

from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.config.models import RuleProfile
from boardgate.domain.enums import (
    BoardSide,
    FileType,
    LayerRole,
    RiskMode,
    Severity,
)
from boardgate.domain.geometry import CoordinateSystem
from boardgate.domain.layer import LayerMappingCandidate, PCBLayer
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty
from boardgate.rules import (
    ReviewResult,
    RuleContext,
    RuleCoverage,
    RuleEngine,
    RuleEvaluation,
    RuleOutcome,
)
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.file_rules import RequiredLayersPresentRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _profile(role: LayerRole = LayerRole.TOP_COPPER) -> RuleProfile:
    profile = load_rule_profile(PROFILE_PATH)
    return profile.model_copy(update={"required_layers": (role,)})


def _source(
    *,
    file_type: FileType = FileType.GERBER,
    source_id: str = SOURCE_ID,
    logical_path: str = "board.gtl",
) -> SourceFile:
    return SourceFile(
        source_file_id=source_id,
        logical_path=logical_path,
        sha256="a" * 64,
        size_bytes=1,
        file_type=file_type,
    )


def _layer(
    *,
    role: LayerRole,
    candidates: tuple[LayerMappingCandidate, ...] = (),
    uncertain: bool = False,
) -> PCBLayer:
    uncertainties = (
        (
            Uncertainty(
                risk_mode=RiskMode.LAYER_MAPPING_UNCERTAIN,
                subject="board.gtl",
                summary="Layer mapping is unresolved.",
            ),
        )
        if uncertain
        else ()
    )
    return PCBLayer(
        layer_id="layer-0123456789abcdef",
        source_file_id=SOURCE_ID,
        role=role,
        side=(BoardSide.TOP if role is LayerRole.TOP_COPPER else BoardSide.UNKNOWN),
        mapping_confidence=(0.0 if uncertain else 0.99),
        mapping_candidates=candidates,
        uncertainties=uncertainties,
    )


def _project(
    *,
    sources: tuple[SourceFile, ...] | None = None,
    layers: tuple[PCBLayer, ...] = (),
) -> PCBProject:
    project_sources = sources if sources is not None else (_source(),)
    manifest = ProjectManifest(
        project_id=PROJECT_ID,
        source_files=project_sources,
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=project_sources,
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        layers=layers,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="b" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = _profile()
    return RequiredLayersPresentRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_strongly_mapped_required_layer_passes_fully() -> None:
    result = _evaluate(_project(layers=(_layer(role=LayerRole.TOP_COPPER),)))

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == 1
    assert not result.findings


def test_confirmed_missing_layer_has_stable_blocker_finding() -> None:
    project = _project()

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert finding.finding_id == second.findings[0].finding_id
    assert finding.category is RiskMode.FILE_INCOMPLETE
    assert finding.severity is Severity.BLOCKER
    assert finding.config_path == "required_layers[0]"
    assert finding.measurement is None
    assert not finding.requires_human_confirmation
    assert finding.evidence[0].provenance.source_file_id == SOURCE_ID


def test_mapping_candidate_is_partial_confirmation_not_false_absence() -> None:
    candidate = LayerMappingCandidate(
        role=LayerRole.TOP_COPPER,
        side=BoardSide.TOP,
        confidence=0.86,
        evidence=("extension:.gtl",),
    )
    project = _project(
        layers=(
            _layer(
                role=LayerRole.UNKNOWN,
                candidates=(candidate,),
                uncertain=True,
            ),
        )
    )

    result = _evaluate(project)

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.evaluated_object_count == 0
    finding = result.findings[0]
    assert finding.category is RiskMode.LAYER_MAPPING_UNCERTAIN
    assert finding.requires_human_confirmation
    assert finding.evidence[0].layer_id == "layer-0123456789abcdef"


def test_unknown_file_type_prevents_absence_claim() -> None:
    unknown = _source(file_type=FileType.UNKNOWN)

    result = _evaluate(_project(sources=(unknown,)))

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation
    assert "absence cannot be proven" in (result.findings[0].evidence[0].note or "")


def test_rule_result_and_review_round_trip() -> None:
    profile = _profile()
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(),
        profile,
    )

    required_result = next(
        result
        for result in review.rule_results
        if result.rule_id.value == "required_layers_present"
    )
    assert required_result.outcome is RuleOutcome.FINDINGS
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review
