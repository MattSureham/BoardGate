"""Deterministic binding of an admitted plan to one immutable request."""

from __future__ import annotations

from dataclasses import dataclass

from boardgate.authoring.generation_models import GenerationRequest
from boardgate.authoring.identifiers import (
    generation_operation_sha256,
    generation_request_sha256,
    operation_sha256,
    plan_authorization_sha256,
    request_sha256,
)
from boardgate.authoring.models import ModificationRequest
from boardgate.authoring.plan_models import AuthoringPlan


class PlanAdmissionError(ValueError):
    """Typed plan/request binding failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


@dataclass(frozen=True, slots=True)
class AdmittedAuthoringPlan:
    """One authorized plan bound to exactly one admitted immutable request."""

    plan: AuthoringPlan
    request: ModificationRequest | GenerationRequest


def admit_authoring_plan(
    plan: AuthoringPlan,
    request: ModificationRequest | GenerationRequest,
) -> AdmittedAuthoringPlan:
    """Prove the plan authorizes exactly the presented immutable request.

    Admission performs no I/O, invokes no executor or review, and returns
    only the already-admitted request for the existing deterministic
    services, so prose can neither execute nor bypass fresh validation.
    """
    if plan.request_kind == "modification":
        if not isinstance(request, ModificationRequest):
            raise PlanAdmissionError(
                "PLAN_REQUEST_KIND_MISMATCH",
                plan.operation_kind,
                "plan request_kind does not match the presented request type",
            )
        actual_request_digest = request_sha256(request)
        actual_operation_digest = operation_sha256(request.operation)
    else:
        if not isinstance(request, GenerationRequest):
            raise PlanAdmissionError(
                "PLAN_REQUEST_KIND_MISMATCH",
                plan.operation_kind,
                "plan request_kind does not match the presented request type",
            )
        actual_request_digest = generation_request_sha256(request)
        actual_operation_digest = generation_operation_sha256(request.operation)
    operation = request.operation
    if (
        operation.kind != plan.operation_kind
        or operation.operation_version != plan.operation_version
    ):
        raise PlanAdmissionError(
            "PLAN_OPERATION_MISMATCH",
            plan.operation_kind,
            "plan operation kind/version does not match the request operation",
        )
    if plan.request_sha256 != actual_request_digest:
        raise PlanAdmissionError(
            "PLAN_REQUEST_DIGEST_MISMATCH",
            plan.operation_kind,
            "plan request digest does not match the presented request",
        )
    if plan.operation_sha256 != actual_operation_digest:
        raise PlanAdmissionError(
            "PLAN_OPERATION_DIGEST_MISMATCH",
            plan.operation_kind,
            "plan operation digest does not match the presented request",
        )
    actual_authorization_digest = plan_authorization_sha256(
        approver=plan.authorization.approver,
        statement=plan.authorization.statement,
        request_sha256=plan.authorization.request_sha256,
    )
    if plan.authorization.authorization_sha256 != actual_authorization_digest:
        raise PlanAdmissionError(
            "PLAN_AUTHORIZATION_MISMATCH",
            plan.operation_kind,
            "authorization digest does not match its canonical evidence",
        )
    return AdmittedAuthoringPlan(plan=plan, request=request)
