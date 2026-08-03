"""Deterministic PCB modification and independent review validation."""

from __future__ import annotations

import hashlib
import math
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath

from boardgate import __version__
from boardgate.application.artifacts import (
    COMPLETE_ARTIFACT_PATHS,
    CompleteArtifactBundle,
    validate_artifact_bundle,
)
from boardgate.application.modification_registry import (
    OperationExecutionError,
    OperationRegistryError,
    ParserExecutor,
    resolve_operation_executor,
)
from boardgate.application.output import (
    OutputError,
    OutputTransaction,
    preflight_output,
)
from boardgate.application.parser_runner import run_parser
from boardgate.application.review_service import (
    FailOn,
    ReviewExitCode,
    ReviewPublicationError,
    ReviewService,
    reject_output_input_overlap,
)
from boardgate.authoring.excellon import (
    AuthoringOperationError,
    scan_excellon_tool_definitions,
)
from boardgate.authoring.identifiers import (
    operation_sha256,
    request_sha256,
    revision_id,
)
from boardgate.authoring.models import (
    MODIFICATION_DISCLAIMER,
    ModificationRequest,
    ModificationResult,
    PayloadFileEvidence,
    RevisionValidationEvidence,
)
from boardgate.config.models import RuleProfile
from boardgate.domain.enums import FileType, ReviewStatus
from boardgate.domain.identifiers import project_id, source_file_id
from boardgate.domain.project import PCBProject
from boardgate.domain.serialization import canonical_json
from boardgate.domain.source import ProjectManifest, SourceFile
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.ingestion.discovery import DiscoveredFile, DiscoveredProject
from boardgate.rules.models import ReviewResult

DESIGN_DIRECTORY = "design"
REQUEST_ARTIFACT = "evidence/request.json"
RESULT_ARTIFACT = "evidence/result.json"
VALIDATION_DIRECTORY = "validation"

_AUTHORING_PAYLOAD_FILE_TYPES = frozenset(
    {
        FileType.GERBER,
        FileType.EXCELLON,
        FileType.BOM_CSV,
        FileType.BOM_XLSX,
        FileType.PLACEMENT_CSV,
    }
)
_INPUT_OPERATION_ERROR_CODES = frozenset(
    {
        "AUTHORING_EXCELLON_NEW_DIAMETER_PRECISION",
        "AUTHORING_EXCELLON_NEW_DIAMETER_WIDTH",
        "AUTHORING_EXCELLON_TOOL_AMBIGUOUS",
        "AUTHORING_EXCELLON_TOOL_DUPLICATE",
        "AUTHORING_EXCELLON_TOOL_NOT_FOUND",
        "AUTHORING_EXCELLON_TOOL_UNUSED",
        "AUTHORING_PRECONDITION_MISMATCH",
        "AUTHORING_SOURCE_ID_MISMATCH",
        "AUTHORING_SOURCE_SHA_MISMATCH",
    }
)


class ModificationInputError(ValueError):
    """Typed stale, ambiguous, or invalid modification input."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


class ModificationExecutionError(ValueError):
    """Typed capability, parser, operation, or validation failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


class ModificationPublicationError(ValueError):
    """Sanitized failure to atomically publish a complete revision."""

    def __init__(self, code: str, summary: str) -> None:
        self.code = code
        self.summary = summary
        super().__init__(f"{code}: {summary}")


@dataclass(frozen=True, slots=True)
class ModificationRun:
    """Published modification outcome returned to the CLI adapter."""

    revision_id: str
    base_project_id: str
    output_project_id: str
    overall_status: ReviewStatus
    exit_code: ReviewExitCode
    output_path: Path


def _logical_destination(root: Path, logical_path: str) -> Path:
    return root.joinpath(*PurePosixPath(logical_path).parts)


def _source_by_path(manifest: ProjectManifest, logical_path: str) -> SourceFile:
    matches = tuple(
        source
        for source in manifest.source_files
        if source.logical_path == logical_path
    )
    if len(matches) != 1:
        raise ModificationInputError(
            "MODIFICATION_TARGET_NOT_FOUND",
            logical_path,
            "request target must match exactly one safely ingested source",
        )
    return matches[0]


