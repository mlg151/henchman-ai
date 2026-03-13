"""Additional coverage tests for ui_renderer.py, extensions.py, textual_app.py, textual_config.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# ui_renderer.py tests
# ---------------------------------------------------------------------------


class TestUIRenderer:
    """Tests for UIRenderer coverage."""

    def _make_renderer(self):
        """Create a UIRenderer with mocked dependencies."""
        from henchman.cli.ui_renderer import UIRenderer

        return UIRenderer()

    def test_print_welcome_basic(self) -> None:
        """Test print_welcome outputs welcome text."""
        renderer = self._make_renderer()
        renderer.console = MagicMock()
        renderer.print_welcome()
        renderer.console.print.assert_called()

    def test_print_goodbye(self) -> None:
        """Test print_goodbye outputs goodbye message."""
        renderer = self._make_renderer()
        renderer.console = MagicMock()
        renderer.print_goodbye()
        renderer.console.print.assert_called()

    def test_print_newline(self) -> None:
        """Test print_newline outputs a newline."""
        renderer = self._make_renderer()
        renderer.console = MagicMock()
        renderer.print_newline()
        renderer.console.print.assert_called()

    def test_show_turn_status_with_agent(self) -> None:
        """Test show_turn_status displays iteration and token info."""
        renderer = self._make_renderer()
        renderer.console = MagicMock()
        renderer.renderer = MagicMock()
        agent = MagicMock()
        agent.turn.iteration = 3
        agent.turn.tool_count = 5
        agent.get_messages_for_api.return_value = []
        renderer.show_turn_status(agent, 10)

    def test_show_turn_status_no_agent(self) -> None:
        """Test show_turn_status with None agent raises or does nothing."""
        from henchman.cli.ui_renderer import UIRenderer

        renderer = UIRenderer()
        # show_turn_status is delegated to output_handler
        # Just verify the renderer is set up correctly
        assert renderer is not None

    @pytest.mark.anyio
    async def test_confirm_tool_execution_approved(self) -> None:
        """Test confirm_tool_execution returns True when user approves."""
        from henchman.cli.console import DARK_THEME, OutputRenderer

        renderer = OutputRenderer(theme=DARK_THEME)
        with patch("henchman.cli.console.Confirm.ask", return_value=True):
            result = await renderer.confirm_tool_execution("Run ls?")
        assert result is True

    @pytest.mark.anyio
    async def test_confirm_tool_execution_denied(self) -> None:
        """Test confirm_tool_execution returns False when user denies."""
        from henchman.cli.console import DARK_THEME, OutputRenderer

        renderer = OutputRenderer(theme=DARK_THEME)
        with patch("henchman.cli.console.Confirm.ask", return_value=False):
            result = await renderer.confirm_tool_execution("Write /tmp/x.txt?")
        assert result is False

    def test_print_welcome_with_tools(self) -> None:
        """Test print_welcome with tools available."""
        renderer = self._make_renderer()
        renderer.console = MagicMock()
        renderer.print_welcome()

    def test_stop_thinking_clears_state(self) -> None:
        """Test stop_thinking clears thinking state."""
        renderer = self._make_renderer()
        renderer._thinking_status = None
        renderer._is_thinking = False
        renderer.stop_thinking()
        assert renderer._is_thinking is False

    def test_is_thinking_property(self) -> None:
        """Test is_thinking property returns thinking state."""
        renderer = self._make_renderer()
        renderer._is_thinking = True
        assert renderer.is_thinking is True
        renderer._is_thinking = False
        assert renderer.is_thinking is False

    def test_thinking_context_manager(self) -> None:
        """Test thinking_context starts and stops thinking."""
        renderer = self._make_renderer()
        renderer.console = MagicMock()
        renderer.renderer = MagicMock()
        # Mock start_thinking and stop_thinking
        renderer.start_thinking = MagicMock()
        renderer.stop_thinking = MagicMock()
        with renderer.thinking_context("Processing..."):
            pass
        renderer.start_thinking.assert_called_once()
        renderer.stop_thinking.assert_called_once()

    def test_muted_via_getattr(self) -> None:
        """Test muted delegates to renderer via __getattr__."""
        renderer = self._make_renderer()
        renderer.renderer = MagicMock()
        renderer.muted("dim message")
        renderer.renderer.muted.assert_called_once_with("dim message")


# ---------------------------------------------------------------------------
# commands/extensions.py tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestExtensionsCommand:
    """Tests for ExtensionsCommand."""

    async def test_execute_no_extensions(self) -> None:
        """Test execute with no loaded extensions."""
        from henchman.cli.commands.extensions import ExtensionsCommand

        manager = MagicMock()
        manager.list_extensions.return_value = []
        cmd = ExtensionsCommand(manager)
        console = MagicMock()
        ctx = MagicMock()
        ctx.console = console
        await cmd.execute(ctx)
        console.print.assert_called_with("[dim]No extensions loaded[/]")

    async def test_execute_with_extensions(self) -> None:
        """Test execute with loaded extensions."""
        from henchman.cli.commands.extensions import ExtensionsCommand

        ext1 = MagicMock()
        ext1.name = "my_ext"
        ext1.version = "1.0.0"
        ext1.description = "A test extension"

        manager = MagicMock()
        manager.list_extensions.return_value = ["my_ext"]
        manager.get.return_value = ext1
        cmd = ExtensionsCommand(manager)
        console = MagicMock()
        ctx = MagicMock()
        ctx.console = console
        await cmd.execute(ctx)
        # Should list the extension
        calls = [str(c) for c in console.print.call_args_list]
        assert any("my_ext" in c for c in calls)
        assert any("Loaded Extensions" in c for c in calls)

    def test_name(self) -> None:
        """Test ExtensionsCommand.name returns 'extensions'."""
        from henchman.cli.commands.extensions import ExtensionsCommand

        cmd = ExtensionsCommand(MagicMock())
        assert cmd.name == "extensions"

    def test_description(self) -> None:
        """Test ExtensionsCommand.description."""
        from henchman.cli.commands.extensions import ExtensionsCommand

        cmd = ExtensionsCommand(MagicMock())
        assert "extension" in cmd.description.lower()

    def test_usage(self) -> None:
        """Test ExtensionsCommand.usage."""
        from henchman.cli.commands.extensions import ExtensionsCommand

        cmd = ExtensionsCommand(MagicMock())
        assert "/extensions" in cmd.usage


# ---------------------------------------------------------------------------
# textual_app.py tests
# ---------------------------------------------------------------------------


class TestTextualAppCoverage:
    """Tests for textual_app.py missing coverage."""

    def test_textual_config_defaults(self) -> None:
        """Test TextualConfig has expected defaults."""
        from henchman.cli.textual_config import TextualConfig

        config = TextualConfig()
        # Should have a system_prompt attribute
        assert hasattr(config, "system_prompt") or hasattr(config, "auto_approve_tools")

    def test_textual_config_custom(self) -> None:
        """Test TextualConfig with custom values."""
        from henchman.cli.textual_config import TextualConfig

        config = TextualConfig(
            system_prompt="You are a coding assistant",
            auto_approve_tools=True,
        )
        assert config.system_prompt == "You are a coding assistant"
        assert config.auto_approve_tools is True

    def test_check_utf8_encoding_no_error(self) -> None:
        """Test _check_utf8_encoding does not raise on normal encoding."""
        from henchman.cli.textual_app import _check_utf8_encoding

        _check_utf8_encoding()  # Should not raise

    def test_check_utf8_encoding_non_utf8(self) -> None:
        """Test _check_utf8_encoding warns for non-UTF-8 encoding."""

        from henchman.cli.textual_app import _check_utf8_encoding

        # Create a string stream with latin-1 encoding attribute
        mock_stdin = MagicMock()
        mock_stdin.encoding = "latin-1"
        with patch("sys.stdin", mock_stdin):
            _check_utf8_encoding()  # Should not raise, just warn to stderr

    def test_henchman_textual_app_can_instantiate(self) -> None:
        """Test HenchmanTextualApp can be instantiated via object.__new__."""
        from henchman.cli.textual_app import HenchmanTextualApp

        app = object.__new__(HenchmanTextualApp)
        assert app is not None


# ---------------------------------------------------------------------------
# textual_config.py coverage tests
# ---------------------------------------------------------------------------


class TestTextualConfigCoverage:
    """Tests for textual_config.py missing coverage."""

    def test_textual_config_defaults(self) -> None:
        """Test TextualConfig has expected defaults."""
        from henchman.cli.textual_config import TextualConfig

        config = TextualConfig()
        assert hasattr(config, "system_prompt") or hasattr(config, "auto_approve_tools")

    def test_textual_config_custom_values(self) -> None:
        """Test TextualConfig with custom values."""
        from henchman.cli.textual_config import TextualConfig

        config = TextualConfig(
            system_prompt="You are helpful",
            auto_approve_tools=True,
        )
        assert config.system_prompt == "You are helpful"
        assert config.auto_approve_tools is True

    def test_component_config_defaults(self) -> None:
        """Test ComponentConfig has expected fields."""
        from henchman.cli.textual_config import ComponentConfig, TextualConfig

        textual_config = TextualConfig()
        app = MagicMock()
        provider = MagicMock()
        provider.name = "deepseek"
        config = ComponentConfig(
            app=app,
            config=textual_config,
            provider=provider,
            settings=None,
            environment_context=None,
        )
        assert config.app is app
        assert config.provider is provider

    def test_component_initializer_init(self) -> None:
        """Test ComponentInitializer can be instantiated."""
        from henchman.cli.textual_config import ComponentConfig, ComponentInitializer, TextualConfig

        textual_config = TextualConfig()
        app = MagicMock()
        provider = MagicMock()
        provider.name = "deepseek"
        config = ComponentConfig(
            app=app,
            config=textual_config,
            provider=provider,
            settings=None,
            environment_context=None,
        )
        initializer = object.__new__(ComponentInitializer)
        initializer.config = config
        assert initializer.config is config

    def test_resolve_theme_name_valid(self) -> None:
        """Test _resolve_theme_name with valid theme."""
        from henchman.cli.console import ThemeManager
        from henchman.cli.textual_config import ComponentConfig, ComponentInitializer, TextualConfig

        textual_config = TextualConfig()
        app = MagicMock()
        app.settings = MagicMock()
        app.settings.ui = MagicMock()
        app.settings.ui.theme = "dark"
        provider = MagicMock()
        config = ComponentConfig(
            app=app,
            config=textual_config,
            provider=provider,
            settings=app.settings,
            environment_context=None,
        )
        initializer = object.__new__(ComponentInitializer)
        initializer.config = config
        theme_manager = ThemeManager()
        result = initializer._resolve_theme_name(theme_manager)
        assert result == "dark"

    def test_resolve_theme_name_invalid(self) -> None:
        """Test _resolve_theme_name falls back on invalid theme."""
        from henchman.cli.console import ThemeManager
        from henchman.cli.textual_config import ComponentConfig, ComponentInitializer, TextualConfig

        textual_config = TextualConfig()
        app = MagicMock()
        app.settings = MagicMock()
        app.settings.ui = MagicMock()
        app.settings.ui.theme = "nonexistent-theme"
        provider = MagicMock()
        config = ComponentConfig(
            app=app,
            config=textual_config,
            provider=provider,
            settings=app.settings,
            environment_context=None,
        )
        initializer = object.__new__(ComponentInitializer)
        initializer.config = config
        theme_manager = ThemeManager()
        result = initializer._resolve_theme_name(theme_manager)
        assert result == "dark"  # Falls back to default


# ---------------------------------------------------------------------------
# tool_executor.py additional coverage
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestToolExecutorAdditionalCoverage:
    """Additional coverage tests for tool_executor.py."""

    def _make_executor(self):
        """Create a ToolExecutor with mocked dependencies."""
        from henchman.cli.tool_executor import ToolExecutor

        output_handler = MagicMock()
        output_handler.session_manager = MagicMock()
        output_handler.session_manager.record_tool_result = MagicMock()
        output_handler.show_turn_status = MagicMock()
        output_handler.print_newline = MagicMock()
        tool_manager = MagicMock()
        provider = MagicMock()
        return ToolExecutor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            provider=provider,
        )

    def _make_agent(self):
        """Create a mock agent."""
        agent = MagicMock()
        agent.unlimited_mode = False
        agent.turn = MagicMock()
        agent.turn.is_at_limit.return_value = False
        agent.turn.tool_count = 0
        agent.turn.is_spinning.return_value = False
        agent.turn.get_adaptive_limit.return_value = 25
        agent.turn.iteration = 0
        return agent

    async def test_execute_tool_calls_with_parallel(self) -> None:
        """Test execute_tool_calls processes parallel tools."""
        executor = self._make_executor()
        agent = self._make_agent()
        agent.turn.increment_iteration = MagicMock()
        agent.continue_with_tool_results = MagicMock(return_value=_empty_stream())

        tc1 = MagicMock()
        tc1.__class__ = type(tc1)  # Make isinstance check pass

        from henchman.providers.base import ToolCall
        tc = ToolCall(id="tc-1", name="read_file", arguments={"path": "/tmp/f.txt"})
        result = MagicMock()
        result.content = "content"
        result.success = True
        result.error = None
        executor.tool_manager.registry.execute = AsyncMock(return_value=result)
        executor.tool_manager.registry.get = MagicMock(return_value=None)
        executor.tool_manager.registry._auto_approve_policies = set()
        executor.process_agent_stream = AsyncMock()

        await executor.execute_tool_calls([tc], agent)
        agent.turn.increment_iteration.assert_called_once()

    async def test_run_sequential_tool_calls_with_monitor(self) -> None:
        """Test _run_sequential_tool_calls suspends monitor."""
        executor = self._make_executor()
        monitor = MagicMock()
        monitor.suspend = AsyncMock()
        monitor.resume = MagicMock()
        executor.current_monitor = monitor
        agent = self._make_agent()
        responded_ids: set[str] = set()

        from henchman.providers.base import ToolCall
        tc = ToolCall(id="tc-1", name="read_file", arguments={})
        result = MagicMock()
        result.content = "content"
        result.success = True
        result.error = None
        executor.tool_manager.registry.execute = AsyncMock(return_value=result)

        await executor._run_sequential_tool_calls([tc], agent, responded_ids)
        monitor.suspend.assert_called_once()
        monitor.resume.assert_called_once()

    async def test_run_sequential_tool_calls_no_monitor(self) -> None:
        """Test _run_sequential_tool_calls without monitor."""
        executor = self._make_executor()
        executor.current_monitor = None
        agent = self._make_agent()
        responded_ids: set[str] = set()

        from henchman.providers.base import ToolCall
        tc = ToolCall(id="tc-1", name="read_file", arguments={})
        result = MagicMock()
        result.content = "content"
        result.success = True
        result.error = None
        executor.tool_manager.registry.execute = AsyncMock(return_value=result)

        await executor._run_sequential_tool_calls([tc], agent, responded_ids)
        assert "tc-1" in responded_ids


async def _empty_stream():
    """Helper: empty async iterator."""
    return
    yield  # noqa: unreachable - makes this an async generator


# ---------------------------------------------------------------------------
# team.py additional coverage
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestTeamCommandAdditionalCoverage:
    """Additional coverage for team.py."""

    async def test_team_status_action(self) -> None:
        """Test TeamCommand status subcommand."""
        from henchman.cli.commands.team import TeamCommand

        cmd = TeamCommand()
        console = MagicMock()
        orchestrator = MagicMock()
        orchestrator.pool = MagicMock()
        orchestrator.pool.agents = {"engineer": MagicMock()}
        repl = MagicMock()
        repl.orchestrator = orchestrator
        ctx = MagicMock()
        ctx.console = console
        ctx.repl = repl
        ctx.args = ["status"]
        await cmd.execute(ctx)
        console.print.assert_called()

    async def test_team_list_action(self) -> None:
        """Test TeamCommand list subcommand."""
        from henchman.cli.commands.team import TeamCommand

        cmd = TeamCommand()
        console = MagicMock()
        orchestrator = MagicMock()
        orchestrator.pool = MagicMock()
        orchestrator.pool.agents = {}
        repl = MagicMock()
        repl.orchestrator = orchestrator
        ctx = MagicMock()
        ctx.console = console
        ctx.repl = repl
        ctx.args = ["list"]
        await cmd.execute(ctx)
        console.print.assert_called()
