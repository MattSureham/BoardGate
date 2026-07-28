"""Gerbonara-backed Gerber adapter golden tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.domain.enums import ApertureShape, Polarity
from boardgate.domain.geometry import Unit
from boardgate.domain.layer import (
    ArcPrimitive,
    FlashPrimitive,
    LinePrimitive,
    RegionArcSegment,
    RegionPrimitive,
)
from boardgate.parsers import GerberParseResult, ParserError, parse_gerber

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "parser" / "gerber"
SOURCE_ID = "src-0123456789abcdef"


def parse_fixture(name: str) -> GerberParseResult:
    return parse_gerber(
        (FIXTURES / name).read_bytes(),
        logical_path=name,
        source_file_id=SOURCE_ID,
    )


def test_standard_primitives_polarity_attributes_and_round_trip() -> None:
    result = parse_fixture("primitives.gbr")

    assert result.original_unit is Unit.MILLIMETRE
    assert result.coordinate_format == (4, 6)
    assert result.file_attributes[".FileFunction"] == ("Copper", "L1", "Top")
    assert result.file_attributes[".SameCoordinates"] == ("boardgate-origin",)
    assert len(result.primitives) == 7
    line, arc, flash, obround, polygon, clear_flash, region = result.primitives
    assert isinstance(line, LinePrimitive)
    assert line.start.x == 0.0
    assert line.end.x == 10.0
    assert line.aperture.shape is ApertureShape.CIRCLE
    assert line.aperture.width_mm == 0.2
    assert isinstance(arc, ArcPrimitive)
    assert arc.center.x == 10.0
    assert arc.center.y == 5.0
    assert arc.clockwise is False
    assert isinstance(flash, FlashPrimitive)
    assert flash.aperture.shape is ApertureShape.RECTANGLE
    assert flash.aperture.width_mm == 1.0
    assert flash.aperture.height_mm == 2.0
    assert isinstance(obround, FlashPrimitive)
    assert obround.aperture.shape is ApertureShape.OBROUND
    assert isinstance(polygon, FlashPrimitive)
    assert polygon.aperture.shape is ApertureShape.POLYGON
    assert polygon.aperture.vertices == 6
    assert polygon.aperture.rotation_degrees == pytest.approx(30.0)
    assert clear_flash.polarity is Polarity.CLEAR
    assert isinstance(region, RegionPrimitive)
    assert len(region.contours[0]) == 4
    assert line.provenance.source_span is not None
    assert line.provenance.metadata["aperture_code"] == "D10"
    assert not result.limitations
    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_inch_geometry_is_normalized_to_millimetres() -> None:
    result = parse_fixture("inch.gbr")
    line = result.primitives[0]

    assert result.original_unit is Unit.INCH
    assert isinstance(line, LinePrimitive)
    assert line.end.x == pytest.approx(25.4)
    assert line.end.y == pytest.approx(50.8)
    assert line.aperture.width_mm == pytest.approx(0.254)


def test_region_arc_remains_analytic() -> None:
    result = parse_fixture("region_arc.gbr")
    region = result.primitives[0]

    assert isinstance(region, RegionPrimitive)
    assert isinstance(region.contours[0][0], RegionArcSegment)
    assert region.contours[0][0].center.x == 1.0


def test_macro_is_retained_by_bounds_and_explicitly_limited() -> None:
    result = parse_fixture("macro.gbr")
    flash = result.primitives[0]

    assert isinstance(flash, FlashPrimitive)
    assert flash.aperture.shape is ApertureShape.MACRO
    assert flash.aperture.macro_name == "ROUND"
    assert [item.code for item in result.limitations] == [
        "GERBER_APERTURE_MACRO_LIMITATION"
    ]


def test_unknown_statement_is_a_spanned_limitation() -> None:
    payload = b"%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.2*%\nG99*\nD10*\nX0Y0D03*\nM02*\n"

    result = parse_gerber(
        payload,
        logical_path="unknown.gbr",
        source_file_id=SOURCE_ID,
    )

    limitation = result.limitations[0]
    assert limitation.code == "GERBER_COMMAND_LIMITATION"
    assert limitation.source_span is not None
    assert limitation.source_span.start_line == 4


def test_include_is_rejected_without_file_access() -> None:
    payload = b"%FSLAX46Y46*%\n%MOMM*%\n%IFsecret.gbr*%\nM02*\n"

    with pytest.raises(ParserError, match="GERBER_INCLUDE_REJECTED"):
        parse_gerber(
            payload,
            logical_path="include.gbr",
            source_file_id=SOURCE_ID,
        )


def test_malformed_and_encoding_errors_are_typed() -> None:
    with pytest.raises(ParserError) as malformed:
        parse_fixture("malformed.gbr")
    assert malformed.value.code == "GERBER_PARSE_ERROR"
    assert str(FIXTURES) not in str(malformed.value)

    with pytest.raises(ParserError, match="GERBER_ENCODING_ERROR"):
        parse_gerber(
            b"\xff",
            logical_path="bad.gbr",
            source_file_id=SOURCE_ID,
        )
