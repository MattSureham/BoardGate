"""Normalized BOM CSV parser."""

from __future__ import annotations

import json
import re

from pydantic import Field

from boardgate import __version__
from boardgate.domain.base import VersionedModel
from boardgate.domain.component import BOMItem
from boardgate.domain.identifiers import object_id
from boardgate.domain.provenance import JsonScalar, Provenance
from boardgate.parsers.errors import ParserError
from boardgate.parsers.tabular import (
    TabularData,
    TabularRow,
    parse_csv,
    resolve_columns,
)
from boardgate.parsers.xlsx import parse_xlsx

_ALIASES = {
    "references": frozenset(
        {
            "designator",
            "designators",
            "ref",
            "refdes",
            "reference",
            "referencedesignator",
            "references",
            "refs",
        }
    ),
    "quantity": frozenset({"count", "quantity", "qty"}),
    "part_number": frozenset(
        {
            "manufacturerpartnumber",
            "mpn",
            "partnumber",
            "pn",
        }
    ),
    "value": frozenset({"comment", "componentvalue", "value"}),
    "footprint": frozenset({"footprint", "package", "pattern"}),
    "dnp": frozenset(
        {
            "dnp",
            "donotfit",
            "donotplace",
            "donotpopulate",
            "fitted",
            "populate",
        }
    ),
}
_REFERENCE_SPLIT = re.compile(r"[\s,;]+")
_REFERENCE_RANGE = re.compile(
    r"^(?P<prefix>[A-Za-z]+)(?P<start>\d+)-(?:(?P=prefix))?(?P<end>\d+)$"
)
_MAX_REFERENCE_RANGE = 10_000
_TRUE_DNP = frozenset(
    {"1", "dnp", "dnf", "do not fit", "do not place", "do not populate", "true", "yes"}
)
_FALSE_DNP = frozenset({"", "0", "false", "fit", "fitted", "no", "populate"})


class BOMParseResult(VersionedModel):
    """Normalized BOM rows."""

    source_file_id: str = Field(pattern=r"^src-[0-9a-f]{16}$")
    items: tuple[BOMItem, ...] = ()


def _references(value: str, logical_path: str, row_number: int) -> tuple[str, ...]:
    references: list[str] = []
    for token in filter(None, _REFERENCE_SPLIT.split(value.strip())):
        if match := _REFERENCE_RANGE.match(token):
            start = int(match.group("start"))
            end = int(match.group("end"))
            if end < start or end - start > _MAX_REFERENCE_RANGE:
                raise ParserError(
                    "BOM_REFERENCE_RANGE",
                    logical_path,
                    f"invalid reference range at row {row_number}",
                )
            references.extend(
                f"{match.group('prefix').upper()}{index}"
                for index in range(start, end + 1)
            )
        else:
            references.append(token.upper())
    if not references:
        raise ParserError(
            "BOM_REFERENCE_EMPTY",
            logical_path,
            f"row {row_number} has no references",
        )
    if len(references) != len(set(references)):
        raise ParserError(
            "BOM_REFERENCE_DUPLICATE",
            logical_path,
            f"row {row_number} repeats a reference",
        )
    return tuple(references)


def _dnp(
    value: str,
    *,
    header: str,
    logical_path: str,
    row_number: int,
) -> bool:
    normalized = value.strip().casefold()
    header_normalized = header.casefold()
    if header_normalized in {"fitted", "populate"}:
        if normalized in {"", "1", "true", "yes", "fitted", "populate"}:
            return False
        if normalized in {"0", "false", "no", "dnp", "dnf"}:
            return True
    if normalized in _TRUE_DNP:
        return True
    if normalized in _FALSE_DNP:
        return False
    raise ParserError(
        "BOM_DNP_VALUE",
        logical_path,
        f"row {row_number} has an unrecognized DNP value",
    )


def _optional(row: tuple[str, ...], columns: dict[str, int], key: str) -> str | None:
    index = columns.get(key)
    value = row[index].strip() if index is not None else ""
    return value or None


