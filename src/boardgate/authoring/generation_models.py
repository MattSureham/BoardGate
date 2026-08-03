"""Versioned public contracts for deterministic two-layer coupon generation."""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from typing import Annotated, Literal, Self, cast

from pydantic import Discriminator, Field, Tag, field_validator, model_validator

from boardgate.authoring.models import RevisionValidationEvidence
from boardgate.domain.base import VersionedModel
from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.paths import normalize_logical_path

_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_PROJECT_ID_PATTERN = r"^prj-[0-9a-f]{16}$"
_GENERATION_ID_PATTERN = r"^gen-[0-9a-f]{16}$"
_DRILL_ID_PATTERN = r"^drill-[0-9a-f]{16}$"
_EMISSION_QUANTUM = Decimal("0.000001")
MIN_COUPON_DIMENSION_MM = 1.0
MAX_COUPON_DIMENSION_MM = 500.0
MAX_COUPON_FEATURE_MM = 500.0
MAX_COUPON_HOLES = 1024
MAX_COUPON_TRACES = 4096
GENERATION_OPERATION_KEYS = frozenset(
    {
        ("generate_two_layer_coupon", "1.0"),
        ("generate_two_layer_coupon_with_npth", "1.0"),
    }
)
GENERATION_DISCLAIMER = (
    "This revision records a deterministic generation from structured "
    "requirements and an independent BoardGate review; it does not guarantee "
    "manufacturability or replace fabricator and engineer approval."
)


def _validate_safe_logical_path(value: str) -> str:
    """Reject paths that cannot identify one immutable bundle member."""
    try:
        normalized = normalize_logical_path(value, subject="<logical-path>")
    except IngestionError as error:
        msg = "logical path must be a normalized relative POSIX path"
        raise ValueError(msg) from error
    if normalized != value:
        msg = "logical path must be a normalized relative POSIX path"
        raise ValueError(msg)
    return value


def _require_emission_quantum(value: float) -> float:
    """Require exact representation at the 1e-6 mm emission quantum."""
    scaled = Decimal(str(value)) / _EMISSION_QUANTUM
    if scaled != scaled.to_integral_value():
        msg = "values must be exact multiples of the 0.000001 mm emission quantum"
        raise ValueError(msg)
    return value


def to_emission_nanometres(value: float) -> int:
    """Convert one quantum-validated millimetre value to exact integers."""
    return int(Decimal(str(value)) / _EMISSION_QUANTUM)


def _dimension_field() -> float:
    """Constrain board dimensions to the bounded writer envelope."""
    return cast(
        "float",
        Field(
            ge=MIN_COUPON_DIMENSION_MM,
            le=MAX_COUPON_DIMENSION_MM,
        ),
    )


class CouponHole(VersionedModel):
    """One explicit plated round hole with its explicit copper pad."""

    x_mm: float = Field(gt=0.0, le=MAX_COUPON_FEATURE_MM)
    y_mm: float = Field(gt=0.0, le=MAX_COUPON_FEATURE_MM)
    drill_diameter_mm: float = Field(gt=0.0, le=MAX_COUPON_FEATURE_MM)
    pad_diameter_mm: float = Field(gt=0.0, le=MAX_COUPON_FEATURE_MM)

    _x_quantum = field_validator("x_mm")(_require_emission_quantum)
    _y_quantum = field_validator("y_mm")(_require_emission_quantum)
    _drill_quantum = field_validator("drill_diameter_mm")(_require_emission_quantum)
    _pad_quantum = field_validator("pad_diameter_mm")(_require_emission_quantum)

    @model_validator(mode="after")
    def require_pad_larger_than_drill(self) -> Self:
        """Reject geometrically impossible pad/drill combinations."""
        if to_emission_nanometres(self.pad_diameter_mm) <= to_emission_nanometres(
            self.drill_diameter_mm
        ):
            msg = "pad_diameter_mm must be larger than drill_diameter_mm"
            raise ValueError(msg)
        return self


class CouponNpthHole(VersionedModel):
    """One explicit non-plated round hole without an implied copper pad."""

    x_mm: float = Field(gt=0.0, le=MAX_COUPON_FEATURE_MM)
    y_mm: float = Field(gt=0.0, le=MAX_COUPON_FEATURE_MM)
    drill_diameter_mm: float = Field(gt=0.0, le=MAX_COUPON_FEATURE_MM)

    _x_quantum = field_validator("x_mm")(_require_emission_quantum)
    _y_quantum = field_validator("y_mm")(_require_emission_quantum)
    _drill_quantum = field_validator("drill_diameter_mm")(_require_emission_quantum)


