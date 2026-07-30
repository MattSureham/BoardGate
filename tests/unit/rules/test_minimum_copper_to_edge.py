"""minimum_copper_to_edge v1 outer, cutout, and touch semantics."""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Literal

import pytest

from boardgate.config import load_rule_profile, profile_hash
from boardgate.config.models import RuleProfile
from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    FileType,
    LayerRole,
    Polarity,
    RiskMode,
)
from boardgate.domain.geometry import BoundingBox, CoordinateSystem, Point
from boardgate.domain.layer import (
    Aperture,
    BoardOutline,
    FlashPrimitive,
    GraphicPrimitive,
    LinePrimitive,
    OutlineContour,
    PCBLayer,
    RegionLineSegment,
)
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile
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
from boardgate.rules.geometry_rules import MinimumCopperToEdgeRule

PROFILE_PATH = Path("rules/default.yaml")
PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"


def _contour(
    identifier: str,
    *,
    minimum: float,
    maximum: float,
    kind: Literal["outer", "cutout"],
) -> OutlineContour:
    points = (
        Point(x=minimum, y=minimum),
        Point(x=maximum, y=minimum),
        Point(x=maximum, y=maximum),
        Point(x=minimum, y=maximum),
        Point(x=minimum, y=minimum),
    )
    return OutlineContour(
        contour_id=identifier,
        kind=kind,
        segments=tuple(
            RegionLineSegment(start=start, end=end) for start, end in pairwise(points)
        ),
        points=points,
        closed=True,
        approximation_error_mm=0.001,
        source_primitive_ids=tuple(
            f"{identifier}-segment-{index}" for index in range(4)
        ),
    )


def _outline(*, cutout: bool = False) -> BoardOutline:
    contours = [_contour("outer", minimum=0.0, maximum=10.0, kind="outer")]
    if cutout:
        contours.append(_contour("cutout", minimum=4.0, maximum=6.0, kind="cutout"))
    return BoardOutline(
        contours=tuple(contours),
        bounding_box=BoundingBox(
            minimum=Point(x=0.0, y=0.0),
            maximum=Point(x=10.0, y=10.0),
        ),
        outer_contour_count=1,
        measurement_error_mm=0.001,
        provenance=(
            Provenance(
                source_file_id=SOURCE_ID,
                object_id="outline-source",
                parser="test-outline",
                parser_version="1.0",
            ),
        ),
    )


def _flash(
    identifier: str,
    *,
    x: float,
    y: float = 5.0,
    diameter: float = 0.2,
    polarity: Polarity = Polarity.DARK,
) -> FlashPrimitive:
    return FlashPrimitive(
        primitive_id=identifier,
        position=Point(x=x, y=y),
        aperture=Aperture(
            shape=ApertureShape.CIRCLE,
            width_mm=diameter,
            height_mm=diameter,
        ),
        polarity=polarity,
        provenance=Provenance(
            source_file_id=SOURCE_ID,
            object_id=identifier,
            parser="test-gerber",
            parser_version="1.0",
        ),
    )


def _layer(
    *primitives: GraphicPrimitive,
    role: LayerRole = LayerRole.TOP_COPPER,
) -> PCBLayer:
    return PCBLayer(
        layer_id=f"layer-{role.value}",
        source_file_id=SOURCE_ID,
        role=role,
        side=(BoardSide.TOP if role is LayerRole.TOP_COPPER else BoardSide.BOTTOM),
        mapping_confidence=0.99,
        primitives=primitives,
    )


def _project(
    *primitives: GraphicPrimitive,
    cutout: bool = False,
    include_outline: bool = True,
) -> PCBProject:
    source = SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.gbr",
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
        layers=(_layer(*primitives),),
        board_outline=(_outline(cutout=cutout) if include_outline else None),
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256="b" * 64,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _rectangular_line(identifier: str, *, y: float) -> LinePrimitive:
    return LinePrimitive(
        primitive_id=identifier,
        start=Point(x=1.0, y=y),
        end=Point(x=9.0, y=y),
        aperture=Aperture(
            shape=ApertureShape.RECTANGLE,
            width_mm=1.0,
            height_mm=0.01,
        ),
        polarity=Polarity.DARK,
        provenance=Provenance(
            source_file_id=SOURCE_ID,
            object_id=identifier,
            parser="test-gerber",
            parser_version="1.0",
        ),
    )


def _profile(*, touch_policy: Literal["confirm", "strict"] = "confirm") -> RuleProfile:
    profile = load_rule_profile(PROFILE_PATH)
    return profile.model_copy(
        update={
            "policy": profile.policy.model_copy(
                update={"copper_edge_touch": touch_policy}
            )
        }
    )


