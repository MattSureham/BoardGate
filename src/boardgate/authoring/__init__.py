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
    plan_authorization_sha256,
    request_sha256,
    revision_id,
)
from boardgate.authoring.models import (
    AppliedExcellonToolDiameterChange,
    AppliedGerberStandardApertureDiameterChange,
    ModificationRequest,
    ModificationResult,
    PayloadFileEvidence,
    RevisionValidationEvidence,
    SetExcellonToolDiameter,
    SetGerberStandardApertureDiameter,
)
from boardgate.authoring.plan_admission import (
    AdmittedAuthoringPlan,
    PlanAdmissionError,
    admit_authoring_plan,
)
from boardgate.authoring.plan_minting import mint_authoring_plan
from boardgate.authoring.plan_models import (
    PLAN_AUTHORIZATION_STATEMENT,
    AuthoringPlan,
    PlanAuthorization,
)
from boardgate.authoring.plan_request import (
    AuthoringPlanError,
    load_authoring_plan,
    load_authoring_plan_bytes,
)
from boardgate.authoring.request import (
    ModificationRequestError,
    load_modification_request,
    load_modification_request_bytes,
)

__all__ = [
    "PLAN_AUTHORIZATION_STATEMENT",
    "AdmittedAuthoringPlan",
    "AppliedExcellonToolDiameterChange",
    "AppliedGerberStandardApertureDiameterChange",
    "AppliedTwoLayerCouponGeneration",
    "AppliedTwoLayerCouponWithNpthGeneration",
    "AuthoringPlan",
    "AuthoringPlanError",
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
    "PlanAdmissionError",
    "PlanAuthorization",
    "RevisionValidationEvidence",
    "SetExcellonToolDiameter",
    "SetGerberStandardApertureDiameter",
    "admit_authoring_plan",
    "generation_id",
    "generation_operation_sha256",
    "generation_request_sha256",
    "load_authoring_plan",
    "load_authoring_plan_bytes",
    "load_generation_request",
    "load_generation_request_bytes",
    "load_modification_request",
    "load_modification_request_bytes",
    "mint_authoring_plan",
    "operation_sha256",
    "plan_authorization_sha256",
    "request_sha256",
    "revision_id",
]
