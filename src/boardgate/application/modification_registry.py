"""Complete registry of bounded deterministic modification executors."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from boardgate.application.parser_runner import (
    ParserExecution,
    ParserJob,
    run_parser,
)
from boardgate.authoring.excellon import (
    AuthoringOperationError,
    prepare_excellon_tool_diameter_patch,
    verify_excellon_tool_diameter_patch,
)
from boardgate.authoring.gerber import (
    prepare_gerber_aperture_diameter_patch,
    verify_gerber_aperture_diameter_patch,
)
from boardgate.authoring.models import (
    MODIFICATION_OPERATION_KEYS,
    AppliedExcellonToolDiameterChange,
    AppliedGerberStandardApertureDiameterChange,
    ModificationOperation,
    SetExcellonToolDiameter,
    SetGerberStandardApertureDiameter,
)
from boardgate.domain.enums import FileType
from boardgate.domain.source import SourceFile
from boardgate.parsers.excellon import ExcellonParseResult
from boardgate.parsers.gerber import GerberParseResult

type ParserExecutor = Callable[[ParserJob], ParserExecution]
type AppliedModification = (
    AppliedExcellonToolDiameterChange | AppliedGerberStandardApertureDiameterChange
)


class OperationRegistryError(ValueError):
    """Typed incomplete or unknown deterministic executor registration."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class OperationExecutionError(ValueError):
    """Typed parser or semantic-postcondition executor failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


@dataclass(frozen=True, slots=True)
class ExecutedModification:
    """One emitted payload whose semantic delta has been independently proved."""

    payload: bytes
    output_source_file_id: str
    output_sha256: str
    applied: AppliedModification


class ModificationExecutor(Protocol):
    """Application boundary for one versioned deterministic operation."""

    @property
    def kind(self) -> str:
        """Return the exact admitted operation kind."""
        ...

    @property
    def operation_version(self) -> str:
        """Return the exact admitted operation contract version."""
        ...

    @property
    def file_type(self) -> FileType:
        """Return the required confirmed target-source classification."""
        ...

    def execute(
        self,
        source: SourceFile,
        payload: bytes,
        operation: ModificationOperation,
        *,
        parser_executor: ParserExecutor,
    ) -> ExecutedModification:
        """Emit and semantically verify one changed source payload."""
        ...


def _parse_excellon(
    source: SourceFile,
    payload: bytes,
    *,
    parser_executor: ParserExecutor,
) -> ExcellonParseResult:
    execution = parser_executor(
        ParserJob(
            source_file_id=source.source_file_id,
            logical_path=source.logical_path,
            file_type=source.file_type,
            payload=payload,
        )
    )
    if execution.failure is not None:
        raise OperationExecutionError(
            "MODIFICATION_SOURCE_PARSE_FAILED",
            source.logical_path,
            f"source parser did not complete ({execution.failure.code})",
        )
    result = execution.result
    if not isinstance(result, ExcellonParseResult):
        raise OperationExecutionError(
            "MODIFICATION_SOURCE_PARSE_TYPE_MISMATCH",
            source.logical_path,
            "source parser did not return normalized Excellon evidence",
        )
    return result


@dataclass(frozen=True, slots=True)
class ExcellonToolDiameterExecutor:
    """Executor for one exact, same-width Excellon diameter-token change."""

    kind: str = "set_excellon_tool_diameter"
    operation_version: str = "1.0"
    file_type: FileType = FileType.EXCELLON

    def execute(
        self,
        source: SourceFile,
        payload: bytes,
        operation: ModificationOperation,
        *,
        parser_executor: ParserExecutor = run_parser,
    ) -> ExecutedModification:
        """Patch, reparse, and prove the exact requested semantic delta."""
        if not isinstance(operation, SetExcellonToolDiameter):
            raise OperationRegistryError(
                "MODIFICATION_EXECUTOR_TYPE_MISMATCH",
                "registered operation model does not match its executor",
            )
        before = _parse_excellon(
            source,
            payload,
            parser_executor=parser_executor,
        )
        candidate = prepare_excellon_tool_diameter_patch(
            payload,
            before,
            operation,
        )
        output_source = source.model_copy(
            update={
                "source_file_id": candidate.output_source_file_id,
                "sha256": candidate.output_sha256,
                "size_bytes": len(candidate.payload),
            }
        )
        after = _parse_excellon(
            output_source,
            candidate.payload,
            parser_executor=parser_executor,
        )
        try:
            applied = verify_excellon_tool_diameter_patch(
                before,
                after,
                operation,
                candidate,
            )
        except AuthoringOperationError as error:
            raise OperationExecutionError(
                error.code,
                error.subject,
                error.detail,
            ) from error
        return ExecutedModification(
            payload=candidate.payload,
            output_source_file_id=candidate.output_source_file_id,
            output_sha256=candidate.output_sha256,
            applied=applied,
        )


def _parse_gerber(
    source: SourceFile,
    payload: bytes,
    *,
    parser_executor: ParserExecutor,
) -> GerberParseResult:
    execution = parser_executor(
        ParserJob(
            source_file_id=source.source_file_id,
            logical_path=source.logical_path,
            file_type=source.file_type,
            payload=payload,
        )
    )
    if execution.failure is not None:
        raise OperationExecutionError(
            "MODIFICATION_SOURCE_PARSE_FAILED",
            source.logical_path,
            f"source parser did not complete ({execution.failure.code})",
        )
    result = execution.result
    if not isinstance(result, GerberParseResult):
        raise OperationExecutionError(
            "MODIFICATION_SOURCE_PARSE_TYPE_MISMATCH",
            source.logical_path,
            "source parser did not return normalized Gerber evidence",
        )
    return result


@dataclass(frozen=True, slots=True)
class GerberStandardApertureDiameterExecutor:
    """Executor for one exact, same-width Gerber diameter-token change."""

    kind: str = "set_gerber_standard_aperture_diameter"
    operation_version: str = "1.0"
    file_type: FileType = FileType.GERBER

    def execute(
        self,
        source: SourceFile,
        payload: bytes,
        operation: ModificationOperation,
        *,
        parser_executor: ParserExecutor = run_parser,
    ) -> ExecutedModification:
        """Patch, reparse, and prove the exact requested semantic delta."""
        if not isinstance(operation, SetGerberStandardApertureDiameter):
            raise OperationRegistryError(
                "MODIFICATION_EXECUTOR_TYPE_MISMATCH",
                "registered operation model does not match its executor",
            )
        before = _parse_gerber(
            source,
            payload,
            parser_executor=parser_executor,
        )
        candidate = prepare_gerber_aperture_diameter_patch(
            payload,
            before,
            operation,
        )
        output_source = source.model_copy(
            update={
                "source_file_id": candidate.output_source_file_id,
                "sha256": candidate.output_sha256,
                "size_bytes": len(candidate.payload),
            }
        )
        after = _parse_gerber(
            output_source,
            candidate.payload,
            parser_executor=parser_executor,
        )
        try:
            applied = verify_gerber_aperture_diameter_patch(
                before,
                after,
                operation,
                candidate,
            )
        except AuthoringOperationError as error:
            raise OperationExecutionError(
                error.code,
                error.subject,
                error.detail,
            ) from error
        return ExecutedModification(
            payload=candidate.payload,
            output_source_file_id=candidate.output_source_file_id,
            output_sha256=candidate.output_sha256,
            applied=applied,
        )


_EXECUTORS: Mapping[tuple[str, str], ModificationExecutor] = MappingProxyType(
    {
        ("set_excellon_tool_diameter", "1.0"): ExcellonToolDiameterExecutor(),
        ("set_gerber_standard_aperture_diameter", "1.0"): (
            GerberStandardApertureDiameterExecutor()
        ),
    }
)


def registered_operation_keys() -> frozenset[tuple[str, str]]:
    """Expose the complete immutable registry key set for contract tests."""
    return frozenset(_EXECUTORS)


def validate_operation_registry() -> None:
    """Require one matching executor for every operation admitted by the model."""
    if registered_operation_keys() != MODIFICATION_OPERATION_KEYS:
        raise OperationRegistryError(
            "MODIFICATION_REGISTRY_INCOMPLETE",
            "admitted operation models and registered executors differ",
        )
    for key, executor in _EXECUTORS.items():
        if key != (executor.kind, executor.operation_version):
            raise OperationRegistryError(
                "MODIFICATION_REGISTRY_KEY_MISMATCH",
                "executor metadata does not match its registry key",
            )


def resolve_operation_executor_key(
    kind: str,
    operation_version: str,
) -> ModificationExecutor:
    """Resolve an exact kind/version pair without fallback or version coercion."""
    executor = _EXECUTORS.get((kind, operation_version))
    if executor is None:
        raise OperationRegistryError(
            "MODIFICATION_OPERATION_UNREGISTERED",
            "no deterministic executor is registered for the operation version",
        )
    return executor


def resolve_operation_executor(
    operation: ModificationOperation,
) -> ModificationExecutor:
    """Resolve the executor for one schema-admitted operation."""
    return resolve_operation_executor_key(
        operation.kind,
        operation.operation_version,
    )


validate_operation_registry()
