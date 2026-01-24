"""Extended tests for CLI entry point to reach 100% coverage."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from henchman.cli.app import _run_headless, _run_interactive, cli
from henchman.core.events import AgentEvent, EventType


def test_run_interactive_json_warning():
    """Test that interactive mode warns about JSON formats."""
    with (
        patch("henchman.cli.app._get_provider"),
        patch("henchman.config.ContextLoader") as mock_loader,
        patch("henchman.cli.repl.Repl"),
        patch("henchman.cli.app.anyio.run"),
        patch("henchman.cli.app.console.print") as mock_print
    ):
        mock_loader.return_value.load.return_value = "system prompt"
        _run_interactive("json")
        mock_print.assert_called()
        assert "JSON output formats not supported" in mock_print.call_args[0][0]

def test_run_interactive_plan_mode():
    """Test starting interactive mode in plan mode."""
    mock_repl_instance = MagicMock()
    mock_repl_instance.session = MagicMock()
    mock_repl_instance.agent = MagicMock()
    mock_repl_instance.agent.system_prompt = "Original"
    mock_repl_instance.tool_registry = MagicMock()
    with (
        patch("henchman.cli.app._get_provider"),
        patch("henchman.config.ContextLoader"),
        patch("henchman.cli.repl.Repl", return_value=mock_repl_instance),
        patch("henchman.cli.app.anyio.run")
    ):
        _run_interactive("text", plan_mode=True)
        assert mock_repl_instance.session.plan_mode is True
        mock_repl_instance.tool_registry.set_plan_mode.assert_called_once_with(True)
        assert "PLAN" in mock_repl_instance.agent.system_prompt

def test_run_headless_json():
    """Test headless mode with JSON output."""
    mock_repl_instance = MagicMock()
    with (
        patch("henchman.cli.app._get_provider"),
        patch("henchman.config.ContextLoader"),
        patch("henchman.cli.repl.Repl", return_value=mock_repl_instance),
        patch("henchman.cli.app.anyio.run") as mock_run
    ):
        _run_headless("prompt", "json")
        mock_run.assert_called_once()
        # Get the internal function passed to anyio.run
        run_func = mock_run.call_args[0][0]
        assert "run_single_prompt_json" in run_func.__name__

def test_run_headless_stream_json():
    """Test headless mode with stream-json output."""
    mock_repl_instance = MagicMock()
    with (
        patch("henchman.cli.app._get_provider"),
        patch("henchman.config.ContextLoader"),
        patch("henchman.cli.repl.Repl", return_value=mock_repl_instance),
        patch("henchman.cli.app.anyio.run") as mock_run
    ):
        _run_headless("prompt", "stream-json")
        mock_run.assert_called_once()
        run_func = mock_run.call_args[0][0]
        assert "run_single_prompt_stream_json" in run_func.__name__

@pytest.mark.anyio
async def test_run_single_prompt_json_inner():
    """Test the run_single_prompt_json inner function."""
    from henchman.cli.app import _run_headless
    mock_repl_instance = MagicMock()
    mock_repl_instance.agent.run.return_value = AsyncMock()
    # Mock the async generator
    async def mock_run_gen(_p):
        yield AgentEvent(type=EventType.CONTENT, data="Result")
        yield AgentEvent(type=EventType.FINISHED)
    mock_repl_instance.agent.run = mock_run_gen
    with (
        patch("henchman.cli.app._get_provider"),
        patch("henchman.config.ContextLoader"),
        patch("henchman.cli.repl.Repl", return_value=mock_repl_instance),
        patch("henchman.cli.app.anyio.run") as mock_run,
        patch("henchman.cli.json_output.JsonOutputRenderer") as mock_renderer
    ):
        _run_headless("prompt", "json")
        run_func = mock_run.call_args[0][0]
        await run_func()
        assert mock_renderer.return_value.render.call_count == 2

@pytest.mark.anyio
async def test_run_single_prompt_stream_json_inner():
    """Test the run_single_prompt_stream_json inner function."""
    mock_repl_instance = MagicMock()
    async def mock_run_gen(_p):
        yield AgentEvent(type=EventType.CONTENT, data="Result")
    mock_repl_instance.agent.run = mock_run_gen
    with (
        patch("henchman.cli.app._get_provider"),
        patch("henchman.config.ContextLoader"),
        patch("henchman.cli.repl.Repl", return_value=mock_repl_instance),
        patch("henchman.cli.app.anyio.run") as mock_run,
        patch("henchman.cli.json_output.JsonOutputRenderer") as mock_renderer
    ):
        _run_headless("prompt", "stream-json")
        run_func = mock_run.call_args[0][0]
        await run_func()
        assert mock_renderer.return_value.render_stream_json.called

def test_cli_plan_flag():
    """Test the --plan flag in CLI."""
    runner = CliRunner()
    with patch("henchman.cli.app._run_interactive") as mock_run:
        result = runner.invoke(cli, ["--plan"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with("text", True)
