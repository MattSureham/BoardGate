"""Deterministic assembly of parser results into the PCBProject IR."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import sha256

from boardgate import __version__
from boardgate.application.parser_runner import (
    ParsedResult,
    ParserExecution,
    ParserJob,
    run_parser,
)
from boardgate.config.models import RuleProfile, profile_hash
from boardgate.domain.component import BOMItem, ComponentPlacement
from boardgate.domain.diagnostic import SourceDiagnostic, SourceDiagnosticLevel
from boardgate.domain.drill import DrillHit, DrillSlot
from boardgate.domain.enums import FileType, RiskMode
from boardgate.domain.geometry import CoordinateSystem
from boardgate.domain.identifiers import object_id
from boardgate.domain.layer import PCBLayer
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty
from boardgate.ingestion.discovery import DiscoveredProject
from boardgate.normalization import (
    normalize_gerber_layer,
    reconstruct_board_outline,
)
from boardgate.parsers import (
    BOMParseResult,
    ExcellonParseResult,
    GerberParseResult,
    PlacementParseResult,
)
from boardgate.parsers.models import DiagnosticLevel, ParserDiagnostic

_PARSABLE_TYPES = frozenset(
    {
        FileType.GERBER,
        FileType.EXCELLON,
        FileType.BOM_CSV,
        FileType.BOM_XLSX,
        FileType.PLACEMENT_CSV,
    }
)

type ParserExecutor = Callable[..., ParserExecution]


class ProjectBuildError(ValueError):
    """A source-safe project assembly invariant failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


def _payload(
    source: SourceFile,
    discovered: DiscoveredProject,
) -> bytes:
    by_path = {item.logical_path: item for item in discovered.files}
    item = by_path.get(source.logical_path)
    if item is None:
        raise ProjectBuildError(
            "PROJECT_SOURCE_MISSING",
            source.logical_path,
            "manifest source is absent from the staged project",
        )
    try:
        payload = item.staged_path.read_bytes()
    except OSError as error:
        raise ProjectBuildError(
            "PROJECT_SOURCE_READ_ERROR",
            source.logical_path,
            "staged source could not be read",
        ) from error
    if (
        len(payload) != source.size_bytes
        or sha256(payload).hexdigest() != source.sha256
    ):
        raise ProjectBuildError(
            "PROJECT_SOURCE_CHANGED",
            source.logical_path,
            "staged source no longer matches its manifest digest",
        )
    return payload


def _source_diagnostic(
    source: SourceFile,
    diagnostic: ParserDiagnostic,
    *,
    index: int,
) -> SourceDiagnostic:
    level = (
        SourceDiagnosticLevel.WARNING
        if diagnostic.level is DiagnosticLevel.WARNING
        else SourceDiagnosticLevel.LIMITATION
    )
    identifier = object_id(
        "diagnostic",
        source.source_file_id,
        index,
        f"{diagnostic.code}:{diagnostic.message}",
    )
    return SourceDiagnostic(
        diagnostic_id=identifier,
        source_file_id=source.source_file_id,
        code=diagnostic.code,
        level=level,
        message=diagnostic.message,
        source_span=diagnostic.source_span,
    )


def _failure_diagnostic(
    source: SourceFile,
    execution: ParserExecution,
) -> SourceDiagnostic:
    failure = execution.failure
    if failure is None:  # pragma: no cover - execution invariant
        raise ValueError("failed parser execution omitted its failure")
    return SourceDiagnostic(
        diagnostic_id=object_id(
            "diagnostic",
            source.source_file_id,
            0,
            f"{failure.code}:{failure.detail}",
        ),
        source_file_id=source.source_file_id,
        code=failure.code,
        level=SourceDiagnosticLevel.ERROR,
        message=failure.detail,
    )


def _diagnostic_uncertainty(
    source: SourceFile,
    diagnostic: SourceDiagnostic,
) -> Uncertainty:
    return Uncertainty(
        risk_mode=RiskMode.PARSER_LIMITATION,
        subject=f"{source.logical_path}:{diagnostic.code}",
        summary=diagnostic.message,
        candidates=(diagnostic.code,),
        evidence=(
            Provenance(
                source_file_id=source.source_file_id,
                object_id=diagnostic.diagnostic_id,
                parser="boardgate-parser-runner",
                parser_version=__version__,
                source_span=diagnostic.source_span,
                metadata={"logical_path": source.logical_path},
            ),
        ),
    )


def _result_diagnostics(
    source: SourceFile,
    result: ParsedResult,
) -> tuple[tuple[SourceDiagnostic, ...], tuple[Uncertainty, ...]]:
    raw_diagnostics: tuple[ParserDiagnostic, ...] = ()
    if isinstance(result, GerberParseResult | ExcellonParseResult):
        raw_diagnostics = (*result.warnings, *result.limitations)
    diagnostics = tuple(
        _source_diagnostic(source, diagnostic, index=index)
        for index, diagnostic in enumerate(raw_diagnostics)
    )
    uncertainties = tuple(
        _diagnostic_uncertainty(source, diagnostic)
        for diagnostic in diagnostics
        if diagnostic.level is SourceDiagnosticLevel.LIMITATION
    )
    return diagnostics, uncertainties


