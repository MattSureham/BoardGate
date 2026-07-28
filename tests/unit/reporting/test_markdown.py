"""Deterministic Markdown report-composer tests."""

from __future__ import annotations

from itertools import pairwise

from boardgate.config.models import RuleId
from boardgate.domain.diagnostic import (
    AnalysisDiagnostic,
    AnalysisDiagnosticCategory,
    AnalysisStage,
    SourceDiagnostic,
    SourceDiagnosticLevel,
)
from boardgate.domain.enums import (
    BoardSide,
    FileType,
    LayerRole,
    ReviewStatus,
    RiskMode,
    Severity,
)
from boardgate.domain.finding import Finding, FindingEvidence, Measurement
from boardgate.domain.geometry import BoundingBox, CoordinateSystem, Point, Unit
from boardgate.domain.layer import (
    BoardOutline,
    OutlineContour,
    PCBLayer,
    RegionLineSegment,
)
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance, SourceSpan
from boardgate.domain.source import ProjectManifest, SourceFile, Uncertainty
from boardgate.reporting import compose_markdown_report
from boardgate.rules import (
    ReviewResult,
    RuleCoverage,
    RuleOutcome,
    RuleReason,
    RuleResult,
)

PROJECT_ID = "prj-0123456789abcdef"
SOURCE_ID = "src-0123456789abcdef"
PROFILE_SHA = "a" * 64


def _source(
    *,
    source_id: str = SOURCE_ID,
    logical_path: str = "inputs/board.gtl",
    file_type: FileType = FileType.GERBER,
) -> SourceFile:
    return SourceFile(
        source_file_id=source_id,
        logical_path=logical_path,
        sha256="b" * 64,
        size_bytes=42,
        file_type=file_type,
    )


def _provenance(
    *,
    source_id: str = SOURCE_ID,
    object_id: str = "primitive-1",
    with_span: bool = True,
) -> Provenance:
    return Provenance(
        source_file_id=source_id,
        object_id=object_id,
        parser="test<parser>",
        parser_version="1.0",
        source_span=(
            SourceSpan(
                start_line=7,
                end_line=7,
                start_byte=10,
                end_byte=20,
            )
            if with_span
            else None
        ),
    )


def _outline() -> BoardOutline:
    points = (
        Point(x=0.0, y=0.0),
        Point(x=10.0, y=0.0),
        Point(x=10.0, y=5.0),
        Point(x=0.0, y=5.0),
        Point(x=0.0, y=0.0),
    )
    segments = tuple(
        RegionLineSegment(start=start, end=end) for start, end in pairwise(points)
    )
    contour = OutlineContour(
        contour_id="outer-1",
        kind="outer",
        segments=segments,
        points=points,
        closed=True,
        approximation_error_mm=0.001,
        source_primitive_ids=("line-1", "line-2", "line-3", "line-4"),
    )
    return BoardOutline(
        contours=(contour,),
        bounding_box=BoundingBox(
            minimum=Point(x=0.0, y=0.0),
            maximum=Point(x=10.0, y=5.0),
        ),
        outer_contour_count=1,
        measurement_error_mm=0.001,
        provenance=(_provenance(object_id="outline-1"),),
    )


def _project(  # noqa: PLR0913
    *,
    sources: tuple[SourceFile, ...] | None = None,
    outline: BoardOutline | None = None,
    include_layer: bool = False,
    uncertainties: tuple[Uncertainty, ...] = (),
    diagnostics: tuple[SourceDiagnostic, ...] = (),
    review_requested: bool = False,
) -> PCBProject:
    selected_sources = sources or (_source(),)
    layers = (
        (
            PCBLayer(
                layer_id="top<copper>",
                source_file_id=SOURCE_ID,
                role=LayerRole.TOP_COPPER,
                side=BoardSide.TOP,
                mapping_confidence=0.875,
            ),
        )
        if include_layer
        else ()
    )
    return PCBProject(
        project_id=PROJECT_ID,
        source_files=selected_sources,
        manifest=ProjectManifest(
            project_id=PROJECT_ID,
            source_files=selected_sources,
        ),
        coordinate_system=CoordinateSystem(),
        layers=layers,
        board_outline=outline,
        source_diagnostics=diagnostics,
        fabrication_requirements=FabricationRequirements(
            profile_id="test.profile",
            profile_sha256=PROFILE_SHA,
        ),
        assembly_requirements=AssemblyRequirements(
            review_requested=review_requested,
        ),
        uncertainties=uncertainties,
    )


