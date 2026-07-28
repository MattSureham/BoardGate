"""Normalized placement CSV tests."""

import pytest

from boardgate.domain.enums import BoardSide
from boardgate.domain.geometry import Unit
from boardgate.parsers import (
    ParserError,
    PlacementParseResult,
    parse_placement_csv,
)

SOURCE_ID = "src-0123456789abcdef"


def test_mm_headers_normalize_placements_and_provenance() -> None:
    payload = (
        b"Ref,PosX (mm),PosY (mm),Rotation,Side,Value,Package,Feeder\n"
        b"r1,1.25,2.5,90,top,10k,0402,F1\n"
        b"c1,-1,0,0,bottom,100n,0603,F2\n"
    )

    result = parse_placement_csv(
        payload,
        logical_path="placement.csv",
        source_file_id=SOURCE_ID,
    )

    assert result.source_unit is Unit.MILLIMETRE
    assert result.placements[0].reference == "R1"
    assert result.placements[0].position.x == 1.25
    assert result.placements[0].rotation_degrees == 90.0
    assert result.placements[0].side is BoardSide.TOP
    assert result.placements[1].side is BoardSide.BOTTOM
    assert result.placements[0].metadata == {"Feeder": "F1"}
    assert result.placements[0].provenance.raw_coordinates == {
        "x": "1.25",
        "y": "2.5",
        "unit": "mm",
    }
    assert PlacementParseResult.model_validate_json(result.model_dump_json()) == (
        result
    )


def test_explicit_inch_unit_is_converted() -> None:
    result = parse_placement_csv(
        b"Ref,X,Y,Rotation,Side\nU1,1,2,180,front\n",
        logical_path="placement.csv",
        source_file_id=SOURCE_ID,
        coordinate_unit=Unit.INCH,
    )

    assert result.source_unit is Unit.INCH
    assert result.placements[0].position.x == pytest.approx(25.4)
    assert result.placements[0].position.y == pytest.approx(50.8)


def test_unit_column_can_supply_unit() -> None:
    result = parse_placement_csv(
        b"Ref,X,Y,Rotation,Side,Units\nU1,1,2,0,T,mm\n",
        logical_path="placement.csv",
        source_file_id=SOURCE_ID,
    )

    assert result.source_unit is Unit.MILLIMETRE


def test_explicit_dnp_values_are_normalized() -> None:
    result = parse_placement_csv(
        (
            b"Ref,X (mm),Y (mm),Rotation,Side,DNP\n"
            b"R1,1,2,0,top,true\n"
            b"R2,3,4,0,top,false\n"
        ),
        logical_path="placement.csv",
        source_file_id=SOURCE_ID,
    )

    assert result.placements[0].dnp is True
    assert result.placements[1].dnp is False


@pytest.mark.parametrize(
    ("header", "value", "expected_dnp"),
    [
        ("Fitted", "yes", False),
        ("Fitted", "no", True),
        ("Populate", "1", False),
        ("Populate", "0", True),
    ],
)
def test_fitted_and_populate_columns_use_inverse_dnp_semantics(
    header: str,
    value: str,
    expected_dnp: bool,
) -> None:
    payload = (
        f"Ref,X (mm),Y (mm),Rotation,Side,{header}\nR1,1,2,0,top,{value}\n"
    ).encode()

    result = parse_placement_csv(
        payload,
        logical_path="placement.csv",
        source_file_id=SOURCE_ID,
    )

    assert result.placements[0].dnp is expected_dnp


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            b"Ref,X,Y,Rotation,Side\nU1,1,2,0,top\n",
            "PLACEMENT_UNIT_AMBIGUOUS",
        ),
        (
            b"Ref,X (mm),Y (inch),Rotation,Side\nU1,1,2,0,top\n",
            "PLACEMENT_UNIT_CONFLICT",
        ),
        (
            b"Ref,X (mm),Y (mm),Rotation,Side\nU1,nope,2,0,top\n",
            "PLACEMENT_NUMBER_VALUE",
        ),
        (
            b"Ref,X (mm),Y (mm),Rotation,Side\nU1,1,2,nan,top\n",
            "PLACEMENT_NUMBER_VALUE",
        ),
        (
            b"Ref,X (mm),Y (mm),Rotation,Side\nU1,1,2,0,middle\n",
            "PLACEMENT_SIDE_VALUE",
        ),
        (
            b"Ref,X (mm),Y (mm),Rotation,Side\n,1,2,0,top\n",
            "PLACEMENT_REFERENCE_EMPTY",
        ),
        (
            b"Ref,X (mm),Y (mm),Rotation,Side,DNP\nU1,1,2,0,top,maybe\n",
            "PLACEMENT_DNP_VALUE",
        ),
    ],
)
def test_placement_errors_are_typed(payload: bytes, code: str) -> None:
    with pytest.raises(ParserError) as caught:
        parse_placement_csv(
            payload,
            logical_path="placement.csv",
            source_file_id=SOURCE_ID,
        )

    assert caught.value.code == code
