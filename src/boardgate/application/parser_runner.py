"""Spawn-isolated execution for untrusted third-party parser work."""

from __future__ import annotations

import math
import multiprocessing
from dataclasses import dataclass
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess

from pydantic import Field, model_validator

from boardgate.domain.base import StrictModel, VersionedModel
from boardgate.domain.enums import FileType
from boardgate.domain.serialization import canonical_json
from boardgate.parsers import (
    BOMParseResult,
    ExcellonParseResult,
    GerberParseResult,
    ParserError,
    PlacementParseResult,
    parse_bom_csv,
    parse_bom_xlsx,
    parse_excellon,
    parse_gerber,
    parse_placement_csv,
)

_SUPPORTED_TYPES = frozenset(
    {
        FileType.GERBER,
        FileType.EXCELLON,
        FileType.BOM_CSV,
        FileType.BOM_XLSX,
        FileType.PLACEMENT_CSV,
    }
)
_MAX_SOURCE_BYTES = 50 * 1024 * 1024
_MAX_WORKER_MESSAGE_BYTES = 250 * 1024 * 1024
_CLEANUP_TIMEOUT_SECONDS = 1.0

type ParsedResult = (
    GerberParseResult | ExcellonParseResult | BOMParseResult | PlacementParseResult
)


class ParserJob(StrictModel):
    """Fully resolved parser input copied into one isolated worker."""

    source_file_id: str = Field(pattern=r"^src-[0-9a-f]{16}$")
    logical_path: str = Field(min_length=1)
    file_type: FileType
    payload: bytes = Field(max_length=_MAX_SOURCE_BYTES)

    @model_validator(mode="after")
    def require_supported_type(self) -> ParserJob:
        """Reject ambiguous or non-parser manifest types."""
        if self.file_type not in _SUPPORTED_TYPES:
            msg = f"no parser runner is registered for {self.file_type.value}"
            raise ValueError(msg)
        return self


