"""Optional, offline narrative presentation over immutable review evidence."""

from __future__ import annotations

from hashlib import sha256
from typing import Any, Protocol

from boardgate.agent.models import (
    NarrativeFinding,
    NarrativeItem,
    NarrativeRequest,
    NarrativeResponse,
    NarrativeSection,
    PresentationGroupKind,
    PresentationView,
)
from boardgate.domain.project import PCBProject
from boardgate.reporting import compose_markdown_report
from boardgate.rules.models import ReviewResult


class NarrativeProvider(Protocol):
    """Callable provider contract; v0.1 implementations remain offline."""

    def __call__(self, request: NarrativeRequest) -> NarrativeResponse:
        """Return a typed selection of facts already present in the request."""


class DeterministicNarrativeProvider:
    """Select every deterministic fact in the canonical presentation order."""

    def __call__(self, request: NarrativeRequest) -> NarrativeResponse:
        """Return a complete, deterministic evidence-selection response."""
        findings = {finding.finding_id: finding for finding in request.findings}
        return NarrativeResponse(
            project_id=request.project_id,
            baseline_sha256=request.baseline_sha256,
            deterministic=True,
            sections=tuple(
                NarrativeSection(
                    kind=group.kind,
                    items=tuple(
                        NarrativeItem(
                            finding_id=finding_id,
                            fact_indices=tuple(range(len(findings[finding_id].facts))),
                        )
                        for finding_id in group.finding_ids
                    ),
                )
                for group in request.groups
            ),
        )


def build_narrative_request(
    review: ReviewResult,
    presentation: PresentationView,
    baseline_report: str,
) -> NarrativeRequest:
    """Copy only existing finding facts into the provider boundary."""
    if review.project_id != presentation.project_id:
        msg = "review and presentation identifiers do not match"
        raise ValueError(msg)
    group_by_finding = {
        finding_id: group.kind
        for group in presentation.groups
        for finding_id in group.finding_ids
    }
    review_ids = {finding.finding_id for finding in review.findings}
    if set(group_by_finding) != review_ids:
        msg = "presentation must cover exactly the review findings"
        raise ValueError(msg)
    findings = tuple(
        NarrativeFinding(
            finding_id=finding.finding_id,
            group=group_by_finding[finding.finding_id],
            severity=finding.severity,
            risk_mode=finding.category,
            title=finding.title,
            summary=finding.summary,
            facts=finding.facts,
            suggested_action=finding.suggested_action,
            requires_human_confirmation=finding.requires_human_confirmation,
        )
        for finding in sorted(review.findings, key=lambda item: item.finding_id)
    )
    return NarrativeRequest(
        project_id=review.project_id,
        overall_status=review.overall_status,
        baseline_sha256=sha256(baseline_report.encode("utf-8")).hexdigest(),
        findings=findings,
        groups=presentation.groups,
    )


def compose_narrative_report(
    project: PCBProject,
    review: ReviewResult,
    presentation: PresentationView,
    provider: NarrativeProvider | None,
) -> str:
    """Compose a provider-enhanced report or return the exact baseline."""
    baseline = compose_markdown_report(project, review)
    if provider is None or not review.findings:
        return baseline
    try:
        request = build_narrative_request(review, presentation, baseline)
        raw_response: Any = provider(request)
        response = NarrativeResponse.model_validate(raw_response)
        _validate_response(request, response)
        return _render_narrative(baseline, request, response)
    except Exception:
        return baseline


def _validate_response(
    request: NarrativeRequest,
    response: NarrativeResponse,
) -> None:
    if not response.deterministic:
        raise ValueError("provider marked output as nondeterministic")
    if (
        response.project_id != request.project_id
        or response.baseline_sha256 != request.baseline_sha256
    ):
        raise ValueError("provider response identity does not match request")
    expected_kinds = tuple(group.kind for group in request.groups)
    if tuple(section.kind for section in response.sections) != expected_kinds:
        raise ValueError("provider sections do not follow the presentation plan")
    requested_groups = {group.kind: group.finding_ids for group in request.groups}
    findings = {finding.finding_id: finding for finding in request.findings}
    seen: list[str] = []
    for section in response.sections:
        item_ids = tuple(item.finding_id for item in section.items)
        if item_ids != requested_groups[section.kind]:
            raise ValueError("provider response must preserve grouped finding order")
        for item in section.items:
            finding = findings.get(item.finding_id)
            if finding is None:
                raise ValueError("provider referenced an unknown finding")
            if any(index >= len(finding.facts) for index in item.fact_indices):
                raise ValueError("provider referenced an unknown finding fact")
            seen.append(item.finding_id)
    if set(seen) != set(findings) or len(seen) != len(findings):
        raise ValueError("provider response must cover every finding exactly once")


_GROUP_HEADINGS = {
    PresentationGroupKind.BLOCKERS: "Blockers",
    PresentationGroupKind.HIGH_RISK: "High-Risk Findings",
    PresentationGroupKind.REQUIRES_HUMAN_CONFIRMATION: ("Requires Human Confirmation"),
    PresentationGroupKind.OPTIMIZATION_SUGGESTIONS: ("Optimization Suggestions"),
}
_MARKDOWN_PUNCTUATION = frozenset("\\`*_{}[]()<>#+-.!|:")


def _render_narrative(
    baseline: str,
    request: NarrativeRequest,
    response: NarrativeResponse,
) -> str:
    findings = {finding.finding_id: finding for finding in request.findings}
    lines = [
        "## Agent Evidence Narrative",
        "",
        (
            "This display groups existing deterministic findings and facts; "
            "it adds no measurements or manufacturing conclusions."
        ),
    ]
    for section in response.sections:
        if not section.items:
            continue
        lines.extend(("", f"### {_GROUP_HEADINGS[section.kind]}", ""))
        for item in section.items:
            finding = findings[item.finding_id]
            lines.append(
                f"- **{finding.finding_id} — {_escape_markdown(finding.title)}**"
            )
            lines.extend(
                "  - " + _escape_markdown(finding.facts[index])
                for index in item.fact_indices
            )
            if finding.suggested_action is not None:
                lines.append(
                    "  - Suggested action: "
                    + _escape_markdown(finding.suggested_action)
                )
    narrative = "\n".join(lines) + "\n"
    disclaimer_marker = "\n## Disclaimer\n"
    if disclaimer_marker not in baseline:
        raise ValueError("baseline report has no disclaimer insertion point")
    return baseline.replace(
        disclaimer_marker,
        f"\n{narrative}\n## Disclaimer\n",
        1,
    )


def _escape_markdown(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    escaped = "".join(
        f"\\{character}" if character in _MARKDOWN_PUNCTUATION else character
        for character in normalized
    )
    return escaped.replace("\n", " ")
