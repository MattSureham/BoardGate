"""Parser-independent layer and graphical primitive models."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import (
    ApertureShape,
    BoardSide,
    LayerRole,
    Polarity,
)
from boardgate.domain.geometry import BoundingBox, Point
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import Uncertainty


class Aperture(VersionedModel):
    """Normalized aperture dimensions."""

    shape: ApertureShape
    width_mm: float = Field(gt=0.0)
    height_mm: float | None = Field(default=None, gt=0.0)
    hole_diameter_mm: float | None = Field(default=None, ge=0.0)
    rotation_degrees: float = 0.0
    vertices: int | None = Field(default=None, ge=3)
    macro_name: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_shape_fields(self) -> Self:
        """Require enough dimensions without inventing macro geometry."""
        if (
            self.shape is ApertureShape.CIRCLE
            and self.height_mm is not None
            and self.height_mm != self.width_mm
        ):
            msg = "circle aperture height must equal width when provided"
            raise ValueError(msg)
        if self.shape is ApertureShape.MACRO and self.macro_name is None:
            msg = "macro aperture requires macro_name"
            raise ValueError(msg)
        if self.shape is ApertureShape.POLYGON and self.vertices is None:
            msg = "polygon aperture requires vertices"
            raise ValueError(msg)
        if self.shape is not ApertureShape.POLYGON and self.vertices is not None:
            msg = "vertices are only valid for polygon apertures"
            raise ValueError(msg)
        return self


class LinePrimitive(VersionedModel):
    """A linear Gerber draw."""

    kind: Literal["line"] = "line"
    primitive_id: str = Field(min_length=1)
    start: Point
    end: Point
    aperture: Aperture
    polarity: Polarity
    provenance: Provenance


class ArcPrimitive(VersionedModel):
    """An analytic circular Gerber draw."""

    kind: Literal["arc"] = "arc"
    primitive_id: str = Field(min_length=1)
    start: Point
    end: Point
    center: Point
    clockwise: bool
    aperture: Aperture
    polarity: Polarity
    provenance: Provenance


class FlashPrimitive(VersionedModel):
    """A Gerber aperture flash."""

    kind: Literal["flash"] = "flash"
    primitive_id: str = Field(min_length=1)
    position: Point
    aperture: Aperture
    polarity: Polarity
    provenance: Provenance


class RegionLineSegment(VersionedModel):
    """One analytic straight segment in a Gerber region contour."""

    kind: Literal["line"] = "line"
    start: Point
    end: Point


class RegionArcSegment(VersionedModel):
    """One analytic circular segment in a Gerber region contour."""

    kind: Literal["arc"] = "arc"
    start: Point
    end: Point
    center: Point
    clockwise: bool


type RegionSegment = Annotated[
    RegionLineSegment | RegionArcSegment,
    Field(discriminator="kind"),
]


class RegionPrimitive(VersionedModel):
    """A normalized analytic Gerber region."""

    kind: Literal["region"] = "region"
    primitive_id: str = Field(min_length=1)
    contours: tuple[tuple[RegionSegment, ...], ...] = Field(min_length=1)
    polarity: Polarity
    provenance: Provenance

    @model_validator(mode="after")
    def require_closed_contours(self) -> Self:
        """Require connected, closed analytic contours."""
        for contour in self.contours:
            if not contour:
                msg = "region contours require at least one segment"
                raise ValueError(msg)
            for current, following in zip(
                contour,
                (*contour[1:], contour[0]),
                strict=True,
            ):
                if current.end != following.start:
                    msg = "region contour segments must be connected and closed"
                    raise ValueError(msg)
        return self


type GraphicPrimitive = Annotated[
    LinePrimitive | ArcPrimitive | FlashPrimitive | RegionPrimitive,
    Field(discriminator="kind"),
]


class LayerMappingCandidate(VersionedModel):
    """One evidence-backed interpretation of a source layer."""

    role: LayerRole
    side: BoardSide
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[str, ...] = ()


class PCBLayer(VersionedModel):
    """Normalized graphical content for one physical/logical layer."""

    layer_id: str = Field(min_length=1)
    source_file_id: str = Field(pattern=r"^src-[0-9a-f]{16}$")
    role: LayerRole
    side: BoardSide
    mapping_confidence: float = Field(ge=0.0, le=1.0)
    mapping_candidates: tuple[LayerMappingCandidate, ...] = ()
    coordinate_evidence: tuple[str, ...] = ()
    primitives: tuple[GraphicPrimitive, ...] = ()
    bounding_box: BoundingBox | None = None
    uncertainties: tuple[Uncertainty, ...] = ()

    @model_validator(mode="after")
    def require_unique_primitive_ids(self) -> Self:
        """Keep primitive evidence addresses unambiguous."""
        primitive_ids = [primitive.primitive_id for primitive in self.primitives]
        if len(primitive_ids) != len(set(primitive_ids)):
            msg = "primitive_id values must be unique within a layer"
            raise ValueError(msg)
        return self


class OutlineContour(VersionedModel):
    """One reconstructed board outline contour."""

    contour_id: str = Field(min_length=1)
    points: tuple[Point, ...] = Field(min_length=2)
    closed: bool
    source_primitive_ids: tuple[str, ...] = ()


class BoardOutline(VersionedModel):
    """Reconstructed board material boundary."""

    contours: tuple[OutlineContour, ...] = Field(min_length=1)
    bounding_box: BoundingBox
    provenance: tuple[Provenance, ...]
