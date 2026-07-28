"""Security-preflighted, read-only XLSX table adapter."""

from __future__ import annotations

import datetime as dt
import math
import stat
import zipfile
from io import BytesIO
from pathlib import PurePosixPath
from xml.etree import ElementTree

from python_calamine import CalamineError, CalamineWorkbook, SheetTypeEnum

from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.limits import IngestionLimits
from boardgate.ingestion.paths import normalize_logical_path, path_collision_key
from boardgate.parsers.errors import ParserError
from boardgate.parsers.tabular import (
    MAX_CELL_CHARACTERS,
    MAX_TABULAR_COLUMNS,
    MAX_TABULAR_ROWS,
    TabularData,
    TabularRow,
    build_tabular_data,
)

_CHUNK_BYTES = 1024 * 1024
_REQUIRED_PARTS = frozenset(
    {
        "[content_types].xml",
        "_rels/.rels",
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
    }
)
_FORBIDDEN_PATH_FRAGMENTS = (
    "/activex/",
    "/embeddings/",
    "/externallinks/",
    "/macrosheets/",
    "/oleobjects/",
)
_FORBIDDEN_FILE_NAMES = frozenset({"vbaproject.bin", "vbadata.xml"})
_XML_DECLARATIONS = (b"<!doctype", b"<!entity")


def _error(code: str, logical_path: str, detail: str) -> ParserError:
    return ParserError(code, logical_path, detail)


def _member_path(raw_path: str, logical_path: str) -> str:
    try:
        return normalize_logical_path(raw_path, subject=logical_path)
    except IngestionError as error:
        raise _error(
            "XLSX_UNSAFE_PATH",
            logical_path,
            "workbook contains an unsafe ZIP member path",
        ) from error


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def _is_special_file(info: zipfile.ZipInfo) -> bool:
    kind = stat.S_IFMT(info.external_attr >> 16)
    return kind not in {0, stat.S_IFREG, stat.S_IFDIR}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _xml_root(payload: bytes, *, member: str, logical_path: str) -> ElementTree.Element:
    lowered = payload.lower()
    if any(declaration in lowered for declaration in _XML_DECLARATIONS):
        raise _error(
            "XLSX_XML_DECLARATION_FORBIDDEN",
            logical_path,
            f"forbidden XML declaration in {member}",
        )
    try:
        return ElementTree.fromstring(payload)  # noqa: S314
    except ElementTree.ParseError as error:
        raise _error(
            "XLSX_XML_INVALID",
            logical_path,
            f"malformed XML part: {member}",
        ) from error


def _check_xml_semantics(
    root: ElementTree.Element,
    *,
    member: str,
    logical_path: str,
) -> None:
    member_key = member.casefold()
    if member_key == "[content_types].xml":
        attribute_values = " ".join(
            str(value).casefold()
            for element in root.iter()
            for value in element.attrib.values()
        )
        if (
            "macroenabled" in attribute_values
            or "vbaproject" in attribute_values
            or "macrosheet" in attribute_values
        ):
            raise _error(
                "XLSX_MACRO_FORBIDDEN",
                logical_path,
                "macro-enabled workbook content is rejected",
            )
    if member_key.endswith(".rels") and any(
        _local_name(element.tag) == "relationship"
        and element.attrib.get("TargetMode", "").casefold() == "external"
        for element in root.iter()
    ):
        raise _error(
            "XLSX_EXTERNAL_LINK_FORBIDDEN",
            logical_path,
            "external workbook relationships are rejected",
        )
    if "/worksheets/" not in f"/{member_key}":
        return
    rows = [element for element in root.iter() if _local_name(element.tag) == "row"]
    if len(rows) > MAX_TABULAR_ROWS + 1:
        raise _error(
            "XLSX_ROW_LIMIT",
            logical_path,
            f"worksheet exceeds {MAX_TABULAR_ROWS} data rows",
        )
    for row in rows:
        cells = [element for element in row if _local_name(element.tag) == "c"]
        if len(cells) > MAX_TABULAR_COLUMNS:
            raise _error(
                "XLSX_COLUMN_LIMIT",
                logical_path,
                f"worksheet exceeds {MAX_TABULAR_COLUMNS} columns",
            )
        if any(
            _local_name(element.tag) == "f" for cell in cells for element in cell.iter()
        ):
            raise _error(
                "XLSX_FORMULA_FORBIDDEN",
                logical_path,
                "worksheet formulas are rejected",
            )
        if any(
            len("".join(element.itertext())) > MAX_CELL_CHARACTERS for element in cells
        ):
            raise _error(
                "XLSX_CELL_LIMIT",
                logical_path,
                "worksheet cell exceeds the character limit",
            )


