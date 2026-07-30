"""Bounded review-lifetime Shapely derivation from analytic BoardGate geometry."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from shapely import affinity, get_num_coordinates
from shapely.geometry import GeometryCollection, LineString, Polygon, box
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.strtree import STRtree

from boardgate.domain.enums import ApertureShape, Polarity
from boardgate.domain.geometry import BoundingBox, Point
from boardgate.domain.layer import (
    ArcPrimitive,
    BoardOutline,
    FlashPrimitive,
    GraphicPrimitive,
    LinePrimitive,
    PCBLayer,
    RegionArcSegment,
    RegionPrimitive,
)
from boardgate.domain.project import PCBProject
from boardgate.geometry.arcs import GeometryError, approximate_arc
from boardgate.rules.models import GeometryResourcePolicy, RuleCoverageGap

_PAIR_SIZE = 2


class IntersectionCandidateScope(StrEnum):
    """Stable v1 partitions of the per-layer intersection-candidate budget."""

    LAYER_COMPOSITION = "layer_composition"
    TRACE_WIDTH_CONTRIBUTORS = "minimum_trace_width.contributors"
    COPPER_SPACING_CONTRIBUTORS = "minimum_copper_spacing.contributors"
    COPPER_EDGE_CONTRIBUTORS = "minimum_copper_to_edge.contributors"
    SILK_COPPER_CONTRIBUTORS = "silkscreen_over_exposed_pad.copper"
    SILK_MASK_CONTRIBUTORS = "silkscreen_over_exposed_pad.mask"
    SILKSCREEN_CONTRIBUTORS = "silkscreen_over_exposed_pad.silkscreen"
    SOLDER_MASK_DAM_CONTRIBUTORS = "minimum_solder_mask_dam.contributors"
    ANNULAR_DRILL_CANDIDATES = "minimum_annular_ring.drill_candidates"
    ANNULAR_PAD_INTERFERENCE = "minimum_annular_ring.pad_interference"


# These fixed weights are part of geometry resource policy 1.0. Every spatial
# candidate operation belongs to exactly one scope, so the per-scope limits sum
# to (and can never independently reset beyond) the configured per-layer cap.
_INTERSECTION_SCOPE_WEIGHTS: tuple[
    tuple[IntersectionCandidateScope, int],
    ...,
] = (
    (IntersectionCandidateScope.LAYER_COMPOSITION, 32),
    (IntersectionCandidateScope.TRACE_WIDTH_CONTRIBUTORS, 20),
    (IntersectionCandidateScope.COPPER_SPACING_CONTRIBUTORS, 12),
    (IntersectionCandidateScope.COPPER_EDGE_CONTRIBUTORS, 8),
    (IntersectionCandidateScope.SILK_COPPER_CONTRIBUTORS, 4),
    (IntersectionCandidateScope.SILK_MASK_CONTRIBUTORS, 4),
    (IntersectionCandidateScope.SILKSCREEN_CONTRIBUTORS, 4),
    (IntersectionCandidateScope.SOLDER_MASK_DAM_CONTRIBUTORS, 8),
    (IntersectionCandidateScope.ANNULAR_DRILL_CANDIDATES, 4),
    (IntersectionCandidateScope.ANNULAR_PAD_INTERFERENCE, 4),
)
_INTERSECTION_WEIGHT_TOTAL = sum(weight for _, weight in _INTERSECTION_SCOPE_WEIGHTS)


def _intersection_scope_limits(
    maximum: int,
) -> dict[IntersectionCandidateScope, int]:
    """Partition one per-layer maximum without mutable first-come accounting."""
    limits = {
        scope: maximum * weight // _INTERSECTION_WEIGHT_TOTAL
        for scope, weight in _INTERSECTION_SCOPE_WEIGHTS
    }
    remainder_count = maximum - sum(limits.values())
    remainders = sorted(
        (
            (
                -(maximum * weight % _INTERSECTION_WEIGHT_TOTAL),
                index,
                scope,
            )
            for index, (scope, weight) in enumerate(_INTERSECTION_SCOPE_WEIGHTS)
        )
    )
    for _, _, scope in remainders[:remainder_count]:
        limits[scope] += 1
    return limits


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
    error_bound_mm: float
    coverage_gaps: tuple[RuleCoverageGap, ...] = ()
    evaluated_primitive_count: int = 0
    applicable_primitive_count: int = 0
    evaluated_primitive_ids: tuple[str, ...] = ()
    evaluated_dark_primitive_count: int = 0
    polarity_complete: bool = True
    geometry_supported: bool = True


@dataclass(frozen=True, slots=True)
class ComponentPairQuery:
    """Stable bounded component-pair candidates."""

    pairs: tuple[tuple[int, int, float], ...]
    coverage_gaps: tuple[RuleCoverageGap, ...] = ()
    evaluated_pair_count: int = 0
    complete: bool = True


@dataclass(frozen=True, slots=True)
class PrimitiveQueryBatch:
    """Bounded stable primitive candidates for a deterministic witness batch."""

    matches: tuple[
        tuple[tuple[GraphicPrimitive, DerivedGeometry], ...],
        ...,
    ]
    coverage_gaps: tuple[RuleCoverageGap, ...] = ()
    candidate_count: int = 0
    complete: bool = True


def _quad_segments(radius: float, chord_error_mm: float) -> int:
    if radius <= chord_error_mm:
        return 4
    ratio = chord_error_mm / radius
    if ratio <= 0.0:
        return 2**63
    half_angle = math.asin(math.sqrt(min(1.0, ratio / 2.0)))
    angle = 2.0 * half_angle
    if angle <= 0.0:
        return 2**63
    return max(4, math.ceil(math.pi / (4.0 * angle)))


def _primitive_support_hint(primitive: GraphicPrimitive) -> bool:
    if isinstance(primitive, FlashPrimitive):
        return primitive.aperture.shape in {
            ApertureShape.CIRCLE,
            ApertureShape.RECTANGLE,
            ApertureShape.OBROUND,
            ApertureShape.POLYGON,
        }
    if isinstance(primitive, RegionPrimitive):
        return True
    return primitive.aperture.shape is ApertureShape.CIRCLE


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


def _stable_geometry_key(
    geometry: BaseGeometry,
) -> tuple[float, ...] | tuple[object, ...]:
    return (*geometry.bounds, geometry.wkb_hex)


def _geometry_collection(geometries: Iterable[BaseGeometry]) -> BaseGeometry:
    ordered = tuple(
        sorted(
            (geometry for geometry in geometries if not geometry.is_empty),
            key=_stable_geometry_key,
        )
    )
    if not ordered:
        return GeometryCollection()
    if len(ordered) == 1:
        return ordered[0]
    return GeometryCollection(ordered)


def _bounded_union(
    geometries: Iterable[BaseGeometry],
    *,
    batch_size: int,
) -> BaseGeometry:
    current = tuple(
        sorted(
            (geometry for geometry in geometries if not geometry.is_empty),
            key=_stable_geometry_key,
        )
    )
    if not current:
        return GeometryCollection()
    while len(current) > 1:
        next_level: list[BaseGeometry] = []
        for offset in range(0, len(current), batch_size):
            batch = current[offset : offset + batch_size]
            next_level.append(batch[0] if len(batch) == 1 else unary_union(batch))
        current = tuple(sorted(next_level, key=_stable_geometry_key))
    return current[0]


def _connected_groups(
    geometries: tuple[BaseGeometry, ...],
    *,
    candidate_limit: int,
) -> tuple[tuple[tuple[int, ...], ...], int, bool]:
    """Return exact intersecting groups and whether candidate enumeration completed."""
    if not geometries:
        return (), 0, True
    parents = list(range(len(geometries)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def connect(first: int, second: int) -> None:
        first_root = root(first)
        second_root = root(second)
        if first_root == second_root:
            return
        if first_root < second_root:
            parents[second_root] = first_root
        else:
            parents[first_root] = second_root

    tree = STRtree(geometries)
    candidate_count = 0
    for first_index, geometry in enumerate(geometries):
        for raw_index in sorted(int(value) for value in tree.query(geometry)):
            if raw_index <= first_index:
                continue
            candidate_count += 1
            if candidate_count > candidate_limit:
                return (), candidate_count, False
            if geometry.intersects(geometries[raw_index]):
                connect(first_index, raw_index)
    groups: dict[int, list[int]] = {}
    for index in range(len(geometries)):
        groups.setdefault(root(index), []).append(index)
    return (
        tuple(
            sorted(
                (tuple(indices) for indices in groups.values()),
                key=lambda indices: indices[0],
            )
        ),
        candidate_count,
        True,
    )


def _arc_point_count(
    primitive: ArcPrimitive | RegionArcSegment,
    *,
    chord_error_mm: float,
    geometry_epsilon_mm: float,
    saturation: int,
) -> int:
    """Count analytic approximation points in O(1) without allocating them."""
    start_radius = math.hypot(
        primitive.start.x - primitive.center.x,
        primitive.start.y - primitive.center.y,
    )
    end_radius = math.hypot(
        primitive.end.x - primitive.center.x,
        primitive.end.y - primitive.center.y,
    )
    if start_radius <= geometry_epsilon_mm or end_radius <= geometry_epsilon_mm:
        raise GeometryError("arc radius is too small for geometry tolerance")
    radial_mismatch = abs(start_radius - end_radius) / 2.0
    if radial_mismatch > geometry_epsilon_mm:
        raise GeometryError("arc endpoints do not share a radius within tolerance")
    radius = (start_radius + end_radius) / 2.0
    start_angle = math.atan2(
        primitive.start.y - primitive.center.y,
        primitive.start.x - primitive.center.x,
    )
    end_angle = math.atan2(
        primitive.end.y - primitive.center.y,
        primitive.end.x - primitive.center.x,
    )
    closed = (
        math.dist(
            (primitive.start.x, primitive.start.y),
            (primitive.end.x, primitive.end.y),
        )
        <= geometry_epsilon_mm
    )
    if closed:
        sweep = math.tau
    elif primitive.clockwise:
        sweep = (start_angle - end_angle) % math.tau
    else:
        sweep = (end_angle - start_angle) % math.tau
    if math.isclose(sweep, 0.0, abs_tol=1e-15):
        raise GeometryError("arc sweep is zero")
    if chord_error_mm >= radius:
        maximum_angle = math.pi
    else:
        ratio = chord_error_mm / radius
        if ratio <= 0.0:
            return saturation
        maximum_angle = 4.0 * math.asin(math.sqrt(min(0.5, ratio / 2.0)))
    if maximum_angle <= 0.0:
        return saturation
    segment_count = math.ceil(sweep / maximum_angle)
    return min(saturation, segment_count + 1)


def _saturated_count(
    *,
    factor: int,
    value: int,
    offset: int,
    saturation: int,
) -> int:
    if value >= saturation:
        return saturation
    return min(saturation, factor * value + offset)


def _primitive_coordinate_upper_bound(  # noqa: PLR0911
    primitive: GraphicPrimitive,
    *,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
    saturation: int,
) -> int:
    """Estimate a conservative coordinate upper bound without entering GEOS."""
    if isinstance(primitive, RegionPrimitive):
        count = 0
        for contour in primitive.contours:
            count += 1
            for segment in contour:
                count += (
                    _arc_point_count(
                        segment,
                        chord_error_mm=arc_chord_error_mm,
                        geometry_epsilon_mm=geometry_epsilon_mm,
                        saturation=saturation,
                    )
                    - 1
                    if isinstance(segment, RegionArcSegment)
                    else 1
                )
                if count >= saturation:
                    return saturation
        return count
    if isinstance(primitive, FlashPrimitive):
        aperture = primitive.aperture
        if aperture.shape is ApertureShape.CIRCLE:
            return _saturated_count(
                factor=4,
                value=_quad_segments(
                    aperture.width_mm / 2.0,
                    arc_chord_error_mm,
                ),
                offset=1,
                saturation=saturation,
            )
        if aperture.shape is ApertureShape.OBROUND:
            radius = (
                min(
                    aperture.width_mm,
                    aperture.height_mm or aperture.width_mm,
                )
                / 2.0
            )
            return _saturated_count(
                factor=4,
                value=_quad_segments(radius, arc_chord_error_mm),
                offset=3,
                saturation=saturation,
            )
        if aperture.shape is ApertureShape.POLYGON:
            return min(saturation, (aperture.vertices or 4) + 1)
        return 5
    aperture_radius = (
        max(
            primitive.aperture.width_mm,
            primitive.aperture.height_mm or primitive.aperture.width_mm,
        )
        / 2.0
    )
    quad_segments = _quad_segments(aperture_radius, arc_chord_error_mm)
    if isinstance(primitive, ArcPrimitive):
        buffered_curve = _arc_point_count(
            primitive,
            chord_error_mm=arc_chord_error_mm,
            geometry_epsilon_mm=geometry_epsilon_mm,
            saturation=saturation,
        )
        if buffered_curve >= saturation or quad_segments >= saturation:
            return saturation
        return min(saturation, 3 * buffered_curve + 4 * quad_segments + 4)
    return _saturated_count(
        factor=4,
        value=quad_segments,
        offset=3,
        saturation=saturation,
    )


class DerivedGeometryWorkspace:
    """One-review cache for bounded Shapely derivation and spatial indexes."""

    def __init__(
        self,
        *,
        project: PCBProject | None = None,
        policy: GeometryResourcePolicy | None = None,
    ) -> None:
        self.policy = policy or GeometryResourcePolicy()
        self._review_primitive_count = (
            sum(len(layer.primitives) for layer in project.layers)
            if project is not None
            else None
        )
        self._derived: dict[
            tuple[str, str, str, float, float],
            DerivedGeometry,
        ] = {}
        self._composites: dict[
            tuple[str, str, float, float],
            LayerComposite,
        ] = {}
        self._primitive_indexes: dict[
            tuple[str, str, float, float],
            tuple[
                tuple[tuple[GraphicPrimitive, DerivedGeometry], ...],
                STRtree,
            ],
        ] = {}
        self._contributor_queries: dict[
            tuple[
                str,
                str,
                IntersectionCandidateScope,
                float,
                float,
                float,
                tuple[int, ...],
            ],
            tuple[tuple[BaseGeometry, ...], PrimitiveQueryBatch],
        ] = {}
        self._contributor_scope_keys: dict[
            tuple[str, str, IntersectionCandidateScope],
            tuple[
                str,
                str,
                IntersectionCandidateScope,
                float,
                float,
                float,
                tuple[int, ...],
            ],
        ] = {}
        self._board_material: dict[str, BaseGeometry] = {}
        self._components: dict[
            int,
            tuple[BaseGeometry, tuple[BaseGeometry, ...]],
        ] = {}

    @staticmethod
    def _layer_key(layer: PCBLayer) -> tuple[str, str]:
        return (layer.source_file_id, layer.layer_id)

    def _gap(  # noqa: PLR0913
        self,
        layer: PCBLayer,
        *,
        metric: str,
        unit: Literal["primitives", "coordinates", "candidates"],
        observed: int,
        limit: int,
        scope: str,
    ) -> RuleCoverageGap:
        return RuleCoverageGap(
            policy_version=self.policy.policy_version,
            source_file_id=layer.source_file_id,
            layer_id=layer.layer_id,
            metric=metric,
            unit=unit,
            observed=observed,
            limit=limit,
            summary=(
                f"{scope} requires {observed} {unit}, exceeding the deterministic "
                f"limit of {limit}."
            ),
        )

    def intersection_candidate_limit(
        self,
        scope: IntersectionCandidateScope,
    ) -> int:
        """Return one fixed scope's share of the per-layer v1 candidate cap."""
        return _intersection_scope_limits(
            self.policy.max_intersection_candidates_per_layer
        )[scope]

    def derive(
        self,
        layer: PCBLayer,
        primitive: GraphicPrimitive,
        *,
        arc_chord_error_mm: float,
        geometry_epsilon_mm: float,
    ) -> DerivedGeometry:
        """Derive one primitive once within this workspace."""
        key = (
            layer.source_file_id,
            layer.layer_id,
            primitive.primitive_id,
            arc_chord_error_mm,
            geometry_epsilon_mm,
        )
        cached = self._derived.get(key)
        if cached is None:
            cached = derive_primitive(
                primitive,
                arc_chord_error_mm=arc_chord_error_mm,
                geometry_epsilon_mm=geometry_epsilon_mm,
            )
            self._derived[key] = cached
        return cached

    def _limited_composite(
        self,
        layer: PCBLayer,
        gap: RuleCoverageGap,
        *additional_gaps: RuleCoverageGap,
    ) -> LayerComposite:
        return LayerComposite(
            geometry=GeometryCollection(),
            primitive_geometries=(),
            coverage_complete=False,
            error_bound_mm=0.0,
            coverage_gaps=(gap, *additional_gaps),
            evaluated_primitive_count=0,
            applicable_primitive_count=len(layer.primitives),
            evaluated_primitive_ids=(),
            evaluated_dark_primitive_count=0,
            polarity_complete=all(
                primitive.polarity in {Polarity.DARK, Polarity.CLEAR}
                for primitive in layer.primitives
            ),
            geometry_supported=all(
                _primitive_support_hint(primitive) for primitive in layer.primitives
            ),
        )

    def composite_layer(  # noqa: PLR0911, PLR0912, PLR0915
        self,
        layer: PCBLayer,
        *,
        arc_chord_error_mm: float,
        geometry_epsilon_mm: float,
    ) -> LayerComposite:
        """Compose one layer once using deterministic spatial groups and budgets."""
        key = (
            *self._layer_key(layer),
            arc_chord_error_mm,
            geometry_epsilon_mm,
        )
        cached = self._composites.get(key)
        if cached is not None:
            return cached
        primitive_count = len(layer.primitives)
        if (
            self._review_primitive_count is not None
            and self._review_primitive_count > self.policy.max_primitives_per_review
        ):
            result = self._limited_composite(
                layer,
                self._gap(
                    layer,
                    metric="review_primitive_count",
                    unit="primitives",
                    observed=self._review_primitive_count,
                    limit=self.policy.max_primitives_per_review,
                    scope="The review geometry inventory",
                ),
            )
            self._composites[key] = result
            return result
        if primitive_count > self.policy.max_primitives_per_layer:
            result = self._limited_composite(
                layer,
                self._gap(
                    layer,
                    metric="layer_primitive_count",
                    unit="primitives",
                    observed=primitive_count,
                    limit=self.policy.max_primitives_per_layer,
                    scope="The layer",
                ),
            )
            self._composites[key] = result
            return result
        polarity_complete = all(
            primitive.polarity in {Polarity.DARK, Polarity.CLEAR}
            for primitive in layer.primitives
        )
        if not polarity_complete:
            result = LayerComposite(
                geometry=GeometryCollection(),
                primitive_geometries=(),
                coverage_complete=False,
                error_bound_mm=0.0,
                evaluated_primitive_count=0,
                applicable_primitive_count=primitive_count,
                evaluated_dark_primitive_count=0,
                polarity_complete=False,
                geometry_supported=all(
                    _primitive_support_hint(primitive) for primitive in layer.primitives
                ),
            )
            self._composites[key] = result
            return result

        coordinate_saturation = self.policy.max_derived_coordinates_per_layer + 1
        coordinate_upper_bound = 0
        for primitive in layer.primitives:
            coordinate_upper_bound = min(
                coordinate_saturation,
                coordinate_upper_bound
                + _primitive_coordinate_upper_bound(
                    primitive,
                    arc_chord_error_mm=arc_chord_error_mm,
                    geometry_epsilon_mm=geometry_epsilon_mm,
                    saturation=coordinate_saturation,
                ),
            )
            if coordinate_upper_bound >= coordinate_saturation:
                break
        if coordinate_upper_bound > self.policy.max_derived_coordinates_per_layer:
            result = self._limited_composite(
                layer,
                self._gap(
                    layer,
                    metric="derived_coordinate_upper_bound",
                    unit="coordinates",
                    observed=coordinate_upper_bound,
                    limit=self.policy.max_derived_coordinates_per_layer,
                    scope="The preflight derived layer geometry",
                ),
            )
            self._composites[key] = result
            return result

        derived = tuple(
            (
                primitive,
                self.derive(
                    layer,
                    primitive,
                    arc_chord_error_mm=arc_chord_error_mm,
                    geometry_epsilon_mm=geometry_epsilon_mm,
                ),
            )
            for primitive in layer.primitives
        )
        coordinate_count = sum(
            get_num_coordinates(item.geometry) for _, item in derived
        )
        if coordinate_count > self.policy.max_derived_coordinates_per_layer:
            result = self._limited_composite(
                layer,
                self._gap(
                    layer,
                    metric="derived_coordinate_count",
                    unit="coordinates",
                    observed=coordinate_count,
                    limit=self.policy.max_derived_coordinates_per_layer,
                    scope="The derived layer geometry",
                ),
            )
            self._composites[key] = result
            return result
        exact_supported = all(item.exact_supported for _, item in derived)
        if not exact_supported:
            result = LayerComposite(
                geometry=GeometryCollection(),
                primitive_geometries=derived,
                coverage_complete=False,
                error_bound_mm=max(
                    (item.error_bound_mm for _, item in derived),
                    default=0.0,
                ),
                evaluated_primitive_count=primitive_count,
                applicable_primitive_count=primitive_count,
                evaluated_primitive_ids=tuple(
                    primitive.primitive_id for primitive, _ in derived
                ),
                evaluated_dark_primitive_count=sum(
                    primitive.polarity is Polarity.DARK for primitive, _ in derived
                ),
                polarity_complete=True,
                geometry_supported=False,
            )
            self._composites[key] = result
            return result

        known_by_polarity = {
            polarity: tuple(
                (primitive, item)
                for primitive, item in derived
                if primitive.polarity is polarity
            )
            for polarity in (Polarity.DARK, Polarity.CLEAR)
        }
        composed_by_polarity: dict[
            Polarity,
            tuple[BaseGeometry, ...],
        ] = {}
        gaps: list[RuleCoverageGap] = []
        evaluated_indices: set[tuple[Polarity, int]] = set()
        composition_limit = self.intersection_candidate_limit(
            IntersectionCandidateScope.LAYER_COMPOSITION
        )
        remaining_candidates = composition_limit
        clear_subset_omitted = False
        grouping_failed = False
        for polarity, items in known_by_polarity.items():
            geometries = tuple(item.geometry for _, item in items)
            used_candidates = composition_limit - remaining_candidates
            groups, candidate_count, complete = _connected_groups(
                geometries,
                candidate_limit=remaining_candidates,
            )
            remaining_candidates -= min(candidate_count, remaining_candidates)
            if not complete:
                gaps.append(
                    self._gap(
                        layer,
                        metric="intersection_candidate_count",
                        unit="candidates",
                        observed=used_candidates + candidate_count,
                        limit=composition_limit,
                        scope=(
                            f"The {polarity.value} spatial grouping in the fixed "
                            "layer_composition reservation"
                        ),
                    )
                )
                composed_by_polarity[polarity] = ()
                grouping_failed = True
                if polarity is Polarity.CLEAR:
                    clear_subset_omitted = True
                continue
            composed: list[BaseGeometry] = []
            for indices in groups:
                if len(indices) > self.policy.max_primitives_per_connected_subset:
                    gaps.append(
                        self._gap(
                            layer,
                            metric="connected_subset_primitive_count",
                            unit="primitives",
                            observed=len(indices),
                            limit=self.policy.max_primitives_per_connected_subset,
                            scope=f"A {polarity.value} connected subset",
                        )
                    )
                    if polarity is Polarity.CLEAR:
                        clear_subset_omitted = True
                    continue
                composed.append(
                    _bounded_union(
                        (geometries[index] for index in indices),
                        batch_size=self.policy.max_union_inputs_per_batch,
                    )
                )
                evaluated_indices.update((polarity, index) for index in indices)
            composed_by_polarity[polarity] = tuple(composed)

        if grouping_failed or clear_subset_omitted:
            first_gap, *additional_gaps = gaps
            result = self._limited_composite(
                layer,
                first_gap,
                *additional_gaps,
            )
            self._composites[key] = result
            return result

        dark = composed_by_polarity.get(Polarity.DARK, ())
        clear = composed_by_polarity.get(Polarity.CLEAR, ())
        if clear and dark:
            clear_tree = STRtree(clear)
            final_dark: list[BaseGeometry] = []
            for dark_geometry in dark:
                clear_indices = tuple(
                    sorted(int(value) for value in clear_tree.query(dark_geometry))
                )
                observed_candidate_count = (
                    composition_limit - remaining_candidates + len(clear_indices)
                )
                if len(clear_indices) > remaining_candidates:
                    gap = self._gap(
                        layer,
                        metric="intersection_candidate_count",
                        unit="candidates",
                        observed=observed_candidate_count,
                        limit=composition_limit,
                        scope=(
                            "The cumulative fixed layer_composition candidate "
                            "reservation"
                        ),
                    )
                    result = self._limited_composite(
                        layer,
                        gap,
                        *gaps,
                    )
                    self._composites[key] = result
                    return result
                remaining_candidates -= len(clear_indices)
                relevant_clear = tuple(
                    clear[index]
                    for index in clear_indices
                    if dark_geometry.intersects(clear[index])
                )
                final_dark.append(
                    dark_geometry.difference(
                        _bounded_union(
                            relevant_clear,
                            batch_size=self.policy.max_union_inputs_per_batch,
                        )
                    )
                    if relevant_clear
                    else dark_geometry
                )
        else:
            final_dark = list(dark)

        result = LayerComposite(
            geometry=_geometry_collection(final_dark),
            primitive_geometries=derived,
            coverage_complete=not gaps,
            error_bound_mm=max(
                (item.error_bound_mm for _, item in derived),
                default=0.0,
            ),
            coverage_gaps=tuple(gaps),
            evaluated_primitive_count=len(evaluated_indices),
            applicable_primitive_count=primitive_count,
            evaluated_primitive_ids=tuple(
                primitive.primitive_id
                for polarity, items in known_by_polarity.items()
                for index, (primitive, _) in enumerate(items)
                if (polarity, index) in evaluated_indices
            ),
            evaluated_dark_primitive_count=sum(
                1
                for polarity, index in evaluated_indices
                if polarity is Polarity.DARK
                and index < len(known_by_polarity[Polarity.DARK])
            ),
            polarity_complete=True,
            geometry_supported=True,
        )
        self._composites[key] = result
        return result

    def primitive_index(
        self,
        layer: PCBLayer,
        *,
        arc_chord_error_mm: float,
        geometry_epsilon_mm: float,
    ) -> tuple[
        tuple[tuple[GraphicPrimitive, DerivedGeometry], ...],
        STRtree,
    ]:
        """Return the cached stable per-layer primitive STRtree."""
        key = (
            *self._layer_key(layer),
            arc_chord_error_mm,
            geometry_epsilon_mm,
        )
        cached = self._primitive_indexes.get(key)
        if cached is not None:
            return cached
        composite = self.composite_layer(
            layer,
            arc_chord_error_mm=arc_chord_error_mm,
            geometry_epsilon_mm=geometry_epsilon_mm,
        )
        items = composite.primitive_geometries
        tree = STRtree(tuple(item.geometry for _, item in items))
        cached = (items, tree)
        self._primitive_indexes[key] = cached
        return cached

    def query_primitives(  # noqa: PLR0913
        self,
        layer: PCBLayer,
        witnesses: tuple[BaseGeometry, ...],
        *,
        scope: IntersectionCandidateScope,
        arc_chord_error_mm: float,
        geometry_epsilon_mm: float,
        witness_buffer_mm: float,
    ) -> PrimitiveQueryBatch:
        """Run one query in a stable partition of the per-layer candidate cap."""
        if witness_buffer_mm < 0.0 or not math.isfinite(witness_buffer_mm):
            raise ValueError("witness buffer must be finite and non-negative")
        cache_key = (
            *self._layer_key(layer),
            scope,
            arc_chord_error_mm,
            geometry_epsilon_mm,
            witness_buffer_mm,
            tuple(id(witness) for witness in witnesses),
        )
        scope_key = (*self._layer_key(layer), scope)
        prior_scope_key = self._contributor_scope_keys.get(scope_key)
        if prior_scope_key is not None and prior_scope_key != cache_key:
            msg = (
                f"intersection candidate scope {scope.value!r} accepts one "
                "deterministic witness batch per layer and review"
            )
            raise ValueError(msg)
        self._contributor_scope_keys[scope_key] = cache_key
        cached = self._contributor_queries.get(cache_key)
        if cached is not None and all(
            cached_witness is witness
            for cached_witness, witness in zip(
                cached[0],
                witnesses,
                strict=True,
            )
        ):
            return cached[1]
        items, tree = self.primitive_index(
            layer,
            arc_chord_error_mm=arc_chord_error_mm,
            geometry_epsilon_mm=geometry_epsilon_mm,
        )
        if not items or not witnesses:
            result = PrimitiveQueryBatch(
                matches=tuple(() for _ in witnesses),
            )
            self._contributor_queries[cache_key] = (witnesses, result)
            return result
        candidate_count = 0
        candidate_limit = self.intersection_candidate_limit(scope)
        matches: list[tuple[tuple[GraphicPrimitive, DerivedGeometry], ...]] = []
        for witness in witnesses:
            query = (
                witness.buffer(witness_buffer_mm)
                if witness_buffer_mm > 0.0
                else witness
            )
            candidate_indices = tuple(sorted(int(value) for value in tree.query(query)))
            candidate_count += len(candidate_indices)
            if candidate_count > candidate_limit:
                result = PrimitiveQueryBatch(
                    matches=(),
                    coverage_gaps=(
                        self._gap(
                            layer,
                            metric="primitive_query_candidate_count",
                            unit="candidates",
                            observed=candidate_count,
                            limit=candidate_limit,
                            scope=(
                                f"The fixed {scope.value} reservation within the "
                                "per-layer intersection-candidate policy"
                            ),
                        ),
                    ),
                    candidate_count=candidate_count,
                    complete=False,
                )
                self._contributor_queries[cache_key] = (witnesses, result)
                return result
            matches.append(
                tuple(
                    items[index]
                    for index in candidate_indices
                    if items[index][1].geometry.intersects(query)
                )
            )
        result = PrimitiveQueryBatch(
            matches=tuple(matches),
            candidate_count=candidate_count,
        )
        self._contributor_queries[cache_key] = (witnesses, result)
        return result

    def geometry_components(
        self,
        geometry: BaseGeometry,
    ) -> tuple[BaseGeometry, ...]:
        """Return stable final components cached within this review."""
        key = id(geometry)
        cached = self._components.get(key)
        if cached is not None and cached[0] is geometry:
            return cached[1]
        components = geometry_components(geometry)
        self._components[key] = (geometry, components)
        return components

    def component_pairs_within(
        self,
        components: tuple[BaseGeometry, ...],
        *,
        maximum_distance: float,
        layer: PCBLayer,
    ) -> ComponentPairQuery:
        """Return stable unique component pairs, bounded before publication."""
        if maximum_distance < 0.0 or not math.isfinite(maximum_distance):
            raise ValueError(
                "maximum component distance must be finite and non-negative"
            )
        if len(components) < _PAIR_SIZE:
            return ComponentPairQuery(
                (),
                evaluated_pair_count=0,
            )
        tree = STRtree(components)
        pairs: list[tuple[int, int, float]] = []
        candidate_count = 0
        evaluated_pair_count = 0
        for first_index, component in enumerate(components):
            candidate_indices = tree.query(
                component,
                predicate="dwithin",
                distance=maximum_distance,
            )
            for second_index in sorted(int(value) for value in candidate_indices):
                if second_index <= first_index:
                    continue
                candidate_count += 1
                if candidate_count > self.policy.max_component_pair_candidates:
                    return ComponentPairQuery(
                        pairs=tuple(sorted(pairs)),
                        coverage_gaps=(
                            self._gap(
                                layer,
                                metric="component_pair_candidate_count",
                                unit="candidates",
                                observed=candidate_count,
                                limit=self.policy.max_component_pair_candidates,
                                scope="The component-pair query",
                            ),
                        ),
                        evaluated_pair_count=evaluated_pair_count,
                        complete=False,
                    )
                distance = component.distance(components[second_index])
                if distance <= maximum_distance or math.isclose(
                    distance,
                    maximum_distance,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ):
                    pairs.append((first_index, second_index, distance))
                evaluated_pair_count += 1
        return ComponentPairQuery(
            tuple(sorted(pairs)),
            evaluated_pair_count=len(components) * (len(components) - 1) // 2,
        )

    def board_material_geometry(self, outline: BoardOutline) -> BaseGeometry:
        """Derive and cache board material as outer regions minus cutouts."""
        key = outline.model_dump_json()
        cached = self._board_material.get(key)
        if cached is not None:
            return cached
        outer = _bounded_union(
            (
                Polygon((point.x, point.y) for point in contour.points)
                for contour in outline.contours
                if contour.kind == "outer"
            ),
            batch_size=self.policy.max_union_inputs_per_batch,
        )
        cutouts = _bounded_union(
            (
                Polygon((point.x, point.y) for point in contour.points)
                for contour in outline.contours
                if contour.kind == "cutout"
            ),
            batch_size=self.policy.max_union_inputs_per_batch,
        )
        material = outer.difference(cutouts) if not cutouts.is_empty else outer
        self._board_material[key] = material
        return material

    def bounded_union(self, geometries: Iterable[BaseGeometry]) -> BaseGeometry:
        """Union a bounded local subset using the policy's fixed fan-in."""
        return _bounded_union(
            geometries,
            batch_size=self.policy.max_union_inputs_per_batch,
        )


