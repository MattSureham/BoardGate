"""Complete registry of bounded deterministic generation executors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol

from boardgate.application.modification_registry import ParserExecutor
from boardgate.application.parser_runner import (
    ParsedResult,
    ParserJob,
    run_parser,
)
from boardgate.authoring.coupon import (
    BOTTOM_COPPER_PATH,
    OUTLINE_PATH,
    PLATED_DRILL_PATH,
    TOP_COPPER_PATH,
    GeneratedPayload,
    GenerationOperationError,
    emit_coupon_payloads,
    verify_coupon_copper,
    verify_coupon_drills,
    verify_coupon_outline,
)
from boardgate.authoring.generation_models import (
    GENERATION_OPERATION_KEYS,
    AppliedTwoLayerCouponGeneration,
    GenerateTwoLayerCoupon,
    GenerationOperation,
)
from boardgate.domain.enums import FileType
from boardgate.parsers.excellon import ExcellonParseResult
from boardgate.parsers.gerber import GerberParseResult


class GenerationRegistryError(ValueError):
    """Typed incomplete or unknown deterministic generator registration."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class GenerationExecutorError(ValueError):
    """Typed parser or semantic-postcondition generator failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


@dataclass(frozen=True, slots=True)
class ExecutedGeneration:
    """One emitted payload set whose semantics have been independently proved."""

    payloads: tuple[GeneratedPayload, ...]
    applied: AppliedTwoLayerCouponGeneration


class GenerationExecutor(Protocol):
    """Application boundary for one versioned deterministic generator."""

    @property
    def kind(self) -> str:
        """Return the exact admitted operation kind."""
        ...

    @property
    def operation_version(self) -> str:
        """Return the exact admitted operation contract version."""
        ...

    def execute(
        self,
        operation: GenerationOperation,
        *,
        parser_executor: ParserExecutor,
    ) -> ExecutedGeneration:
        """Emit and semantically verify one complete design payload set."""
        ...


def _parse_generated(
    payload: GeneratedPayload,
    file_type: FileType,
    *,
    parser_executor: ParserExecutor,
) -> ParsedResult | None:
    execution = parser_executor(
        ParserJob(
            source_file_id=payload.source_file_id,
            logical_path=payload.logical_path,
            file_type=file_type,
            payload=payload.payload,
        )
    )
    if execution.failure is not None:
        raise GenerationExecutorError(
            "GENERATION_REPARSE_FAILED",
            payload.logical_path,
            f"generated payload parser did not complete ({execution.failure.code})",
        )
    return execution.result


@dataclass(frozen=True, slots=True)
class TwoLayerCouponExecutor:
    """Executor for the bounded metric two-layer coupon generator."""

    kind: str = "generate_two_layer_coupon"
    operation_version: str = "1.0"

    def execute(
        self,
        operation: GenerationOperation,
        *,
        parser_executor: ParserExecutor = run_parser,
    ) -> ExecutedGeneration:
        """Emit, reparse, and prove the exact requested coupon semantics."""
        if not isinstance(operation, GenerateTwoLayerCoupon):
            raise GenerationRegistryError(
                "GENERATION_EXECUTOR_TYPE_MISMATCH",
                "registered operation model does not match its executor",
            )
        payloads = emit_coupon_payloads(operation)
        by_path = {payload.logical_path: payload for payload in payloads}
        drill_payload = by_path[PLATED_DRILL_PATH]
        drill_result = _parse_generated(
            drill_payload,
            FileType.EXCELLON,
            parser_executor=parser_executor,
        )
        if not isinstance(drill_result, ExcellonParseResult):
            raise GenerationExecutorError(
                "GENERATION_REPARSE_TYPE_MISMATCH",
                drill_payload.logical_path,
                "drill parser did not return normalized Excellon evidence",
            )
        try:
            drill_ids = verify_coupon_drills(
                operation,
                drill_result,
                expected_source_file_id=drill_payload.source_file_id,
            )
            outline_payload = by_path[OUTLINE_PATH]
            outline_result = _parse_generated(
                outline_payload,
                FileType.GERBER,
                parser_executor=parser_executor,
            )
            if not isinstance(outline_result, GerberParseResult):
                raise GenerationExecutorError(
                    "GENERATION_REPARSE_TYPE_MISMATCH",
                    outline_payload.logical_path,
                    "outline parser did not return normalized Gerber evidence",
                )
            verify_coupon_outline(
                operation,
                outline_result,
                expected_source_file_id=outline_payload.source_file_id,
            )
            for copper_path, layer in (
                (TOP_COPPER_PATH, "top"),
                (BOTTOM_COPPER_PATH, "bottom"),
            ):
                copper_payload = by_path[copper_path]
                copper_result = _parse_generated(
                    copper_payload,
                    FileType.GERBER,
                    parser_executor=parser_executor,
                )
                if not isinstance(copper_result, GerberParseResult):
                    raise GenerationExecutorError(
                        "GENERATION_REPARSE_TYPE_MISMATCH",
                        copper_payload.logical_path,
                        "copper parser did not return normalized Gerber evidence",
                    )
                verify_coupon_copper(
                    operation,
                    copper_result,
                    expected_source_file_id=copper_payload.source_file_id,
                    logical_path=copper_path,
                    layer=layer,
                )
        except GenerationOperationError as error:
            raise GenerationExecutorError(
                error.code,
                error.subject,
                error.detail,
            ) from error
        applied = AppliedTwoLayerCouponGeneration(
            board_width_mm=operation.board_width_mm,
            board_height_mm=operation.board_height_mm,
            hole_count=len(operation.holes),
            tool_count=len({hole.drill_diameter_mm for hole in operation.holes}),
            trace_count=len(operation.traces),
            drill_ids=drill_ids,
        )
        return ExecutedGeneration(payloads=payloads, applied=applied)


_GENERATORS: Mapping[tuple[str, str], GenerationExecutor] = MappingProxyType(
    {
        ("generate_two_layer_coupon", "1.0"): TwoLayerCouponExecutor(),
    }
)


def registered_generator_keys() -> frozenset[tuple[str, str]]:
    """Expose the complete immutable registry key set for contract tests."""
    return frozenset(_GENERATORS)


def validate_generation_registry() -> None:
    """Require one matching executor for every operation admitted by the model."""
    if registered_generator_keys() != GENERATION_OPERATION_KEYS:
        raise GenerationRegistryError(
            "GENERATION_REGISTRY_INCOMPLETE",
            "admitted operation models and registered executors differ",
        )
    for key, executor in _GENERATORS.items():
        if key != (executor.kind, executor.operation_version):
            raise GenerationRegistryError(
                "GENERATION_REGISTRY_KEY_MISMATCH",
                "executor metadata does not match its registry key",
            )


def resolve_generation_executor_key(
    kind: str,
    operation_version: str,
) -> GenerationExecutor:
    """Resolve an exact kind/version pair without fallback or version coercion."""
    executor = _GENERATORS.get((kind, operation_version))
    if executor is None:
        raise GenerationRegistryError(
            "GENERATION_OPERATION_UNREGISTERED",
            "no deterministic executor is registered for the operation version",
        )
    return executor


def resolve_generation_executor(
    operation: GenerationOperation,
) -> GenerationExecutor:
    """Resolve the executor for one schema-admitted operation."""
    return resolve_generation_executor_key(
        operation.kind,
        operation.operation_version,
    )


validate_generation_registry()
