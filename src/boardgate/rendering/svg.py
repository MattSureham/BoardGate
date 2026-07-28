"""Deterministic, script-free SVG rendering for review artifacts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from xml.sax.saxutils import escape

from boardgate.domain.drill import DrillSlot
from boardgate.domain.enums import ApertureShape, LayerRole, Polarity
from boardgate.domain.finding import Finding
from boardgate.domain.geometry import BoundingBox, Point
from boardgate.domain.layer import (
    Aperture,
    ArcPrimitive,
    FlashPrimitive,
    GraphicPrimitive,
    LinePrimitive,
    OutlineContour,
    PCBLayer,
    RegionArcSegment,
    RegionLineSegment,
    RegionPrimitive,
    RegionSegment,
)
from boardgate.domain.project import PCBProject
from boardgate.rules.models import ReviewResult

_DECIMAL_PLACES = 6
_MINIMUM_CANVAS_SPAN = 10.0
_LAYER_COLORS: dict[LayerRole, str] = {
    LayerRole.TOP_COPPER: "#b66a2c",
    LayerRole.BOTTOM_COPPER: "#7f4a24",
    LayerRole.INNER_COPPER: "#9b7735",
    LayerRole.TOP_SOLDER_MASK: "#16835b",
    LayerRole.BOTTOM_SOLDER_MASK: "#126949",
    LayerRole.TOP_SILKSCREEN: "#536271",
    LayerRole.BOTTOM_SILKSCREEN: "#718096",
    LayerRole.TOP_PASTE: "#7e8790",
    LayerRole.BOTTOM_PASTE: "#626c76",
    LayerRole.BOARD_OUTLINE: "#263f53",
    LayerRole.DRILL_PLATED: "#315d86",
    LayerRole.DRILL_NON_PLATED: "#61798d",
    LayerRole.UNKNOWN: "#8b5a8c",
}


@dataclass(frozen=True)
class _Extent:
    minimum_x: float
    minimum_y: float
    maximum_x: float
    maximum_y: float

    @property
    def width(self) -> float:
        return self.maximum_x - self.minimum_x

    @property
    def height(self) -> float:
        return self.maximum_y - self.minimum_y

    def include(self, other: _Extent) -> _Extent:
        return _Extent(
            minimum_x=min(self.minimum_x, other.minimum_x),
            minimum_y=min(self.minimum_y, other.minimum_y),
            maximum_x=max(self.maximum_x, other.maximum_x),
            maximum_y=max(self.maximum_y, other.maximum_y),
        )


def render_svg(project: PCBProject, review: ReviewResult) -> str:
    """Return a standalone SVG preview for one project and its review."""
    if project.project_id != review.project_id:
        msg = "review project_id must match the rendered PCB project"
        raise ValueError(msg)

    extent = _project_extent(project, review)
    span = max(extent.width, extent.height, _MINIMUM_CANVAS_SPAN)
    margin = max(1.0, span * 0.05)
    board_width = extent.width + (2.0 * margin)
    board_height = extent.height + (2.0 * margin)
    font_size = min(3.0, max(1.5, span / 50.0))
    marker_radius = max(0.6, font_size * 0.45)
    line_width = max(0.15, span / 500.0)
    non_spatial = tuple(
        finding
        for finding in sorted(review.findings, key=lambda item: item.finding_id)
        if _finding_position(finding) is None
    )
    legend_width = _legend_width(non_spatial, font_size)
    legend_height = (
        margin + font_size + len(non_spatial) * font_size * 1.6 if non_spatial else 0.0
    )
    translate_x = margin - extent.minimum_x
    translate_y = margin + extent.maximum_y
    spatial_width = _spatial_content_width(
        review,
        translate_x=translate_x,
        marker_radius=marker_radius,
        font_size=font_size,
        margin=margin,
    )
    canvas_width = max(board_width, legend_width, spatial_width)
    canvas_height = board_height + legend_height

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
            f'viewBox="0 0 {_number(canvas_width)} {_number(canvas_height)}" '
            'role="img" aria-labelledby="boardgate-title boardgate-description">'
        ),
        (
            f'  <title id="boardgate-title">'
            f"{_text('BoardGate PCB review preview')}</title>"
        ),
        (
            '  <desc id="boardgate-description">'
            f"{_text(f'Deterministic preview for project {project.project_id}.')}"
            "</desc>"
        ),
        (
            f'  <rect id="canvas-background" x="0" y="0" '
            f'width="{_number(canvas_width)}" height="{_number(canvas_height)}" '
            'fill="#ffffff"/>'
        ),
        (
            '  <g id="board-coordinate-system" '
            'data-coordinate-system="x-right-y-up" '
            f'transform="translate({_number(translate_x)} '
            f'{_number(translate_y)}) scale(1 -1)">'
        ),
    ]
    lines.extend(_render_outline(project, line_width))
    lines.extend(_render_layers(project.layers))
    lines.extend(_render_drills(project, line_width))
    lines.append("  </g>")
    lines.extend(
        _render_spatial_findings(
            review,
            translate_x=translate_x,
            translate_y=translate_y,
            marker_radius=marker_radius,
            font_size=font_size,
        )
    )
    lines.extend(
        _render_non_spatial_legend(
            non_spatial,
            x=margin,
            y=board_height + margin,
            font_size=font_size,
        )
    )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _render_outline(project: PCBProject, line_width: float) -> list[str]:
    lines = ['    <g id="board-outline">']
    cutouts: list[OutlineContour] = []
    if project.board_outline is not None:
        for contour in sorted(
            project.board_outline.contours,
            key=lambda item: (item.kind, item.contour_id),
        ):
            if contour.kind == "cutout":
                cutouts.append(contour)
                continue
            lines.append(
                _outline_path(
                    contour,
                    indent="      ",
                    stroke="#20394d",
                    line_width=line_width,
                )
            )
    lines.append("    </g>")
    lines.append('    <g id="board-cutouts">')
    lines.extend(
        (
            _outline_path(
                contour,
                indent="      ",
                stroke="#c03d35",
                line_width=line_width,
            )
        )
        for contour in cutouts
    )
    lines.append("    </g>")
    return lines


def _outline_path(
    contour: OutlineContour,
    *,
    indent: str,
    stroke: str,
    line_width: float,
) -> str:
    path = _segments_path(contour.segments, close=contour.closed)
    return (
        f'{indent}<path data-contour-id="{_attr(contour.contour_id)}" '
        f'data-contour-kind="{contour.kind}" d="{_attr(path)}" '
        f'fill="none" stroke="{stroke}" stroke-width="{_number(line_width)}"/>'
    )


def _render_layers(layers: tuple[PCBLayer, ...]) -> list[str]:
    lines = ['    <g id="pcb-layers">']
    for index, layer in enumerate(
        sorted(
            layers,
            key=lambda item: (item.role.value, item.side.value, item.layer_id),
        ),
        start=1,
    ):
        color = _LAYER_COLORS[layer.role]
        lines.append(
            f'      <g id="pcb-layer-{index:04d}" '
            f'data-layer-id="{_attr(layer.layer_id)}" '
            f'data-layer-role="{layer.role.value}" '
            f'data-layer-side="{layer.side.value}" color="{color}">'
        )
        for primitive in layer.primitives:
            lines.extend(_render_primitive(primitive))
        lines.append("      </g>")
    lines.append("    </g>")
    return lines


def _render_primitive(primitive: GraphicPrimitive) -> list[str]:
    match primitive:
        case LinePrimitive():
            return [_render_line(primitive)]
        case ArcPrimitive():
            return [_render_arc(primitive)]
        case FlashPrimitive():
            return [_render_flash(primitive)]
        case RegionPrimitive():
            return [_render_region(primitive)]


def _render_line(primitive: LinePrimitive) -> str:
    opacity, dash = _polarity_stroke(primitive.polarity, primitive.aperture.width_mm)
    dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'        <line data-primitive-id="{_attr(primitive.primitive_id)}" '
        f'data-kind="line" data-polarity="{primitive.polarity.value}" '
        f'data-aperture-shape="{primitive.aperture.shape.value}" '
        f'x1="{_number(primitive.start.x)}" y1="{_number(primitive.start.y)}" '
        f'x2="{_number(primitive.end.x)}" y2="{_number(primitive.end.y)}" '
        f'fill="none" stroke="currentColor" '
        f'stroke-width="{_number(primitive.aperture.width_mm)}" '
        f'stroke-linecap="{_line_cap(primitive.aperture)}" '
        f'opacity="{opacity}"{dash_attribute}/>'
    )


def _render_arc(primitive: ArcPrimitive) -> str:
    opacity, dash = _polarity_stroke(primitive.polarity, primitive.aperture.width_mm)
    dash_attribute = f' stroke-dasharray="{dash}"' if dash else ""
    path = _arc_path(
        primitive.start,
        primitive.end,
        primitive.center,
        primitive.clockwise,
    )
    return (
        f'        <path data-primitive-id="{_attr(primitive.primitive_id)}" '
        f'data-kind="arc" data-polarity="{primitive.polarity.value}" '
        f'data-aperture-shape="{primitive.aperture.shape.value}" '
        f'd="{_attr(path)}" fill="none" stroke="currentColor" '
        f'stroke-width="{_number(primitive.aperture.width_mm)}" '
        f'stroke-linecap="{_line_cap(primitive.aperture)}" '
        f'opacity="{opacity}"{dash_attribute}/>'
    )


def _render_flash(primitive: FlashPrimitive) -> str:
    aperture = primitive.aperture
    common = (
        f'data-primitive-id="{_attr(primitive.primitive_id)}" '
        f'data-kind="flash" data-polarity="{primitive.polarity.value}" '
        f'data-aperture-shape="{aperture.shape.value}" '
        f'fill="currentColor" opacity="{_polarity_opacity(primitive.polarity)}"'
    )
    x = primitive.position.x
    y = primitive.position.y
    height = aperture.height_mm or aperture.width_mm
    rotation = _rotation(aperture.rotation_degrees, primitive.position)
    if aperture.shape is ApertureShape.CIRCLE:
        return (
            f'        <circle {common} cx="{_number(x)}" cy="{_number(y)}" '
            f'r="{_number(aperture.width_mm / 2.0)}"/>'
        )
    if aperture.shape in {ApertureShape.RECTANGLE, ApertureShape.OBROUND}:
        rounding = (
            f' rx="{_number(min(aperture.width_mm, height) / 2.0)}"'
            if aperture.shape is ApertureShape.OBROUND
            else ""
        )
        return (
            f'        <rect {common} x="{_number(x - aperture.width_mm / 2.0)}" '
            f'y="{_number(y - height / 2.0)}" '
            f'width="{_number(aperture.width_mm)}" height="{_number(height)}"'
            f"{rounding}{rotation}/>"
        )
    if aperture.shape is ApertureShape.POLYGON and aperture.vertices is not None:
        points = _regular_polygon_points(
            primitive.position,
            radius=aperture.width_mm / 2.0,
            vertices=aperture.vertices,
            rotation_degrees=aperture.rotation_degrees,
        )
        return f'        <polygon {common} points="{points}"/>'
    return (
        f'        <ellipse {common} cx="{_number(x)}" cy="{_number(y)}" '
        f'rx="{_number(aperture.width_mm / 2.0)}" '
        f'ry="{_number(height / 2.0)}" stroke="currentColor" '
        f'stroke-width="{_number(max(aperture.width_mm, height) / 20.0)}" '
        f'stroke-dasharray="{_number(aperture.width_mm / 4.0)} '
        f'{_number(aperture.width_mm / 4.0)}"{rotation}/>'
    )


def _render_region(primitive: RegionPrimitive) -> str:
    path = " ".join(
        _segments_path(contour, close=True) for contour in primitive.contours
    )
    return (
        f'        <path data-primitive-id="{_attr(primitive.primitive_id)}" '
        f'data-kind="region" data-polarity="{primitive.polarity.value}" '
        f'd="{_attr(path)}" fill="currentColor" fill-rule="evenodd" '
        f'opacity="{_polarity_opacity(primitive.polarity)}"/>'
    )


def _render_drills(project: PCBProject, line_width: float) -> list[str]:
    lines = ['    <g id="round-drills">']
    lines.extend(
        (
            f'      <circle data-drill-id="{_attr(drill.drill_id)}" '
            f'data-plating="{drill.plating.value}" '
            f'cx="{_number(drill.position.x)}" '
            f'cy="{_number(drill.position.y)}" '
            f'r="{_number(drill.diameter_mm / 2.0)}" fill="#ffffff" '
            f'stroke="#315d86" stroke-width="{_number(line_width)}"/>'
        )
        for drill in sorted(project.drills, key=lambda item: item.drill_id)
    )
    lines.append("    </g>")
    lines.append('    <g id="drill-slots">')
    for slot in sorted(project.drill_slots, key=lambda item: item.slot_id):
        path = _slot_path(slot)
        lines.append(
            f'      <path data-slot-id="{_attr(slot.slot_id)}" '
            f'data-slot-kind="{slot.kind}" data-plating="{slot.plating.value}" '
            f'd="{_attr(path)}" fill="none" stroke="#315d86" '
            f'stroke-width="{_number(slot.width_mm)}" stroke-linecap="round"/>'
        )
    lines.append("    </g>")
    return lines


def _render_spatial_findings(
    review: ReviewResult,
    *,
    translate_x: float,
    translate_y: float,
    marker_radius: float,
    font_size: float,
) -> list[str]:
    lines = ['  <g id="spatial-findings">']
    for finding in sorted(review.findings, key=lambda item: item.finding_id):
        position = _finding_position(finding)
        if position is None:
            continue
        screen_x = position.x + translate_x
        screen_y = translate_y - position.y
        lines.extend(
            (
                f'    <g data-finding-id="{_attr(finding.finding_id)}" '
                f'data-finding-severity="{finding.severity.value}">',
                (
                    f'      <circle cx="{_number(screen_x)}" '
                    f'cy="{_number(screen_y)}" r="{_number(marker_radius)}" '
                    'fill="#fff3cd" stroke="#b42318" '
                    f'stroke-width="{_number(marker_radius / 3.0)}"/>'
                ),
                (
                    f'      <text x="{_number(screen_x + marker_radius * 1.5)}" '
                    f'y="{_number(screen_y + font_size * 0.35)}" '
                    f'font-family="monospace" font-size="{_number(font_size)}" '
                    f'fill="#7a271a">{_text(finding.finding_id)}</text>'
                ),
                "    </g>",
            )
        )
    lines.append("  </g>")
    return lines


def _render_non_spatial_legend(
    findings: tuple[Finding, ...],
    *,
    x: float,
    y: float,
    font_size: float,
) -> list[str]:
    lines = ['  <g id="non-spatial-findings">']
    if findings:
        lines.append(
            f'    <text x="{_number(x)}" y="{_number(y)}" '
            f'font-family="sans-serif" font-size="{_number(font_size)}" '
            f'font-weight="bold" fill="#233044">{_text("Non-spatial findings")}</text>'
        )
    for index, finding in enumerate(findings, start=1):
        row_y = y + index * font_size * 1.6
        label = f"{finding.finding_id} — {finding.title}"
        lines.extend(
            (
                f'    <g data-finding-id="{_attr(finding.finding_id)}" '
                f'data-finding-severity="{finding.severity.value}">',
                (
                    f'      <text x="{_number(x)}" y="{_number(row_y)}" '
                    f'font-family="monospace" font-size="{_number(font_size)}" '
                    f'fill="#344054">{_text(label)}</text>'
                ),
                "    </g>",
            )
        )
    lines.append("  </g>")
    return lines


def _project_extent(project: PCBProject, review: ReviewResult) -> _Extent:
    extents: list[_Extent] = []
    if project.board_outline is not None:
        extents.append(_box_extent(project.board_outline.bounding_box))
    for layer in project.layers:
        if layer.bounding_box is not None:
            extents.append(_box_extent(layer.bounding_box))
        else:
            extents.extend(_primitive_extent(item) for item in layer.primitives)
    extents.extend(
        _point_radius_extent(drill.position, drill.diameter_mm / 2.0)
        for drill in project.drills
    )
    extents.extend(_slot_extent(slot) for slot in project.drill_slots)
    extents.extend(
        _point_radius_extent(position, 0.0)
        for finding in review.findings
        if (position := _finding_position(finding)) is not None
    )
    if not extents:
        return _Extent(0.0, 0.0, _MINIMUM_CANVAS_SPAN, _MINIMUM_CANVAS_SPAN)
    combined = extents[0]
    for extent in extents[1:]:
        combined = combined.include(extent)
    if combined.width == 0.0:
        combined = combined.include(
            _Extent(
                combined.minimum_x - _MINIMUM_CANVAS_SPAN / 2.0,
                combined.minimum_y,
                combined.maximum_x + _MINIMUM_CANVAS_SPAN / 2.0,
                combined.maximum_y,
            )
        )
    if combined.height == 0.0:
        combined = combined.include(
            _Extent(
                combined.minimum_x,
                combined.minimum_y - _MINIMUM_CANVAS_SPAN / 2.0,
                combined.maximum_x,
                combined.maximum_y + _MINIMUM_CANVAS_SPAN / 2.0,
            )
        )
    return combined


def _primitive_extent(primitive: GraphicPrimitive) -> _Extent:
    match primitive:
        case LinePrimitive():
            radius = (
                max(
                    primitive.aperture.width_mm,
                    primitive.aperture.height_mm or 0.0,
                )
                / 2.0
            )
            return _points_extent((primitive.start, primitive.end), radius)
        case ArcPrimitive():
            radius = math.hypot(
                primitive.start.x - primitive.center.x,
                primitive.start.y - primitive.center.y,
            )
            aperture_radius = (
                max(
                    primitive.aperture.width_mm,
                    primitive.aperture.height_mm or 0.0,
                )
                / 2.0
            )
            return _point_radius_extent(primitive.center, radius + aperture_radius)
        case FlashPrimitive():
            radius_x = primitive.aperture.width_mm / 2.0
            radius_y = (
                primitive.aperture.height_mm or primitive.aperture.width_mm
            ) / 2.0
            radius = math.hypot(radius_x, radius_y)
            return _point_radius_extent(primitive.position, radius)
        case RegionPrimitive():
            points = tuple(
                point
                for contour in primitive.contours
                for segment in contour
                for point in _segment_extent_points(segment)
            )
            return _points_extent(points, 0.0)


def _slot_extent(slot: DrillSlot) -> _Extent:
    if slot.kind == "arc" and slot.center is not None:
        radius = math.hypot(
            slot.start.x - slot.center.x,
            slot.start.y - slot.center.y,
        )
        return _point_radius_extent(slot.center, radius + slot.width_mm / 2.0)
    return _points_extent((slot.start, slot.end), slot.width_mm / 2.0)


def _segment_extent_points(segment: RegionSegment) -> tuple[Point, ...]:
    if isinstance(segment, RegionArcSegment):
        radius = math.hypot(
            segment.start.x - segment.center.x,
            segment.start.y - segment.center.y,
        )
        return (
            segment.start,
            segment.end,
            Point(x=segment.center.x - radius, y=segment.center.y - radius),
            Point(x=segment.center.x + radius, y=segment.center.y + radius),
        )
    return (segment.start, segment.end)


def _finding_position(finding: Finding) -> Point | None:
    if finding.location is not None:
        return finding.location
    for evidence in finding.evidence:
        if evidence.witness_bounds is not None:
            bounds = evidence.witness_bounds
            return Point(
                x=(bounds.minimum.x + bounds.maximum.x) / 2.0,
                y=(bounds.minimum.y + bounds.maximum.y) / 2.0,
            )
    return None


def _segments_path(
    segments: tuple[RegionSegment, ...],
    *,
    close: bool,
) -> str:
    first = segments[0]
    commands = [f"M {_point(first.start)}"]
    for segment in segments:
        if isinstance(segment, RegionLineSegment):
            commands.append(f"L {_point(segment.end)}")
        else:
            commands.append(
                _arc_command(
                    segment.start,
                    segment.end,
                    segment.center,
                    segment.clockwise,
                )
            )
    if close:
        commands.append("Z")
    return " ".join(commands)


def _spatial_content_width(
    review: ReviewResult,
    *,
    translate_x: float,
    marker_radius: float,
    font_size: float,
    margin: float,
) -> float:
    right_edges = (
        position.x
        + translate_x
        + marker_radius * 1.5
        + len(finding.finding_id) * font_size * 0.62
        + margin
        for finding in review.findings
        if (position := _finding_position(finding)) is not None
    )
    return max(right_edges, default=0.0)


def _arc_path(start: Point, end: Point, center: Point, clockwise: bool) -> str:
    prefix = f"M {_point(start)}"
    radius = math.hypot(start.x - center.x, start.y - center.y)
    if radius == 0.0:
        return f"{prefix} L {_point(end)}"
    if start == end:
        opposite = Point(
            x=(2.0 * center.x) - start.x,
            y=(2.0 * center.y) - start.y,
        )
        sweep = "0" if clockwise else "1"
        radius_text = _number(radius)
        return (
            f"{prefix} A {radius_text} {radius_text} 0 0 {sweep} "
            f"{_point(opposite)} A {radius_text} {radius_text} 0 0 {sweep} "
            f"{_point(end)}"
        )
    return f"{prefix} {_arc_command(start, end, center, clockwise)}"


def _arc_command(
    start: Point,
    end: Point,
    center: Point,
    clockwise: bool,
) -> str:
    start_radius = math.hypot(start.x - center.x, start.y - center.y)
    end_radius = math.hypot(end.x - center.x, end.y - center.y)
    radius = (start_radius + end_radius) / 2.0
    if radius == 0.0:
        return f"L {_point(end)}"
    if start == end:
        opposite = Point(
            x=(2.0 * center.x) - start.x,
            y=(2.0 * center.y) - start.y,
        )
        sweep = "0" if clockwise else "1"
        radius_text = _number(radius)
        return (
            f"A {radius_text} {radius_text} 0 0 {sweep} {_point(opposite)} "
            f"A {radius_text} {radius_text} 0 0 {sweep} {_point(end)}"
        )
    start_angle = math.atan2(start.y - center.y, start.x - center.x)
    end_angle = math.atan2(end.y - center.y, end.x - center.x)
    span = (
        (start_angle - end_angle) % math.tau
        if clockwise
        else (end_angle - start_angle) % math.tau
    )
    large_arc = "1" if span > math.pi else "0"
    # The containing board group reflects Y; SVG sweep 0 is clockwise in the
    # canonical X-right/Y-up project coordinate system after that reflection.
    sweep = "0" if clockwise else "1"
    radius_text = _number(radius)
    return f"A {radius_text} {radius_text} 0 {large_arc} {sweep} {_point(end)}"


def _slot_path(slot: DrillSlot) -> str:
    if slot.kind == "arc" and slot.center is not None and slot.clockwise is not None:
        return _arc_path(slot.start, slot.end, slot.center, slot.clockwise)
    return f"M {_point(slot.start)} L {_point(slot.end)}"


def _box_extent(box: BoundingBox) -> _Extent:
    return _Extent(
        box.minimum.x,
        box.minimum.y,
        box.maximum.x,
        box.maximum.y,
    )


def _point_radius_extent(point: Point, radius: float) -> _Extent:
    return _Extent(
        point.x - radius,
        point.y - radius,
        point.x + radius,
        point.y + radius,
    )


def _points_extent(points: tuple[Point, ...], radius: float) -> _Extent:
    return _Extent(
        min(point.x for point in points) - radius,
        min(point.y for point in points) - radius,
        max(point.x for point in points) + radius,
        max(point.y for point in points) + radius,
    )


def _legend_width(findings: tuple[Finding, ...], font_size: float) -> float:
    if not findings:
        return 0.0
    longest = max(
        len("Non-spatial findings"),
        *(len(finding.finding_id) + len(finding.title) + 3 for finding in findings),
    )
    return max(_MINIMUM_CANVAS_SPAN, (longest * font_size * 0.62) + (font_size * 2.0))


def _line_cap(aperture: Aperture) -> str:
    if aperture.shape in {ApertureShape.CIRCLE, ApertureShape.OBROUND}:
        return "round"
    return "butt"


def _polarity_stroke(polarity: Polarity, width: float) -> tuple[str, str | None]:
    if polarity is Polarity.DARK:
        return "0.86", None
    dash = f"{_number(width * 2.0)} {_number(width)}"
    if polarity is Polarity.CLEAR:
        return "0.38", dash
    return "0.55", dash


def _polarity_opacity(polarity: Polarity) -> str:
    if polarity is Polarity.DARK:
        return "0.72"
    if polarity is Polarity.CLEAR:
        return "0.24"
    return "0.4"


def _rotation(degrees: float, center: Point) -> str:
    if degrees == 0.0:
        return ""
    return (
        f' transform="rotate({_number(degrees)} {_number(center.x)} '
        f'{_number(center.y)})"'
    )


def _regular_polygon_points(
    center: Point,
    *,
    radius: float,
    vertices: int,
    rotation_degrees: float,
) -> str:
    rotation = math.radians(rotation_degrees)
    return " ".join(
        _point(
            Point(
                x=center.x + radius * math.cos(rotation + math.tau * index / vertices),
                y=center.y + radius * math.sin(rotation + math.tau * index / vertices),
            )
        )
        for index in range(vertices)
    )


def _point(point: Point) -> str:
    return f"{_number(point.x)} {_number(point.y)}"


def _number(value: float) -> str:
    if math.isclose(value, 0.0, abs_tol=0.5 * 10**-_DECIMAL_PLACES):
        return "0"
    text = f"{value:.{_DECIMAL_PLACES}f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _xml_characters(value: str) -> str:
    return "".join(
        character
        if (
            character in "\t\n\r"
            or "\u0020" <= character <= "\ud7ff"
            or "\ue000" <= character <= "\ufffd"
        )
        else "\ufffd"
        for character in value
    )


def _text(value: str) -> str:
    return escape(_xml_characters(value))


def _attr(value: str) -> str:
    return escape(_xml_characters(value), {'"': "&quot;", "'": "&apos;"})
