"""Strict per-project review configuration from ``boardgate.toml``."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import Field

from boardgate.domain.base import StrictModel

CONFIG_FILENAME = "boardgate.toml"
_MAX_CONFIG_BYTES = 16 * 1024


class ProjectConfigError(ValueError):
    """A source-safe project configuration failure."""


class ProjectReviewConfig(StrictModel):
    """Review-output defaults owned by one input project."""

    output: str = Field(min_length=1, max_length=512)


class ProjectConfig(StrictModel):
    """Top-level boardgate.toml contract."""

    review: ProjectReviewConfig


def load_project_config(input_dir: Path) -> ProjectConfig | None:
    """Return the validated project config, or None when no file exists."""
    candidate = input_dir / CONFIG_FILENAME
    if not candidate.exists():
        return None
    subject = candidate.name
    if candidate.is_symlink() or not candidate.is_file():
        raise ProjectConfigError(
            f"PROJECT_CONFIG_ERROR: {subject} is not a regular file"
        )
    try:
        size = candidate.stat().st_size
        if size > _MAX_CONFIG_BYTES:
            raise ProjectConfigError(
                f"PROJECT_CONFIG_ERROR: {subject} exceeds the size limit"
            )
        payload = tomllib.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ProjectConfigError(
            f"PROJECT_CONFIG_ERROR: {subject} could not be parsed"
        ) from error
    try:
        return ProjectConfig.model_validate(payload)
    except ValueError as error:
        raise ProjectConfigError(
            f"PROJECT_CONFIG_ERROR: {subject} failed validation"
        ) from error
