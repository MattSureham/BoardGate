"""minimum_drill_diameter v1 round-hit scope and uncertainty semantics."""

from __future__ import annotations

from pathlib import Path

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.drill import DrillHit, DrillSlot
from boardgate.domain.enums import FileType, Plating, RiskMode
from boardgate.domain.geometry import CoordinateSystem, Point
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
)
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.drill_rules import MinimumDrillDiameterRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _provenance(identifier: str) -> Provenance:
    return Provenance(
        source_file_id=SOURCE_ID,
        object_id=identifier,
        parser="test-excellon",
        parser_version="1.0",
    )


def _hit(
    identifier: str,
    diameter: float,
    *,
    plating: Plating = Plating.UNKNOWN,
    tool_code: str | None = "T01",
) -> DrillHit:
    return DrillHit(
        drill_id=identifier,
        position=Point(x=1.0, y=2.0),
        diameter_mm=diameter,
        tool_code=tool_code,
        plating=plating,
        provenance=_provenance(identifier),
    )


def _slot(identifier: str = "slot-a") -> DrillSlot:
    return DrillSlot(
        slot_id=identifier,
        start=Point(x=0.0, y=0.0),
        end=Point(x=1.0, y=0.0),
        width_mm=0.1,
        tool_code="T02",
        provenance=_provenance(identifier),
    )


def _project(
    *drills: DrillHit,
    slots: tuple[DrillSlot, ...] = (),
    uncertain: bool = False,
) -> PCBProject:
    source = SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.drl",
        sha256="a" * 64,
        size_bytes=1,
        file_type=FileType.EXCELLON,
    )
    manifest = ProjectManifest(project_id=PROJECT_ID, source_files=(source,))
    uncertainties = (
        (
            Uncertainty(
                risk_mode=RiskMode.PARSER_LIMITATION,
                subject="board.drl:EXCELLON_COMMAND_LIMITATION",
                summary="A drill source command requires confirmation.",
                candidates=("EXCELLON_COMMAND_LIMITATION",),
                evidence=(_provenance("diagnostic-a"),),
            ),
        )
        if uncertain
        else ()
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=(source,),
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        drills=drills,
        drill_slots=slots,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="b" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
        uncertainties=uncertainties,
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return MinimumDrillDiameterRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_wide_drill_and_exact_threshold_pass() -> None:
    wide = _evaluate(_project(_hit("wide", 0.3)))
    equal = _evaluate(_project(_hit("equal", 0.2)))

    assert wide.outcome is RuleOutcome.PASS
    assert wide.coverage is RuleCoverage.FULL
    assert equal.outcome is RuleOutcome.PASS


def test_confirmed_small_hit_has_tool_and_source_evidence() -> None:
    project = _project(_hit("small", 0.198, plating=Plating.PLATED))

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert not finding.requires_human_confirmation
    assert finding.config_path == "fabrication.min_drill_diameter"
    assert finding.measurement is not None
    assert finding.measurement.actual == 0.198
    assert finding.evidence[0].provenance.object_id == "small"
    assert "Plating is not used" in finding.facts[2]


def test_error_band_requires_confirmation() -> None:
    result = _evaluate(_project(_hit("band", 0.1995)))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation


def test_source_uncertainty_downgrades_violation_and_pass_coverage() -> None:
    violation = _evaluate(_project(_hit("small", 0.198), uncertain=True))
    passing = _evaluate(_project(_hit("wide", 0.3), uncertain=True))

    assert violation.coverage is RuleCoverage.PARTIAL
    assert violation.findings[0].requires_human_confirmation
    assert {item.provenance.object_id for item in violation.findings[0].evidence} == {
        "small",
        "diagnostic-a",
    }
    assert violation.findings[0].facts[-1].endswith("True.")
    assert passing.outcome is RuleOutcome.PASS
    assert passing.coverage is RuleCoverage.PARTIAL
    assert "prevents a complete pass claim" in passing.summary


def test_tool_code_may_be_unavailable_when_diameter_is_known() -> None:
    result = _evaluate(_project(_hit("small", 0.198, tool_code=None)))

    assert result.outcome is RuleOutcome.FINDINGS
    assert "diameter is parsed" in result.findings[0].facts[1]


def test_routed_slots_are_explicitly_outside_v1_scope() -> None:
    result = _evaluate(_project(slots=(_slot(),)))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.NOT_APPLICABLE
    assert "routed slots" in result.summary


def test_routed_slot_does_not_change_round_hit_finding() -> None:
    hit = _hit("small", 0.198)
    without_slot = _evaluate(_project(hit))
    with_slot = _evaluate(_project(hit, slots=(_slot(),)))

    assert with_slot.findings == without_slot.findings


def test_no_drill_features_is_not_applicable() -> None:
    result = _evaluate(_project())

    assert result.reason is RuleReason.NOT_APPLICABLE


def test_drill_diameter_review_json_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(_hit("small", 0.198)),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "minimum_drill_diameter"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    restored = ReviewResult.model_validate_json(review.model_dump_json())
    assert restored.model_dump_json() == review.model_dump_json()
