"""Restricted XLSX preflight and BOM adapter tests."""

from __future__ import annotations

import stat
import warnings
import zipfile
from dataclasses import dataclass
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr

import pytest

from boardgate.ingestion.limits import IngestionLimits
from boardgate.parsers import ParserError
from boardgate.parsers.bom import BOMParseResult, parse_bom_xlsx
from boardgate.parsers.xlsx import parse_xlsx, preflight_xlsx

SOURCE_ID = "src-0123456789abcdef"


@dataclass(frozen=True)
class Formula:
    """Test-only formula marker."""

    expression: str
    cached: str


def _column_label(index: int) -> str:
    result = ""
    current = index + 1
    while current:
        current, remainder = divmod(current - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _cell(value: object, row: int, column: int) -> str:
    reference = f"{_column_label(column)}{row}"
    if isinstance(value, Formula):
        return (
            f'<c r="{reference}"><f>{escape(value.expression)}</f>'
            f"<v>{escape(value.cached)}</v></c>"
        )
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{reference}"><v>{value}</v></c>'
    return f'<c r="{reference}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def _sheet_xml(rows: list[list[object | None]]) -> bytes:
    row_xml = []
    for row_index, values in enumerate(rows, start=1):
        cells = "".join(
            _cell(value, row_index, column_index)
            for column_index, value in enumerate(values)
            if value is not None
        )
        row_xml.append(f'<row r="{row_index}">{cells}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main"><sheetData>'
        + "".join(row_xml)
        + "</sheetData></worksheet>"
    ).encode()


def _workbook(
    sheets: dict[str, list[list[object | None]]],
    *,
    formula: bool = False,
    external: bool = False,
    macro: bool = False,
    extra_members: tuple[tuple[zipfile.ZipInfo | str, bytes], ...] = (),
) -> bytes:
    sheet_items = list(sheets.items())
    if formula:
        sheet_items[0][1][1][1] = Formula("1+1", "2")
    overrides = "".join(
        (
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.worksheet+xml"/>'
        )
        for index in range(1, len(sheet_items) + 1)
    )
    if macro:
        overrides += (
            '<Override PartName="/xl/vbaProject.bin" '
            'ContentType="application/vnd.ms-office.vbaProject"/>'
        )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
        'content-types"><Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        f'spreadsheetml.sheet.main+xml"/>{overrides}</Types>'
    ).encode()
    root_relationships = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        b'relationships"><Relationship Id="rId1" '
        b'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        b'relationships/officeDocument" Target="xl/workbook.xml"/>'
        b"</Relationships>"
    )
    workbook_sheets = "".join(
        (f'<sheet name={quoteattr(name)} sheetId="{index}" r:id="rId{index}"/>')
        for index, (name, _) in enumerate(sheet_items, start=1)
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
        '2006/main" xmlns:r="http://schemas.openxmlformats.org/'
        f'officeDocument/2006/relationships"><sheets>{workbook_sheets}</sheets>'
        "</workbook>"
    ).encode()
    workbook_relationships = "".join(
        (
            f'<Relationship Id="rId{index}" Type="http://schemas.'
            "openxmlformats.org/officeDocument/2006/relationships/worksheet"
            f'" Target="worksheets/sheet{index}.xml"/>'
        )
        for index in range(1, len(sheet_items) + 1)
    )
    if external:
        workbook_relationships += (
            '<Relationship Id="rExternal" Type="http://schemas.openxmlformats.'
            'org/officeDocument/2006/relationships/externalLink" '
            'Target="https://example.invalid/data.xlsx" TargetMode="External"/>'
        )
    workbook_rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
        f'2006/relationships">{workbook_relationships}</Relationships>'
    ).encode()
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_relationships)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml)
        for index, (_, rows) in enumerate(sheet_items, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows))
        if macro:
            archive.writestr("xl/vbaProject.bin", b"not-a-real-macro")
        for member, content in extra_members:
            archive.writestr(member, content)
    return stream.getvalue()


def _rows() -> list[list[object | None]]:
    return [
        [None, "References", "Qty", "Value", "MPN", "DNP"],
        [None, "R1-R2", 2, "10k", "ABC-1", False],
        [None, "C1", 0, "100n", "ABC-2", True],
    ]


def _mark_first_entry_encrypted(payload: bytes) -> bytes:
    marked = bytearray(payload)
    for signature, flag_offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        index = marked.index(signature)
        flags = int.from_bytes(
            marked[index + flag_offset : index + flag_offset + 2],
            "little",
        )
        marked[index + flag_offset : index + flag_offset + 2] = (flags | 0x1).to_bytes(
            2,
            "little",
        )
    return bytes(marked)


