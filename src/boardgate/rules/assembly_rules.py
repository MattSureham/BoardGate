"""Deterministic cross-file assembly data rules."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from shapely.geometry import Point as ShapelyPoint

from boardgate import __version__
from boardgate.config.models import RuleId
from boardgate.domain.component import BOMItem, ComponentPlacement
from boardgate.domain.diagnostic import SourceDiagnosticLevel
from boardgate.domain.enums import RiskMode
from boardgate.domain.finding import Finding, FindingEvidence, Measurement
from boardgate.domain.geometry import Unit
from boardgate.domain.provenance import JsonScalar, Provenance
from boardgate.domain.source import SourceFile
from boardgate.rules.assembly_data import (
    assembly_data_inventory,
    bom_file_types,
    placement_file_types,
)
from boardgate.rules.common import (
    evidence_identifier,
    make_finding,
    project_uncertainty_evidence,
)
from boardgate.rules.derived_geometry import board_material_geometry
from boardgate.rules.engine import RuleContext
from boardgate.rules.models import (
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
)


def _reference(value: str) -> str:
    return value.strip().casefold()


def _marker_values(
    *,
    value: str | None,
    footprint: str | None,
    metadata: dict[str, JsonScalar],
) -> tuple[str, ...]:
    return tuple(
        item.strip().casefold()
        for item in (value, footprint, *metadata.values())
        if isinstance(item, str) and item.strip()
    )


def _is_bom_dnp(item: BOMItem, markers: frozenset[str]) -> bool:
    return item.dnp or any(
        value in markers
        for value in _marker_values(
            value=item.value,
            footprint=item.footprint,
            metadata=item.metadata,
        )
    )


def _is_placement_dnp(
    placement: ComponentPlacement,
    markers: frozenset[str],
) -> bool:
    return placement.dnp or any(
        value in markers
        for value in _marker_values(
            value=placement.value,
            footprint=placement.footprint,
            metadata=placement.metadata,
        )
    )


def _bom_references(
    context: RuleContext,
) -> dict[str, tuple[BOMItem, ...]]:
    ignored = {_reference(value) for value in context.profile.policy.ignored_references}
    markers = frozenset(
        value.strip().casefold() for value in context.profile.policy.dnp_markers
    )
    grouped: dict[str, list[BOMItem]] = {}
    for item in context.project.bom_items:
        if _is_bom_dnp(item, markers):
            continue
        for raw_reference in item.references:
            reference = _reference(raw_reference)
            if reference in ignored:
                continue
            grouped.setdefault(reference, []).append(item)
    return {reference: tuple(items) for reference, items in grouped.items()}


def _placement_references(
    context: RuleContext,
) -> dict[str, tuple[ComponentPlacement, ...]]:
    grouped: dict[str, list[ComponentPlacement]] = {}
    for placement in _active_placements(context):
        reference = _reference(placement.reference)
        grouped.setdefault(reference, []).append(placement)
    return {reference: tuple(placements) for reference, placements in grouped.items()}


def _active_placements(context: RuleContext) -> tuple[ComponentPlacement, ...]:
    ignored = {_reference(value) for value in context.profile.policy.ignored_references}
    markers = frozenset(
        value.strip().casefold() for value in context.profile.policy.dnp_markers
    )
    return tuple(
        placement
        for placement in context.project.components
        if not _is_placement_dnp(placement, markers)
        and _reference(placement.reference) not in ignored
    )


def _source_evidence(source: SourceFile) -> FindingEvidence:
    return FindingEvidence(
        provenance=Provenance(
            source_file_id=source.source_file_id,
            object_id=source.source_file_id,
            parser="boardgate-manifest",
            parser_version=__version__,
            metadata={
                "logical_path": source.logical_path,
                "classified_type": source.file_type.value,
            },
        ),
        note="Classified project inventory used for assembly-data evaluation.",
    )


def _record_evidence(
    records: Iterable[BOMItem | ComponentPlacement],
    *,
    note: str,
) -> tuple[FindingEvidence, ...]:
    return _unique_evidence(
        FindingEvidence(provenance=record.provenance, note=note) for record in records
    )


def _unique_evidence(
    evidence: Iterable[FindingEvidence],
) -> tuple[FindingEvidence, ...]:
    by_identifier: dict[str, FindingEvidence] = {}
    for item in evidence:
        by_identifier.setdefault(evidence_identifier(item), item)
    return tuple(by_identifier[key] for key in sorted(by_identifier))


def _failed_source_evidence(
    context: RuleContext,
    *,
    source_ids: frozenset[str],
) -> tuple[FindingEvidence, ...]:
    return tuple(
        FindingEvidence(
            provenance=Provenance(
                source_file_id=diagnostic.source_file_id,
                object_id=diagnostic.diagnostic_id,
                parser="boardgate-parser-runner",
                parser_version=__version__,
                source_span=diagnostic.source_span,
                metadata={"diagnostic_code": diagnostic.code},
            ),
            note="A confirmed assembly source did not complete parsing.",
        )
        for diagnostic in context.project.source_diagnostics
        if diagnostic.source_file_id in source_ids
        and diagnostic.level is SourceDiagnosticLevel.ERROR
    )


def _unavailable_dataset_finding(
    context: RuleContext,
    *,
    unavailable: tuple[str, ...],
    evidence: tuple[FindingEvidence, ...],
    category: RiskMode,
    requires_confirmation: bool,
) -> Finding:
    display = " and ".join(unavailable)
    return make_finding(
        context,
        rule_id=RuleId.BOM_PLACEMENT_REFERENCE_MATCH,
        category=category,
        config_path="rules.bom_placement_reference_match",
        title=(
            "Assembly dataset availability requires confirmation"
            if requires_confirmation
            else f"{display} dataset is missing"
        ),
        summary=(
            "Assembly review is active, but a usable "
            f"{display} dataset is not available for comparison."
        ),
        facts=(
            f"Unavailable datasets: {', '.join(unavailable)}.",
            "Both a usable BOM and placement dataset are required for comparison.",
        ),
        evidence=evidence,
        confidence=(0.5 if requires_confirmation else 1.0),
        suggested_action=(
            f"Export or correct the {display} dataset, then rerun the review."
        ),
        requires_human_confirmation=requires_confirmation,
    )


@dataclass(frozen=True, slots=True)
class BOMPlacementReferenceMatchRule:
    """Compare normalized, populated BOM and placement reference sets."""

    rule_id: RuleId = RuleId.BOM_PLACEMENT_REFERENCE_MATCH
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = ()

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Report missing datasets and directional set differences."""
        if not context.project.assembly_requirements.review_requested:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary="Assembly review scope is not active.",
            )
        project = context.project
        inventory = assembly_data_inventory(project)
        uncertainty_by_source = project_uncertainty_evidence(context)
        inventory_evidence = tuple(
            _source_evidence(source) for source in project.source_files
        )
        if not inventory.bom_usable or not inventory.placement_usable:
            unavailable = (
                *(() if inventory.bom_usable else ("BOM",)),
                *(() if inventory.placement_usable else ("placement",)),
            )
            unavailable_types = (
                frozenset() if inventory.bom_usable else bom_file_types()
            ) | (frozenset() if inventory.placement_usable else placement_file_types())
            candidate_sources = inventory.candidate_sources(
                project,
                file_types=unavailable_types,
            )
            failed_source_ids = frozenset(
                source.source_file_id
                for source in (
                    *(() if inventory.bom_usable else inventory.bom_sources),
                    *(
                        ()
                        if inventory.placement_usable
                        else inventory.placement_sources
                    ),
                )
                if source.source_file_id in inventory.failed_source_ids
            )
            failed_evidence = _failed_source_evidence(
                context,
                source_ids=failed_source_ids,
            )
            evidence = _unique_evidence(
                (
                    *_record_evidence(
                        (*project.bom_items, *project.components),
                        note="Parsed record from an available assembly dataset.",
                    ),
                    *inventory_evidence,
                    *failed_evidence,
                )
            )
            if not evidence:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.INPUT_UNCERTAIN,
                    summary=(
                        "Assembly scope is active, but no source inventory is "
                        "available to establish dataset availability."
                    ),
                )
            requires_confirmation = bool(failed_evidence or candidate_sources)
            category = (
                RiskMode.PARSER_LIMITATION
                if failed_evidence
                else (
                    RiskMode.FILE_TYPE_UNKNOWN
                    if candidate_sources
                    else RiskMode.FILE_INCOMPLETE
                )
            )
            return RuleEvaluation(
                outcome=RuleOutcome.FINDINGS,
                coverage=(
                    RuleCoverage.PARTIAL if requires_confirmation else RuleCoverage.FULL
                ),
                findings=(
                    _unavailable_dataset_finding(
                        context,
                        unavailable=unavailable,
                        evidence=evidence,
                        category=category,
                        requires_confirmation=requires_confirmation,
                    ),
                ),
                summary=("One or more required assembly datasets are unavailable."),
                evaluated_object_count=(
                    0 if requires_confirmation else len(unavailable)
                ),
                applicable_object_count=len(unavailable),
            )

        bom = _bom_references(context)
        placement = _placement_references(context)
        assembly_sources = (
            *inventory.bom_sources,
            *inventory.placement_sources,
        )
        all_assembly_source_ids = {source.source_file_id for source in assembly_sources}
        source_uncertainty = tuple(
            provenance
            for source_id in sorted(all_assembly_source_ids)
            for provenance in uncertainty_by_source.get(source_id, ())
        )
        confirmation = bool(source_uncertainty)
        bom_only = tuple(sorted(bom.keys() - placement.keys()))
        placement_only = tuple(sorted(placement.keys() - bom.keys()))
        applicable_count = len(set(bom) | set(placement))
        if not bom_only and not placement_only:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=(RuleCoverage.PARTIAL if confirmation else RuleCoverage.FULL),
                summary=(
                    "Populated BOM and placement references match, but source "
                    "uncertainty prevents a complete pass claim."
                    if confirmation
                    else (
                        "Populated BOM and placement reference sets match after "
                        "symmetric DNP and ignore filtering."
                    )
                ),
                evaluated_object_count=applicable_count,
                applicable_object_count=applicable_count,
            )

        mismatched_records: tuple[BOMItem | ComponentPlacement, ...] = (
            *(record for reference in bom_only for record in bom[reference]),
            *(
                record
                for reference in placement_only
                for record in placement[reference]
            ),
        )
        comparison_evidence = _unique_evidence(
            (
                *_record_evidence(
                    mismatched_records,
                    note="Row-level evidence for a directional reference mismatch.",
                ),
                *(_source_evidence(source) for source in assembly_sources),
                *(
                    FindingEvidence(
                        provenance=provenance,
                        note=(
                            "Project uncertainty witness affecting an assembly source."
                        ),
                    )
                    for provenance in source_uncertainty
                ),
            )
        )
        bom_only_display = ", ".join(reference.upper() for reference in bom_only)
        placement_only_display = ", ".join(
            reference.upper() for reference in placement_only
        )
        finding = make_finding(
            context,
            rule_id=self.rule_id,
            category=RiskMode.CROSS_FILE_INCONSISTENCY,
            config_path="rules.bom_placement_reference_match",
            title="BOM and placement reference sets differ",
            summary=(
                "The populated, non-ignored BOM and placement reference sets "
                "contain directional differences."
            ),
            facts=(
                f"BOM-only references: {bom_only_display or 'none'}.",
                f"Placement-only references: {placement_only_display or 'none'}.",
                ("DNP and configured ignored references were excluded symmetrically."),
            ),
            evidence=comparison_evidence,
            confidence=(0.5 if confirmation else 1.0),
            suggested_action=(
                "Reconcile the listed references between the populated BOM and "
                "placement export."
            ),
            requires_human_confirmation=confirmation,
        )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if confirmation else RuleCoverage.FULL),
            findings=(finding,),
            summary="BOM-only or placement-only references were found.",
            evaluated_object_count=applicable_count,
            applicable_object_count=applicable_count,
        )


