"""Deterministic PCB generation and independent review validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from boardgate import __version__
from boardgate.application.artifacts import (
    COMPLETE_ARTIFACT_PATHS,
    validate_artifact_bundle,
)
from boardgate.application.generation_registry import (
    GenerationExecutorError,
    GenerationRegistryError,
    resolve_generation_executor,
    validate_generation_operation_evidence,
)
from boardgate.application.modification_registry import ParserExecutor
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
)
from boardgate.application.revision_workspace import (
    DESIGN_DIRECTORY,
    REQUEST_ARTIFACT,
    RESULT_ARTIFACT,
    VALIDATION_DIRECTORY,
    canonical_artifact,
    load_validation_bundle,
    logical_destination,
    parent_directories,
    workspace_inventory,
)
from boardgate.authoring.generation_models import (
    GENERATION_DISCLAIMER,
    GeneratedFileEvidence,
    GenerationRequest,
    GenerationResult,
)
from boardgate.authoring.identifiers import (
    generation_id,
    generation_operation_sha256,
    generation_request_sha256,
)
from boardgate.authoring.models import RevisionValidationEvidence
from boardgate.config.models import RuleProfile
from boardgate.domain.enums import ReviewStatus
from boardgate.domain.identifiers import project_id
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.rules.models import ReviewResult


class GenerationExecutionError(ValueError):
    """Typed capability, parser, generator, or validation failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


class GenerationPublicationError(ValueError):
    """Sanitized failure to atomically publish a complete revision."""

    def __init__(self, code: str, summary: str) -> None:
        self.code = code
        self.summary = summary
        super().__init__(f"{code}: {summary}")


@dataclass(frozen=True, slots=True)
class GenerationRun:
    """Published generation outcome returned to the CLI adapter."""

    generation_id: str
    output_project_id: str
    overall_status: ReviewStatus
    exit_code: ReviewExitCode
    output_path: Path


def validate_generation_workspace(root: Path) -> None:  # noqa: PLR0912
    """Validate exact revision inventory, hashes, identities, and nested review."""
    actual_files, actual_directories = workspace_inventory(root)
    if not {REQUEST_ARTIFACT, RESULT_ARTIFACT}.issubset(actual_files):
        raise ValueError("revision workspace is missing canonical evidence")
    request_path = root / REQUEST_ARTIFACT
    result_path = root / RESULT_ARTIFACT
    request = GenerationRequest.model_validate_json(
        request_path.read_text(encoding="utf-8")
    )
    result = GenerationResult.model_validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if request_path.read_text(encoding="utf-8") != canonical_artifact(request):
        raise ValueError("request artifact is not canonical")
    if result_path.read_text(encoding="utf-8") != canonical_artifact(result):
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
    if actual_files != expected_files or actual_directories != parent_directories(
        expected_files
    ):
        raise ValueError("revision workspace inventory is inconsistent")

    if generation_request_sha256(request) != result.request_sha256:
        raise ValueError("request digest does not match result evidence")
    if generation_operation_sha256(request.operation) != result.operation_sha256:
        raise ValueError("operation digest does not match result evidence")
    output_project_id = project_id(
        tuple((item.logical_path, item.sha256) for item in result.payload_files)
    )
    if output_project_id != result.output_project_id:
        raise ValueError("output project_id is inconsistent with payload evidence")
    if (
        generation_id(
            operation_digest=result.operation_sha256,
            output_project_id=result.output_project_id,
        )
        != result.generation_id
    ):
        raise ValueError("generation_id is inconsistent with canonical evidence")
    request_operation = request.operation
    result_operation = result.operation

    for item in result.payload_files:
        path = logical_destination(root / DESIGN_DIRECTORY, item.logical_path)
        payload = path.read_bytes()
        if len(payload) != item.size_bytes:
            raise ValueError("design payload size does not match result evidence")
        if hashlib.sha256(payload).hexdigest() != item.sha256:
            raise ValueError("design payload digest does not match result evidence")

    bundle = load_validation_bundle(root)
    validate_artifact_bundle(bundle)
    validation_manifest = ProjectManifest.model_validate_json(bundle.manifest_json)
    validation_project = PCBProject.model_validate_json(bundle.project_json)
    validation_review = ReviewResult.model_validate_json(bundle.findings_json)
    payload_inventory = tuple(
        (item.logical_path, item.sha256, item.size_bytes)
        for item in result.payload_files
    )
    manifest_inventory = tuple(
        (source.logical_path, source.sha256, source.size_bytes)
        for source in validation_manifest.source_files
    )
    if payload_inventory != manifest_inventory:
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
    validate_generation_operation_evidence(
        request_operation,
        result_operation,
        result.payload_files,
        validation_project,
    )


