"""BoardGate command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import click
from pydantic import ValidationError

from boardgate import __version__
from boardgate.application import (
    FailOn,
    GenerationExecutionError,
    GenerationPublicationError,
    GenerationRun,
    GenerationService,
    ModificationExecutionError,
    ModificationInputError,
    ModificationPublicationError,
    ModificationRun,
    ModificationService,
    ReviewExitCode,
    ReviewPublicationError,
    ReviewRun,
    ReviewService,
)
from boardgate.application.output import (
    OutputError,
    preflight_output,
    resolve_output_directory,
)
from boardgate.application.review_service import reject_output_input_overlap
from boardgate.authoring.generation_models import GenerationRequest
from boardgate.authoring.generation_request import (
    GenerationRequestError,
    load_generation_request,
)
from boardgate.authoring.models import ModificationRequest
from boardgate.authoring.plan_admission import (
    PlanAdmissionError,
    admit_authoring_plan,
)
from boardgate.authoring.plan_minting import mint_authoring_plan
from boardgate.authoring.plan_request import (
    AuthoringPlanError,
    load_authoring_plan,
)
from boardgate.authoring.request import (
    ModificationRequestError,
    load_modification_request,
)
from boardgate.config import (
    ProjectConfigError,
    RuleProfileError,
    load_project_config,
    load_rule_profile,
)
from boardgate.domain.serialization import canonical_json
from boardgate.ingestion import IngestionError


class _UserInputError(click.ClickException):
    exit_code = 2


class _InternalError(click.ClickException):
    exit_code = 4


class _PipelineError(click.ClickException):
    exit_code = 3


def _raise_click_error(error: Exception) -> NoReturn:
    if isinstance(
        error,
        (
            IngestionError,
            AuthoringPlanError,
            GenerationRequestError,
            ModificationInputError,
            ModificationRequestError,
            OutputError,
            PlanAdmissionError,
            ProjectConfigError,
            RuleProfileError,
        ),
    ):
        raise _UserInputError(str(error)) from error
    if isinstance(error, (GenerationExecutionError, ModificationExecutionError)):
        raise _PipelineError(str(error)) from error
    if isinstance(error, (GenerationPublicationError, ModificationPublicationError)):
        raise _InternalError(str(error)) from error
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


def _emit_modification_summary(run: ModificationRun) -> None:
    click.echo(
        f"Revision {run.revision_id}: {run.base_project_id} -> "
        f"{run.output_project_id}; validation {run.overall_status.value}; "
        f"workspace written to {run.output_path}"
    )


def _emit_generation_summary(run: GenerationRun) -> None:
    click.echo(
        f"Generation {run.generation_id}: {run.output_project_id}; "
        f"validation {run.overall_status.value}; "
        f"workspace written to {run.output_path}"
    )


def _reject_authoring_control_inputs(
    inputs: tuple[Path, ...],
    controls: tuple[Path, ...],
) -> None:
    """Keep request/profile control files outside emitted design inputs."""
    for input_path in inputs:
        input_resolved = input_path.resolve()
        for control in controls:
            control_resolved = control.resolve()
            if control_resolved == input_resolved or (
                input_path.is_dir() and control_resolved.is_relative_to(input_resolved)
            ):
                raise ModificationInputError(
                    "MODIFICATION_CONTROL_INSIDE_INPUT",
                    control.name or "<control>",
                    "request and rule-profile files must be outside project inputs",
                )


@click.group()
@click.version_option(version=__version__, prog_name="pcb-review")
def main() -> None:
    """Review and deterministically author supported PCB manufacturing data."""


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
    type=click.Path(path_type=Path, file_okay=False),
    help=(
        "Artifact output directory. Defaults to boardgate.toml "
        "[review].output, then a sibling <INPUT>.review-output directory."
    ),
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
    output_path: Path | None,
    *,
    overwrite: bool,
    fail_on: str,
    log_level: str,
) -> None:
    """Safely inspect one PCB project from INPUTS."""
    try:
        configured_output: str | None = None
        if output_path is None and len(inputs) == 1 and inputs[0].is_dir():
            project_config = load_project_config(inputs[0])
            if project_config is not None:
                configured_output = project_config.review.output
        resolved_output = resolve_output_directory(
            inputs,
            output_path,
            configured_output,
        )
        preflight_output(resolved_output, overwrite=overwrite)
        reject_output_input_overlap((*inputs, rules_path), resolved_output)
        profile = load_rule_profile(rules_path)
        run = ReviewService().inspect(
            inputs,
            profile,
            resolved_output,
            overwrite=overwrite,
            fail_on=FailOn(fail_on.casefold()),
        )
    except (
        IngestionError,
        OSError,
        OutputError,
        ProjectConfigError,
        RuleProfileError,
    ) as error:
        _raise_click_error(error)
    except ReviewPublicationError as error:
        _raise_click_error(error)
    except Exception as error:  # pragma: no cover - defensive CLI boundary
        _raise_click_error(error)
    _emit_run_summary(run, log_level=log_level.casefold())
    if run.exit_code is not ReviewExitCode.SUCCESS:
        raise click.exceptions.Exit(run.exit_code)


@main.command()
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(path_type=Path),
)
@click.option(
    "--request",
    "request_path",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Strict JSON modification request bound to the input project.",
)
@click.option(
    "--plan",
    "plan_path",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Optional strict JSON authoring plan authorizing the exact request.",
)
@click.option(
    "--rules",
    "rules_path",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Explicit YAML or JSON manufacturing rule profile for validation.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(path_type=Path, file_okay=False),
    help="Atomic revision workspace; never written inside an input project.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Atomically replace an existing non-empty revision workspace.",
)
def modify(  # noqa: PLR0913
    inputs: tuple[Path, ...],
    request_path: Path,
    plan_path: Path | None,
    rules_path: Path,
    output_path: Path,
    *,
    overwrite: bool,
) -> None:
    """Apply one explicit supported operation, then independently review it."""
    try:
        preflight_output(output_path, overwrite=overwrite)
        controls: tuple[Path, ...] = (request_path, rules_path)
        if plan_path is not None:
            controls = (*controls, plan_path)
        _reject_authoring_control_inputs(inputs, controls)
        reject_output_input_overlap((*inputs, *controls), output_path)
        request = load_modification_request(request_path)
        if plan_path is not None:
            admit_authoring_plan(load_authoring_plan(plan_path), request)
        profile = load_rule_profile(rules_path)
        run = ModificationService().modify(
            inputs,
            request,
            profile,
            output_path,
            overwrite=overwrite,
        )
    except (
        IngestionError,
        AuthoringPlanError,
        ModificationExecutionError,
        ModificationInputError,
        ModificationPublicationError,
        ModificationRequestError,
        OSError,
        OutputError,
        PlanAdmissionError,
        RuleProfileError,
    ) as error:
        _raise_click_error(error)
    except Exception as error:  # pragma: no cover - defensive CLI boundary
        _raise_click_error(error)
    _emit_modification_summary(run)
    if run.exit_code is not ReviewExitCode.SUCCESS:
        raise click.exceptions.Exit(run.exit_code)


@main.command()
@click.option(
    "--request",
    "request_path",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Strict JSON generation requirements for one supported generator.",
)
@click.option(
    "--plan",
    "plan_path",
    type=click.Path(path_type=Path, dir_okay=False),
    help="Optional strict JSON authoring plan authorizing the exact request.",
)
@click.option(
    "--rules",
    "rules_path",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Explicit YAML or JSON manufacturing rule profile for validation.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(path_type=Path, file_okay=False),
    help="Atomic revision workspace; never contains the control files.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Atomically replace an existing non-empty revision workspace.",
)
def generate(
    request_path: Path,
    plan_path: Path | None,
    rules_path: Path,
    output_path: Path,
    *,
    overwrite: bool,
) -> None:
    """Emit one supported deterministic design, then independently review it."""
    try:
        preflight_output(output_path, overwrite=overwrite)
        controls: tuple[Path, ...] = (request_path, rules_path)
        if plan_path is not None:
            controls = (*controls, plan_path)
        reject_output_input_overlap(controls, output_path)
        request = load_generation_request(request_path)
        if plan_path is not None:
            admit_authoring_plan(load_authoring_plan(plan_path), request)
        profile = load_rule_profile(rules_path)
        run = GenerationService().generate(
            request,
            profile,
            output_path,
            overwrite=overwrite,
        )
    except (
        AuthoringPlanError,
        GenerationExecutionError,
        GenerationPublicationError,
        GenerationRequestError,
        OSError,
        OutputError,
        PlanAdmissionError,
        RuleProfileError,
    ) as error:
        _raise_click_error(error)
    except Exception as error:  # pragma: no cover - defensive CLI boundary
        _raise_click_error(error)
    _emit_generation_summary(run)
    if run.exit_code is not ReviewExitCode.SUCCESS:
        raise click.exceptions.Exit(run.exit_code)


@main.command()
@click.option(
    "--request",
    "request_path",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Strict JSON modification or generation request to authorize.",
)
@click.option(
    "--kind",
    "request_kind",
    required=True,
    type=click.Choice(("modification", "generation"), case_sensitive=False),
    help="Explicit request contract kind; there is no auto-detection fallback.",
)
@click.option(
    "--approver",
    required=True,
    help="Explicit approver identity bound into the authorization digest.",
)
@click.option(
    "--rationale",
    default="",
    help="Optional bounded prose recorded in the plan; never part of any digest.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(path_type=Path, dir_okay=False),
    help="Plan JSON output path; must end in .json.",
)
@click.option(
    "--overwrite",
    is_flag=True,
    help="Replace an existing plan file.",
)
def plan(  # noqa: PLR0913
    request_path: Path,
    request_kind: str,
    approver: str,
    rationale: str,
    output_path: Path,
    *,
    overwrite: bool,
) -> None:
    """Mint one authorized authoring plan for an exact admitted request."""
    try:
        request: ModificationRequest | GenerationRequest
        if request_kind.casefold() == "modification":
            request = load_modification_request(request_path)
        else:
            request = load_generation_request(request_path)
        if output_path.suffix != ".json":
            raise AuthoringPlanError(
                "AUTHORING_PLAN_FORMAT_ERROR",
                output_path.name or "<plan>",
                "plan output must be a .json file",
            )
        if output_path.resolve() == request_path.resolve():
            raise OutputError(
                "PLAN_OUTPUT_OVERLAPS_REQUEST",
                output_path.name or "<plan>",
                "plan output must be a different file than the request",
            )
        minted = mint_authoring_plan(
            request,
            approver=approver,
            rationale=rationale,
        )
        payload = f"{canonical_json(minted)}\n"
        if output_path.exists():
            if not overwrite:
                raise OutputError(
                    "PLAN_OUTPUT_EXISTS",
                    output_path.name or "<plan>",
                    "plan output already exists; pass --overwrite to replace it",
                )
            output_path.write_text(payload, encoding="utf-8")
        else:
            with output_path.open("x", encoding="utf-8") as stream:
                stream.write(payload)
    except (
        AuthoringPlanError,
        GenerationRequestError,
        ModificationRequestError,
        OSError,
        OutputError,
    ) as error:
        _raise_click_error(error)
    except ValidationError as error:
        raise _UserInputError(
            "PLAN_MINT_CONTRACT_ERROR: approver must be 1-200 characters and "
            "rationale at most 500 characters"
        ) from error
    except Exception as error:  # pragma: no cover - defensive CLI boundary
        _raise_click_error(error)
    click.echo(
        f"Plan {minted.operation_kind}/{minted.operation_version} "
        f"({minted.request_kind}) authorized by {minted.authorization.approver}; "
        f"written to {output_path}"
    )
