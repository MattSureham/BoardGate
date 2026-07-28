"""BOM and component-placement domain models."""

from pydantic import Field

from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import BoardSide
from boardgate.domain.geometry import Point
from boardgate.domain.provenance import JsonScalar, Provenance


class BOMItem(VersionedModel):
    """Normalized bill-of-materials row."""

    references: tuple[str, ...] = Field(min_length=1)
    quantity: int = Field(ge=1)
    part_number: str | None = Field(default=None, min_length=1)
    value: str | None = Field(default=None, min_length=1)
    footprint: str | None = Field(default=None, min_length=1)
    dnp: bool = False
    provenance: Provenance
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)


class ComponentPlacement(VersionedModel):
    """Normalized pick-and-place record."""

    reference: str = Field(min_length=1)
    position: Point
    rotation_degrees: float
    side: BoardSide
    value: str | None = Field(default=None, min_length=1)
    footprint: str | None = Field(default=None, min_length=1)
    provenance: Provenance
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)
