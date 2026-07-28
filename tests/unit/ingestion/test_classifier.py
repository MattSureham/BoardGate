"""Evidence-preserving file classification tests."""

from pathlib import Path

import pytest

from boardgate.domain.enums import FileType
from boardgate.ingestion.classifier import classify_file

GERBER = b"""G04 BoardGate fixture*
%FSLAX46Y46*%
%MOMM*%
%TF.FileFunction,Copper,L1,Top*%
%TF.SameCoordinates,original*%
%ADD10C,0.200*%
D10*
X0Y0D02*
X1000000Y0D01*
M02*
"""
EXCELLON = b"""M48
METRIC,TZ
T01C0.300
%
T01
X1000Y2000
M30
"""


@pytest.mark.parametrize(
    ("filename", "content", "expected"),
    [
        ("board.gtl", GERBER, FileType.GERBER),
        ("board.txt", GERBER, FileType.GERBER),
        ("drill.drl", EXCELLON, FileType.EXCELLON),
        ("drill.txt", EXCELLON, FileType.EXCELLON),
        (
            "bom.csv",
            b"Reference,Quantity,Value,MPN\nR1,1,10k,ABC\n",
            FileType.BOM_CSV,
        ),
        (
            "positions.csv",
            b"Ref,PosX,PosY,Rotation,Side\nR1,1,2,0,top\n",
            FileType.PLACEMENT_CSV,
        ),
    ],
)
def test_content_and_name_classification(
    tmp_path: Path,
    filename: str,
    content: bytes,
    expected: FileType,
) -> None:
    path = tmp_path / filename
    path.write_bytes(content)

    result = classify_file(path, filename)

    assert result.file_type is expected
    assert not result.ambiguous
    assert result.candidates[0].evidence


def test_x2_evidence_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "board.gbr"
    path.write_bytes(GERBER)

    result = classify_file(path, "board.gbr")
    evidence = result.candidates[0].evidence

    assert "x2:file-function:Copper,L1,Top" in evidence
    assert "x2:same-coordinates:original" in evidence


def test_conflicting_strong_content_and_extension_is_unknown(
    tmp_path: Path,
) -> None:
    path = tmp_path / "misnamed.gtl"
    path.write_bytes(EXCELLON)

    result = classify_file(path, "misnamed.gtl")

    assert result.file_type is FileType.UNKNOWN
    assert result.ambiguous
    assert {candidate.file_type for candidate in result.candidates} == {
        FileType.EXCELLON,
        FileType.GERBER,
    }


def test_csv_with_bom_and_placement_columns_remains_ambiguous(
    tmp_path: Path,
) -> None:
    path = tmp_path / "combined.csv"
    path.write_bytes(b"Ref,Value,PosX,PosY,Rotation\nR1,10k,1,2,0\n")

    result = classify_file(path, "combined.csv")

    assert result.file_type is FileType.UNKNOWN
    assert result.ambiguous


def test_unknown_binary_has_explicit_unknown_candidate(tmp_path: Path) -> None:
    path = tmp_path / "readme.bin"
    path.write_bytes(b"\x00\x01\x02")

    result = classify_file(path, "readme.bin")

    assert result.file_type is FileType.UNKNOWN
    assert result.candidates[0].file_type is FileType.UNKNOWN
    assert not result.ambiguous


def test_default_profiles_are_classified_by_structure(tmp_path: Path) -> None:
    yaml_path = tmp_path / "factory.yml"
    yaml_path.write_text(
        "schema_version: '1.0'\nprofile: {}\nfabrication: {}\nrules: {}\n"
    )
    json_path = tmp_path / "factory.json"
    json_path.write_text(
        '{"schema_version":"1.0","profile":{},"fabrication":{},"rules":{}}'
    )

    assert classify_file(yaml_path, yaml_path.name).file_type is FileType.RULES_YAML
    assert classify_file(json_path, json_path.name).file_type is FileType.RULES_JSON