def _read_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    member: str,
    logical_path: str,
    limits: IngestionLimits,
) -> bytes | None:
    is_xml = member.casefold().endswith((".xml", ".rels"))
    content = bytearray() if is_xml else None
    actual_size = 0
    try:
        with archive.open(info) as source:
            while chunk := source.read(_CHUNK_BYTES):
                actual_size += len(chunk)
                if actual_size > info.file_size or actual_size > limits.max_file_bytes:
                    raise _error(
                        "XLSX_SIZE_MISMATCH",
                        logical_path,
                        "expanded workbook part exceeds declared or allowed size",
                    )
                if content is not None:
                    content.extend(chunk)
    except ParserError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise _error(
            "XLSX_ARCHIVE_READ_ERROR",
            logical_path,
            "workbook ZIP member could not be read",
        ) from error
    if actual_size != info.file_size:
        raise _error(
            "XLSX_SIZE_MISMATCH",
            logical_path,
            "expanded workbook part differs from its declared size",
        )
    return bytes(content) if content is not None else None


def _validated_member(
    info: zipfile.ZipInfo,
    *,
    logical_path: str,
    limits: IngestionLimits,
    total_expanded: int,
) -> tuple[str | None, int]:
    if info.flag_bits & 0x1:
        raise _error(
            "XLSX_ENCRYPTED_ENTRY",
            logical_path,
            "encrypted workbook entries are rejected",
        )
    if _is_symlink(info) or _is_special_file(info):
        raise _error(
            "XLSX_SPECIAL_FILE",
            logical_path,
            "workbook symlink and special-file entries are rejected",
        )
    if info.is_dir():
        return None, total_expanded
    member = _member_path(info.filename, logical_path)
    if info.file_size > limits.max_file_bytes:
        raise _error(
            "XLSX_PART_SIZE_LIMIT",
            logical_path,
            f"workbook part exceeds {limits.max_file_bytes} bytes",
        )
    total_expanded += info.file_size
    if total_expanded > limits.max_total_expanded_bytes:
        raise _error(
            "XLSX_EXPANDED_SIZE_LIMIT",
            logical_path,
            "workbook exceeds the total expanded-byte limit",
        )
    ratio = (
        float("inf")
        if info.compress_size == 0 and info.file_size > 0
        else info.file_size / max(info.compress_size, 1)
    )
    if ratio > limits.max_compression_ratio:
        raise _error(
            "XLSX_COMPRESSION_RATIO_LIMIT",
            logical_path,
            "workbook part exceeds the compression-ratio limit",
        )
    return member, total_expanded


def _index_members(
    infos: list[zipfile.ZipInfo],
    *,
    logical_path: str,
    limits: IngestionLimits,
) -> dict[str, tuple[zipfile.ZipInfo, str]]:
    if len(infos) > limits.max_file_count:
        raise _error(
            "XLSX_ENTRY_LIMIT",
            logical_path,
            f"workbook exceeds {limits.max_file_count} ZIP entries",
        )
    paths: dict[str, tuple[zipfile.ZipInfo, str]] = {}
    total_expanded = 0
    for info in infos:
        member, total_expanded = _validated_member(
            info,
            logical_path=logical_path,
            limits=limits,
            total_expanded=total_expanded,
        )
        if member is None:
            continue
        collision_key = path_collision_key(member)
        if collision_key in paths:
            raise _error(
                "XLSX_DUPLICATE_PATH",
                logical_path,
                "workbook contains duplicate normalized ZIP paths",
            )
        paths[collision_key] = (info, member)
    return paths


def preflight_xlsx(
    payload: bytes,
    *,
    logical_path: str,
    limits: IngestionLimits | None = None,
) -> None:
    """Reject unsafe or active XLSX content before invoking calamine."""
    limits = limits or IngestionLimits()
    if PurePosixPath(logical_path).suffix.casefold() != ".xlsx":
        raise _error(
            "XLSX_EXTENSION_REQUIRED",
            logical_path,
            "BOM workbook input must use the .xlsx extension",
        )
    if len(payload) > limits.max_file_bytes:
        raise _error(
            "XLSX_FILE_SIZE_LIMIT",
            logical_path,
            f"workbook exceeds {limits.max_file_bytes} bytes",
        )
    try:
        archive = zipfile.ZipFile(BytesIO(payload))
    except (OSError, zipfile.BadZipFile) as error:
        raise _error(
            "XLSX_INVALID_ARCHIVE",
            logical_path,
            "input is not a valid XLSX ZIP archive",
        ) from error
    with archive:
        paths = _index_members(
            archive.infolist(),
            logical_path=logical_path,
            limits=limits,
        )

        missing = sorted(_REQUIRED_PARTS - paths.keys())
        if missing:
            raise _error(
                "XLSX_REQUIRED_PART_MISSING",
                logical_path,
                "workbook is missing required OOXML parts",
            )
        for _, member in paths.values():
            member_key = f"/{member.casefold()}"
            if PurePosixPath(member).name.casefold() in _FORBIDDEN_FILE_NAMES or any(
                fragment in member_key for fragment in _FORBIDDEN_PATH_FRAGMENTS
            ):
                code = (
                    "XLSX_EXTERNAL_LINK_FORBIDDEN"
                    if "/externallinks/" in member_key
                    else "XLSX_MACRO_FORBIDDEN"
                )
                raise _error(code, logical_path, "active workbook content is rejected")

        for info, member in paths.values():
            xml_payload = _read_member(
                archive,
                info,
                member=member,
                logical_path=logical_path,
                limits=limits,
            )
            if xml_payload is not None:
                _check_xml_semantics(
                    _xml_root(
                        xml_payload,
                        member=member,
                        logical_path=logical_path,
                    ),
                    member=member,
                    logical_path=logical_path,
                )


