"""Output resolution precedence tests (ADR 0004)."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from click.testing import CliRunner, Result

from boardgate.cli import main

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "rules" / "default.yaml"
FIXTURE = ROOT / "tests" / "fixtures" / "valid_minimal_board"


def invoke_inspect(*arguments: str) -> Result:
    return CliRunner().invoke(main, ["inspect", *arguments])


def copy_fixture(destination: Path) -> Path:
    shutil.copytree(FIXTURE, destination)
    return destination


def test_default_output_is_sibling_review_directory(tmp_path: Path) -> None:
    project = copy_fixture(tmp_path / "board")
    result = invoke_inspect(str(project), "--rules", str(RULES))
    assert result.exit_code == 0, result.output
    assert (tmp_path / "board.review-output" / "manifest.json").is_file()


def test_project_config_output_is_honored(tmp_path: Path) -> None:
    project = copy_fixture(tmp_path / "board")
    (project / "boardgate.toml").write_text(
        '[review]\noutput = "custom-review"\n',
        encoding="utf-8",
    )
    result = invoke_inspect(str(project), "--rules", str(RULES))
    assert result.exit_code == 0, result.output
    assert (tmp_path / "custom-review" / "manifest.json").is_file()


def test_cli_output_overrides_project_config(tmp_path: Path) -> None:
    project = copy_fixture(tmp_path / "board")
    (project / "boardgate.toml").write_text(
        '[review]\noutput = "custom-review"\n',
        encoding="utf-8",
    )
    explicit = tmp_path / "explicit"
    result = invoke_inspect(
        str(project),
        "--rules",
        str(RULES),
        "--output",
        str(explicit),
    )
    assert result.exit_code == 0, result.output
    assert (explicit / "manifest.json").is_file()
    assert not (tmp_path / "custom-review").exists()


def test_invalid_project_config_returns_two(tmp_path: Path) -> None:
    project = copy_fixture(tmp_path / "board")
    (project / "boardgate.toml").write_text("[review\n", encoding="utf-8")
    result = invoke_inspect(str(project), "--rules", str(RULES))
    assert result.exit_code == 2
    assert "PROJECT_CONFIG_ERROR" in result.output


def test_config_output_inside_input_is_rejected(tmp_path: Path) -> None:
    project = copy_fixture(tmp_path / "board")
    (project / "boardgate.toml").write_text(
        '[review]\noutput = "board/inside"\n',
        encoding="utf-8",
    )
    result = invoke_inspect(str(project), "--rules", str(RULES))
    assert result.exit_code == 2
    assert "OUTPUT_OVERLAPS_INPUT" in result.output
    assert not (project / "inside").exists()


def test_multiple_inputs_without_output_return_two(tmp_path: Path) -> None:
    project = copy_fixture(tmp_path / "board")
    files = sorted(path for path in project.iterdir() if path.is_file())
    result = invoke_inspect(
        *(str(path) for path in files),
        "--rules",
        str(RULES),
    )
    assert result.exit_code == 2
    assert "OUTPUT_REQUIRED" in result.output


def test_archive_input_default_uses_archive_stem(tmp_path: Path) -> None:
    project = copy_fixture(tmp_path / "board")
    archive = tmp_path / "board-pack.zip"
    with zipfile.ZipFile(archive, "w") as destination:
        for path in sorted(project.iterdir()):
            destination.write(path, path.name)
    result = invoke_inspect(str(archive), "--rules", str(RULES))
    assert result.exit_code == 0, result.output
    assert (tmp_path / "board-pack.review-output" / "manifest.json").is_file()
