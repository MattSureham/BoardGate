"""Gerbonara-backed Excellon adapter."""

from __future__ import annotations

import re
import warnings
from typing import Literal, Self

import gerbonara
from gerbonara.excellon import ExcellonFile
from gerbonara.graphic_objects import Arc, Flash, Line
from gerbonara.utils import MM, Inch
from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.drill import DrillHit, DrillSlot
from boardgate.domain.enums import Plating
from boardgate.domain.geometry import Point, Unit
from boardgate.domain.identifiers import object_id
from boardgate.domain.provenance import Provenance, SourceSpan
from boardgate.parsers.errors import ParserError
from boardgate.parsers.models import DiagnosticLevel, ParserDiagnostic
from boardgate.parsers.scanner import (
    CommandWitness,
    scan_excellon_object_commands,
    span_for_line,
)

_WARNING_LINE = re.compile(r":(\d+)\s+\"")
_MAX_DIAGNOSTIC_LENGTH = 500
_COORDINATE_FORMAT_PARTS = 2


class ExcellonParseResult(VersionedModel):
    """Normalized Excellon output with no Gerbonara objects."""

    source_file_id: str = Field(pattern=r"^src-[0-9a-f]{16}$")
    original_unit: Unit
    notation: Literal["absolute", "incremental"]
    zero_suppression: Literal["leading", "trailing", "none"]
    coordinate_format: tuple[int, int] | None
    drills: tuple[DrillHit, ...] = ()
    slots: tuple[DrillSlot, ...] = ()
    warnings: tuple[ParserDiagnostic, ...] = ()
    limitations: tuple[ParserDiagnostic, ...] = ()
    generator_hints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_unique_features(self) -> Self:
        """Keep adapter feature identifiers unique."""
        identifiers = [
            *(drill.drill_id for drill in self.drills),
            *(slot.slot_id for slot in self.slots),
        ]
        if len(identifiers) != len(set(identifiers)):
            msg = "Excellon feature identifiers must be unique"
            raise ValueError(msg)
        return self


def _decode(payload: bytes, logical_path: str) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ParserError(
            "EXCELLON_ENCODING_ERROR",
            logical_path,
            "Excellon input must be UTF-8-compatible ASCII text",
        ) from error


def _source_unit(settings: object, logical_path: str) -> Unit:
    unit = getattr(settings, "unit", None)
    if unit == MM:
        return Unit.MILLIMETRE
    if unit == Inch:
        return Unit.INCH
    raise ParserError(
        "EXCELLON_UNIT_UNKNOWN",
        logical_path,
        "parser could not determine an explicit source unit",
    )


def _plating(value: bool | None) -> Plating:
    if value is True:
        return Plating.PLATED
    if value is False:
        return Plating.NON_PLATED
    return Plating.UNKNOWN


def _warning_span(payload: bytes, message: str) -> SourceSpan | None:
    match = _WARNING_LINE.search(message)
    return span_for_line(payload, int(match.group(1))) if match else None


def _clean_message(message: str, logical_path: str) -> str:
    cleaned = message.replace(logical_path, "<source>")
    return cleaned[:_MAX_DIAGNOSTIC_LENGTH]


def _diagnostics(
    captured: list[warnings.WarningMessage],
    *,
    payload: bytes,
    logical_path: str,
) -> tuple[tuple[ParserDiagnostic, ...], tuple[ParserDiagnostic, ...]]:
    regular: list[ParserDiagnostic] = []
    limitations: list[ParserDiagnostic] = []
    for item in captured:
        message = _clean_message(str(item.message), logical_path)
        ignored = (
            "intended for CAM tools" in message
            or "Ignoring" in message
            or "without radius" in message
        )
        diagnostic = ParserDiagnostic(
            code=(
                "EXCELLON_COMMAND_LIMITATION" if ignored else "EXCELLON_PARSER_WARNING"
            ),
            level=(DiagnosticLevel.LIMITATION if ignored else DiagnosticLevel.WARNING),
            message=message,
            source_span=_warning_span(payload, str(item.message)),
        )
        (limitations if ignored else regular).append(diagnostic)
    return tuple(regular), tuple(limitations)


def _provenance(
    *,
    source_file_id: str,
    identifier: str,
    witness: CommandWitness | None,
    source_unit: Unit,
) -> Provenance:
    metadata: dict[str, str | int | float | bool | None] = {
        "source_unit": source_unit.value,
    }
    raw_coordinates: dict[str, str | int | float | bool | None] = {}
    source_span = None
    if witness is not None:
        metadata["raw_command"] = witness.raw_command
        if witness.tool_code is not None:
            metadata["tool_code"] = witness.tool_code
        raw_coordinates.update(dict(witness.raw_coordinates))
        source_span = witness.source_span
    return Provenance(
        source_file_id=source_file_id,
        object_id=identifier,
        parser="gerbonara-excellon-adapter",
        parser_version=gerbonara.__version__,
        source_span=source_span,
        raw_coordinates=raw_coordinates,
        metadata=metadata,
    )


def _coordinate_format(settings: object) -> tuple[int, int] | None:
    value = getattr(settings, "number_format", None)
    if (
        isinstance(value, tuple)
        and len(value) == _COORDINATE_FORMAT_PARTS
        and all(isinstance(item, int) for item in value)
    ):
        return value
    return None


