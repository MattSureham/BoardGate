"""Evidence-backed finding and measurement models."""

from typing import Literal, Self

from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import FindingStatus, RiskMode, Severity
from boardgate.domain.geometry import BoundingBox, Point, Unit
from boardgate.domain.provenance import Provenance


class Measurement(VersionedModel):
    """A fact measured by deterministic code against a configured requirement."""

    actual: float
    required: float
    operator: Literal[">=", "<=", "=="]
    unit: Unit
    error_bound: float = Field(default=0.0, ge=0.0)
    config_path: str = Field(min_length=1)


class FindingEvidence(VersionedModel):
    """Source and geometric witness for a finding."""

    provenance: Provenance
    layer_id: str | None = Field(default=None, min_length=1)
    witness_bounds: BoundingBox | None = None
    note: str | None = Field(default=None, min_length=1)


class Finding(VersionedModel):
    """Structured review result that keeps facts separate from interpretation."""

    finding_id: str = Field(pattern=r"^fnd-[0-9a-f]{16}$")
    rule_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    category: RiskMode
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    status: FindingStatus = FindingStatus.OPEN
    config_path: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    facts: tuple[str, ...] = Field(min_length=1)
    inference: str | None = Field(default=None, min_length=1)
    location: Point | None = None
    layer_ids: tuple[str, ...] = ()
    measurement: Measurement | None = None
    evidence: tuple[FindingEvidence, ...] = Field(min_length=1)
    suggested_action: str | None = Field(default=None, min_length=1)
    requires_human_confirmation: bool = False
    related_findings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_confirmation_for_uncertain_facts(self) -> Self:
        """Do not present uncertainty categories as unconditional facts."""
        uncertain_categories = {
            RiskMode.DESIGN_INTENT_UNKNOWN,
            RiskMode.LAYER_MAPPING_UNCERTAIN,
            RiskMode.OUTLINE_UNCERTAIN,
            RiskMode.UNIT_AMBIGUITY,
        }
        if (
            self.category in uncertain_categories
            and not self.requires_human_confirmation
        ):
            msg = "uncertain finding categories require human confirmation"
            raise ValueError(msg)
        return self
