"""Typed authoring-plan contracts bound to registered operations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import pytest
from pydantic import ValidationError

from boardgate.authoring.generation_models import (
    GENERATION_OPERATION_KEYS,
    GenerationRequest,
)
from boardgate.authoring.identifiers import (
    generation_operation_sha256,
    generation_request_sha256,
    operation_sha256,
    plan_authorization_sha256,
    request_sha256,
)
from boardgate.authoring.models import (
    MODIFICATION_OPERATION_KEYS,
    ModificationRequest,
)
from boardgate.authoring.plan_models import (
    AUTHORING_OPERATION_KEYS,
    PLAN_AUTHORIZATION_STATEMENT,
    AuthoringPlan,
    PlanAuthorization,
)

from .test_generation_models import request as generation_request
from .test_generation_npth_models import (
    _admit_request,
    _request_payload,
)
from .test_models_identifiers import request as modification_request

APPROVER = "engineer@example.com"


def npth_request() -> GenerationRequest:
    return _admit_request(_request_payload())


def plan_for(
    request: ModificationRequest | GenerationRequest,
    *,
    rationale: str = "Selected Finding minimum_drill_diameter.",
) -> AuthoringPlan:
    if isinstance(request, ModificationRequest):
        request_kind: Literal["modification", "generation"] = "modification"
        request_digest = request_sha256(request)
        operation_digest = operation_sha256(request.operation)
    else:
        request_kind = "generation"
        request_digest = generation_request_sha256(request)
        operation_digest = generation_operation_sha256(request.operation)
    operation = request.operation
    return AuthoringPlan(
        schema_version="1.0",
        plan_version="1.0",
        request_kind=request_kind,
        operation_kind=operation.kind,
        operation_version=operation.operation_version,
        request_sha256=request_digest,
        operation_sha256=operation_digest,
        authorization=PlanAuthorization(
            approver=APPROVER,
            statement=PLAN_AUTHORIZATION_STATEMENT,
            request_sha256=request_digest,
            authorization_sha256=plan_authorization_sha256(
                approver=APPROVER,
                statement=PLAN_AUTHORIZATION_STATEMENT,
                request_sha256=request_digest,
            ),
        ),
        rationale=rationale,
    )


def test_plan_keys_are_exactly_the_registered_operation_union() -> None:
    assert AUTHORING_OPERATION_KEYS == (
        MODIFICATION_OPERATION_KEYS | GENERATION_OPERATION_KEYS
    )


@pytest.mark.parametrize(
    "request_factory",
    (modification_request, generation_request, npth_request),
)
def test_valid_plans_are_admitted_for_every_registered_operation(
    request_factory: Callable[[], ModificationRequest | GenerationRequest],
) -> None:
    plan = plan_for(request_factory())

    assert plan.kind == "authoring_plan"
    assert plan.plan_version == "1.0"
    assert plan.authorization.statement == PLAN_AUTHORIZATION_STATEMENT
    assert plan.authorization.request_sha256 == plan.request_sha256


@pytest.mark.parametrize(
    ("kind", "version"),
    (
        ("set_excellon_tool_diameter", "2.0"),
        ("generate_two_layer_coupon", "2.0"),
        ("generate_two_layer_coupon_with_npth", "2.0"),
        ("free_form_writer", "1.0"),
        ("raw_text_patch", "1.0"),
    ),
)
def test_plan_rejects_unregistered_kinds_and_versions_without_fallback(
    kind: str,
    version: str,
) -> None:
    payload = plan_for(modification_request()).model_dump(mode="json")
    payload["operation_kind"] = kind
    payload["operation_version"] = version

    with pytest.raises(ValidationError, match="registered operation kind/version"):
        AuthoringPlan.model_validate(payload)


def test_authorization_must_bind_the_plan_request_digest() -> None:
    payload = plan_for(modification_request()).model_dump(mode="json")
    payload["authorization"]["request_sha256"] = "f" * 64

    with pytest.raises(ValidationError, match="bound to the plan request digest"):
        AuthoringPlan.model_validate(payload)


def test_authorization_statement_is_pinned_to_normative_text() -> None:
    payload = plan_for(modification_request()).model_dump(mode="json")
    payload["authorization"]["statement"] = "Manufacturability guaranteed."

    with pytest.raises(ValidationError, match="normative authorization text"):
        AuthoringPlan.model_validate(payload)


def test_plan_rejects_extra_keys_and_malformed_digests() -> None:
    payload = plan_for(modification_request()).model_dump(mode="json")
    payload["execute_immediately"] = True

    with pytest.raises(ValidationError):
        AuthoringPlan.model_validate(payload)

    payload = plan_for(modification_request()).model_dump(mode="json")
    payload["authorization"]["authorization_sha256"] = "zz"
    with pytest.raises(ValidationError):
        AuthoringPlan.model_validate(payload)


def test_rationale_is_bounded_optional_prose() -> None:
    plan = plan_for(modification_request())
    payload = plan.model_dump(mode="json")
    del payload["rationale"]

    admitted = AuthoringPlan.model_validate(payload)
    assert admitted.rationale == ""

    payload["rationale"] = "x" * 501
    with pytest.raises(ValidationError):
        AuthoringPlan.model_validate(payload)