class CouponTrace(VersionedModel):
    """One explicit straight copper trace with round-aperture endpoints."""

    x1_mm: float = Field(ge=0.0, le=MAX_COUPON_FEATURE_MM)
    y1_mm: float = Field(ge=0.0, le=MAX_COUPON_FEATURE_MM)
    x2_mm: float = Field(ge=0.0, le=MAX_COUPON_FEATURE_MM)
    y2_mm: float = Field(ge=0.0, le=MAX_COUPON_FEATURE_MM)
    width_mm: float = Field(gt=0.0, le=MAX_COUPON_FEATURE_MM)
    copper_layers: Literal["top", "bottom", "both"]

    _x1_quantum = field_validator("x1_mm")(_require_emission_quantum)
    _y1_quantum = field_validator("y1_mm")(_require_emission_quantum)
    _x2_quantum = field_validator("x2_mm")(_require_emission_quantum)
    _y2_quantum = field_validator("y2_mm")(_require_emission_quantum)
    _width_quantum = field_validator("width_mm")(_require_emission_quantum)

    @model_validator(mode="after")
    def require_positive_length(self) -> Self:
        """Reject degenerate traces the writer cannot draw."""
        if to_emission_nanometres(self.x1_mm) == to_emission_nanometres(
            self.x2_mm
        ) and to_emission_nanometres(self.y1_mm) == to_emission_nanometres(self.y2_mm):
            msg = "trace endpoints must differ"
            raise ValueError(msg)
        return self


def _require_circle_inside_board(  # noqa: PLR0913
    *,
    x_nm: int,
    y_nm: int,
    diameter_nm: int,
    width_nm: int,
    height_nm: int,
    subject: str,
) -> None:
    if (
        2 * x_nm < diameter_nm
        or 2 * x_nm + diameter_nm > 2 * width_nm
        or 2 * y_nm < diameter_nm
        or 2 * y_nm + diameter_nm > 2 * height_nm
    ):
        msg = f"each {subject} circle must fit inside the board outline"
        raise ValueError(msg)


def _require_non_overlapping_drills(
    positions: list[tuple[int, int, int]],
) -> None:
    for index, (x_first, y_first, drill_first) in enumerate(positions):
        for x_second, y_second, drill_second in positions[index + 1 :]:
            diameter_sum = drill_first + drill_second
            distance_squared = (x_first - x_second) ** 2 + (y_first - y_second) ** 2
            if 4 * distance_squared < diameter_sum**2:
                msg = "drill circles must not overlap"
                raise ValueError(msg)


def _require_trace_footprints_inside_board(
    traces: tuple[CouponTrace, ...],
    *,
    width_nm: int,
    height_nm: int,
) -> None:
    for trace in traces:
        trace_width_nm = to_emission_nanometres(trace.width_mm)
        for coordinate, axis_nm in (
            (trace.x1_mm, width_nm),
            (trace.x2_mm, width_nm),
            (trace.y1_mm, height_nm),
            (trace.y2_mm, height_nm),
        ):
            value_nm = to_emission_nanometres(coordinate)
            if (
                2 * value_nm < trace_width_nm
                or 2 * value_nm + trace_width_nm > 2 * axis_nm
            ):
                msg = (
                    "each round-aperture trace footprint must fit inside "
                    "the board outline"
                )
                raise ValueError(msg)


