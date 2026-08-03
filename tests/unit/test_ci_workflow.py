"""Contracts for failure diagnostics in the GitHub Actions workflow."""

from pathlib import Path
from typing import Any, cast

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "ci.yml"


def test_viewer_browser_failures_upload_only_playwright_context() -> None:
    workflow = cast(
        dict[str, Any],
        yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8")),
    )
    assert workflow["permissions"] == {"contents": "read"}
    jobs = cast(dict[str, Any], workflow["jobs"])
    viewer_job = cast(dict[str, Any], jobs["viewer-browsers"])
    steps = cast(list[dict[str, Any]], viewer_job["steps"])

    e2e_step = next(step for step in steps if step.get("id") == "viewer_e2e")
    assert e2e_step == {
        "name": "Run viewer browser tests",
        "id": "viewer_e2e",
        "run": "npm run test:e2e",
    }

    upload_steps = [
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert len(upload_steps) == 1

    upload_step = upload_steps[0]
    assert steps.index(upload_step) == steps.index(e2e_step) + 1
    assert upload_step["name"] == "Upload Playwright failure context"
    assert upload_step["if"] == (
        "${{ failure() && steps.viewer_e2e.conclusion == 'failure' }}"
    )
    assert upload_step["continue-on-error"] is True
    assert upload_step["uses"] == (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    )
    assert upload_step["with"] == {
        "name": "viewer-browser-failure-${{ github.run_id }}-${{ github.run_attempt }}",
        "path": (
            "viewer/test-results/**/trace.zip\n"
            "viewer/test-results/**/error-context.md\n"
        ),
        "if-no-files-found": "warn",
        "retention-days": 7,
        "compression-level": 0,
        "overwrite": False,
        "include-hidden-files": False,
    }
