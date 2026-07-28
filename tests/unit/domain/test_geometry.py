"""Canonical geometry model tests."""

import math

import pytest
from pydantic import ValidationError

from boardgate.domain.geometry import (
    AxisDirection,
    BoundingBox,
    CoordinateSystem,
    Point,
    Unit,
)
from boardgate.domain.serialization import canonical_json


def test_point_json_round_trip_and_rounding() -> None:
    point = Point(x=1.23456789, y=-2.0000004)

    payload = point.model_dump_json()
    restored = Point.model_validate_json(payload)

    assert restored == Point(x=1.234568, y=-2.0)
    assert point.model_dump(mode="json")["x"] == 1.234568
    assert canonical_json(point) == (
        '{"schema_version":"1.0","unit":"mm","x":1.234568,"y":-2.0}'
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_point_rejects_non_finite_coordinates(value: float) -> None:
    with pytest.raises(ValidationError):
        Point(x=value, y=0.0)


def test_point_rejects_non_normalized_units() -> None:
    with pytest.raises(ValidationError, match="normalized to millimetres"):
        Point(x=1.0, y=2.0, unit=Unit.INCH)


def test_bounding_box_exposes_ordered_extent() -> None:
    bounds = BoundingBox(
        minimum=Point(x=-1.0, y=2.0),
        maximum=Point(x=4.0, y=8.0),
    )

    assert bounds.width == 5.0
    assert bounds.height == 6.0
    assert BoundingBox.model_validate_json(bounds.model_dump_json()) == bounds


def test_bounding_box_rejects_inverted_extent() -> None:
    with pytest.raises(ValidationError, match="minimum must not exceed maximum"):
        BoundingBox(
            minimum=Point(x=2.0, y=0.0),
            maximum=Point(x=1.0, y=1.0),
        )


def test_coordinate_system_defaults_to_canonical_orientation() -> None:
    coordinates = CoordinateSystem()

    assert coordinates.origin == Point(x=0.0, y=0.0)
    assert coordinates.x_axis is AxisDirection.RIGHT
    assert coordinates.y_axis is AxisDirection.UP


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("unit", Unit.INCH, "must use millimetres"),
        ("x_axis", AxisDirection.LEFT, "X axis must point right"),
        ("y_axis", AxisDirection.DOWN, "Y axis must point up"),
        ("rotation_degrees", 90.0, "zero residual rotation"),
    ],
)
def test_coordinate_system_rejects_noncanonical_state(
    field: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        CoordinateSystem.model_validate({field: value})
