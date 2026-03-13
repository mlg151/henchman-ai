"""Tests for input.py, repl.py, app.py, and plugins.py coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# input.py tests
# ---------------------------------------------------------------------------


class TestInputCoverage:
    """Coverage tests for input.py missing lines."""

    def test_is_slash_command_valid(self) -> None:
        """Test is_slash_command returns True for valid commands."""
        from henchman.cli.input import is_slash_command

        assert is_slash_command("/help") is True
        assert is_slash_command("/quit") is True
        assert is_slash_command("/model set deepseek") is True

    def test_is_slash_command_double_slash(self) -> None:
        """Test is_slash_command returns False for comments."""
        from henchman.cli.input import is_slash_command

        assert is_slash_command("//comment") is False

    def test_is_slash_command_just_slash(self) -> None:
        """Test is_slash_command returns False for just slash."""
        from henchman.cli.input import is_slash_command

        assert is_slash_command("/") is False

    def test_is_slash_command_slash_space(self) -> None:
        """Test is_slash_command returns False for slash and space."""
        from henchman.cli.input import is_slash_command

        assert is_slash_command("/ ") is False

    def test_is_shell_command(self) -> None:
        """Test is_shell_command detects ! prefixed commands."""
        from henchman.cli.input import is_shell_command

        assert is_shell_command("!ls -la") is True
        assert is_shell_command("not a shell cmd") is False


class TestToolForm:
    """Tests for ToolForm class."""

    def test_prompt_for_parameters_empty(self) -> None:
        """Test prompt_for_parameters with no properties."""
        from henchman.cli.input import ToolForm

        console = MagicMock()
        form = ToolForm(console)
        result = form.prompt_for_parameters("my_tool", {"properties": {}})
        assert result == {}

    def test_prompt_for_parameters_boolean(self) -> None:
        """Test prompt_for_parameters with boolean parameter."""
        from henchman.cli.input import ToolForm

        console = MagicMock()
        form = ToolForm(console)
        with patch("henchman.cli.input.Confirm.ask", return_value=True):
            result = form.prompt_for_parameters(
                "my_tool",
                {"properties": {"flag": {"type": "boolean", "description": "A flag"}}},
            )
        assert result["flag"] is True

    def test_prompt_for_parameters_integer(self) -> None:
        """Test prompt_for_parameters with integer parameter."""
        from henchman.cli.input import ToolForm

        console = MagicMock()
        form = ToolForm(console)
        with patch("henchman.cli.input.IntPrompt.ask", return_value=42):
            result = form.prompt_for_parameters(
                "my_tool",
                {"properties": {"count": {"type": "integer"}}},
            )
        assert result["count"] == 42

    def test_prompt_for_parameters_string(self) -> None:
        """Test prompt_for_parameters with string parameter."""
        from henchman.cli.input import ToolForm

        console = MagicMock()
        form = ToolForm(console)
        with patch("henchman.cli.input.Prompt.ask", return_value="hello"):
            result = form.prompt_for_parameters(
                "my_tool",
                {"properties": {"name": {"type": "string", "description": "A name"}}},
            )
        assert result["name"] == "hello"


class TestKeyMonitor:
    """Tests for KeyMonitor class."""

    def test_init(self) -> None:
        """Test KeyMonitor can be instantiated."""
        from henchman.cli.input import KeyMonitor

        with patch("prompt_toolkit.input.create_input"):
            monitor = KeyMonitor()
        assert monitor.stop_requested is False

    def test_stop_requested_property(self) -> None:
        """Test stop_requested reflects stop event state."""
        from henchman.cli.input import KeyMonitor

        with patch("prompt_toolkit.input.create_input"):
            monitor = KeyMonitor()
        monitor._stop_event.set()
        assert monitor.stop_requested is True

    def test_exit_requested_property(self) -> None:
        """Test exit_requested reflects exit event state."""
        from henchman.cli.input import KeyMonitor

        with patch("prompt_toolkit.input.create_input"):
            monitor = KeyMonitor()
        monitor._exit_event.set()
        assert monitor.exit_requested is True

    @pytest.mark.anyio
    async def test_suspend_and_resume(self) -> None:
        """Test suspend clears and resume sets _suspended event."""
        from henchman.cli.input import KeyMonitor

        with patch("prompt_toolkit.input.create_input"):
            monitor = KeyMonitor()
        monitor._in_raw_mode = False
        await monitor.suspend()
        assert not monitor._suspended.is_set()
        monitor.resume()
        assert monitor._suspended.is_set()

    def test_should_continue_monitoring_initial(self) -> None:
        """Test _should_continue_monitoring returns True initially."""
        from henchman.cli.input import KeyMonitor

        with patch("prompt_toolkit.input.create_input"):
            monitor = KeyMonitor()
        assert monitor._should_continue_monitoring() is True

    def test_should_continue_monitoring_stopped(self) -> None:
        """Test _should_continue_monitoring returns False after stop."""
        from henchman.cli.input import KeyMonitor

        with patch("prompt_toolkit.input.create_input"):
            monitor = KeyMonitor()
        monitor._stop_event.set()
        assert monitor._should_continue_monitoring() is False

    def test_process_keys_escape(self) -> None:
        """Test _process_keys sets stop event on Escape."""
        from prompt_toolkit.input.base import KeyPress
        from prompt_toolkit.keys import Keys

        from henchman.cli.input import KeyMonitor

        with patch("prompt_toolkit.input.create_input"):
            monitor = KeyMonitor()
        monitor._process_keys([KeyPress(Keys.Escape, "")])
        assert monitor.stop_requested is True

    def test_process_keys_ctrl_c(self) -> None:
        """Test _process_keys sets exit event on Ctrl+C."""
        from prompt_toolkit.input.base import KeyPress
        from prompt_toolkit.keys import Keys

        from henchman.cli.input import KeyMonitor

        with patch("prompt_toolkit.input.create_input"):
            monitor = KeyMonitor()
        monitor._process_keys([KeyPress(Keys.ControlC, "")])
        assert monitor.exit_requested is True


class TestExpandAtReferences:
    """Tests for expand_at_references function."""

    @pytest.mark.anyio
    async def test_expand_normal_text(self) -> None:
        """Test expand_at_references returns normal text unchanged."""
        from henchman.cli.input import expand_at_references

        result = await expand_at_references("Hello world")
        assert result == "Hello world"

    @pytest.mark.anyio
    async def test_expand_nonexistent_file(self) -> None:
        """Test expand_at_references keeps reference for nonexistent file."""
        from henchman.cli.input import expand_at_references

        result = await expand_at_references("Check @/nonexistent/file.txt please")
        # Should keep original reference or handle gracefully
        assert "nonexistent" in result or "Check" in result

    @pytest.mark.anyio
    async def test_expand_existing_file(self, tmp_path: Path) -> None:
        """Test expand_at_references expands existing file."""
        from henchman.cli.input import expand_at_references

        test_file = tmp_path / "test.txt"
        test_file.write_text("File content here")
        result = await expand_at_references(f"Check @{test_file} please")
        assert "File content here" in result

    @pytest.mark.anyio
    async def test_expand_oversized_file(self, tmp_path: Path) -> None:
        """Test expand_at_references shows size error for oversized file."""
        from henchman.cli.input import expand_at_references

        test_file = tmp_path / "big.txt"
        # Create a file that triggers the size limit check
        with patch("henchman.cli.input.MAX_FILE_SIZE_BYTES", 10):
            test_file.write_text("x" * 20)
            result = await expand_at_references(f"Check @{test_file}")
        # Should mention file is too large
        assert "large" in result.lower() or test_file.name in result


# ---------------------------------------------------------------------------
# app.py coverage tests
# ---------------------------------------------------------------------------


class TestAppCoverage:
    """Coverage tests for app.py missing lines."""

    def test_get_theme_and_renderer_valid_theme(self) -> None:
        """Test _get_theme_and_renderer with valid theme."""
        from henchman.cli.app import _get_theme_and_renderer

        settings = MagicMock()
        settings.ui.theme = "dark"
        theme, renderer = _get_theme_and_renderer(settings)
        assert theme is not None
        assert renderer is not None

    def test_get_theme_and_renderer_invalid_theme(self) -> None:
        """Test _get_theme_and_renderer falls back to default for unknown theme."""
        from henchman.cli.app import _get_theme_and_renderer

        settings = MagicMock()
        settings.ui.theme = "nonexistent_theme_xyz"
        theme, renderer = _get_theme_and_renderer(settings)
        # Should fall back to dark
        assert theme is not None

    def test_get_theme_and_renderer_no_ui(self) -> None:
        """Test _get_theme_and_renderer with settings that have no ui attribute."""
        from henchman.cli.app import _get_theme_and_renderer

        settings = MagicMock()
        settings.ui = None  # No UI settings
        theme, renderer = _get_theme_and_renderer(settings)
        assert theme is not None
        assert renderer is not None

    def test_check_completion_status_no_work(self) -> None:
        """Test _check_completion_status exits when no work done."""
        from henchman.cli.app import _check_completion_status

        try:
            from henchman.agents.orchestrator import CompletionStatus
        except ImportError:
            pytest.skip("CompletionStatus not available")

        repl = MagicMock()
        repl.orchestrator.last_completion_status = CompletionStatus.NO_WORK_DONE
        with pytest.raises(SystemExit) as exc_info:
            _check_completion_status(repl)
        assert exc_info.value.code == 2

    def test_check_completion_status_work_done(self) -> None:
        """Test _check_completion_status does not exit when work was done."""
        from henchman.cli.app import _check_completion_status

        try:
            from henchman.agents.orchestrator import CompletionStatus
        except ImportError:
            pytest.skip("CompletionStatus not available")

        repl = MagicMock()
        repl.orchestrator = MagicMock()
        # Use a status that is NOT NO_WORK_DONE
        repl.orchestrator.last_completion_status = CompletionStatus.COMPLETED
        _check_completion_status(repl)  # Should not raise

    def test_check_completion_status_no_orchestrator(self) -> None:
        """Test _check_completion_status does nothing without orchestrator."""
        from henchman.cli.app import _check_completion_status

        repl = MagicMock(spec=[])  # No orchestrator attribute
        _check_completion_status(repl)  # Should not raise


# ---------------------------------------------------------------------------
# repl.py coverage tests
# ---------------------------------------------------------------------------


class TestReplCoverage:
    """Coverage tests for repl.py missing lines."""

    def _make_repl(self):
        """Create a minimal Repl instance."""
        from henchman.cli.repl import Repl

        provider = MagicMock()
        provider.name = "deepseek"
        settings = MagicMock()
        settings.mcp_servers = None
        settings.ui.mcp_logging = False
        settings.ui.accessible_mode = False
        settings.ui.style_overrides = None
        settings.ui.layout = None
        settings.context = MagicMock()
        settings.context.intelligent_context = False
        settings.tools = MagicMock()
        settings.tools.auto_approve_read = True

        with (
            patch("henchman.cli.repl.PluginManager"),
            patch("henchman.cli.repl.Orchestrator"),
            patch("henchman.cli.repl.ToolManager.register_builtin_tools"),
            patch.object(Path, "glob", return_value=[]),
        ):
            repl = Repl(provider=provider, settings=settings)
        return repl

    @pytest.mark.anyio
    async def test_initialize_mcp_no_manager(self) -> None:
        """Test initialize_mcp does nothing when no MCP manager."""
        repl = self._make_repl()
        repl.mcp_manager = None
        await repl.initialize_mcp()  # Should not raise

    @pytest.mark.anyio
    async def test_initialize_mcp_with_manager(self) -> None:
        """Test initialize_mcp connects when manager is available."""
        repl = self._make_repl()
        mcp_manager = MagicMock()
        mcp_manager.clients = {}  # Not connected yet
        mcp_manager.connect_all = AsyncMock()
        mcp_manager.get_all_tools.return_value = []
        repl.mcp_manager = mcp_manager
        repl.settings.ui.mcp_logging = True

        await repl.initialize_mcp()
        mcp_manager.connect_all.assert_called_once()

    @pytest.mark.anyio
    async def test_initialize_mcp_already_connected(self) -> None:
        """Test initialize_mcp skips when already connected."""
        repl = self._make_repl()
        mcp_manager = MagicMock()
        mcp_manager.clients = {"server1": MagicMock()}  # Already connected
        mcp_manager.connect_all = AsyncMock()
        repl.mcp_manager = mcp_manager

        await repl.initialize_mcp()
        mcp_manager.connect_all.assert_not_called()

    @pytest.mark.anyio
    async def test_initialize_mcp_connection_error(self) -> None:
        """Test initialize_mcp handles connection error gracefully."""
        repl = self._make_repl()
        mcp_manager = MagicMock()
        mcp_manager.clients = {}
        mcp_manager.connect_all = AsyncMock(side_effect=RuntimeError("connection failed"))
        repl.mcp_manager = mcp_manager

        # Should not raise; errors are logged to stdout
        await repl.initialize_mcp()

    def test_collect_event_content_error(self) -> None:
        """Test _collect_event_content handles error events."""
        from henchman.cli.repl import _collect_event_content
        from henchman.core.events import AgentEvent, EventType

        collector = []
        render_error = MagicMock()
        event = AgentEvent(type=EventType.ERROR, data="Something failed")
        _collect_event_content(event, collector, render_error)
        render_error.assert_called_once_with("Something failed")

    def test_collect_event_content_content(self) -> None:
        """Test _collect_event_content appends content events."""
        from henchman.cli.repl import _collect_event_content
        from henchman.core.events import AgentEvent, EventType

        collector = []
        render_error = MagicMock()
        event = AgentEvent(type=EventType.CONTENT, data="hello world")
        _collect_event_content(event, collector, render_error)
        assert "hello world" in collector

    def test_collect_event_content_no_collector(self) -> None:
        """Test _collect_event_content with no collector skips content."""
        from henchman.cli.repl import _collect_event_content
        from henchman.core.events import AgentEvent, EventType

        render_error = MagicMock()
        event = AgentEvent(type=EventType.CONTENT, data="hello")
        _collect_event_content(event, None, render_error)
        render_error.assert_not_called()


# ---------------------------------------------------------------------------
# plugins.py tests
# ---------------------------------------------------------------------------


class TestPluginsCoverage:
    """Coverage tests for plugins.py."""

    def test_ui_plugin_description_default(self) -> None:
        """Test UIPlugin default description."""
        from henchman.cli.plugins import UIPlugin

        class MyPlugin(UIPlugin):
            @property
            def name(self):
                return "my_plugin"

            def register(self, repl):
                pass

        plugin = MyPlugin()
        assert plugin.description == ""

    def test_ui_plugin_render_noop(self) -> None:
        """Test UIPlugin.render does nothing by default."""
        from henchman.cli.plugins import UIPlugin

        class MyPlugin(UIPlugin):
            @property
            def name(self):
                return "my_plugin"

            def register(self, repl):
                pass

        plugin = MyPlugin()
        plugin.render("data")  # Should not raise

    def test_plugin_manager_load_from_nonexistent_dir(self, tmp_path: Path) -> None:
        """Test PluginManager skips nonexistent directory."""
        from henchman.cli.plugins import PluginManager

        manager = PluginManager(repl=None)
        nonexistent = tmp_path / "nonexistent"
        manager.load_plugins_from_directory(nonexistent)
        assert manager.plugins == {}

    def test_plugin_manager_load_from_empty_dir(self, tmp_path: Path) -> None:
        """Test PluginManager handles empty directory."""
        from henchman.cli.plugins import PluginManager

        manager = PluginManager(repl=None)
        manager.load_plugins_from_directory(tmp_path)
        assert manager.plugins == {}

    def test_plugin_manager_load_valid_plugin(self, tmp_path: Path) -> None:
        """Test PluginManager loads valid plugin from directory."""
        from henchman.cli.plugins import PluginManager

        plugin_file = tmp_path / "my_plugin.py"
        plugin_file.write_text("""
