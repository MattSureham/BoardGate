"""CLI baseline tests."""

from click.testing import CliRunner

from boardgate.cli import main


def test_version_is_available() -> None:
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert result.output.startswith("pcb-review, version ")
