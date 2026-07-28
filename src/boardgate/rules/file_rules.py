"""Deterministic source-presence and board-outline rules."""

from __future__ import annotations

from dataclasses import dataclass

from boardgate import __version__
from boardgate.config.models import RuleId
from boardgate.domain.enums import FileType, LayerRole, RiskMode
from boardgate.domain.finding import FindingEvidence
from boardgate.domain.provenance import Provenance
from boardgate.rules.common import make_finding
from boardgate.rules.engine import RuleContext
from boardgate.rules.models import (
    RuleCoverage,
    RuleEvaluation,
    RuleOutcome,
    RuleReason,
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
