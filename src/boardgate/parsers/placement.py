"""Normalized component-placement CSV parser."""

from __future__ import annotations

import json
import math

from pydantic import Field

from boardgate import __version__
from boardgate.domain.base import VersionedModel
from boardgate.domain.component import ComponentPlacement
from boardgate.domain.enums import BoardSide
from boardgate.domain.geometry import Point, Unit
from boardgate.domain.identifiers import object_id
from boardgate.domain.provenance import JsonScalar, Provenance
from boardgate.parsers.errors import ParserError
from boardgate.parsers.tabular import parse_csv, resolve_columns

_ALIASES = {
    "reference": frozenset(
        {
            "designator",
            "ref",
            "refdes",
            "reference",
            "referencedesignator",
        }
    ),
    "x": frozenset(
        {
            "centerx",
            "centerxinch",
            "centerxmm",
            "midx",
            "midxinch",
            "midxmm",
            "posx",
            "posxinch",
            "posxmm",
            "positionx",
            "positionxinch",
            "positionxmm",
            "x",
            "xinch",
            "xmm",
        }
    ),
    "y": frozenset(
        {
            "centery",
            "centeryinch",
            "centerymm",
            "midy",
            "midyinch",
            "midymm",
            "posy",
            "posyinch",
            "posymm",
            "positiony",
            "positionyinch",
            "positionymm",
            "y",
            "yinch",
            "ymm",
        }
    ),
    "rotation": frozenset({"angle", "rotation", "rotationdegrees", "rot"}),
    "side": frozenset({"boardside", "layer", "side", "topbottom"}),
    "value": frozenset({"comment", "componentvalue", "value"}),
    "footprint": frozenset({"footprint", "package", "pattern"}),
    "unit": frozenset({"coordinateunit", "units", "unit"}),
}
_TOP_VALUES = frozenset({"f", "front", "t", "top"})
_BOTTOM_VALUES = frozenset({"b", "back", "bottom"})


class PlacementParseResult(VersionedModel):
    """Normalized placement rows."""

    source_file_id: str = Field(pattern=r"^src-[0-9a-f]{16}$")
    source_unit: Unit
    placements: tuple[ComponentPlacement, ...] = ()


def _header_unit(header: str) -> Unit | None:
    normalized = header.casefold()
    if "mm" in normalized or "millimet" in normalized:
        return Unit.MILLIMETRE
    if "inch" in normalized or normalized.endswith("in"):
        return Unit.INCH
    return None


def _determine_unit(
    *,
    table_headers: tuple[str, ...],
    columns: dict[str, int],
    rows: tuple[tuple[str, ...], ...],
    explicit: Unit | None,
    logical_path: str,
) -> Unit:
    header_units = {
        unit
        for key in ("x", "y")
        for unit in (_header_unit(table_headers[columns[key]]),)
        if unit is not None
    }
    if len(header_units) > 1:
        raise ParserError(
            "PLACEMENT_UNIT_CONFLICT",
            logical_path,
            "X and Y headers declare conflicting units",
        )
    declared = next(iter(header_units), None)
    unit_column = columns.get("unit")
    row_units: set[Unit] = set()
    if unit_column is not None:
        for row in rows:
            value = row[unit_column].strip().casefold()
            if value in {"mm", "millimeter", "millimetre"}:
                row_units.add(Unit.MILLIMETRE)
            elif value in {"in", "inch", "inches"}:
                row_units.add(Unit.INCH)
            else:
                raise ParserError(
                    "PLACEMENT_UNIT_VALUE",
                    logical_path,
                    "placement unit column contains an unsupported value",
                )
    if len(row_units) > 1:
        raise ParserError(
            "PLACEMENT_UNIT_CONFLICT",
            logical_path,
            "placement rows contain mixed coordinate units",
        )
    row_unit = next(iter(row_units), None)
    candidates = {unit for unit in (explicit, declared, row_unit) if unit is not None}
    if len(candidates) > 1:
        raise ParserError(
            "PLACEMENT_UNIT_CONFLICT",
            logical_path,
            "placement unit evidence conflicts",
        )
    if not candidates:
        raise ParserError(
            "PLACEMENT_UNIT_AMBIGUOUS",
            logical_path,
            "placement coordinate unit must be explicit",
        )
    return next(iter(candidates))


