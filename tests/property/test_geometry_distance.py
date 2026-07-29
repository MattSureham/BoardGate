"""Properties for deterministic geometric distances."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from shapely.geometry import box

from boardgate.domain.geometry import BoundingBox, Point
from boardgate.rules import geometry_rules

BOUNDS = st.tuples(
    st.integers(min_value=-100, max_value=100),
    st.integers(min_value=-100, max_value=100),
    st.integers(min_value=1, max_value=20),
    st.integers(min_value=1, max_value=20),
)


def _bounding_box(bounds: tuple[int, int, int, int]) -> BoundingBox:
    x, y, width, height = bounds
    return BoundingBox(
        minimum=Point(x=x / 10, y=y / 10),
        maximum=Point(x=(x + width) / 10, y=(y + height) / 10),
    )


@given(first_bounds=BOUNDS, second_bounds=BOUNDS)
@settings(derandomize=True)
def test_bounding_box_distance_is_symmetric(
    first_bounds: tuple[int, int, int, int],
    second_bounds: tuple[int, int, int, int],
) -> None:
    first = _bounding_box(first_bounds)
    second = _bounding_box(second_bounds)

    forward = geometry_rules._bbox_distance(first, second)
    reverse = geometry_rules._bbox_distance(second, first)
    first_shape = box(
        first.minimum.x,
        first.minimum.y,
        first.maximum.x,
        first.maximum.y,
    )
    second_shape = box(
        second.minimum.x,
        second.minimum.y,
        second.maximum.x,
        second.maximum.y,
    )

    assert forward == reverse
    assert forward >= 0.0
    assert forward == pytest.approx(first_shape.distance(second_shape))
