"""Deterministic source-presence and board-outline rules."""

from __future__ import annotations

import math
from dataclasses import dataclass

from boardgate import __version__
from boardgate.config.models import RuleId
from boardgate.domain.diagnostic import SourceDiagnosticLevel
from boardgate.domain.enums import FileType, LayerRole, RiskMode
from boardgate.domain.finding import FindingEvidence, Measurement
from boardgate.domain.geometry import Unit
from boardgate.domain.provenance import Provenance
from boardgate.rules.common import make_finding
from boardgate.rules.engine import RuleContext
from boardgate.rules.models import (
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
    ThresholdDisposition,
    evaluate_maximum_threshold,
)

_STRONG_MAPPING_CONFIDENCE = 0.75


def _layer_candidate_evidence(
    context: RuleContext,
    role: LayerRole,
) -> tuple[FindingEvidence, ...]:
    evidence: list[FindingEvidence] = []
    for layer in context.project.layers:
        matching = tuple(
            candidate
            for candidate in layer.mapping_candidates
            if candidate.role is role
        )
        if layer.role is not LayerRole.UNKNOWN or not matching:
            continue
        evidence.append(
            FindingEvidence(
                provenance=Provenance(
                    source_file_id=layer.source_file_id,
                    object_id=layer.layer_id,
                    parser="boardgate-layer-mapper",
                    parser_version=__version__,
                    metadata={
                        "required_role": role.value,
                        "maximum_candidate_confidence": max(
                            candidate.confidence for candidate in matching
                        ),
                    },
                ),
                layer_id=layer.layer_id,
                note="Unresolved layer mapping includes the required role.",
            )
        )
    return tuple(evidence)


def _unknown_source_evidence(context: RuleContext) -> tuple[FindingEvidence, ...]:
    return tuple(
        FindingEvidence(
            provenance=Provenance(
                source_file_id=source.source_file_id,
                object_id=source.source_file_id,
                parser="boardgate-classifier",
                parser_version=__version__,
                metadata={"logical_path": source.logical_path},
            ),
            note="File type is unresolved, so absence cannot be proven.",
        )
        for source in context.project.source_files
        if source.file_type is FileType.UNKNOWN
    )


def _inventory_evidence(context: RuleContext) -> tuple[FindingEvidence, ...]:
    return tuple(
        FindingEvidence(
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
            note="Confirmed project inventory used to establish absence.",
        )
        for source in context.project.source_files
    )


