"""Spawn-isolated deterministic rule-stage tests."""

from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
import time
from collections.abc import Callable
from hashlib import sha256
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Never, Protocol

import pytest

import boardgate.application.rule_runner as rule_runner_module
from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
    parse_job,
)
from boardgate.application.project_builder import build_project
from boardgate.application.rule_runner import (
    RuleExecution,
    run_rule_evaluation,
)
from boardgate.config import load_rule_profile
from boardgate.config.models import RuleId, RuleProfile
from boardgate.domain.project import PCBProject
from boardgate.ingestion import build_manifest, discover_inputs
from boardgate.parsers import ParserError
from boardgate.rules.models import RuleOutcome, RuleReason

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
PROFILE_PATH = Path("rules/default.yaml")


class _ResultPath(Protocol):
    result: str


class _StartFailingProcess:
    def start(self) -> Never:
        raise OSError

    def is_alive(self) -> bool:
        return False

    def join(self, timeout: float | None = None) -> None:
        del timeout

    def terminate(self) -> None:
        return None

    def kill(self) -> None:
        return None

    def close(self) -> None:
        return None


class _StartFailingContext:
    def __init__(self) -> None:
        self._delegate = multiprocessing.get_context("spawn")

    def Pipe(self, *, duplex: bool) -> tuple[Connection, Connection]:  # noqa: N802
        return self._delegate.Pipe(duplex=duplex)

    def Process(  # noqa: N802
        self,
        *,
        target: Callable[..., None],
        args: tuple[object, ...],
        daemon: bool,
    ) -> _StartFailingProcess:
        del target, args, daemon
        return _StartFailingProcess()


def _crash_worker(send_connection: Connection, paths: object) -> Never:
    del send_connection, paths
    os._exit(17)


def _invalid_worker(send_connection: Connection, paths: object) -> None:
    del paths
    send_connection.send_bytes(b"not-json")
    send_connection.close()


def _oversized_envelope_worker(
    send_connection: Connection,
    paths: object,
) -> None:
    del paths
    send_connection.send_bytes(b"x" * (16 * 1024 + 1))
    send_connection.close()


def _invalid_result_worker(
    send_connection: Connection,
    paths: _ResultPath,
) -> None:
    payload = b"{}"
    Path(paths.result).write_bytes(payload)
    envelope = {
        "code": None,
        "detail": None,
        "ok": True,
        "result_sha256": sha256(payload).hexdigest(),
        "result_size": len(payload),
    }
    send_connection.send_bytes(
        json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    send_connection.close()


def _hanging_worker(send_connection: Connection, paths: object) -> Never:
    del send_connection, paths
    while True:
        time.sleep(1.0)


def _inline_executor(
    job: ParserJob,
    *,
    timeout_seconds: float,
) -> ParserExecution:
    del timeout_seconds
    try:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            result=parse_job(job),
        )
    except ParserError as error:
        return ParserExecution(
            file_type=job.file_type,
            source_file_id=job.source_file_id,
            failure=ParserFailure(code=error.code, detail=error.detail),
        )


@pytest.fixture(scope="module")
def project_and_profile() -> tuple[PCBProject, RuleProfile]:
    profile = load_rule_profile(PROFILE_PATH)
    with discover_inputs((FIXTURES / "valid_minimal_board",)) as discovered:
        manifest = build_manifest(discovered)
        project = build_project(
            discovered,
            manifest,
            profile,
            parser_executor=_inline_executor,
        )
    return project, profile


def test_isolated_rule_stage_returns_a_validated_complete_inventory(
    project_and_profile: tuple[PCBProject, RuleProfile],
) -> None:
    project, profile = project_and_profile

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=time.monotonic() + 30.0,
    )

    assert execution.failure is None
    assert execution.result is not None
    assert execution.result.project_id == project.project_id
    assert len(execution.result.rule_results) == 16


def test_deadline_equality_fails_before_starting_a_worker(
    project_and_profile: tuple[PCBProject, RuleProfile],
) -> None:
    project, profile = project_and_profile

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=10.0,
        monotonic_clock=lambda: 10.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "REVIEW_TIMEOUT"


def test_selected_rules_still_return_the_complete_registry_inventory(
    project_and_profile: tuple[PCBProject, RuleProfile],
) -> None:
    project, profile = project_and_profile

    execution = run_rule_evaluation(
        project,
        profile,
        selected_rule_ids=frozenset({RuleId.REQUIRED_LAYERS_PRESENT}),
        deadline=time.monotonic() + 30.0,
    )

    assert execution.failure is None
    assert execution.result is not None
    by_id = {result.rule_id: result for result in execution.result.rule_results}
    assert set(by_id) == set(RuleId)
    assert by_id[RuleId.REQUIRED_LAYERS_PRESENT].outcome is RuleOutcome.PASS
    assert by_id[RuleId.DRILL_FILE_PRESENT].reason is RuleReason.ORCHESTRATOR_FILTERED


