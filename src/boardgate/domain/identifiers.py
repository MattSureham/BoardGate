"""Deterministic identifiers derived from canonical evidence."""

import hashlib
import json
from collections.abc import Mapping, Sequence

from boardgate.domain.finding import Measurement
from boardgate.domain.geometry import Point

type JsonValue = (
    bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
)


def _digest(prefix: str, payload: object) -> str:
    canonical = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    value = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{value}"


def source_file_id(logical_path: str, sha256: str) -> str:
    """Build a stable source identifier."""
    return _digest("src", {"logical_path": logical_path, "sha256": sha256})


def project_id(sources: Sequence[tuple[str, str]]) -> str:
    """Build a stable project identifier independent of input ordering."""
    normalized = [[path, digest] for path, digest in sorted(sources)]
    return _digest("prj", normalized)


def object_id(
    kind: str,
    source_id: str,
    parser_index: int,
    raw_signature: str,
) -> str:
    """Build a stable parser-object identifier."""
    return _digest(
        kind,
        {
            "parser_index": parser_index,
            "raw_signature": raw_signature,
            "source_file_id": source_id,
        },
    )


def finding_id(  # noqa: PLR0913
    *,
    rule_id: str,
    rule_version: str,
    profile_sha256: str,
    evidence_ids: Sequence[str],
    location: Point | None,
    measurement: Measurement | None,
) -> str:
    """Build a cross-run stable finding identifier."""
    location_payload: JsonValue = None
    if location is not None:
        dumped_location = location.model_dump(mode="json")
        location_payload = _json_mapping(dumped_location)
    measurement_payload: JsonValue = None
    if measurement is not None:
        dumped_measurement = measurement.model_dump(mode="json")
        measurement_payload = _json_mapping(dumped_measurement)
    return _digest(
        "fnd",
        {
            "evidence_ids": sorted(evidence_ids),
            "location": location_payload,
            "measurement": measurement_payload,
            "profile_sha256": profile_sha256,
            "rule_id": rule_id,
            "rule_version": rule_version,
        },
    )


def _json_mapping(value: Mapping[str, object]) -> dict[str, JsonValue]:
    """Narrow a model dump to the recursive JSON type after validation."""
    encoded = json.dumps(value, allow_nan=False, sort_keys=True)
    decoded: object = json.loads(encoded)
    if not isinstance(decoded, dict):
        msg = "expected a JSON object"
        raise TypeError(msg)
    return {str(key): _json_value(item) for key, item in decoded.items()}


def _json_value(value: object) -> JsonValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    msg = f"unsupported JSON value: {type(value).__name__}"
    raise TypeError(msg)
