"""Unified, parser-independent PCB project representation."""

from typing import Self

from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.component import BOMItem, ComponentPlacement
from boardgate.domain.drill import DrillHit, DrillSlot
from boardgate.domain.geometry import CoordinateSystem
from boardgate.domain.layer import BoardOutline, PCBLayer
from boardgate.domain.provenance import JsonScalar
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty


class FabricationRequirements(VersionedModel):
    """Manufacturing thresholds copied from the selected rule profile."""

    profile_id: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    min_trace_width_mm: float | None = Field(default=None, gt=0.0)
    min_copper_spacing_mm: float | None = Field(default=None, gt=0.0)
    min_copper_to_edge_mm: float | None = Field(default=None, ge=0.0)
    min_drill_diameter_mm: float | None = Field(default=None, gt=0.0)
    min_annular_ring_mm: float | None = Field(default=None, ge=0.0)
    min_solder_mask_dam_mm: float | None = Field(default=None, ge=0.0)


class AssemblyRequirements(VersionedModel):
    """Assembly-review scope copied from the selected profile."""

    review_requested: bool
    ignored_references: tuple[str, ...] = ()
    dnp_markers: tuple[str, ...] = ()


class PCBProject(VersionedModel):
    """Complete normalized project consumed by deterministic rules."""

    project_id: str = Field(pattern=r"^prj-[0-9a-f]{16}$")
    source_files: tuple[SourceFile, ...]
    manifest: ProjectManifest
    coordinate_system: CoordinateSystem
    layers: tuple[PCBLayer, ...] = ()
    board_outline: BoardOutline | None = None
    drills: tuple[DrillHit, ...] = ()
    drill_slots: tuple[DrillSlot, ...] = ()
    components: tuple[ComponentPlacement, ...] = ()
    bom_items: tuple[BOMItem, ...] = ()
    fabrication_requirements: FabricationRequirements
    assembly_requirements: AssemblyRequirements
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)
    uncertainties: tuple[Uncertainty, ...] = ()

    @model_validator(mode="after")
    def validate_project_references(self) -> Self:
        """Keep all project identifiers internally consistent and unique."""
        if self.manifest.project_id != self.project_id:
            msg = "project_id must match manifest.project_id"
            raise ValueError(msg)
        source_ids = [source.source_file_id for source in self.source_files]
        manifest_ids = [source.source_file_id for source in self.manifest.source_files]
        if source_ids != manifest_ids:
            msg = "source_files must match manifest source order and identifiers"
            raise ValueError(msg)
        collections = {
            "layer_id": [layer.layer_id for layer in self.layers],
            "drill_id": [drill.drill_id for drill in self.drills],
            "slot_id": [slot.slot_id for slot in self.drill_slots],
        }
        for label, values in collections.items():
            if len(values) != len(set(values)):
                msg = f"{label} values must be unique"
                raise ValueError(msg)
        return self
