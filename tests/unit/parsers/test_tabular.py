"""Bounded CSV decoding and column mapping tests."""

import pytest

from boardgate.parsers.errors import ParserError
from boardgate.parsers.tabular import parse_csv, resolve_columns


def test_semicolon_csv_and_multiline_row_spans() -> None:
    payload = b'Reference;Description;Value\r\nR1;"line one\r\nline two";10k\r\n'

    table = parse_csv(payload, logical_path="bom.csv")

    assert table.delimiter == ";"
    assert table.normalized_headers == ("reference", "description", "value")
    assert len(table.rows) == 1
    assert table.rows[0].values[1] == "line one\r\nline two"
    source_span = table.rows[0].source_span
    assert source_span is not None
    assert source_span.start_line == 2
    assert source_span.end_line == 3
    assert source_span.start_byte == payload.index(b"R1")
    assert source_span.end_byte == len(payload)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"", "TABULAR_EMPTY"),
        (b"\xff", "TABULAR_ENCODING_ERROR"),
        (b"Reference, reference\nR1,R2\n", "TABULAR_HEADER_DUPLICATE"),
        (b"Reference,Value\nR1\n", "TABULAR_ROW_WIDTH"),
        (b"Reference,Value;Other\nR1,10k;X\n", "TABULAR_DIALECT_AMBIGUOUS"),
    ],
)
def test_csv_structure_errors_are_typed(payload: bytes, code: str) -> None:
    with pytest.raises(ParserError) as caught:
        parse_csv(payload, logical_path="input.csv")

    assert caught.value.code == code


def test_column_alias_conflict_and_required_columns() -> None:
    table = parse_csv(
        b"Reference,Ref,Value\nR1,R1,10k\n",
        logical_path="bom.csv",
    )

    with pytest.raises(ParserError, match="TABULAR_COLUMN_CONFLICT"):
        resolve_columns(
            table,
            aliases={"references": frozenset({"reference", "ref"})},
            required=frozenset({"references"}),
            logical_path="bom.csv",
        )
    with pytest.raises(ParserError, match="TABULAR_REQUIRED_COLUMN"):
        resolve_columns(
            table,
            aliases={"quantity": frozenset({"quantity"})},
            required=frozenset({"quantity"}),
            logical_path="bom.csv",
        )
