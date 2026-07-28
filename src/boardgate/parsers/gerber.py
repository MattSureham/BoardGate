"""Gerbonara-backed Gerber analytic-primitive adapter."""

from __future__ import annotations

import math
import re
import warnings
from typing import Literal, Protocol, Self, cast

import gerbonara
from gerbonara.apertures import (
    ApertureMacroInstance,
    CircleAperture,
    ObroundAperture,
    PolygonAperture,
    RectangleAperture,
)
from gerbonara.graphic_objects import Arc, Flash, Line, Region
from gerbonara.rs274x import GerberFile
from gerbonara.utils import MM, Inch
from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import ApertureShape, Polarity
from boardgate.domain.geometry import BoundingBox, Point, Unit
from boardgate.domain.identifiers import object_id
from boardgate.domain.layer import (
    Aperture,
    ArcPrimitive,
    FlashPrimitive,
    GraphicPrimitive,
    LinePrimitive,
    RegionArcSegment,
    RegionLineSegment,
    RegionPrimitive,
    RegionSegment,
)
from boardgate.domain.provenance import Provenance
from boardgate.parsers.errors import ParserError
from boardgate.parsers.gerber_scanner import (
    GerberCommandWitness,
    gerber_span_for_line,
    scan_gerber_object_commands,
    scan_gerber_tokens,
)
from boardgate.parsers.models import DiagnosticLevel, ParserDiagnostic

_WARNING_LINE = re.compile(r":(\d+)\s+\"")
_INCLUDE_COMMAND = re.compile(r"^IF", re.IGNORECASE)
_MAX_DIAGNOSTIC_LENGTH = 500
_COORDINATE_FORMAT_PARTS = 2

type _Bounds = tuple[tuple[float, float], tuple[float, float]]


class _BoundedAperture(Protocol):
    def bounding_box(self, unit: object) -> _Bounds:
        """Return aperture-local bounds."""


class GerberParseResult(VersionedModel):
    """Normalized Gerber output with no Gerbonara or Shapely objects."""

    source_file_id: str = Field(pattern=r"^src-[0-9a-f]{16}$")
    original_unit: Unit
    notation: Literal["absolute", "incremental"]
    zero_suppression: Literal["leading", "trailing", "none"]
    coordinate_format: tuple[int, int] | None
    file_attributes: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    layer_hints: tuple[str, ...] = ()
    primitives: tuple[GraphicPrimitive, ...] = ()
    bounding_box: BoundingBox | None = None
    warnings: tuple[ParserDiagnostic, ...] = ()
    limitations: tuple[ParserDiagnostic, ...] = ()
    generator_hints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_unique_primitives(self) -> Self:
        """Keep adapter primitive identifiers unique."""
        identifiers = [primitive.primitive_id for primitive in self.primitives]
        if len(identifiers) != len(set(identifiers)):
            msg = "Gerber primitive identifiers must be unique"
            raise ValueError(msg)
        return self


def _decode(payload: bytes, logical_path: str) -> str:
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ParserError(
            "GERBER_ENCODING_ERROR",
            logical_path,
            "Gerber input must be UTF-8 as required by the format",
        ) from error


def _clean_message(message: str, logical_path: str) -> str:
    return message.replace(logical_path, "<source>")[:_MAX_DIAGNOSTIC_LENGTH]