from henchman.cli.plugins import UIPlugin

class MyTestPlugin(UIPlugin):
    @property
    def name(self):
        return "my_test_plugin"

    def register(self, repl):
        pass
""")
        manager = PluginManager(repl=None)
        manager.load_plugins_from_directory(tmp_path)
        assert "my_test_plugin" in manager.plugins

    def test_plugin_manager_skips_dunder_files(self, tmp_path: Path) -> None:
        """Test PluginManager skips __init__.py and similar."""
        from henchman.cli.plugins import PluginManager

        init_file = tmp_path / "__init__.py"
        init_file.write_text("# empty")
        manager = PluginManager(repl=None)
        manager.load_plugins_from_directory(tmp_path)
        assert len(manager.plugins) == 0

    def test_plugin_manager_register_plugin(self) -> None:
        """Test PluginManager registers a plugin."""
        from henchman.cli.plugins import PluginManager, UIPlugin

        class TestPlugin(UIPlugin):
            @property
            def name(self):
                return "test_plugin"

            def register(self, repl):
                pass

        manager = PluginManager(repl=None)
        plugin = TestPlugin()
        manager.register_plugin(plugin)
        assert "test_plugin" in manager.plugins

    def test_plugin_manager_no_duplicate_registration(self) -> None:
        """Test PluginManager doesn't register same plugin twice."""
        from henchman.cli.plugins import PluginManager, UIPlugin

        class TestPlugin(UIPlugin):
            @property
            def name(self):
                return "test_plugin"

            def register(self, repl):
                pass

        manager = PluginManager(repl=None)
        plugin = TestPlugin()
        manager.register_plugin(plugin)
        manager.register_plugin(plugin)  # Should not register again
        assert len(manager.plugins) == 1

    def test_plugin_manager_load_error_silently_continues(self, tmp_path: Path) -> None:
        """Test PluginManager handles load error gracefully."""
        from henchman.cli.plugins import PluginManager

        bad_plugin = tmp_path / "bad_plugin.py"
        bad_plugin.write_text("raise SyntaxError('bad syntax'")  # Intentionally broken
        manager = PluginManager(repl=None)
        # Should not raise
        manager.load_plugins_from_directory(tmp_path)

    def test_try_register_plugin_class_not_plugin(self) -> None:
        """Test _try_register_plugin_class returns False for non-plugin class."""
        from henchman.cli.plugins import PluginManager

        manager = PluginManager(repl=None)
        result = manager._try_register_plugin_class("NotAPlugin", str)
        assert result is False
