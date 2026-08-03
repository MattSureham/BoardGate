"""Content-derived identifiers for deterministic authoring evidence."""

from __future__ import annotations

import hashlib
import json

from boardgate.authoring.generation_models import (
    GenerationOperation,
    GenerationRequest,
)
from boardgate.authoring.models import (
    ModificationRequest,
    SetExcellonToolDiameter,
)
from boardgate.domain.serialization import canonical_json


def request_sha256(request: ModificationRequest) -> str:
    """Hash the canonical request without filesystem or run-varying state."""
    return hashlib.sha256(canonical_json(request).encode("utf-8")).hexdigest()


def operation_sha256(operation: SetExcellonToolDiameter) -> str:
    """Hash executable fields while excluding non-semantic instruction prose."""
    payload = json.dumps(
        operation.model_dump(mode="json", exclude={"instruction"}),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def revision_id(
    *,
    base_project_id: str,
    operation_digest: str,
    output_project_id: str,
) -> str:
    """Build a stable revision ID from its immutable before/after evidence."""
    payload = json.dumps(
        {
            "base_project_id": base_project_id,
            "operation_sha256": operation_digest,
            "output_project_id": output_project_id,
        },
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"rev-{digest}"


def generation_request_sha256(request: GenerationRequest) -> str:
    """Hash the canonical requirements without filesystem or run-varying state."""
    return hashlib.sha256(canonical_json(request).encode("utf-8")).hexdigest()


def generation_operation_sha256(operation: GenerationOperation) -> str:
    """Hash executable fields while excluding non-semantic instruction prose."""
    payload = json.dumps(
        operation.model_dump(mode="json", exclude={"instruction"}),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generation_id(
    *,
    operation_digest: str,
    output_project_id: str,
) -> str:
    """Build a stable generation ID from its immutable evidence."""
    payload = json.dumps(
        {
            "operation_sha256": operation_digest,
            "output_project_id": output_project_id,
        },
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"gen-{digest}"


def plan_authorization_sha256(
    *,
    approver: str,
    statement: str,
    request_sha256: str,
) -> str:
    """Hash the explicit approval bound to one exact request digest."""
    payload = json.dumps(
        {
            "approver": approver,
            "request_sha256": request_sha256,
            "statement": statement,
        },
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