class GenerateTwoLayerCoupon(VersionedModel):
    """Bounded requirements for one metric two-layer rectangular coupon."""

    schema_version: Literal["1.0"]
    kind: Literal["generate_two_layer_coupon"] = "generate_two_layer_coupon"
    operation_version: Literal["1.0"]
    board_width_mm: float = _dimension_field()
    board_height_mm: float = _dimension_field()
    holes: tuple[CouponHole, ...] = Field(max_length=MAX_COUPON_HOLES)
    traces: tuple[CouponTrace, ...] = Field(max_length=MAX_COUPON_TRACES)
    instruction: str = Field(min_length=1, max_length=500)

    _width_quantum = field_validator("board_width_mm")(_require_emission_quantum)
    _height_quantum = field_validator("board_height_mm")(_require_emission_quantum)

    @model_validator(mode="after")
    def require_realizable_geometry(self) -> Self:
        """Reject holes the bounded writer cannot realize inside the outline."""
        width_nm = to_emission_nanometres(self.board_width_mm)
        height_nm = to_emission_nanometres(self.board_height_mm)
        positions: list[tuple[int, int, int]] = []
        for hole in self.holes:
            x_nm = to_emission_nanometres(hole.x_mm)
            y_nm = to_emission_nanometres(hole.y_mm)
            pad_nm = to_emission_nanometres(hole.pad_diameter_mm)
            _require_circle_inside_board(
                x_nm=x_nm,
                y_nm=y_nm,
                diameter_nm=pad_nm,
                width_nm=width_nm,
                height_nm=height_nm,
                subject="hole pad",
            )
            positions.append(
                (x_nm, y_nm, to_emission_nanometres(hole.drill_diameter_mm))
            )
        _require_non_overlapping_drills(positions)
        _require_trace_footprints_inside_board(
            self.traces,
            width_nm=width_nm,
            height_nm=height_nm,
        )
        return self


class GenerateTwoLayerCouponWithNpth(VersionedModel):
    """Bounded two-layer coupon with separate plated and NPTH payloads."""

    schema_version: Literal["1.0"]
    kind: Literal["generate_two_layer_coupon_with_npth"]
    operation_version: Literal["1.0"]
    board_width_mm: float = _dimension_field()
    board_height_mm: float = _dimension_field()
    plated_holes: tuple[CouponHole, ...] = Field(
        min_length=1,
        max_length=MAX_COUPON_HOLES,
    )
    non_plated_holes: tuple[CouponNpthHole, ...] = Field(
        min_length=1,
        max_length=MAX_COUPON_HOLES,
    )
    traces: tuple[CouponTrace, ...] = Field(max_length=MAX_COUPON_TRACES)
    instruction: str = Field(min_length=1, max_length=500)

    _width_quantum = field_validator("board_width_mm")(_require_emission_quantum)
    _height_quantum = field_validator("board_height_mm")(_require_emission_quantum)

    @model_validator(mode="after")
    def require_realizable_geometry(self) -> Self:
        """Prove the complete bounded mixed-drill coupon geometry."""
        if len(self.plated_holes) + len(self.non_plated_holes) > MAX_COUPON_HOLES:
            msg = (
                f"combined plated and non-plated holes cannot exceed {MAX_COUPON_HOLES}"
            )
            raise ValueError(msg)
        width_nm = to_emission_nanometres(self.board_width_mm)
        height_nm = to_emission_nanometres(self.board_height_mm)
        positions: list[tuple[int, int, int]] = []
        for plated_hole in self.plated_holes:
            x_nm = to_emission_nanometres(plated_hole.x_mm)
            y_nm = to_emission_nanometres(plated_hole.y_mm)
            _require_circle_inside_board(
                x_nm=x_nm,
                y_nm=y_nm,
                diameter_nm=to_emission_nanometres(plated_hole.pad_diameter_mm),
                width_nm=width_nm,
                height_nm=height_nm,
                subject="plated-hole pad",
            )
            positions.append(
                (
                    x_nm,
                    y_nm,
                    to_emission_nanometres(plated_hole.drill_diameter_mm),
                )
            )
        for non_plated_hole in self.non_plated_holes:
            x_nm = to_emission_nanometres(non_plated_hole.x_mm)
            y_nm = to_emission_nanometres(non_plated_hole.y_mm)
            drill_nm = to_emission_nanometres(non_plated_hole.drill_diameter_mm)
            _require_circle_inside_board(
                x_nm=x_nm,
                y_nm=y_nm,
                diameter_nm=drill_nm,
                width_nm=width_nm,
                height_nm=height_nm,
                subject="non-plated drill",
            )
            positions.append((x_nm, y_nm, drill_nm))
        _require_non_overlapping_drills(positions)
        _require_trace_footprints_inside_board(
            self.traces,
            width_nm=width_nm,
            height_nm=height_nm,
        )
        return self


def _request_operation_tag(value: object) -> str | None:
    """Dispatch exact kinds while preserving the legacy defaulted discriminator."""
    if isinstance(value, (GenerateTwoLayerCoupon, GenerateTwoLayerCouponWithNpth)):
        return value.kind
    if isinstance(value, Mapping):
        kind = value.get("kind")
        if isinstance(kind, str):
            return kind
        if "holes" in value:
            return "generate_two_layer_coupon"
    return None


