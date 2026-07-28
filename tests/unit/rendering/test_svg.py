"""Deterministic SVG renderer tests."""

from __future__ import annotations

from itertools import pairwise
from typing import Literal
from xml.etree import ElementTree

import pytest

from boardgate.config.models import RuleId
from boardgate.domain.drill import DrillHit, DrillSlot
from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    FileType,
    LayerRole,
    Plating,
    Polarity,
    ReviewStatus,
    RiskMode,
    Severity,
)
from boardgate.domain.finding import Finding, FindingEvidence
from boardgate.domain.geometry import BoundingBox, CoordinateSystem, Point
from boardgate.domain.layer import (
    Aperture,
    ArcPrimitive,
    BoardOutline,
    FlashPrimitive,
    LinePrimitive,
    OutlineContour,
    PCBLayer,
    RegionLineSegment,
    RegionPrimitive,
)
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile
from boardgate.rendering import render_svg
from boardgate.rules import (
    ReviewResult,
    RuleCoverage,
    RuleOutcome,
    RuleResult,
)

PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"
PROFILE_SHA = "b" * 64
SVG_NAMESPACE = {"svg": "http://www.w3.org/2000/svg"}


def _provenance(object_id: str = "object-1") -> Provenance:
    return Provenance(
        source_file_id=SOURCE_ID,
        object_id=object_id,
        parser="test",
        parser_version="1.0",
    )


def _segment(
    start: tuple[float, float],
    end: tuple[float, float],
) -> RegionLineSegment:
    return RegionLineSegment(
        start=Point(x=start[0], y=start[1]),
        end=Point(x=end[0], y=end[1]),
    )


def _contour(
    identifier: str,
    kind: Literal["outer", "cutout"],
    coordinates: tuple[tuple[float, float], ...],
) -> OutlineContour:
    segments = tuple(_segment(start, end) for start, end in pairwise(coordinates))
    return OutlineContour(
        contour_id=identifier,
        kind=kind,
        segments=segments,
        points=tuple(Point(x=x, y=y) for x, y in coordinates),
        closed=True,
        approximation_error_mm=0.0,
    )


def _source() -> SourceFile:
    return SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.gtl",
        sha256="a" * 64,
        size_bytes=1,
        file_type=FileType.GERBER,
    )


