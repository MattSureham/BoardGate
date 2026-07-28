"""Safe input discovery and ZIP expansion tests."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path

import pytest

from boardgate.ingestion import IngestionError, IngestionLimits, discover_inputs
from boardgate.ingestion.archive import validate_zip_entry


def write_zip(
    path: Path,
    entries: list[tuple[str, bytes]],
    *,
    compression: int = zipfile.ZIP_STORED,
) -> None:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, content in entries:
            archive.writestr(name, content)


def test_directory_is_staged_deterministically_and_cleaned(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "fab").mkdir(parents=True)
    (project / "fab" / "bottom.gbl").write_bytes(b"bottom")
    (project / "top.gtl").write_bytes(b"top")

    with discover_inputs([project]) as discovered:
        staging = discovered.staging_directory
        assert staging.exists()
        assert [item.logical_path for item in discovered.files] == [
            "fab/bottom.gbl",
            "top.gtl",
        ]
        assert [item.staged_path.read_bytes() for item in discovered.files] == [
            b"bottom",
            b"top",
        ]

    assert not staging.exists()


def test_zip_is_expanded_without_returning_the_archive(tmp_path: Path) -> None:
    archive = tmp_path / "project.zip"
    write_zip(
        archive,
        [("fab/top.gtl", b"top"), ("fab/drill.drl", b"drill")],
    )

    with discover_inputs([archive]) as discovered:
        assert [item.logical_path for item in discovered.files] == [
            "fab/drill.drl",
            "fab/top.gtl",
        ]
        assert {item.source_kind for item in discovered.files} == {"zip"}


@pytest.mark.parametrize(
    ("entry_name", "code"),
    [
        ("../escape.gtl", "UNSAFE_PATH"),
        ("/absolute.gtl", "UNSAFE_PATH"),
        ("C:/drive.gtl", "UNSAFE_PATH"),
        ("nested/project.zip", "NESTED_ARCHIVE"),
    ],
)
def test_zip_rejects_unsafe_entry_names(
    tmp_path: Path,
    entry_name: str,
    code: str,
) -> None:
    archive = tmp_path / "unsafe.zip"
    write_zip(archive, [(entry_name, b"bad")])

    with pytest.raises(IngestionError) as caught:
        with discover_inputs([archive]):
            pass

    assert caught.value.code == code


def test_zip_rejects_casefolded_duplicate_paths(tmp_path: Path) -> None:
    archive = tmp_path / "duplicate.zip"
    write_zip(archive, [("Top.GTL", b"a"), ("top.gtl", b"b")])

    with pytest.raises(IngestionError, match="DUPLICATE_LOGICAL_PATH"):
        with discover_inputs([archive]):
            pass


def test_zip_rejects_file_parent_conflict(tmp_path: Path) -> None:
    archive = tmp_path / "conflict.zip"
    write_zip(archive, [("fab", b"a"), ("fab/top.gtl", b"b")])

    with pytest.raises(IngestionError, match="DUPLICATE_LOGICAL_PATH"):
        with discover_inputs([archive]):
            pass


def test_zip_symlink_and_encryption_metadata_are_rejected() -> None:
    symlink = zipfile.ZipInfo("link.gtl")
    symlink.create_system = 3
    symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
    encrypted = zipfile.ZipInfo("secret.gtl")
    encrypted.flag_bits = 1
    limits = IngestionLimits()

    with pytest.raises(IngestionError, match="ARCHIVE_SYMLINK"):
        validate_zip_entry(
            symlink,
            archive_subject="project.zip",
            limits=limits,
        )
    with pytest.raises(IngestionError, match="ENCRYPTED_ARCHIVE_ENTRY"):
        validate_zip_entry(
            encrypted,
            archive_subject="project.zip",
            limits=limits,
        )


def test_compression_ratio_limit_is_checked_before_expansion(tmp_path: Path) -> None:
    archive = tmp_path / "ratio.zip"
    write_zip(
        archive,
        [("huge.gtl", b"0" * 20_000)],
        compression=zipfile.ZIP_DEFLATED,
    )

    with pytest.raises(IngestionError, match="COMPRESSION_RATIO_LIMIT"):
        with discover_inputs(
            [archive],
            limits=IngestionLimits(max_compression_ratio=2.0),
        ):
            pass


@pytest.mark.parametrize(
    ("limits", "entries", "code"),
    [
        (
            IngestionLimits(max_file_count=1),
            [("a.gtl", b"a"), ("b.gbl", b"b")],
            "FILE_COUNT_LIMIT",
        ),
        (
            IngestionLimits(max_file_bytes=1),
            [("a.gtl", b"aa")],
            "FILE_SIZE_LIMIT",
        ),
        (
            IngestionLimits(max_total_expanded_bytes=1),
            [("a.gtl", b"a"), ("b.gbl", b"b")],
            "EXPANDED_SIZE_LIMIT",
        ),
    ],
)
def test_expansion_budgets_are_enforced(
    tmp_path: Path,
    limits: IngestionLimits,
    entries: list[tuple[str, bytes]],
    code: str,
) -> None:
    archive = tmp_path / "limited.zip"
    write_zip(archive, entries)

    with pytest.raises(IngestionError) as caught:
        with discover_inputs([archive], limits=limits):
            pass

    assert caught.value.code == code


def test_archive_size_limit_uses_compressed_file_size(tmp_path: Path) -> None:
    archive = tmp_path / "archive.zip"
    write_zip(archive, [("a.gtl", b"a")])

    with pytest.raises(IngestionError, match="ARCHIVE_SIZE_LIMIT"):
        with discover_inputs(
            [archive],
            limits=IngestionLimits(max_archive_bytes=1),
        ):
            pass


def test_direct_symlink_is_rejected_and_path_is_not_disclosed(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.gtl"
    target.write_bytes(b"data")
    link = tmp_path / "link.gtl"
    link.symlink_to(target)

    with pytest.raises(IngestionError) as caught:
        with discover_inputs([link]):
            pass

    assert caught.value.code == "INPUT_SYMLINK"
    assert str(tmp_path) not in str(caught.value)


def test_multiple_inputs_share_collision_and_size_budgets(tmp_path: Path) -> None:
    first = tmp_path / "Top.GTL"
    second_directory = tmp_path / "other"
    second_directory.mkdir()
    second = second_directory / "top.gtl"
    first.write_bytes(b"a")
    second.write_bytes(b"b")

    with pytest.raises(IngestionError, match="DUPLICATE_LOGICAL_PATH"):
        with discover_inputs([first, second]):
            pass


def test_multiple_inputs_reject_file_directory_tree_conflict(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "project.zip"
    write_zip(archive, [("fab/top.gtl", b"a")])
    direct = tmp_path / "fab"
    direct.write_bytes(b"b")

    with pytest.raises(IngestionError, match="DUPLICATE_LOGICAL_PATH"):
        with discover_inputs([direct, archive]):
            pass


def test_missing_and_empty_inputs_are_typed(tmp_path: Path) -> None:
    with pytest.raises(IngestionError, match="NO_INPUTS"):
        with discover_inputs([]):
            pass
    with pytest.raises(IngestionError, match="INPUT_NOT_FOUND"):
        with discover_inputs([tmp_path / "missing.zip"]):
            pass
