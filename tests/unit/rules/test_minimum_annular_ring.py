"""minimum_annular_ring v1 unique pad/drill matching semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.drill import DrillHit
from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    FileType,
    LayerRole,
    Plating,
    Polarity,
    RiskMode,
)
from boardgate.domain.geometry import CoordinateSystem, Point
from boardgate.domain.layer import (
    Aperture,
    FlashPrimitive,
    LinePrimitive,
    PCBLayer,
)
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
from boardgate.rules.drill_rules import MinimumAnnularRingRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
DRILL_SOURCE = "src-0123456789abcdef"
COPPER_SOURCE = "src-fedcba9876543210"


def _provenance(identifier: str, source_id: str) -> Provenance:
    return Provenance(
        source_file_id=source_id,
        object_id=identifier,
        parser="test-source",
        parser_version="1.0",
    )


def _drill(
    *,
    diameter: float = 0.2,
    plating: Plating = Plating.PLATED,
) -> DrillHit:
    return DrillHit(
        drill_id="drill-a",
        position=Point(x=0.0, y=0.0),
        diameter_mm=diameter,
        tool_code="T01",
        plating=plating,
        provenance=_provenance("drill-a", DRILL_SOURCE),
    )


def _pad(
    identifier: str,
    *,
    diameter: float = 0.4,
    x: float = 0.0,
    shape: ApertureShape = ApertureShape.CIRCLE,
    polarity: Polarity = Polarity.DARK,
) -> FlashPrimitive:
    return FlashPrimitive(
        primitive_id=identifier,
        position=Point(x=x, y=0.0),
        aperture=Aperture(
            shape=shape,
            width_mm=diameter,
            height_mm=diameter,
            macro_name=("TEST" if shape is ApertureShape.MACRO else None),
        ),
        polarity=polarity,
        provenance=_provenance(identifier, COPPER_SOURCE),
    )


def _clear_line() -> LinePrimitive:
    return LinePrimitive(
        primitive_id="clear-line",
        start=Point(x=-0.2, y=0.0),
        end=Point(x=0.2, y=0.0),
        aperture=Aperture(
            shape=ApertureShape.CIRCLE,
            width_mm=0.05,
            height_mm=0.05,
        ),
        polarity=Polarity.CLEAR,
        provenance=_provenance("clear-line", COPPER_SOURCE),
    )


def _layer(
    *primitives: FlashPrimitive | LinePrimitive,
    layer_id: str = "layer-top",
    role: LayerRole = LayerRole.TOP_COPPER,
) -> PCBLayer:
    return PCBLayer(
        layer_id=layer_id,
        source_file_id=COPPER_SOURCE,
        role=role,
        side=(BoardSide.TOP if role is LayerRole.TOP_COPPER else BoardSide.BOTTOM),
        mapping_confidence=0.99,
        primitives=primitives,
    )


def _project(
    drill: DrillHit,
    *layers: PCBLayer,
    uncertain_source: str | None = None,
) -> PCBProject:
    sources = (
        SourceFile(
            source_file_id=DRILL_SOURCE,
            logical_path="board.drl",
            sha256="a" * 64,
            size_bytes=1,
            file_type=FileType.EXCELLON,
        ),
        SourceFile(
            source_file_id=COPPER_SOURCE,
            logical_path="board.gtl",
            sha256="b" * 64,
            size_bytes=1,
            file_type=FileType.GERBER,
        ),
    )
    uncertainties = (
        (
            Uncertainty(
                risk_mode=RiskMode.PARSER_LIMITATION,
                subject="source limitation",
                summary="A relevant source limitation requires confirmation.",
                candidates=("SOURCE_LIMITATION",),
                evidence=(_provenance("diagnostic-a", uncertain_source),),
            ),
        )
        if uncertain_source is not None
        else ()
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=sources,
        manifest=ProjectManifest(project_id=PROJECT_ID, source_files=sources),
        coordinate_system=CoordinateSystem(),
        layers=layers,
        drills=(drill,),
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="c" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
        uncertainties=uncertainties,
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return MinimumAnnularRingRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_wide_ring_and_exact_threshold_pass() -> None:
    wide = _evaluate(_project(_drill(), _layer(_pad("wide", diameter=0.42))))
    equal = _evaluate(_project(_drill(), _layer(_pad("equal", diameter=0.4))))

    assert wide.outcome is RuleOutcome.PASS
    assert wide.coverage is RuleCoverage.FULL
    assert equal.outcome is RuleOutcome.PASS


def test_confirmed_narrow_ring_has_pad_and_drill_evidence() -> None:
    project = _project(_drill(), _layer(_pad("narrow", diameter=0.396)))

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.actual == pytest.approx(0.098)
    assert finding.config_path == "fabrication.min_annular_ring"
    assert {item.provenance.object_id for item in finding.evidence} == {
        "drill-a",
        "narrow",
    }


def test_pad_smaller_than_drill_is_a_confirmed_negative_ring() -> None:
    result = _evaluate(_project(_drill(), _layer(_pad("undersized", diameter=0.1))))

    assert result.coverage is RuleCoverage.FULL
    assert result.findings[0].measurement is not None
    assert result.findings[0].measurement.actual == pytest.approx(-0.05)
    assert not result.findings[0].requires_human_confirmation


def test_error_band_and_center_eccentricity_require_confirmation() -> None:
    band = _evaluate(_project(_drill(), _layer(_pad("band", diameter=0.399))))
    eccentric = _evaluate(
        _project(_drill(), _layer(_pad("offset", diameter=0.4, x=0.0005)))
    )

    assert band.coverage is RuleCoverage.PARTIAL
    assert band.findings[0].requires_human_confirmation
    assert eccentric.coverage is RuleCoverage.PARTIAL
    assert eccentric.findings[0].measurement is not None
    assert eccentric.findings[0].measurement.actual == pytest.approx(0.0995)


@pytest.mark.parametrize("plating", [Plating.NON_PLATED, Plating.UNKNOWN])
def test_npth_and_unknown_plating_are_not_applicable(plating: Plating) -> None:
    result = _evaluate(_project(_drill(plating=plating), _layer(_pad("pad"))))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.reason is RuleReason.NOT_APPLICABLE


@pytest.mark.parametrize(
    "primitives",
    [
        (),
        (_pad("rect", shape=ApertureShape.RECTANGLE),),
        (_pad("macro", shape=ApertureShape.MACRO),),
        (_pad("first"), _pad("second")),
    ],
)
def test_unmatched_or_ambiguous_pad_is_confirmation(
    primitives: tuple[FlashPrimitive, ...],
) -> None:
    result = _evaluate(_project(_drill(), _layer(*primitives)))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    finding = result.findings[0]
    assert finding.category is RiskMode.DESIGN_INTENT_UNKNOWN
    assert finding.requires_human_confirmation
    assert finding.measurement is None


def test_ambiguous_matches_on_two_layers_have_distinct_finding_ids() -> None:
    result = _evaluate(
        _project(
            _drill(),
            _layer(layer_id="layer-top"),
            _layer(
                layer_id="layer-bottom",
                role=LayerRole.BOTTOM_COPPER,
            ),
        )
    )

    assert len(result.findings) == 2
    assert len({finding.finding_id for finding in result.findings}) == 2


def test_clear_geometry_intersecting_pad_prevents_numeric_claim() -> None:
    result = _evaluate(_project(_drill(), _layer(_pad("pad"), _clear_line())))

    assert result.coverage is RuleCoverage.PARTIAL
    finding = result.findings[0]
    assert finding.category is RiskMode.DESIGN_INTENT_UNKNOWN
    assert "clear-line" in {item.provenance.object_id for item in finding.evidence}


def test_source_uncertainty_downgrades_numeric_violation() -> None:
    result = _evaluate(
        _project(
            _drill(),
            _layer(_pad("narrow", diameter=0.396)),
            uncertain_source=COPPER_SOURCE,
        )
    )

    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation
    assert "diagnostic-a" in {
        item.provenance.object_id for item in result.findings[0].evidence
    }


def test_missing_trusted_copper_is_input_uncertain() -> None:
    result = _evaluate(_project(_drill()))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.reason is RuleReason.INPUT_UNCERTAIN


def test_annular_ring_review_json_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(_drill(), _layer(_pad("narrow", diameter=0.396))),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "minimum_annular_ring"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    restored = ReviewResult.model_validate_json(review.model_dump_json())
    assert restored.model_dump_json() == review.model_dump_json()
