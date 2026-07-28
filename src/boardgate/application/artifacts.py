"""Complete-review artifact contracts and pre-publication validation."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from typing import Self
from xml.etree import ElementTree

from pydantic import Field, field_validator

from boardgate.domain.base import StrictModel, VersionedModel
from boardgate.domain.diagnostic import (
    AnalysisDiagnostic,
    AnalysisDiagnosticCategory,
    AnalysisStage,
    ordered_analysis_diagnostics,
    validate_safe_diagnostic_summary,
)
from boardgate.domain.enums import ReviewStatus
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.rules.models import ReviewResult

MANIFEST_PATH = "manifest.json"
PROJECT_PATH = "project.json"
FINDINGS_PATH = "findings.json"
REPORT_PATH = "report.md"
PREVIEW_PATH = "preview.svg"
RUN_LOG_PATH = "logs/run.jsonl"

COMPLETE_ARTIFACT_PATHS: tuple[str, ...] = (
    MANIFEST_PATH,
    PROJECT_PATH,
    FINDINGS_PATH,
    REPORT_PATH,
    PREVIEW_PATH,
    RUN_LOG_PATH,
)
DETERMINISTIC_ARTIFACT_PATHS: tuple[str, ...] = COMPLETE_ARTIFACT_PATHS[:5]
RUN_VARYING_ARTIFACT_PATHS: tuple[str, ...] = (RUN_LOG_PATH,)

_FINDING_ID = re.compile(r"\bfnd-[0-9a-f]{16}\b")
_URL_SCHEME = re.compile(r"(?i)(?:https?|ftp|file|javascript|data):")
_CSS_URL = re.compile(r"(?i)url\(\s*([^)]+?)\s*\)")
_REVIEW_DISCLAIMER = (
    "BoardGate provides deterministic evidence for engineer review; it does not "
    "guarantee manufacturability or replace fabricator approval."
)


class ArtifactContractError(ValueError):
    """Stable, path-safe rejection raised before artifact publication."""

    def __init__(self, code: str, summary: str) -> None:
        self.code = code
        self.summary = summary
        super().__init__(f"{code}: {summary}")


class RunLogLevel(StrEnum):
    """Structured log severity independent of a logging implementation."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class RunLogEvent(VersionedModel):
    """One sanitized, run-varying event written to ``logs/run.jsonl``."""

    run_id: str = Field(pattern=r"^run-[0-9a-f]{16}$")
    sequence: int = Field(ge=1)
    occurred_at: datetime
    elapsed_ms: int = Field(ge=0)
    level: RunLogLevel
    category: AnalysisDiagnosticCategory
    stage: AnalysisStage
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    summary: str = Field(min_length=1, max_length=500)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Keep timestamps unambiguous across execution environments."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run-log timestamps must include a UTC offset")
        return value

    @field_validator("summary")
    @classmethod
    def require_sanitized_summary(cls, value: str) -> str:
        """Apply the same safe-text contract as persisted diagnostics."""
        return validate_safe_diagnostic_summary(value)


class CompleteArtifactBundle(VersionedModel):
    """The exact six UTF-8 payloads required for one published review."""

    manifest_json: str = Field(min_length=1)
    project_json: str = Field(min_length=1)
    findings_json: str = Field(min_length=1)
    report_markdown: str = Field(min_length=1)
    preview_svg: str = Field(min_length=1)
    run_log_jsonl: str = Field(min_length=1)

    @classmethod
    def from_files(cls, files: Mapping[str, str]) -> Self:
        """Construct only when the logical inventory is exactly complete."""
        if set(files) != set(COMPLETE_ARTIFACT_PATHS):
            raise ArtifactContractError(
                "ARTIFACT_INVENTORY_MISMATCH",
                "The artifact inventory does not match the required six-file contract.",
            )
        return cls(
            manifest_json=files[MANIFEST_PATH],
            project_json=files[PROJECT_PATH],
            findings_json=files[FINDINGS_PATH],
            report_markdown=files[REPORT_PATH],
            preview_svg=files[PREVIEW_PATH],
            run_log_jsonl=files[RUN_LOG_PATH],
        )

    def as_files(self) -> dict[str, str]:
        """Return the six logical paths in their normative stable order."""
        return {
            MANIFEST_PATH: self.manifest_json,
            PROJECT_PATH: self.project_json,
            FINDINGS_PATH: self.findings_json,
            REPORT_PATH: self.report_markdown,
            PREVIEW_PATH: self.preview_svg,
            RUN_LOG_PATH: self.run_log_jsonl,
        }

    def deterministic_bytes(self) -> dict[str, bytes]:
        """Return the five byte-stable artifacts, excluding the run log."""
        files = self.as_files()
        return {
            path: files[path].encode("utf-8") for path in DETERMINISTIC_ARTIFACT_PATHS
        }


class ArtifactBundleValidation(StrictModel):
    """Validated public models recovered from a complete bundle."""

    manifest: ProjectManifest
    project: PCBProject
    review: ReviewResult
    run_events: tuple[RunLogEvent, ...] = Field(min_length=1)