def _discovered_by_path(
    discovered: DiscoveredProject,
    logical_path: str,
) -> DiscoveredFile:
    matches = tuple(
        item for item in discovered.files if item.logical_path == logical_path
    )
    if len(matches) != 1:  # pragma: no cover - manifest/discovery invariant
        raise ModificationInputError(
            "MODIFICATION_TARGET_NOT_FOUND",
            logical_path,
            "request target must match exactly one staged source",
        )
    return matches[0]


def _copy_design(
    discovered: DiscoveredProject,
    destination: Path,
    *,
    changed_path: str,
    changed_payload: bytes,
) -> None:
    for item in discovered.files:
        target = _logical_destination(destination, item.logical_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.logical_path == changed_path:
            target.write_bytes(changed_payload)
        else:
            shutil.copyfile(item.staged_path, target)


def _load_validation_bundle(root: Path) -> CompleteArtifactBundle:
    files: dict[str, str] = {}
    for logical_path in COMPLETE_ARTIFACT_PATHS:
        path = root / VALIDATION_DIRECTORY / logical_path
        files[logical_path] = path.read_text(encoding="utf-8")
    return CompleteArtifactBundle.from_files(files)


def _canonical_artifact(model: ModificationRequest | ModificationResult) -> str:
    return f"{canonical_json(model)}\n"


def _workspace_inventory(root: Path) -> tuple[set[str], set[str]]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("revision workspace root must be a regular directory")
    files: set[str] = set()
    directories: set[str] = set()
    for path in root.rglob("*"):
        logical_path = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise ValueError("revision workspace must not contain symbolic links")
        if path.is_file():
            files.add(logical_path)
        elif path.is_dir():
            directories.add(logical_path)
        else:
            raise ValueError("revision workspace contains a non-regular node")
    return files, directories


def _parent_directories(logical_paths: set[str]) -> set[str]:
    return {
        parent.as_posix()
        for logical_path in logical_paths
        for parent in PurePosixPath(logical_path).parents
        if parent.as_posix() != "."
    }


def validate_modification_workspace(root: Path) -> None:  # noqa: PLR0912, PLR0915
    """Validate exact revision inventory, hashes, identities, and nested review."""
    actual_files, actual_directories = _workspace_inventory(root)
    if not {REQUEST_ARTIFACT, RESULT_ARTIFACT}.issubset(actual_files):
        raise ValueError("revision workspace is missing canonical evidence")
    request_path = root / REQUEST_ARTIFACT
    result_path = root / RESULT_ARTIFACT
    request = ModificationRequest.model_validate_json(
        request_path.read_text(encoding="utf-8")
    )
    result = ModificationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if request_path.read_text(encoding="utf-8") != _canonical_artifact(request):
        raise ValueError("request artifact is not canonical")
    if result_path.read_text(encoding="utf-8") != _canonical_artifact(result):
        raise ValueError("result artifact is not canonical")

    expected_files = {
        REQUEST_ARTIFACT,
        RESULT_ARTIFACT,
        *(f"{DESIGN_DIRECTORY}/{item.logical_path}" for item in result.payload_files),
        *(
            f"{VALIDATION_DIRECTORY}/{logical_path}"
            for logical_path in COMPLETE_ARTIFACT_PATHS
        ),
    }
    if actual_files != expected_files or actual_directories != _parent_directories(
        expected_files
    ):
        raise ValueError("revision workspace inventory is inconsistent")

    if request_sha256(request) != result.request_sha256:
        raise ValueError("request digest does not match result evidence")
    if operation_sha256(request.operation) != result.operation_sha256:
        raise ValueError("operation digest does not match result evidence")
    if request.base_project_id != result.base_project_id:
        raise ValueError("request base project does not match result evidence")
    before_project_id = project_id(
        tuple((item.logical_path, item.before_sha256) for item in result.payload_files)
    )
    after_project_id = project_id(
        tuple((item.logical_path, item.after_sha256) for item in result.payload_files)
    )
    if before_project_id != result.base_project_id:
        raise ValueError("base project_id is inconsistent with payload evidence")
    if after_project_id != result.output_project_id:
        raise ValueError("output project_id is inconsistent with payload evidence")
    request_operation = request.operation
    result_operation = result.operation
    if (
        request_operation.source_logical_path != result_operation.source_logical_path
        or request_operation.source_file_id != result_operation.input_source_file_id
        or request_operation.source_sha256 != result_operation.input_sha256
        or request_operation.tool_code != result_operation.tool_code
        or request_operation.expected_diameter_mm != result_operation.old_diameter_mm
        or request_operation.new_diameter_mm != result_operation.new_diameter_mm
    ):
        raise ValueError("request operation does not match applied operation evidence")
    if (
        source_file_id(
            result_operation.source_logical_path,
            result_operation.input_sha256,
        )
        != result_operation.input_source_file_id
    ):
        raise ValueError("input source_file_id is inconsistent with operation evidence")
    if (
        source_file_id(
            result_operation.source_logical_path,
            result_operation.output_sha256,
        )
        != result_operation.output_source_file_id
    ):
        raise ValueError(
            "output source_file_id is inconsistent with operation evidence"
        )
    if (
        revision_id(
            base_project_id=result.base_project_id,
            operation_digest=result.operation_sha256,
            output_project_id=result.output_project_id,
        )
        != result.revision_id
    ):
        raise ValueError("revision_id is inconsistent with canonical evidence")

    for item in result.payload_files:
        path = _logical_destination(root / DESIGN_DIRECTORY, item.logical_path)
        payload = path.read_bytes()
        if len(payload) != item.after_size_bytes:
            raise ValueError("design payload size does not match result evidence")
        if hashlib.sha256(payload).hexdigest() != item.after_sha256:
            raise ValueError("design payload digest does not match result evidence")
        if item.logical_path == result_operation.source_logical_path:
            witnesses = tuple(
                witness
                for witness in scan_excellon_tool_definitions(
                    payload,
                    subject="<design-source>",
                )
                if witness.tool_code == result_operation.tool_code
            )
            if (
                len(witnesses) != 1
                or witnesses[0].value_span != result_operation.output_value_span
                or witnesses[0].diameter_mm
                != Decimal(str(result_operation.new_diameter_mm))
            ):
                raise ValueError(
                    "operation token evidence does not match the design payload"
                )

    bundle = _load_validation_bundle(root)
    validate_artifact_bundle(bundle)
    validation_manifest = ProjectManifest.model_validate_json(bundle.manifest_json)
    validation_project = PCBProject.model_validate_json(bundle.project_json)
    validation_review = ReviewResult.model_validate_json(bundle.findings_json)
    after_inventory = tuple(
        (item.logical_path, item.after_sha256, item.after_size_bytes)
        for item in result.payload_files
    )
    manifest_inventory = tuple(
        (source.logical_path, source.sha256, source.size_bytes)
        for source in validation_manifest.source_files
    )
    if after_inventory != manifest_inventory:
        raise ValueError("design payload evidence does not match validation manifest")
    expected_validation = RevisionValidationEvidence(
        project_id=validation_review.project_id,
        profile_id=validation_review.profile_id,
        profile_sha256=validation_review.profile_sha256,
        overall_status=validation_review.overall_status,
        finding_ids=tuple(
            sorted(finding.finding_id for finding in validation_review.findings)
        ),
    )
    if result.validation != expected_validation:
        raise ValueError("result validation evidence does not match nested review")
    if validation_manifest.project_id != result.output_project_id:
        raise ValueError("nested review project does not match output_project_id")
    target_sources = tuple(
        source
        for source in validation_manifest.source_files
        if source.logical_path == result_operation.source_logical_path
    )
    if (
        len(target_sources) != 1
        or target_sources[0].source_file_id != result_operation.output_source_file_id
    ):
        raise ValueError("operation output source does not match validation manifest")
    output_target_drills = tuple(
        drill
        for drill in validation_project.drills
        if drill.provenance.source_file_id == result_operation.output_source_file_id
        and drill.tool_code == result_operation.tool_code
    )
    if tuple(sorted(drill.drill_id for drill in output_target_drills)) != tuple(
        sorted(result_operation.affected_output_drill_ids)
    ) or any(
        not math.isclose(
            drill.diameter_mm,
            result_operation.new_diameter_mm,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for drill in output_target_drills
    ):
        raise ValueError("operation output drills do not match validation project")


class ModificationService:
    """Create one deterministic revision and validate it through ReviewService."""

    def __init__(
        self,
        *,
        parser_executor: ParserExecutor = run_parser,
        review_service: ReviewService | None = None,
    ) -> None:
        self._parser_executor = parser_executor
        self._review_service = review_service or ReviewService()

    def modify(  # noqa: PLR0912, PLR0915
        self,
        inputs: Sequence[Path],
        request: ModificationRequest,
        profile: RuleProfile,
        output_path: Path,
        *,
        overwrite: bool = False,
    ) -> ModificationRun:
        """Apply, reparse, independently review, and atomically publish a revision."""
        preflight_output(output_path, overwrite=overwrite)
        reject_output_input_overlap(inputs, output_path)
        with discover_inputs(inputs) as discovered:
            manifest = build_manifest(discovered)
            if manifest.project_id != request.base_project_id:
                raise ModificationInputError(
                    "MODIFICATION_BASE_PROJECT_MISMATCH",
                    manifest.project_id,
                    "safely ingested project does not match base_project_id",
                )
            non_design_sources = tuple(
                source
                for source in manifest.source_files
                if source.file_type not in _AUTHORING_PAYLOAD_FILE_TYPES
            )
            if non_design_sources:
                raise ModificationInputError(
                    "MODIFICATION_NON_DESIGN_INPUT",
                    non_design_sources[0].logical_path,
                    "v1 authoring inputs may contain only confirmed design payloads",
                )
            operation = request.operation
            source = _source_by_path(manifest, operation.source_logical_path)
            if (
                source.source_file_id != operation.source_file_id
                or source.sha256 != operation.source_sha256
            ):
                raise ModificationInputError(
                    "MODIFICATION_SOURCE_IDENTITY_MISMATCH",
                    operation.source_logical_path,
                    "target source identity or digest is stale",
                )
            try:
                executor = resolve_operation_executor(operation)
            except OperationRegistryError as error:
                raise ModificationExecutionError(
                    error.code,
                    operation.source_logical_path,
                    error.detail,
                ) from error
            if source.file_type is not executor.file_type:
                raise ModificationInputError(
                    "AUTHORING_TARGET_TYPE_MISMATCH",
                    source.logical_path,
                    f"{operation.kind} requires a confirmed "
                    f"{executor.file_type.value} source",
                )
            staged_source = _discovered_by_path(discovered, source.logical_path)
            try:
                original_payload = staged_source.staged_path.read_bytes()
            except OSError as error:
                raise ModificationExecutionError(
                    "MODIFICATION_SOURCE_READ_FAILED",
                    source.logical_path,
                    "safely staged target source could not be read",
                ) from error
            try:
                execution = executor.execute(
                    source,
                    original_payload,
                    operation,
                    parser_executor=self._parser_executor,
                )
            except AuthoringOperationError as error:
                if error.code in _INPUT_OPERATION_ERROR_CODES:
                    raise ModificationInputError(
                        error.code,
                        error.subject,
                        error.detail,
                    ) from error
                raise ModificationExecutionError(
                    error.code,
                    error.subject,
                    error.detail,
                ) from error
            except OperationExecutionError as error:
                raise ModificationExecutionError(
                    error.code,
                    error.subject,
                    error.detail,
                ) from error
            except OperationRegistryError as error:
                raise ModificationExecutionError(
                    error.code,
                    operation.source_logical_path,
                    error.detail,
                ) from error

            try:
                with OutputTransaction(output_path, overwrite=overwrite) as transaction:
                    staging = transaction.staging_directory
                    design = staging / DESIGN_DIRECTORY
                    _copy_design(
                        discovered,
                        design,
                        changed_path=source.logical_path,
                        changed_payload=execution.payload,
                    )
                    validation_directory = staging / VALIDATION_DIRECTORY
                    try:
                        review_run = self._review_service.inspect(
                            (design,),
                            profile,
                            validation_directory,
                            fail_on=FailOn.BLOCKER,
                        )
                    except ReviewPublicationError as error:
                        raise ModificationExecutionError(
                            "MODIFICATION_VALIDATION_FAILED",
                            source.logical_path,
                            "independent review artifacts could not be published",
                        ) from error
                    if review_run.exit_code in {
                        ReviewExitCode.PIPELINE,
                        ReviewExitCode.INTERNAL,
                    }:
                        raise ModificationExecutionError(
                            "MODIFICATION_VALIDATION_FAILED",
                            source.logical_path,
                            "independent review did not produce a trustworthy result",
                        )
                    validation_bundle = _load_validation_bundle(staging)
                    validation_review = ReviewResult.model_validate_json(
                        validation_bundle.findings_json
                    )
                    validation_manifest = ProjectManifest.model_validate_json(
                        validation_bundle.manifest_json
                    )
                    output_sources = {
                        item.logical_path: item
                        for item in validation_manifest.source_files
                    }
                    payload_evidence = tuple(
                        PayloadFileEvidence(
                            logical_path=item.logical_path,
                            before_sha256=manifest_source.sha256,
                            after_sha256=output_sources[item.logical_path].sha256,
                            before_size_bytes=manifest_source.size_bytes,
                            after_size_bytes=output_sources[
                                item.logical_path
                            ].size_bytes,
                            changed=(item.logical_path == source.logical_path),
                        )
                        for item, manifest_source in (
                            (
                                discovered_item,
                                _source_by_path(
                                    manifest,
                                    discovered_item.logical_path,
                                ),
                            )
                            for discovered_item in discovered.files
                        )
                    )
                    request_digest = request_sha256(request)
                    operation_digest = operation_sha256(operation)
                    result = ModificationResult(
                        revision_id=revision_id(
                            base_project_id=manifest.project_id,
                            operation_digest=operation_digest,
                            output_project_id=validation_manifest.project_id,
                        ),
                        base_project_id=manifest.project_id,
                        output_project_id=validation_manifest.project_id,
                        request_sha256=request_digest,
                        operation_sha256=operation_digest,
                        implementation_version=__version__,
                        operation=execution.applied,
                        payload_files=payload_evidence,
                        validation=RevisionValidationEvidence(
                            project_id=validation_review.project_id,
                            profile_id=validation_review.profile_id,
                            profile_sha256=validation_review.profile_sha256,
                            overall_status=validation_review.overall_status,
                            finding_ids=tuple(
                                sorted(
                                    finding.finding_id
                                    for finding in validation_review.findings
                                )
                            ),
                        ),
                        disclaimer=MODIFICATION_DISCLAIMER,
                    )
                    request_artifact = staging / REQUEST_ARTIFACT
                    result_artifact = staging / RESULT_ARTIFACT
                    request_artifact.parent.mkdir(parents=True, exist_ok=True)
                    request_artifact.write_text(
                        _canonical_artifact(request),
                        encoding="utf-8",
                        newline="\n",
                    )
                    result_artifact.write_text(
                        _canonical_artifact(result),
                        encoding="utf-8",
                        newline="\n",
                    )
                    required_files = (
                        REQUEST_ARTIFACT,
                        RESULT_ARTIFACT,
                        *(
                            f"{DESIGN_DIRECTORY}/{item.logical_path}"
                            for item in payload_evidence
                        ),
                        *(
                            f"{VALIDATION_DIRECTORY}/{logical_path}"
                            for logical_path in COMPLETE_ARTIFACT_PATHS
                        ),
                    )
                    transaction.commit(
                        required_files=required_files,
                        validator=validate_modification_workspace,
                    )
            except ModificationExecutionError:
                raise
            except (OSError, OutputError, ValueError) as error:
                raise ModificationPublicationError(
                    "MODIFICATION_PUBLICATION_FAILED",
                    "The complete validated revision could not be published.",
                ) from error

            return ModificationRun(
                revision_id=result.revision_id,
                base_project_id=result.base_project_id,
                output_project_id=result.output_project_id,
                overall_status=result.validation.overall_status,
                exit_code=review_run.exit_code,
                output_path=output_path,
            )