type GenerationOperation = Annotated[
    Annotated[GenerateTwoLayerCoupon, Tag("generate_two_layer_coupon")]
    | Annotated[
        GenerateTwoLayerCouponWithNpth,
        Tag("generate_two_layer_coupon_with_npth"),
    ],
    Discriminator(_request_operation_tag),
    Field(
        json_schema_extra={
            "discriminator": {
                "propertyName": "kind",
                "mapping": {
                    "generate_two_layer_coupon": ("#/$defs/GenerateTwoLayerCoupon"),
                    "generate_two_layer_coupon_with_npth": (
                        "#/$defs/GenerateTwoLayerCouponWithNpth"
                    ),
                },
            }
        }
    ),
]


class GenerationRequest(VersionedModel):
    """One canonical, explicitly authorized generation requirements document."""

    schema_version: Literal["1.0"]
    operation: GenerationOperation


class GeneratedFileEvidence(VersionedModel):
    """Digest evidence for one emitted design file."""

    logical_path: str = Field(min_length=1, max_length=1024)
    sha256: str = Field(pattern=_SHA256_PATTERN)
    size_bytes: int = Field(ge=0)

    _safe_payload_path = field_validator("logical_path")(_validate_safe_logical_path)


class AppliedTwoLayerCouponGeneration(VersionedModel):
    """Auditable evidence for one emitted two-layer coupon payload set."""

    kind: Literal["generate_two_layer_coupon"] = "generate_two_layer_coupon"
    operation_version: Literal["1.0"] = "1.0"
    adapter_id: Literal["boardgate-two-layer-coupon-writer"] = (
        "boardgate-two-layer-coupon-writer"
    )
    adapter_policy_version: Literal["1.0"] = "1.0"
    board_width_mm: float = _dimension_field()
    board_height_mm: float = _dimension_field()
    hole_count: int = Field(ge=0, le=MAX_COUPON_HOLES)
    tool_count: int = Field(ge=0, le=MAX_COUPON_HOLES)
    trace_count: int = Field(ge=0, le=MAX_COUPON_TRACES)
    drill_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_applied_generation(self) -> Self:
        """Keep emitted-feature evidence internally consistent."""
        if len(self.drill_ids) != self.hole_count:
            msg = "drill_ids must record exactly one ID per generated hole"
            raise ValueError(msg)
        if len(set(self.drill_ids)) != len(self.drill_ids):
            msg = "drill_ids must be unique"
            raise ValueError(msg)
        if tuple(sorted(self.drill_ids)) != self.drill_ids:
            msg = "drill_ids must be sorted"
            raise ValueError(msg)
        if any(
            re.fullmatch(_DRILL_ID_PATTERN, value) is None for value in self.drill_ids
        ):
            msg = "drill_ids must be stable BoardGate drill IDs"
            raise ValueError(msg)
        if (self.tool_count == 0) != (self.hole_count == 0):
            msg = "tool_count must be zero exactly when no holes are generated"
            raise ValueError(msg)
        if self.tool_count > self.hole_count:
            msg = "tool_count cannot exceed hole_count"
            raise ValueError(msg)
        return self


