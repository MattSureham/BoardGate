"""Strict contracts and deterministic operations for PCB authoring revisions."""

from boardgate.authoring.generation_models import (
    AppliedTwoLayerCouponGeneration,
    AppliedTwoLayerCouponWithNpthGeneration,
    CouponHole,
    CouponNpthHole,
    GeneratedFileEvidence,
    GenerateTwoLayerCoupon,
    GenerateTwoLayerCouponWithNpth,
    GenerationRequest,
    GenerationResult,
)
from boardgate.authoring.generation_request import (
    GenerationRequestError,
    load_generation_request,
    load_generation_request_bytes,
)
from boardgate.authoring.identifiers import (
    generation_id,
    generation_operation_sha256,
    generation_request_sha256,
    operation_sha256,
    request_sha256,
    revision_id,
)
from boardgate.authoring.models import (
    AppliedExcellonToolDiameterChange,
    ModificationRequest,
    ModificationResult,
    PayloadFileEvidence,
    RevisionValidationEvidence,
    SetExcellonToolDiameter,
)
from boardgate.authoring.request import (
    ModificationRequestError,
    load_modification_request,
    load_modification_request_bytes,
)

__all__ = [
    "AppliedExcellonToolDiameterChange",
    "AppliedTwoLayerCouponGeneration",
    "AppliedTwoLayerCouponWithNpthGeneration",
    "CouponHole",
    "CouponNpthHole",
    "GenerateTwoLayerCoupon",
    "GenerateTwoLayerCouponWithNpth",
    "GeneratedFileEvidence",
    "GenerationRequest",
    "GenerationRequestError",
    "GenerationResult",
    "ModificationRequest",
    "ModificationRequestError",
    "ModificationResult",
    "PayloadFileEvidence",
    "RevisionValidationEvidence",
    "SetExcellonToolDiameter",
    "generation_id",
    "generation_operation_sha256",
    "generation_request_sha256",
    "load_generation_request",
    "load_generation_request_bytes",
    "load_modification_request",
    "load_modification_request_bytes",
    "operation_sha256",
    "request_sha256",
    "revision_id",
]