def _zero_suppression(settings: object) -> Literal["leading", "trailing", "none"]:
    value = getattr(settings, "zeros", None)
    if value == "leading":
        return "leading"
    if value == "trailing":
        return "trailing"
    return "none"


def parse_excellon(
    payload: bytes,
    *,
    logical_path: str,
    source_file_id: str,
    plating_hint: Plating = Plating.UNKNOWN,
) -> ExcellonParseResult:
    """Parse Excellon into immutable BoardGate drills and analytic slots."""
    text = _decode(payload, logical_path)
    plated = {
        Plating.PLATED: True,
        Plating.NON_PLATED: False,
        Plating.UNKNOWN: None,
    }[plating_hint]
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            parsed = ExcellonFile.from_string(
                text,
                filename=logical_path,
                plated=plated,
            )
    except (SyntaxError, TypeError, ValueError) as error:
        detail = _clean_message(str(error), logical_path)
        code = (
            "EXCELLON_UNSUPPORTED_COMMAND"
            if "Unknown excellon statement" in detail
            or "not supported" in detail.casefold()
            else "EXCELLON_PARSE_ERROR"
        )
        raise ParserError(code, logical_path, detail) from error
    settings = parsed.import_settings
    source_unit = _source_unit(settings, logical_path)
    command_witnesses = scan_excellon_object_commands(payload)
    regular_warnings, limitations = _diagnostics(
        captured,
        payload=payload,
        logical_path=logical_path,
    )
    mutable_limitations = list(limitations)
    if getattr(settings, "notation", "absolute") == "incremental":
        mutable_limitations.append(
            ParserDiagnostic(
                code="EXCELLON_INCREMENTAL_NOTATION",
                level=DiagnosticLevel.LIMITATION,
                message=(
                    "Incremental notation was parsed but is outside BoardGate "
                    "v1 full-coverage scope."
                ),
            )
        )
    if len(command_witnesses) != len(parsed.objects):
        mutable_limitations.append(
            ParserDiagnostic(
                code="EXCELLON_PROVENANCE_ALIGNMENT_PARTIAL",
                level=DiagnosticLevel.LIMITATION,
                message=(
                    "Command scanner and parser object counts differ; unmatched "
                    "source spans remain null."
                ),
            )
        )

    drills: list[DrillHit] = []
    slots: list[DrillSlot] = []
    for index, feature in enumerate(parsed.objects):
        witness = command_witnesses[index] if index < len(command_witnesses) else None
        raw_signature = (
            witness.raw_command
            if witness is not None
            else f"{type(feature).__name__}:{index}"
        )
        tool_code = witness.tool_code if witness is not None else None
        diameter = float(feature.tool.equivalent_width(MM))
        feature_plating = _plating(
            feature.plated if feature.plated is not None else plated
        )
        if isinstance(feature, Flash):
            identifier = object_id(
                "drill",
                source_file_id,
                index,
                raw_signature,
            )
            drills.append(
                DrillHit(
                    drill_id=identifier,
                    position=Point(
                        x=float(MM(feature.x, feature.unit)),
                        y=float(MM(feature.y, feature.unit)),
                    ),
                    diameter_mm=diameter,
                    tool_code=tool_code,
                    plating=feature_plating,
                    provenance=_provenance(
                        source_file_id=source_file_id,
                        identifier=identifier,
                        witness=witness,
                        source_unit=source_unit,
                    ),
                )
            )
        elif isinstance(feature, Line | Arc):
            identifier = object_id(
                "slot",
                source_file_id,
                index,
                raw_signature,
            )
            start = Point(
                x=float(MM(feature.x1, feature.unit)),
                y=float(MM(feature.y1, feature.unit)),
            )
            end = Point(
                x=float(MM(feature.x2, feature.unit)),
                y=float(MM(feature.y2, feature.unit)),
            )
            provenance = _provenance(
                source_file_id=source_file_id,
                identifier=identifier,
                witness=witness,
                source_unit=source_unit,
            )
            if isinstance(feature, Arc):
                center_x, center_y = feature.center
                slots.append(
                    DrillSlot(
                        kind="arc",
                        slot_id=identifier,
                        start=start,
                        end=end,
                        center=Point(
                            x=float(MM(center_x, feature.unit)),
                            y=float(MM(center_y, feature.unit)),
                        ),
                        clockwise=bool(feature.clockwise),
                        width_mm=diameter,
                        tool_code=tool_code,
                        plating=feature_plating,
                        provenance=provenance,
                    )
                )
            else:
                slots.append(
                    DrillSlot(
                        kind="line",
                        slot_id=identifier,
                        start=start,
                        end=end,
                        width_mm=diameter,
                        tool_code=tool_code,
                        plating=feature_plating,
                        provenance=provenance,
                    )
                )
        else:
            mutable_limitations.append(
                ParserDiagnostic(
                    code="EXCELLON_OBJECT_UNSUPPORTED",
                    level=DiagnosticLevel.LIMITATION,
                    message=f"Unsupported parser object {type(feature).__name__}.",
                )
            )
    return ExcellonParseResult(
        source_file_id=source_file_id,
        original_unit=source_unit,
        notation=getattr(settings, "notation", "absolute"),
        zero_suppression=_zero_suppression(settings),
        coordinate_format=_coordinate_format(settings),
        drills=tuple(drills),
        slots=tuple(slots),
        warnings=regular_warnings,
        limitations=tuple(mutable_limitations),
        generator_hints=tuple(sorted(set(parsed.generator_hints))),
    )
