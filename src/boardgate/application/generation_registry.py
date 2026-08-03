"""Complete registry of bounded deterministic generation executors."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
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
    GENERATION_PAYLOAD_PATHS,
    NON_PLATED_DRILL_PATH,
    NPTH_GENERATION_PAYLOAD_PATHS,
    OUTLINE_PATH,
    PLATED_DRILL_PATH,
    TOP_COPPER_PATH,
    GeneratedPayload,
    GenerationOperationError,
    emit_coupon_payloads,
    emit_coupon_with_npth_payloads,
    verify_coupon_copper,
    verify_coupon_drills,
    verify_coupon_outline,
    verify_coupon_with_npth_copper,
    verify_coupon_with_npth_drills,
)
from boardgate.authoring.generation_models import (
    GENERATION_OPERATION_KEYS,
    AppliedGenerationOperation,
    AppliedTwoLayerCouponGeneration,
    AppliedTwoLayerCouponWithNpthGeneration,
    CouponHole,
    CouponNpthHole,
    GeneratedFileEvidence,
    GenerateTwoLayerCoupon,
    GenerateTwoLayerCouponWithNpth,
    GenerationOperation,
)
from boardgate.domain.enums import FileType, Plating
from boardgate.domain.identifiers import source_file_id
from boardgate.domain.project import PCBProject
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
    applied: AppliedGenerationOperation


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


@dataclass(frozen=True, slots=True)
class TwoLayerCouponWithNpthExecutor:
    """Executor for the bounded mixed plated/non-plated coupon generator."""

    kind: str = "generate_two_layer_coupon_with_npth"
    operation_version: str = "1.0"

    def execute(
        self,
        operation: GenerationOperation,
        *,
        parser_executor: ParserExecutor = run_parser,
    ) -> ExecutedGeneration:
        """Emit, reparse, and prove exact mixed-drill coupon semantics."""
        if not isinstance(operation, GenerateTwoLayerCouponWithNpth):
            raise GenerationRegistryError(
                "GENERATION_EXECUTOR_TYPE_MISMATCH",
                "registered operation model does not match its executor",
            )
        payloads = emit_coupon_with_npth_payloads(operation)
        by_path = {payload.logical_path: payload for payload in payloads}
        drill_ids: dict[Plating, tuple[str, ...]] = {}
        for logical_path, holes, plating in (
            (PLATED_DRILL_PATH, operation.plated_holes, Plating.PLATED),
            (
                NON_PLATED_DRILL_PATH,
                operation.non_plated_holes,
                Plating.NON_PLATED,
            ),
        ):
            drill_payload = by_path[logical_path]
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
                drill_ids[plating] = verify_coupon_with_npth_drills(
                    holes,
                    drill_result,
                    expected_source_file_id=drill_payload.source_file_id,
                    logical_path=logical_path,
                    expected_plating=plating,
                )
            except GenerationOperationError as error:
                raise GenerationExecutorError(
                    error.code,
                    error.subject,
                    error.detail,
                ) from error
        try:
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
                verify_coupon_with_npth_copper(
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
        applied = AppliedTwoLayerCouponWithNpthGeneration(
            kind="generate_two_layer_coupon_with_npth",
            operation_version="1.0",
            board_width_mm=operation.board_width_mm,
            board_height_mm=operation.board_height_mm,
            plated_hole_count=len(operation.plated_holes),
            plated_tool_count=len(
                {hole.drill_diameter_mm for hole in operation.plated_holes}
            ),
            non_plated_hole_count=len(operation.non_plated_holes),
            non_plated_tool_count=len(
                {hole.drill_diameter_mm for hole in operation.non_plated_holes}
            ),
            trace_count=len(operation.traces),
            plated_drill_ids=drill_ids[Plating.PLATED],
            non_plated_drill_ids=drill_ids[Plating.NON_PLATED],
        )
        return ExecutedGeneration(payloads=payloads, applied=applied)


_GENERATORS: Mapping[tuple[str, str], GenerationExecutor] = MappingProxyType(
    {
        ("generate_two_layer_coupon", "1.0"): TwoLayerCouponExecutor(),
        (
            "generate_two_layer_coupon_with_npth",
            "1.0",
        ): TwoLayerCouponWithNpthExecutor(),
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


def _validate_project_drill_population(  # noqa: PLR0913
    *,
    project: PCBProject,
    payload_files: tuple[GeneratedFileEvidence, ...],
    logical_path: str,
    expected_holes: Sequence[CouponHole | CouponNpthHole],
    expected_ids: tuple[str, ...],
    expected_plating: Plating,
) -> None:
    digests = {item.logical_path: item.sha256 for item in payload_files}
    digest = digests.get(logical_path)
    if digest is None:
        raise ValueError("generated drill payload is missing from result evidence")
    expected_source_id = source_file_id(logical_path, digest)
    drills = tuple(
        drill
        for drill in project.drills
        if drill.provenance.source_file_id == expected_source_id
    )
    if tuple(sorted(drill.drill_id for drill in drills)) != expected_ids:
        raise ValueError("generated drill IDs do not match validation project")
    expected_geometry = sorted(
        (
            hole.x_mm,
            hole.y_mm,
            hole.drill_diameter_mm,
        )
        for hole in expected_holes
    )
    actual_geometry = sorted(
        (drill.position.x, drill.position.y, drill.diameter_mm) for drill in drills
    )
    if len(actual_geometry) != len(expected_geometry) or any(
        not all(
            math.isclose(actual_value, expected_value, rel_tol=0.0, abs_tol=1e-9)
            for actual_value, expected_value in zip(actual, expected, strict=True)
        )
        for actual, expected in zip(actual_geometry, expected_geometry, strict=True)
    ):
        raise ValueError("generated drills do not match validation project")
    if any(drill.plating is not expected_plating for drill in drills):
        raise ValueError("generated drills lost explicit plating evidence")


def validate_generation_operation_evidence(
    request_operation: GenerationOperation,
    applied_operation: AppliedGenerationOperation,
    payload_files: tuple[GeneratedFileEvidence, ...],
    validation_project: PCBProject,
) -> None:
    """Dispatch exact persisted-evidence checks through the registered key."""
    resolve_generation_executor(request_operation)
    if isinstance(request_operation, GenerateTwoLayerCoupon):
        expected_payloads = emit_coupon_payloads(request_operation)
    else:
        expected_payloads = emit_coupon_with_npth_payloads(request_operation)
    expected_payload_evidence = tuple(
        GeneratedFileEvidence(
            logical_path=payload.logical_path,
            sha256=payload.sha256,
            size_bytes=len(payload.payload),
        )
        for payload in sorted(expected_payloads, key=lambda item: item.logical_path)
    )
    if payload_files != expected_payload_evidence:
        raise ValueError(
            "request operation does not match deterministic design payload evidence"
        )
    if validation_project.drill_slots:
        raise ValueError("generated coupon validation project contains drill slots")
    payload_paths = tuple(item.logical_path for item in payload_files)
    if isinstance(request_operation, GenerateTwoLayerCoupon):
        if not isinstance(applied_operation, AppliedTwoLayerCouponGeneration):
            raise ValueError("request and applied generation operation types differ")
        if payload_paths != GENERATION_PAYLOAD_PATHS:
            raise ValueError("legacy coupon payload inventory is inconsistent")
        if (
            request_operation.board_width_mm != applied_operation.board_width_mm
            or request_operation.board_height_mm != applied_operation.board_height_mm
            or len(request_operation.holes) != applied_operation.hole_count
            or len({hole.drill_diameter_mm for hole in request_operation.holes})
            != applied_operation.tool_count
            or len(request_operation.traces) != applied_operation.trace_count
        ):
            raise ValueError(
                "request operation does not match applied generation evidence"
            )
        _validate_project_drill_population(
            project=validation_project,
            payload_files=payload_files,
            logical_path=PLATED_DRILL_PATH,
            expected_holes=request_operation.holes,
            expected_ids=applied_operation.drill_ids,
            expected_plating=Plating.PLATED,
        )
        return
    if not isinstance(
        applied_operation,
        AppliedTwoLayerCouponWithNpthGeneration,
    ):
        raise ValueError("request and applied generation operation types differ")
    if payload_paths != NPTH_GENERATION_PAYLOAD_PATHS:
        raise ValueError("mixed coupon payload inventory is inconsistent")
    if (
        request_operation.board_width_mm != applied_operation.board_width_mm
        or request_operation.board_height_mm != applied_operation.board_height_mm
        or len(request_operation.plated_holes) != applied_operation.plated_hole_count
        or len({hole.drill_diameter_mm for hole in request_operation.plated_holes})
        != applied_operation.plated_tool_count
        or len(request_operation.non_plated_holes)
        != applied_operation.non_plated_hole_count
        or len({hole.drill_diameter_mm for hole in request_operation.non_plated_holes})
        != applied_operation.non_plated_tool_count
        or len(request_operation.traces) != applied_operation.trace_count
    ):
        raise ValueError("request operation does not match applied generation evidence")
    _validate_project_drill_population(
        project=validation_project,
        payload_files=payload_files,
        logical_path=PLATED_DRILL_PATH,
        expected_holes=request_operation.plated_holes,
        expected_ids=applied_operation.plated_drill_ids,
        expected_plating=Plating.PLATED,
    )
    _validate_project_drill_population(
        project=validation_project,
        payload_files=payload_files,
        logical_path=NON_PLATED_DRILL_PATH,
        expected_holes=request_operation.non_plated_holes,
        expected_ids=applied_operation.non_plated_drill_ids,
        expected_plating=Plating.NON_PLATED,
    )
    if len(validation_project.drills) != (
        applied_operation.plated_hole_count + applied_operation.non_plated_hole_count
    ):
        raise ValueError("validation project contains unexpected drill hits")


validate_generation_registry()
