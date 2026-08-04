"""Deterministic plan minting bound to admitted requests and approvers."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from boardgate.authoring.generation_models import GenerationRequest
from boardgate.authoring.identifiers import (
    generation_operation_sha256,
    generation_request_sha256,
    operation_sha256,
    plan_authorization_sha256,
    request_sha256,
)
from boardgate.authoring.models import ModificationRequest
from boardgate.authoring.plan_admission import admit_authoring_plan
from boardgate.authoring.plan_minting import mint_authoring_plan
from boardgate.authoring.plan_models import PLAN_AUTHORIZATION_STATEMENT
from boardgate.domain.serialization import canonical_json

from .test_generation_models import request as generation_request
from .test_models_identifiers import request as modification_request
from .test_plan_models import APPROVER, npth_request


@pytest.mark.parametrize(
    "request_factory",
    (modification_request, generation_request, npth_request),
)
def test_minted_plans_admit_for_every_registered_operation(
    request_factory: Callable[[], ModificationRequest | GenerationRequest],
) -> None:
    request = request_factory()

    minted = mint_authoring_plan(request, approver=APPROVER)

    if isinstance(request, ModificationRequest):
        assert minted.request_kind == "modification"
        assert minted.request_sha256 == request_sha256(request)
        assert minted.operation_sha256 == operation_sha256(request.operation)
    else:
        assert minted.request_kind == "generation"
        assert minted.request_sha256 == generation_request_sha256(request)
        assert minted.operation_sha256 == generation_operation_sha256(request.operation)
    assert minted.operation_kind == request.operation.kind
    assert minted.operation_version == request.operation.operation_version
    assert minted.authorization.approver == APPROVER
    assert minted.authorization.statement == PLAN_AUTHORIZATION_STATEMENT
    assert minted.authorization.request_sha256 == minted.request_sha256
    assert minted.authorization.authorization_sha256 == plan_authorization_sha256(
        approver=APPROVER,
        statement=PLAN_AUTHORIZATION_STATEMENT,
        request_sha256=minted.request_sha256,
    )
    assert minted.rationale == ""
    assert admit_authoring_plan(minted, request).request == request


def test_minting_is_byte_deterministic() -> None:
    request = generation_request()

    first = mint_authoring_plan(request, approver=APPROVER, rationale="r")
    second = mint_authoring_plan(request, approver=APPROVER, rationale="r")

    assert first == second
    assert canonical_json(first) == canonical_json(second)


def test_rationale_is_recorded_but_never_digested() -> None:
    request = modification_request()

    plain = mint_authoring_plan(request, approver=APPROVER)
    reasoned = mint_authoring_plan(
        request,
        approver=APPROVER,
        rationale="Selected Finding minimum_drill_diameter.",
    )

    assert reasoned.rationale == "Selected Finding minimum_drill_diameter."
    assert reasoned.request_sha256 == plain.request_sha256
    assert reasoned.operation_sha256 == plain.operation_sha256
    assert (
        reasoned.authorization.authorization_sha256
        == plain.authorization.authorization_sha256
    )
    assert admit_authoring_plan(reasoned, request).plan == reasoned


def test_approver_changes_only_the_authorization_digest() -> None:
    request = generation_request()

    first = mint_authoring_plan(request, approver="one@example.com")
    second = mint_authoring_plan(request, approver="two@example.com")

    assert first.request_sha256 == second.request_sha256
    assert first.operation_sha256 == second.operation_sha256
    assert (
        first.authorization.authorization_sha256
        != second.authorization.authorization_sha256
    )


def test_minting_rejects_contract_violating_approver_and_rationale() -> None:
    request = modification_request()

    with pytest.raises(ValidationError):
        mint_authoring_plan(request, approver="")
    with pytest.raises(ValidationError):
        mint_authoring_plan(request, approver="x" * 201)
    with pytest.raises(ValidationError):
        mint_authoring_plan(request, approver=APPROVER, rationale="x" * 501)
