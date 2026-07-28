"""Canonical millimetre geometry and coordinate-system models."""

from enum import StrEnum
from typing import Self

from pydantic import field_serializer, model_validator

from boardgate.domain.base import VersionedModel

SERIALIZED_DECIMAL_PLACES = 6


class Unit(StrEnum):
    """Supported source length units."""

    MILLIMETRE = "mm"
    INCH = "inch"


class AxisDirection(StrEnum):
    """Axis directions used by an explicit coordinate system."""

    RIGHT = "right"
    LEFT = "left"
    UP = "up"
    DOWN = "down"


class Point(VersionedModel):
    """A point in BoardGate's canonical millimetre coordinate space."""

    x: float
    y: float
    unit: Unit = Unit.MILLIMETRE

    @model_validator(mode="after")
    def require_millimetres(self) -> Self:
        """Reject non-normalized points at the domain boundary."""
        if self.unit is not Unit.MILLIMETRE:
            msg = "domain points must be normalized to millimetres"
            raise ValueError(msg)
        return self

    @field_serializer("x", "y")
    def serialize_coordinate(self, value: float) -> float:
        """Make persisted coordinates stable without changing calculations."""
        return round(value, SERIALIZED_DECIMAL_PLACES)


class BoundingBox(VersionedModel):
    """Axis-aligned bounding box in canonical coordinates."""

    minimum: Point
    maximum: Point

    @model_validator(mode="after")
    def validate_extent(self) -> Self:
        """Require ordered bounds."""
        if self.minimum.x > self.maximum.x or self.minimum.y > self.maximum.y:
            msg = "bounding-box minimum must not exceed maximum"
            raise ValueError(msg)
        return self

    @property
    def width(self) -> float:
        """Return the X extent in millimetres."""
        return self.maximum.x - self.minimum.x

    @property
    def height(self) -> float:
        """Return the Y extent in millimetres."""
        return self.maximum.y - self.minimum.y


class CoordinateSystem(VersionedModel):
    """Explicit canonical coordinate-system description."""

    unit: Unit = Unit.MILLIMETRE
    origin: Point = Point(x=0.0, y=0.0)
    x_axis: AxisDirection = AxisDirection.RIGHT
    y_axis: AxisDirection = AxisDirection.UP
    rotation_degrees: float = 0.0

    @model_validator(mode="after")
    def require_canonical_axes(self) -> Self:
        """Ensure normalized projects use the canonical orientation."""
        if self.unit is not Unit.MILLIMETRE:
            msg = "domain coordinate systems must use millimetres"
            raise ValueError(msg)
        if self.x_axis is not AxisDirection.RIGHT:
            msg = "domain X axis must point right"
            raise ValueError(msg)
        if self.y_axis is not AxisDirection.UP:
            msg = "domain Y axis must point up"
            raise ValueError(msg)
        if self.rotation_degrees != 0.0:
            msg = "domain coordinates must have zero residual rotation"
            raise ValueError(msg)
        return self
