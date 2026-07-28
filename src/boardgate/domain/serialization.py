"""Deterministic JSON serialization helpers."""

import json

from boardgate.domain.base import StrictModel


def canonical_json(model: StrictModel) -> str:
    """Serialize a strict model deterministically for hashing and artifacts."""
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
