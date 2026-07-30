"""Project configuration (boardgate.toml) loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from boardgate.config.project import (
    _MAX_CONFIG_BYTES,
    ProjectConfigError,
    load_project_config,
)


def test_missing_config_returns_none(tmp_path: Path) -> None:
    assert load_project_config(tmp_path) is None


def test_valid_config_returns_output(tmp_path: Path) -> None:
    (tmp_path / "boardgate.toml").write_text(
        '[review]\noutput = ".review-output"\n',
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config is not None
    assert config.review.output == ".review-output"


def test_unknown_field_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "boardgate.toml").write_text(
        '[review]\noutput = "x"\nextra = true\n',
        encoding="utf-8",
    )
    with pytest.raises(ProjectConfigError, match="PROJECT_CONFIG_ERROR"):
        load_project_config(tmp_path)


def test_missing_review_table_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "boardgate.toml").write_text("[other]\nx = 1\n", encoding="utf-8")
    with pytest.raises(ProjectConfigError, match="PROJECT_CONFIG_ERROR"):
        load_project_config(tmp_path)


def test_empty_output_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "boardgate.toml").write_text(
        '[review]\noutput = ""\n',
        encoding="utf-8",
    )
    with pytest.raises(ProjectConfigError, match="PROJECT_CONFIG_ERROR"):
        load_project_config(tmp_path)


def test_invalid_toml_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "boardgate.toml").write_text("[review\n", encoding="utf-8")
    with pytest.raises(ProjectConfigError, match="PROJECT_CONFIG_ERROR"):
        load_project_config(tmp_path)


def test_oversized_config_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "boardgate.toml").write_bytes(b"x" * (_MAX_CONFIG_BYTES + 1))
    with pytest.raises(ProjectConfigError, match="PROJECT_CONFIG_ERROR"):
        load_project_config(tmp_path)


def test_symlink_config_is_rejected(tmp_path: Path) -> None:
    real = tmp_path / "real.toml"
    real.write_text('[review]\noutput = "x"\n', encoding="utf-8")
    (tmp_path / "boardgate.toml").symlink_to(real)
    with pytest.raises(ProjectConfigError, match="PROJECT_CONFIG_ERROR"):
        load_project_config(tmp_path)
