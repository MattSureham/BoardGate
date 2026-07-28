"""Stable project manifest tests."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import jsonschema

from boardgate.domain.enums import FileType, RiskMode
from boardgate.domain.identifiers import project_id
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion import build_manifest, discover_inputs, manifest_json

ROOT = Path(__file__).resolve().parents[3]

GERBER = b"%FSLAX46Y46*%\n%MOMM*%\n%ADD10C,0.2*%\nX0Y0D02*\nX1Y1D01*\nM02*\n"
DRILL = b"M48\nMETRIC,TZ\nT01C0.3\n%\nT01\nX1Y1\nM30\n"


def write_project(directory: Path) -> None:
    directory.mkdir()
    (directory / "board.gtl").write_bytes(GERBER)
    (directory / "drill.drl").write_bytes(DRILL)


def test_manifest_hashes_classifies_and_validates_schema(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_project(project)

    with discover_inputs([project]) as discovered:
        manifest = build_manifest(discovered)

    assert [source.file_type for source in manifest.source_files] == [
        FileType.GERBER,
        FileType.EXCELLON,
    ]
    expected_id = project_id(
        [
            ("board.gtl", hashlib.sha256(GERBER).hexdigest()),
            ("drill.drl", hashlib.sha256(DRILL).hexdigest()),
        ]
    )
    assert manifest.project_id == expected_id
    assert not manifest.uncertainties
    schema = json.loads((ROOT / "schemas/v1/manifest.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(manifest.model_dump(mode="json"))


def test_manifest_is_stable_across_directory_zip_and_input_order(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    write_project(project)
    archive = tmp_path / "project.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.write(project / "board.gtl", "board.gtl")
        output.write(project / "drill.drl", "drill.drl")

    with discover_inputs([project]) as discovered:
        directory_bytes = manifest_json(build_manifest(discovered))
    with discover_inputs([archive]) as discovered:
        archive_bytes = manifest_json(build_manifest(discovered))
    with discover_inputs([project / "drill.drl", project / "board.gtl"]) as discovered:
        file_bytes = manifest_json(build_manifest(discovered))

    assert directory_bytes == archive_bytes == file_bytes
    assert manifest_json(json_to_manifest(directory_bytes)) == directory_bytes


def json_to_manifest(payload: str) -> ProjectManifest:
    return ProjectManifest.model_validate_json(payload)


def test_unknown_and_conflicting_files_create_uncertainties(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "notes.bin").write_bytes(b"\x00\x01")
    (project / "wrong.gtl").write_bytes(DRILL)

    with discover_inputs([project]) as discovered:
        manifest = build_manifest(discovered)

    assert len(manifest.uncertainties) == 2
    assert {item.risk_mode for item in manifest.uncertainties} == {
        RiskMode.FILE_TYPE_UNKNOWN
    }
    conflict = next(
        item for item in manifest.uncertainties if item.subject == "wrong.gtl"
    )
    assert conflict.candidates == ("excellon", "gerber")
    assert "Conflicting" in conflict.summary
    assert conflict.evidence[0].source_span is None


def test_xlsx_is_staged_as_one_file_not_expanded(tmp_path: Path) -> None:
    workbook = tmp_path / "bom.xlsx"
    with zipfile.ZipFile(workbook, "w") as archive:
        archive.writestr("[Content_Types].xml", b"<Types/>")
        archive.writestr("xl/workbook.xml", b"<workbook/>")

    with discover_inputs([workbook]) as discovered:
        assert [item.logical_path for item in discovered.files] == ["bom.xlsx"]
        manifest = build_manifest(discovered)

    assert manifest.source_files[0].file_type is FileType.BOM_XLSX
