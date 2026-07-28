"""Source provenance model tests."""

import math

import pytest
from pydantic import ValidationError

from boardgate.domain.provenance import Provenance, SourceSpan


def test_provenance_round_trip_with_unknown_span() -> None:
    provenance = Provenance(
        source_file_id="src-0123456789abcdef",
        object_id="line-0001",
        parser="gerbonara-adapter",
        parser_version="1.6.3",
        source_span=None,
        raw_coordinates={"x": "010000", "y": "025000"},
    )

    restored = Provenance.model_validate_json(provenance.model_dump_json())

    assert restored == provenance
    assert restored.source_span is None


def test_source_span_round_trip() -> None:
    span = SourceSpan(start_line=4, end_line=5, start_byte=20, end_byte=45)

    assert SourceSpan.model_validate_json(span.model_dump_json()) == span


@pytest.mark.parametrize(
    "values",
    [
        {"start_line": 1},
        {"end_line": 1},
        {"start_byte": 0},
        {"end_byte": 1},
        {"start_line": 3, "end_line": 2},
        {"start_byte": 4, "end_byte": 3},
    ],
)
def test_source_span_rejects_incomplete_or_inverted_ranges(
    values: dict[str, int],
) -> None:
    with pytest.raises(ValidationError):
        SourceSpan.model_validate(values)


def test_provenance_rejects_blank_identifiers() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_file_id="",
            parser="adapter",
            parser_version="1.0",
        )


def test_provenance_rejects_non_finite_metadata() -> None:
    with pytest.raises(ValidationError):
        Provenance(
            source_file_id="src-1",
            parser="adapter",
            parser_version="1.0",
            metadata={"invalid": math.nan},
        )