def _finding(  # noqa: PLR0913
    finding_id: str,
    rule_id: RuleId,
    *,
    category: RiskMode,
    severity: Severity,
    confirmation: bool = False,
    title: str = "Structured finding",
    summary: str = "Structured evidence requires review.",
    source_id: str = SOURCE_ID,
    suggested_action: str | None = None,
    detailed: bool = False,
) -> Finding:
    evidence = FindingEvidence(
        provenance=_provenance(source_id=source_id),
        layer_id="top<copper>" if detailed else None,
        witness_bounds=(
            BoundingBox(
                minimum=Point(x=1.0, y=2.0),
                maximum=Point(x=3.0, y=4.0),
            )
            if detailed
            else None
        ),
        note="Evidence <note>" if detailed else None,
    )
    return Finding(
        finding_id=finding_id,
        rule_id=rule_id.value,
        rule_version="1.0",
        category=category,
        severity=severity,
        confidence=0.8,
        config_path="rules.test[0]",
        title=title,
        summary=summary,
        facts=("Measured <fact>.\n# not a heading",),
        inference="Possible [interpretation]." if detailed else None,
        location=Point(x=1.25, y=2.5) if detailed else None,
        layer_ids=("top<copper>",) if detailed else (),
        measurement=(
            Measurement(
                actual=0.1,
                required=0.2,
                operator=">=",
                unit=Unit.MILLIMETRE,
                error_bound=0.001,
                config_path="fabrication.min_width",
            )
            if detailed
            else None
        ),
        evidence=(evidence,),
        suggested_action=suggested_action,
        requires_human_confirmation=confirmation,
        related_findings=("fnd-9999999999999999",) if detailed else (),
    )


def _result(  # noqa: PLR0913
    rule_id: RuleId,
    *,
    outcome: RuleOutcome = RuleOutcome.PASS,
    coverage: RuleCoverage = RuleCoverage.FULL,
    findings: tuple[Finding, ...] = (),
    reason: RuleReason | None = None,
    summary: str = "The configured scope was evaluated.",
    required: bool = True,
) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_version="1.0",
        outcome=outcome,
        coverage=coverage,
        required=required,
        affects_readiness=True,
        findings=findings,
        reason=reason,
        summary=summary,
        evaluated_object_count=1 if coverage is not RuleCoverage.NONE else 0,
        applicable_object_count=2 if coverage is RuleCoverage.PARTIAL else 1,
    )


def _review(
    *results: RuleResult,
    status: ReviewStatus = ReviewStatus.READY_FOR_REVIEW,
    disclaimer: str = "Engineer review required.",
    analysis_diagnostics: tuple[AnalysisDiagnostic, ...] = (),
) -> ReviewResult:
    findings = tuple(finding for result in results for finding in result.findings)
    return ReviewResult(
        project_id=PROJECT_ID,
        profile_id="test.profile",
        profile_sha256=PROFILE_SHA,
        overall_status=status,
        rule_results=results,
        findings=findings,
        risk_modes=tuple(sorted({finding.category for finding in findings}, key=str)),
        analysis_diagnostics=analysis_diagnostics,
        disclaimer=disclaimer,
    )