def _evaluate(
    project: PCBProject,
    *,
    touch_policy: Literal["confirm", "strict"] = "confirm",
) -> RuleEvaluation:
    profile = _profile(touch_policy=touch_policy)
    return MinimumCopperToEdgeRule().evaluate(
        RuleContext(
            project=project,
            profile=profile,
            profile_sha256=profile_hash(profile),
            prior_results=(),
        )
    )


def test_clear_copper_and_exact_threshold_pass() -> None:
    clear = _evaluate(_project(_flash("clear", x=1.0)))
    equal = _evaluate(_project(_flash("equal", x=0.35)))

    assert clear.outcome is RuleOutcome.PASS
    assert clear.coverage is RuleCoverage.FULL
    assert equal.outcome is RuleOutcome.PASS


def test_confirmed_outer_edge_violation_has_direct_evidence() -> None:
    project = _project(_flash("near-edge", x=0.30))

    first = _evaluate(project)
    second = _evaluate(project)

    assert first == second
    assert first.outcome is RuleOutcome.FINDINGS
    assert first.coverage is RuleCoverage.FULL
    finding = first.findings[0]
    assert finding.category is RiskMode.GEOMETRY_VIOLATION
    assert finding.config_path == "fabrication.min_copper_to_edge"
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.actual == pytest.approx(0.2)
    assert {item.provenance.object_id for item in finding.evidence} == {
        "near-edge",
        "outline-source",
    }


def test_edge_clearance_error_band_requires_confirmation() -> None:
    result = _evaluate(_project(_flash("edge-band", x=0.348)))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.PARTIAL
    assert result.findings[0].requires_human_confirmation


def test_edge_touch_policy_can_confirm_or_strictly_reject() -> None:
    project = _project(_flash("touch", x=0.1))

    confirm = _evaluate(project)
    strict = _evaluate(project, touch_policy="strict")

    assert confirm.coverage is RuleCoverage.PARTIAL
    assert confirm.findings[0].requires_human_confirmation
    assert strict.coverage is RuleCoverage.FULL
    assert not strict.findings[0].requires_human_confirmation


def test_copper_outside_material_has_non_positive_signed_clearance() -> None:
    result = _evaluate(_project(_flash("outside", x=-0.2)))

    assert result.coverage is RuleCoverage.FULL
    finding = result.findings[0]
    assert not finding.requires_human_confirmation
    assert finding.measurement is not None
    assert finding.measurement.actual < 0.0
    assert "outside board material" in finding.title


def test_unknown_polarity_suppresses_edge_measurements() -> None:
    result = _evaluate(
        _project(
            _flash("near-edge", x=0.3),
            _flash("unknown", x=5.0, polarity=Polarity.UNKNOWN),
        )
    )

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.INPUT_UNCERTAIN
    assert not result.findings


def test_unsupported_draw_shape_cannot_create_edge_violation() -> None:
    result = _evaluate(_project(_rectangular_line("rectangular", y=0.4)))

    assert result.outcome is RuleOutcome.SKIPPED
    assert result.coverage is RuleCoverage.NONE
    assert result.reason is RuleReason.UNSUPPORTED_GEOMETRY
    assert not result.findings


def test_cutout_boundary_is_included_in_edge_clearance() -> None:
    result = _evaluate(_project(_flash("near-cutout", x=3.8), cutout=True))

    assert result.outcome is RuleOutcome.FINDINGS
    assert result.coverage is RuleCoverage.FULL
    assert result.findings[0].measurement is not None
    assert result.findings[0].measurement.actual == pytest.approx(0.1)


def test_missing_outline_or_copper_is_not_applicable() -> None:
    no_outline = _evaluate(_project(_flash("copper", x=1.0), include_outline=False))
    no_copper = _evaluate(_project())

    assert no_outline.reason is RuleReason.NOT_APPLICABLE
    assert no_copper.reason is RuleReason.NOT_APPLICABLE


def test_copper_edge_review_round_trip() -> None:
    profile = _profile()
    review = RuleEngine(build_builtin_registry(require_complete=False)).evaluate(
        _project(_flash("near-edge", x=0.30)),
        profile,
    )
    result = next(
        item
        for item in review.rule_results
        if item.rule_id.value == "minimum_copper_to_edge"
    )

    assert result.outcome is RuleOutcome.FINDINGS
    restored = ReviewResult.model_validate_json(review.model_dump_json())
    assert restored.model_dump_json() == review.model_dump_json()
