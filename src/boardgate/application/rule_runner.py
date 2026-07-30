"""Spawn-isolated execution for the built-in deterministic rule stage."""

from __future__ import annotations

import math
import multiprocessing
import os
import stat
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Self

from pydantic import Field, model_validator

from boardgate.config.models import RuleId, RuleProfile, profile_hash
from boardgate.domain.base import StrictModel, VersionedModel
from boardgate.domain.project import PCBProject
from boardgate.domain.serialization import canonical_json
from boardgate.rules.builtin import build_builtin_registry
from boardgate.rules.engine import RuleEngine
from boardgate.rules.models import ReviewResult

_MAX_PROJECT_BYTES = 250 * 1024 * 1024
_MAX_PROFILE_BYTES = 1024 * 1024
_MAX_REQUEST_BYTES = 64 * 1024
_MAX_RESULT_BYTES = 250 * 1024 * 1024
_MAX_ENVELOPE_BYTES = 16 * 1024
_GRACEFUL_JOIN_SECONDS = 0.05
_CLEANUP_TIMEOUT_SECONDS = 1.0

type MonotonicClock = Callable[[], float]


class RuleFailure(VersionedModel):
    """Typed, source-safe failure returned by the rule-process boundary."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]+$")
    detail: str = Field(min_length=1, max_length=500)


class _FileSizeLimitError(ValueError):
    """Private signal distinguishing a budget breach from malformed content."""


@dataclass(frozen=True, slots=True)
class RuleExecution:
    """Exactly one validated review result or typed worker failure."""

    result: ReviewResult | None = None
    failure: RuleFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("rule execution requires exactly one result or failure")


class _WorkerRequest(VersionedModel):
    """Small canonical request stored beside the two public BoardGate models."""

    selected_rule_ids: tuple[RuleId, ...] | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if self.selected_rule_ids is None:
            return self
        expected = tuple(sorted(set(self.selected_rule_ids), key=str))
        if self.selected_rule_ids != expected:
            raise ValueError("selected rule identifiers must be unique and sorted")
        return self


@dataclass(frozen=True, slots=True)
class _WorkerPaths:
    project: str
    profile: str
    request: str
    result: str


class _WorkerEnvelope(StrictModel):
    """Bounded pipe response; the potentially large result stays in a file."""

    ok: bool
    result_size: int | None = Field(default=None, ge=0, le=_MAX_RESULT_BYTES)
    result_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]+$")
    detail: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        success_shape = (
            self.result_size is not None
            and self.result_sha256 is not None
            and self.code is None
            and self.detail is None
        )
        failure_shape = (
            self.result_size is None
            and self.result_sha256 is None
            and self.code is not None
            and self.detail is not None
        )
        if (self.ok and not success_shape) or (not self.ok and not failure_shape):
            raise ValueError("rule worker envelope is inconsistent")
        return self


def _failure(code: str, detail: str) -> RuleExecution:
    return RuleExecution(failure=RuleFailure(code=code, detail=detail))


def _write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        stat.S_IRUSR | stat.S_IWUSR,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
    except BaseException:
        with suppress(OSError):
            os.close(descriptor)
        raise


def _canonical_payload(
    model: StrictModel,
    *,
    maximum_bytes: int,
    label: str,
) -> bytes:
    payload = canonical_json(model).encode("utf-8")
    if len(payload) > maximum_bytes:
        raise ValueError(f"{label} exceeds the isolated rule input limit")
    return payload


def _read_bounded(path: Path, maximum_bytes: int) -> bytes:
    size = path.stat().st_size
    if size > maximum_bytes:
        raise _FileSizeLimitError("isolated rule file exceeds its size limit")
    payload = path.read_bytes()
    if len(payload) > maximum_bytes:
        raise _FileSizeLimitError("isolated rule file exceeds its size limit")
    if len(payload) != size:
        raise ValueError("isolated rule file changed while being read")
    return payload


def _validate_project_profile(project: PCBProject, profile: RuleProfile) -> None:
    digest = profile_hash(profile)
    requirements = project.fabrication_requirements
    if (
        requirements.profile_id != profile.profile.id
        or requirements.profile_sha256 != digest
    ):
        raise ValueError("project fabrication requirements do not match the profile")


def _validate_review(
    review: ReviewResult,
    *,
    project: PCBProject,
    profile: RuleProfile,
) -> None:
    digest = profile_hash(profile)
    if review.project_id != project.project_id:
        raise ValueError("rule result references a different project")
    if review.profile_id != profile.profile.id or review.profile_sha256 != digest:
        raise ValueError("rule result references a different profile")
    registry = build_builtin_registry(require_complete=True)
    expected_inventory = tuple(rule.rule_id for rule in registry.ordered_rules)
    observed_inventory = tuple(result.rule_id for result in review.rule_results)
    if observed_inventory != expected_inventory:
        raise ValueError("rule result inventory does not match the built-in registry")


def _send_envelope(
    send_connection: Connection,
    envelope: _WorkerEnvelope,
) -> None:
    message = canonical_json(envelope).encode("utf-8")
    if len(message) > _MAX_ENVELOPE_BYTES:  # pragma: no cover - model bounds
        message = canonical_json(
            _WorkerEnvelope(
                ok=False,
                code="RULE_PROTOCOL_ERROR",
                detail="rule worker response exceeded the envelope limit",
            )
        ).encode("utf-8")
    send_connection.send_bytes(message)


def _worker(send_connection: Connection, paths: _WorkerPaths) -> None:
    try:
        try:
            project_payload = _read_bounded(
                Path(paths.project),
                _MAX_PROJECT_BYTES,
            )
            profile_payload = _read_bounded(
                Path(paths.profile),
                _MAX_PROFILE_BYTES,
            )
            request_payload = _read_bounded(
                Path(paths.request),
                _MAX_REQUEST_BYTES,
            )
            project = PCBProject.model_validate_json(project_payload)
            profile = RuleProfile.model_validate_json(profile_payload)
            request = _WorkerRequest.model_validate_json(request_payload)
            _validate_project_profile(project, profile)
            selected_rule_ids = (
                None
                if request.selected_rule_ids is None
                else frozenset(request.selected_rule_ids)
            )
            review = RuleEngine(build_builtin_registry(require_complete=True)).evaluate(
                project,
                profile,
                selected_rule_ids=selected_rule_ids,
            )
            _validate_review(review, project=project, profile=profile)
            result_payload = canonical_json(review).encode("utf-8")
            if len(result_payload) > _MAX_RESULT_BYTES:
                envelope = _WorkerEnvelope(
                    ok=False,
                    code="RULE_RESULT_SIZE_LIMIT",
                    detail="rule result exceeds the isolated result limit",
                )
            else:
                _write_private(Path(paths.result), result_payload)
                envelope = _WorkerEnvelope(
                    ok=True,
                    result_size=len(result_payload),
                    result_sha256=sha256(result_payload).hexdigest(),
                )
        except (OSError, ValueError):
            envelope = _WorkerEnvelope(
                ok=False,
                code="RULE_WORKER_INPUT_INVALID",
                detail="isolated rule inputs failed BoardGate validation",
            )
        except BaseException as error:  # pragma: no cover - worker safety boundary
            envelope = _WorkerEnvelope(
                ok=False,
                code="RULE_WORKER_EXCEPTION",
                detail=f"rule worker raised {type(error).__name__}",
            )
        _send_envelope(send_connection, envelope)
    except (OSError, ValueError):
        pass
    finally:
        send_connection.close()


def _stop_process(process: BaseProcess) -> None:
    if process.is_alive():
        process.join(_GRACEFUL_JOIN_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(_CLEANUP_TIMEOUT_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(_CLEANUP_TIMEOUT_SECONDS)


def _decode_result(  # noqa: PLR0911
    *,
    message: bytes,
    result_path: Path,
    project: PCBProject,
    profile: RuleProfile,
) -> RuleExecution:
    try:
        envelope = _WorkerEnvelope.model_validate_json(message)
    except ValueError:
        return _failure(
            "RULE_PROTOCOL_ERROR",
            "rule worker returned an invalid response",
        )
    if not envelope.ok:
        return _failure(
            envelope.code or "RULE_PROTOCOL_ERROR",
            envelope.detail or "rule worker returned an incomplete failure",
        )
    expected_size = envelope.result_size
    expected_sha256 = envelope.result_sha256
    if expected_size is None or expected_sha256 is None:  # pragma: no cover
        return _failure(
            "RULE_PROTOCOL_ERROR",
            "rule worker omitted its result metadata",
        )
    try:
        if not result_path.is_file():
            raise ValueError
        result_payload = _read_bounded(result_path, _MAX_RESULT_BYTES)
    except _FileSizeLimitError:
        return _failure(
            "RULE_RESULT_SIZE_LIMIT",
            "rule worker result exceeds the isolated result limit",
        )
    except (OSError, ValueError):
        return _failure(
            "RULE_PROTOCOL_ERROR",
            "rule worker result file is missing or invalid",
        )
    if (
        len(result_payload) != expected_size
        or sha256(result_payload).hexdigest() != expected_sha256
    ):
        return _failure(
            "RULE_RESULT_INTEGRITY_ERROR",
            "rule worker result failed its integrity check",
        )
    try:
        review = ReviewResult.model_validate_json(result_payload)
        _validate_review(review, project=project, profile=profile)
    except ValueError:
        return _failure(
            "RULE_RESULT_INVALID",
            "rule worker result failed BoardGate model validation",
        )
    return RuleExecution(result=review)


def run_rule_evaluation(  # noqa: PLR0911, PLR0912, PLR0915
    project: PCBProject,
    profile: RuleProfile,
    *,
    selected_rule_ids: frozenset[RuleId] | None = None,
    deadline: float,
    monotonic_clock: MonotonicClock = time.monotonic,
) -> RuleExecution:
    """Evaluate built-in rules in a fresh spawned process before ``deadline``."""
    if not math.isfinite(deadline):
        raise ValueError("rule deadline must be finite")
    try:
        _validate_project_profile(project, profile)
    except ValueError:
        return _failure(
            "RULE_INPUT_MISMATCH",
            "project and rule profile identifiers do not match",
        )
    remaining = deadline - monotonic_clock()
    if remaining <= 0.0:
        return _failure(
            "REVIEW_TIMEOUT",
            "the review runtime limit was reached before rule execution",
        )
    request = _WorkerRequest(
        selected_rule_ids=(
            None
            if selected_rule_ids is None
            else tuple(sorted(selected_rule_ids, key=str))
        )
    )
    try:
        project_payload = _canonical_payload(
            project,
            maximum_bytes=_MAX_PROJECT_BYTES,
            label="project",
        )
        profile_payload = _canonical_payload(
            profile,
            maximum_bytes=_MAX_PROFILE_BYTES,
            label="profile",
        )
        request_payload = _canonical_payload(
            request,
            maximum_bytes=_MAX_REQUEST_BYTES,
            label="rule request",
        )
    except ValueError:
        return _failure(
            "RULE_INPUT_SIZE_LIMIT",
            "isolated rule inputs exceed the configured size limit",
        )

    with tempfile.TemporaryDirectory(prefix="boardgate-rule-runner-") as directory:
        workspace = Path(directory)
        workspace.chmod(stat.S_IRWXU)
        project_path = workspace / "project.json"
        profile_path = workspace / "profile.json"
        request_path = workspace / "request.json"
        result_path = workspace / "result.json"
        try:
            _write_private(project_path, project_payload)
            _write_private(profile_path, profile_payload)
            _write_private(request_path, request_payload)
        except OSError:
            return _failure(
                "RULE_STAGING_FAILED",
                "isolated rule inputs could not be staged",
            )
        if monotonic_clock() >= deadline:
            return _failure(
                "REVIEW_TIMEOUT",
                "the review runtime limit was reached before rule execution",
            )

        paths = _WorkerPaths(
            project=str(project_path),
            profile=str(profile_path),
            request=str(request_path),
            result=str(result_path),
        )
        context = multiprocessing.get_context("spawn")
        receive_connection, send_connection = context.Pipe(duplex=False)
        process = context.Process(
            target=_worker,
            args=(send_connection, paths),
            daemon=True,
        )
        try:
            try:
                process.start()
            except (OSError, RuntimeError):
                return _failure(
                    "RULE_PROCESS_START_FAILED",
                    "isolated rule process could not be started",
                )
            finally:
                send_connection.close()
            remaining = deadline - monotonic_clock()
            try:
                response_ready = remaining > 0.0 and receive_connection.poll(remaining)
            except (OSError, ValueError):
                return _failure(
                    "RULE_PROTOCOL_ERROR",
                    "rule process response could not be received",
                )
            if not response_ready:
                return _failure(
                    "REVIEW_TIMEOUT",
                    "the review runtime limit was reached during rule execution",
                )
            try:
                message = receive_connection.recv_bytes(_MAX_ENVELOPE_BYTES)
            except EOFError:
                return _failure(
                    "RULE_PROCESS_CRASH",
                    "rule process exited without a result",
                )
            except OSError:
                return _failure(
                    "RULE_PROTOCOL_ERROR",
                    "rule worker response exceeded the envelope limit",
                )
            if monotonic_clock() >= deadline:
                return _failure(
                    "REVIEW_TIMEOUT",
                    "the review runtime limit was reached during rule execution",
                )
            execution = _decode_result(
                message=message,
                result_path=result_path,
                project=project,
                profile=profile,
            )
            if monotonic_clock() >= deadline:
                return _failure(
                    "REVIEW_TIMEOUT",
                    "the review runtime limit was reached during rule execution",
                )
            return execution
        finally:
            receive_connection.close()
            _stop_process(process)
            process.close()
