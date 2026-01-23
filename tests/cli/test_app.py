"""Tests for CLI entry point."""

from click.testing import CliRunner

from mlg.cli.app import cli, main
from mlg.version import VERSION


def test_cli_version_option() -> None:
    """Test that --version flag prints version."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert VERSION in result.output


def test_cli_help_option() -> None:
    """Test that --help flag shows help text."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "MLG-CLI" in result.output or "mlg" in result.output.lower()
    assert "--version" in result.output
    assert "--help" in result.output


def test_cli_default_invocation() -> None:
    """Test that CLI can be invoked without arguments."""
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert result.exit_code == 0
    assert "MLG-CLI" in result.output
    assert "Interactive mode not yet implemented" in result.output


def test_cli_with_prompt_option() -> None:
    """Test headless mode with --prompt option."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--prompt", "Hello world"])
    assert result.exit_code == 0
    assert "Prompt: Hello world" in result.output
    assert "Not yet implemented" in result.output


def test_cli_with_short_prompt_option() -> None:
    """Test headless mode with -p option."""
    runner = CliRunner()
    result = runner.invoke(cli, ["-p", "Test prompt"])
    assert result.exit_code == 0
    assert "Prompt: Test prompt" in result.output


def test_main_function() -> None:
    """Test that main() function invokes the CLI."""
    runner = CliRunner()
    # Test that main() is callable and works
    # Since main() just calls cli() with sys.argv, we test via subprocess
    # which is already covered in test_main.py
    assert callable(main)

    # Also verify cli works through runner
    result = runner.invoke(cli, [], standalone_mode=False)
    assert result.exit_code == 0


def test_main_function_via_import() -> None:
    """Test main() can be imported and is the expected function."""
    from mlg.cli.app import main as imported_main

    assert imported_main is main
    assert main.__doc__ == "Main entry point for the CLI."
