"""Gerber command-span scanner tests."""

from boardgate.parsers.gerber_scanner import (
    gerber_span_for_line,
    scan_gerber_object_commands,
    scan_gerber_tokens,
)


def test_scanner_splits_extended_and_coordinate_commands() -> None:
    payload = (
        b"G04 fixture*\n"
        b"%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.2*%\n"
        b"D10*\nX0Y0D02*\nX100Y0D01*\nX50Y50D03*\nM02*\n"
    )

    tokens = scan_gerber_tokens(payload)
    witnesses = scan_gerber_object_commands(payload)

    assert any(token.command == "FSLAX46Y46" for token in tokens)
    assert len(witnesses) == 2
    assert witnesses[0].aperture_code == "D10"
    assert witnesses[0].raw_coordinates == (("X", "100"), ("Y", "0"))
    assert witnesses[0].source_span.start_line == 7
    assert witnesses[1].raw_command == "X50Y50D03"


def test_region_is_one_spanned_witness() -> None:
    payload = (
        b"%FSLAX46Y46*%\n%MOMM*%\nG36*\n"
        b"X0Y0D02*\nX1Y0D01*\nX1Y1D01*\nX0Y0D01*\nG37*\nM02*\n"
    )

    witnesses = scan_gerber_object_commands(payload)

    assert len(witnesses) == 1
    assert witnesses[0].raw_command == "G36...G37"
    assert witnesses[0].source_span.start_line == 3
    assert witnesses[0].source_span.end_line == 8


def test_warning_line_lookup_returns_none_when_absent() -> None:
    assert gerber_span_for_line(b"M02*\n", 2) is None
