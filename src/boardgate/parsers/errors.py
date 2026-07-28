"""Typed parser failures."""


class ParserError(ValueError):
    """A source-safe parser or adapter failure."""

    def __init__(self, code: str, subject: str, detail: str) -> None:
        self.code = code
        self.subject = subject
        self.detail = detail
        super().__init__(f"{code}: {detail} [{subject}]")
