"""Deterministic cross-file assembly data rules."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from boardgate import __version__
from boardgate.config.models import RuleId
from boardgate.domain.component import BOMItem, ComponentPlacement
from boardgate.domain.diagnostic import SourceDiagnosticLevel
from boardgate.domain.enums import RiskMode
from boardgate.domain.finding import Finding, FindingEvidence
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
    ignored = {_reference(value) for value in context.profile.policy.ignored_references}
    markers = frozenset(
        value.strip().casefold() for value in context.profile.policy.dnp_markers
    )
    grouped: dict[str, list[ComponentPlacement]] = {}
    for placement in context.project.components:
        if _is_placement_dnp(placement, markers):
            continue
        reference = _reference(placement.reference)
        if reference in ignored:
            continue
        grouped.setdefault(reference, []).append(placement)
    return {reference: tuple(placements) for reference, placements in grouped.items()}


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
        note="Classified project inventory used for cross-file comparison.",
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
