"""Complete-review artifact and catastrophic-failure contract tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from boardgate.application.artifacts import (
    COMPLETE_ARTIFACT_PATHS,
    DETERMINISTIC_ARTIFACT_PATHS,
    RUN_LOG_PATH,
    RUN_VARYING_ARTIFACT_PATHS,
    ArtifactContractError,
    CompleteArtifactBundle,
    RunLogEvent,
    RunLogLevel,
    build_analysis_unavailable_review,
    build_complete_artifact_bundle,
    deterministic_model_json,
    parse_run_log,
    run_log_jsonl,
    validate_artifact_bundle,
)
from boardgate.config.models import RuleId
from boardgate.domain.diagnostic import (
    AnalysisDiagnostic,
    AnalysisDiagnosticCategory,
    AnalysisStage,
)
from boardgate.domain.enums import (
    BoardSide,
    FileType,
    LayerRole,
    ReviewStatus,
    RiskMode,
    Severity,
)
from boardgate.domain.finding import Finding, FindingEvidence
from boardgate.domain.geometry import CoordinateSystem
from boardgate.domain.identifiers import (
    finding_id,
    project_id,
    source_file_id,
)
from boardgate.domain.layer import PCBLayer
from boardgate.domain.project import (
    AssemblyRequirements,
    FabricationRequirements,
    PCBProject,
)
from boardgate.domain.provenance import Provenance
from boardgate.domain.source import ProjectManifest, SourceFile
from boardgate.rules.models import (
    ReviewResult,
    RuleCoverage,
    RuleCoverageGap,
    RuleOutcome,
    RuleResult,
)

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIRECTORY = ROOT / "schemas" / "v1"
PROFILE_SHA = "a" * 64
SOURCE_SHA = "b" * 64
SOURCE_ID = source_file_id("board.gtl", SOURCE_SHA)
PROJECT_ID = project_id((("board.gtl", SOURCE_SHA),))
FINDING_ID = finding_id(
    rule_id=RuleId.MINIMUM_TRACE_WIDTH.value,
    rule_version="1.0",
    profile_sha256=PROFILE_SHA,
    evidence_ids=("profile-config:fabrication.min_trace_width", "line-1"),
    location=None,
    measurement=None,
)
RUN_ID = "run-0123456789abcdef"


def _manifest(*, project_id: str = PROJECT_ID) -> ProjectManifest:
    source = SourceFile(
        source_file_id=SOURCE_ID,
        logical_path="board.gtl",
        sha256=SOURCE_SHA,
        size_bytes=12,
        file_type=FileType.GERBER,
    )
    return ProjectManifest(project_id=project_id, source_files=(source,))


def _project(
    *,
    manifest: ProjectManifest | None = None,
    profile_id: str = "default-2layer",
    profile_sha256: str = PROFILE_SHA,
    include_layer: bool = False,
) -> PCBProject:
    selected_manifest = manifest or _manifest()
    layers = (
        (
            PCBLayer(
                layer_id="top-copper",
                source_file_id=SOURCE_ID,
                role=LayerRole.TOP_COPPER,
                side=BoardSide.TOP,
                mapping_confidence=1.0,
            ),
        )
        if include_layer
        else ()
    )
    return PCBProject(
        project_id=selected_manifest.project_id,
        source_files=selected_manifest.source_files,
        manifest=selected_manifest,
        coordinate_system=CoordinateSystem(),
        layers=layers,
        fabrication_requirements=FabricationRequirements(
            profile_id=profile_id,
            profile_sha256=profile_sha256,
            min_trace_width_mm=0.1,
        ),
        assembly_requirements=AssemblyRequirements(review_requested=False),
    )


def _finding() -> Finding:
    return Finding(
        finding_id=FINDING_ID,
        rule_id=RuleId.MINIMUM_TRACE_WIDTH.value,
        rule_version="1.0",
        category=RiskMode.GEOMETRY_VIOLATION,
        severity=Severity.WARNING,
        confidence=1.0,
        config_path="fabrication.min_trace_width",
        title="Trace width requires review",
        summary="A supported trace is below the configured threshold.",
        facts=("Measured trace width is 0.08 mm.",),
        evidence=(
            FindingEvidence(
                provenance=Provenance(
                    source_file_id=SOURCE_ID,
                    object_id="line-1",
                    parser="test",
                    parser_version="1.0",
                )
            ),
        ),
        suggested_action="Increase the trace width.",
    )


def _review(
    *,
    project_id: str = PROJECT_ID,
    profile_id: str = "default-2layer",
    profile_sha256: str = PROFILE_SHA,
) -> ReviewResult:
    finding = _finding()
    result = RuleResult(
        rule_id=RuleId.MINIMUM_TRACE_WIDTH,
        rule_version="1.0",
        outcome=RuleOutcome.FINDINGS,
        coverage=RuleCoverage.FULL,
        required=True,
        affects_readiness=True,
        findings=(finding,),
        summary="One trace-width issue was found.",
        evaluated_object_count=1,
        applicable_object_count=1,
    )
    return ReviewResult(
        project_id=project_id,
        profile_id=profile_id,
        profile_sha256=profile_sha256,
        overall_status=ReviewStatus.READY_FOR_REVIEW,
        rule_results=(result,),
        findings=(finding,),
        risk_modes=(RiskMode.GEOMETRY_VIOLATION,),
        disclaimer=(
            "Deterministic review evidence; fabricator approval is still required."
        ),
    )


def _coverage_limited_review() -> ReviewResult:
    gap = RuleCoverageGap(
        source_file_id=SOURCE_ID,
        layer_id="top-copper",
        metric="intersection_candidates_per_layer",
        unit="candidates",
        observed=1_000_001,
        limit=1_000_000,
        summary="The layer exceeded the deterministic candidate budget.",
    )
    result = RuleResult(
        rule_id=RuleId.MINIMUM_COPPER_SPACING,
        rule_version="1.0",
        outcome=RuleOutcome.PASS,
        coverage=RuleCoverage.PARTIAL,
        required=True,
        affects_readiness=True,
        coverage_gaps=(gap,),
        summary="No issue was found in the evaluated component pairs.",
        evaluated_object_count=1,
        applicable_object_count=2,
    )
    return ReviewResult(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        overall_status=ReviewStatus.READY_WITH_CONFIRMATIONS,
        rule_results=(result,),
        coverage_gaps=(gap,),
        risk_modes=(RiskMode.ANALYSIS_LIMITATION,),
        disclaimer="Deterministic review evidence; fabricator approval is required.",
    )


def _event(
    *,
    run_id: str = RUN_ID,
    sequence: int = 1,
    occurred_at: datetime | None = None,
    elapsed_ms: int = 12,
) -> RunLogEvent:
    return RunLogEvent(
        run_id=run_id,
        project_id=PROJECT_ID,
        sequence=sequence,
        occurred_at=occurred_at or datetime(2026, 7, 28, 12, 0, tzinfo=UTC),
        elapsed_ms=elapsed_ms,
        level=RunLogLevel.INFO,
        category=AnalysisDiagnosticCategory.ANALYSIS,
        stage=AnalysisStage.RULE_EXECUTION,
        code="REVIEW_COMPLETED",
        summary="The deterministic review completed.",
    )


def _report(review: ReviewResult) -> str:
    finding_lines = "\n".join(
        f"- {finding.finding_id}: {finding.title}" for finding in review.findings
    )
    return (
        "# PCB Manufacturing Review\n\n"
        f"<!-- boardgate-project-id: {review.project_id} -->\n"
        f"<!-- boardgate-profile-sha256: {review.profile_sha256} -->\n\n"
        f"{review.overall_status.value}\n{finding_lines}\n"
    )


def _svg(review: ReviewResult) -> str:
    markers = "".join(
        (
            f'<g data-finding-id="{finding.finding_id}">'
            f"<text>{finding.finding_id}</text></g>"
        )
        for finding in review.findings
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" '
        f'data-project-id="{review.project_id}" '
        f'data-profile-sha256="{review.profile_sha256}">'
        '<defs><linearGradient id="safe-gradient"/></defs>'
        f'<g fill="url(#safe-gradient)">{markers}</g></svg>\n'
    )


def _bundle(  # noqa: PLR0913
    *,
    manifest: ProjectManifest | None = None,
    project: PCBProject | None = None,
    review: ReviewResult | None = None,
    report: str | None = None,
    svg: str | None = None,
    events: tuple[RunLogEvent, ...] | None = None,
) -> CompleteArtifactBundle:
    selected_manifest = manifest or _manifest()
    selected_project = project or _project(manifest=selected_manifest)
    selected_review = review or _review(
        project_id=selected_project.project_id,
        profile_id=selected_project.fabrication_requirements.profile_id,
        profile_sha256=selected_project.fabrication_requirements.profile_sha256,
    )
    return build_complete_artifact_bundle(
        manifest=selected_manifest,
        project=selected_project,
        review=selected_review,
        report_markdown=report if report is not None else _report(selected_review),
        preview_svg=svg if svg is not None else _svg(selected_review),
        run_events=events or (_event(),),
    )


def _replace_file(
    bundle: CompleteArtifactBundle,
    path: str,
    payload: str,
) -> CompleteArtifactBundle:
    files = bundle.as_files()
    files[path] = payload
    return CompleteArtifactBundle.from_files(files)


def test_complete_bundle_has_exact_inventory_and_valid_public_schemas() -> None:
    bundle = _bundle()
    validated = validate_artifact_bundle(bundle)

    assert tuple(bundle.as_files()) == COMPLETE_ARTIFACT_PATHS
    assert COMPLETE_ARTIFACT_PATHS[:5] == DETERMINISTIC_ARTIFACT_PATHS
    assert RUN_VARYING_ARTIFACT_PATHS == (RUN_LOG_PATH,)
    assert validated.manifest == _manifest()
    assert validated.project == _project()
    assert validated.review == _review()
    assert validated.run_events == (_event(),)
    assert (
        CompleteArtifactBundle.model_validate_json(bundle.model_dump_json()) == bundle
    )

    for path, schema_name in (
        ("manifest.json", "manifest.schema.json"),
        ("project.json", "project.schema.json"),
        ("findings.json", "findings.schema.json"),
    ):
        schema = json.loads((SCHEMA_DIRECTORY / schema_name).read_text())
        jsonschema.Draft202012Validator(schema).validate(
            json.loads(bundle.as_files()[path])
        )


def test_preview_accepts_unique_local_static_gradient_references() -> None:
    review = _review()
    svg = _svg(review).replace(
        '<linearGradient id="safe-gradient"/>',
        (
            '<radialGradient id="safe-gradient" cx="50%" cy="50%" r="50%" '
            'gradientUnits="objectBoundingBox" spreadMethod="pad">'
            '<stop offset="0%" stop-color="#ffffff" stop-opacity="1"/>'
            '<stop offset="100%" stop-color="#000000" stop-opacity="0.5"/>'
            "</radialGradient>"
        ),
    )

    validated = validate_artifact_bundle(_bundle(review=review, svg=svg))

    assert validated.review == review


def test_only_run_log_varies_between_equivalent_runs() -> None:
    first = _bundle()
    second = _bundle(
        events=(
            _event(
                run_id="run-fedcba9876543210",
                occurred_at=datetime(2026, 7, 28, 12, 1, tzinfo=UTC),
                elapsed_ms=99,
            ),
        )
    )

    assert first.deterministic_bytes() == second.deterministic_bytes()
    assert first.run_log_jsonl != second.run_log_jsonl


@pytest.mark.parametrize(
    "files",
    [
        {path: "x" for path in COMPLETE_ARTIFACT_PATHS if path != "preview.svg"},
        {
            **dict.fromkeys(COMPLETE_ARTIFACT_PATHS, "x"),
            "unexpected.txt": "x",
        },
    ],
)
def test_bundle_rejects_missing_or_extra_artifact(files: dict[str, str]) -> None:
    with pytest.raises(
        ArtifactContractError,
        match="ARTIFACT_INVENTORY_MISMATCH",
    ):
        CompleteArtifactBundle.from_files(files)


def test_bundle_rejects_cross_artifact_project_and_profile_mismatch() -> None:
    bundle = _bundle()
    wrong_project_review = _review(project_id="prj-fedcba9876543210")
    wrong_profile_review = _review(profile_id="other-profile")

    with pytest.raises(ArtifactContractError, match="PROJECT_ID_MISMATCH"):
        validate_artifact_bundle(
            _replace_file(
                bundle,
                "findings.json",
                deterministic_model_json(wrong_project_review),
            )
        )
    with pytest.raises(ArtifactContractError, match="PROFILE_ID_MISMATCH"):
        validate_artifact_bundle(
            _replace_file(
                bundle,
                "findings.json",
                deterministic_model_json(wrong_profile_review),
            )
        )


def test_coverage_gap_evidence_is_cross_validated() -> None:
    project = _project(include_layer=True)
    review = _coverage_limited_review()
    bundle = _bundle(project=project, review=review)

    validated = validate_artifact_bundle(bundle)

    assert validated.review.coverage_gaps == review.coverage_gaps
    assert validated.review.risk_modes == (RiskMode.ANALYSIS_LIMITATION,)

    for field, invalid_value, expected_code in (
        (
            "source_file_id",
            "src-fedcba9876543210",
            "COVERAGE_GAP_SOURCE_EVIDENCE_MISMATCH",
        ),
        (
            "layer_id",
            "unknown-layer",
            "COVERAGE_GAP_LAYER_EVIDENCE_MISMATCH",
        ),
    ):
        payload = review.model_dump(mode="json")
        payload["coverage_gaps"][0][field] = invalid_value
        payload["rule_results"][0]["coverage_gaps"][0][field] = invalid_value
        invalid_review = ReviewResult.model_validate_json(json.dumps(payload))

        with pytest.raises(ArtifactContractError, match=expected_code):
            validate_artifact_bundle(
                _replace_file(
                    bundle,
                    "findings.json",
                    deterministic_model_json(invalid_review),
                )
            )


def test_bundle_rejects_noncanonical_model_json() -> None:
    bundle = _bundle()
    noncanonical = json.dumps(json.loads(bundle.manifest_json))

    with pytest.raises(ArtifactContractError, match="JSON_NONDETERMINISTIC"):
        validate_artifact_bundle(_replace_file(bundle, "manifest.json", noncanonical))


def test_report_and_svg_finding_ids_must_exactly_match_findings_json() -> None:
    bundle = _bundle()

    with pytest.raises(ArtifactContractError, match="REPORT_FINDING_ID_MISMATCH"):
        validate_artifact_bundle(
            _replace_file(
                bundle,
                "report.md",
                _report(_review()).replace(FINDING_ID, "finding-omitted"),
            )
        )
    with pytest.raises(ArtifactContractError, match="SVG_FINDING_ID_MISMATCH"):
        validate_artifact_bundle(
            _replace_file(
                bundle,
                "preview.svg",
                (
                    '<svg xmlns="http://www.w3.org/2000/svg" '
                    f'data-project-id="{PROJECT_ID}" '
                    f'data-profile-sha256="{PROFILE_SHA}"/>\n'
                ),
            )
        )


@pytest.mark.parametrize(
    ("svg", "code"),
    [
        (
            '<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>',
            "SVG_SCRIPT_REJECTED",
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
            "SVG_ACTIVE_ELEMENT_REJECTED",
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
            "SVG_EVENT_HANDLER_REJECTED",
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<image href="https://invalid.example/image.png"/></svg>',
            "SVG_EXTERNAL_REFERENCE_REJECTED",
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<style>@import "theme.css";</style></svg>',
            "SVG_EXTERNAL_REFERENCE_REJECTED",
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            "<style>g { animation: pulse 1s }</style></svg>",
            "SVG_ACTIVE_ELEMENT_REJECTED",
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g style="animation: pulse 1s"/></svg>',
            "SVG_ACTIVE_ELEMENT_REJECTED",
        ),
        (
            '<!DOCTYPE svg><svg xmlns="http://www.w3.org/2000/svg"/>',
            "SVG_ACTIVE_XML_REJECTED",
        ),
        (
            '<?xml version="1.0"?><?xml-stylesheet href="theme.css"?>'
            '<svg xmlns="http://www.w3.org/2000/svg"/>',
            "SVG_ACTIVE_XML_REJECTED",
        ),
    ],
)
def test_preview_rejects_active_or_external_content(svg: str, code: str) -> None:
    review = build_analysis_unavailable_review(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        diagnostics=(_diagnostic(),),
    )

    with pytest.raises(ArtifactContractError, match=code):
        _bundle(review=review, svg=svg)


@pytest.mark.parametrize(
    "element",
    [
        "animate",
        "animateColor",
        "animateMotion",
        "animateTransform",
        "discard",
        "mpath",
        "set",
    ],
)
def test_preview_rejects_every_svg_animation_element(element: str) -> None:
    review = build_analysis_unavailable_review(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        diagnostics=(_diagnostic(),),
    )
    svg = f'<svg xmlns="http://www.w3.org/2000/svg"><{element}/></svg>'

    with pytest.raises(ArtifactContractError, match="SVG_ACTIVE_ELEMENT_REJECTED"):
        _bundle(review=review, svg=svg)


@pytest.mark.parametrize(
    "svg",
    [
        "<svg/>",
        '<svg xmlns="urn:not-svg"/>',
        '<svg xmlns="http://www.w3.org/2000/svg"><g xmlns=""/></svg>',
        (
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:foreign="urn:test">'
            "<foreign:g/></svg>"
        ),
        (
            '<svg xmlns="http://www.w3.org/2000/svg" xmlns:foreign="urn:test">'
            '<g foreign:data-layer-id="top-copper"/></svg>'
        ),
    ],
)
def test_preview_requires_the_svg_namespace_for_elements_and_attributes(
    svg: str,
) -> None:
    review = build_analysis_unavailable_review(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        diagnostics=(_diagnostic(),),
    )

    with pytest.raises(ArtifactContractError, match="SVG_NAMESPACE_INVALID"):
        _bundle(review=review, svg=svg)


def test_preview_requires_an_exact_svg_root_local_name() -> None:
    review = build_analysis_unavailable_review(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        diagnostics=(_diagnostic(),),
    )

    with pytest.raises(ArtifactContractError, match="SVG_ROOT_INVALID"):
        _bundle(
            review=review,
            svg='<SVG xmlns="http://www.w3.org/2000/svg"/>',
        )


@pytest.mark.parametrize(
    "body",
    [
        "<a/>",
        "<use/>",
        "<image/>",
        "<filter/>",
        '<g class="layer"/>',
        '<g visibility="hidden"/>',
        '<g href="#local"/>',
        '<g data-unrecognized="value"/>',
    ],
)
def test_preview_rejects_elements_and_attributes_outside_passive_vocabulary(
    body: str,
) -> None:
    review = build_analysis_unavailable_review(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        diagnostics=(_diagnostic(),),
    )
    svg = f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>'

    with pytest.raises(ArtifactContractError, match="SVG_VOCABULARY_REJECTED"):
        _bundle(review=review, svg=svg)


@pytest.mark.parametrize(
    "body",
    [
        '<g fill="url(#missing-gradient)"/>',
        '<g id="not-a-gradient" fill="url(#not-a-gradient)"/>',
        (
            '<defs><linearGradient id="duplicate"/>'
            '<radialGradient id="duplicate"/></defs>'
            '<g fill="url(#duplicate)"/>'
        ),
        ('<defs><linearGradient id="quoted"/></defs><g fill="url(\'#quoted\')"/>'),
        (
            '<defs><linearGradient id="namespaced:id"/></defs>'
            '<g fill="url(#namespaced:id)"/>'
        ),
        (
            '<defs><linearGradient id="safe-gradient"/></defs>'
            '<g color="url(#safe-gradient)"/>'
        ),
        (
            '<defs><linearGradient id="safe-gradient">'
            '<stop offset="0" stop-color="url(#safe-gradient)"/>'
            "</linearGradient></defs>"
        ),
    ],
)
def test_preview_rejects_ambiguous_or_unsupported_internal_references(
    body: str,
) -> None:
    review = build_analysis_unavailable_review(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        diagnostics=(_diagnostic(),),
    )
    svg = f'<svg xmlns="http://www.w3.org/2000/svg">{body}</svg>'

    with pytest.raises(ArtifactContractError, match="SVG_VOCABULARY_REJECTED"):
        _bundle(review=review, svg=svg)


def test_run_log_round_trip_is_strict_single_run_and_monotonic() -> None:
    events = (
        _event(sequence=1),
        _event(
            sequence=3,
            occurred_at=datetime(2026, 7, 28, 12, 0, 1, tzinfo=UTC),
        ),
    )
    payload = run_log_jsonl(events)

    assert parse_run_log(payload) == events
    assert all(
        RunLogEvent.model_validate_json(line) in events for line in payload.splitlines()
    )

    with pytest.raises(ArtifactContractError, match="RUN_LOG_ID_MISMATCH"):
        run_log_jsonl(
            (
                _event(),
                _event(run_id="run-fedcba9876543210", sequence=2),
            )
        )
    with pytest.raises(ArtifactContractError, match="RUN_LOG_SEQUENCE_INVALID"):
        run_log_jsonl((_event(sequence=2), _event(sequence=2)))


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ("{}\n", "RUN_LOG_EVENT_INVALID"),
        ('{"sequence":1,"sequence":2}\n', "RUN_LOG_EVENT_INVALID"),
        ("NaN\n", "RUN_LOG_EVENT_INVALID"),
        ("{}\n\n", "RUN_LOG_LINE_INVALID"),
        ("{}", "RUN_LOG_TERMINATOR_MISSING"),
    ],
)
def test_invalid_jsonl_is_rejected(payload: str, code: str) -> None:
    with pytest.raises(ArtifactContractError, match=code):
        parse_run_log(payload)


def test_run_log_rejects_naive_timestamp_host_path_and_extra_fields() -> None:
    event = _event()

    with pytest.raises(ValidationError, match="UTC offset"):
        _event(occurred_at=datetime(2026, 7, 28, 12, 0))
    with pytest.raises(ValidationError, match="absolute host path"):
        RunLogEvent.model_validate(
            {
                **event.model_dump(),
                "summary": "Parser failed at /private/tmp/board.gbr.",
            }
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        RunLogEvent.model_validate(
            {
                **event.model_dump(),
                "exception": "must not be persisted",
            }
        )


def _diagnostic(
    *,
    code: str = "PROJECT_BUILD_UNAVAILABLE",
) -> AnalysisDiagnostic:
    return AnalysisDiagnostic(
        category=AnalysisDiagnosticCategory.ANALYSIS,
        stage=AnalysisStage.PROJECT_CONSTRUCTION,
        code=code,
        summary="The normalized project could not be constructed.",
    )


def test_analysis_unavailable_review_is_self_diagnostic_without_findings() -> None:
    later = _diagnostic(code="PROJECT_SOURCE_CHANGED")
    earlier = _diagnostic()

    review = build_analysis_unavailable_review(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        diagnostics=(later, earlier, later),
    )

    assert review.overall_status is ReviewStatus.ANALYSIS_FAILED
    assert review.rule_results == ()
    assert review.findings == ()
    assert review.risk_modes == ()
    assert review.analysis_diagnostics == (earlier, later)
    assert ReviewResult.model_validate_json(review.model_dump_json()) == review

    schema = json.loads((SCHEMA_DIRECTORY / "findings.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(review.model_dump(mode="json"))

    with pytest.raises(ValueError, match="requires a diagnostic"):
        build_analysis_unavailable_review(
            project_id=PROJECT_ID,
            profile_id="default-2layer",
            profile_sha256=PROFILE_SHA,
            diagnostics=(),
        )


def test_failure_bundle_is_complete_and_contains_no_normal_finding() -> None:
    review = build_analysis_unavailable_review(
        project_id=PROJECT_ID,
        profile_id="default-2layer",
        profile_sha256=PROFILE_SHA,
        diagnostics=(_diagnostic(),),
    )
    bundle = _bundle(
        review=review,
        report=_report(review),
        svg=_svg(review),
    )

    validated = validate_artifact_bundle(bundle)

    assert tuple(bundle.as_files()) == COMPLETE_ARTIFACT_PATHS
    assert validated.review.overall_status is ReviewStatus.ANALYSIS_FAILED
    assert not validated.review.findings


def test_run_varying_identifier_must_not_leak_into_stable_artifacts() -> None:
    bundle = _bundle()

    with pytest.raises(ArtifactContractError, match="RUN_VARIANCE_LEAKED"):
        validate_artifact_bundle(
            _replace_file(
                bundle,
                "report.md",
                f"{bundle.report_markdown}\nRun: {RUN_ID}\n",
            )
        )


def test_run_log_accepts_offset_aware_non_utc_timestamp() -> None:
    offset = timezone(timedelta(hours=8))
    event = _event(occurred_at=datetime(2026, 7, 28, 20, 0, tzinfo=offset))

    assert parse_run_log(run_log_jsonl((event,))) == (event,)