class AppliedTwoLayerCouponWithNpthGeneration(VersionedModel):
    """Evidence for one mixed plated/non-plated coupon payload set."""

    kind: Literal["generate_two_layer_coupon_with_npth"]
    operation_version: Literal["1.0"]
    adapter_id: Literal["boardgate-two-layer-coupon-writer"] = (
        "boardgate-two-layer-coupon-writer"
    )
    adapter_policy_version: Literal["1.1"] = "1.1"
    board_width_mm: float = _dimension_field()
    board_height_mm: float = _dimension_field()
    plated_hole_count: int = Field(ge=1, le=MAX_COUPON_HOLES)
    plated_tool_count: int = Field(ge=1, le=MAX_COUPON_HOLES)
    non_plated_hole_count: int = Field(ge=1, le=MAX_COUPON_HOLES)
    non_plated_tool_count: int = Field(ge=1, le=MAX_COUPON_HOLES)
    trace_count: int = Field(ge=0, le=MAX_COUPON_TRACES)
    plated_drill_ids: tuple[str, ...]
    non_plated_drill_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_applied_generation(self) -> Self:
        """Keep both emitted drill populations exact and disjoint."""
        populations = (
            (
                "plated",
                self.plated_hole_count,
                self.plated_tool_count,
                self.plated_drill_ids,
            ),
            (
                "non_plated",
                self.non_plated_hole_count,
                self.non_plated_tool_count,
                self.non_plated_drill_ids,
            ),
        )
        for label, hole_count, tool_count, drill_ids in populations:
            if len(drill_ids) != hole_count:
                msg = f"{label}_drill_ids must record exactly one ID per generated hole"
                raise ValueError(msg)
            if len(set(drill_ids)) != len(drill_ids):
                msg = f"{label}_drill_ids must be unique"
                raise ValueError(msg)
            if tuple(sorted(drill_ids)) != drill_ids:
                msg = f"{label}_drill_ids must be sorted"
                raise ValueError(msg)
            if any(
                re.fullmatch(_DRILL_ID_PATTERN, value) is None for value in drill_ids
            ):
                msg = f"{label}_drill_ids must be stable BoardGate drill IDs"
                raise ValueError(msg)
            if tool_count > hole_count:
                msg = f"{label}_tool_count cannot exceed its hole count"
                raise ValueError(msg)
        if set(self.plated_drill_ids) & set(self.non_plated_drill_ids):
            msg = "plated and non-plated drill IDs must be disjoint"
            raise ValueError(msg)
        if self.plated_hole_count + self.non_plated_hole_count > MAX_COUPON_HOLES:
            msg = "combined applied hole count exceeds the generator limit"
            raise ValueError(msg)
        return self


def _applied_operation_tag(value: object) -> str | None:
    """Dispatch result kinds while preserving the legacy defaulted discriminator."""
    if isinstance(
        value,
        (AppliedTwoLayerCouponGeneration, AppliedTwoLayerCouponWithNpthGeneration),
    ):
        return value.kind
    if isinstance(value, Mapping):
        kind = value.get("kind")
        if isinstance(kind, str):
            return kind
        if "hole_count" in value:
            return "generate_two_layer_coupon"
    return None


type AppliedGenerationOperation = Annotated[
    Annotated[AppliedTwoLayerCouponGeneration, Tag("generate_two_layer_coupon")]
    | Annotated[
        AppliedTwoLayerCouponWithNpthGeneration,
        Tag("generate_two_layer_coupon_with_npth"),
    ],
    Discriminator(_applied_operation_tag),
    Field(
        json_schema_extra={
            "discriminator": {
                "propertyName": "kind",
                "mapping": {
                    "generate_two_layer_coupon": (
                        "#/$defs/AppliedTwoLayerCouponGeneration"
                    ),
                    "generate_two_layer_coupon_with_npth": (
                        "#/$defs/AppliedTwoLayerCouponWithNpthGeneration"
                    ),
                },
            }
        }
    ),
]


class GenerationResult(VersionedModel):
    """Deterministic evidence binding requirements, payload, and fresh review."""

    generation_id: str = Field(pattern=_GENERATION_ID_PATTERN)
    output_project_id: str = Field(pattern=_PROJECT_ID_PATTERN)
    request_sha256: str = Field(pattern=_SHA256_PATTERN)
    operation_sha256: str = Field(pattern=_SHA256_PATTERN)
    implementation_version: str = Field(min_length=1)
    operation: AppliedGenerationOperation
    payload_files: tuple[GeneratedFileEvidence, ...] = Field(min_length=1)
    validation: RevisionValidationEvidence
    disclaimer: str = Field(
        default=GENERATION_DISCLAIMER,
        min_length=1,
        max_length=500,
    )

    @field_validator("disclaimer")
    @classmethod
    def require_normative_disclaimer(cls, value: str) -> str:
        """Prevent generation evidence from claiming fabrication guarantees."""
        if value != GENERATION_DISCLAIMER:
            msg = "disclaimer must use the normative non-guarantee text"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_generation_evidence(self) -> Self:
        """Cross-check payload inventory and validation identities."""
        if self.validation.project_id != self.output_project_id:
            msg = "validation project_id must match output_project_id"
            raise ValueError(msg)
        paths = [item.logical_path for item in self.payload_files]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            msg = "payload_files must be unique and sorted by logical_path"
            raise ValueError(msg)
        return self
