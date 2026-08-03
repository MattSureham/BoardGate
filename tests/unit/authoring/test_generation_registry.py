"""Complete, exact-version deterministic generation executor registry."""

from __future__ import annotations

from typing import cast

import pytest

from boardgate.application.generation_registry import (
    GenerationExecutorError,
    GenerationRegistryError,
    TwoLayerCouponExecutor,
    registered_generator_keys,
    resolve_generation_executor,
    resolve_generation_executor_key,
    validate_generation_registry,
)
from boardgate.application.parser_runner import (
    ParserExecution,
    ParserFailure,
    ParserJob,
)
from boardgate.authoring.generation_models import (
    GENERATION_OPERATION_KEYS,
    GenerationOperation,
)

from .test_generation_models import operation


def fail_parser(job: ParserJob) -> ParserExecution:
    return ParserExecution(
        file_type=job.file_type,
        source_file_id=job.source_file_id,
        failure=ParserFailure(
            code="PARSER_TEST_FAILURE",
            detail="simulated bounded parser failure",
        ),
    )


def test_registry_is_complete_and_resolves_the_admitted_operation() -> None:
    validate_generation_registry()

    assert registered_generator_keys() == GENERATION_OPERATION_KEYS
    assert isinstance(
        resolve_generation_executor(operation()),
        TwoLayerCouponExecutor,
    )


@pytest.mark.parametrize(
    ("kind", "version"),
    (
        ("generate_two_layer_coupon", "2.0"),
        ("free_form_writer", "1.0"),
    ),
)
def test_registry_rejects_unknown_kinds_and_versions_without_fallback(
    kind: str,
    version: str,
) -> None:
    with pytest.raises(GenerationRegistryError) as caught:
        resolve_generation_executor_key(kind, version)

    assert caught.value.code == "GENERATION_OPERATION_UNREGISTERED"


def test_executor_rejects_mismatched_operation_models() -> None:
    with pytest.raises(GenerationRegistryError) as caught:
        TwoLayerCouponExecutor().execute(
            cast("GenerationOperation", object()),
            parser_executor=fail_parser,
        )

    assert caught.value.code == "GENERATION_EXECUTOR_TYPE_MISMATCH"


def test_executor_surfaces_bounded_parser_failures() -> None:
    with pytest.raises(GenerationExecutorError) as caught:
        TwoLayerCouponExecutor().execute(operation(), parser_executor=fail_parser)

    assert caught.value.code == "GENERATION_REPARSE_FAILED"
    assert "PARSER_TEST_FAILURE" in caught.value.detail