def _dataset_uncertainty(
    uncertainty_by_source: dict[str, tuple[Provenance, ...]],
    sources: tuple[SourceFile, ...],
) -> tuple[Provenance, ...]:
    source_ids = sorted(source.source_file_id for source in sources)
    return tuple(
        provenance
        for source_id in source_ids
        for provenance in uncertainty_by_source.get(source_id, ())
    )


def _duplicate_finding(
    context: RuleContext,
    *,
    dataset: str,
    duplicate_references: tuple[str, ...],
    records_by_reference: Mapping[
        str,
        tuple[BOMItem | ComponentPlacement, ...],
    ],
    uncertainty: tuple[Provenance, ...],
) -> Finding:
    records: tuple[BOMItem | ComponentPlacement, ...] = tuple(
        record
        for reference in duplicate_references
        for record in records_by_reference[reference]
    )
    evidence = _unique_evidence(
        (
            *_record_evidence(
                records,
                note=f"Row-level evidence for a duplicate {dataset} reference.",
            ),
            *(
                FindingEvidence(
                    provenance=provenance,
                    note=f"Project uncertainty witness affecting the {dataset}.",
                )
                for provenance in uncertainty
            ),
        )
    )
    display = ", ".join(reference.upper() for reference in duplicate_references)
    requires_confirmation = bool(uncertainty)
    return make_finding(
        context,
        rule_id=RuleId.DUPLICATE_REFERENCE_DESIGNATOR,
        category=RiskMode.CROSS_FILE_INCONSISTENCY,
        config_path="rules.duplicate_reference_designator",
        title=f"{dataset} contains duplicate reference designators",
        summary=(
            f"The normalized, populated {dataset} contains reference "
            "designators more than once."
        ),
        facts=(
            f"Dataset: {dataset}.",
            f"Duplicate normalized references: {display}.",
            (
                "DNP and configured ignored references were excluded before "
                "same-dataset duplicate detection."
            ),
        ),
        evidence=evidence,
        confidence=(0.5 if requires_confirmation else 1.0),
        suggested_action=(
            f"Remove or reconcile duplicate reference rows within the {dataset}."
        ),
        requires_human_confirmation=requires_confirmation,
    )


