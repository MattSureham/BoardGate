"""Same-filesystem staging and recoverable output replacement."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from types import TracebackType


class OutputError(ValueError):
    """A typed output policy or transaction failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")


def _subject(target: Path) -> str:
    return target.name or "<output>"


def preflight_output(target: Path, *, overwrite: bool) -> None:
    """Check output policy without mutating filesystem state."""
    subject = _subject(target)
    if target.is_symlink():
        raise OutputError(
            "OUTPUT_SYMLINK",
            subject,
            "symbolic-link output targets are rejected",
        )
    if not target.exists():
        return
    if not target.is_dir():
        raise OutputError(
            "OUTPUT_NOT_DIRECTORY",
            subject,
            "output target exists and is not a directory",
        )
    try:
        nonempty = next(target.iterdir(), None) is not None
    except OSError as error:
        raise OutputError(
            "OUTPUT_READ_ERROR",
            subject,
            "output directory could not be inspected",
        ) from error
    if nonempty and not overwrite:
        raise OutputError(
            "OUTPUT_NOT_EMPTY",
            subject,
            "output directory is not empty; pass --overwrite to replace it",
        )


class OutputTransaction:
    """Build artifacts beside their target, validate, then replace as a unit."""

    def __init__(self, target: Path, *, overwrite: bool) -> None:
        preflight_output(target, overwrite=overwrite)
        self.target = target
        self.overwrite = overwrite
        self._subject = _subject(target)
        self._staging: Path | None = None
        self._committed = False

    @property
    def staging_directory(self) -> Path:
        """Return the active private staging directory."""
        if self._staging is None:
            raise OutputError(
                "OUTPUT_TRANSACTION_STATE",
                self._subject,
                "output transaction has not started",
            )
        return self._staging

    def __enter__(self) -> OutputTransaction:
        try:
            self.target.parent.mkdir(parents=True, exist_ok=True)
            temporary = tempfile.mkdtemp(
                prefix=f".{self._subject}.staging-",
                dir=self.target.parent,
            )
        except OSError as error:
            raise OutputError(
                "OUTPUT_CREATE_ERROR",
                self._subject,
                "output staging directory could not be created",
            ) from error
        self._staging = Path(temporary)
        return self

    def commit(
        self,
        *,
        required_files: Iterable[str],
        validator: Callable[[Path], None],
    ) -> None:
        """Validate staged artifacts and atomically publish the directory."""
        staging = self.staging_directory
        for relative_name in required_files:
            artifact = staging / relative_name
            if not artifact.is_file():
                raise OutputError(
                    "OUTPUT_INCOMPLETE",
                    self._subject,
                    f"required artifact {relative_name!r} is missing",
                )
        try:
            validator(staging)
        except OutputError:
            raise
        except Exception as error:
            raise OutputError(
                "OUTPUT_VALIDATION_ERROR",
                self._subject,
                "staged artifacts failed validation",
            ) from error

        backup: Path | None = None
        try:
            if self.target.exists():
                backup_path = tempfile.mkdtemp(
                    prefix=f".{self._subject}.backup-",
                    dir=self.target.parent,
                )
                backup = Path(backup_path)
                backup.rmdir()
                self.target.replace(backup)
            staging.replace(self.target)
        except OSError as error:
            if backup is not None and backup.exists() and not self.target.exists():
                try:
                    backup.replace(self.target)
                except OSError as restore_error:
                    raise OutputError(
                        "OUTPUT_RESTORE_ERROR",
                        self._subject,
                        "publishing failed and the prior output could not be restored",
                    ) from restore_error
            raise OutputError(
                "OUTPUT_REPLACE_ERROR",
                self._subject,
                "staged output could not replace the target",
            ) from error
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)
        self._staging = None
        self._committed = True

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exception_type, exception, traceback
        if self._staging is not None:
            shutil.rmtree(self._staging, ignore_errors=True)
            self._staging = None
