"""Versioned public contracts for deterministic PCB modification revisions."""

from __future__ import annotations

import re
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from boardgate.domain.base import VersionedModel
from boardgate.domain.enums import ReviewStatus
from boardgate.domain.provenance import SourceSpan
from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.paths import normalize_logical_path

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_SOURCE_ID_PATTERN = r"^src-[0-9a-f]{16}$"
_PROJECT_ID_PATTERN = r"^prj-[0-9a-f]{16}$"
_FINDING_ID_PATTERN = r"^fnd-[0-9a-f]{16}$"
_REVISION_ID_PATTERN = r"^rev-[0-9a-f]{16}$"
_TOOL_CODE_PATTERN = r"^T[0-9]{2,6}$"
_MAX_DRILL_DIAMETER_MM = 100.0
MODIFICATION_DISCLAIMER = (
    "This revision records a deterministic file modification and an independent "
    "BoardGate review; it does not guarantee manufacturability or replace "
    "fabricator and engineer approval."
)
MODIFICATION_OPERATION_KEYS = frozenset({("set_excellon_tool_diameter", "1.0")})


def _validate_safe_logical_path(value: str) -> str:
    """Reject paths that cannot identify one immutable bundle member."""
    try:
        normalized = normalize_logical_path(value, subject="<logical-path>")
    except IngestionError as error:
        msg = "logical path must be a normalized relative POSIX path"
        raise ValueError(msg) from error
    if normalized != value:
        msg = "logical path must be a normalized relative POSIX path"
        raise ValueError(msg)
    return value


class SetExcellonToolDiameter(VersionedModel):
    """One explicitly targeted, stale-safe Excellon tool-diameter request."""

    schema_version: Literal["1.0"]
    kind: Literal["set_excellon_tool_diameter"] = "set_excellon_tool_diameter"
    operation_version: Literal["1.0"]
    source_logical_path: str = Field(min_length=1, max_length=1024)
    source_file_id: str = Field(pattern=_SOURCE_ID_PATTERN)
    source_sha256: str = Field(pattern=_SHA256_PATTERN)
    tool_code: str = Field(pattern=_TOOL_CODE_PATTERN)
    expected_diameter_mm: float = Field(
        gt=0.0,
        le=_MAX_DRILL_DIAMETER_MM,
    )
    new_diameter_mm: float = Field(
        gt=0.0,
        le=_MAX_DRILL_DIAMETER_MM,
    )
    instruction: str = Field(min_length=1, max_length=500)

    _safe_source_path = field_validator("source_logical_path")(
        _validate_safe_logical_path
    )

    @model_validator(mode="after")
    def require_real_change(self) -> Self:
        """Reject no-op requests before any source is touched."""
        if self.expected_diameter_mm == self.new_diameter_mm:
            msg = "new_diameter_mm must differ from expected_diameter_mm"
            raise ValueError(msg)
        return self


type ModificationOperation = Annotated[
    SetExcellonToolDiameter,
    Field(discriminator="kind"),
]


class ModificationRequest(VersionedModel):
    """One canonical, explicitly authorized modification operation."""

    schema_version: Literal["1.0"]
    base_project_id: str = Field(pattern=_PROJECT_ID_PATTERN)
    operation: ModificationOperation


class PayloadFileEvidence(VersionedModel):
    """Before/after digest evidence for one emitted design file."""

    logical_path: str = Field(min_length=1, max_length=1024)
    before_sha256: str = Field(pattern=_SHA256_PATTERN)
    after_sha256: str = Field(pattern=_SHA256_PATTERN)
    before_size_bytes: int = Field(ge=0)
    after_size_bytes: int = Field(ge=0)
    changed: bool

    _safe_payload_path = field_validator("logical_path")(_validate_safe_logical_path)

    @model_validator(mode="after")
    def require_truthful_change_marker(self) -> Self:
        """Bind the marker to observable byte identity and size."""
        differs = (
            self.before_sha256 != self.after_sha256
            or self.before_size_bytes != self.after_size_bytes
        )
        if self.changed != differs:
            msg = "changed must match before/after byte evidence"
            raise ValueError(msg)
        return self


