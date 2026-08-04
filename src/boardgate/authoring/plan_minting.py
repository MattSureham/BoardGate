"""Deterministic authoring-plan minting for one explicit human approval."""

from __future__ import annotations

from typing import Literal

from boardgate.authoring.generation_models import GenerationRequest
from boardgate.authoring.identifiers import (
    generation_operation_sha256,
    generation_request_sha256,
    operation_sha256,
    plan_authorization_sha256,
    request_sha256,
)
from boardgate.authoring.models import ModificationRequest
from boardgate.authoring.plan_models import (
    PLAN_AUTHORIZATION_STATEMENT,
    AuthoringPlan,
    PlanAuthorization,
)


def mint_authoring_plan(
    request: ModificationRequest | GenerationRequest,
    *,
    approver: str,
    rationale: str = "",
) -> AuthoringPlan:
    """Derive the canonical authorized plan for one admitted request."""
    request_kind: Literal["modification", "generation"]
    if isinstance(request, ModificationRequest):
        request_kind = "modification"
        request_digest = request_sha256(request)
        operation_digest = operation_sha256(request.operation)
    else:
        request_kind = "generation"
        request_digest = generation_request_sha256(request)
        operation_digest = generation_operation_sha256(request.operation)
    return AuthoringPlan(
        schema_version="1.0",
        plan_version="1.0",
        request_kind=request_kind,
        operation_kind=request.operation.kind,
        operation_version=request.operation.operation_version,
        request_sha256=request_digest,
        operation_sha256=operation_digest,
        authorization=PlanAuthorization(
            approver=approver,
            statement=PLAN_AUTHORIZATION_STATEMENT,
            request_sha256=request_digest,
            authorization_sha256=plan_authorization_sha256(
                approver=approver,
                statement=PLAN_AUTHORIZATION_STATEMENT,
                request_sha256=request_digest,
            ),
        ),
        rationale=rationale,
    )
