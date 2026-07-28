"""Deterministic Markdown composition from structured review evidence."""

from __future__ import annotations

from collections.abc import Callable

from boardgate.domain.enums import FileType, RiskMode, Severity
from boardgate.domain.finding import Finding, FindingEvidence
from boardgate.domain.geometry import BoundingBox
from boardgate.domain.project import PCBProject
from boardgate.domain.provenance import SourceSpan
from boardgate.domain.source import SourceFile
from boardgate.rules.models import (
    ReviewResult,
    RuleCoverage,
    RuleOutcome,
    RuleReason,
    RuleResult,
)

_MARKDOWN_PUNCTUATION = frozenset("\\`*_{}[]()<>#+-.!|:")

_STATUS_SUMMARIES = {
    "READY_FOR_REVIEW": (
        "Required checks completed; the evidence is ready for engineer review."
    ),
    "NOT_READY_FOR_FABRICATION": (
        "At least one confirmed blocker prevents fabrication readiness."
    ),
    "READY_WITH_CONFIRMATIONS": (
        "The checked evidence requires one or more human confirmations."
    ),
    "INSUFFICIENT_INFORMATION": (
        "Required evidence or a required rule result is unavailable."
    ),
    "ANALYSIS_FAILED": (
        "The analysis did not produce a complete, trustworthy review result."
    ),
}


def compose_markdown_report(project: PCBProject, review: ReviewResult) -> str:
    """Render a stable evidence-first report without timestamps or runtime data."""
    if project.project_id != review.project_id:
        msg = "project and review identifiers do not match"
        raise ValueError(msg)

    sections = [
        "# PCB Manufacturing Review",
        *_overall_assessment(review),
        *_evidence_confidence(project, review),
        *_input_files(project),
        *_board_summary(project),
        *_findings(review),
        *_missing_inputs(project, review),
        *_rules_executed(review),
        *_rules_not_executed(review),
        *_parser_and_analysis_limitations(project, review),
        *_confirmations_required(project, review),
        *_recommended_actions(review),
        *_evidence_index(project, review),
        "",
        "## Disclaimer",
        "",
        _escape_markdown(review.disclaimer),
    ]
    return "\n".join(sections).rstrip() + "\n"


def _overall_assessment(review: ReviewResult) -> list[str]:
    blocker_count = sum(
        finding.severity is Severity.BLOCKER for finding in review.findings
    )
    warning_count = sum(
        finding.severity in {Severity.HIGH, Severity.WARNING}
        for finding in review.findings
    )
    informational_count = sum(
        finding.severity is Severity.INFO for finding in review.findings
    )
    confirmation_count = sum(
        finding.requires_human_confirmation for finding in review.findings
    )
    status = review.overall_status.value
    lines = [
        "",
        "## Executive Summary",
        "",
        "### Overall Assessment",
        "",
        f"- Overall status: **{status}**",
        f"- Interpretation: {_STATUS_SUMMARIES[status]}",
        f"- Rule profile: {_escape_markdown(review.profile_id)}",
        (
            "- Findings: "
            f"{blocker_count} blocker(s), {warning_count} warning/high-risk, "
            f"{informational_count} informational"
        ),
        f"- Confirmation-required findings: {confirmation_count}",
    ]
    if review.analysis_diagnostics:
        lines.append("- Analysis diagnostics:")
        lines.extend(
            "  - "
            f"{diagnostic.category.value}/{diagnostic.stage.value}/"
            f"{diagnostic.code}: {_escape_markdown(diagnostic.summary)}"
            for diagnostic in review.analysis_diagnostics
        )
    return lines


