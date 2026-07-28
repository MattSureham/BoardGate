"""Trusted analytic board-outline reconstruction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from shapely.geometry import Polygon

from boardgate import __version__
from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import LayerRole, Polarity, RiskMode
from boardgate.domain.geometry import BoundingBox, Point
from boardgate.domain.identifiers import object_id
from boardgate.domain.layer import (
    ArcPrimitive,
    BoardOutline,
    LinePrimitive,
    OutlineContour,
    PCBLayer,
    RegionArcSegment,
    RegionLineSegment,
    RegionSegment,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import Uncertainty
from boardgate.geometry.arcs import GeometryError, approximate_arc

_CYCLE_NODE_DEGREE = 2


class OutlineReconstruction(VersionedModel):
    """Board outline plus every topology uncertainty."""

    outline: BoardOutline | None = None
    uncertainties: tuple[Uncertainty, ...] = ()


@dataclass(frozen=True, slots=True)
class _Endpoint:
    edge_index: int
    is_start: bool
    point: Point
    primitive_id: str


@dataclass(slots=True)
class _Cluster:
    endpoints: list[_Endpoint]

    @property
    def representative(self) -> Point:
        return Point(
            x=sum(endpoint.point.x for endpoint in self.endpoints)
            / len(self.endpoints),
            y=sum(endpoint.point.y for endpoint in self.endpoints)
            / len(self.endpoints),
        )


@dataclass(frozen=True, slots=True)
class _Edge:
    primitive: LinePrimitive | ArcPrimitive
    start_node: int
    end_node: int


@dataclass(frozen=True, slots=True)
class _Loop:
    segments: tuple[RegionSegment, ...]
    points: tuple[Point, ...]
    source_ids: tuple[str, ...]
    snap_error_mm: float
    approximation_error_mm: float
    polygon: Polygon


def _uncertainty(
    summary: str,
    *,
    layers: tuple[PCBLayer, ...],
    candidates: tuple[str, ...] = (),
) -> OutlineReconstruction:
    evidence = tuple(
        Provenance(
            source_file_id=layer.source_file_id,
            parser="boardgate-outline-reconstructor",
            parser_version=__version__,
            metadata={"layer_id": layer.layer_id},
        )
        for layer in layers
    )
    return OutlineReconstruction(
        uncertainties=(
            Uncertainty(
                risk_mode=RiskMode.OUTLINE_UNCERTAIN,
                subject="board_outline",
                summary=summary,
                candidates=candidates,
                evidence=evidence,
            ),
        )
    )


def _cluster_endpoints(
    primitives: tuple[LinePrimitive | ArcPrimitive, ...],
    tolerance: float,
) -> tuple[tuple[_Cluster, ...], tuple[tuple[int, int], ...], float]:
    endpoints = [
        _Endpoint(index, is_start, point, primitive.primitive_id)
        for index, primitive in enumerate(primitives)
        for is_start, point in ((True, primitive.start), (False, primitive.end))
    ]
    endpoints.sort(
        key=lambda endpoint: (
            endpoint.point.x,
            endpoint.point.y,
            endpoint.primitive_id,
            not endpoint.is_start,
        )
    )
    clusters: list[_Cluster] = []
    assignments: dict[tuple[int, bool], int] = {}
    for endpoint in endpoints:
        matches = [
            index
            for index, cluster in enumerate(clusters)
            if math.dist(
                (endpoint.point.x, endpoint.point.y),
                (
                    cluster.representative.x,
                    cluster.representative.y,
                ),
            )
            <= tolerance
        ]
        if len(matches) > 1:
            raise GeometryError("endpoint lies within multiple snap clusters")
        if matches:
            cluster_index = matches[0]
            clusters[cluster_index].endpoints.append(endpoint)
            representative = clusters[cluster_index].representative
            if any(
                math.dist(
                    (member.point.x, member.point.y),
                    (representative.x, representative.y),
                )
                > tolerance
                for member in clusters[cluster_index].endpoints
            ):
                raise GeometryError("endpoint snap cluster exceeds tolerance")
        else:
            cluster_index = len(clusters)
            clusters.append(_Cluster([endpoint]))
        assignments[(endpoint.edge_index, endpoint.is_start)] = cluster_index
    edge_nodes = tuple(
        (
            assignments[(index, True)],
            assignments[(index, False)],
        )
        for index in range(len(primitives))
    )
    maximum_error = max(
        (
            math.dist(
                (endpoint.point.x, endpoint.point.y),
                (
                    clusters[node].representative.x,
                    clusters[node].representative.y,
                ),
            )
            for endpoint in endpoints
            for node in (assignments[(endpoint.edge_index, endpoint.is_start)],)
        ),
        default=0.0,
    )
    return tuple(clusters), edge_nodes, maximum_error


def _graph_edges(
    primitives: tuple[LinePrimitive | ArcPrimitive, ...],
    edge_nodes: tuple[tuple[int, int], ...],
) -> tuple[_Edge, ...]:
    return tuple(
        _Edge(primitive, nodes[0], nodes[1])
        for primitive, nodes in zip(primitives, edge_nodes, strict=True)
    )


def _oriented_segment(
    edge: _Edge,
    *,
    from_node: int,
    clusters: tuple[_Cluster, ...],
) -> tuple[RegionSegment, int]:
    forward = edge.start_node == from_node
    to_node = edge.end_node if forward else edge.start_node
    start = clusters[from_node].representative
    end = clusters[to_node].representative
    primitive = edge.primitive
    if isinstance(primitive, ArcPrimitive):
        return (
            RegionArcSegment(
                start=start,
                end=end,
                center=primitive.center,
                clockwise=(primitive.clockwise if forward else not primitive.clockwise),
            ),
            to_node,
        )
    return RegionLineSegment(start=start, end=end), to_node


def _trace_cycles(
    edges: tuple[_Edge, ...],
    clusters: tuple[_Cluster, ...],
) -> tuple[tuple[tuple[RegionSegment, ...], tuple[str, ...]], ...]:
    adjacency: dict[int, list[int]] = {index: [] for index in range(len(clusters))}
    for edge_index, edge in enumerate(edges):
        adjacency[edge.start_node].append(edge_index)
        adjacency[edge.end_node].append(edge_index)
    invalid_degrees = {
        node: len(indices)
        for node, indices in adjacency.items()
        if len(indices) != _CYCLE_NODE_DEGREE
    }
    if invalid_degrees:
        degree_values = sorted(invalid_degrees.values())
        raise GeometryError(f"outline graph has non-cycle degrees {degree_values}")
    remaining = set(range(len(edges)))
    cycles: list[tuple[tuple[RegionSegment, ...], tuple[str, ...]]] = []
    while remaining:
        first_edge_index = min(
            remaining,
            key=lambda index: edges[index].primitive.primitive_id,
        )
        first_edge = edges[first_edge_index]
        start_node = min(first_edge.start_node, first_edge.end_node)
        current_node = start_node
        segments: list[RegionSegment] = []
        source_ids: list[str] = []
        while True:
            available = sorted(
                {
                    edge_index
                    for edge_index in adjacency[current_node]
                    if edge_index in remaining
                },
                key=lambda index: edges[index].primitive.primitive_id,
            )
            if not available:
                if current_node != start_node:
                    raise GeometryError("outline traversal ended before closure")
                break
            edge_index = available[0]
            remaining.remove(edge_index)
            edge = edges[edge_index]
            segment, current_node = _oriented_segment(
                edge,
                from_node=current_node,
                clusters=clusters,
            )
            segments.append(segment)
            source_ids.append(edge.primitive.primitive_id)
        cycles.append((tuple(segments), tuple(source_ids)))
    return tuple(cycles)


def _derived_points(
    segments: tuple[RegionSegment, ...],
    *,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> tuple[tuple[Point, ...], float]:
    points = [segments[0].start]
    maximum_error = 0.0
    for segment in segments:
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
            maximum_error = max(maximum_error, approximation.total_error_mm)
        else:
            points.append(segment.end)
    if points[-1] != points[0]:
        points.append(points[0])
    return tuple(points), maximum_error


def _build_loops(
    cycles: tuple[tuple[tuple[RegionSegment, ...], tuple[str, ...]], ...],
    *,
    snap_error_mm: float,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> tuple[_Loop, ...]:
    loops: list[_Loop] = []
    for segments, source_ids in cycles:
        points, approximation_error = _derived_points(
            segments,
            arc_chord_error_mm=arc_chord_error_mm,
            geometry_epsilon_mm=geometry_epsilon_mm,
        )
        polygon = Polygon([(point.x, point.y) for point in points])
        if not polygon.is_valid or polygon.area <= geometry_epsilon_mm**2:
            raise GeometryError("outline contour does not form valid board area")
        loops.append(
            _Loop(
                segments=segments,
                points=points,
                source_ids=source_ids,
                snap_error_mm=snap_error_mm,
                approximation_error_mm=approximation_error,
                polygon=polygon,
            )
        )
    return tuple(
        sorted(
            loops,
            key=lambda loop: (
                *loop.polygon.bounds,
                loop.source_ids,
            ),
        )
    )


def _nesting_depths(loops: tuple[_Loop, ...]) -> tuple[int, ...]:
    for index, first in enumerate(loops):
        for second in loops[index + 1 :]:
            if first.polygon.boundary.intersects(second.polygon.boundary):
                raise GeometryError("outline contours touch or cross")
    depths: list[int] = []
    for index, loop in enumerate(loops):
        representative = loop.polygon.representative_point()
        depths.append(
            sum(
                other.polygon.area > loop.polygon.area
                and other.polygon.contains(representative)
                for other_index, other in enumerate(loops)
                if other_index != index
            )
        )
    return tuple(depths)


def _build_outline(
    layer: PCBLayer,
    loops: tuple[_Loop, ...],
    depths: tuple[int, ...],
) -> BoardOutline:
    contours: list[OutlineContour] = []
    for index, (loop, depth) in enumerate(zip(loops, depths, strict=True)):
        kind: Literal["outer", "cutout"] = "outer" if depth % 2 == 0 else "cutout"
        contours.append(
            OutlineContour(
                contour_id=object_id(
                    "contour",
                    layer.source_file_id,
                    index,
                    "|".join(sorted(loop.source_ids)),
                ),
                kind=kind,
                segments=loop.segments,
                points=loop.points,
                closed=True,
                approximation_error_mm=(
                    loop.snap_error_mm + loop.approximation_error_mm
                ),
                source_primitive_ids=loop.source_ids,
            )
        )
    minimum_x = min(point.x for contour in contours for point in contour.points)
    minimum_y = min(point.y for contour in contours for point in contour.points)
    maximum_x = max(point.x for contour in contours for point in contour.points)
    maximum_y = max(point.y for contour in contours for point in contour.points)
    provenance_by_object = {
        primitive.primitive_id: primitive.provenance
        for primitive in layer.primitives
        if isinstance(primitive, LinePrimitive | ArcPrimitive)
    }
    provenance = tuple(
        provenance_by_object[primitive_id]
        for primitive_id in sorted(provenance_by_object)
    )
    return BoardOutline(
        contours=tuple(contours),
        bounding_box=BoundingBox(
            minimum=Point(x=minimum_x, y=minimum_y),
            maximum=Point(x=maximum_x, y=maximum_y),
        ),
        outer_contour_count=sum(contour.kind == "outer" for contour in contours),
        measurement_error_mm=max(
            contour.approximation_error_mm for contour in contours
        ),
        provenance=provenance,
    )


def reconstruct_board_outline(
    layers: tuple[PCBLayer, ...],
    *,
    closure_tolerance_mm: float,
    arc_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> OutlineReconstruction:
    """Reconstruct board material topology only from trusted outline layers."""
    if (
        closure_tolerance_mm <= 0.0
        or arc_chord_error_mm <= 0.0
        or geometry_epsilon_mm <= 0.0
    ):
        raise ValueError("outline tolerances must be positive")
    trusted = tuple(
        layer
        for layer in layers
        if layer.role is LayerRole.BOARD_OUTLINE and not layer.uncertainties
    )
    if not trusted:
        return _uncertainty(
            "No trusted board-outline layer is available.", layers=layers
        )
    if len(trusted) != 1:
        return _uncertainty(
            "Multiple trusted outline layers require coordinate confirmation.",
            layers=trusted,
            candidates=tuple(layer.layer_id for layer in trusted),
        )
    layer = trusted[0]
    unsupported = tuple(
        primitive.primitive_id
        for primitive in layer.primitives
        if not isinstance(primitive, LinePrimitive | ArcPrimitive)
        or primitive.polarity is not Polarity.DARK
    )
    if unsupported:
        return _uncertainty(
            "Outline layer contains unsupported or clear-polarity geometry.",
            layers=(layer,),
            candidates=unsupported,
        )
    primitives = tuple(
        primitive
        for primitive in layer.primitives
        if isinstance(primitive, LinePrimitive | ArcPrimitive)
    )
    if not primitives:
        return _uncertainty(
            "Trusted outline layer contains no line or arc geometry.",
            layers=(layer,),
        )
    try:
        clusters, edge_nodes, snap_error = _cluster_endpoints(
            primitives,
            closure_tolerance_mm,
        )
        edges = _graph_edges(primitives, edge_nodes)
        cycles = _trace_cycles(edges, clusters)
        loops = _build_loops(
            cycles,
            snap_error_mm=snap_error,
            arc_chord_error_mm=arc_chord_error_mm,
            geometry_epsilon_mm=geometry_epsilon_mm,
        )
        depths = _nesting_depths(loops)
        outline = _build_outline(layer, loops, depths)
    except GeometryError as error:
        return _uncertainty(
            str(error),
            layers=(layer,),
            candidates=tuple(primitive.primitive_id for primitive in primitives),
        )
    uncertainties: tuple[Uncertainty, ...] = ()
    if outline.outer_contour_count > 1:
        uncertainties = (
            Uncertainty(
                risk_mode=RiskMode.OUTLINE_UNCERTAIN,
                subject="board_outline",
                summary="Multiple disjoint outer board contours were reconstructed.",
                candidates=tuple(
                    contour.contour_id
                    for contour in outline.contours
                    if contour.kind == "outer"
                ),
                evidence=outline.provenance,
            ),
        )
    return OutlineReconstruction(outline=outline, uncertainties=uncertainties)
