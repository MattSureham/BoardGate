"""Checked-in public JSON Schema tests."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from boardgate.domain.base import StrictModel
from boardgate.schemas import MODEL_SCHEMAS, schema_document

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIRECTORY = ROOT / "schemas" / "v1"


@pytest.mark.parametrize(("filename", "model"), MODEL_SCHEMAS)
def test_checked_in_schema_is_current(
    filename: str,
    model: type[StrictModel],
) -> None:
    checked_in = json.loads((SCHEMA_DIRECTORY / filename).read_text())

    assert checked_in == schema_document(model)
    jsonschema.Draft202012Validator.check_schema(checked_in)
