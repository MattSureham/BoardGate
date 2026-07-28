"""Bounded deterministic CSV decoding with row source spans."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from boardgate.domain.provenance import SourceSpan
from boardgate.parsers.errors import ParserError

MAX_TABULAR_ROWS = 100_000
MAX_TABULAR_COLUMNS = 64
MAX_CELL_CHARACTERS = 1024 * 1024
_DELIMITERS = (",", ";", "\t")
_NORMALIZE_HEADER = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class TabularRow:
    """One decoded row with exact source bounds."""

    values: tuple[str, ...]
    source_span: SourceSpan
    row_number: int


@dataclass(frozen=True, slots=True)
class TabularData:
    """Normalized header and non-empty data rows."""

    headers: tuple[str, ...]
    normalized_headers: tuple[str, ...]
    rows: tuple[TabularRow, ...]
    delimiter: str


def normalize_header(value: str) -> str:
    """Normalize a header only for deterministic alias matching."""
    return _NORMALIZE_HEADER.sub("", value.strip().casefold())


def _decode(payload: bytes, logical_path: str) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ParserError(
            "TABULAR_ENCODING_ERROR",
            logical_path,
            "CSV input must be UTF-8",
        ) from error


def _candidate_rows(text: str, delimiter: str) -> list[list[str]]:
    try:
        return list(csv.reader(io.StringIO(text), delimiter=delimiter, strict=True))
    except csv.Error:
        return []


def _dialect(text: str, logical_path: str) -> str:
    first_nonempty = next(
        (line for line in text.splitlines() if line.strip()),
        "",
    )
    if not first_nonempty:
        raise ParserError("TABULAR_EMPTY", logical_path, "CSV input is empty")
    present = [delimiter for delimiter in _DELIMITERS if delimiter in first_nonempty]
    if not present:
        return ","
    scored: list[tuple[tuple[float, int], str]] = []
    for delimiter in present:
        rows = [row for row in _candidate_rows(text, delimiter) if any(row)]
        if not rows:
            continue
        header_width = len(rows[0])
        consistency = sum(len(row) == header_width for row in rows) / len(rows)
        scored.append(((consistency, header_width), delimiter))
    if not scored:
        raise ParserError(
            "TABULAR_DIALECT_ERROR",
            logical_path,
            "CSV delimiter could not be determined",
        )
    scored.sort(reverse=True)
    best_score = scored[0][0]
    winners = [delimiter for score, delimiter in scored if score == best_score]
    if len(winners) != 1:
        raise ParserError(
            "TABULAR_DIALECT_AMBIGUOUS",
            logical_path,
            "multiple CSV delimiters are equally plausible",
        )
    return winners[0]


def _line_offsets(payload: bytes) -> tuple[int, ...]:
    offsets = [0]
    for raw_line in payload.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(raw_line))
    if offsets[-1] < len(payload):
        offsets.append(len(payload))
    return tuple(offsets)


def _span(
    offsets: tuple[int, ...],
    *,
    start_line: int,
    end_line: int,
    payload_size: int,
) -> SourceSpan:
    start_byte = offsets[start_line - 1]
    end_byte = offsets[end_line] if end_line < len(offsets) else payload_size
    return SourceSpan(
        start_line=start_line,
        end_line=end_line,
        start_byte=start_byte,
        end_byte=end_byte,
    )


def parse_csv(payload: bytes, *, logical_path: str) -> TabularData:
    """Decode one bounded CSV while preserving multiline row spans."""
    text = _decode(payload, logical_path)
    delimiter = _dialect(text, logical_path)
    offsets = _line_offsets(payload)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
    parsed: list[TabularRow] = []
    previous_line = 0
    try:
        for values in reader:
            start_line = previous_line + 1
            end_line = reader.line_num
            previous_line = end_line
            if not any(value.strip() for value in values):
                continue
            if len(values) > MAX_TABULAR_COLUMNS:
                raise ParserError(
                    "TABULAR_COLUMN_LIMIT",
                    logical_path,
                    f"CSV exceeds {MAX_TABULAR_COLUMNS} columns",
                )
            if any(len(value) > MAX_CELL_CHARACTERS for value in values):
                raise ParserError(
                    "TABULAR_CELL_LIMIT",
                    logical_path,
                    "CSV cell exceeds the character limit",
                )
            parsed.append(
                TabularRow(
                    values=tuple(value.strip() for value in values),
                    source_span=_span(
                        offsets,
                        start_line=start_line,
                        end_line=end_line,
                        payload_size=len(payload),
                    ),
                    row_number=start_line,
                )
            )
            if len(parsed) > MAX_TABULAR_ROWS + 1:
                raise ParserError(
                    "TABULAR_ROW_LIMIT",
                    logical_path,
                    f"CSV exceeds {MAX_TABULAR_ROWS} data rows",
                )
    except csv.Error as error:
        raise ParserError(
            "TABULAR_SYNTAX_ERROR",
            logical_path,
            f"invalid CSV near line {reader.line_num}",
        ) from error
    if not parsed:
        raise ParserError("TABULAR_EMPTY", logical_path, "CSV input is empty")
    header = parsed[0]
    normalized = tuple(normalize_header(value) for value in header.values)
    if any(not value for value in normalized):
        raise ParserError(
            "TABULAR_HEADER_EMPTY",
            logical_path,
            "CSV headers must not be blank",
        )
    if len(normalized) != len(set(normalized)):
        raise ParserError(
            "TABULAR_HEADER_DUPLICATE",
            logical_path,
            "CSV headers must be unique after normalization",
        )
    rows: list[TabularRow] = []
    for row in parsed[1:]:
        if len(row.values) != len(header.values):
            raise ParserError(
                "TABULAR_ROW_WIDTH",
                logical_path,
                f"row {row.row_number} does not match header width",
            )
        rows.append(row)
    return TabularData(
        headers=header.values,
        normalized_headers=normalized,
        rows=tuple(rows),
        delimiter=delimiter,
    )


def resolve_columns(
    table: TabularData,
    *,
    aliases: dict[str, frozenset[str]],
    required: frozenset[str],
    logical_path: str,
) -> dict[str, int]:
    """Resolve aliases while rejecting multiple columns for one field."""
    resolved: dict[str, int] = {}
    for canonical, field_aliases in aliases.items():
        matches = [
            index
            for index, header in enumerate(table.normalized_headers)
            if header in field_aliases
        ]
        if len(matches) > 1:
            raise ParserError(
                "TABULAR_COLUMN_CONFLICT",
                logical_path,
                f"multiple columns map to {canonical!r}",
            )
        if matches:
            resolved[canonical] = matches[0]
    missing = sorted(required - resolved.keys())
    if missing:
        raise ParserError(
            "TABULAR_REQUIRED_COLUMN",
            logical_path,
            "missing required columns: " + ", ".join(missing),
        )
    return resolved