def test_report_is_deterministic_and_has_all_required_sections() -> None:
    project = _project(outline=_outline(), include_layer=True)
    review = _review(_result(RuleId.MINIMUM_TRACE_WIDTH))

    first = compose_markdown_report(project, review)
    second = compose_markdown_report(project, review)

    assert first == second
    assert first.endswith("\n")
    for heading in (
        "# PCB Manufacturing Review",
        "## Executive Summary",
        "## Evidence Confidence",
        "## Input Files",
        "## Project Interpretation",
        "## Blockers",
        "## High-Risk Findings",
        "## Requires Human Confirmation",
        "## Optimization Suggestions",
        "## Rules Executed",
        "## Rules Not Executed",
        "## Parser and Analysis Limitations",
        "## Evidence Index",
        "## Disclaimer",
    ):
        assert heading in first
    assert "10 x 5 mm" in first
    assert first.count("- Assembly data:") == 1
    assert "minimum\\_trace\\_width v1.0: PASS; coverage FULL" in first
    assert "timestamp" not in first.casefold()


def test_findings_are_grouped_escaped_and_indexed_with_source_spans() -> None:
    unsafe_source = _source(
        logical_path="inputs/[board]<raw>.gtl",
    )
    blocker = _finding(
        "fnd-1111111111111111",
        RuleId.REQUIRED_LAYERS_PRESENT,
        category=RiskMode.FILE_INCOMPLETE,
        severity=Severity.BLOCKER,
        title="<script>\n# injected [title]",
        summary="Missing [input](javascript:alert(1)).",
        suggested_action="Add <trusted> input.",
        detailed=True,
    )
    warning = _finding(
        "fnd-2222222222222222",
        RuleId.MINIMUM_TRACE_WIDTH,
        category=RiskMode.GEOMETRY_VIOLATION,
        severity=Severity.WARNING,
        confirmation=True,
    )
    informational = _finding(
        "fnd-3333333333333333",
        RuleId.DUPLICATE_REFERENCE_DESIGNATOR,
        category=RiskMode.CROSS_FILE_INCONSISTENCY,
        severity=Severity.INFO,
    )
    review = _review(
        _result(
            RuleId.REQUIRED_LAYERS_PRESENT,
            outcome=RuleOutcome.FINDINGS,
            findings=(blocker,),
        ),
        _result(
            RuleId.MINIMUM_TRACE_WIDTH,
            outcome=RuleOutcome.FINDINGS,
            findings=(warning,),
        ),
        _result(
            RuleId.DUPLICATE_REFERENCE_DESIGNATOR,
            outcome=RuleOutcome.FINDINGS,
            findings=(informational,),
        ),
        status=ReviewStatus.NOT_READY_FOR_FABRICATION,
        disclaimer="Do not trust <raw> Markdown.",
    )

    report = compose_markdown_report(
        _project(sources=(unsafe_source,), include_layer=True),
        review,
    )

    for identifier in (
        blocker.finding_id,
        warning.finding_id,
        informational.finding_id,
    ):
        assert identifier in report
    assert report.index(blocker.finding_id) > report.index("## Blockers")
    assert report.index(warning.finding_id) > report.index("## Warning Findings")
    assert report.index(informational.finding_id) > report.index(
        "## Informational Findings"
    )
    assert "inputs/\\[board\\]\\<raw\\>\\.gtl" in report
    assert "<script>" not in report
    assert "\n# injected" not in report
    assert "\\[input\\]\\(javascript\\:alert\\(1\\)\\)" in report
    assert "line 7; bytes 10-20" in report
    assert "Witness bounds: (1, 2) to (3, 4) mm" in report
    assert blocker.suggested_action is not None
    assert "\\<trusted\\>" in report


def test_partial_pass_never_claims_a_full_pass() -> None:
    partial = _result(
        RuleId.MINIMUM_COPPER_SPACING,
        coverage=RuleCoverage.PARTIAL,
        summary="UNSAFE FULL PASS CLAIM",
    )

    report = compose_markdown_report(
        _project(),
        _review(
            partial,
            status=ReviewStatus.READY_WITH_CONFIRMATIONS,
        ),
    )

    assert "no issue found in checked scope" in report
    assert "UNSAFE FULL PASS CLAIM" not in report
    assert "PASS; coverage PARTIAL" not in report
    assert "Rule minimum\\_copper\\_spacing has PARTIAL coverage" in report