class AppliedExcellonToolDiameterChange(VersionedModel):
    """Auditable semantic and byte-span evidence for the applied operation."""

    kind: Literal["set_excellon_tool_diameter"] = "set_excellon_tool_diameter"
    operation_version: Literal["1.0"] = "1.0"
    adapter_id: Literal["boardgate-excellon-tool-diameter-patch"] = (
        "boardgate-excellon-tool-diameter-patch"
    )
    adapter_policy_version: Literal["1.0"] = "1.0"
    source_logical_path: str = Field(min_length=1, max_length=1024)
    input_source_file_id: str = Field(pattern=_SOURCE_ID_PATTERN)
    output_source_file_id: str = Field(pattern=_SOURCE_ID_PATTERN)
    input_sha256: str = Field(pattern=_SHA256_PATTERN)
    output_sha256: str = Field(pattern=_SHA256_PATTERN)
    tool_code: str = Field(pattern=_TOOL_CODE_PATTERN)
    old_diameter_mm: float = Field(gt=0.0, le=_MAX_DRILL_DIAMETER_MM)
    new_diameter_mm: float = Field(gt=0.0, le=_MAX_DRILL_DIAMETER_MM)
    input_value_span: SourceSpan
    output_value_span: SourceSpan
    affected_input_drill_ids: tuple[str, ...] = Field(min_length=1)
    affected_output_drill_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_applied_change(self) -> Self:
        """Require new content identity and one-to-one affected objects."""
        if self.input_sha256 == self.output_sha256:
            msg = "applied operation must change the source digest"
            raise ValueError(msg)
        if self.input_source_file_id == self.output_source_file_id:
            msg = "changed source bytes must receive a new source_file_id"
            raise ValueError(msg)
        if self.old_diameter_mm == self.new_diameter_mm:
            msg = "applied operation must change the tool diameter"
            raise ValueError(msg)
        if len(self.affected_input_drill_ids) != len(self.affected_output_drill_ids):
            msg = "affected input and output drills must correspond one-to-one"
            raise ValueError(msg)
        if len(self.affected_input_drill_ids) != len(
            set(self.affected_input_drill_ids)
        ) or len(self.affected_output_drill_ids) != len(
            set(self.affected_output_drill_ids)
        ):
            msg = "affected drill identifiers must be unique"
            raise ValueError(msg)
        span = self.input_value_span
        if span != self.output_value_span:
            msg = "same-width v1 patches must preserve the value source span"
            raise ValueError(msg)
        if (
            span.start_line is None
            or span.end_line is None
            or span.start_line != span.end_line
            or span.start_byte is None
            or span.end_byte is None
            or span.start_byte >= span.end_byte
        ):
            msg = "tool-diameter evidence requires one non-empty source token span"
            raise ValueError(msg)
        return self


class RevisionValidationEvidence(VersionedModel):
    """Identity and conclusion of the independent post-emission review."""

    review_artifact_directory: Literal["validation"] = "validation"
    project_id: str = Field(pattern=_PROJECT_ID_PATTERN)
    profile_id: str = Field(min_length=1)
    profile_sha256: str = Field(pattern=_SHA256_PATTERN)
    overall_status: ReviewStatus
    finding_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_completed_review(self) -> Self:
        """The initial revision contract never publishes failed analysis."""
        if self.overall_status is ReviewStatus.ANALYSIS_FAILED:
            msg = "revision validation must be a completed review"
            raise ValueError(msg)
        if len(self.finding_ids) != len(set(self.finding_ids)):
            msg = "validation finding_ids must be unique"
            raise ValueError(msg)
        if any(
            re.fullmatch(_FINDING_ID_PATTERN, value) is None
            for value in self.finding_ids
        ):
            msg = "validation finding_ids must be stable BoardGate IDs"
            raise ValueError(msg)
        if self.finding_ids != tuple(sorted(self.finding_ids)):
            msg = "validation finding_ids must be sorted"
            raise ValueError(msg)
        return self


class ModificationResult(VersionedModel):
    """Deterministic evidence binding one request, revision, and fresh review."""

    revision_id: str = Field(pattern=_REVISION_ID_PATTERN)
    base_project_id: str = Field(pattern=_PROJECT_ID_PATTERN)
    output_project_id: str = Field(pattern=_PROJECT_ID_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    operation_sha256: str = Field(pattern=_SHA256_PATTERN)
    implementation_version: str = Field(min_length=1)
    operation: AppliedExcellonToolDiameterChange
    payload_files: tuple[PayloadFileEvidence, ...] = Field(min_length=1)
    validation: RevisionValidationEvidence
    disclaimer: str = Field(
        default=MODIFICATION_DISCLAIMER,
        min_length=1,
        max_length=500,
    )

    @field_validator("disclaimer")
    @classmethod
    def require_normative_disclaimer(cls, value: str) -> str:
        """Prevent revision evidence from claiming fabrication guarantees."""
        if value != MODIFICATION_DISCLAIMER:
            msg = "disclaimer must use the normative non-guarantee text"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_revision_evidence(self) -> Self:
        """Cross-check project, target, and inventory identities."""
        if self.base_project_id == self.output_project_id:
            msg = "a modification revision must receive a new project_id"
            raise ValueError(msg)
        if self.validation.project_id != self.output_project_id:
            msg = "validation project_id must match output_project_id"
            raise ValueError(msg)
        paths = [item.logical_path for item in self.payload_files]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            msg = "payload_files must be unique and sorted by logical_path"
            raise ValueError(msg)
        changed = [item for item in self.payload_files if item.changed]
        if len(changed) != 1:
            msg = "the v1 modification result requires exactly one changed file"
            raise ValueError(msg)
        target = changed[0]
        operation = self.operation
        if target.logical_path != operation.source_logical_path:
            msg = "changed payload path must match the operation target"
            raise ValueError(msg)
        if (
            target.before_sha256 != operation.input_sha256
            or target.after_sha256 != operation.output_sha256
        ):
            msg = "changed payload digests must match operation evidence"
            raise ValueError(msg)
        return self
