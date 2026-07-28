"""Shared strict model configuration and schema constants."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

SchemaVersion = Literal["1.0"]
SCHEMA_VERSION: SchemaVersion = "1.0"


class StrictModel(BaseModel):
    """Base for persisted models that reject ambiguous input."""

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        frozen=True,
        strict=True,
    )


class VersionedModel(StrictModel):
    """Strict model carrying the public schema version."""

    schema_version: SchemaVersion = SCHEMA_VERSION