def test_active_worker_timeout_is_typed_and_cleanup_completes(
    project_and_profile: tuple[PCBProject, RuleProfile],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project, profile = project_and_profile
    original_temporary_directory = tempfile.TemporaryDirectory
    staged_directories: list[Path] = []

    def temporary_directory(*, prefix: str) -> object:
        temporary = original_temporary_directory(prefix=prefix, dir=tmp_path)
        staged_directories.append(Path(temporary.name))
        return temporary

    monkeypatch.setattr(
        tempfile,
        "TemporaryDirectory",
        temporary_directory,
    )
    monkeypatch.setattr(rule_runner_module, "_worker", _hanging_worker)
    children_before = {process.pid for process in multiprocessing.active_children()}

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=time.monotonic() + 0.05,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "REVIEW_TIMEOUT"
    assert staged_directories
    assert all(not path.exists() for path in staged_directories)
    children_after = {process.pid for process in multiprocessing.active_children()}
    assert children_after <= children_before


def test_worker_crash_is_typed(
    project_and_profile: tuple[PCBProject, RuleProfile],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, profile = project_and_profile
    monkeypatch.setattr(rule_runner_module, "_worker", _crash_worker)

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=time.monotonic() + 30.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "RULE_PROCESS_CRASH"


def test_invalid_worker_envelope_is_rejected(
    project_and_profile: tuple[PCBProject, RuleProfile],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, profile = project_and_profile
    monkeypatch.setattr(rule_runner_module, "_worker", _invalid_worker)

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=time.monotonic() + 30.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "RULE_PROTOCOL_ERROR"


def test_oversized_worker_envelope_is_rejected(
    project_and_profile: tuple[PCBProject, RuleProfile],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, profile = project_and_profile
    monkeypatch.setattr(rule_runner_module, "_worker", _oversized_envelope_worker)

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=time.monotonic() + 30.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "RULE_PROTOCOL_ERROR"


def test_oversized_result_file_is_rejected_without_reading_it(
    project_and_profile: tuple[PCBProject, RuleProfile],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, profile = project_and_profile
    monkeypatch.setattr(rule_runner_module, "_worker", _invalid_result_worker)
    monkeypatch.setattr(rule_runner_module, "_MAX_RESULT_BYTES", 1)

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=time.monotonic() + 30.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "RULE_RESULT_SIZE_LIMIT"


def test_invalid_result_file_is_rejected_after_integrity_check(
    project_and_profile: tuple[PCBProject, RuleProfile],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, profile = project_and_profile
    monkeypatch.setattr(rule_runner_module, "_worker", _invalid_result_worker)

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=time.monotonic() + 30.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "RULE_RESULT_INVALID"


def test_process_start_failure_is_typed(
    project_and_profile: tuple[PCBProject, RuleProfile],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, profile = project_and_profile
    context = _StartFailingContext()

    def get_context(method: str) -> _StartFailingContext:
        assert method == "spawn"
        return context

    monkeypatch.setattr(multiprocessing, "get_context", get_context)

    execution = run_rule_evaluation(
        project,
        profile,
        deadline=time.monotonic() + 30.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "RULE_PROCESS_START_FAILED"


def test_project_profile_mismatch_is_rejected_before_worker_start(
    project_and_profile: tuple[PCBProject, RuleProfile],
) -> None:
    project, profile = project_and_profile
    mismatched_metadata = profile.profile.model_copy(update={"id": "other-profile"})
    mismatched_profile = profile.model_copy(update={"profile": mismatched_metadata})

    execution = run_rule_evaluation(
        project,
        mismatched_profile,
        deadline=time.monotonic() + 30.0,
    )

    assert execution.result is None
    assert execution.failure is not None
    assert execution.failure.code == "RULE_INPUT_MISMATCH"


def test_rule_execution_and_deadline_invariants_are_strict(
    project_and_profile: tuple[PCBProject, RuleProfile],
) -> None:
    project, profile = project_and_profile

    with pytest.raises(ValueError, match="exactly one"):
        RuleExecution()
    with pytest.raises(ValueError, match="finite"):
        run_rule_evaluation(project, profile, deadline=float("inf"))
