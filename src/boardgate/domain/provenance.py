"""Source provenance attached to parsed and derived domain objects."""

from pydantic import Field, model_validator

from boardgate.domain.base import VersionedModel

type JsonScalar = str | int | float | bool | None


class SourceSpan(VersionedModel):
    """Optional, evidence-backed location in a source file."""

    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    start_byte: int | None = Field(default=None, ge=0)
    end_byte: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "SourceSpan":
        """Require paired, ordered line and byte ranges."""
        if (self.start_line is None) != (self.end_line is None):
            msg = "line span must provide both start_line and end_line"
            raise ValueError(msg)
        if (self.start_byte is None) != (self.end_byte is None):
            msg = "byte span must provide both start_byte and end_byte"
            raise ValueError(msg)
        if (
            self.start_line is not None
            and self.end_line is not None
            and self.start_line > self.end_line
        ):
            msg = "start_line must not exceed end_line"
            raise ValueError(msg)
        if (
            self.start_byte is not None
            and self.end_byte is not None
            and self.start_byte > self.end_byte
        ):
            msg = "start_byte must not exceed end_byte"
            raise ValueError(msg)
        return self


class Provenance(VersionedModel):
    """Trace a domain object back to parser and source evidence."""

    source_file_id: str = Field(min_length=1)
    object_id: str | None = Field(default=None, min_length=1)
    parser: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    source_span: SourceSpan | None = None
    raw_coordinates: dict[str, JsonScalar] = Field(default_factory=dict)
    metadata: dict[str, JsonScalar] = Field(default_factory=dict)
