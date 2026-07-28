"""minimum_solder_mask_dam v1 final-opening component semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.config import load_rule_profile, profile_hash
from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    FileType,
    LayerRole,
    Polarity,
    RiskMode,
)
from boardgate.domain.geometry import CoordinateSystem, Point
from boardgate.domain.layer import Aperture, FlashPrimitive, PCBLayer
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
from boardgate.rules.surface_rules import MinimumSolderMaskDamRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
TOP_SOURCE = "src-1111111111111111"
BOTTOM_SOURCE = "src-2222222222222222"


def _provenance(identifier: str, source_id: str) -> Provenance:
    return Provenance(
        source_file_id=source_id,
        object_id=identifier,
        parser="test-gerber",
        parser_version="1.0",
    )


def _flash(  # noqa: PLR0913
    identifier: str,
    *,
    source_id: str = TOP_SOURCE,
    x: float = 0.0,
    width: float = 0.2,
    height: float | None = None,
    shape: ApertureShape = ApertureShape.CIRCLE,
    polarity: Polarity = Polarity.DARK,
) -> FlashPrimitive:
    return FlashPrimitive(
        primitive_id=identifier,
        position=Point(x=x, y=0.0),
        aperture=Aperture(
            shape=shape,
            width_mm=width,
            height_mm=height or width,
            macro_name=("TEST" if shape is ApertureShape.MACRO else None),
        ),
        polarity=polarity,
        provenance=_provenance(identifier, source_id),
    )


def _mask_layer(
    *primitives: FlashPrimitive,
    role: LayerRole = LayerRole.TOP_SOLDER_MASK,
    source_id: str = TOP_SOURCE,
    confidence: float = 0.99,
) -> PCBLayer:
    return PCBLayer(
        layer_id=f"layer-{role.value}",
        source_file_id=source_id,
        role=role,
        side=(BoardSide.TOP if role is LayerRole.TOP_SOLDER_MASK else BoardSide.BOTTOM),
        mapping_confidence=confidence,
        primitives=primitives,
    )


def _project(
    *layers: PCBLayer,
    uncertain_source: str | None = None,
) -> PCBProject:
    source_ids = tuple(dict.fromkeys(layer.source_file_id for layer in layers))
    sources = tuple(
        SourceFile(
            source_file_id=source_id,
            logical_path=f"mask-{index}.gbr",
            sha256=f"{index + 1:x}" * 64,
            size_bytes=1,
            file_type=FileType.GERBER,
        )
        for index, source_id in enumerate(source_ids)
    )
    uncertainties = (
        (
            Uncertainty(
                risk_mode=RiskMode.PARSER_LIMITATION,
                subject="mask source limitation",
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
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="a" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
        uncertainties=uncertainties,
    )


def _evaluate(project: PCBProject) -> RuleEvaluation:
    profile = load_rule_profile(PROFILE_PATH)
    return MinimumSolderMaskDamRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_wide_dam_and_exact_threshold_pass() -> None:
    wide = _evaluate(_project(_mask_layer(_flash("a"), _flash("b", x=0.4))))
    equal = _evaluate(_project(_mask_layer(_flash("a"), _flash("b", x=0.3))))

    assert wide.outcome is RuleOutcome.PASS
    assert wide.coverage is RuleCoverage.FULL
    assert equal.outcome is RuleOutcome.PASS


def test_confirmed_narrow_dam_has_two_opening_witnesses() -> None:
    project = _project(_mask_layer(_flash("a"), _flash("b", x=0.29)))

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.actual == pytest.approx(0.09)
    assert {item.provenance.object_id for item in finding.evidence} == {"a", "b"}


def test_dam_error_band_requires_confirmation() -> None:
    result = _evaluate(_project(_mask_layer(_flash("a"), _flash("b", x=0.298))))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation


def test_connected_gang_opening_is_not_reported_as_zero_dam() -> None:
    result = _evaluate(_project(_mask_layer(_flash("a"), _flash("b", x=0.15))))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.reason is RuleReason.NOT_APPLICABLE
    assert "gang openings are not dams" in result.summary


def test_openings_on_opposite_sides_are_never_compared() -> None:
    result = _evaluate(
        _project(
            _mask_layer(_flash("top")),
            _mask_layer(
                _flash("bottom", source_id=BOTTOM_SOURCE),
                role=LayerRole.BOTTOM_SOLDER_MASK,
                source_id=BOTTOM_SOURCE,
            ),
        )
    )

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.reason is RuleReason.NOT_APPLICABLE


def test_clear_polarity_can_split_one_dark_shape_into_two_openings() -> None:
    layer = _mask_layer(
        _flash(
            "dark",
            width=1.0,
            height=0.2,
            shape=ApertureShape.RECTANGLE,
        ),
        _flash(
            "clear",
            width=0.05,
            height=0.4,
            shape=ApertureShape.RECTANGLE,
            polarity=Polarity.CLEAR,
        ),
    )

    result = _evaluate(_project(layer))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.findings[0].measurement is not None
    assert result.findings[0].measurement.actual == pytest.approx(0.05)


def test_unknown_polarity_or_weak_mapping_is_input_uncertain() -> None:
    unknown = _evaluate(
        _project(
            _mask_layer(
                _flash("unknown", polarity=Polarity.UNKNOWN),
                _flash("other", x=0.4),
            )
        )
    )
    weak = _evaluate(
        _project(
            _mask_layer(
                _flash("a"),
                _flash("b", x=0.4),
                confidence=0.5,
            )
        )
    )

    assert unknown.reason is RuleReason.INPUT_UNCERTAIN
    assert weak.reason is RuleReason.INPUT_UNCERTAIN


def test_macro_mask_geometry_is_explicitly_unsupported() -> None:
    result = _evaluate(
        _project(
            _mask_layer(
                _flash("macro", shape=ApertureShape.MACRO),
                _flash("other", x=0.4),
            )
        )
    )

    assert result.reason is RuleReason.UNSUPPORTED_GEOMETRY


def test_source_uncertainty_downgrades_violation_and_pass() -> None:
    violation = _evaluate(
        _project(
            _mask_layer(_flash("a"), _flash("b", x=0.29)),
            uncertain_source=TOP_SOURCE,
        )
    )
    passing = _evaluate(
        _project(
            _mask_layer(_flash("a"), _flash("b", x=0.4)),
            uncertain_source=TOP_SOURCE,
        )
    )

    assert violation.coverage is RuleCoverage.PARTIAL
    assert violation.findings[0].requires_human_confirmation
    assert "diagnostic-a" in {
        item.provenance.object_id for item in violation.findings[0].evidence
    }
    assert passing.outcome is RuleOutcome.PASS
    assert passing.coverage is RuleCoverage.PARTIAL


def test_missing_mask_layer_is_not_applicable() -> None:
    result = _evaluate(_project())

    assert result.reason is RuleReason.NOT_APPLICABLE


def test_solder_mask_dam_review_json_round_trip() -> None:
    profile = load_rule_profile(PROFILE_PATH)
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(_mask_layer(_flash("a"), _flash("b", x=0.29))),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "minimum_solder_mask_dam"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    restored = ReviewResult.model_validate_json(review.model_dump_json())
    assert restored.model_dump_json() == review.model_dump_json()