def _evidence_confidence(
    project: PCBProject,
    review: ReviewResult,
) -> list[str]:
    full_count = sum(
        result.coverage is RuleCoverage.FULL for result in review.rule_results
    )
    partial_count = sum(
        result.coverage is RuleCoverage.PARTIAL for result in review.rule_results
    )
    none_count = sum(
        result.coverage is RuleCoverage.NONE for result in review.rule_results
    )
    lines = [
        "",
        "## Evidence Confidence",
        "",
        (
            f"- Rule coverage: {full_count} full, {partial_count} partial, "
            f"{none_count} none"
        ),
    ]
    if review.findings:
        confidences = [finding.confidence for finding in review.findings]
        lines.append(
            "- Finding confidence: "
            f"minimum {_format_percent(min(confidences))}, "
            f"mean {_format_percent(sum(confidences) / len(confidences))}"
        )
    else:
        lines.append("- No findings carry per-finding confidence values.")

    if project.layers:
        layer_confidences = [layer.mapping_confidence for layer in project.layers]
        lines.append(
            "- Layer-mapping confidence: "
            f"minimum {_format_percent(min(layer_confidences))}, "
            f"mean {_format_percent(sum(layer_confidences) / len(layer_confidences))}"
        )
    else:
        lines.append("- No normalized layers are available for confidence scoring.")

    uncertainties = sorted(
        project.uncertainties,
        key=lambda item: (
            item.risk_mode.value,
            item.subject.casefold(),
            item.summary.casefold(),
        ),
    )
    if not uncertainties:
        lines.append("- No project-level uncertainties were recorded.")
    else:
        lines.append(f"- Project-level uncertainties: {len(uncertainties)}")
        lines.extend(
            (
                "  - "
                f"{uncertainty.risk_mode.value}: "
                f"{_escape_markdown(uncertainty.subject)} — "
                f"{_escape_markdown(uncertainty.summary)}"
            )
            for uncertainty in uncertainties
        )
    return lines


def _input_files(project: PCBProject) -> list[str]:
    recognized = tuple(
        source
        for source in project.source_files
        if source.file_type is not FileType.UNKNOWN
    )
    unknown = tuple(
        source
        for source in project.source_files
        if source.file_type is FileType.UNKNOWN
    )
    lines = [
        "",
        "## Input Files",
        "",
        (
            f"- Inventory: {len(project.source_files)} total; "
            f"{len(recognized)} recognized; {len(unknown)} unknown"
        ),
    ]
    lines.extend(
        (
            "  - "
            f"{_escape_markdown(source.logical_path)} — "
            f"{_escape_markdown(source.file_type.value)} "
            f"({source.source_file_id})"
        )
        for source in sorted(
            project.source_files,
            key=lambda item: (item.logical_path.casefold(), item.logical_path),
        )
    )
    return lines


def _board_summary(project: PCBProject) -> list[str]:
    coordinate_system = project.coordinate_system
    lines = [
        "",
        "## Project Interpretation",
        "",
        "### Board Summary",
        "",
        f"- Project ID: {project.project_id}",
        (
            "- Coordinate system: "
            f"{coordinate_system.unit.value}; "
            f"X {_escape_markdown(coordinate_system.x_axis.value)}, "
            f"Y {_escape_markdown(coordinate_system.y_axis.value)}; "
            f"origin ({_format_number(coordinate_system.origin.x)}, "
            f"{_format_number(coordinate_system.origin.y)})"
        ),
    ]

    role_counts: dict[str, int] = {}
    for layer in project.layers:
        role_counts[layer.role.value] = role_counts.get(layer.role.value, 0) + 1
    roles = ", ".join(
        f"{_escape_markdown(role)}: {count}"
        for role, count in sorted(role_counts.items())
    )
    layer_suffix = f" ({roles})" if roles else ""
    lines.append(f"- Normalized layers: {len(project.layers)}{layer_suffix}")

    if project.board_outline is None:
        lines.append("- Board outline: unavailable")
    else:
        bounds = project.board_outline.bounding_box
        cutout_count = sum(
            contour.kind == "cutout" for contour in project.board_outline.contours
        )
        lines.append(
            "- Board dimensions: "
            f"{_format_number(bounds.width)} x {_format_number(bounds.height)} mm; "
            f"{project.board_outline.outer_contour_count} outer region(s); "
            f"{cutout_count} cutout(s)"
        )
    lines.extend(
        (
            f"- Drill features: {len(project.drills)} round hit(s), "
            f"{len(project.drill_slots)} routed slot(s)",
            (
                f"- Assembly data: {len(project.bom_items)} BOM row(s), "
                f"{len(project.components)} placement row(s); "
                "scope "
                + (
                    "enabled"
                    if project.assembly_requirements.review_requested
                    else "not requested"
                )
            ),
        )
    )
    return lines


def _findings(review: ReviewResult) -> list[str]:
    groups: tuple[
        tuple[str, Callable[[Finding], bool]],
        ...,
    ] = (
        ("Blockers", lambda finding: finding.severity is Severity.BLOCKER),
        (
            "High-Risk Findings",
            lambda finding: finding.severity is Severity.HIGH,
        ),
        (
            "Warning Findings",
            lambda finding: finding.severity is Severity.WARNING,
        ),
        (
            "Informational Findings",
            lambda finding: finding.severity is Severity.INFO,
        ),
    )
    lines: list[str] = []
    for heading, predicate in groups:
        lines.extend(("", f"## {heading}", ""))
        selected = sorted(
            (finding for finding in review.findings if predicate(finding)),
            key=lambda finding: finding.finding_id,
        )
        if not selected:
            lines.append("No findings in this category.")
            continue
        for finding in selected:
            lines.extend(_finding_detail(finding))
    return lines


