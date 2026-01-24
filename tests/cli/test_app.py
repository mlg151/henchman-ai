"""Tests for CLI entry point."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from henchman.cli.app import cli, main
from henchman.version import VERSION


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
    assert "Henchman-AI" in result.output or "mlg" in result.output.lower()
    assert "--version" in result.output
    assert "--help" in result.output


def test_cli_default_invocation() -> None:
    """Test that CLI can be invoked without arguments (interactive mode)."""
    runner = CliRunner()
    with patch("henchman.cli.app._run_interactive") as mock_run:
        mock_run.return_value = None
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_cli_with_prompt_option() -> None:
    """Test headless mode with --prompt option."""
    runner = CliRunner()
    with patch("henchman.cli.app._run_headless") as mock_run:
        mock_run.return_value = None
        result = runner.invoke(cli, ["--prompt", "Hello world"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        # Check prompt is passed
        call_args = mock_run.call_args
        assert call_args[0][0] == "Hello world"  # First positional arg


def test_cli_with_short_prompt_option() -> None:
    """Test headless mode with -p option."""
    runner = CliRunner()
    with patch("henchman.cli.app._run_headless") as mock_run:
        mock_run.return_value = None
        result = runner.invoke(cli, ["-p", "Test prompt"])
        assert result.exit_code == 0
        mock_run.assert_called_once()


def test_main_function() -> None:
    """Test that main() function invokes the CLI."""
    runner = CliRunner()
    assert callable(main)

    # Test cli works through runner
    with patch("henchman.cli.app._run_interactive"):
        result = runner.invoke(cli, [], standalone_mode=False)
        assert result.exit_code == 0


def test_main_function_via_import() -> None:
    """Test main() can be imported and is the expected function."""
    from henchman.cli.app import main as imported_main

    assert imported_main is main
    assert main.__doc__ == "Main entry point for the CLI."


class TestGetProvider:
    """Tests for _get_provider function."""

    def test_get_provider_from_env(self) -> None:
        """Test getting provider from environment variable."""
        from henchman.cli.app import _get_provider

        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"}):
            provider = _get_provider()
            assert provider is not None
            assert provider.name == "deepseek"

    def test_get_provider_from_mlg_api_key(self) -> None:
        """Test getting provider from HENCHMAN_API_KEY environment variable."""
        from henchman.cli.app import _get_provider

        with patch.dict("os.environ", {"HENCHMAN_API_KEY": "test-key"}, clear=True):
            provider = _get_provider()
            assert provider is not None
            assert provider.name == "deepseek"

    def test_get_provider_from_settings(self) -> None:
        """Test getting provider from settings file."""
        import os

        from henchman.cli.app import _get_provider

        # Create mock settings
        mock_settings = MagicMock()
        mock_settings.providers.default = "deepseek"
        mock_settings.providers.deepseek = MagicMock(api_key="settings-key", model="deepseek-chat")

        orig_environ = os.environ.copy()
        try:
            os.environ.clear()
            with patch("henchman.config.load_settings", return_value=mock_settings):
                provider = _get_provider()
                assert provider is not None
                assert provider.name == "deepseek"
        finally:
            os.environ.clear()
            os.environ.update(orig_environ)

    def test_get_provider_no_provider_settings(self) -> None:
        """Test that missing provider settings raises ClickException."""
        import os

        import click

        from henchman.cli.app import _get_provider

        # Create mock settings where provider_settings is None
        mock_settings = MagicMock()
        mock_settings.providers.default = "unknown_provider"
        # Make getattr return None for the provider
        mock_settings.providers.unknown_provider = None

        orig_environ = os.environ.copy()
        try:
            os.environ.clear()
            with (
                patch("henchman.config.load_settings", return_value=mock_settings),
                pytest.raises(click.ClickException),
            ):
                _get_provider()
        finally:
            os.environ.clear()
            os.environ.update(orig_environ)

    def test_get_provider_no_key_raises(self) -> None:
        """Test that missing API key raises ClickException."""
        import os

        import click

        from henchman.cli.app import _get_provider

        # Temporarily clear environment and mock load_settings to fail
        orig_environ = os.environ.copy()
        try:
            os.environ.clear()
            with (
                patch("henchman.config.load_settings", side_effect=Exception("No settings")),
                pytest.raises(click.ClickException),
            ):
                _get_provider()
        finally:
            os.environ.clear()
            os.environ.update(orig_environ)


class TestRunInteractive:
    """Tests for _run_interactive function."""

    def test_run_interactive_creates_repl(self) -> None:
        """Test that interactive mode creates and runs REPL."""
        from henchman.cli.app import _run_interactive

        mock_repl_instance = MagicMock()
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = "system prompt"
        mock_settings = MagicMock()

        with (
            patch("henchman.cli.app._get_provider") as mock_provider,
            patch("henchman.config.ContextLoader", return_value=mock_loader_instance),
            patch("henchman.config.load_settings", return_value=mock_settings),
            patch("henchman.cli.repl.Repl", return_value=mock_repl_instance) as mock_repl,
            patch("henchman.cli.app.anyio") as mock_anyio,
        ):
            mock_provider.return_value = MagicMock()
            _run_interactive("text")

            # Verify Repl was called with correct arguments
            assert mock_repl.call_count == 1
            call_kwargs = mock_repl.call_args[1]
            assert call_kwargs["provider"] == mock_provider.return_value
            assert call_kwargs["settings"] == mock_settings
            assert call_kwargs["config"].system_prompt == "system prompt"
            mock_anyio.run.assert_called_once_with(mock_repl_instance.run)


class TestRunHeadless:
    """Tests for _run_headless function."""

    def test_run_headless_processes_prompt(self) -> None:
        """Test that headless mode processes a single prompt."""
        from henchman.cli.app import _run_headless

        mock_repl_instance = MagicMock()
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = ""

        with (
            patch("henchman.cli.app._get_provider") as mock_provider,
            patch("henchman.config.ContextLoader", return_value=mock_loader_instance),
            patch("henchman.cli.repl.Repl", return_value=mock_repl_instance) as mock_repl,
            patch("henchman.cli.app.anyio") as mock_anyio,
        ):
            mock_provider.return_value = MagicMock()

            _run_headless("Hello world", "text")

            # Verify Repl was called with correct arguments
            assert mock_repl.call_count == 1
            call_kwargs = mock_repl.call_args[1]
            assert call_kwargs["provider"] == mock_provider.return_value
            assert call_kwargs["config"].system_prompt == ""
            # Check anyio.run was called with an async function
            mock_anyio.run.assert_called_once()
            # The function passed to anyio.run should be the run_single_prompt coroutine
            call_args = mock_anyio.run.call_args
            assert callable(call_args[0][0])


@pytest.mark.anyio
async def test_run_single_prompt_integration() -> None:
    """Test the run_single_prompt inner function in headless mode."""
    from io import StringIO

    from rich.console import Console

    from henchman.cli.repl import Repl, ReplConfig
    from henchman.core.events import EventType
    from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk

    class TestProvider(ModelProvider):
        @property
        def name(self) -> str:
            return "test"

        async def chat_completion_stream(
            self, messages: list[Message], tools: Any = None, **kwargs: Any
        ) -> Any:
            yield StreamChunk(content="Test response")
            yield StreamChunk(content=None, finish_reason=FinishReason.STOP)

    console = Console(file=StringIO(), force_terminal=True)
    provider = TestProvider()
    config = ReplConfig(system_prompt="")
    repl = Repl(provider=provider, console=console, config=config)

    # Process a single prompt like headless mode does
    async for event in repl.agent.run("Hello"):
        if event.type == EventType.CONTENT:
            console.print(event.data, end="")
        elif event.type == EventType.FINISHED:
            console.print()

    output = console.file.getvalue()  # type: ignore[union-attr]
    assert "Test response" in output
