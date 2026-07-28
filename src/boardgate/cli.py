"""BoardGate command-line interface."""

import click

from boardgate import __version__


@click.group()
@click.version_option(version=__version__, prog_name="pcb-review")
def main() -> None:
    """Inspect PCB manufacturing data using deterministic checks."""
