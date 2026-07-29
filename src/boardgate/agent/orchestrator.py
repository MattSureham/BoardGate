"""Deterministic planning and display-only review organization."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from boardgate.agent.models import (
    PRESENTATION_GROUP_ORDER,
    ParserId,
    ParserTask,
    PresentationGroup,
    PresentationGroupKind,
    PresentationView,
    ReviewPlan,
    RulePlanDisposition,
    RuleTask,
)
from boardgate.agent.risk_modes import directives_for, identify_risk_modes
from boardgate.config.models import RuleProfile, profile_hash
from boardgate.domain.enums import FileType, RiskMode, Severity
from boardgate.domain.source import ProjectManifest
from boardgate.rules.models import ReviewResult
from boardgate.rules.registry import RuleRegistry

_PARSER_BY_FILE_TYPE = {
    FileType.GERBER: ParserId.GERBER,
    FileType.EXCELLON: ParserId.EXCELLON,
    FileType.BOM_CSV: ParserId.BOM,
    FileType.BOM_XLSX: ParserId.BOM,
    FileType.PLACEMENT_CSV: ParserId.PLACEMENT,
}


@dataclass(frozen=True, slots=True)
class OrchestratedReview:
    """Raw review identity plus a separate, serializable presentation view."""

    raw_review: ReviewResult
    presentation: PresentationView


class DeterministicOrchestrator:
    """Plan deterministic tools and group their immutable output."""

    def __init__(self, registry: RuleRegistry) -> None:
        self._registry = registry

    def plan(
        self,
        manifest: ProjectManifest,
        profile: RuleProfile,
        *,
        risk_modes: Iterable[RiskMode] = (),
    ) -> ReviewPlan:
        """Select parsers and delegate profile-enabled rules to the rule engine."""
        by_parser: dict[ParserId, list[str]] = {}
        for source in manifest.source_files:
            parser_id = _PARSER_BY_FILE_TYPE.get(source.file_type)
            if parser_id is not None:
                by_parser.setdefault(parser_id, []).append(source.source_file_id)
        parser_tasks = tuple(
            ParserTask(
                parser_id=parser_id,
                source_file_ids=tuple(sorted(source_ids)),
            )
            for parser_id, source_ids in sorted(
                by_parser.items(), key=lambda item: str(item[0])
            )
        )
        rule_tasks = tuple(
            RuleTask(
                rule_id=rule.rule_id,
                disposition=(
                    RulePlanDisposition.EXECUTE
                    if profile.rules.by_id(rule.rule_id).enabled
                    else RulePlanDisposition.PROFILE_DISABLED
                ),
            )
            for rule in self._registry.ordered_rules
        )
        identified_modes = identify_risk_modes(manifest, risk_modes)
        return ReviewPlan(
            project_id=manifest.project_id,
            profile_id=profile.profile.id,
            profile_sha256=profile_hash(profile),
            parser_tasks=parser_tasks,
            rule_tasks=rule_tasks,
            risk_directives=directives_for(identified_modes),
        )

    def organize(
        self,
        plan: ReviewPlan,
        review: ReviewResult,
    ) -> OrchestratedReview:
        """Create a display partition while retaining the exact raw result."""
        if review.project_id != plan.project_id:
            msg = "review and orchestration plan identifiers do not match"
            raise ValueError(msg)
        if (
            review.profile_id != plan.profile_id
            or review.profile_sha256 != plan.profile_sha256
        ):
            msg = "review and orchestration plan profiles do not match"
            raise ValueError(msg)
        grouped: dict[PresentationGroupKind, list[str]] = {
            kind: [] for kind in PRESENTATION_GROUP_ORDER
        }
        for finding in review.findings:
            if finding.requires_human_confirmation:
                kind = PresentationGroupKind.REQUIRES_HUMAN_CONFIRMATION
            elif finding.severity is Severity.BLOCKER:
                kind = PresentationGroupKind.BLOCKERS
            elif finding.severity in {Severity.HIGH, Severity.WARNING}:
                kind = PresentationGroupKind.HIGH_RISK
            else:
                kind = PresentationGroupKind.OPTIMIZATION_SUGGESTIONS
            grouped[kind].append(finding.finding_id)
        groups = tuple(
            PresentationGroup(
                kind=kind,
                finding_ids=tuple(sorted(grouped[kind])),
            )
            for kind in PRESENTATION_GROUP_ORDER
        )
        modes = {
            *(directive.risk_mode for directive in plan.risk_directives),
            *review.risk_modes,
        }
        presentation = PresentationView(
            project_id=review.project_id,
            groups=groups,
            risk_directives=directives_for(modes),
        )
        return OrchestratedReview(raw_review=review, presentation=presentation)
