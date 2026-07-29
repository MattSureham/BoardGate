"""Properties for parser-to-domain unit normalization."""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from boardgate.domain.geometry import Unit
from boardgate.parsers import parse_placement_csv

SOURCE_ID = "src-0123456789abcdef"
INCH_TO_MILLIMETRE = Decimal("25.4")
COORDINATES = st.decimals(
    min_value=Decimal("-1000"),
    max_value=Decimal("1000"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)


@given(x=COORDINATES, y=COORDINATES)
@settings(derandomize=True)
def test_inch_and_mm_placements_share_canonical_coordinates(
    x: Decimal,
    y: Decimal,
) -> None:
    """Equivalent source units must produce the same millimetre point."""
    inch_payload = f"Ref,X,Y,Rotation,Side\nU1,{x},{y},0,top\n".encode()
    mm_payload = (
        "Ref,X (mm),Y (mm),Rotation,Side\n"
        f"U1,{x * INCH_TO_MILLIMETRE},{y * INCH_TO_MILLIMETRE},0,top\n"
    ).encode()

    from_inches = parse_placement_csv(
        inch_payload,
        logical_path="placement-inch.csv",
        source_file_id=SOURCE_ID,
        coordinate_unit=Unit.INCH,
    )
    from_mm = parse_placement_csv(
        mm_payload,
        logical_path="placement-mm.csv",
        source_file_id=SOURCE_ID,
    )

    inch_point = from_inches.placements[0].position
    mm_point = from_mm.placements[0].position
    assert inch_point.unit is Unit.MILLIMETRE
    assert mm_point.unit is Unit.MILLIMETRE
    assert inch_point.x == pytest.approx(mm_point.x, rel=1e-12, abs=1e-9)
    assert inch_point.y == pytest.approx(mm_point.y, rel=1e-12, abs=1e-9)
