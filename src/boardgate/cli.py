"""BoardGate command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import click

from boardgate import __version__
from boardgate.application import (
    FailOn,
    ReviewExitCode,
    ReviewPublicationError,
    ReviewRun,
    ReviewService,
)
from boardgate.application.output import (
    OutputError,
    preflight_output,
)
from boardgate.application.review_service import reject_output_input_overlap
from boardgate.config import RuleProfileError, load_rule_profile
from boardgate.ingestion import IngestionError


class _UserInputError(click.ClickException):
    exit_code = 2


class _InternalError(click.ClickException):
    exit_code = 4


def _raise_click_error(error: Exception) -> NoReturn:
    if isinstance(error, (IngestionError, OutputError, RuleProfileError)):
        raise _UserInputError(str(error)) from error
    if isinstance(error, ReviewPublicationError):
        raise _InternalError(str(error)) from error
    raise _InternalError(
        "INTERNAL_ERROR: review failed unexpectedly; no output was published"
    ) from error


def _emit_run_summary(run: ReviewRun, *, log_level: str) -> None:
    if log_level in {"info", "debug"} or run.exit_code is not ReviewExitCode.SUCCESS:
        fallback = " (diagnostic fallback)" if run.fallback_used else ""
        click.echo(
            f"Review {run.project_id}: {run.overall_status.value}{fallback}; "
            f"artifacts written to {run.output_path}"
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
    try:
        preflight_output(output_path, overwrite=overwrite)
        reject_output_input_overlap((*inputs, rules_path), output_path)
        profile = load_rule_profile(rules_path)
        run = ReviewService().inspect(
            inputs,
            profile,
            output_path,
            overwrite=overwrite,
            fail_on=FailOn(fail_on.casefold()),
        )
    except (IngestionError, OSError, OutputError, RuleProfileError) as error:
        _raise_click_error(error)
    except ReviewPublicationError as error:
        _raise_click_error(error)
    except Exception as error:  # pragma: no cover - defensive CLI boundary
        _raise_click_error(error)
    _emit_run_summary(run, log_level=log_level.casefold())
    if run.exit_code is not ReviewExitCode.SUCCESS:
        raise click.exceptions.Exit(run.exit_code)
