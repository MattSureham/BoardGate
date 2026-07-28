"""Typed ingestion failures with source-safe diagnostics."""


class IngestionError(ValueError):
    """A classified input or archive rejection."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")
