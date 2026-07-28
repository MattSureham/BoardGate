"""Minimal end-to-end inspect CLI tests."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import jsonschema
from click.testing import CliRunner, Result

from boardgate.cli import main

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "rules" / "default.yaml"
SCHEMA = json.loads((ROOT / "schemas" / "v1" / "manifest.schema.json").read_text())
GERBER = b"%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.2*%\nX0Y0D02*\nX1Y1D01*\nM02*\n"
DRILL = b"M48\nMETRIC,TZ\nT01C0.3\n%\nT01\nX1Y1\nM30\n"


def make_project(path: Path) -> Path:
    path.mkdir()
    (path / "board.gtl").write_bytes(GERBER)
    (path / "drill.drl").write_bytes(DRILL)
    return path


def invoke_inspect(*arguments: str) -> Result:
    return CliRunner().invoke(main, ["inspect", *arguments])


def test_directory_inspect_emits_schema_valid_manifest(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    output = tmp_path / "output"

    result = invoke_inspect(
        str(project),
        "--rules",
        str(RULES),
        "--output",
        str(output),
    )

    assert result.exit_code == 0, result.output
    assert [path.name for path in output.iterdir()] == ["manifest.json"]
    payload = json.loads((output / "manifest.json").read_text())
    jsonschema.Draft202012Validator(SCHEMA).validate(payload)
    assert "Manifest prj-" in result.output


def test_zip_and_separate_files_have_identical_output(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    archive = tmp_path / "project.zip"
    with zipfile.ZipFile(archive, "w") as destination:
        destination.write(project / "board.gtl", "board.gtl")
        destination.write(project / "drill.drl", "drill.drl")
    zip_output = tmp_path / "zip-output"
    files_output = tmp_path / "files-output"

    zip_result = invoke_inspect(
        str(archive),
        "--rules",
        str(RULES),
        "--output",
        str(zip_output),
    )
    files_result = invoke_inspect(
        str(project / "drill.drl"),
        str(project / "board.gtl"),
        "--rules",
        str(RULES),
        "--output",
        str(files_output),
    )

    assert zip_result.exit_code == files_result.exit_code == 0
    assert (zip_output / "manifest.json").read_bytes() == (
        files_output / "manifest.json"
    ).read_bytes()


def test_nonempty_output_is_preserved_without_overwrite(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    output = tmp_path / "output"
    output.mkdir()
    old = output / "old.txt"
    old.write_text("keep")

    result = invoke_inspect(
        str(project),
        "--rules",
        str(RULES),
        "--output",
        str(output),
    )

    assert result.exit_code == 2
    assert "OUTPUT_NOT_EMPTY" in result.output
    assert old.read_text() == "keep"


def test_overwrite_replaces_old_output(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")
    output = tmp_path / "output"
    output.mkdir()
    (output / "old.txt").write_text("old")

    result = invoke_inspect(
        str(project),
        "--rules",
        str(RULES),
        "--output",
        str(output),
        "--overwrite",
    )

    assert result.exit_code == 0, result.output
    assert not (output / "old.txt").exists()
    assert (output / "manifest.json").is_file()


def test_invalid_rules_and_input_return_exit_two_without_host_path(
    tmp_path: Path,
) -> None:
    project = make_project(tmp_path / "project")
    invalid_rules = tmp_path / "invalid.yaml"
    invalid_rules.write_text("schema_version: nope\n")
    output = tmp_path / "output"

    invalid_result = invoke_inspect(
        str(project),
        "--rules",
        str(invalid_rules),
        "--output",
        str(output),
    )
    missing_result = invoke_inspect(
        str(tmp_path / "missing.zip"),
        "--rules",
        str(RULES),
        "--output",
        str(output),
    )

    assert invalid_result.exit_code == missing_result.exit_code == 2
    assert "PROFILE_VALIDATION_ERROR" in invalid_result.output
    assert "INPUT_NOT_FOUND" in missing_result.output
    assert str(tmp_path) not in invalid_result.output
    assert str(tmp_path) not in missing_result.output
    assert not output.exists()


def test_output_inside_input_is_rejected(tmp_path: Path) -> None:
    project = make_project(tmp_path / "project")

    result = invoke_inspect(
        str(project),
        "--rules",
        str(RULES),
        "--output",
        str(project / "artifacts"),
    )

    assert result.exit_code == 2
    assert "OUTPUT_OVERLAPS_INPUT" in result.output


def test_cli_contract_requires_inputs_rules_and_output() -> None:
    result = invoke_inspect()

    assert result.exit_code == 2
    assert "Missing argument 'INPUTS...'" in result.output
