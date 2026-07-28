"""Lightweight command-span scanner tests."""

from boardgate.parsers.scanner import (
    scan_excellon_object_commands,
    span_for_line,
)


def test_scanner_tracks_hits_slots_tools_and_exact_spans() -> None:
    payload = (
        b"M48\r\n"
        b"METRIC,TZ,000.000\r\n"
        b"T01C0.3\r\n"
        b"%\r\n"
        b"T01\r\n"
        b"X1.0Y2.0\r\n"
        b"X1.0Y2.0G85X3.0Y2.0\r\n"
        b"M30\r\n"
    )

    witnesses = scan_excellon_object_commands(payload)

    assert len(witnesses) == 2
    assert witnesses[0].tool_code == "T01"
    assert witnesses[0].raw_coordinates == (("X", "1.0"), ("Y", "2.0"))
    assert witnesses[0].source_span.start_line == 6
    start = payload.index(b"X1.0Y2.0\r\n")
    assert witnesses[0].source_span.start_byte == start
    assert witnesses[0].source_span.end_byte == start + len(b"X1.0Y2.0")
    assert witnesses[1].source_span.start_line == 7


def test_scanner_expands_repeat_witnesses_and_tracks_routes() -> None:
    payload = (
        b"M48\nMETRIC,TZ,000.000\nT01C0.3\n%\nT01\n"
        b"X1Y1\nR3X1Y0\n"
        b"G00X4Y1\nM15\nG01X5Y1\nM16\nM30\n"
    )

    witnesses = scan_excellon_object_commands(payload)

    assert len(witnesses) == 5
    assert [item.raw_command for item in witnesses].count("R3X1Y0") == 3
    assert witnesses[-1].raw_command == "G01X5Y1"


def test_span_for_missing_line_is_none() -> None:
    assert span_for_line(b"one\ntwo\n", 3) is None
