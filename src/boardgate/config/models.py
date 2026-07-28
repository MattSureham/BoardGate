"""Strict, versioned manufacturing rule-profile contracts."""

from enum import StrEnum
from hashlib import sha256
from typing import Literal, Self

from pydantic import Field, model_validator

from boardgate.domain.base import StrictModel, VersionedModel
from boardgate.domain.enums import LayerRole
from boardgate.domain.serialization import canonical_json


class RuleId(StrEnum):
    """Rule identifiers supported by the v1 deterministic engine."""

    REQUIRED_LAYERS_PRESENT = "required_layers_present"
    DRILL_FILE_PRESENT = "drill_file_present"
    BOARD_OUTLINE_PRESENT = "board_outline_present"
    BOARD_OUTLINE_CLOSED = "board_outline_closed"
    MULTIPLE_OUTLINE_REGIONS = "multiple_outline_regions"
    GERBER_DRILL_COORDINATE_ALIGNMENT = "gerber_drill_coordinate_alignment"
    MINIMUM_TRACE_WIDTH = "minimum_trace_width"
    MINIMUM_COPPER_SPACING = "minimum_copper_spacing"
    MINIMUM_COPPER_TO_EDGE = "minimum_copper_to_edge"
    MINIMUM_DRILL_DIAMETER = "minimum_drill_diameter"
    MINIMUM_ANNULAR_RING = "minimum_annular_ring"
    SILKSCREEN_OVER_EXPOSED_PAD = "silkscreen_over_exposed_pad"
    MINIMUM_SOLDER_MASK_DAM = "minimum_solder_mask_dam"
    BOM_PLACEMENT_REFERENCE_MATCH = "bom_placement_reference_match"
    DUPLICATE_REFERENCE_DESIGNATOR = "duplicate_reference_designator"
    PLACEMENT_OUTSIDE_BOARD_OUTLINE = "placement_outside_board_outline"


class RuleSeverity(StrEnum):
    """Config-facing severity spellings."""

    BLOCKER = "blocker"
    HIGH = "high"
    WARNING = "warning"
    INFO = "info"


class ProfileMetadata(StrictModel):
    """Human and machine identity for a manufacturing profile."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    name: str = Field(min_length=1, max_length=128)
    manufacturer: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=1)
    description: str = Field(min_length=1, max_length=512)


class FabricationThresholds(StrictModel):
    """All physical requirements, expressed in profile units."""

    min_trace_width: float = Field(gt=0.0)
    min_copper_spacing: float = Field(gt=0.0)
    min_copper_to_edge: float = Field(ge=0.0)
    min_drill_diameter: float = Field(gt=0.0)
    min_annular_ring: float = Field(ge=0.0)
    min_solder_mask_dam: float = Field(ge=0.0)


class GeometryTolerances(StrictModel):
    """Explicit numerical and reconstruction tolerances in millimetres."""

    outline_closure: float = Field(gt=0.0)
    geometry_epsilon: float = Field(gt=0.0)
    gross_alignment: float = Field(gt=0.0)
    arc_chord_error: float = Field(gt=0.0)

    @model_validator(mode="after")
    def validate_relative_tolerances(self) -> Self:
        """Keep approximation error within the general geometry epsilon."""
        if self.arc_chord_error > self.geometry_epsilon:
            msg = "arc_chord_error must not exceed geometry_epsilon"
            raise ValueError(msg)
        return self


class RuleSetting(StrictModel):
    """Execution and readiness behavior for one rule."""

    version: Literal["1.0"]
    enabled: bool
    severity: RuleSeverity
    affects_readiness: bool
    required: bool


class RuleSettings(StrictModel):
    """Complete v1 rule registry with no arbitrary extension keys."""

    required_layers_present: RuleSetting
    drill_file_present: RuleSetting
    board_outline_present: RuleSetting
    board_outline_closed: RuleSetting
    multiple_outline_regions: RuleSetting
    gerber_drill_coordinate_alignment: RuleSetting
    minimum_trace_width: RuleSetting
    minimum_copper_spacing: RuleSetting
    minimum_copper_to_edge: RuleSetting
    minimum_drill_diameter: RuleSetting
    minimum_annular_ring: RuleSetting
    silkscreen_over_exposed_pad: RuleSetting
    minimum_solder_mask_dam: RuleSetting
    bom_placement_reference_match: RuleSetting
    duplicate_reference_designator: RuleSetting
    placement_outside_board_outline: RuleSetting

    def by_id(self, rule_id: RuleId) -> RuleSetting:
        """Return the typed setting for a registered rule."""
        value = getattr(self, rule_id.value)
        if not isinstance(value, RuleSetting):  # pragma: no cover - type invariant
            msg = f"invalid setting registered for {rule_id.value}"
            raise TypeError(msg)
        return value


class ReviewPolicy(StrictModel):
    """Explicit policies for ambiguity and optional assembly inputs."""

    copper_edge_touch: Literal["confirm", "strict"]
    assembly_auto_scope: bool
    ignored_references: tuple[str, ...]
    dnp_markers: tuple[str, ...]

    @model_validator(mode="after")
    def validate_normalized_tokens(self) -> Self:
        """Reject duplicate or blank matching tokens."""
        for label, values in (
            ("ignored_references", self.ignored_references),
            ("dnp_markers", self.dnp_markers),
        ):
            normalized = [value.strip().casefold() for value in values]
            if any(not value for value in normalized):
                msg = f"{label} must not contain blank values"
                raise ValueError(msg)
            if len(normalized) != len(set(normalized)):
                msg = f"{label} must be unique when case-folded"
                raise ValueError(msg)
        return self


class RuleProfile(VersionedModel):
    """Complete, immutable input to deterministic rule evaluation."""

    profile: ProfileMetadata
    units: Literal["mm"]
    required_layers: tuple[LayerRole, ...] = Field(min_length=1)
    fabrication: FabricationThresholds
    tolerances: GeometryTolerances
    policy: ReviewPolicy
    rules: RuleSettings

    @model_validator(mode="after")
    def validate_required_layers(self) -> Self:
        """Required layers must be meaningful and non-duplicated."""
        if LayerRole.UNKNOWN in self.required_layers:
            msg = "required_layers must not contain unknown"
            raise ValueError(msg)
        if len(self.required_layers) != len(set(self.required_layers)):
            msg = "required_layers must be unique"
            raise ValueError(msg)
        return self


def profile_hash(profile: RuleProfile) -> str:
    """Hash the canonical validated profile for stable finding identifiers."""
    return sha256(canonical_json(profile).encode("utf-8")).hexdigest()