@dataclass(frozen=True, slots=True)
class DuplicateReferenceDesignatorRule:
    """Detect duplicates independently within BOM and placement data."""

    rule_id: RuleId = RuleId.DUPLICATE_REFERENCE_DESIGNATOR
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = ()

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Report same-dataset duplicates without comparing BOM against CPL."""
        if not context.project.assembly_requirements.review_requested:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary="Assembly review scope is not active.",
            )

        project = context.project
        inventory = assembly_data_inventory(project)
        usable_dataset_count = sum((inventory.bom_usable, inventory.placement_usable))
        if not usable_dataset_count:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.INPUT_UNCERTAIN,
                summary="No usable assembly dataset is available for duplicate checks.",
            )

        bom = _bom_references(context) if inventory.bom_usable else {}
        placement = _placement_references(context) if inventory.placement_usable else {}
        bom_duplicates = tuple(
            sorted(reference for reference, records in bom.items() if len(records) > 1)
        )
        placement_duplicates = tuple(
            sorted(
                reference
                for reference, records in placement.items()
                if len(records) > 1
            )
        )
        uncertainty_by_source = project_uncertainty_evidence(context)
        bom_uncertainty = _dataset_uncertainty(
            uncertainty_by_source,
            inventory.bom_sources,
        )
        placement_uncertainty = _dataset_uncertainty(
            uncertainty_by_source,
            inventory.placement_sources,
        )
        assembly_source_ids = {
            source.source_file_id
            for source in (*inventory.bom_sources, *inventory.placement_sources)
        }
        unresolved_candidates = (
            *inventory.candidate_sources(
                project,
                file_types=bom_file_types(),
            ),
            *inventory.candidate_sources(
                project,
                file_types=placement_file_types(),
            ),
        )
        coverage_partial = bool(
            bom_uncertainty
            or placement_uncertainty
            or unresolved_candidates
            or inventory.failed_source_ids.intersection(assembly_source_ids)
        )
        findings = (
            *(
                (
                    _duplicate_finding(
                        context,
                        dataset="BOM",
                        duplicate_references=bom_duplicates,
                        records_by_reference=bom,
                        uncertainty=bom_uncertainty,
                    ),
                )
                if bom_duplicates
                else ()
            ),
            *(
                (
                    _duplicate_finding(
                        context,
                        dataset="placement",
                        duplicate_references=placement_duplicates,
                        records_by_reference=placement,
                        uncertainty=placement_uncertainty,
                    ),
                )
                if placement_duplicates
                else ()
            ),
        )
        evaluated_count = len(bom) + len(placement)
        if not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=(
                    RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL
                ),
                summary=(
                    "No duplicates were found in evaluated assembly data, but "
                    "source uncertainty prevents a complete pass claim."
                    if coverage_partial
                    else (
                        "No duplicate reference designators were found within "
                        "the evaluated BOM or placement datasets."
                    )
                ),
                evaluated_object_count=evaluated_count,
                applicable_object_count=evaluated_count,
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=findings,
            summary="Duplicate references were found within assembly datasets.",
            evaluated_object_count=evaluated_count,
            applicable_object_count=evaluated_count,
        )


@dataclass(frozen=True, slots=True)
class PlacementOutsideBoardOutlineRule:
    """Classify placement anchor points against normalized board material."""

    rule_id: RuleId = RuleId.PLACEMENT_OUTSIDE_BOARD_OUTLINE
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (RuleId.BOARD_OUTLINE_CLOSED,)

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Check only CPL anchors, never inferred component extents."""
        if not context.project.assembly_requirements.review_requested:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.NOT_APPLICABLE,
                summary="Assembly review scope is not active.",
            )

        project = context.project
        inventory = assembly_data_inventory(project)
        placement_candidates = inventory.candidate_sources(
            project,
            file_types=placement_file_types(),
        )
        placements = _active_placements(context)
        if not inventory.placement_usable or not placements:
            uncertain_input = bool(
                not inventory.placement_usable
                and (inventory.placement_sources or placement_candidates)
            )
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=(
                    RuleReason.INPUT_UNCERTAIN
                    if uncertain_input
                    else RuleReason.NOT_APPLICABLE
                ),
                summary=(
                    "Placement input exists but did not produce a usable dataset."
                    if uncertain_input
                    else ("No populated, non-ignored placement anchor is applicable.")
                ),
            )

        outline = project.board_outline
        if outline is None or not all(contour.closed for contour in outline.contours):
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.INPUT_UNCERTAIN,
                summary="A trusted closed board outline is required.",
            )
        material = board_material_geometry(outline)
        if material.is_empty or not material.is_valid:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.UNSUPPORTED_GEOMETRY,
                summary="Normalized board material geometry is empty or invalid.",
            )

        uncertainty_by_source = project_uncertainty_evidence(context)
        outline_source_ids = {
            provenance.source_file_id for provenance in outline.provenance
        }
        placement_source_ids = {
            *(source.source_file_id for source in inventory.placement_sources),
            *(placement.provenance.source_file_id for placement in placements),
        }
        relevant_source_ids = outline_source_ids | placement_source_ids
        relevant_uncertainty = tuple(
            provenance
            for source_id in sorted(relevant_source_ids)
            for provenance in uncertainty_by_source.get(source_id, ())
        )
        failed_placement_sources = inventory.failed_source_ids.intersection(
            placement_source_ids
        )
        coverage_partial = bool(
            relevant_uncertainty or failed_placement_sources or placement_candidates
        )
        error_bound = (
            outline.measurement_error_mm + context.profile.tolerances.geometry_epsilon
        )
        findings: list[Finding] = []
        boundary = material.boundary
        for placement in placements:
            anchor = ShapelyPoint(placement.position.x, placement.position.y)
            if material.covers(anchor):
                boundary_distance = anchor.distance(boundary)
                if boundary_distance <= error_bound or math.isclose(
                    boundary_distance,
                    error_bound,
                    rel_tol=1e-12,
                    abs_tol=1e-12,
                ):
                    coverage_partial = True
                continue

            separation = anchor.distance(material)
            error_confirmation = separation <= error_bound or math.isclose(
                separation,
                error_bound,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            placement_uncertainty = uncertainty_by_source.get(
                placement.provenance.source_file_id,
                (),
            )
            outline_uncertainty = tuple(
                provenance
                for source_id in sorted(outline_source_ids)
                for provenance in uncertainty_by_source.get(source_id, ())
            )
            finding_uncertainty = (
                *placement_uncertainty,
                *outline_uncertainty,
            )
            confirmation = bool(error_confirmation or finding_uncertainty)
            evidence = _unique_evidence(
                (
                    FindingEvidence(
                        provenance=placement.provenance,
                        note="CPL anchor-point row evidence.",
                    ),
                    *(
                        FindingEvidence(
                            provenance=provenance,
                            witness_bounds=outline.bounding_box,
                            note="Outer/cutout board material boundary witness.",
                        )
                        for provenance in outline.provenance
                    ),
                    *(
                        FindingEvidence(
                            provenance=provenance,
                            note=(
                                "Project uncertainty witness affecting this "
                                "anchor classification."
                            ),
                        )
                        for provenance in finding_uncertainty
                    ),
                )
            )
            measurement = Measurement(
                actual=separation,
                required=0.0,
                operator="<=",
                unit=Unit.MILLIMETRE,
                error_bound=error_bound,
                config_path="rules.placement_outside_board_outline",
            )
            findings.append(
                make_finding(
                    context,
                    rule_id=self.rule_id,
                    category=(
                        RiskMode.OUTLINE_UNCERTAIN
                        if error_confirmation
                        else RiskMode.GEOMETRY_VIOLATION
                    ),
                    config_path="rules.placement_outside_board_outline",
                    title=(
                        "Placement anchor containment requires confirmation"
                        if confirmation
                        else "Placement anchor is outside board material"
                    ),
                    summary=(
                        "The CPL anchor is outside the normalized outer/cutout "
                        "board material; no component-body extent was inferred."
                    ),
                    facts=(
                        f"Reference is {placement.reference}.",
                        (
                            "Anchor position is "
                            f"({placement.position.x:.6f}, "
                            f"{placement.position.y:.6f}) mm."
                        ),
                        f"Distance to board material is {separation:.6f} mm.",
                        (
                            "Only the placement anchor was evaluated; body, "
                            "courtyard, and rotation clearance were not inferred."
                        ),
                    ),
                    evidence=evidence,
                    confidence=(0.5 if confirmation else 1.0),
                    location=placement.position,
                    measurement=measurement,
                    suggested_action=(
                        "Confirm the intended origin or move the placement "
                        "anchor onto board material."
                    ),
                    requires_human_confirmation=confirmation,
                )
            )
            coverage_partial = coverage_partial or confirmation

        evaluated_count = len(placements)
        if not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=(
                    RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL
                ),
                summary=(
                    "No evaluated placement anchor is outside board material, "
                    "but boundary or source uncertainty prevents a complete "
                    "pass claim."
                    if coverage_partial
                    else "Every evaluated placement anchor is on board material."
                ),
                evaluated_object_count=evaluated_count,
                applicable_object_count=evaluated_count,
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if coverage_partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary="One or more placement anchors are outside board material.",
            evaluated_object_count=evaluated_count,
            applicable_object_count=evaluated_count,
        )
