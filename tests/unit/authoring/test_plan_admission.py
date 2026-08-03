"""Deterministic plan/request binding without execution or writes."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.application.generation_registry import registered_generator_keys
from boardgate.application.modification_registry import registered_operation_keys
from boardgate.authoring.generation_models import GenerationRequest
from boardgate.authoring.identifiers import (
    generation_request_sha256,
    operation_sha256,
    plan_authorization_sha256,
    request_sha256,
)
from boardgate.authoring.plan_admission import (
    AdmittedAuthoringPlan,
    PlanAdmissionError,
    admit_authoring_plan,
)
from boardgate.authoring.plan_models import (
    AUTHORING_OPERATION_KEYS,
    PLAN_AUTHORIZATION_STATEMENT,
    AuthoringPlan,
)

from .test_generation_models import request as generation_request
from .test_models_identifiers import request as modification_request
from .test_plan_models import npth_request, plan_for


def test_plan_keys_match_both_complete_registries() -> None:
    assert (
        registered_operation_keys() | registered_generator_keys()
    ) == AUTHORING_OPERATION_KEYS


def test_modification_plan_binds_the_exact_request() -> None:
    request = modification_request()
    plan = plan_for(request)

    admitted = admit_authoring_plan(plan, request)

    assert isinstance(admitted, AdmittedAuthoringPlan)
    assert admitted.request == request
    assert admitted.plan == plan


def test_generation_plans_bind_the_exact_requests() -> None:
    for request in (generation_request(), npth_request()):
        plan = plan_for(request)

        admitted = admit_authoring_plan(plan, request)

        assert admitted.request == request
        assert admitted.plan.operation_kind == request.operation.kind


def test_plan_rejects_a_request_of_the_wrong_kind() -> None:
    plan = plan_for(modification_request())

    with pytest.raises(PlanAdmissionError) as caught:
        admit_authoring_plan(plan, generation_request())
    assert caught.value.code == "PLAN_REQUEST_KIND_MISMATCH"

    generation_plan = plan_for(generation_request())
    with pytest.raises(PlanAdmissionError) as caught:
        admit_authoring_plan(generation_plan, modification_request())
    assert caught.value.code == "PLAN_REQUEST_KIND_MISMATCH"


def test_plan_rejects_a_mismatched_operation_identity() -> None:
    request = modification_request()
    payload = plan_for(request).model_dump(mode="json")
    payload["operation_kind"] = "generate_two_layer_coupon"
    mismatched = AuthoringPlan.model_validate(payload)

    with pytest.raises(PlanAdmissionError) as caught:
        admit_authoring_plan(mismatched, request)
    assert caught.value.code == "PLAN_OPERATION_MISMATCH"


def test_prose_cannot_alter_operation_identity_or_authorization() -> None:
    request = modification_request()
    reworded_operation = request.operation.model_copy(
        update={"instruction": "Completely different prose."}
    )
    reworded_request = request.model_copy(update={"operation": reworded_operation})

    assert operation_sha256(reworded_request.operation) == operation_sha256(
        request.operation
    )
    assert request_sha256(reworded_request) != request_sha256(request)

    plan = plan_for(request)
    with pytest.raises(PlanAdmissionError) as caught:
        admit_authoring_plan(plan, reworded_request)
    assert caught.value.code == "PLAN_REQUEST_DIGEST_MISMATCH"

    reworded_plan = plan_for(request, rationale="Unrelated rationale prose.")
    assert reworded_plan.request_sha256 == plan.request_sha256
    assert reworded_plan.operation_sha256 == plan.operation_sha256
    assert (
        reworded_plan.authorization.authorization_sha256
        == plan.authorization.authorization_sha256
    )
    assert admit_authoring_plan(reworded_plan, request).request == request


def test_plan_rejects_a_tampered_operation_digest() -> None:
    request = modification_request()
    other_digest = operation_sha256(
        request.operation.model_copy(update={"new_diameter_mm": 0.4})
    )
    payload = plan_for(request).model_dump(mode="json")
    payload["operation_sha256"] = other_digest
    tampered = AuthoringPlan.model_validate(payload)

    with pytest.raises(PlanAdmissionError) as caught:
        admit_authoring_plan(tampered, request)
    assert caught.value.code == "PLAN_OPERATION_DIGEST_MISMATCH"


def test_plan_rejects_a_tampered_authorization_digest() -> None:
    request = modification_request()
    payload = plan_for(request).model_dump(mode="json")
    payload["authorization"]["authorization_sha256"] = plan_authorization_sha256(
        approver="mallory@example.com",
        statement=PLAN_AUTHORIZATION_STATEMENT,
        request_sha256=payload["authorization"]["request_sha256"],
    )
    tampered = AuthoringPlan.model_validate(payload)

    with pytest.raises(PlanAdmissionError) as caught:
        admit_authoring_plan(tampered, request)
    assert caught.value.code == "PLAN_AUTHORIZATION_MISMATCH"


def test_plan_rejects_an_authorization_bound_to_another_request() -> None:
    request = modification_request()
    other_request = generation_request()
    payload = plan_for(request).model_dump(mode="json")
    payload["request_sha256"] = generation_request_sha256(other_request)
    payload["authorization"]["request_sha256"] = payload["request_sha256"]
    payload["authorization"]["authorization_sha256"] = plan_authorization_sha256(
        approver=payload["authorization"]["approver"],
        statement=PLAN_AUTHORIZATION_STATEMENT,
        request_sha256=payload["request_sha256"],
    )
    rebound = AuthoringPlan.model_validate(payload)

    with pytest.raises(PlanAdmissionError) as caught:
        admit_authoring_plan(rebound, request)
    assert caught.value.code == "PLAN_REQUEST_DIGEST_MISMATCH"

    with pytest.raises(PlanAdmissionError) as caught:
        admit_authoring_plan(rebound, other_request)
    assert caught.value.code == "PLAN_REQUEST_KIND_MISMATCH"


def test_admission_performs_no_writes_and_exposes_only_evidence(
    tmp_path: Path,
) -> None:
    request = generation_request()
    plan = plan_for(request)

    admitted = admit_authoring_plan(plan, request)

    assert tuple(tmp_path.iterdir()) == ()
    assert set(AdmittedAuthoringPlan.__dataclass_fields__) == {"plan", "request"}
    assert isinstance(admitted.request, GenerationRequest)