def composite_layer(
    layer: PCBLayer,
    *,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> LayerComposite:
    """Backward-compatible one-shot layer composition."""
    return DerivedGeometryWorkspace().composite_layer(
        layer,
        arc_chord_error_mm=arc_chord_error_mm,
        geometry_epsilon_mm=geometry_epsilon_mm,
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


def geometry_components(geometry: BaseGeometry) -> tuple[BaseGeometry, ...]:
    """Recursively flatten final polygonal geometry into stable components."""
    if geometry.is_empty:
        return ()
    if geometry.geom_type == "Polygon":
        return (geometry,)
    if not hasattr(geometry, "geoms"):
        return ()
    components = tuple(
        component
        for child in geometry.geoms
        for component in geometry_components(child)
        if not component.is_empty and component.area > 0.0
    )
    return tuple(sorted(components, key=_stable_geometry_key))


def component_pairs_within(
    components: tuple[BaseGeometry, ...],
    *,
    maximum_distance: float,
) -> tuple[tuple[int, int, float], ...]:
    """Backward-compatible unscoped component query using the fixed budget."""
    if maximum_distance < 0.0 or not math.isfinite(maximum_distance):
        raise ValueError("maximum component distance must be finite and non-negative")
    if len(components) < _PAIR_SIZE:
        return ()
    tree = STRtree(components)
    pairs: list[tuple[int, int, float]] = []
    for first_index, component in enumerate(components):
        for second_index in sorted(
            int(value)
            for value in tree.query(
                component,
                predicate="dwithin",
                distance=maximum_distance,
            )
        ):
            if second_index <= first_index:
                continue
            distance = component.distance(components[second_index])
            if distance <= maximum_distance or math.isclose(
                distance,
                maximum_distance,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                pairs.append((first_index, second_index, distance))
    return tuple(sorted(pairs))


def board_material_geometry(outline: BoardOutline) -> BaseGeometry:
    """Backward-compatible one-shot board material derivation."""
    return DerivedGeometryWorkspace().board_material_geometry(outline)