@dataclass(frozen=True, slots=True)
class RequiredLayersPresentRule:
    """Require each profile role without treating ambiguity as absence."""

    rule_id: RuleId = RuleId.REQUIRED_LAYERS_PRESENT
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = ()

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Evaluate trusted presence, confirmed absence, and candidates."""
        inventory = _inventory_evidence(context)
        if not inventory:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.INPUT_UNCERTAIN,
                summary="No classified project sources are available.",
            )
        trusted_roles = {
            layer.role
            for layer in context.project.layers
            if layer.role is not LayerRole.UNKNOWN
            and layer.mapping_confidence >= _STRONG_MAPPING_CONFIDENCE
            and not layer.uncertainties
        }
        findings = []
        partial = False
        uncertain_count = 0
        unknown_sources = _unknown_source_evidence(context)
        for index, role in enumerate(context.profile.required_layers):
            if role in trusted_roles:
                continue
            candidate_evidence = (
                *_layer_candidate_evidence(context, role),
                *unknown_sources,
            )
            config_path = f"required_layers[{index}]"
            if candidate_evidence:
                partial = True
                uncertain_count += 1
                findings.append(
                    make_finding(
                        context,
                        rule_id=self.rule_id,
                        category=RiskMode.LAYER_MAPPING_UNCERTAIN,
                        config_path=config_path,
                        title=f"Required layer {role.value} is unresolved",
                        summary=(
                            "Available source evidence could represent the "
                            "required layer, but its mapping is not confirmed."
                        ),
                        facts=(
                            f"The profile requires layer role {role.value}.",
                            "At least one source or layer mapping remains unresolved.",
                        ),
                        evidence=tuple(candidate_evidence),
                        confidence=0.5,
                        suggested_action=(
                            "Confirm the candidate file's X2 FileFunction or "
                            "provide an unambiguous layer export."
                        ),
                        requires_human_confirmation=True,
                    )
                )
            else:
                findings.append(
                    make_finding(
                        context,
                        rule_id=self.rule_id,
                        category=RiskMode.FILE_INCOMPLETE,
                        config_path=config_path,
                        title=f"Required layer {role.value} is missing",
                        summary=(
                            "No confirmed or unresolved project source can "
                            "satisfy the required layer role."
                        ),
                        facts=(
                            f"The profile requires layer role {role.value}.",
                            "The completely classified inventory contains no match.",
                        ),
                        evidence=inventory,
                        confidence=1.0,
                        suggested_action=(
                            f"Export and include the {role.value} fabrication layer."
                        ),
                    )
                )
        if not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=RuleCoverage.FULL,
                summary="All profile-required layer roles are strongly mapped.",
                evaluated_object_count=len(context.profile.required_layers),
                applicable_object_count=len(context.profile.required_layers),
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary=(
                "One or more required layer roles are missing or require "
                "mapping confirmation."
            ),
            evaluated_object_count=(
                len(context.profile.required_layers) - uncertain_count
            ),
            applicable_object_count=len(context.profile.required_layers),
        )


@dataclass(frozen=True, slots=True)
class DrillFilePresentRule:
    """Require one successfully parsed Excellon source."""

    rule_id: RuleId = RuleId.DRILL_FILE_PRESENT
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = ()

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Distinguish successful empty files, parse failures, and absence."""
        drill_sources = tuple(
            source
            for source in context.project.source_files
            if source.file_type is FileType.EXCELLON
        )
        failed_source_ids = {
            diagnostic.source_file_id
            for diagnostic in context.project.source_diagnostics
            if diagnostic.level is SourceDiagnosticLevel.ERROR
        }
        parsed_sources = tuple(
            source
            for source in drill_sources
            if source.source_file_id not in failed_source_ids
        )
        if parsed_sources:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=RuleCoverage.FULL,
                summary=("At least one confirmed Excellon source parsed successfully."),
                evaluated_object_count=len(parsed_sources),
                applicable_object_count=len(drill_sources),
            )

        failed_evidence = tuple(
            FindingEvidence(
                provenance=Provenance(
                    source_file_id=diagnostic.source_file_id,
                    object_id=diagnostic.diagnostic_id,
                    parser="boardgate-parser-runner",
                    parser_version=__version__,
                    source_span=diagnostic.source_span,
                    metadata={"diagnostic_code": diagnostic.code},
                ),
                note="A confirmed drill source could not be parsed completely.",
            )
            for diagnostic in context.project.source_diagnostics
            if diagnostic.source_file_id
            in {source.source_file_id for source in drill_sources}
            and diagnostic.level is SourceDiagnosticLevel.ERROR
        )
        candidate_evidence = tuple(
            FindingEvidence(
                provenance=Provenance(
                    source_file_id=source.source_file_id,
                    object_id=source.source_file_id,
                    parser="boardgate-classifier",
                    parser_version=__version__,
                    metadata={"logical_path": source.logical_path},
                ),
                note="Unresolved file classification could represent drill data.",
            )
            for source in context.project.source_files
            if source.file_type is FileType.UNKNOWN
        )
        uncertain_evidence = (*failed_evidence, *candidate_evidence)
        if uncertain_evidence:
            category = (
                RiskMode.PARSER_LIMITATION
                if failed_evidence
                else RiskMode.FILE_TYPE_UNKNOWN
            )
            finding = make_finding(
                context,
                rule_id=self.rule_id,
                category=category,
                config_path="rules.drill_file_present",
                title="Drill file availability requires confirmation",
                summary=(
                    "A potential or confirmed drill source exists, but a usable "
                    "Excellon parse is not available."
                ),
                facts=(
                    "No confirmed Excellon source completed parsing.",
                    "At least one unresolved or failed source could contain "
                    "drill data.",
                ),
                evidence=tuple(uncertain_evidence),
                confidence=0.5,
                suggested_action=(
                    "Provide a valid, unambiguous Excellon drill export and rerun."
                ),
                requires_human_confirmation=True,
            )
            return RuleEvaluation(
                outcome=RuleOutcome.FINDINGS,
                coverage=RuleCoverage.PARTIAL,
                findings=(finding,),
                summary="Drill-file presence cannot be confirmed.",
                evaluated_object_count=0,
                applicable_object_count=len(drill_sources),
            )

        inventory = _inventory_evidence(context)
        if not inventory:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.INPUT_UNCERTAIN,
                summary="No classified project sources are available.",
            )
        finding = make_finding(
            context,
            rule_id=self.rule_id,
            category=RiskMode.FILE_INCOMPLETE,
            config_path="rules.drill_file_present",
            title="Drill file is missing",
            summary=(
                "The completely classified project inventory contains no "
                "Excellon drill source."
            ),
            facts=("No source is classified as Excellon drill data.",),
            evidence=inventory,
            confidence=1.0,
            suggested_action="Export and include the plated/NPTH drill data.",
        )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=RuleCoverage.FULL,
            findings=(finding,),
            summary="The required Excellon drill source is absent.",
            evaluated_object_count=1,
            applicable_object_count=1,
        )