def _finding_detail(finding: Finding) -> list[str]:
    lines = [
        f"#### {finding.finding_id} — {_escape_markdown(finding.title)}",
        "",
        (
            f"- Rule: {_escape_markdown(finding.rule_id)} "
            f"v{_escape_markdown(finding.rule_version)}"
        ),
        f"- Severity: {finding.severity.value}",
        f"- Category: {finding.category.value}",
        f"- Status: {finding.status.value}",
        f"- Confidence: {_format_percent(finding.confidence)}",
        f"- Summary: {_escape_markdown(finding.summary)}",
    ]
    if finding.location is not None:
        lines.append(
            "- Location: "
            f"({_format_number(finding.location.x)}, "
            f"{_format_number(finding.location.y)}) "
            f"{finding.location.unit.value}"
        )
    if finding.layer_ids:
        layers = ", ".join(_escape_markdown(layer) for layer in finding.layer_ids)
        lines.append(f"- Layers: {layers}")
    if finding.measurement is not None:
        measurement = finding.measurement
        lines.append(
            "- Measurement: "
            f"actual {_format_number(measurement.actual)} "
            f"{measurement.unit.value}; required {measurement.operator} "
            f"{_format_number(measurement.required)} {measurement.unit.value}; "
            f"error bound ±{_format_number(measurement.error_bound)} "
            f"{measurement.unit.value}; profile field "
            f"{_escape_markdown(measurement.config_path)}"
        )
    lines.append("- Facts:")
    lines.extend(f"  - {_escape_markdown(fact)}" for fact in finding.facts)
    if finding.inference is not None:
        lines.append(f"- Inference: {_escape_markdown(finding.inference)}")
    lines.append(
        "- Human confirmation required: "
        + ("yes" if finding.requires_human_confirmation else "no")
    )
    if finding.suggested_action is not None:
        lines.append(
            f"- Suggested action: {_escape_markdown(finding.suggested_action)}"
        )
    if finding.related_findings:
        related = ", ".join(
            _escape_markdown(identifier)
            for identifier in sorted(finding.related_findings)
        )
        lines.append(f"- Related findings: {related}")
    lines.extend(("",))
    return lines


def _missing_inputs(project: PCBProject, review: ReviewResult) -> list[str]:
    missing_findings = sorted(
        (
            finding
            for finding in review.findings
            if finding.category is RiskMode.FILE_INCOMPLETE
        ),
        key=lambda finding: finding.finding_id,
    )
    input_results = sorted(
        (
            result
            for result in review.rule_results
            if result.outcome in {RuleOutcome.SKIPPED, RuleOutcome.FAILED}
            and result.reason
            in {RuleReason.DEPENDENCY_UNAVAILABLE, RuleReason.INPUT_UNCERTAIN}
        ),
        key=lambda result: result.rule_id.value,
    )
    input_uncertainties = sorted(
        (
            uncertainty
            for uncertainty in project.uncertainties
            if uncertainty.risk_mode is RiskMode.FILE_INCOMPLETE
        ),
        key=lambda uncertainty: (
            uncertainty.subject.casefold(),
            uncertainty.summary.casefold(),
        ),
    )
    lines = ["", "## Missing Inputs", ""]
    if not (missing_findings or input_results or input_uncertainties):
        lines.append(
            "No missing input was identified by structured findings, "
            "uncertainties, or rule-result reasons."
        )
        return lines
    lines.extend(
        f"- {finding.finding_id}: {_escape_markdown(finding.summary)}"
        for finding in missing_findings
    )
    for result in input_results:
        assert result.reason is not None
        lines.append(
            f"- Rule {_escape_markdown(result.rule_id.value)}: "
            f"{result.reason.value} — {_escape_markdown(result.summary)}"
        )
    lines.extend(
        (
            "- "
            f"{_escape_markdown(uncertainty.subject)}: "
            f"{_escape_markdown(uncertainty.summary)}"
        )
        for uncertainty in input_uncertainties
    )
    return lines


