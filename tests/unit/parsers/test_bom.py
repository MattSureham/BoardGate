"""Normalized BOM CSV tests."""

import pytest

from boardgate.parsers import BOMParseResult, ParserError, parse_bom_csv

SOURCE_ID = "src-0123456789abcdef"


def test_bom_groups_ranges_dnp_metadata_and_provenance() -> None:
    payload = (
        b"References,Qty,Value,MPN,Footprint,DNP,Vendor\n"
        b'"R1-R3",3,10k,ABC-1,0402,no,Acme\n'
        b"C1,0,100n,ABC-2,0603,yes,Acme\n"
    )

    result = parse_bom_csv(
        payload,
        logical_path="bom.csv",
        source_file_id=SOURCE_ID,
    )

    assert result.items[0].references == ("R1", "R2", "R3")
    assert result.items[0].quantity == 3
    assert result.items[0].part_number == "ABC-1"
    assert result.items[0].metadata == {"Vendor": "Acme"}
    assert not result.items[0].dnp
    assert result.items[1].quantity == 0
    assert result.items[1].dnp
    assert result.items[0].provenance.source_span is not None
    assert result.items[0].provenance.source_span.start_line == 2
    assert result.items[0].provenance.object_id is not None
    assert result.items[0].provenance.object_id.startswith("bom-")
    assert BOMParseResult.model_validate_json(result.model_dump_json()) == result


def test_bom_infers_quantity_and_retains_dnp_row() -> None:
    result = parse_bom_csv(
        b"Reference,Do Not Populate\nR1 R2,false\nC1,true\n",
        logical_path="bom.csv",
        source_file_id=SOURCE_ID,
    )

    assert result.items[0].quantity == 2
    assert result.items[1].quantity == 0
    assert result.items[1].dnp


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            b"Value,Qty\n10k,1\n",
            "TABULAR_REQUIRED_COLUMN",
        ),
        (
            b"Reference,Qty\nR1 R2,1\n",
            "BOM_QUANTITY_MISMATCH",
        ),
        (
            b"Reference,Qty\nR1,nope\n",
            "BOM_QUANTITY_VALUE",
        ),
        (
            b"Reference,DNP\nR1,maybe\n",
            "BOM_DNP_VALUE",
        ),
        (
            b"Reference\nR3-R1\n",
            "BOM_REFERENCE_RANGE",
        ),
        (
            b"Reference\nR1 R1\n",
            "BOM_REFERENCE_DUPLICATE",
        ),
    ],
)
def test_bom_errors_are_typed(payload: bytes, code: str) -> None:
    with pytest.raises(ParserError) as caught:
        parse_bom_csv(
            payload,
            logical_path="bom.csv",
            source_file_id=SOURCE_ID,
        )

    assert caught.value.code == code
