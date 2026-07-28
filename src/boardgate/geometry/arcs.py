"""Deterministic analytic-arc approximation with a bounded chord error."""

from __future__ import annotations

import math
from dataclasses import dataclass

from boardgate.domain.geometry import Point


class GeometryError(ValueError):
    """A derived-geometry construction failure."""


@dataclass(frozen=True, slots=True)
class ArcApproximation:
    """Polyline points and the proven maximum radial chord error."""

    points: tuple[Point, ...]
    chord_error_mm: float
    radial_mismatch_mm: float

    @property
    def total_error_mm(self) -> float:
        """Conservative error bound for downstream measurements."""
        return self.chord_error_mm + self.radial_mismatch_mm


def _sweep(
    start_angle: float,
    end_angle: float,
    *,
    clockwise: bool,
    closed: bool,
) -> float:
    full_turn = 2.0 * math.pi
    if closed:
        return -full_turn if clockwise else full_turn
    if clockwise:
        return -((start_angle - end_angle) % full_turn)
    return (end_angle - start_angle) % full_turn


def approximate_arc(  # noqa: PLR0913
    start: Point,
    end: Point,
    center: Point,
    *,
    clockwise: bool,
    max_chord_error_mm: float,
    geometry_epsilon_mm: float,
) -> ArcApproximation:
    """Approximate one circular arc without exceeding the requested sagitta."""
    if max_chord_error_mm <= 0.0 or geometry_epsilon_mm <= 0.0:
        raise GeometryError("arc tolerances must be positive")
    start_radius = math.hypot(start.x - center.x, start.y - center.y)
    end_radius = math.hypot(end.x - center.x, end.y - center.y)
    if start_radius <= geometry_epsilon_mm or end_radius <= geometry_epsilon_mm:
        raise GeometryError("arc radius is too small for geometry tolerance")
    radial_mismatch = abs(start_radius - end_radius) / 2.0
    if radial_mismatch > geometry_epsilon_mm:
        raise GeometryError("arc endpoints do not share a radius within tolerance")
    radius = (start_radius + end_radius) / 2.0
    start_angle = math.atan2(start.y - center.y, start.x - center.x)
    end_angle = math.atan2(end.y - center.y, end.x - center.x)
    closed = math.dist((start.x, start.y), (end.x, end.y)) <= (geometry_epsilon_mm)
    sweep = _sweep(
        start_angle,
        end_angle,
        clockwise=clockwise,
        closed=closed,
    )
    if math.isclose(sweep, 0.0, abs_tol=1e-15):
        raise GeometryError("arc sweep is zero")
    if max_chord_error_mm >= radius:
        maximum_angle = math.pi
    else:
        maximum_angle = 2.0 * math.acos(1.0 - (max_chord_error_mm / radius))
    segment_count = max(1, math.ceil(abs(sweep) / maximum_angle))
    angle_step = sweep / segment_count
    points = [start]
    for index in range(1, segment_count):
        angle = start_angle + angle_step * index
        points.append(
            Point(
                x=center.x + radius * math.cos(angle),
                y=center.y + radius * math.sin(angle),
            )
        )
    points.append(end)
    actual_angle = abs(angle_step)
    chord_error = radius * (1.0 - math.cos(actual_angle / 2.0))
    return ArcApproximation(
        points=tuple(points),
        chord_error_mm=chord_error,
        radial_mismatch_mm=radial_mismatch,
    )
