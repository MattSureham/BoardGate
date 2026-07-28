"""Drill feature domain models."""

from typing import Literal, Self

from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import Plating
from boardgate.domain.geometry import Point
from boardgate.domain.provenance import Provenance


class DrillHit(VersionedModel):
    """One round Excellon drill hit."""

    drill_id: str = Field(min_length=1)
    position: Point
    diameter_mm: float = Field(gt=0.0)
    tool_code: str | None = Field(default=None, min_length=1)
    plating: Plating = Plating.UNKNOWN
    provenance: Provenance


class DrillSlot(VersionedModel):
    """One routed drill slot retained for explicit partial coverage."""

    kind: Literal["line", "arc"] = "line"
    slot_id: str = Field(min_length=1)
    start: Point
    end: Point
    center: Point | None = None
    clockwise: bool | None = None
    width_mm: float = Field(gt=0.0)
    tool_code: str | None = Field(default=None, min_length=1)
    plating: Plating = Plating.UNKNOWN
    provenance: Provenance

    @model_validator(mode="after")
    def validate_slot_shape(self) -> Self:
        """Require analytic arc metadata only for arc-routed slots."""
        if self.kind == "arc":
            if self.center is None or self.clockwise is None:
                msg = "arc slots require center and clockwise"
                raise ValueError(msg)
        elif self.center is not None or self.clockwise is not None:
            msg = "line slots must not contain arc metadata"
            raise ValueError(msg)
        return self