def _source_unit(settings: object, logical_path: str) -> Unit:
    unit = getattr(settings, "unit", None)
    if unit == MM:
        return Unit.MILLIMETRE
    if unit == Inch:
        return Unit.INCH
    raise ParserError(
        "GERBER_UNIT_UNKNOWN",
        logical_path,
        "parser could not determine an explicit source unit",
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


def _point(x: float, y: float, unit: object) -> Point:
    return Point(x=float(MM(x, unit)), y=float(MM(y, unit)))


def _polarity(feature: object) -> Polarity:
    return (
        Polarity.DARK
        if bool(getattr(feature, "polarity_dark", False))
        else Polarity.CLEAR
    )


def _hole_diameter(aperture: object) -> float | None:
    value = getattr(aperture, "hole_dia", None)
    unit = getattr(aperture, "unit", None)
    return float(MM(value, unit)) if value is not None else None


def _macro_aperture(aperture: _BoundedAperture) -> Aperture:
    try:
        (minimum_x, minimum_y), (maximum_x, maximum_y) = aperture.bounding_box(MM)
    except (TypeError, ValueError) as error:
        raise ParserError(
            "GERBER_MACRO_BOUNDS_ERROR",
            "<aperture>",
            "macro aperture bounds could not be derived",
        ) from error
    width = float(maximum_x - minimum_x)
    height = float(maximum_y - minimum_y)
    if width <= 0.0 or height <= 0.0:
        raise ParserError(
            "GERBER_MACRO_BOUNDS_ERROR",
            "<aperture>",
            "macro aperture bounds are empty",
        )
    macro = getattr(aperture, "macro", None)
    macro_name = str(getattr(macro, "name", "<unnamed>"))
    return Aperture(
        shape=ApertureShape.MACRO,
        width_mm=width,
        height_mm=height,
        macro_name=macro_name,
    )


def _normalize_aperture(aperture: object) -> Aperture:
    unit = getattr(aperture, "unit", None)
    hole = _hole_diameter(aperture)
    if isinstance(aperture, CircleAperture):
        width = float(MM(aperture.diameter, unit))
        return Aperture(
            shape=ApertureShape.CIRCLE,
            width_mm=width,
            height_mm=width,
            hole_diameter_mm=hole,
        )
    if isinstance(aperture, RectangleAperture):
        return Aperture(
            shape=ApertureShape.RECTANGLE,
            width_mm=float(MM(aperture.w, unit)),
            height_mm=float(MM(aperture.h, unit)),
            hole_diameter_mm=hole,
        )
    if isinstance(aperture, ObroundAperture):
        return Aperture(
            shape=ApertureShape.OBROUND,
            width_mm=float(MM(aperture.w, unit)),
            height_mm=float(MM(aperture.h, unit)),
            hole_diameter_mm=hole,
        )
    if isinstance(aperture, PolygonAperture):
        width = float(MM(aperture.diameter, unit))
        return Aperture(
            shape=ApertureShape.POLYGON,
            width_mm=width,
            height_mm=width,
            hole_diameter_mm=hole,
            rotation_degrees=math.degrees(aperture.rotation),
            vertices=int(aperture.n_vertices),
        )
    if isinstance(aperture, ApertureMacroInstance):
        return _macro_aperture(cast(_BoundedAperture, aperture))
    raise ParserError(
        "GERBER_APERTURE_UNSUPPORTED",
        "<aperture>",
        f"unsupported aperture type {type(aperture).__name__}",
    )


def _provenance(
    *,
    source_file_id: str,
    identifier: str,
    witness: GerberCommandWitness | None,
    source_unit: Unit,
    aperture: object | None,
) -> Provenance:
    metadata: dict[str, str | int | float | bool | None] = {
        "source_unit": source_unit.value,
    }
    raw_coordinates: dict[str, str | int | float | bool | None] = {}
    source_span = None
    if witness is not None:
        metadata["raw_command"] = witness.raw_command
        if witness.aperture_code is not None:
            metadata["aperture_code"] = witness.aperture_code
        raw_coordinates.update(dict(witness.raw_coordinates))
        source_span = witness.source_span
    original_number = getattr(aperture, "original_number", None)
    if original_number is not None:
        metadata["aperture_number"] = int(original_number)
    return Provenance(
        source_file_id=source_file_id,
        object_id=identifier,
        parser="gerbonara-gerber-adapter",
        parser_version=gerbonara.__version__,
        source_span=source_span,
        raw_coordinates=raw_coordinates,
        metadata=metadata,
    )


def _warning_diagnostics(
    captured: list[warnings.WarningMessage],
    *,
    payload: bytes,
    logical_path: str,
) -> tuple[tuple[ParserDiagnostic, ...], tuple[ParserDiagnostic, ...]]:
    regular: list[ParserDiagnostic] = []
    limitations: list[ParserDiagnostic] = []
    for item in captured:
        original = str(item.message)
        message = _clean_message(original, logical_path)
        limited = "Unknown statement" in message or "ignoring" in message.casefold()
        match = _WARNING_LINE.search(original)
        diagnostic = ParserDiagnostic(
            code=("GERBER_COMMAND_LIMITATION" if limited else "GERBER_PARSER_WARNING"),
            level=(DiagnosticLevel.LIMITATION if limited else DiagnosticLevel.WARNING),
            message=message,
            source_span=(
                gerber_span_for_line(payload, int(match.group(1)))
                if match is not None
                else None
            ),
        )
        (limitations if limited else regular).append(diagnostic)
    return tuple(regular), tuple(limitations)


def _region_segments(feature: Region) -> tuple[RegionSegment, ...]:
    segments: list[RegionSegment] = []
    for start, end, arc in feature.iter_segments():
        clockwise, center = arc
        if clockwise is None:
            segments.append(
                RegionLineSegment(
                    start=_point(start[0], start[1], feature.unit),
                    end=_point(end[0], end[1], feature.unit),
                )
            )
        else:
            segments.append(
                RegionArcSegment(
                    start=_point(start[0], start[1], feature.unit),
                    end=_point(end[0], end[1], feature.unit),
                    center=_point(center[0], center[1], feature.unit),
                    clockwise=bool(clockwise),
                )
            )
    return tuple(segments)


def _bounding_box(parsed: GerberFile) -> BoundingBox | None:
    bounds = parsed.bounding_box(MM, default=None)
    if bounds is None:
        return None
    minimum, maximum = bounds
    return BoundingBox(
        minimum=Point(x=minimum[0], y=minimum[1]),
        maximum=Point(x=maximum[0], y=maximum[1]),
    )


def parse_gerber(  # noqa: PLR0912, PLR0915
    payload: bytes,
    *,
    logical_path: str,
    source_file_id: str,
) -> GerberParseResult:
    """Parse Gerber into immutable analytic BoardGate primitives."""
    text = _decode(payload, logical_path)
    if any(
        _INCLUDE_COMMAND.match(token.command) for token in scan_gerber_tokens(payload)
    ):
        raise ParserError(
            "GERBER_INCLUDE_REJECTED",
            logical_path,
            "Gerber include commands are disabled",
        )
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            parsed = GerberFile.from_string(text, filename=logical_path)
    except (SyntaxError, TypeError, ValueError) as error:
        detail = _clean_message(str(error), logical_path)
        raise ParserError("GERBER_PARSE_ERROR", logical_path, detail) from error
    settings = parsed.import_settings
    source_unit = _source_unit(settings, logical_path)
    witnesses = scan_gerber_object_commands(payload)
    regular_warnings, limitations = _warning_diagnostics(
        captured,
        payload=payload,
        logical_path=logical_path,
    )
    mutable_limitations = list(limitations)
    if getattr(settings, "notation", "absolute") == "incremental":
        mutable_limitations.append(
            ParserDiagnostic(
                code="GERBER_INCREMENTAL_NOTATION",
                level=DiagnosticLevel.LIMITATION,
                message=(
                    "Incremental notation was parsed but is outside BoardGate "
                    "v1 full-coverage scope."
                ),
            )
        )
    if len(witnesses) != len(parsed.objects):
        mutable_limitations.append(
            ParserDiagnostic(
                code="GERBER_PROVENANCE_ALIGNMENT_PARTIAL",
                level=DiagnosticLevel.LIMITATION,
                message=(
                    "Command scanner and parser object counts differ; unmatched "
                    "source spans remain null."
                ),
            )
        )

    primitives: list[GraphicPrimitive] = []
    reported_macros: set[str] = set()
    for index, feature in enumerate(parsed.objects):
        witness = witnesses[index] if index < len(witnesses) else None
        raw_signature = (
            witness.raw_command
            if witness is not None
            else f"{type(feature).__name__}:{index}"
        )
        aperture_object = getattr(feature, "aperture", None)
        normalized_aperture: Aperture | None = None
        if aperture_object is not None:
            try:
                normalized_aperture = _normalize_aperture(aperture_object)
            except ParserError as error:
                mutable_limitations.append(
                    ParserDiagnostic(
                        code=error.code,
                        level=DiagnosticLevel.LIMITATION,
                        message=error.detail,
                    )
                )
                continue
            if normalized_aperture.shape is ApertureShape.MACRO:
                macro_name = normalized_aperture.macro_name or "<unnamed>"
                if macro_name not in reported_macros:
                    reported_macros.add(macro_name)
                    mutable_limitations.append(
                        ParserDiagnostic(
                            code="GERBER_APERTURE_MACRO_LIMITATION",
                            level=DiagnosticLevel.LIMITATION,
                            message=(
                                f"Aperture macro {macro_name!r} is retained by "
                                "bounds but excluded from standard-aperture rules."
                            ),
                        )
                    )
        identifier = object_id(
            type(feature).__name__.casefold(),
            source_file_id,
            index,
            raw_signature,
        )
        provenance = _provenance(
            source_file_id=source_file_id,
            identifier=identifier,
            witness=witness,
            source_unit=source_unit,
            aperture=aperture_object,
        )
        if isinstance(feature, Line) and normalized_aperture is not None:
            primitives.append(
                LinePrimitive(
                    primitive_id=identifier,
                    start=_point(feature.x1, feature.y1, feature.unit),
                    end=_point(feature.x2, feature.y2, feature.unit),
                    aperture=normalized_aperture,
                    polarity=_polarity(feature),
                    provenance=provenance,
                )
            )
        elif isinstance(feature, Arc) and normalized_aperture is not None:
            center_x, center_y = feature.center
            primitives.append(
                ArcPrimitive(
                    primitive_id=identifier,
                    start=_point(feature.x1, feature.y1, feature.unit),
                    end=_point(feature.x2, feature.y2, feature.unit),
                    center=_point(center_x, center_y, feature.unit),
                    clockwise=bool(feature.clockwise),
                    aperture=normalized_aperture,
                    polarity=_polarity(feature),
                    provenance=provenance,
                )
            )
        elif isinstance(feature, Flash) and normalized_aperture is not None:
            primitives.append(
                FlashPrimitive(
                    primitive_id=identifier,
                    position=_point(feature.x, feature.y, feature.unit),
                    aperture=normalized_aperture,
                    polarity=_polarity(feature),
                    provenance=provenance,
                )
            )
        elif isinstance(feature, Region):
            primitives.append(
                RegionPrimitive(
                    primitive_id=identifier,
                    contours=(_region_segments(feature),),
                    polarity=_polarity(feature),
                    provenance=provenance,
                )
            )
        else:
            mutable_limitations.append(
                ParserDiagnostic(
                    code="GERBER_OBJECT_UNSUPPORTED",
                    level=DiagnosticLevel.LIMITATION,
                    message=f"Unsupported parser object {type(feature).__name__}.",
                )
            )
    file_attributes = {
        str(key): tuple(str(item) for item in value)
        for key, value in sorted(parsed.file_attrs.items())
    }
    return GerberParseResult(
        source_file_id=source_file_id,
        original_unit=source_unit,
        notation=getattr(settings, "notation", "absolute"),
        zero_suppression=_zero_suppression(settings),
        coordinate_format=_coordinate_format(settings),
        file_attributes=file_attributes,
        layer_hints=tuple(sorted(set(parsed.layer_hints))),
        primitives=tuple(primitives),
        bounding_box=_bounding_box(parsed),
        warnings=regular_warnings,
        limitations=tuple(mutable_limitations),
        generator_hints=tuple(sorted(set(parsed.generator_hints))),
    )
