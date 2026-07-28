"""Local Shapely derivation from analytic BoardGate geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely import affinity
from shapely.geometry import LineString, Polygon, box
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from boardgate.domain.enums import ApertureShape, Polarity
from boardgate.domain.geometry import BoundingBox, Point
from boardgate.domain.layer import (
    ArcPrimitive,
    FlashPrimitive,
    GraphicPrimitive,
    LinePrimitive,
    PCBLayer,
    RegionArcSegment,
    RegionPrimitive,
)
from boardgate.geometry.arcs import approximate_arc


@dataclass(frozen=True, slots=True)
class DerivedGeometry:
    """One local derived geometry plus approximation support status."""

    geometry: BaseGeometry
    error_bound_mm: float
    exact_supported: bool


@dataclass(frozen=True, slots=True)
class LayerComposite:
    """Polarity-composited local geometry for one layer."""

    geometry: BaseGeometry
    primitive_geometries: tuple[tuple[GraphicPrimitive, DerivedGeometry], ...]
    coverage_complete: bool


def _quad_segments(radius: float, chord_error_mm: float) -> int:
    if radius <= chord_error_mm:
        return 4
    ratio = max(-1.0, min(1.0, 1.0 - chord_error_mm / radius))
    angle = math.acos(ratio)
    return max(4, math.ceil(math.pi / (4.0 * angle)))


def _buffer(
    geometry: BaseGeometry,
    radius: float,
    *,
    chord_error_mm: float,
) -> BaseGeometry:
    return geometry.buffer(
        radius,
        quad_segs=_quad_segments(radius, chord_error_mm),
        cap_style="round",
        join_style="round",
    )


def _centerline(
    primitive: LinePrimitive | ArcPrimitive,
    *,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> tuple[LineString, float]:
    if isinstance(primitive, LinePrimitive):
        return (
            LineString(
                (
                    (primitive.start.x, primitive.start.y),
                    (primitive.end.x, primitive.end.y),
                )
            ),
            0.0,
        )
    approximation = approximate_arc(
        primitive.start,
        primitive.end,
        primitive.center,
        clockwise=primitive.clockwise,
        max_chord_error_mm=arc_chord_error_mm,
        geometry_epsilon_mm=geometry_epsilon_mm,
    )
    return (
        LineString((point.x, point.y) for point in approximation.points),
        approximation.total_error_mm,
    )


def _flash_geometry(
    primitive: FlashPrimitive,
    *,
    chord_error_mm: float,
) -> DerivedGeometry:
    aperture = primitive.aperture
    width = aperture.width_mm
    height = aperture.height_mm or width
    origin = primitive.position
    if aperture.shape is ApertureShape.CIRCLE:
        geometry = _buffer(
            ShapelyPoint(origin.x, origin.y),
            width / 2.0,
            chord_error_mm=chord_error_mm,
        )
        return DerivedGeometry(geometry, chord_error_mm, True)
    if aperture.shape is ApertureShape.RECTANGLE:
        geometry = box(
            origin.x - width / 2.0,
            origin.y - height / 2.0,
            origin.x + width / 2.0,
            origin.y + height / 2.0,
        )
        geometry = affinity.rotate(
            geometry,
            aperture.rotation_degrees,
            origin=(origin.x, origin.y),
        )
        return DerivedGeometry(geometry, 0.0, True)
    if aperture.shape is ApertureShape.OBROUND:
        horizontal = width >= height
        radius = min(width, height) / 2.0
        half_axis = max(width, height) / 2.0 - radius
        if horizontal:
            endpoints = (
                (origin.x - half_axis, origin.y),
                (origin.x + half_axis, origin.y),
            )
        else:
            endpoints = (
                (origin.x, origin.y - half_axis),
                (origin.x, origin.y + half_axis),
            )
        geometry = _buffer(
            LineString(endpoints),
            radius,
            chord_error_mm=chord_error_mm,
        )
        geometry = affinity.rotate(
            geometry,
            aperture.rotation_degrees,
            origin=(origin.x, origin.y),
        )
        return DerivedGeometry(geometry, chord_error_mm, True)
    if aperture.shape is ApertureShape.POLYGON and aperture.vertices is not None:
        radius = width / 2.0
        start = math.radians(aperture.rotation_degrees)
        geometry = Polygon(
            (
                origin.x
                + radius * math.cos(start + index * math.tau / aperture.vertices),
                origin.y
                + radius * math.sin(start + index * math.tau / aperture.vertices),
            )
            for index in range(aperture.vertices)
        )
        return DerivedGeometry(geometry, 0.0, True)
    geometry = box(
        origin.x - width / 2.0,
        origin.y - height / 2.0,
        origin.x + width / 2.0,
        origin.y + height / 2.0,
    )
    return DerivedGeometry(geometry, max(width, height) / 2.0, False)


def _region_geometry(
    primitive: RegionPrimitive,
    *,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> DerivedGeometry:
    rings: list[list[tuple[float, float]]] = []
    maximum_error = 0.0
    for contour in primitive.contours:
        points = [contour[0].start]
        for segment in contour:
            if isinstance(segment, RegionArcSegment):
                approximation = approximate_arc(
                    segment.start,
                    segment.end,
                    segment.center,
                    clockwise=segment.clockwise,
                    max_chord_error_mm=arc_chord_error_mm,
                    geometry_epsilon_mm=geometry_epsilon_mm,
                )
                points.extend(approximation.points[1:])
                maximum_error = max(
                    maximum_error,
                    approximation.total_error_mm,
                )
            else:
                points.append(segment.end)
        rings.append([(point.x, point.y) for point in points])
    geometry = Polygon(rings[0], holes=rings[1:])
    return DerivedGeometry(geometry, maximum_error, geometry.is_valid)


def derive_primitive(
    primitive: GraphicPrimitive,
    *,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> DerivedGeometry:
    """Derive local geometry without mutating or serializing Shapely objects."""
    if isinstance(primitive, FlashPrimitive):
        return _flash_geometry(
            primitive,
            chord_error_mm=arc_chord_error_mm,
        )
    if isinstance(primitive, RegionPrimitive):
        return _region_geometry(
            primitive,
            arc_chord_error_mm=arc_chord_error_mm,
            geometry_epsilon_mm=geometry_epsilon_mm,
        )
    centerline, centerline_error = _centerline(
        primitive,
        arc_chord_error_mm=arc_chord_error_mm,
        geometry_epsilon_mm=geometry_epsilon_mm,
    )
    width = primitive.aperture.width_mm
    height = primitive.aperture.height_mm or width
    radius = max(width, height) / 2.0
    geometry = _buffer(
        centerline,
        radius,
        chord_error_mm=arc_chord_error_mm,
    )
    exact = primitive.aperture.shape is ApertureShape.CIRCLE
    return DerivedGeometry(
        geometry=geometry,
        error_bound_mm=centerline_error + arc_chord_error_mm,
        exact_supported=exact,
    )


def composite_layer(
    layer: PCBLayer,
    *,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> LayerComposite:
    """Apply dark union then clear subtraction for one local layer."""
    derived = tuple(
        (
            primitive,
            derive_primitive(
                primitive,
                arc_chord_error_mm=arc_chord_error_mm,
                geometry_epsilon_mm=geometry_epsilon_mm,
            ),
        )
        for primitive in layer.primitives
    )
    dark = unary_union(
        [
            item.geometry
            for primitive, item in derived
            if primitive.polarity is Polarity.DARK
        ]
    )
    clear = unary_union(
        [
            item.geometry
            for primitive, item in derived
            if primitive.polarity is Polarity.CLEAR
        ]
    )
    composite = dark.difference(clear) if not clear.is_empty else dark
    return LayerComposite(
        geometry=composite,
        primitive_geometries=derived,
        coverage_complete=all(item.exact_supported for _, item in derived),
    )


def shapely_bounds(geometry: BaseGeometry) -> BoundingBox | None:
    """Convert local derived bounds back to the strict public domain."""
    if geometry.is_empty:
        return None
    minimum_x, minimum_y, maximum_x, maximum_y = geometry.bounds
    return BoundingBox(
        minimum=Point(x=minimum_x, y=minimum_y),
        maximum=Point(x=maximum_x, y=maximum_y),
    )
