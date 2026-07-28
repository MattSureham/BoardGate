"""Draft 2020-12 schema generation for public boundary models."""

from boardgate.config.models import RuleProfile
from boardgate.domain.base import StrictModel
from boardgate.domain.finding import Finding
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest

MODEL_SCHEMAS: tuple[tuple[str, type[StrictModel]], ...] = (
    ("rule-profile.schema.json", RuleProfile),
    ("manifest.schema.json", ProjectManifest),
    ("project.schema.json", PCBProject),
    ("finding.schema.json", Finding),
)


def schema_document(model: type[StrictModel]) -> dict[str, object]:
    """Build one canonical public schema document."""
    document = model.model_json_schema(mode="serialization")
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return document
