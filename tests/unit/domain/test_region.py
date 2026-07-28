"""Analytic Gerber region contract tests."""

import pytest
from pydantic import ValidationError

from boardgate.domain.enums import Polarity
from boardgate.domain.geometry import Point
from boardgate.domain.layer import RegionLineSegment, RegionPrimitive
from boardgate.domain.provenance import Provenance


def segment(
    start: tuple[float, float],
    end: tuple[float, float],
) -> RegionLineSegment:
    return RegionLineSegment(
        start=Point(x=start[0], y=start[1]),
        end=Point(x=end[0], y=end[1]),
    )


def region(contour: tuple[RegionLineSegment, ...]) -> RegionPrimitive:
    return RegionPrimitive(
        primitive_id="region-1",
        contours=(contour,),
        polarity=Polarity.DARK,
        provenance=Provenance(
            source_file_id="src-0123456789abcdef",
            parser="test",
            parser_version="1",
        ),
    )


def test_region_requires_connected_closed_contour() -> None:
    valid = (
        segment((0, 0), (1, 0)),
        segment((1, 0), (0, 1)),
        segment((0, 1), (0, 0)),
    )
    assert region(valid).contours[0] == valid

    disconnected = (
        segment((0, 0), (1, 0)),
        segment((2, 0), (0, 1)),
        segment((0, 1), (0, 0)),
    )
    with pytest.raises(ValidationError, match="connected and closed"):
        region(disconnected)


def test_region_rejects_empty_contour() -> None:
    with pytest.raises(ValidationError, match="at least one"):
        region(())
