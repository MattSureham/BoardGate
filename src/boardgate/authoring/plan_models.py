"""Versioned public contracts for explicitly authorized authoring plans."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from boardgate.authoring.generation_models import GENERATION_OPERATION_KEYS
from boardgate.authoring.models import MODIFICATION_OPERATION_KEYS
from boardgate.domain.base import VersionedModel

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
AUTHORING_OPERATION_KEYS = MODIFICATION_OPERATION_KEYS | GENERATION_OPERATION_KEYS
PLAN_AUTHORIZATION_STATEMENT = (
    "I authorize exactly the referenced deterministic BoardGate authoring "
    "operation; this authorization does not guarantee manufacturability or "
    "replace fabricator and engineer approval."
)


class PlanAuthorization(VersionedModel):
    """One explicit offline approval bound to an exact request digest."""

    approver: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=500)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    authorization_sha256: str = Field(pattern=_SHA256_PATTERN)

    @field_validator("statement")
    @classmethod
    def require_normative_statement(cls, value: str) -> str:
        """Prevent authorization evidence from claiming wider authority."""
        if value != PLAN_AUTHORIZATION_STATEMENT:
            msg = "statement must use the normative authorization text"
            raise ValueError(msg)
        return value


class AuthoringPlan(VersionedModel):
    """One typed, explicitly authorized proposal for one registered operation."""

    schema_version: Literal["1.0"]
    kind: Literal["authoring_plan"] = "authoring_plan"
    plan_version: Literal["1.0"]
    request_kind: Literal["modification", "generation"]
    operation_kind: str = Field(min_length=1, max_length=200)
    operation_version: str = Field(min_length=1, max_length=50)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    operation_sha256: str = Field(pattern=_SHA256_PATTERN)
    authorization: PlanAuthorization
    rationale: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        """Bind the plan to registered operations and its authorization."""
        if (self.operation_kind, self.operation_version) not in (
            AUTHORING_OPERATION_KEYS
        ):
            msg = "plan must reference one registered operation kind/version"
            raise ValueError(msg)
        if self.authorization.request_sha256 != self.request_sha256:
            msg = "authorization must be bound to the plan request digest"
            raise ValueError(msg)
        return self