def _project(
    *,
    layers: tuple[PCBLayer, ...] = (),
    board_outline: BoardOutline | None = None,
    drills: tuple[DrillHit, ...] = (),
    slots: tuple[DrillSlot, ...] = (),
) -> PCBProject:
    source = _source()
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=(source,),
        manifest=ProjectManifest(project_id=PROJECT_ID, source_files=(source,)),
        coordinate_system=CoordinateSystem(),
        layers=layers,
        board_outline=board_outline,
        drills=drills,
        drill_slots=slots,
        fabrication_requirements=FabricationRequirements(
            profile_id="test",
            profile_sha256=PROFILE_SHA,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _finding(
    suffix: str,
    *,
    location: Point | None,
    title: str = "Review this feature",
    witness_bounds: BoundingBox | None = None,
) -> Finding:
    return Finding(
        finding_id=f"fnd-{suffix * 16}",
        rule_id=RuleId.MINIMUM_TRACE_WIDTH.value,
        rule_version="1.0",
        category=RiskMode.GEOMETRY_VIOLATION,
        severity=Severity.WARNING,
        confidence=1.0,
        config_path="rules.minimum_trace_width",
        title=title,
        summary="A deterministic rendering test finding.",
        facts=("The feature was measured.",),
        location=location,
        evidence=(
            FindingEvidence(
                provenance=_provenance(f"evidence-{suffix}"),
                witness_bounds=witness_bounds,
            ),
        ),
    )


def _review(*findings: Finding) -> ReviewResult:
    result = RuleResult(
        rule_id=RuleId.MINIMUM_TRACE_WIDTH,
        rule_version="1.0",
        outcome=RuleOutcome.FINDINGS if findings else RuleOutcome.PASS,
        coverage=RuleCoverage.FULL,
        required=True,
        affects_readiness=True,
        findings=findings,
        summary="Rendering fixture result.",
    )
    return ReviewResult(
        project_id=PROJECT_ID,
        profile_id="test",
        profile_sha256=PROFILE_SHA,
        overall_status=ReviewStatus.READY_FOR_REVIEW,
        rule_results=(result,),
        findings=findings,
        risk_modes=((RiskMode.GEOMETRY_VIOLATION,) if findings else ()),
        disclaimer="Engineering review remains required.",
    )


def _root(svg: str) -> ElementTree.Element:
    return ElementTree.fromstring(svg)  # noqa: S314 - renderer output is trusted


def test_renders_outline_cutout_and_explicit_y_up_transform() -> None:
    outer = _contour(
        "outer-1",
        "outer",
        ((0, 0), (20, 0), (20, 10), (0, 10), (0, 0)),
    )
    cutout = _contour(
        "cutout-1",
        "cutout",
        ((5, 3), (7, 3), (7, 5), (5, 5), (5, 3)),
    )
    outline = BoardOutline(
        contours=(outer, cutout),
        bounding_box=BoundingBox(
            minimum=Point(x=0, y=0),
            maximum=Point(x=20, y=10),
        ),
        outer_contour_count=1,
        measurement_error_mm=0.0,
        provenance=(_provenance(),),
    )

    root = _root(render_svg(_project(board_outline=outline), _review()))

    coordinate_group = root.find("svg:g[@id='board-coordinate-system']", SVG_NAMESPACE)
    assert coordinate_group is not None
    assert "scale(1 -1)" in coordinate_group.attrib["transform"]
    outer_group = coordinate_group.find("svg:g[@id='board-outline']", SVG_NAMESPACE)
    cutout_group = coordinate_group.find("svg:g[@id='board-cutouts']", SVG_NAMESPACE)
    assert outer_group is not None
    assert cutout_group is not None
    outer_path = outer_group.find("svg:path", SVG_NAMESPACE)
    cutout_path = cutout_group.find("svg:path", SVG_NAMESPACE)
    assert outer_path is not None
    assert cutout_path is not None
    assert outer_path.attrib["data-contour-id"] == "outer-1"
    assert cutout_path.attrib["data-contour-id"] == "cutout-1"


def test_renders_normalized_layer_primitives_in_stable_group() -> None:
    aperture = Aperture(shape=ApertureShape.CIRCLE, width_mm=0.2)
    region_segments = (
        _segment((1, 1), (3, 1)),
        _segment((3, 1), (2, 2)),
        _segment((2, 2), (1, 1)),
    )
    layer = PCBLayer(
        layer_id="top<&copper",
        source_file_id=SOURCE_ID,
        role=LayerRole.TOP_COPPER,
        side=BoardSide.TOP,
        mapping_confidence=1.0,
        primitives=(
            LinePrimitive(
                primitive_id="line-1",
                start=Point(x=0, y=0),
                end=Point(x=5, y=0),
                aperture=aperture,
                polarity=Polarity.DARK,
                provenance=_provenance("line-1"),
            ),
            ArcPrimitive(
                primitive_id="arc-1",
                start=Point(x=5, y=0),
                end=Point(x=6, y=1),
                center=Point(x=5, y=1),
                clockwise=False,
                aperture=aperture,
                polarity=Polarity.CLEAR,
                provenance=_provenance("arc-1"),
            ),
            FlashPrimitive(
                primitive_id="flash-1",
                position=Point(x=3, y=3),
                aperture=Aperture(
                    shape=ApertureShape.RECTANGLE,
                    width_mm=1,
                    height_mm=0.5,
                    rotation_degrees=45,
                ),
                polarity=Polarity.DARK,
                provenance=_provenance("flash-1"),
            ),
            RegionPrimitive(
                primitive_id="region-1",
                contours=(region_segments,),
                polarity=Polarity.DARK,
                provenance=_provenance("region-1"),
            ),
        ),
    )

    svg = render_svg(_project(layers=(layer,)), _review())
    root = _root(svg)
    layer_group = root.find(".//svg:g[@data-layer-id='top<&copper']", SVG_NAMESPACE)

    assert layer_group is not None
    assert layer_group.attrib["data-layer-role"] == "top_copper"
    assert [child.attrib["data-kind"] for child in layer_group] == [
        "line",
        "arc",
        "flash",
        "region",
    ]
    assert " A " in layer_group[1].attrib["d"]
    assert layer_group[2].tag.endswith("rect")
    assert layer_group[3].attrib["fill-rule"] == "evenodd"
    assert 'data-layer-id="top&lt;&amp;copper"' in svg


def test_renders_round_drills_and_line_and_arc_slots() -> None:
    project = _project(
        drills=(
            DrillHit(
                drill_id="drill-1",
                position=Point(x=2, y=2),
                diameter_mm=0.8,
                plating=Plating.PLATED,
                provenance=_provenance("drill-1"),
            ),
        ),
        slots=(
            DrillSlot(
                slot_id="slot-line",
                start=Point(x=4, y=2),
                end=Point(x=7, y=2),
                width_mm=1,
                plating=Plating.NON_PLATED,
                provenance=_provenance("slot-line"),
            ),
            DrillSlot(
                kind="arc",
                slot_id="slot-arc",
                start=Point(x=8, y=2),
                end=Point(x=9, y=3),
                center=Point(x=8, y=3),
                clockwise=False,
                width_mm=0.7,
                plating=Plating.UNKNOWN,
                provenance=_provenance("slot-arc"),
            ),
        ),
    )

    root = _root(render_svg(project, _review()))

    drill = root.find(".//svg:circle[@data-drill-id='drill-1']", SVG_NAMESPACE)
    line_slot = root.find(".//svg:path[@data-slot-id='slot-line']", SVG_NAMESPACE)
    arc_slot = root.find(".//svg:path[@data-slot-id='slot-arc']", SVG_NAMESPACE)
    assert drill is not None
    assert drill.attrib["r"] == "0.4"
    assert line_slot is not None and " L " in line_slot.attrib["d"]
    assert arc_slot is not None and " A " in arc_slot.attrib["d"]


def test_empty_project_has_deterministic_nonzero_viewbox() -> None:
    project = _project()
    review = _review()

    first = render_svg(project, review)
    second = render_svg(project, review)
    root = _root(first)

    assert first == second
    assert root.attrib["viewBox"] == "0 0 12 12"
    assert root.find(".//svg:g[@id='pcb-layers']", SVG_NAMESPACE) is not None


def test_spatial_and_witness_findings_render_as_markers() -> None:
    located = _finding("1", location=Point(x=1, y=2))
    witnessed = _finding(
        "2",
        location=None,
        witness_bounds=BoundingBox(
            minimum=Point(x=3, y=4),
            maximum=Point(x=5, y=6),
        ),
    )
    root = _root(render_svg(_project(), _review(located, witnessed)))

    for finding in (located, witnessed):
        marker = root.find(
            f".//svg:g[@data-finding-id='{finding.finding_id}']",
            SVG_NAMESPACE,
        )
        assert marker is not None
        assert marker.find("svg:circle", SVG_NAMESPACE) is not None
    legend = root.find("svg:g[@id='non-spatial-findings']", SVG_NAMESPACE)
    assert legend is not None
    assert not list(legend)


def test_non_spatial_finding_has_deterministic_escaped_legend_entry() -> None:
    finding = _finding(
        "3",
        location=None,
        title='Check <BOM> & "placement"',
    )
    svg = render_svg(_project(), _review(finding))
    root = _root(svg)
    legend_item = root.find(
        f".//svg:g[@data-finding-id='{finding.finding_id}']",
        SVG_NAMESPACE,
    )

    assert legend_item is not None
    text = legend_item.find("svg:text", SVG_NAMESPACE)
    assert text is not None
    assert text.text == f'{finding.finding_id} — Check <BOM> & "placement"'
    assert 'Check &lt;BOM&gt; &amp; "placement"' in svg
    assert svg.count(finding.finding_id) == 2


def test_output_is_well_formed_and_contains_no_active_content() -> None:
    hostile = _finding(
        "4",
        location=None,
        title='<script>alert("x")</script>\x00',
    )
    svg = render_svg(_project(), _review(hostile))
    root = _root(svg)

    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert not root.findall(".//svg:script", SVG_NAMESPACE)
    assert "javascript:" not in svg.casefold()
    assert " href=" not in svg.casefold()
    assert " onload=" not in svg.casefold()
    assert "<script>" not in svg.casefold()
    assert "\x00" not in svg


def test_rejects_review_for_a_different_project() -> None:
    review = _review().model_copy(update={"project_id": "prj-fedcba9876543210"})

    with pytest.raises(ValueError, match="project_id"):
        render_svg(_project(), review)
