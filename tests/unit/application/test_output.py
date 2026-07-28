"""Recoverable output transaction tests."""

from pathlib import Path

import pytest

from boardgate.application.output import (
    OutputError,
    OutputTransaction,
    preflight_output,
)


def validate_text(staging: Path) -> None:
    if (staging / "artifact.txt").read_text() != "new":
        raise ValueError


def test_transaction_publishes_validated_directory(tmp_path: Path) -> None:
    target = tmp_path / "artifacts"

    with OutputTransaction(target, overwrite=False) as transaction:
        (transaction.staging_directory / "artifact.txt").write_text("new")
        transaction.commit(
            required_files=("artifact.txt",),
            validator=validate_text,
        )

    assert (target / "artifact.txt").read_text() == "new"
    assert not list(tmp_path.glob(".artifacts.*-*"))


def test_nonempty_output_requires_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "artifacts"
    target.mkdir()
    (target / "old.txt").write_text("old")

    with pytest.raises(OutputError, match="OUTPUT_NOT_EMPTY"):
        preflight_output(target, overwrite=False)

    assert (target / "old.txt").read_text() == "old"


def test_overwrite_replaces_complete_directory(tmp_path: Path) -> None:
    target = tmp_path / "artifacts"
    target.mkdir()
    (target / "old.txt").write_text("old")

    with OutputTransaction(target, overwrite=True) as transaction:
        (transaction.staging_directory / "artifact.txt").write_text("new")
        transaction.commit(
            required_files=("artifact.txt",),
            validator=validate_text,
        )

    assert not (target / "old.txt").exists()
    assert (target / "artifact.txt").read_text() == "new"
    assert not list(tmp_path.glob(".artifacts.backup-*"))


def test_validation_failure_preserves_old_output(tmp_path: Path) -> None:
    target = tmp_path / "artifacts"
    target.mkdir()
    (target / "old.txt").write_text("old")

    with pytest.raises(OutputError, match="OUTPUT_VALIDATION_ERROR"):
        with OutputTransaction(target, overwrite=True) as transaction:
            (transaction.staging_directory / "artifact.txt").write_text("bad")
            transaction.commit(
                required_files=("artifact.txt",),
                validator=validate_text,
            )

    assert (target / "old.txt").read_text() == "old"
    assert not list(tmp_path.glob(".artifacts.staging-*"))


def test_publish_failure_restores_old_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "artifacts"
    target.mkdir()
    (target / "old.txt").write_text("old")
    original_replace = Path.replace

    def fail_staging_replace(source: Path, destination: Path) -> Path:
        if ".staging-" in source.name:
            raise OSError
        return original_replace(source, destination)

    monkeypatch.setattr(Path, "replace", fail_staging_replace)

    with pytest.raises(OutputError, match="OUTPUT_REPLACE_ERROR"):
        with OutputTransaction(target, overwrite=True) as transaction:
            (transaction.staging_directory / "artifact.txt").write_text("new")
            transaction.commit(
                required_files=("artifact.txt",),
                validator=validate_text,
            )

    assert (target / "old.txt").read_text() == "old"
    assert not list(tmp_path.glob(".artifacts.backup-*"))


def test_missing_required_artifact_preserves_target(tmp_path: Path) -> None:
    target = tmp_path / "artifacts"

    with pytest.raises(OutputError, match="OUTPUT_INCOMPLETE"):
        with OutputTransaction(target, overwrite=False) as transaction:
            transaction.commit(
                required_files=("artifact.txt",),
                validator=validate_text,
            )

    assert not target.exists()


def test_output_file_and_symlink_are_rejected(tmp_path: Path) -> None:
    target_file = tmp_path / "artifacts"
    target_file.write_text("not a directory")
    link = tmp_path / "link"
    link.symlink_to(target_file)

    with pytest.raises(OutputError, match="OUTPUT_NOT_DIRECTORY"):
        preflight_output(target_file, overwrite=True)
    with pytest.raises(OutputError, match="OUTPUT_SYMLINK"):
        preflight_output(link, overwrite=True)
