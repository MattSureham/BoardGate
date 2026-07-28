"""duplicate_reference_designator v1 same-dataset semantics."""

from __future__ import annotations

from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.config.models import RuleProfile
from boardgate.domain.component import BOMItem, ComponentPlacement
from boardgate.domain.enums import BoardSide, FileType, RiskMode
from boardgate.domain.finding import Finding
from boardgate.domain.geometry import CoordinateSystem, Point
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import JsonScalar, Provenance, SourceSpan
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
)
from boardgate.rules.assembly_rules import DuplicateReferenceDesignatorRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
BOM_SOURCE = "src-1111111111111111"
PLACEMENT_SOURCE = "src-2222222222222222"
UNRELATED_SOURCE = "src-3333333333333333"


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


def _source(source_id: str, file_type: FileType) -> SourceFile:
    logical_paths = {
        BOM_SOURCE: "bom.csv",
        PLACEMENT_SOURCE: "placement.csv",
        UNRELATED_SOURCE: "notes.txt",
    }
    digest_digits = {
        BOM_SOURCE: "1",
        PLACEMENT_SOURCE: "2",
        UNRELATED_SOURCE: "3",
    }
    return SourceFile(
        source_file_id=source_id,
        logical_path=logical_paths[source_id],
        sha256=digest_digits[source_id] * 64,
        size_bytes=1,
        file_type=file_type,
    )


