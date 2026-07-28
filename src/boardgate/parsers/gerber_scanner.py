"""Lightweight Gerber command scanner for source provenance."""

from __future__ import annotations

import re
from dataclasses import dataclass

from boardgate.domain.provenance import SourceSpan

_COMMAND = re.compile(rb"G04.*?\*\s*|%.*?%\s*|[^*%]*\*\s*", re.DOTALL)
_APERTURE_SELECTION = re.compile(r"^(?:G5[45])?D(\d+)$")
_OPERATION = re.compile(r"D0?([123])$")
_RAW_COORDINATE = re.compile(r"([XYIJ])([+\-]?\d+)")


@dataclass(frozen=True, slots=True)
class GerberCommandWitness:
    """One parser object mapped to its source command or region block."""

    raw_command: str
    source_span: SourceSpan
    aperture_code: str | None
    raw_coordinates: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class _Token:
    command: str
    source_span: SourceSpan


def scan_gerber_tokens(payload: bytes) -> tuple[_Token, ...]:
    """Split Gerber's star/percent command stream with byte-accurate spans."""
    tokens: list[_Token] = []
    current_line = 1
    previous_end = 0
    for match in _COMMAND.finditer(payload):
        current_line += payload[previous_end : match.start()].count(b"\n")
        raw = match.group(0)
        command_bytes = raw.strip().strip(b"%").rstrip(b"*").strip()
        newline_count = command_bytes.count(b"\n")
        end_line = current_line + newline_count
        previous_end = match.end()
        if not command_bytes:
            current_line += raw.count(b"\n")
            continue
        try:
            command = command_bytes.decode("utf-8")
        except UnicodeDecodeError:
            command = command_bytes.decode("utf-8", errors="replace")
        leading = len(raw) - len(raw.lstrip())
        stripped_end = len(raw.rstrip())
        tokens.append(
            _Token(
                command=command,
                source_span=SourceSpan(
                    start_line=current_line,
                    end_line=end_line,
                    start_byte=match.start() + leading,
                    end_byte=match.start() + stripped_end,
                ),
            )
        )
        current_line += raw.count(b"\n")
    return tuple(tokens)


def scan_gerber_object_commands(
    payload: bytes,
) -> tuple[GerberCommandWitness, ...]:
    """Identify object-producing commands without interpreting coordinates."""
    aperture_code: str | None = None
    last_operation: str | None = None
    region_tokens: list[_Token] | None = None
    witnesses: list[GerberCommandWitness] = []
    for token in scan_gerber_tokens(payload):
        command = token.command.replace("\r", "").replace("\n", "")
        if selection := _APERTURE_SELECTION.match(command):
            aperture_code = f"D{int(selection.group(1))}"
            continue
        if command == "G36":
            region_tokens = [token]
            continue
        if region_tokens is not None:
            region_tokens.append(token)
            if command == "G37":
                first = region_tokens[0]
                witnesses.append(
                    GerberCommandWitness(
                        raw_command="G36...G37",
                        source_span=SourceSpan(
                            start_line=first.source_span.start_line,
                            end_line=token.source_span.end_line,
                            start_byte=first.source_span.start_byte,
                            end_byte=token.source_span.end_byte,
                        ),
                        aperture_code=None,
                        raw_coordinates=(),
                    )
                )
                region_tokens = None
            continue
        operation_match = _OPERATION.search(command)
        operation = operation_match.group(1) if operation_match is not None else None
        has_coordinates = bool(_RAW_COORDINATE.search(command))
        if operation is not None:
            last_operation = operation
        elif has_coordinates:
            operation = last_operation
        if has_coordinates and operation in {"1", "3"}:
            witnesses.append(
                GerberCommandWitness(
                    raw_command=command,
                    source_span=token.source_span,
                    aperture_code=aperture_code,
                    raw_coordinates=tuple(_RAW_COORDINATE.findall(command)),
                )
            )
    return tuple(witnesses)


def gerber_span_for_line(payload: bytes, line_number: int) -> SourceSpan | None:
    """Return the first command span that begins on a warning line."""
    return next(
        (
            token.source_span
            for token in scan_gerber_tokens(payload)
            if token.source_span.start_line == line_number
        ),
        None,
    )
