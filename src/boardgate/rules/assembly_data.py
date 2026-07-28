"""Shared assembly-dataset availability facts for rules and readiness."""

from __future__ import annotations

from dataclasses import dataclass

from boardgate.domain.diagnostic import SourceDiagnosticLevel
from boardgate.domain.enums import FileType
from boardgate.domain.project import PCBProject
from boardgate.domain.source import SourceFile

_BOM_TYPES = frozenset({FileType.BOM_CSV, FileType.BOM_XLSX})
_PLACEMENT_TYPES = frozenset({FileType.PLACEMENT_CSV})


@dataclass(frozen=True, slots=True)
class AssemblyDataInventory:
    """Usable, failed, and unresolved assembly inputs."""

    bom_sources: tuple[SourceFile, ...]
    placement_sources: tuple[SourceFile, ...]
    failed_source_ids: frozenset[str]
    bom_usable: bool
    placement_usable: bool

    def candidate_sources(
        self,
        project: PCBProject,
        *,
        file_types: frozenset[FileType],
    ) -> tuple[SourceFile, ...]:
        """Return unknown sources explicitly classified as a wanted candidate."""
        return tuple(
            source
            for source in project.source_files
            if source.file_type is FileType.UNKNOWN
            and any(
                candidate.file_type in file_types for candidate in source.candidates
            )
        )


def assembly_data_inventory(project: PCBProject) -> AssemblyDataInventory:
    """Derive assembly availability without treating failed parses as usable."""
    failed_source_ids = frozenset(
        diagnostic.source_file_id
        for diagnostic in project.source_diagnostics
        if diagnostic.level is SourceDiagnosticLevel.ERROR
    )
    bom_sources = tuple(
        source for source in project.source_files if source.file_type in _BOM_TYPES
    )
    placement_sources = tuple(
        source
        for source in project.source_files
        if source.file_type in _PLACEMENT_TYPES
    )
    return AssemblyDataInventory(
        bom_sources=bom_sources,
        placement_sources=placement_sources,
        failed_source_ids=failed_source_ids,
        bom_usable=bool(project.bom_items)
        or any(
            source.source_file_id not in failed_source_ids for source in bom_sources
        ),
        placement_usable=bool(project.components)
        or any(
            source.source_file_id not in failed_source_ids
            for source in placement_sources
        ),
    )


def bom_file_types() -> frozenset[FileType]:
    """Return the immutable file-type set accepted as BOM input."""
    return _BOM_TYPES


def placement_file_types() -> frozenset[FileType]:
    """Return the immutable file-type set accepted as placement input."""
    return _PLACEMENT_TYPES