def test_bom_xlsx_normalizes_values_and_cell_evidence() -> None:
    result = parse_bom_xlsx(
        _workbook({"BOM": _rows()}),
        logical_path="assembly/bom.xlsx",
        source_file_id=SOURCE_ID,
    )

    assert result.items[0].references == ("R1", "R2")
    assert result.items[0].quantity == 2
    assert result.items[1].dnp
    provenance = result.items[0].provenance
    assert provenance.source_span is None
    assert provenance.parser == "boardgate-bom-xlsx"
    assert provenance.metadata["worksheet"] == "BOM"
    assert provenance.metadata["row_number"] == 2
    assert provenance.metadata["columns"] == ("B:References;C:Qty;D:Value;E:MPN;F:DNP")
    assert BOMParseResult.model_validate_json(result.model_dump_json()) == result


def test_multiple_worksheets_require_exact_selection() -> None:
    payload = _workbook({"BOM": _rows(), "Notes": [["Note"], ["not BOM"]]})

    with pytest.raises(ParserError) as caught:
        parse_bom_xlsx(
            payload,
            logical_path="bom.xlsx",
            source_file_id=SOURCE_ID,
        )
    assert caught.value.code == "XLSX_WORKSHEET_REQUIRED"

    result = parse_bom_xlsx(
        payload,
        logical_path="bom.xlsx",
        source_file_id=SOURCE_ID,
        worksheet="BOM",
    )
    assert len(result.items) == 2

    with pytest.raises(ParserError) as caught:
        parse_xlsx(payload, logical_path="bom.xlsx", worksheet="bom")
    assert caught.value.code == "XLSX_WORKSHEET_NOT_FOUND"


@pytest.mark.parametrize(
    ("payload", "logical_path", "code"),
    [
        (b"not a zip", "bom.xlsx", "XLSX_INVALID_ARCHIVE"),
        (_workbook({"BOM": _rows()}), "bom.xlsm", "XLSX_EXTENSION_REQUIRED"),
        (
            _workbook({"BOM": _rows()}, formula=True),
            "bom.xlsx",
            "XLSX_FORMULA_FORBIDDEN",
        ),
        (
            _workbook({"BOM": _rows()}, external=True),
            "bom.xlsx",
            "XLSX_EXTERNAL_LINK_FORBIDDEN",
        ),
        (
            _workbook({"BOM": _rows()}, macro=True),
            "bom.xlsx",
            "XLSX_MACRO_FORBIDDEN",
        ),
        (
            _workbook(
                {"BOM": _rows()},
                extra_members=(("../escape.xml", b"<root/>"),),
            ),
            "bom.xlsx",
            "XLSX_UNSAFE_PATH",
        ),
        (
            _mark_first_entry_encrypted(_workbook({"BOM": _rows()})),
            "bom.xlsx",
            "XLSX_ENCRYPTED_ENTRY",
        ),
    ],
)
def test_forbidden_workbook_content_is_typed(
    payload: bytes,
    logical_path: str,
    code: str,
) -> None:
    with pytest.raises(ParserError) as caught:
        parse_xlsx(payload, logical_path=logical_path)

    assert caught.value.code == code


def test_malformed_xml_and_compression_ratio_are_rejected() -> None:
    malformed = _workbook(
        {"BOM": _rows()},
        extra_members=(("xl/styles.xml", b"<styles>"),),
    )
    with pytest.raises(ParserError) as caught:
        preflight_xlsx(malformed, logical_path="bom.xlsx")
    assert caught.value.code == "XLSX_XML_INVALID"

    compressed = _workbook(
        {"BOM": _rows()},
        extra_members=(("docProps/repetitive.xml", b"A" * 100_000),),
    )
    with pytest.raises(ParserError) as caught:
        preflight_xlsx(compressed, logical_path="bom.xlsx")
    assert caught.value.code == "XLSX_COMPRESSION_RATIO_LIMIT"


def test_preflight_honors_entry_and_expanded_size_limits() -> None:
    payload = _workbook({"BOM": _rows()})

    with pytest.raises(ParserError) as caught:
        preflight_xlsx(
            payload,
            logical_path="bom.xlsx",
            limits=IngestionLimits(max_file_count=2),
        )
    assert caught.value.code == "XLSX_ENTRY_LIMIT"

    with pytest.raises(ParserError) as caught:
        preflight_xlsx(
            payload,
            logical_path="bom.xlsx",
            limits=IngestionLimits(max_total_expanded_bytes=16),
        )
    assert caught.value.code == "XLSX_EXPANDED_SIZE_LIMIT"


def test_symlink_and_duplicate_normalized_paths_are_rejected() -> None:
    symlink = zipfile.ZipInfo("xl/link.xml")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
    payload = _workbook(
        {"BOM": _rows()},
        extra_members=((symlink, b"target"),),
    )
    with pytest.raises(ParserError) as caught:
        preflight_xlsx(payload, logical_path="bom.xlsx")
    assert caught.value.code == "XLSX_SPECIAL_FILE"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        duplicate = _workbook(
            {"BOM": _rows()},
            extra_members=(("XL/WORKBOOK.XML", b"<workbook/>"),),
        )
    with pytest.raises(ParserError) as caught:
        preflight_xlsx(duplicate, logical_path="bom.xlsx")
    assert caught.value.code == "XLSX_DUPLICATE_PATH"
