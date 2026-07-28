"""bom_placement_reference_match v1 cross-file set semantics."""

from __future__ import annotations

from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.config.models import RuleProfile
from boardgate.domain.component import BOMItem, ComponentPlacement
from boardgate.domain.diagnostic import SourceDiagnostic, SourceDiagnosticLevel
from boardgate.domain.enums import (
    BoardSide,
    FileType,
    RiskMode,
)
from boardgate.domain.geometry import CoordinateSystem, Point
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import JsonScalar, Provenance, SourceSpan
from boardgate.domain.source import (
    ClassificationCandidate,
    ProjectManifest,
    SourceFile,
    Uncertainty,
)
from boardgate.rules import (
    ReviewResult,
    RuleContext,
    RuleCoverage,
    RuleEngine,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    RuleRegistry,
)
from boardgate.rules.assembly_rules import BOMPlacementReferenceMatchRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
BOM_SOURCE = "src-1111111111111111"
PLACEMENT_SOURCE = "src-2222222222222222"
UNKNOWN_SOURCE = "src-3333333333333333"


def _provenance(
    identifier: str,
    source_id: str,
    *,
    line: int,
) -> Provenance:
    return Provenance(
        source_file_id=source_id,
        object_id=identifier,
        parser="test-tabular",
        parser_version="1.0",
        source_span=SourceSpan(start_line=line, end_line=line),
    )


def _bom(  # noqa: PLR0913
    identifier: str,
    *references: str,
    dnp: bool = False,
    value: str | None = None,
    footprint: str | None = None,
    metadata: dict[str, JsonScalar] | None = None,
    line: int = 2,
) -> BOMItem:
    return BOMItem(
        references=references,
        quantity=(0 if dnp else len(references)),
        value=value,
        footprint=footprint,
        dnp=dnp,
        provenance=_provenance(identifier, BOM_SOURCE, line=line),
        metadata=metadata or {},
    )


def _placement(  # noqa: PLR0913
    identifier: str,
    reference: str,
    *,
    dnp: bool = False,
    value: str | None = None,
    footprint: str | None = None,
    metadata: dict[str, JsonScalar] | None = None,
    line: int = 2,
) -> ComponentPlacement:
    return ComponentPlacement(
        reference=reference,
        position=Point(x=1.0, y=2.0),
        rotation_degrees=0.0,
        side=BoardSide.TOP,
        value=value,
        footprint=footprint,
        dnp=dnp,
        provenance=_provenance(identifier, PLACEMENT_SOURCE, line=line),
        metadata=metadata or {},
    )


def _source(
    source_id: str,
    file_type: FileType,
    *,
    candidate_type: FileType | None = None,
) -> SourceFile:
    logical_paths = {
        BOM_SOURCE: "bom.csv",
        PLACEMENT_SOURCE: "placement.csv",
        UNKNOWN_SOURCE: "unclassified.dat",
    }
    digest_digits = {
        BOM_SOURCE: "1",
        PLACEMENT_SOURCE: "2",
        UNKNOWN_SOURCE: "3",
    }
    return SourceFile(
        source_file_id=source_id,
        logical_path=logical_paths[source_id],
        sha256=digest_digits[source_id] * 64,
        size_bytes=1,
        file_type=file_type,
        candidates=(
            (
                ClassificationCandidate(
                    file_type=candidate_type,
                    confidence=0.4,
                    evidence=("weak assembly filename signature",),
                ),
            )
            if candidate_type is not None
            else ()
        ),
    )


def _project(  # noqa: PLR0913
    *,
    bom_items: tuple[BOMItem, ...] = (),
    placements: tuple[ComponentPlacement, ...] = (),
    include_bom_source: bool | None = None,
    include_placement_source: bool | None = None,
    review_requested: bool = True,
    include_unknown_source: bool = False,
    unknown_candidate_type: FileType | None = FileType.PLACEMENT_CSV,
    uncertainties: tuple[Uncertainty, ...] = (),
    source_diagnostics: tuple[SourceDiagnostic, ...] = (),
) -> PCBProject:
    has_bom_source = (
        bool(bom_items) if include_bom_source is None else include_bom_source
    )
    has_placement_source = (
        bool(placements)
        if include_placement_source is None
        else include_placement_source
    )
    sources = (
        *((_source(BOM_SOURCE, FileType.BOM_CSV),) if has_bom_source else ()),
        *(
            (_source(PLACEMENT_SOURCE, FileType.PLACEMENT_CSV),)
            if has_placement_source
            else ()
        ),
        *(
            (
                _source(
                    UNKNOWN_SOURCE,
                    FileType.UNKNOWN,
                    candidate_type=unknown_candidate_type,
                ),
            )
            if include_unknown_source
            else ()
        ),
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=sources,
        manifest=ProjectManifest(project_id=PROJECT_ID, source_files=sources),
        coordinate_system=CoordinateSystem(),
        components=placements,
        bom_items=bom_items,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="a" * 64,
        ),
        assembly_requirements=AssemblyRequirements(
            review_requested=review_requested,
        ),
        uncertainties=uncertainties,
        source_diagnostics=source_diagnostics,
    )