def _rules_executed(review: ReviewResult) -> list[str]:
    executed = sorted(
        (
            result
            for result in review.rule_results
            if result.outcome in {RuleOutcome.PASS, RuleOutcome.FINDINGS}
        ),
        key=lambda result: result.rule_id.value,
    )
    lines = ["", "## Rules Executed", ""]
    if not executed:
        lines.append("No rule produced an evaluated result.")
        return lines
    lines.extend(_executed_rule_line(result) for result in executed)
    return lines


def _executed_rule_line(result: RuleResult) -> str:
    prefix = f"- {_escape_markdown(result.rule_id.value)} v{result.rule_version}: "
    counts = _object_counts(result)
    if result.outcome is RuleOutcome.PASS and result.coverage is RuleCoverage.PARTIAL:
        return (
            prefix + "no issue found in checked scope " + f"(coverage PARTIAL{counts})"
        )
    return (
        prefix
        + f"{result.outcome.value}; coverage {result.coverage.value}{counts} — "
        + _escape_markdown(result.summary)
    )


def _rules_not_executed(review: ReviewResult) -> list[str]:
    not_executed = sorted(
        (
            result
            for result in review.rule_results
            if result.outcome in {RuleOutcome.SKIPPED, RuleOutcome.FAILED}
        ),
        key=lambda result: result.rule_id.value,
    )
    lines = ["", "## Rules Not Executed", ""]
    if not not_executed:
        lines.append("All configured rule results were evaluated.")
        return lines
    for result in not_executed:
        assert result.reason is not None
        requirement = "required" if result.required else "optional"
        lines.append(
            f"- {_escape_markdown(result.rule_id.value)} v{result.rule_version}: "
            f"{result.outcome.value}; {result.reason.value}; {requirement} — "
            f"{_escape_markdown(result.summary)}"
        )
    return lines


def _parser_and_analysis_limitations(
    project: PCBProject,
    review: ReviewResult,
) -> list[str]:
    source_by_id = {source.source_file_id: source for source in project.source_files}
    limitation_findings = sorted(
        (
            finding
            for finding in review.findings
            if finding.category is RiskMode.PARSER_LIMITATION
        ),
        key=lambda finding: finding.finding_id,
    )
    diagnostics = sorted(
        project.source_diagnostics,
        key=lambda diagnostic: (
            diagnostic.source_file_id,
            diagnostic.code,
            diagnostic.diagnostic_id,
        ),
    )
    lines = ["", "## Parser and Analysis Limitations", ""]
    if not (diagnostics or limitation_findings or review.analysis_diagnostics):
        lines.append("No structured parser or analysis limitation was recorded.")
        return lines
    if review.analysis_diagnostics:
        lines.append(
            "- Run-level analysis diagnostics are listed in the Executive Summary."
        )
    for diagnostic in diagnostics:
        source = source_by_id.get(diagnostic.source_file_id)
        source_label = (
            _escape_markdown(source.logical_path)
            if source is not None
            else "unresolved source"
        )
        lines.append(
            f"- {diagnostic.level.value} {diagnostic.code} in {source_label} "
            f"({_escape_markdown(diagnostic.source_file_id)}), "
            f"{_source_span(diagnostic.source_span)}: "
            f"{_escape_markdown(diagnostic.message)}"
        )
    lines.extend(
        f"- {finding.finding_id}: {_escape_markdown(finding.summary)}"
        for finding in limitation_findings
    )
    return lines


def _confirmations_required(
    project: PCBProject,
    review: ReviewResult,
) -> list[str]:
    confirmation_findings = sorted(
        (finding for finding in review.findings if finding.requires_human_confirmation),
        key=lambda finding: finding.finding_id,
    )
    partial_rules = sorted(
        (
            result
            for result in review.rule_results
            if result.coverage is RuleCoverage.PARTIAL
        ),
        key=lambda result: result.rule_id.value,
    )
    uncertainties = sorted(
        (
            uncertainty
            for uncertainty in project.uncertainties
            if uncertainty.requires_human_confirmation
        ),
        key=lambda uncertainty: (
            uncertainty.risk_mode.value,
            uncertainty.subject.casefold(),
        ),
    )
    lines = [
        "",
        "## Requires Human Confirmation",
        "",
        "### Confirmations Required",
        "",
    ]
    if not (confirmation_findings or partial_rules or uncertainties):
        lines.append("No structured confirmation item was recorded.")
        return lines
    lines.extend(
        f"- {finding.finding_id}: {_escape_markdown(finding.summary)}"
        for finding in confirmation_findings
    )
    for result in partial_rules:
        detail = (
            "no issue found in checked scope"
            if result.outcome is RuleOutcome.PASS
            else _escape_markdown(result.summary)
        )
        lines.append(
            f"- Rule {_escape_markdown(result.rule_id.value)} has PARTIAL "
            f"coverage: {detail}"
        )
    lines.extend(
        (
            f"- {uncertainty.risk_mode.value} — "
            f"{_escape_markdown(uncertainty.subject)}: "
            f"{_escape_markdown(uncertainty.summary)}"
        )
        for uncertainty in uncertainties
    )
    return lines


