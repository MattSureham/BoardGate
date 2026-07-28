"""BoardGate command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import click

from boardgate import __version__
from boardgate.application.output import (
    OutputError,
    OutputTransaction,
    preflight_output,
)
from boardgate.config import RuleProfileError, load_rule_profile
from boardgate.domain.source import ProjectManifest
from boardgate.ingestion import (
    IngestionError,
    build_manifest,
    discover_inputs,
    manifest_json,
)


class _UserInputError(click.ClickException):
    exit_code = 2


class _PipelineError(click.ClickException):
    exit_code = 3


class _InternalError(click.ClickException):
    exit_code = 4


def _raise_click_error(error: Exception) -> NoReturn:
    if isinstance(error, (IngestionError, OutputError, RuleProfileError)):
        raise _UserInputError(str(error)) from error
    raise _InternalError(
        "INTERNAL_ERROR: review failed unexpectedly; no output was published"
    ) from error


def _reject_output_input_overlap(inputs: tuple[Path, ...], output: Path) -> None:
    output_resolved = output.resolve()
    for input_path in inputs:
        try:
            input_resolved = input_path.resolve()
        except OSError:
            continue
        if input_path.is_dir() and (
            output_resolved == input_resolved
            or output_resolved.is_relative_to(input_resolved)
        ):
            raise OutputError(
                "OUTPUT_OVERLAPS_INPUT",
                output.name or "<output>",
                "output directory must not be inside an input directory",
            )


def _validate_manifest_artifact(staging: Path) -> None:
    path = staging / "manifest.json"
    payload = path.read_text(encoding="utf-8")
    validated = ProjectManifest.model_validate_json(payload)
    if manifest_json(validated) != payload:
        raise OutputError(
            "OUTPUT_NONCANONICAL",
            path.name,
            "manifest.json is not in canonical artifact form",
        )


@click.group()
@click.version_option(version=__version__, prog_name="pcb-review")
def main() -> None:
    """Inspect PCB manufacturing data using deterministic checks."""


@main.command()
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--rules",
    "rules_path",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Explicit YAML or JSON manufacturing rule profile.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(path_type=Path, file_okay=False),
    help="Artifact output directory.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Atomically replace an existing non-empty output directory.",
)
@click.option(
    "--fail-on",
    type=click.Choice(("none", "blocker"), case_sensitive=False),
    default="none",
    show_default=True,
    help="Return exit code 1 when the completed review reaches this threshold.",
)
@click.option(
    "--log-level",
    type=click.Choice(("error", "warning", "info", "debug"), case_sensitive=False),
    default="info",
    show_default=True,
)
def inspect(  # noqa: PLR0913
    inputs: tuple[Path, ...],
    rules_path: Path,
    output_path: Path,
    *,
    overwrite: bool,
    fail_on: str,
    log_level: str,
) -> None:
    """Safely inspect one PCB project from INPUTS."""
    del fail_on, log_level
    try:
        preflight_output(output_path, overwrite=overwrite)
        _reject_output_input_overlap(inputs, output_path)
        load_rule_profile(rules_path)
        with discover_inputs(inputs) as discovered:
            manifest = build_manifest(discovered)
        with OutputTransaction(output_path, overwrite=overwrite) as transaction:
            destination = transaction.staging_directory / "manifest.json"
            destination.write_text(manifest_json(manifest), encoding="utf-8")
            transaction.commit(
                required_files=("manifest.json",),
                validator=_validate_manifest_artifact,
            )
    except (IngestionError, OSError, OutputError, RuleProfileError) as error:
        _raise_click_error(error)
    except Exception as error:  # pragma: no cover - defensive CLI boundary
        _raise_click_error(error)
    click.echo(
        f"Manifest {manifest.project_id} written to {output_path / 'manifest.json'}"
    )