def _requirements(
    profile: RuleProfile,
    *,
    assembly_present: bool,
) -> tuple[FabricationRequirements, AssemblyRequirements]:
    fabrication = profile.fabrication
    return (
        FabricationRequirements(
            profile_id=profile.profile.id,
            profile_sha256=profile_hash(profile),
            min_trace_width_mm=fabrication.min_trace_width,
            min_copper_spacing_mm=fabrication.min_copper_spacing,
            min_copper_to_edge_mm=fabrication.min_copper_to_edge,
            min_drill_diameter_mm=fabrication.min_drill_diameter,
            min_annular_ring_mm=fabrication.min_annular_ring,
            min_solder_mask_dam_mm=fabrication.min_solder_mask_dam,
        ),
        AssemblyRequirements(
            review_requested=(profile.policy.assembly_auto_scope and assembly_present),
            ignored_references=profile.policy.ignored_references,
            dnp_markers=profile.policy.dnp_markers,
        ),
    )


def _validate_source_inventory(
    discovered: DiscoveredProject,
    manifest: ProjectManifest,
) -> None:
    discovered_paths = tuple(item.logical_path for item in discovered.files)
    manifest_paths = tuple(source.logical_path for source in manifest.source_files)
    if discovered_paths != manifest_paths:
        raise ProjectBuildError(
            "PROJECT_INVENTORY_MISMATCH",
            manifest.project_id,
            "staged source order does not match the manifest",
        )


def build_project(
    discovered: DiscoveredProject,
    manifest: ProjectManifest,
    profile: RuleProfile,
    *,
    parser_timeout_seconds: float = 30.0,
    parser_executor: ParserExecutor = run_parser,
) -> PCBProject:
    """Parse and normalize every confirmed source in stable manifest order."""
    _validate_source_inventory(discovered, manifest)
    layers: list[PCBLayer] = []
    drills: list[DrillHit] = []
    slots: list[DrillSlot] = []
    components: list[ComponentPlacement] = []
    bom_items: list[BOMItem] = []
    diagnostics: list[SourceDiagnostic] = []
    uncertainties = list(manifest.uncertainties)
    assembly_present = False

    for source in manifest.source_files:
        if source.file_type not in _PARSABLE_TYPES:
            continue
        if source.file_type in {
            FileType.BOM_CSV,
            FileType.BOM_XLSX,
            FileType.PLACEMENT_CSV,
        }:
            assembly_present = True
        execution = parser_executor(
            ParserJob(
                source_file_id=source.source_file_id,
                logical_path=source.logical_path,
                file_type=source.file_type,
                payload=_payload(source, discovered),
            ),
            timeout_seconds=parser_timeout_seconds,
        )
        if execution.failure is not None:
            diagnostic = _failure_diagnostic(source, execution)
            diagnostics.append(diagnostic)
            uncertainties.append(_diagnostic_uncertainty(source, diagnostic))
            continue
        result = execution.result
        if result is None:  # pragma: no cover - execution invariant
            raise ValueError("successful parser execution omitted its result")
        result_diagnostics, result_uncertainties = _result_diagnostics(source, result)
        diagnostics.extend(result_diagnostics)
        uncertainties.extend(result_uncertainties)
        if isinstance(result, GerberParseResult):
            layer = normalize_gerber_layer(source, result)
            layers.append(layer)
            uncertainties.extend(layer.uncertainties)
        elif isinstance(result, ExcellonParseResult):
            drills.extend(result.drills)
            slots.extend(result.slots)
        elif isinstance(result, PlacementParseResult):
            components.extend(result.placements)
        elif isinstance(result, BOMParseResult):
            bom_items.extend(result.items)

    outline_result = reconstruct_board_outline(
        tuple(layers),
        closure_tolerance_mm=profile.tolerances.outline_closure,
        arc_chord_error_mm=profile.tolerances.arc_chord_error,
        geometry_epsilon_mm=profile.tolerances.geometry_epsilon,
    )
    uncertainties.extend(outline_result.uncertainties)
    fabrication_requirements, assembly_requirements = _requirements(
        profile,
        assembly_present=assembly_present,
    )
    return PCBProject(
        project_id=manifest.project_id,
        source_files=manifest.source_files,
        manifest=manifest,
        coordinate_system=CoordinateSystem(),
        layers=tuple(layers),
        board_outline=outline_result.outline,
        drills=tuple(drills),
        drill_slots=tuple(slots),
        components=tuple(components),
        bom_items=tuple(bom_items),
        source_diagnostics=tuple(diagnostics),
        fabrication_requirements=fabrication_requirements,
        assembly_requirements=assembly_requirements,
        metadata={"implementation_version": __version__},
        uncertainties=tuple(uncertainties),
    )
