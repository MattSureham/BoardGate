"""Exact-version registry coverage for the mixed plated/NPTH generator."""

from __future__ import annotations

import pytest

from boardgate.application.generation_registry import (
    GenerationExecutorError,
    GenerationRegistryError,
    TwoLayerCouponWithNpthExecutor,
    registered_generator_keys,
    resolve_generation_executor,
    resolve_generation_executor_key,
    validate_generation_registry,
)
from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
    parse_job,
)
from boardgate.authoring.coupon import (
    NON_PLATED_DRILL_PATH,
    NPTH_GENERATION_PAYLOAD_PATHS,
    PLATED_DRILL_PATH,
)
from boardgate.authoring.generation_models import (
    GENERATION_OPERATION_KEYS,
    AppliedTwoLayerCouponWithNpthGeneration,
)

from .test_coupon_npth import operation
from .test_generation_models import operation as legacy_operation


def local_parser(job: ParserJob) -> ParserExecution:
    """Return normalized in-process parser evidence through the executor protocol."""
    return ParserExecution(
        file_type=job.file_type,
        source_file_id=job.source_file_id,
        result=parse_job(job),
    )


def test_registry_has_exactly_two_complete_operation_keys() -> None:
    validate_generation_registry()

    expected = frozenset(
        {
            ("generate_two_layer_coupon", "1.0"),
            ("generate_two_layer_coupon_with_npth", "1.0"),
        }
    )
    assert registered_generator_keys() == expected
    assert expected == GENERATION_OPERATION_KEYS


def test_registry_resolves_the_exact_npth_executor() -> None:
    resolved = resolve_generation_executor(operation())

    assert isinstance(resolved, TwoLayerCouponWithNpthExecutor)
    assert resolved is resolve_generation_executor_key(
        "generate_two_layer_coupon_with_npth",
        "1.0",
    )


@pytest.mark.parametrize("version", ("0.9", "1.1", "2.0"))
def test_registry_does_not_fallback_for_unknown_npth_versions(version: str) -> None:
    with pytest.raises(GenerationRegistryError) as caught:
        resolve_generation_executor_key(
            "generate_two_layer_coupon_with_npth",
            version,
        )

    assert caught.value.code == "GENERATION_OPERATION_UNREGISTERED"


def test_npth_executor_rejects_the_legacy_operation_type() -> None:
    with pytest.raises(GenerationRegistryError) as caught:
        TwoLayerCouponWithNpthExecutor().execute(
            legacy_operation(),
            parser_executor=local_parser,
        )

    assert caught.value.code == "GENERATION_EXECUTOR_TYPE_MISMATCH"


def test_npth_executor_reparses_all_five_payloads_and_records_populations() -> None:
    calls: list[tuple[str, object]] = []

    def recording_parser(job: ParserJob) -> ParserExecution:
        calls.append((job.logical_path, job.file_type))
        return local_parser(job)

    executed = TwoLayerCouponWithNpthExecutor().execute(
        operation(),
        parser_executor=recording_parser,
    )

    assert tuple(sorted(payload.logical_path for payload in executed.payloads)) == (
        NPTH_GENERATION_PAYLOAD_PATHS
    )
    assert {path for path, _ in calls} == set(NPTH_GENERATION_PAYLOAD_PATHS)
    assert len(calls) == 5
    assert isinstance(executed.applied, AppliedTwoLayerCouponWithNpthGeneration)
    assert executed.applied.plated_hole_count == len(operation().plated_holes)
    assert executed.applied.non_plated_hole_count == len(operation().non_plated_holes)
    assert executed.applied.plated_tool_count == 2
    assert executed.applied.non_plated_tool_count == 2
    assert executed.applied.plated_drill_ids == tuple(
        sorted(executed.applied.plated_drill_ids)
    )
    assert executed.applied.non_plated_drill_ids == tuple(
        sorted(executed.applied.non_plated_drill_ids)
    )
    assert set(executed.applied.plated_drill_ids).isdisjoint(
        executed.applied.non_plated_drill_ids
    )


def test_npth_parser_failure_is_typed_and_never_falls_back() -> None:
    calls: list[str] = []

    def fail_only_npth(job: ParserJob) -> ParserExecution:
        calls.append(job.logical_path)
        if job.logical_path == NON_PLATED_DRILL_PATH:
            return ParserExecution(
                file_type=job.file_type,
                source_file_id=job.source_file_id,
                failure=ParserFailure(
                    code="PARSER_TEST_NPTH_FAILURE",
                    detail="simulated bounded NPTH parser failure",
                ),
            )
        return local_parser(job)

    with pytest.raises(GenerationExecutorError) as caught:
        TwoLayerCouponWithNpthExecutor().execute(
            operation(),
            parser_executor=fail_only_npth,
        )

    assert caught.value.code == "GENERATION_REPARSE_FAILED"
    assert caught.value.subject == NON_PLATED_DRILL_PATH
    assert "PARSER_TEST_NPTH_FAILURE" in caught.value.detail
    assert calls == [PLATED_DRILL_PATH, NON_PLATED_DRILL_PATH]