def test_missing_inputs_and_nonexecuted_rules_are_explicit() -> None:
    skipped = _result(
        RuleId.BOARD_OUTLINE_CLOSED,
        outcome=RuleOutcome.SKIPPED,
        coverage=RuleCoverage.NONE,
        reason=RuleReason.DEPENDENCY_UNAVAILABLE,
        summary="The outline dependency is unavailable.",
    )
    failed = _result(
        RuleId.MINIMUM_ANNULAR_RING,
        outcome=RuleOutcome.FAILED,
        coverage=RuleCoverage.NONE,
        reason=RuleReason.RULE_EXCEPTION,
        summary="The deterministic evaluator failed.",
    )

    report = compose_markdown_report(
        _project(),
        _review(
            skipped,
            failed,
            status=ReviewStatus.INSUFFICIENT_INFORMATION,
        ),
    )

    assert "Rule board\\_outline\\_closed: DEPENDENCY_UNAVAILABLE" in report
    assert (
        "board\\_outline\\_closed v1.0: SKIPPED; DEPENDENCY_UNAVAILABLE; required"
    ) in report
    assert ("minimum\\_annular\\_ring v1.0: FAILED; RULE_EXCEPTION; required") in report


def test_uncertainties_diagnostics_and_unresolved_evidence_are_visible() -> None:
    uncertainty = Uncertainty(
        risk_mode=RiskMode.FILE_INCOMPLETE,
        subject="drill<input>",
        summary="Drill source needs [confirmation].",
        evidence=(_provenance(),),
    )
    diagnostic = SourceDiagnostic(
        diagnostic_id="diagnostic-0123456789abcdef",
        source_file_id=SOURCE_ID,
        code="PARSER_LIMITATION",
        level=SourceDiagnosticLevel.LIMITATION,
        message="Unsupported <macro>.\n# hidden heading",
        source_span=SourceSpan(start_line=9, end_line=11),
    )
    limitation = _finding(
        "fnd-4444444444444444",
        RuleId.MINIMUM_SOLDER_MASK_DAM,
        category=RiskMode.PARSER_LIMITATION,
        severity=Severity.INFO,
        source_id="src-9999999999999999",
    )

    report = compose_markdown_report(
        _project(
            uncertainties=(uncertainty,),
            diagnostics=(diagnostic,),
        ),
        _review(
            _result(
                RuleId.MINIMUM_SOLDER_MASK_DAM,
                outcome=RuleOutcome.FINDINGS,
                findings=(limitation,),
            ),
            status=ReviewStatus.READY_WITH_CONFIRMATIONS,
        ),
    )

    assert "PARSER_LIMITATION in inputs/board\\.gtl" in report
    assert "lines 9-11" in report
    assert "Unsupported \\<macro\\>\\. \\# hidden heading" in report
    assert "unresolved source (src\\-9999999999999999)" in report
    assert "drill\\<input\\>" in report
    assert "Drill source needs \\[confirmation\\]\\." in report


def test_report_rejects_a_review_for_another_project() -> None:
    review = _review(_result(RuleId.MINIMUM_TRACE_WIDTH))
    mismatched = review.model_copy(update={"project_id": "prj-fedcba9876543210"})

    try:
        compose_markdown_report(_project(), mismatched)
    except ValueError as error:
        assert str(error) == "project and review identifiers do not match"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("mismatched project/review pair was accepted")


def test_analysis_failed_review_explains_sanitized_run_diagnostics() -> None:
    diagnostic = AnalysisDiagnostic(
        category=AnalysisDiagnosticCategory.ANALYSIS,
        stage=AnalysisStage.PROJECT_CONSTRUCTION,
        code="PROJECT_BUILD_UNAVAILABLE",
        summary="Normalized *project* construction was unavailable.",
    )
    review = _review(
        status=ReviewStatus.ANALYSIS_FAILED,
        analysis_diagnostics=(diagnostic,),
    )

    report = compose_markdown_report(_project(), review)

    assert (
        "ANALYSIS/PROJECT_CONSTRUCTION/PROJECT_BUILD_UNAVAILABLE: "
        "Normalized \\*project\\* construction was unavailable\\."
    ) in report
    assert (
        "Run-level analysis diagnostics are listed in the Executive Summary." in report
    )
