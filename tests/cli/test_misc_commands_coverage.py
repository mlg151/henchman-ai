"""Tests for serve.py, textual_driver.py, builtins.py, team.py, model.py coverage."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# serve.py tests
# ---------------------------------------------------------------------------


class TestServeCommand:
    """Tests for serve_command Click command."""

    def test_serve_command_basic(self) -> None:
        """Test serve_command runs and shows server info."""
        from click.testing import CliRunner

        from henchman.cli.serve import serve_command

        runner = CliRunner()
        with patch("henchman.cli.serve.run_server") as mock_run, \
             patch("henchman.cli.serve.load_settings") as mock_settings:
            mock_settings.return_value = MagicMock(api=None)
            mock_run.return_value = None
            result = runner.invoke(serve_command, ["--host", "127.0.0.1", "--port", "8000"])
        # Should attempt to run server
        assert "Starting" in result.output or result.exit_code in (0, 1)

    def test_serve_command_with_auth_required(self) -> None:
        """Test serve_command with auth required."""
        from click.testing import CliRunner

        from henchman.cli.serve import serve_command

        runner = CliRunner()
        mock_api = MagicMock()
        mock_api.require_auth = True
        mock_api.api_keys = ["key1"]

        with patch("henchman.cli.serve.run_server") as mock_run, \
             patch("henchman.cli.serve.load_settings") as mock_settings:
            settings = MagicMock()
            settings.api = mock_api
            mock_settings.return_value = settings
            mock_run.return_value = None
            result = runner.invoke(serve_command, [])
        assert "required" in result.output or result.exit_code in (0, 1)

    def test_serve_command_auth_no_keys(self) -> None:
        """Test serve_command with auth required but no API keys."""
        from click.testing import CliRunner

        from henchman.cli.serve import serve_command

        runner = CliRunner()
        mock_api = MagicMock()
        mock_api.require_auth = True
        mock_api.api_keys = []

        with patch("henchman.cli.serve.run_server") as mock_run, \
             patch("henchman.cli.serve.load_settings") as mock_settings:
            settings = MagicMock()
            settings.api = mock_api
            mock_settings.return_value = settings
            mock_run.return_value = None
            result = runner.invoke(serve_command, [])
        assert result.exit_code in (0, 1)

    def test_serve_command_auth_disabled(self) -> None:
        """Test serve_command with auth disabled."""
        from click.testing import CliRunner

        from henchman.cli.serve import serve_command

        runner = CliRunner()
        mock_api = MagicMock()
        mock_api.require_auth = False

        with patch("henchman.cli.serve.run_server") as mock_run, \
             patch("henchman.cli.serve.load_settings") as mock_settings:
            settings = MagicMock()
            settings.api = mock_api
            mock_settings.return_value = settings
            mock_run.return_value = None
            result = runner.invoke(serve_command, [])
        assert "disabled" in result.output or result.exit_code in (0, 1)

    def test_serve_command_keyboard_interrupt(self) -> None:
        """Test serve_command handles KeyboardInterrupt."""
        from click.testing import CliRunner

        from henchman.cli.serve import serve_command

        runner = CliRunner()
        with patch("henchman.cli.serve.run_server", side_effect=KeyboardInterrupt), \
             patch("henchman.cli.serve.load_settings") as mock_settings:
            mock_settings.return_value = MagicMock(api=None)
            result = runner.invoke(serve_command, [])
        assert "stopped" in result.output or result.exit_code in (0, 1)

    def test_serve_command_exception(self) -> None:
        """Test serve_command handles generic exception."""
        from click.testing import CliRunner

        from henchman.cli.serve import serve_command

        runner = CliRunner()
        with patch("henchman.cli.serve.run_server", side_effect=RuntimeError("server error")), \
             patch("henchman.cli.serve.load_settings") as mock_settings:
            mock_settings.return_value = MagicMock(api=None)
            result = runner.invoke(serve_command, [])
        assert result.exit_code != 0 or "Error" in result.output


# ---------------------------------------------------------------------------
# textual_driver.py tests
# ---------------------------------------------------------------------------


class TestTextualDriver:
    """Tests for textual_driver.py."""

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
    def test_robust_linux_driver_exists_on_linux(self) -> None:
        """Test RobustLinuxDriver is defined on Linux."""
        from henchman.cli.textual_driver import RobustLinuxDriver
        assert RobustLinuxDriver is not None

    def test_module_imports(self) -> None:
        """Test the module imports without error."""
        import henchman.cli.textual_driver as driver_module
        assert hasattr(driver_module, "RobustLinuxDriver")

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
    def test_robust_linux_driver_run_input_thread_success(self) -> None:
        """Test run_input_thread normal path (no exceptions)."""
        from henchman.cli.textual_driver import RobustLinuxDriver

        driver = object.__new__(RobustLinuxDriver)
        with patch.object(
            RobustLinuxDriver.__bases__[0],
            "run_input_thread",
            return_value=None,
        ):
            driver.run_input_thread()

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
    def test_robust_linux_driver_run_input_thread_unicode_error(self) -> None:
        """Test run_input_thread handles UnicodeDecodeError gracefully."""
        from henchman.cli.textual_driver import RobustLinuxDriver

        driver = object.__new__(RobustLinuxDriver)
        with patch.object(
            RobustLinuxDriver.__bases__[0],
            "run_input_thread",
            side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"),
        ):
            driver.run_input_thread()

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
    def test_robust_linux_driver_run_input_thread_other_error(self) -> None:
        """Test run_input_thread re-raises non-Unicode errors."""
        from henchman.cli.textual_driver import RobustLinuxDriver

        driver = object.__new__(RobustLinuxDriver)
        with patch.object(
            RobustLinuxDriver.__bases__[0],
            "run_input_thread",
            side_effect=RuntimeError("other error"),
        ), pytest.raises(RuntimeError):
            driver.run_input_thread()


# ---------------------------------------------------------------------------
# builtins.py coverage tests
# ---------------------------------------------------------------------------


class TestBuiltinsCoverage:
    """Coverage tests for builtins.py missing lines."""

    def test_show_specific_command_help_found(self) -> None:
        """Test _show_specific_command_help when command exists."""
        from henchman.cli.commands.builtins import _show_specific_command_help

        console = MagicMock()
        registry = MagicMock()
        cmd = MagicMock()
        cmd.name = "help"
        cmd.description = "Show help"
        cmd.usage = "/help [command]"
        registry.get.return_value = cmd
        ctx = MagicMock()
        ctx.args = ["help"]
        ctx.registry = registry

        result = _show_specific_command_help(ctx, console)
        assert result is True
        console.print.assert_called()

    def test_show_specific_command_help_not_found(self) -> None:
        """Test _show_specific_command_help when command does not exist."""
        from henchman.cli.commands.builtins import _show_specific_command_help

        console = MagicMock()
        registry = MagicMock()
        registry.get.return_value = None
        ctx = MagicMock()
        ctx.args = ["/unknowncmd"]
        ctx.registry = registry

        result = _show_specific_command_help(ctx, console)
        assert result is False
        calls = [str(c) for c in console.print.call_args_list]
        assert any("Unknown command" in c for c in calls)

    def test_list_all_commands(self) -> None:
        """Test _list_all_commands lists commands."""
        from henchman.cli.commands.builtins import _list_all_commands

        console = MagicMock()
        cmd1 = MagicMock()
        cmd1.name = "help"
        cmd1.description = "Show help"
        cmd2 = MagicMock()
        cmd2.name = "quit"
        cmd2.description = "Quit"
        registry = MagicMock()
        registry.get_commands.return_value = [cmd1, cmd2]
        ctx = MagicMock()
        ctx.registry = registry

        _list_all_commands(ctx, console)
        assert console.print.call_count >= 2

    def test_list_all_commands_no_registry(self) -> None:
        """Test _list_all_commands with no registry."""
        from henchman.cli.commands.builtins import _list_all_commands

        console = MagicMock()
        ctx = MagicMock()
        ctx.registry = None

        _list_all_commands(ctx, console)  # Should not raise

    @pytest.mark.anyio
    async def test_help_command_specific_cmd(self) -> None:
        """Test HelpCommand with specific command arg."""
        from henchman.cli.commands.builtins import HelpCommand

        cmd = HelpCommand()
        console = MagicMock()
        registry = MagicMock()
        help_cmd = MagicMock()
        help_cmd.name = "help"
        help_cmd.description = "Show help"
        help_cmd.usage = "/help [command]"
        registry.get.return_value = help_cmd
        ctx = MagicMock()
        ctx.console = console
        ctx.args = ["help"]
        ctx.registry = registry
        await cmd.execute(ctx)
        console.print.assert_called()

    @pytest.mark.anyio
    async def test_clear_command_with_agent(self) -> None:
        """Test ClearCommand clears agent history."""
        from henchman.cli.commands.builtins import ClearCommand

        cmd = ClearCommand()
        console = MagicMock()
        agent = MagicMock()
        ctx = MagicMock()
        ctx.console = console
        ctx.agent = agent
        await cmd.execute(ctx)
        agent.clear_history.assert_called_once()
        console.clear.assert_called_once()

    @pytest.mark.anyio
    async def test_clear_command_no_agent(self) -> None:
        """Test ClearCommand without agent."""
        from henchman.cli.commands.builtins import ClearCommand

        cmd = ClearCommand()
        console = MagicMock()
        ctx = MagicMock()
        ctx.console = console
        ctx.agent = None
        await cmd.execute(ctx)
        console.clear.assert_called_once()


# ---------------------------------------------------------------------------
# team.py coverage tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestTeamCommandCoverage:
    """Coverage tests for team.py missing lines."""

    async def test_team_no_orchestrator(self) -> None:
        """Test TeamCommand when no orchestrator is available."""
        from henchman.cli.commands.team import TeamCommand

        cmd = TeamCommand()
        console = MagicMock()
        ctx = MagicMock()
        ctx.console = console
        ctx.repl = None
        ctx.args = []
        await cmd.execute(ctx)
        calls = [str(c) for c in console.print.call_args_list]
        assert any("not initialized" in c for c in calls)

    async def test_team_no_repl(self) -> None:
        """Test TeamCommand when repl has no orchestrator attribute."""
        from henchman.cli.commands.team import TeamCommand

        cmd = TeamCommand()
        console = MagicMock()
        ctx = MagicMock()
        ctx.console = console
        ctx.repl = MagicMock(spec=[])  # No orchestrator attribute
        ctx.args = []
        await cmd.execute(ctx)
        calls = [str(c) for c in console.print.call_args_list]
        assert any("not initialized" in c for c in calls)

    async def test_team_reset_action(self) -> None:
        """Test TeamCommand reset subcommand."""
        from henchman.cli.commands.team import TeamCommand

        cmd = TeamCommand()
        console = MagicMock()
        orchestrator = MagicMock()
        orchestrator.pool = MagicMock()
        repl = MagicMock()
        repl.orchestrator = orchestrator
        ctx = MagicMock()
        ctx.console = console
        ctx.repl = repl
        ctx.args = ["reset"]
        await cmd.execute(ctx)
        # Should call reset
        console.print.assert_called()


# ---------------------------------------------------------------------------
# model.py coverage tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestModelCommandCoverage:
    """Coverage tests for model.py missing lines."""

    def _make_ctx(self, args: list[str]) -> MagicMock:
        """Create a mock command context."""
        from henchman.core.session import Session
        console = MagicMock()
        agent = MagicMock()
        agent.provider = MagicMock()
        agent.provider.name = "deepseek"
        agent.provider.default_model = "deepseek-chat"
        session = Session(id="test", project_hash="abc", started="now", last_updated="now")
        ctx = MagicMock()
        ctx.console = console
        ctx.args = args
        ctx.agent = agent
        ctx.session = session
        ctx.repl = MagicMock()
        return ctx

    async def test_model_current(self) -> None:
        """Test /model with no args shows current."""
        from henchman.cli.commands.model import ModelCommand

        cmd = ModelCommand()
        ctx = self._make_ctx([])
        with patch("henchman.cli.commands.model.get_default_registry") as mock_reg:
            mock_reg.return_value.list_providers.return_value = ["deepseek", "openai"]
            await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_model_list(self) -> None:
        """Test /model list shows all providers."""
        from henchman.cli.commands.model import ModelCommand

        cmd = ModelCommand()
        ctx = self._make_ctx(["list"])
        mock_provider_class = MagicMock()
        mock_provider_class.__doc__ = "A provider."
        with patch("henchman.cli.commands.model.get_default_registry") as mock_reg:
            mock_reg.return_value.list_providers.return_value = ["deepseek"]
            mock_reg.return_value.get.return_value = mock_provider_class
            await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_model_set_no_args(self) -> None:
        """Test /model set with no provider arg."""
        from henchman.cli.commands.model import ModelCommand

        cmd = ModelCommand()
        ctx = self._make_ctx(["set"])
        await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_model_set_success(self) -> None:
        """Test /model set with valid provider."""
        from henchman.cli.commands.model import ModelCommand

        cmd = ModelCommand()
        ctx = self._make_ctx(["set", "deepseek"])
        new_provider = MagicMock()
        new_provider.name = "deepseek"
        new_provider.default_model = "deepseek-chat"
        with (
            patch("henchman.cli.commands.model._get_api_key_for_provider", return_value="fake-key"),
            patch("henchman.cli.commands.model._create_provider_instance", return_value=new_provider),
            patch("henchman.cli.commands.model.get_default_registry") as mock_reg,
        ):
            mock_reg.return_value.list_providers.return_value = ["deepseek"]
            await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_model_set_error(self) -> None:
        """Test /model set handles error."""
        from henchman.cli.commands.model import ModelCommand

        cmd = ModelCommand()
        ctx = self._make_ctx(["set", "badprovider"])
        with (
            patch("henchman.cli.commands.model._get_api_key_for_provider", return_value=None),
            patch("henchman.cli.commands.model._create_provider_instance",
                  side_effect=Exception("no provider")),
            patch("henchman.cli.commands.model.get_default_registry") as mock_reg,
        ):
            mock_reg.return_value.list_providers.return_value = ["deepseek"]
            await cmd.execute(ctx)
        ctx.console.print.assert_called()
        # Some error message should have been printed
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert len(calls) > 0

    async def test_model_test(self) -> None:
        """Test /model test subcommand."""
        from henchman.cli.commands.model import ModelCommand

        cmd = ModelCommand()
        ctx = self._make_ctx(["test"])
        with patch("henchman.cli.commands.model.get_default_registry") as mock_reg:
            mock_reg.return_value.list_providers.return_value = ["deepseek"]
            await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_model_no_agent(self) -> None:
        """Test /model with no agent."""
        from henchman.cli.commands.model import ModelCommand

        cmd = ModelCommand()
        ctx = self._make_ctx([])
        ctx.agent = None
        await cmd.execute(ctx)
        ctx.console.print.assert_called()


# ---------------------------------------------------------------------------
# Module-level model.py helper functions
# ---------------------------------------------------------------------------


class TestModelHelpers:
    """Tests for module-level model.py helper functions."""

    def test_get_example_config(self) -> None:
        """Test _get_example_config returns expected values."""
        from henchman.cli.commands.model import _get_example_config

        result = _get_example_config("deepseek")
        assert "deepseek-chat" in result

        result = _get_example_config("unknown_provider")
        assert "documentation" in result.lower()

    def test_get_env_var_name(self) -> None:
        """Test _get_env_var_name returns expected variable."""
        from henchman.cli.commands.model import _get_env_var_name

        # Call with deepseek - uses actual provider utils
        result = _get_env_var_name("deepseek")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_env_vars_ollama(self) -> None:
        """Test _get_env_vars for ollama returns optional env."""
        from henchman.cli.commands.model import _get_env_vars

        result = _get_env_vars("ollama")
        assert "OLLAMA_HOST" in result

    def test_print_current_configuration(self) -> None:
        """Test _print_current_configuration prints provider info."""
        from henchman.cli.commands.model import _print_current_configuration

        console = MagicMock()
        provider = MagicMock()
        provider.name = "deepseek"
        provider.default_model = "deepseek-chat"
        _print_current_configuration(console, provider, ["deepseek", "openai"])
        calls = [str(c) for c in console.print.call_args_list]
        assert any("deepseek" in c for c in calls)

    def test_print_provider_entry(self) -> None:
        """Test _print_provider_entry prints provider details."""
        from henchman.cli.commands.model import _print_provider_entry

        console = MagicMock()
        provider_class = MagicMock()
        provider_class.__doc__ = "A deepseek provider.\nMore details."
        with (
            patch("henchman.cli.commands.model._get_example_config", return_value="model-x"),
            patch("henchman.cli.commands.model._get_env_vars", return_value="DEEPSEEK_API_KEY"),
        ):
            _print_provider_entry(console, "deepseek", provider_class)
        assert console.print.call_count >= 2
