"""Properties for STRtree candidate selection."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from shapely.geometry import box

from boardgate.rules.derived_geometry import component_pairs_within

RECTANGLE = st.tuples(
    st.integers(min_value=-100, max_value=100),
    st.integers(min_value=-100, max_value=100),
    st.integers(min_value=1, max_value=20),
    st.integers(min_value=1, max_value=20),
)


@given(
    rectangle_bounds=st.lists(RECTANGLE, min_size=0, max_size=12),
    maximum_distance_tenths=st.integers(min_value=0, max_value=20),
)
@settings(derandomize=True)
def test_spatial_index_matches_brute_force(
    rectangle_bounds: list[tuple[int, int, int, int]],
    maximum_distance_tenths: int,
) -> None:
    components = tuple(
        box(x / 10, y / 10, (x + width) / 10, (y + height) / 10)
        for x, y, width, height in rectangle_bounds
    )
    maximum_distance = maximum_distance_tenths / 10

    indexed = component_pairs_within(
        components,
        maximum_distance=maximum_distance,
    )
    brute_force = tuple(
        (
            first_index,
            second_index,
            components[first_index].distance(components[second_index]),
        )
        for first_index in range(len(components))
        for second_index in range(first_index + 1, len(components))
        if components[first_index].distance(components[second_index])
        <= maximum_distance
    )

    assert [(first, second) for first, second, _ in indexed] == [
        (first, second) for first, second, _ in brute_force
    ]
    assert [distance for _, _, distance in indexed] == pytest.approx(
        [distance for _, _, distance in brute_force]
    )