def _project(  # noqa: PLR0913
    *,
    bom_items: tuple[BOMItem, ...] = (),
    placements: tuple[ComponentPlacement, ...] = (),
    include_bom_source: bool | None = None,
    include_placement_source: bool | None = None,
    include_unrelated_source: bool = False,
    review_requested: bool = True,
    uncertainties: tuple[Uncertainty, ...] = (),
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
            (_source(UNRELATED_SOURCE, FileType.UNKNOWN),)
            if include_unrelated_source
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
    return DuplicateReferenceDesignatorRule().evaluate(
        RuleContext(
            project=project,
            profile=selected_profile,
            profile_sha256=profile_hash(selected_profile),
            prior_results=(),
        )
    )


def _review(project: PCBProject, profile: RuleProfile) -> ReviewResult:
    registry = RuleRegistry.build(
        (DuplicateReferenceDesignatorRule(),),
        require_complete=False,
    )
    return RuleEngine(registry).evaluate(project, profile)


def _dataset_finding(
    result: RuleEvaluation,
    dataset: str,
) -> Finding:
    matches = tuple(
        finding
        for finding in result.findings
        if dataset.casefold()
        in " ".join((finding.title, finding.summary, *finding.facts)).casefold()
    )
    assert len(matches) == 1
    return matches[0]


def test_inactive_assembly_scope_is_not_applicable_even_with_duplicates() -> None:
    result = _evaluate(
        _project(
            bom_items=(
                _bom("bom-r1-a", "R1"),
                _bom("bom-r1-b", "r1", line=3),
            ),
            review_requested=False,
        )
    )

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_case_insensitive_duplicates_are_detected_per_dataset() -> None:
    result = _evaluate(
        _project(
            bom_items=(
                _bom("bom-r1-a", " R1 ", line=7),
                _bom("bom-r1-b", "r1", line=8),
            ),
            placements=(
                _placement("cpl-c1-a", "C1", line=11),
                _placement("cpl-c1-b", " c1 ", line=12),
            ),
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert len(result.findings) == 2
    bom_finding = _dataset_finding(result, "BOM")
    placement_finding = _dataset_finding(result, "placement")
    assert "R1" in " ".join(bom_finding.facts)
    assert "C1" in " ".join(placement_finding.facts)
    assert bom_finding.category is RiskMode.CROSS_FILE_INCONSISTENCY
    assert placement_finding.category is RiskMode.CROSS_FILE_INCONSISTENCY
    assert {
        item.provenance.object_id
        for item in bom_finding.evidence
        if item.provenance.object_id in {"bom-r1-a", "bom-r1-b"}
    } == {"bom-r1-a", "bom-r1-b"}
    assert {
        item.provenance.object_id
        for item in placement_finding.evidence
        if item.provenance.object_id in {"cpl-c1-a", "cpl-c1-b"}
    } == {"cpl-c1-a", "cpl-c1-b"}


def test_same_reference_once_in_each_dataset_is_not_a_duplicate() -> None:
    result = _evaluate(
        _project(
            bom_items=(_bom("bom-u1", "U1"),),
            placements=(_placement("cpl-u1", " u1 "),),
        )
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.findings == ()


def test_dnp_markers_and_ignored_references_are_filtered_consistently() -> None:
    result = _evaluate(
        _project(
            bom_items=(
                _bom("bom-active", "U1"),
                _bom("bom-explicit-a", "R1", dnp=True, line=3),
                _bom("bom-explicit-b", "r1", dnp=True, line=4),
                _bom("bom-marker-a", "R2", value="No Fit", line=5),
                _bom("bom-marker-b", "r2", value="no fit", line=6),
                _bom("bom-ignored-a", "TP1", line=7),
                _bom("bom-ignored-b", "tp1", line=8),
            ),
            placements=(
                _placement("cpl-active", "U1"),
                _placement("cpl-explicit-a", "C1", dnp=True, line=3),
                _placement("cpl-explicit-b", "c1", dnp=True, line=4),
                _placement(
                    "cpl-marker-a",
                    "C2",
                    metadata={"Population": "No Fit"},
                    line=5,
                ),
                _placement(
                    "cpl-marker-b",
                    "c2",
                    footprint="NO FIT",
                    line=6,
                ),
                _placement("cpl-ignored-a", "FID1", line=7),
                _placement("cpl-ignored-b", "fid1", line=8),
            ),
        ),
        profile=_profile(
            ignored_references=(" tp1 ", "FID1"),
            dnp_markers=("no fit",),
        ),
    )

    assert result.outcome is RuleOutcome.PASS
    assert result.coverage is RuleCoverage.FULL
    assert result.findings == ()


def test_multi_reference_rows_aggregate_provenance_without_id_collisions() -> None:
    profile = _profile()
    project = _project(
        bom_items=(
            _bom("bom-r1-r2-a", "R1", "R2", line=7),
            _bom("bom-r1-r2-b", "r1", "r2", line=8),
        ),
    )

    result = _evaluate(project, profile=profile)

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert len(result.findings) == 1
    finding = _dataset_finding(result, "BOM")
    assert "R1" in " ".join(finding.facts)
    assert "R2" in " ".join(finding.facts)
    assert {
        item.provenance.object_id
        for item in finding.evidence
        if item.provenance.object_id in {"bom-r1-r2-a", "bom-r1-r2-b"}
    } == {"bom-r1-r2-a", "bom-r1-r2-b"}
    finding_ids = [item.finding_id for item in result.findings]
    assert len(finding_ids) == len(set(finding_ids)) == 1


def test_source_relevant_uncertainty_requires_confirmation() -> None:
    uncertainty = _provenance("bom-uncertainty", BOM_SOURCE, line=1)
    result = _evaluate(
        _project(
            bom_items=(
                _bom("bom-r1-a", "R1"),
                _bom("bom-r1-b", "r1", line=3),
            ),
            uncertainties=(
                Uncertainty(
                    risk_mode=RiskMode.PARSER_LIMITATION,
                    subject="BOM parser limitation",
                    summary="One BOM row could not be interpreted.",
                    candidates=("PARTIAL_BOM",),
                    evidence=(uncertainty,),
                ),
            ),
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.requires_human_confirmation
    assert finding.confidence == 0.5
    assert "bom-uncertainty" in {item.provenance.object_id for item in finding.evidence}


def test_unrelated_source_uncertainty_does_not_downgrade_duplicate() -> None:
    unrelated = _provenance("notes-uncertainty", UNRELATED_SOURCE, line=1)
    result = _evaluate(
        _project(
            bom_items=(
                _bom("bom-r1-a", "R1"),
                _bom("bom-r1-b", "r1", line=3),
            ),
            include_unrelated_source=True,
            uncertainties=(
                Uncertainty(
                    risk_mode=RiskMode.FILE_TYPE_UNKNOWN,
                    subject="Unrelated text file",
                    summary="A notes file could not be classified.",
                    candidates=("notes",),
                    evidence=(unrelated,),
                ),
            ),
        )
    )

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert not finding.requires_human_confirmation
    assert finding.confidence == 1.0
    assert "notes-uncertainty" not in {
        item.provenance.object_id for item in finding.evidence
    }


def test_review_is_stable_and_json_round_trips_with_unique_finding_ids() -> None:
    profile = _profile()
    project = _project(
        bom_items=(
            _bom("bom-r1-r2-a", "R1", "R2"),
            _bom("bom-r1-r2-b", "r1", "r2", line=3),
        ),
        placements=(
            _placement("cpl-c1-a", "C1"),
            _placement("cpl-c1-b", "c1", line=3),
        ),
    )

    first = _review(project, profile)
    second = _review(project, profile)
    restored = ReviewResult.model_validate_json(first.model_dump_json())

    assert first == second
    assert restored.model_dump_json() == first.model_dump_json()
    assert first.rule_results[0].outcome is RuleOutcome.FINDINGS
    finding_ids = [finding.finding_id for finding in first.findings]
    assert len(finding_ids) == len(set(finding_ids)) == 2
