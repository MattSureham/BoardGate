"""Draft 2020-12 schema generation for public boundary models."""

from boardgate.authoring.models import ModificationRequest, ModificationResult
from boardgate.config.models import RuleProfile
from boardgate.domain.base import StrictModel
from boardgate.domain.diagnostic import RunLogEvent
from boardgate.domain.finding import Finding
from boardgate.domain.project import PCBProject
from boardgate.domain.source import ProjectManifest
from boardgate.rules.models import ReviewResult

MODEL_SCHEMAS: tuple[tuple[str, type[StrictModel]], ...] = (
    ("modification-request.schema.json", ModificationRequest),
    ("modification-result.schema.json", ModificationResult),
    ("rule-profile.schema.json", RuleProfile),
    ("manifest.schema.json", ProjectManifest),
    ("project.schema.json", PCBProject),
    ("finding.schema.json", Finding),
    ("findings.schema.json", ReviewResult),
    ("run-log-event.schema.json", RunLogEvent),
)


def schema_document(model: type[StrictModel]) -> dict[str, object]:
    """Build one canonical public schema document."""
    document = model.model_json_schema(mode="serialization")
    document["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return document
