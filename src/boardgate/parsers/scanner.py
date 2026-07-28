"""Lightweight command spans without a second geometry parser."""

from __future__ import annotations

import re
from dataclasses import dataclass

from boardgate.domain.provenance import SourceSpan

_TOOL_DEFINITION = re.compile(r"^T(\d+)[A-Z]")
_TOOL_SELECTION = re.compile(r"^T(\d+)$")
_REPEAT_HIT = re.compile(r"^R(\d+)(?:X|Y)")
_COORDINATE = re.compile(r"(?:^|[G0-9])X[+\-]?[0-9.]|Y[+\-]?[0-9.]")
_RAW_COORDINATE = re.compile(r"([XYAIJ])([+\-]?[0-9.]+)")


@dataclass(frozen=True, slots=True)
class CommandWitness:
    """One likely object-producing source command."""

    raw_command: str
    source_span: SourceSpan
    tool_code: str | None
    raw_coordinates: tuple[tuple[str, str], ...]


def _line_span(
    *,
    line_number: int,
    start_byte: int,
    raw_line: bytes,
) -> SourceSpan:
    content_length = len(raw_line.rstrip(b"\r\n"))
    return SourceSpan(
        start_line=line_number,
        end_line=line_number,
        start_byte=start_byte,
        end_byte=start_byte + content_length,
    )


def scan_excellon_object_commands(  # noqa: PLR0912
    payload: bytes,
) -> tuple[CommandWitness, ...]:
    """Align likely object commands to adapter output in source order."""
    active_tool: str | None = None
    routing = False
    drill_down = False
    interpolation = "linear"
    records: list[CommandWitness] = []
    byte_offset = 0
    for line_number, raw_line in enumerate(payload.splitlines(keepends=True), start=1):
        try:
            command = raw_line.decode("utf-8-sig").strip()
        except UnicodeDecodeError:
            command = raw_line.decode("latin-1").strip()
        span = _line_span(
            line_number=line_number,
            start_byte=byte_offset,
            raw_line=raw_line,
        )
        byte_offset += len(raw_line)
        if not command or command.startswith(";"):
            continue
        if _TOOL_DEFINITION.match(command):
            continue
        if selection := _TOOL_SELECTION.match(command):
            active_tool = f"T{int(selection.group(1)):02d}"
            continue
        if command == "G05":
            routing = False
            drill_down = False
            continue
        if command.startswith("G00"):
            routing = True
            continue
        if command == "M15":
            drill_down = True
            continue
        if command in {"M16", "M17"}:
            drill_down = False
            continue
        if command.startswith(("G01", "G02", "G03")):
            interpolation = "linear" if command.startswith("G01") else "circular"
        raw_coordinates = tuple(_RAW_COORDINATE.findall(command))
        count = 0
        if "G85" in command and raw_coordinates:
            count = 1
        elif repeat := _REPEAT_HIT.match(command):
            count = int(repeat.group(1))
        elif _COORDINATE.search(command):
            if routing:
                count = int(drill_down and interpolation in {"linear", "circular"})
            else:
                count = 1
        witness = CommandWitness(
            raw_command=command,
            source_span=span,
            tool_code=active_tool,
            raw_coordinates=raw_coordinates,
        )
        records.extend(witness for _ in range(count))
    return tuple(records)


def span_for_line(payload: bytes, line_number: int) -> SourceSpan | None:
    """Return the exact byte span for one one-based source line."""
    byte_offset = 0
    for current, raw_line in enumerate(payload.splitlines(keepends=True), start=1):
        if current == line_number:
            return _line_span(
                line_number=current,
                start_byte=byte_offset,
                raw_line=raw_line,
            )
        byte_offset += len(raw_line)
    return None