def _number(
    value: str,
    *,
    label: str,
    logical_path: str,
    row_number: int,
) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise ParserError(
            "PLACEMENT_NUMBER_VALUE",
            logical_path,
            f"row {row_number} {label} is not numeric",
        ) from error
    if not math.isfinite(number):
        raise ParserError(
            "PLACEMENT_NUMBER_VALUE",
            logical_path,
            f"row {row_number} {label} must be finite",
        )
    return number


def _side(value: str, logical_path: str, row_number: int) -> BoardSide:
    normalized = value.strip().casefold()
    if normalized in _TOP_VALUES:
        return BoardSide.TOP
    if normalized in _BOTTOM_VALUES:
        return BoardSide.BOTTOM
    raise ParserError(
        "PLACEMENT_SIDE_VALUE",
        logical_path,
        f"row {row_number} has an unsupported board side",
    )


def _optional(row: tuple[str, ...], columns: dict[str, int], key: str) -> str | None:
    index = columns.get(key)
    value = row[index].strip() if index is not None else ""
    return value or None


def parse_placement_csv(
    payload: bytes,
    *,
    logical_path: str,
    source_file_id: str,
    coordinate_unit: Unit | None = None,
) -> PlacementParseResult:
    """Parse placement anchors with an explicit, normalized source unit."""
    table = parse_csv(payload, logical_path=logical_path)
    columns = resolve_columns(
        table,
        aliases=_ALIASES,
        required=frozenset({"reference", "x", "y", "rotation", "side"}),
        logical_path=logical_path,
    )
    unit = _determine_unit(
        table_headers=table.headers,
        columns=columns,
        rows=tuple(row.values for row in table.rows),
        explicit=coordinate_unit,
        logical_path=logical_path,
    )
    placements: list[ComponentPlacement] = []
    for index, row in enumerate(table.rows):
        reference = row.values[columns["reference"]].strip().upper()
        if not reference:
            raise ParserError(
                "PLACEMENT_REFERENCE_EMPTY",
                logical_path,
                f"row {row.row_number} has no reference",
            )
        x = _number(
            row.values[columns["x"]],
            label="X",
            logical_path=logical_path,
            row_number=row.row_number,
        )
        y = _number(
            row.values[columns["y"]],
            label="Y",
            logical_path=logical_path,
            row_number=row.row_number,
        )
        rotation = _number(
            row.values[columns["rotation"]],
            label="rotation",
            logical_path=logical_path,
            row_number=row.row_number,
        )
        if unit is Unit.INCH:
            x *= 25.4
            y *= 25.4
        raw_signature = json.dumps(row.values, ensure_ascii=False)
        identifier = object_id(
            "placement",
            source_file_id,
            index,
            raw_signature,
        )
        mapped_indices = set(columns.values())
        metadata: dict[str, JsonScalar] = {
            table.headers[column_index]: value
            for column_index, value in enumerate(row.values)
            if column_index not in mapped_indices and value
        }
        placements.append(
            ComponentPlacement(
                reference=reference,
                position=Point(x=x, y=y),
                rotation_degrees=rotation,
                side=_side(
                    row.values[columns["side"]],
                    logical_path,
                    row.row_number,
                ),
                value=_optional(row.values, columns, "value"),
                footprint=_optional(row.values, columns, "footprint"),
                provenance=Provenance(
                    source_file_id=source_file_id,
                    object_id=identifier,
                    parser="boardgate-placement-csv",
                    parser_version=__version__,
                    source_span=row.source_span,
                    raw_coordinates={
                        "x": row.values[columns["x"]],
                        "y": row.values[columns["y"]],
                        "unit": unit.value,
                    },
                    metadata={"row_number": row.row_number},
                ),
                metadata=metadata,
            )
        )
    return PlacementParseResult(
        source_file_id=source_file_id,
        source_unit=unit,
        placements=tuple(placements),
    )
