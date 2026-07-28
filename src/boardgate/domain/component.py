"""BOM and component-placement domain models."""

from typing import Self

from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import BoardSide
from boardgate.domain.geometry import Point
from boardgate.domain.provenance import JsonScalar, Provenance


class BOMItem(VersionedModel):
    """Normalized bill-of-materials row."""

    references: tuple[str, ...] = Field(min_length=1)
    quantity: int = Field(ge=0)
    part_number: str | None = Field(default=None, min_length=1)
    value: str | None = Field(default=None, min_length=1)
    footprint: str | None = Field(default=None, min_length=1)
    dnp: bool = False
    provenance: Provenance
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_zero_quantity(self) -> Self:
        """A zero-quantity BOM row must explicitly be DNP."""
        if self.quantity == 0 and not self.dnp:
            msg = "zero-quantity BOM items must be marked DNP"
            raise ValueError(msg)
        return self


class ComponentPlacement(VersionedModel):
    """Normalized pick-and-place record."""

    reference: str = Field(min_length=1)
    position: Point
    rotation_degrees: float
    side: BoardSide
    value: str | None = Field(default=None, min_length=1)
    footprint: str | None = Field(default=None, min_length=1)
    dnp: bool = False
    provenance: Provenance
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)
