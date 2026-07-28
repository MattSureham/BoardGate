"""Gerbonara-backed Excellon adapter golden tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.domain.enums import Plating
from boardgate.domain.geometry import Unit
from boardgate.parsers import ExcellonParseResult, ParserError, parse_excellon

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "parser" / "excellon"
SOURCE_ID = "src-0123456789abcdef"


def parse_fixture(
    name: str,
    *,
    plating: Plating = Plating.UNKNOWN,
) -> ExcellonParseResult:
    return parse_excellon(
        (FIXTURES / name).read_bytes(),
        logical_path=name,
        source_file_id=SOURCE_ID,
        plating_hint=plating,
    )


def test_metric_hits_preserve_tools_spans_and_round_trip() -> None:
    result = parse_fixture("metric_hits.drl", plating=Plating.PLATED)

    assert result.original_unit is Unit.MILLIMETRE
    assert result.notation == "absolute"
    assert result.coordinate_format == (3, 3)
    assert result.zero_suppression == "leading"
    assert len(result.drills) == 3
    assert not result.slots
    assert [drill.tool_code for drill in result.drills] == ["T01", "T01", "T02"]
    assert [drill.diameter_mm for drill in result.drills] == [0.3, 0.3, 0.8]
    assert result.drills[1].position.x == 3.5
    assert all(drill.plating is Plating.PLATED for drill in result.drills)
    assert result.drills[0].provenance.source_span is not None
    assert result.drills[0].provenance.raw_coordinates == {
        "X": "1.000",
        "Y": "2.000",
    }
    assert not result.limitations
    assert type(result).model_validate_json(result.model_dump_json()) == result


def test_inch_hits_are_normalized_to_millimetres() -> None:
    result = parse_fixture("inch_hits.drl")
    drill = result.drills[0]

    assert result.original_unit is Unit.INCH
    assert drill.position.x == pytest.approx(25.4)
    assert drill.position.y == pytest.approx(50.8)
    assert drill.diameter_mm == pytest.approx(0.254)


def test_linear_and_arc_slots_remain_analytic_and_separate() -> None:
    result = parse_fixture("slots.drl")

    assert not result.drills
    assert len(result.slots) == 2
    line, arc = result.slots
    assert line.kind == "line"
    assert line.start.x == 1.0
    assert line.end.x == 4.0
    assert line.width_mm == 0.5
    assert arc.kind == "arc"
    assert arc.center is not None
    assert arc.center.x == 4.0
    assert arc.center.y == 2.0
    assert arc.clockwise is True


def test_incremental_notation_is_explicitly_partial() -> None:
    result = parse_fixture("incremental.drl")

    assert result.notation == "incremental"
    assert result.drills[1].position.x == 2.0
    assert result.drills[1].position.y == 3.0
    assert [item.code for item in result.limitations] == [
        "EXCELLON_INCREMENTAL_NOTATION"
    ]


def test_ignored_cam_command_becomes_spanned_limitation() -> None:
    result = parse_fixture("warning.drl")

    assert result.zero_suppression == "trailing"
    assert len(result.drills) == 1
    assert len(result.limitations) == 1
    limitation = result.limitations[0]
    assert limitation.code == "EXCELLON_COMMAND_LIMITATION"
    assert limitation.source_span is not None
    assert limitation.source_span.start_line == 6


def test_malformed_tool_selection_is_typed_and_source_safe() -> None:
    with pytest.raises(ParserError) as caught:
        parse_fixture("malformed.drl")

    assert caught.value.code == "EXCELLON_PARSE_ERROR"
    assert "T09" in caught.value.detail
    assert str(FIXTURES) not in str(caught.value)


def test_unknown_command_is_classified_as_parser_limitation() -> None:
    payload = b"M48\nMETRIC,TZ,000.000\nT01C0.3\n%\nT01\nG99\nX1.0Y2.0\nM30\n"

    with pytest.raises(ParserError) as caught:
        parse_excellon(
            payload,
            logical_path="unknown.drl",
            source_file_id=SOURCE_ID,
        )

    assert caught.value.code == "EXCELLON_UNSUPPORTED_COMMAND"


def test_non_utf8_input_is_rejected() -> None:
    with pytest.raises(ParserError, match="EXCELLON_ENCODING_ERROR"):
        parse_excellon(
            b"M48\n\xff\n",
            logical_path="bad.drl",
            source_file_id=SOURCE_ID,
        )