def deterministic_model_json(model: StrictModel) -> str:
    """Serialize one public model to canonical human-readable artifact bytes."""
    return (
        json.dumps(
            model.model_dump(mode="json"),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _compact_model_json(model: StrictModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_run_events(events: tuple[RunLogEvent, ...]) -> None:
    if not events:
        raise ArtifactContractError(
            "RUN_LOG_EMPTY",
            "The structured run log must contain at least one event.",
        )
    if len({event.run_id for event in events}) != 1:
        raise ArtifactContractError(
            "RUN_LOG_ID_MISMATCH",
            "All structured log events must use one run identifier.",
        )
    if any(
        current.sequence <= previous.sequence for previous, current in pairwise(events)
    ):
        raise ArtifactContractError(
            "RUN_LOG_SEQUENCE_INVALID",
            "Structured log sequence values must increase monotonically.",
        )


def run_log_jsonl(events: Iterable[RunLogEvent]) -> str:
    """Serialize sanitized events as deterministic-per-event JSON Lines."""
    ordered = tuple(events)
    _validate_run_events(ordered)
    return "".join(f"{_compact_model_json(event)}\n" for event in ordered)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"unsupported JSON constant {value}")


def parse_run_log(payload: str) -> tuple[RunLogEvent, ...]:
    """Parse one canonical JSONL stream and enforce its run-level invariants."""
    if not payload.endswith("\n"):
        raise ArtifactContractError(
            "RUN_LOG_TERMINATOR_MISSING",
            "The structured run log must end with a newline.",
        )
    lines = payload.splitlines()
    if not lines or any(not line for line in lines):
        raise ArtifactContractError(
            "RUN_LOG_LINE_INVALID",
            "The structured run log contains an empty or missing event.",
        )
    events: list[RunLogEvent] = []
    for line in lines:
        try:
            json.loads(
                line,
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_json_constant,
            )
            event = RunLogEvent.model_validate_json(line)
        except (TypeError, ValueError) as error:
            raise ArtifactContractError(
                "RUN_LOG_EVENT_INVALID",
                "A structured run-log event does not satisfy its strict contract.",
            ) from error
        events.append(event)
    result = tuple(events)
    _validate_run_events(result)
    return result


def build_analysis_unavailable_review(
    *,
    project_id: str,
    profile_id: str,
    profile_sha256: str,
    diagnostics: Iterable[AnalysisDiagnostic],
) -> ReviewResult:
    """Build a self-diagnostic failure result without normal rule findings."""
    ordered_diagnostics = ordered_analysis_diagnostics(diagnostics)
    if not ordered_diagnostics:
        raise ValueError("an analysis-unavailable review requires a diagnostic")
    return ReviewResult(
        project_id=project_id,
        profile_id=profile_id,
        profile_sha256=profile_sha256,
        overall_status=ReviewStatus.ANALYSIS_FAILED,
        rule_results=(),
        findings=(),
        risk_modes=(),
        analysis_diagnostics=ordered_diagnostics,
        disclaimer=_REVIEW_DISCLAIMER,
    )


def _parse_deterministic_model[ModelT: StrictModel](
    payload: str,
    model: type[ModelT],
    *,
    code: str,
) -> ModelT:
    try:
        parsed = model.model_validate_json(payload)
    except ValueError as error:
        raise ArtifactContractError(
            code,
            "A deterministic JSON artifact does not satisfy its public model.",
        ) from error
    if deterministic_model_json(parsed) != payload:
        raise ArtifactContractError(
            "ARTIFACT_JSON_NONDETERMINISTIC",
            "A deterministic JSON artifact is not in canonical serialized form.",
        )
    return parsed


def _local_name(name: str) -> str:
    return name.rsplit("}", maxsplit=1)[-1].casefold()


def _contains_external_reference(value: str) -> bool:
    stripped = value.strip().strip("\"'")
    if stripped.startswith("//") or _URL_SCHEME.search(stripped):
        return True
    for match in _CSS_URL.finditer(stripped):
        reference = match.group(1).strip().strip("\"'")
        if not reference.startswith("#"):
            return True
    return False


def _validate_safe_svg(svg: str) -> ElementTree.Element:
    lowered = svg.casefold()
    without_declaration = re.sub(
        r"^\s*<\?xml[^?]*\?>",
        "",
        svg,
        count=1,
        flags=re.IGNORECASE,
    )
    if "<!doctype" in lowered or "<!entity" in lowered or "<?" in without_declaration:
        raise ArtifactContractError(
            "SVG_ACTIVE_XML_REJECTED",
            "The SVG must not contain declarations that load or define active content.",
        )
    try:
        root = ElementTree.fromstring(svg)  # noqa: S314
    except ElementTree.ParseError as error:
        raise ArtifactContractError(
            "SVG_XML_INVALID",
            "The preview is not a well-formed SVG document.",
        ) from error
    if _local_name(root.tag) != "svg":
        raise ArtifactContractError(
            "SVG_ROOT_INVALID",
            "The preview document root must be an SVG element.",
        )
    for element in root.iter():
        tag = _local_name(element.tag)
        if tag == "script":
            raise ArtifactContractError(
                "SVG_SCRIPT_REJECTED",
                "The preview must not contain script elements.",
            )
        if tag in {"embed", "foreignobject", "iframe", "object"}:
            raise ArtifactContractError(
                "SVG_ACTIVE_ELEMENT_REJECTED",
                "The preview must not contain embedded active document elements.",
            )
        if tag == "style":
            style_text = element.text or ""
            if "@import" in style_text.casefold() or _contains_external_reference(
                style_text
            ):
                raise ArtifactContractError(
                    "SVG_EXTERNAL_REFERENCE_REJECTED",
                    "The preview must not load external style resources.",
                )
        for raw_name, value in element.attrib.items():
            name = _local_name(raw_name)
            if name.startswith("on"):
                raise ArtifactContractError(
                    "SVG_EVENT_HANDLER_REJECTED",
                    "The preview must not contain event-handler attributes.",
                )
            if _contains_external_reference(value) or (
                name in {"href", "src"} and not value.strip().startswith("#")
            ):
                raise ArtifactContractError(
                    "SVG_EXTERNAL_REFERENCE_REJECTED",
                    "The preview must not load or link to an external resource.",
                )
    return root


def validate_artifact_bundle(
    bundle: CompleteArtifactBundle,
) -> ArtifactBundleValidation:
    """Validate models, identities, report/SVG references, and one JSONL run."""
    manifest = _parse_deterministic_model(
        bundle.manifest_json,
        ProjectManifest,
        code="MANIFEST_JSON_INVALID",
    )
    project = _parse_deterministic_model(
        bundle.project_json,
        PCBProject,
        code="PROJECT_JSON_INVALID",
    )
    review = _parse_deterministic_model(
        bundle.findings_json,
        ReviewResult,
        code="FINDINGS_JSON_INVALID",
    )
    run_events = parse_run_log(bundle.run_log_jsonl)

    if project.manifest != manifest or project.project_id != manifest.project_id:
        raise ArtifactContractError(
            "ARTIFACT_PROJECT_ID_MISMATCH",
            "Manifest and project artifacts do not describe the same project.",
        )
    if review.project_id != project.project_id:
        raise ArtifactContractError(
            "ARTIFACT_PROJECT_ID_MISMATCH",
            "Project and findings artifacts do not describe the same project.",
        )
    requirements = project.fabrication_requirements
    if (
        review.profile_id != requirements.profile_id
        or review.profile_sha256 != requirements.profile_sha256
    ):
        raise ArtifactContractError(
            "ARTIFACT_PROFILE_ID_MISMATCH",
            "Project and findings artifacts do not use the same rule profile.",
        )

    expected_findings = {finding.finding_id for finding in review.findings}
    report_findings = set(_FINDING_ID.findall(bundle.report_markdown))
    if report_findings != expected_findings:
        raise ArtifactContractError(
            "REPORT_FINDING_ID_MISMATCH",
            "The report Finding identifiers do not match findings.json.",
        )

    svg_root = _validate_safe_svg(bundle.preview_svg)
    svg_findings = {
        value
        for element in svg_root.iter()
        for raw_name, value in element.attrib.items()
        if _local_name(raw_name) == "data-finding-id"
    }
    if svg_findings != expected_findings:
        raise ArtifactContractError(
            "SVG_FINDING_ID_MISMATCH",
            "The SVG Finding identifiers do not match findings.json.",
        )

    run_ids = {event.run_id for event in run_events}
    if any(
        run_id in payload
        for run_id in run_ids
        for path, payload in bundle.as_files().items()
        if path in DETERMINISTIC_ARTIFACT_PATHS
    ):
        raise ArtifactContractError(
            "RUN_VARIANCE_LEAKED",
            "Run-varying identifiers must occur only in the structured run log.",
        )

    return ArtifactBundleValidation(
        manifest=manifest,
        project=project,
        review=review,
        run_events=run_events,
    )


def build_complete_artifact_bundle(  # noqa: PLR0913
    *,
    manifest: ProjectManifest,
    project: PCBProject,
    review: ReviewResult,
    report_markdown: str,
    preview_svg: str,
    run_events: Iterable[RunLogEvent],
) -> CompleteArtifactBundle:
    """Serialize and validate all six artifacts before publication."""
    bundle = CompleteArtifactBundle(
        manifest_json=deterministic_model_json(manifest),
        project_json=deterministic_model_json(project),
        findings_json=deterministic_model_json(review),
        report_markdown=report_markdown,
        preview_svg=preview_svg,
        run_log_jsonl=run_log_jsonl(run_events),
    )
    validate_artifact_bundle(bundle)
    return bundle