def _column_label(index: int) -> str:
    label = ""
    current = index + 1
    while current:
        current, remainder = divmod(current - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


def _source_metadata(
    table: TabularData,
    row: TabularRow,
) -> dict[str, JsonScalar]:
    metadata: dict[str, JsonScalar] = {"row_number": row.row_number}
    if table.worksheet is not None:
        metadata["worksheet"] = table.worksheet
        metadata["columns"] = ";".join(
            f"{_column_label(table.column_offset + index)}:{header}"
            for index, header in enumerate(table.headers)
        )
    return metadata


def _parse_bom_table(
    table: TabularData,
    *,
    logical_path: str,
    source_file_id: str,
    parser_name: str,
) -> BOMParseResult:
    columns = resolve_columns(
        table,
        aliases=_ALIASES,
        required=frozenset({"references"}),
        logical_path=logical_path,
    )
    items: list[BOMItem] = []
    for index, row in enumerate(table.rows):
        references = _references(
            row.values[columns["references"]],
            logical_path,
            row.row_number,
        )
        dnp_index = columns.get("dnp")
        dnp = (
            _dnp(
                row.values[dnp_index],
                header=table.normalized_headers[dnp_index],
                logical_path=logical_path,
                row_number=row.row_number,
            )
            if dnp_index is not None
            else False
        )
        quantity_index = columns.get("quantity")
        if quantity_index is None or not row.values[quantity_index]:
            quantity = 0 if dnp else len(references)
        else:
            try:
                quantity = int(row.values[quantity_index])
            except ValueError as error:
                raise ParserError(
                    "BOM_QUANTITY_VALUE",
                    logical_path,
                    f"row {row.row_number} quantity is not an integer",
                ) from error
            if quantity < 0:
                raise ParserError(
                    "BOM_QUANTITY_VALUE",
                    logical_path,
                    f"row {row.row_number} quantity must be non-negative",
                )
        if quantity not in {0, len(references)}:
            raise ParserError(
                "BOM_QUANTITY_MISMATCH",
                logical_path,
                f"row {row.row_number} quantity does not match references",
            )
        if quantity == 0 and not dnp:
            raise ParserError(
                "BOM_QUANTITY_VALUE",
                logical_path,
                f"row {row.row_number} zero quantity requires DNP",
            )
        raw_signature = json.dumps(
            (table.worksheet, row.row_number, row.values),
            ensure_ascii=False,
        )
        identifier = object_id("bom", source_file_id, index, raw_signature)
        mapped_indices = set(columns.values())
        metadata: dict[str, JsonScalar] = {
            table.headers[column_index]: value
            for column_index, value in enumerate(row.values)
            if column_index not in mapped_indices and value
        }
        items.append(
            BOMItem(
                references=references,
                quantity=quantity,
                part_number=_optional(row.values, columns, "part_number"),
                value=_optional(row.values, columns, "value"),
                footprint=_optional(row.values, columns, "footprint"),
                dnp=dnp,
                provenance=Provenance(
                    source_file_id=source_file_id,
                    object_id=identifier,
                    parser=parser_name,
                    parser_version=__version__,
                    source_span=row.source_span,
                    metadata=_source_metadata(table, row),
                ),
                metadata=metadata,
            )
        )
    return BOMParseResult(source_file_id=source_file_id, items=tuple(items))


def parse_bom_csv(
    payload: bytes,
    *,
    logical_path: str,
    source_file_id: str,
) -> BOMParseResult:
    """Parse one BOM CSV without discarding DNP rows."""
    return _parse_bom_table(
        parse_csv(payload, logical_path=logical_path),
        logical_path=logical_path,
        source_file_id=source_file_id,
        parser_name="boardgate-bom-csv",
    )


def parse_bom_xlsx(
    payload: bytes,
    *,
    logical_path: str,
    source_file_id: str,
    worksheet: str | None = None,
) -> BOMParseResult:
    """Parse one preflighted XLSX BOM through the read-only adapter."""
    return _parse_bom_table(
        parse_xlsx(payload, logical_path=logical_path, worksheet=worksheet),
        logical_path=logical_path,
        source_file_id=source_file_id,
        parser_name="boardgate-bom-xlsx",
    )