class GenerationService:
    """Create one deterministic revision and validate it through ReviewService."""

    def __init__(
        self,
        *,
        parser_executor: ParserExecutor = run_parser,
        review_service: ReviewService | None = None,
    ) -> None:
        self._parser_executor = parser_executor
        self._review_service = review_service or ReviewService()

    def generate(
        self,
        request: GenerationRequest,
        profile: RuleProfile,
        output_path: Path,
        *,
        overwrite: bool = False,
    ) -> GenerationRun:
        """Emit, reparse, independently review, and atomically publish a revision."""
        preflight_output(output_path, overwrite=overwrite)
        operation = request.operation
        try:
            executor = resolve_generation_executor(operation)
        except GenerationRegistryError as error:
            raise GenerationExecutionError(
                error.code,
                operation.kind,
                error.detail,
            ) from error
        try:
            execution = executor.execute(
                operation,
                parser_executor=self._parser_executor,
            )
        except GenerationExecutorError as error:
            raise GenerationExecutionError(
                error.code,
                error.subject,
                error.detail,
            ) from error
        except GenerationRegistryError as error:
            raise GenerationExecutionError(
                error.code,
                operation.kind,
                error.detail,
            ) from error

        try:
            with OutputTransaction(output_path, overwrite=overwrite) as transaction:
                staging = transaction.staging_directory
                design = staging / DESIGN_DIRECTORY
                for payload in execution.payloads:
                    target = logical_destination(design, payload.logical_path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload.payload)
                validation_directory = staging / VALIDATION_DIRECTORY
                try:
                    review_run = self._review_service.inspect(
                        (design,),
                        profile,
                        validation_directory,
                        fail_on=FailOn.BLOCKER,
                    )
                except ReviewPublicationError as error:
                    raise GenerationExecutionError(
                        "GENERATION_VALIDATION_FAILED",
                        operation.kind,
                        "independent review artifacts could not be published",
                    ) from error
                if review_run.exit_code in {
                    ReviewExitCode.PIPELINE,
                    ReviewExitCode.INTERNAL,
                }:
                    raise GenerationExecutionError(
                        "GENERATION_VALIDATION_FAILED",
                        operation.kind,
                        "independent review did not produce a trustworthy result",
                    )
                validation_bundle = load_validation_bundle(staging)
                validation_review = ReviewResult.model_validate_json(
                    validation_bundle.findings_json
                )
                validation_manifest = ProjectManifest.model_validate_json(
                    validation_bundle.manifest_json
                )
                payload_evidence = tuple(
                    GeneratedFileEvidence(
                        logical_path=payload.logical_path,
                        sha256=payload.sha256,
                        size_bytes=len(payload.payload),
                    )
                    for payload in sorted(
                        execution.payloads,
                        key=lambda item: item.logical_path,
                    )
                )
                request_digest = generation_request_sha256(request)
                operation_digest = generation_operation_sha256(operation)
                result = GenerationResult(
                    generation_id=generation_id(
                        operation_digest=operation_digest,
                        output_project_id=validation_manifest.project_id,
                    ),
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
                    disclaimer=GENERATION_DISCLAIMER,
                )
                request_artifact = staging / REQUEST_ARTIFACT
                result_artifact = staging / RESULT_ARTIFACT
                request_artifact.parent.mkdir(parents=True, exist_ok=True)
                request_artifact.write_text(
                    canonical_artifact(request),
                    encoding="utf-8",
                    newline="\n",
                )
                result_artifact.write_text(
                    canonical_artifact(result),
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
                    validator=validate_generation_workspace,
                )
        except GenerationExecutionError:
            raise
        except (OSError, OutputError, ValueError) as error:
            raise GenerationPublicationError(
                "GENERATION_PUBLICATION_FAILED",
                "The complete validated revision could not be published.",
            ) from error

        return GenerationRun(
            generation_id=result.generation_id,
            output_project_id=result.output_project_id,
            overall_status=result.validation.overall_status,
            exit_code=review_run.exit_code,
            output_path=output_path,
        )