def _profile(
    *,
    ignored_references: tuple[str, ...] = (),
    dnp_markers: tuple[str, ...] | None = None,
) -> RuleProfile:
    profile = load_rule_profile(PROFILE_PATH)
    policy = profile.policy.model_copy(
        update={
            "ignored_references": ignored_references,
            "dnp_markers": (
                profile.policy.dnp_markers if dnp_markers is None else dnp_markers
            ),
        }
    )
    return profile.model_copy(update={"policy": policy})


def _evaluate(
    project: PCBProject,
    *,
    profile: RuleProfile | None = None,
) -> RuleEvaluation:
    selected_profile = profile or _profile()
    return BOMPlacementReferenceMatchRule().evaluate(
        RuleContext(
            project=project,
            profile=selected_profile,
            profile_sha256=profile_hash(selected_profile),
            prior_results=(),
        )
    )


def _review(project: PCBProject, profile: RuleProfile) -> ReviewResult:
    registry = RuleRegistry.build(
        (BOMPlacementReferenceMatchRule(),),
        require_complete=False,
    )
    return RuleEngine(registry).evaluate(project, profile)


def test_inactive_assembly_scope_is_not_applicable_even_with_inputs() -> None:
    result = _evaluate(
        _project(
            bom_items=(_bom("bom-r1", "R1"),),
            placements=(_placement("cpl-r1", "R1"),),
            review_requested=False,
        )
    )

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_case_and_whitespace_normalized_reference_sets_fully_pass() -> None:
    result = _evaluate(
        _project(
            bom_items=(_bom("bom-row", " r1 ", "C2"),),
            placements=(
                _placement("cpl-r1", "R1"),
                _placement("cpl-c2", " c2 ", line=3),
            ),
        )
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == 2
    assert result.applicable_object_count == 2


def test_directional_differences_retain_row_level_evidence() -> None:
    result = _evaluate(
        _project(
            bom_items=(_bom("bom-r1", "R1", line=7),),
            placements=(_placement("cpl-c1", "C1", line=11),),
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.title == "BOM and placement reference sets differ"
    assert finding.facts[:2] == (
        "BOM-only references: R1.",
        "Placement-only references: C1.",
    )
    row_evidence = {
        evidence.provenance.object_id: evidence.provenance.source_span
        for evidence in finding.evidence
        if evidence.provenance.object_id in {"bom-r1", "cpl-c1"}
    }
    assert set(row_evidence) == {"bom-r1", "cpl-c1"}
    assert row_evidence["bom-r1"] is not None
    assert row_evidence["bom-r1"].start_line == 7
    assert row_evidence["cpl-c1"] is not None
    assert row_evidence["cpl-c1"].start_line == 11
    assert finding.category is RiskMode.CROSS_FILE_INCONSISTENCY
    assert not finding.requires_human_confirmation


def test_multi_reference_bom_row_has_contract_valid_stable_finding_id() -> None:
    profile = _profile()
    project = _project(
        bom_items=(_bom("bom-r1-r2", "R1", "R2"),),
        include_placement_source=True,
    )

    first = _evaluate(project, profile=profile)
    second = _evaluate(project, profile=profile)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert len(first.findings) == 1
    assert first.findings[0].facts[:2] == (
        "BOM-only references: R1, R2.",
        "Placement-only references: none.",
    )
    finding_ids = [finding.finding_id for finding in first.findings]
    assert len(finding_ids) == len(set(finding_ids)) == 1
    review = _review(project, profile)
    assert [finding.finding_id for finding in review.findings] == finding_ids
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review


def test_missing_placement_dataset_is_a_confirmed_inventory_finding() -> None:
    result = _evaluate(_project(bom_items=(_bom("bom-r1", "R1"),)))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    finding = result.findings[0]
    assert finding.title == "placement dataset is missing"
    assert finding.category is RiskMode.FILE_INCOMPLETE
    assert not finding.requires_human_confirmation
    assert {item.provenance.source_file_id for item in finding.evidence} == {BOM_SOURCE}


def test_missing_bom_dataset_is_a_confirmed_inventory_finding() -> None:
    result = _evaluate(_project(placements=(_placement("cpl-r1", "R1"),)))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    finding = result.findings[0]
    assert finding.title == "BOM dataset is missing"
    assert finding.category is RiskMode.FILE_INCOMPLETE
    assert not finding.requires_human_confirmation
    assert {item.provenance.source_file_id for item in finding.evidence} == {
        PLACEMENT_SOURCE
    }


def test_explicit_dnp_rows_are_excluded_from_each_dataset() -> None:
    result = _evaluate(
        _project(
            bom_items=(
                _bom("bom-match", "U1"),
                _bom("bom-only-dnp", "R1", dnp=True, line=3),
            ),
            placements=(
                _placement("cpl-match", "u1"),
                _placement("cpl-only-dnp", "C1", dnp=True, line=3),
            ),
        )
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == 1


def test_profile_dnp_markers_are_excluded_symmetrically() -> None:
    result = _evaluate(
        _project(
            bom_items=(
                _bom("bom-match", "U1"),
                _bom("bom-marker", "R1", value="Do Not Fit", line=3),
            ),
            placements=(
                _placement("cpl-match", "U1"),
                _placement(
                    "cpl-marker",
                    "C1",
                    metadata={"Population": "NOPOP"},
                    line=3,
                ),
            ),
        ),
        profile=_profile(dnp_markers=("do not fit", "nopop")),
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == 1


def test_profile_ignored_references_are_excluded_symmetrically() -> None:
    result = _evaluate(
        _project(
            bom_items=(
                _bom("bom-match", "U1"),
                _bom("bom-testpoint", "TP1", line=3),
            ),
            placements=(
                _placement("cpl-match", "u1"),
                _placement("cpl-fiducial", "FID1", line=3),
            ),
        ),
        profile=_profile(ignored_references=(" tp1 ", "fid1")),
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.evaluated_object_count == 1


def test_relevant_source_uncertainty_makes_differences_confirmations() -> None:
    diagnostic = _provenance("bom-diagnostic", BOM_SOURCE, line=1)
    project = _project(
        bom_items=(_bom("bom-r1", "R1"),),
        placements=(_placement("cpl-c1", "C1"),),
        uncertainties=(
            Uncertainty(
                risk_mode=RiskMode.PARSER_LIMITATION,
                subject="BOM parser limitation",
                summary="One BOM command could not be interpreted.",
                candidates=("PARTIAL_BOM",),
                evidence=(diagnostic,),
            ),
        ),
    )

    result = _evaluate(project)

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert all(
        finding.requires_human_confirmation and finding.confidence == 0.5
        for finding in result.findings
    )
    assert all(
        "bom-diagnostic"
        in {evidence.provenance.object_id for evidence in finding.evidence}
        for finding in result.findings
    )


def test_unknown_placement_candidate_makes_dataset_absence_a_confirmation() -> None:
    result = _evaluate(
        _project(
            bom_items=(_bom("bom-r1", "R1"),),
            include_unknown_source=True,
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    finding = result.findings[0]
    assert finding.title == "Assembly dataset availability requires confirmation"
    assert finding.facts[0] == "Unavailable datasets: placement."
    assert finding.category is RiskMode.FILE_TYPE_UNKNOWN
    assert finding.requires_human_confirmation
    assert {item.provenance.source_file_id for item in finding.evidence} == {
        BOM_SOURCE,
        UNKNOWN_SOURCE,
    }


def test_unrelated_unknown_candidate_does_not_downgrade_confirmed_absence() -> None:
    result = _evaluate(
        _project(
            bom_items=(_bom("bom-r1", "R1"),),
            include_unknown_source=True,
            unknown_candidate_type=FileType.BOM_CSV,
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    finding = result.findings[0]
    assert finding.category is RiskMode.FILE_INCOMPLETE
    assert not finding.requires_human_confirmation


def test_failed_classified_placement_parse_is_partial_not_confirmed_absence() -> None:
    diagnostic = SourceDiagnostic(
        diagnostic_id="diagnostic-0123456789abcdef",
        source_file_id=PLACEMENT_SOURCE,
        code="PARSER_TIMEOUT",
        level=SourceDiagnosticLevel.ERROR,
        message="Placement parser timed out.",
    )
    result = _evaluate(
        _project(
            bom_items=(_bom("bom-r1", "R1"),),
            include_placement_source=True,
            source_diagnostics=(diagnostic,),
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    finding = result.findings[0]
    assert finding.category is RiskMode.PARSER_LIMITATION
    assert finding.requires_human_confirmation
    assert diagnostic.diagnostic_id in {
        evidence.provenance.object_id for evidence in finding.evidence
    }


def test_review_result_is_deterministic_and_json_round_trips() -> None:
    profile = _profile()
    project = _project(
        bom_items=(_bom("bom-r1", "R1"),),
        placements=(_placement("cpl-c1", "C1"),),
    )

    first = _review(project, profile)
    second = _review(project, profile)
    restored = ReviewResult.model_validate_json(first.model_dump_json())

    assert first == second
    assert restored.model_dump_json() == first.model_dump_json()
    assert first.rule_results[0].outcome is RuleOutcome.FINDINGS
    assert len(first.findings) == 1
