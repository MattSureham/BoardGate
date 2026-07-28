"""Export deterministic Draft 2020-12 schemas for public boundary models."""

from __future__ import annotations

import json
from pathlib import Path

from boardgate.schemas import MODEL_SCHEMAS, schema_document

SCHEMA_DIRECTORY = Path(__file__).resolve().parents[1] / "schemas" / "v1"


def main() -> None:
    """Write all schemas in stable filename and JSON-key order."""
    SCHEMA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for filename, model in MODEL_SCHEMAS:
        destination = SCHEMA_DIRECTORY / filename
        destination.write_text(
            json.dumps(
                schema_document(model),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