def _outline_candidate_evidence(
    context: RuleContext,
) -> tuple[FindingEvidence, ...]:
    evidence: list[FindingEvidence] = []
    for layer in context.project.layers:
        is_candidate = layer.role is LayerRole.BOARD_OUTLINE or any(
            candidate.role is LayerRole.BOARD_OUTLINE
            for candidate in layer.mapping_candidates
        )
        if not is_candidate:
            continue
        evidence.append(
            FindingEvidence(
                provenance=Provenance(
                    source_file_id=layer.source_file_id,
                    object_id=layer.layer_id,
                    parser="boardgate-outline-reconstructor",
                    parser_version=__version__,
                    metadata={"mapped_role": layer.role.value},
                ),
                layer_id=layer.layer_id,
                note=(
                    "Layer is an outline candidate, but no trustworthy board "
                    "outline was reconstructed."
                ),
            )
        )
    evidence.extend(_unknown_source_evidence(context))
    return tuple(evidence)


@dataclass(frozen=True, slots=True)
class BoardOutlinePresentRule:
    """Require a trustworthy reconstructed board-material boundary."""

    rule_id: RuleId = RuleId.BOARD_OUTLINE_PRESENT
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = ()

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Separate confirmed absence from candidate/reconstruction ambiguity."""
        if context.project.board_outline is not None:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=RuleCoverage.FULL,
                summary="A trustworthy board outline was reconstructed.",
                evaluated_object_count=1,
                applicable_object_count=1,
            )
        candidates = _outline_candidate_evidence(context)
        if candidates:
            finding = make_finding(
                context,
                rule_id=self.rule_id,
                category=RiskMode.OUTLINE_UNCERTAIN,
                config_path="rules.board_outline_present",
                title="Board outline requires confirmation",
                summary=(
                    "Outline-related source evidence exists, but BoardGate "
                    "could not reconstruct a trustworthy board boundary."
                ),
                facts=(
                    "No BoardOutline is available in the normalized project.",
                    "At least one source remains an outline candidate.",
                ),
                evidence=candidates,
                confidence=0.5,
                suggested_action=(
                    "Provide one unambiguous, supported, closed profile layer."
                ),
                requires_human_confirmation=True,
            )
            return RuleEvaluation(
                outcome=RuleOutcome.FINDINGS,
                coverage=RuleCoverage.PARTIAL,
                findings=(finding,),
                summary="Board-outline presence cannot be confirmed.",
                evaluated_object_count=0,
                applicable_object_count=1,
            )
        inventory = _inventory_evidence(context)
        if not inventory:
            return RuleEvaluation(
                outcome=RuleOutcome.SKIPPED,
                coverage=RuleCoverage.NONE,
                reason=RuleReason.INPUT_UNCERTAIN,
                summary="No classified project sources are available.",
            )
        finding = make_finding(
            context,
            rule_id=self.rule_id,
            category=RiskMode.FILE_INCOMPLETE,
            config_path="rules.board_outline_present",
            title="Board outline is missing",
            summary=(
                "No reconstructed outline or unresolved outline candidate is "
                "present in the completely classified project."
            ),
            facts=("The normalized project has no BoardOutline.",),
            evidence=inventory,
            confidence=1.0,
            suggested_action="Export and include one board profile/outline layer.",
        )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=RuleCoverage.FULL,
            findings=(finding,),
            summary="The required board outline is absent.",
            evaluated_object_count=1,
            applicable_object_count=1,
        )


@dataclass(frozen=True, slots=True)
class BoardOutlineClosedRule:
    """Verify outline closure without converting reconstruction uncertainty."""

    rule_id: RuleId = RuleId.BOARD_OUTLINE_CLOSED
    version: str = "1.0"
    dependencies: tuple[RuleId, ...] = (RuleId.BOARD_OUTLINE_PRESENT,)

    def evaluate(self, context: RuleContext) -> RuleEvaluation:
        """Check every contour against the configured closure/error boundary."""
        outline = context.project.board_outline
        if outline is None:
            candidates = _outline_candidate_evidence(context)
            if not candidates:
                return RuleEvaluation(
                    outcome=RuleOutcome.SKIPPED,
                    coverage=RuleCoverage.NONE,
                    reason=RuleReason.NOT_APPLICABLE,
                    summary="No board outline exists to evaluate for closure.",
                )
            finding = make_finding(
                context,
                rule_id=self.rule_id,
                category=RiskMode.OUTLINE_UNCERTAIN,
                config_path="tolerances.outline_closure",
                title="Outline closure cannot be evaluated",
                summary=(
                    "Outline source evidence exists, but supported closed "
                    "topology was not reconstructed."
                ),
                facts=("No normalized BoardOutline is available.",),
                evidence=candidates,
                confidence=0.5,
                suggested_action=(
                    "Repair open, branching, touching, or unsupported profile "
                    "geometry and export it again."
                ),
                requires_human_confirmation=True,
            )
            return RuleEvaluation(
                outcome=RuleOutcome.FINDINGS,
                coverage=RuleCoverage.PARTIAL,
                findings=(finding,),
                summary="Outline closure remains uncertain.",
                applicable_object_count=1,
            )

        evidence = tuple(
            FindingEvidence(
                provenance=provenance,
                witness_bounds=outline.bounding_box,
                note="Analytic outline segment provenance.",
            )
            for provenance in outline.provenance
        )
        findings = []
        partial = False
        for contour in outline.contours:
            gap = math.dist(
                (contour.points[0].x, contour.points[0].y),
                (contour.points[-1].x, contour.points[-1].y),
            )
            disposition = evaluate_maximum_threshold(
                actual=gap,
                required=context.profile.tolerances.outline_closure,
                error_bound=outline.measurement_error_mm,
            )
            if not contour.closed and disposition is ThresholdDisposition.SATISFIED:
                disposition = ThresholdDisposition.REQUIRES_CONFIRMATION
            if disposition is ThresholdDisposition.SATISFIED:
                continue
            confirmation = disposition is ThresholdDisposition.REQUIRES_CONFIRMATION
            partial = partial or confirmation
            measurement = Measurement(
                actual=gap,
                required=context.profile.tolerances.outline_closure,
                operator="<=",
                unit=Unit.MILLIMETRE,
                error_bound=outline.measurement_error_mm,
                config_path="tolerances.outline_closure",
            )
            findings.append(
                make_finding(
                    context,
                    rule_id=self.rule_id,
                    category=(
                        RiskMode.OUTLINE_UNCERTAIN
                        if confirmation
                        else RiskMode.GEOMETRY_VIOLATION
                    ),
                    config_path="tolerances.outline_closure",
                    title=(
                        "Outline closure requires confirmation"
                        if confirmation
                        else "Board outline is open"
                    ),
                    summary=(
                        "The contour closure gap/error band overlaps the "
                        "configured tolerance."
                        if confirmation
                        else (
                            "The contour closure gap remains above the "
                            "configured tolerance after error."
                        )
                    ),
                    facts=(
                        f"Contour {contour.contour_id} closure flag is "
                        f"{contour.closed}.",
                        f"Endpoint gap is {gap:.6f} mm.",
                    ),
                    evidence=evidence,
                    confidence=(0.5 if confirmation else 1.0),
                    location=contour.points[-1],
                    measurement=measurement,
                    suggested_action="Close and reconnect the board profile.",
                    requires_human_confirmation=confirmation,
                )
            )
        if not findings:
            return RuleEvaluation(
                outcome=RuleOutcome.PASS,
                coverage=RuleCoverage.FULL,
                summary=(
                    "Every reconstructed outline contour is closed within the "
                    "configured tolerance and error bound."
                ),
                evaluated_object_count=len(outline.contours),
                applicable_object_count=len(outline.contours),
            )
        return RuleEvaluation(
            outcome=RuleOutcome.FINDINGS,
            coverage=(RuleCoverage.PARTIAL if partial else RuleCoverage.FULL),
            findings=tuple(findings),
            summary="One or more board-outline contours are not proven closed.",
            evaluated_object_count=(
                len(outline.contours)
                - sum(finding.requires_human_confirmation for finding in findings)
            ),
            applicable_object_count=len(outline.contours),
        )
