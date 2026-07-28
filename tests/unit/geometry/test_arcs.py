"""Analytic arc approximation tests."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from boardgate.domain.geometry import Point
from boardgate.geometry.arcs import GeometryError, approximate_arc


@given(
    radius=st.floats(min_value=0.01, max_value=1000.0),
    error=st.floats(min_value=1e-6, max_value=0.005),
)
def test_quarter_arc_respects_chord_error(radius: float, error: float) -> None:
    approximation = approximate_arc(
        Point(x=radius, y=0.0),
        Point(x=0.0, y=radius),
        Point(x=0.0, y=0.0),
        clockwise=False,
        max_chord_error_mm=error,
        geometry_epsilon_mm=max(error, 1e-5),
    )

    assert approximation.points[0] == Point(x=radius, y=0.0)
    assert approximation.points[-1] == Point(x=0.0, y=radius)
    assert approximation.chord_error_mm <= error * (1.0 + 1e-9)
    assert approximation.radial_mismatch_mm == pytest.approx(0.0)


def test_clockwise_and_full_circle_direction() -> None:
    clockwise = approximate_arc(
        Point(x=1.0, y=0.0),
        Point(x=0.0, y=-1.0),
        Point(x=0.0, y=0.0),
        clockwise=True,
        max_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
    )
    full = approximate_arc(
        Point(x=1.0, y=0.0),
        Point(x=1.0, y=0.0),
        Point(x=0.0, y=0.0),
        clockwise=False,
        max_chord_error_mm=0.001,
        geometry_epsilon_mm=0.001,
    )

    assert clockwise.points[1].y < 0.0
    assert len(full.points) > 2
    assert full.points[0] == full.points[-1]


@pytest.mark.parametrize(
    ("start", "end", "center", "message"),
    [
        (
            Point(x=0.0, y=0.0),
            Point(x=1.0, y=0.0),
            Point(x=0.0, y=0.0),
            "radius is too small",
        ),
        (
            Point(x=1.0, y=0.0),
            Point(x=0.0, y=2.0),
            Point(x=0.0, y=0.0),
            "share a radius",
        ),
    ],
)
def test_invalid_arcs_are_rejected(
    start: Point,
    end: Point,
    center: Point,
    message: str,
) -> None:
    with pytest.raises(GeometryError, match=message):
        approximate_arc(
            start,
            end,
            center,
            clockwise=False,
            max_chord_error_mm=0.001,
            geometry_epsilon_mm=0.001,
        )


def test_invalid_tolerance_is_rejected() -> None:
    with pytest.raises(GeometryError, match="positive"):
        approximate_arc(
            Point(x=1.0, y=0.0),
            Point(x=0.0, y=1.0),
            Point(x=0.0, y=0.0),
            clockwise=False,
            max_chord_error_mm=0.0,
            geometry_epsilon_mm=0.001,
        )
