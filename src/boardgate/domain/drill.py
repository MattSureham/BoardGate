"""Drill feature domain models."""

from pydantic import Field

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

    slot_id: str = Field(min_length=1)
    start: Point
    end: Point
    width_mm: float = Field(gt=0.0)
    tool_code: str | None = Field(default=None, min_length=1)
    plating: Plating = Plating.UNKNOWN
    provenance: Provenance