def _cell_text(value: object, *, logical_path: str, row_number: int) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        result = value.strip()
    elif isinstance(value, bool):
        result = "true" if value else "false"
    elif isinstance(value, int):
        result = str(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise _error(
                "XLSX_CELL_VALUE",
                logical_path,
                f"row {row_number} contains a non-finite number",
            )
        result = str(int(value)) if value.is_integer() else format(value, ".15g")
    elif isinstance(value, (dt.datetime, dt.date, dt.time)):
        result = value.isoformat()
    elif isinstance(value, dt.timedelta):
        result = format(value.total_seconds(), ".15g")
    else:
        raise _error(
            "XLSX_CELL_TYPE",
            logical_path,
            f"row {row_number} contains an unsupported cell type",
        )
    if len(result) > MAX_CELL_CHARACTERS:
        raise _error(
            "XLSX_CELL_LIMIT",
            logical_path,
            f"row {row_number} contains an oversized cell",
        )
    return result


def parse_xlsx(
    payload: bytes,
    *,
    logical_path: str,
    worksheet: str | None = None,
) -> TabularData:
    """Return one bounded worksheet as parser-neutral tabular values."""
    preflight_xlsx(payload, logical_path=logical_path)
    try:
        with CalamineWorkbook.from_filelike(BytesIO(payload)) as workbook:
            worksheets = [
                metadata.name
                for metadata in workbook.sheets_metadata
                if metadata.typ is SheetTypeEnum.WorkSheet
            ]
            if len(worksheets) != len(workbook.sheets_metadata):
                raise _error(
                    "XLSX_SHEET_TYPE",
                    logical_path,
                    "only ordinary worksheets are supported",
                )
            if worksheet is None:
                if len(worksheets) != 1:
                    raise _error(
                        "XLSX_WORKSHEET_REQUIRED",
                        logical_path,
                        "multiple worksheets require an explicit exact name",
                    )
                selected = worksheets[0]
            else:
                if worksheet not in worksheets:
                    raise _error(
                        "XLSX_WORKSHEET_NOT_FOUND",
                        logical_path,
                        "configured worksheet name does not exist",
                    )
                selected = worksheet
            sheet = workbook.get_sheet_by_name(selected)
            start = sheet.start
            if start is None:
                raise _error(
                    "TABULAR_EMPTY",
                    logical_path,
                    "selected worksheet is empty",
                )
            start_row, start_column = start
            parsed: list[TabularRow] = []
            for offset, raw_row in enumerate(sheet.iter_rows()):
                row_number = start_row + offset + 1
                values = tuple(
                    _cell_text(
                        value,
                        logical_path=logical_path,
                        row_number=row_number,
                    )
                    for value in raw_row
                )
                if not any(values):
                    continue
                if len(values) > MAX_TABULAR_COLUMNS:
                    raise _error(
                        "XLSX_COLUMN_LIMIT",
                        logical_path,
                        f"worksheet exceeds {MAX_TABULAR_COLUMNS} columns",
                    )
                parsed.append(
                    TabularRow(
                        values=values,
                        source_span=None,
                        row_number=row_number,
                    )
                )
                if len(parsed) > MAX_TABULAR_ROWS + 1:
                    raise _error(
                        "XLSX_ROW_LIMIT",
                        logical_path,
                        f"worksheet exceeds {MAX_TABULAR_ROWS} data rows",
                    )
    except ParserError:
        raise
    except CalamineError as error:
        raise _error(
            "XLSX_PARSE_FAILED",
            logical_path,
            "calamine could not parse the preflighted workbook",
        ) from error
    return build_tabular_data(
        parsed,
        logical_path=logical_path,
        delimiter=None,
        worksheet=selected,
        column_offset=start_column,
    )
