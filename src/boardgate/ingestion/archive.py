"""Preflighted, streaming ZIP expansion."""

from __future__ import annotations

import stat
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from boardgate.ingestion.errors import IngestionError
from boardgate.ingestion.limits import IngestionLimits
from boardgate.ingestion.paths import normalize_logical_path, path_collision_key

_CHUNK_BYTES = 1024 * 1024
_ARCHIVE_SUFFIXES = frozenset({".zip"})


class ExpansionBudget:
    """Shared file-count and expanded-byte budget across every input."""

    def __init__(self, limits: IngestionLimits) -> None:
        self._limits = limits
        self.file_count = 0
        self.total_bytes = 0

    def reserve(self, *, logical_path: str, size_bytes: int) -> None:
        """Reserve metadata-declared capacity before copying bytes."""
        next_count = self.file_count + 1
        if next_count > self._limits.max_file_count:
            raise IngestionError(
                "FILE_COUNT_LIMIT",
                logical_path,
                f"project exceeds {self._limits.max_file_count} files",
            )
        if size_bytes > self._limits.max_file_bytes:
            raise IngestionError(
                "FILE_SIZE_LIMIT",
                logical_path,
                f"file exceeds {self._limits.max_file_bytes} bytes",
            )
        next_total = self.total_bytes + size_bytes
        if next_total > self._limits.max_total_expanded_bytes:
            raise IngestionError(
                "EXPANDED_SIZE_LIMIT",
                logical_path,
                "project exceeds the total expanded-byte limit",
            )
        self.file_count = next_count
        self.total_bytes = next_total


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def _is_special_file(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    kind = stat.S_IFMT(mode)
    return kind not in {0, stat.S_IFREG, stat.S_IFDIR}


def validate_zip_entry(
    info: zipfile.ZipInfo,
    *,
    archive_subject: str,
    limits: IngestionLimits,
) -> str | None:
    """Validate one central-directory entry and return its logical path."""
    if info.flag_bits & 0x1:
        raise IngestionError(
            "ENCRYPTED_ARCHIVE_ENTRY",
            archive_subject,
            "encrypted ZIP entries are rejected",
        )
    if _is_symlink(info):
        raise IngestionError(
            "ARCHIVE_SYMLINK",
            archive_subject,
            "ZIP symlink entries are rejected",
        )
    if _is_special_file(info):
        raise IngestionError(
            "ARCHIVE_SPECIAL_FILE",
            archive_subject,
            "ZIP special-file entries are rejected",
        )
    if info.is_dir():
        return None
    logical_path = normalize_logical_path(info.filename, subject=archive_subject)
    if PurePosixPath(logical_path).suffix.casefold() in _ARCHIVE_SUFFIXES:
        raise IngestionError(
            "NESTED_ARCHIVE",
            logical_path,
            "nested archive entries are rejected",
        )
    compressed_size = info.compress_size
    ratio = (
        float("inf")
        if compressed_size == 0 and info.file_size > 0
        else info.file_size / max(compressed_size, 1)
    )
    if ratio > limits.max_compression_ratio:
        raise IngestionError(
            "COMPRESSION_RATIO_LIMIT",
            logical_path,
            f"entry exceeds the {limits.max_compression_ratio:g}:1 ratio limit",
        )
    return logical_path


def _ensure_no_path_tree_conflict(logical_paths: tuple[str, ...]) -> None:
    path_keys = {path_collision_key(path) for path in logical_paths}
    for logical_path in logical_paths:
        parents = PurePosixPath(logical_path).parents
        for parent in parents:
            if parent == PurePosixPath("."):
                continue
            if path_collision_key(parent.as_posix()) in path_keys:
                raise IngestionError(
                    "DUPLICATE_LOGICAL_PATH",
                    logical_path,
                    "a file conflicts with another file's parent directory",
                )


def expand_zip(
    archive_path: Path,
    destination: Path,
    *,
    limits: IngestionLimits,
    budget: ExpansionBudget,
    register_path: Callable[[str], None],
) -> tuple[tuple[str, Path, int], ...]:
    """Safely stream one ZIP into a private destination."""
    subject = archive_path.name
    try:
        archive_size = archive_path.stat().st_size
    except OSError as error:
        raise IngestionError(
            "INPUT_READ_ERROR",
            subject,
            "archive metadata could not be read",
        ) from error
    if archive_size > limits.max_archive_bytes:
        raise IngestionError(
            "ARCHIVE_SIZE_LIMIT",
            subject,
            f"archive exceeds {limits.max_archive_bytes} bytes",
        )
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as error:
        raise IngestionError(
            "INVALID_ARCHIVE",
            subject,
            "input is not a valid ZIP archive",
        ) from error

    with archive:
        entries: list[tuple[zipfile.ZipInfo, str]] = []
        local_keys: set[str] = set()
        for info in archive.infolist():
            logical_path = validate_zip_entry(
                info,
                archive_subject=subject,
                limits=limits,
            )
            if logical_path is None:
                continue
            collision_key = path_collision_key(logical_path)
            if collision_key in local_keys:
                raise IngestionError(
                    "DUPLICATE_LOGICAL_PATH",
                    logical_path,
                    "archive contains duplicate normalized paths",
                )
            local_keys.add(collision_key)
            entries.append((info, logical_path))
        _ensure_no_path_tree_conflict(tuple(path for _, path in entries))

        for info, logical_path in entries:
            budget.reserve(logical_path=logical_path, size_bytes=info.file_size)
            register_path(logical_path)

        extracted: list[tuple[str, Path, int]] = []
        for info, logical_path in sorted(entries, key=lambda item: item[1]):
            output_path = destination.joinpath(*PurePosixPath(logical_path).parts)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            actual_size = 0
            try:
                with archive.open(info) as source, output_path.open("xb") as target:
                    while chunk := source.read(_CHUNK_BYTES):
                        actual_size += len(chunk)
                        if (
                            actual_size > info.file_size
                            or actual_size > limits.max_file_bytes
                        ):
                            raise IngestionError(
                                "ARCHIVE_SIZE_MISMATCH",
                                logical_path,
                                "expanded bytes exceed declared or allowed size",
                            )
                        target.write(chunk)
            except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                raise IngestionError(
                    "ARCHIVE_READ_ERROR",
                    logical_path,
                    "ZIP entry could not be expanded",
                ) from error
            if actual_size != info.file_size:
                raise IngestionError(
                    "ARCHIVE_SIZE_MISMATCH",
                    logical_path,
                    "expanded bytes differ from declared size",
                )
            extracted.append((logical_path, output_path, actual_size))
    return tuple(extracted)