def _recommended_actions(review: ReviewResult) -> list[str]:
    actions = sorted(
        (
            (finding.finding_id, finding.suggested_action)
            for finding in review.findings
            if finding.suggested_action is not None
        ),
        key=lambda item: item[0],
    )
    lines = [
        "",
        "## Optimization Suggestions",
        "",
        "### Recommended Actions",
        "",
    ]
    if not actions:
        lines.append("No finding-specific recommended action was recorded.")
        return lines
    lines.extend(
        f"- {finding_id}: {_escape_markdown(action)}" for finding_id, action in actions
    )
    return lines


def _evidence_index(
    project: PCBProject,
    review: ReviewResult,
) -> list[str]:
    source_by_id = {source.source_file_id: source for source in project.source_files}
    lines = ["", "## Evidence Index", ""]
    if not review.findings:
        lines.append("No finding evidence is present.")
        return lines
    for finding_index, finding in enumerate(
        sorted(review.findings, key=lambda item: item.finding_id),
    ):
        if finding_index:
            lines.append("")
        lines.extend(
            (
                f"### {finding.finding_id}",
                "",
            )
        )
        for index, evidence in enumerate(finding.evidence, start=1):
            lines.extend(
                _evidence_lines(
                    index=index,
                    evidence=evidence,
                    source=source_by_id.get(evidence.provenance.source_file_id),
                )
            )
    return lines


def _evidence_lines(
    *,
    index: int,
    evidence: FindingEvidence,
    source: SourceFile | None,
) -> list[str]:
    provenance = evidence.provenance
    source_label = (
        _escape_markdown(source.logical_path)
        if source is not None
        else "unresolved source"
    )
    lines = [
        f"- Evidence {index}:",
        (f"  - Source: {source_label} ({_escape_markdown(provenance.source_file_id)})"),
    ]
    if source is not None:
        lines.append(f"  - SHA-256: {source.sha256}")
    lines.extend(
        (
            "  - Parser: "
            f"{_escape_markdown(provenance.parser)} "
            f"v{_escape_markdown(provenance.parser_version)}",
            f"  - Object: {_optional_text(provenance.object_id)}",
            f"  - Source span: {_source_span(provenance.source_span)}",
        )
    )
    if evidence.layer_id is not None:
        lines.append(f"  - Layer: {_escape_markdown(evidence.layer_id)}")
    if evidence.witness_bounds is not None:
        lines.append(f"  - Witness bounds: {_bounding_box(evidence.witness_bounds)}")
    if evidence.note is not None:
        lines.append(f"  - Note: {_escape_markdown(evidence.note)}")
    return lines


def _source_span(span: SourceSpan | None) -> str:
    if span is None:
        return "not available"
    locations: list[str] = []
    if span.start_line is not None and span.end_line is not None:
        locations.append(
            f"line {span.start_line}"
            if span.start_line == span.end_line
            else f"lines {span.start_line}-{span.end_line}"
        )
    if span.start_byte is not None and span.end_byte is not None:
        locations.append(f"bytes {span.start_byte}-{span.end_byte}")
    return "; ".join(locations) if locations else "not available"


def _bounding_box(bounds: BoundingBox) -> str:
    return (
        f"({_format_number(bounds.minimum.x)}, "
        f"{_format_number(bounds.minimum.y)}) to "
        f"({_format_number(bounds.maximum.x)}, "
        f"{_format_number(bounds.maximum.y)}) mm"
    )


def _object_counts(result: RuleResult) -> str:
    if result.applicable_object_count is None:
        return f"; {result.evaluated_object_count} object(s) evaluated"
    return (
        f"; {result.evaluated_object_count}/"
        f"{result.applicable_object_count} object(s) evaluated"
    )


def _optional_text(value: str | None) -> str:
    return "not available" if value is None else _escape_markdown(value)


def _format_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") or "0"


def _format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _escape_markdown(value: str) -> str:
    collapsed = " ".join(value.split())
    escaped = "".join(
        f"\\{character}" if character in _MARKDOWN_PUNCTUATION else character
        for character in collapsed
    )
    return escaped or "(empty)"