class ParserFailure(VersionedModel):
    """Typed, source-safe failure from the isolated parser boundary."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    detail: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True, slots=True)
class ParserExecution:
    """Exactly one normalized result or typed failure."""

    file_type: FileType
    source_file_id: str
    result: ParsedResult | None = None
    failure: ParserFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("parser execution requires exactly one result or failure")


class _WorkerEnvelope(StrictModel):
    ok: bool
    result_json: str | None = None
    code: str | None = None
    detail: str | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> _WorkerEnvelope:
        if self.ok and (
            self.result_json is None or self.code is not None or self.detail is not None
        ):
            raise ValueError("successful worker envelope is inconsistent")
        if not self.ok and (
            self.result_json is not None or self.code is None or self.detail is None
        ):
            raise ValueError("failed worker envelope is inconsistent")
        return self


def parse_job(job: ParserJob) -> ParsedResult:
    """Run a resolved job in-process; worker isolation is applied by run_parser."""
    if job.file_type is FileType.GERBER:
        return parse_gerber(
            job.payload,
            logical_path=job.logical_path,
            source_file_id=job.source_file_id,
        )
    if job.file_type is FileType.EXCELLON:
        return parse_excellon(
            job.payload,
            logical_path=job.logical_path,
            source_file_id=job.source_file_id,
        )
    if job.file_type is FileType.BOM_CSV:
        return parse_bom_csv(
            job.payload,
            logical_path=job.logical_path,
            source_file_id=job.source_file_id,
        )
    if job.file_type is FileType.BOM_XLSX:
        return parse_bom_xlsx(
            job.payload,
            logical_path=job.logical_path,
            source_file_id=job.source_file_id,
        )
    if job.file_type is FileType.PLACEMENT_CSV:
        return parse_placement_csv(
            job.payload,
            logical_path=job.logical_path,
            source_file_id=job.source_file_id,
        )
    raise ParserError(
        "PARSER_TYPE_UNSUPPORTED",
        job.logical_path,
        "manifest file type has no registered parser",
    )


def _worker(send_connection: Connection, job: ParserJob) -> None:
    try:
        try:
            result = parse_job(job)
            envelope = _WorkerEnvelope(
                ok=True,
                result_json=canonical_json(result),
            )
        except ParserError as error:
            envelope = _WorkerEnvelope(
                ok=False,
                code=error.code,
                detail=error.detail[:500],
            )
        except BaseException as error:  # pragma: no cover - worker safety boundary
            envelope = _WorkerEnvelope(
                ok=False,
                code="PARSER_WORKER_EXCEPTION",
                detail=f"parser worker raised {type(error).__name__}",
            )
        message = envelope.model_dump_json().encode("utf-8")
        if len(message) > _MAX_WORKER_MESSAGE_BYTES:
            message = (
                _WorkerEnvelope(
                    ok=False,
                    code="PARSER_RESULT_SIZE_LIMIT",
                    detail="normalized parser result exceeds the worker message limit",
                )
                .model_dump_json()
                .encode("utf-8")
            )
        send_connection.send_bytes(message)
    except (OSError, ValueError):
        pass
    finally:
        send_connection.close()


def _failure(job: ParserJob, code: str, detail: str) -> ParserExecution:
    return ParserExecution(
        file_type=job.file_type,
        source_file_id=job.source_file_id,
        failure=ParserFailure(code=code, detail=detail),
    )


def _decode_result(job: ParserJob, message: bytes) -> ParserExecution:
    try:
        envelope = _WorkerEnvelope.model_validate_json(message)
    except ValueError:
        return _failure(
            job,
            "PARSER_PROTOCOL_ERROR",
            "parser worker returned an invalid response",
        )
    if not envelope.ok:
        return _failure(
            job,
            envelope.code or "PARSER_PROTOCOL_ERROR",
            envelope.detail or "parser worker returned an incomplete failure",
        )
    result_json = envelope.result_json
    if result_json is None:  # pragma: no cover - model invariant
        return _failure(
            job,
            "PARSER_PROTOCOL_ERROR",
            "parser worker omitted its normalized result",
        )
    try:
        if job.file_type is FileType.GERBER:
            result: ParsedResult = GerberParseResult.model_validate_json(result_json)
        elif job.file_type is FileType.EXCELLON:
            result = ExcellonParseResult.model_validate_json(result_json)
        elif job.file_type in {FileType.BOM_CSV, FileType.BOM_XLSX}:
            result = BOMParseResult.model_validate_json(result_json)
        else:
            result = PlacementParseResult.model_validate_json(result_json)
    except ValueError:
        return _failure(
            job,
            "PARSER_PROTOCOL_ERROR",
            "parser worker result failed BoardGate model validation",
        )
    if result.source_file_id != job.source_file_id:
        return _failure(
            job,
            "PARSER_SOURCE_MISMATCH",
            "parser worker result references a different source",
        )
    return ParserExecution(
        file_type=job.file_type,
        source_file_id=job.source_file_id,
        result=result,
    )


def _stop_process(process: BaseProcess) -> None:
    if process.is_alive():
        process.terminate()
        process.join(_CLEANUP_TIMEOUT_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(_CLEANUP_TIMEOUT_SECONDS)


def run_parser(
    job: ParserJob,
    *,
    timeout_seconds: float = 30.0,
) -> ParserExecution:
    """Execute one parser in a fresh spawned process with bounded cleanup."""
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0.0:
        raise ValueError("parser timeout must be a positive finite number")
    context = multiprocessing.get_context("spawn")
    receive_connection, send_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_worker,
        args=(send_connection, job),
        daemon=True,
    )
    try:
        try:
            process.start()
        except (OSError, RuntimeError):
            return _failure(
                job,
                "PARSER_PROCESS_START_FAILED",
                "isolated parser process could not be started",
            )
        finally:
            send_connection.close()
        if not receive_connection.poll(timeout_seconds):
            return _failure(
                job,
                "PARSER_TIMEOUT",
                f"parser exceeded the {timeout_seconds:g}-second limit",
            )
        try:
            message = receive_connection.recv_bytes(_MAX_WORKER_MESSAGE_BYTES)
        except EOFError:
            return _failure(
                job,
                "PARSER_PROCESS_CRASH",
                "parser process exited without a result",
            )
        except OSError:
            return _failure(
                job,
                "PARSER_RESULT_SIZE_LIMIT",
                "parser worker response exceeded the message limit",
            )
        return _decode_result(job, message)
    finally:
        receive_connection.close()
        _stop_process(process)
        process.close()
