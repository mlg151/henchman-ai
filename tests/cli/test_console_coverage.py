"""Tests for console.py, console_helpers.py, core_init.py, and tool_manager.py coverage."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# console.py coverage tests
# ---------------------------------------------------------------------------


class TestConsoleCoverage:
    """Coverage tests for console.py missing lines."""

    def _make_renderer(self):
        """Create an OutputRenderer instance."""
        from henchman.cli.console import DARK_THEME, OutputRenderer

        return OutputRenderer(theme=DARK_THEME)

    def test_table_empty_data(self) -> None:
        """Test table with empty data shows muted message."""
        renderer = self._make_renderer()
        with patch.object(renderer, "muted") as mock_muted:
            renderer.table([])
        mock_muted.assert_called_once_with("No data to display")

    def test_table_with_data(self) -> None:
        """Test table with data renders a table."""
        renderer = self._make_renderer()
        data = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
        renderer.table(data, title="Users")  # Should not raise

    def test_table_with_title(self) -> None:
        """Test table renders with title."""
        renderer = self._make_renderer()
        data = [{"col1": "val1"}]
        renderer.table(data, title="Test Table")

    def test_tree_basic(self) -> None:
        """Test tree renders basic tree."""
        renderer = self._make_renderer()
        items = [("root/child1", "value1"), ("root/child2", "value2")]
        renderer.tree("Root", items)  # Should not raise

    def test_tree_deep_nested(self) -> None:
        """Test tree renders deep nested paths."""
        renderer = self._make_renderer()
        items = [("a/b/c/d", "deep_value")]
        renderer.tree("Root", items)

    def test_diff_with_strings(self) -> None:
        """Test diff with three string arguments."""
        renderer = self._make_renderer()
        renderer.diff("old content\n", "new content\n", "test.py")

    def test_diff_with_params_object(self) -> None:
        """Test diff with DiffParams object."""
        from henchman.cli.console import DiffParams
        renderer = self._make_renderer()
        params = DiffParams(old="old\n", new="new\n", filename="test.py")
        renderer.diff(params)

    def test_diff_no_differences(self) -> None:
        """Test diff shows no differences message when content is same."""
        renderer = self._make_renderer()
        with patch.object(renderer, "success") as mock_success:
            renderer.diff("same content\n", "same content\n", "test.py")
        mock_success.assert_called_once_with("No differences found")

    def test_code_method(self) -> None:
        """Test code renders syntax-highlighted code."""
        renderer = self._make_renderer()
        renderer.code("def hello():\n    pass", "python")

    def test_code_empty(self) -> None:
        """Test code with empty string does nothing."""
        renderer = self._make_renderer()
        renderer.code("")  # Should not raise

    def test_markdown_truncation(self) -> None:
        """Test markdown truncates very long content."""
        renderer = self._make_renderer()
        long_content = "# Title\n\n" + "word " * 50000  # Very long
        renderer.markdown(long_content)  # Should not raise

    def test_tool_result_success(self) -> None:
        """Test tool_result renders successful result."""
        renderer = self._make_renderer()
        renderer.tool_result("File contents here", success=True)

    def test_tool_result_failure(self) -> None:
        """Test tool_result renders failed result."""
        renderer = self._make_renderer()
        renderer.tool_result("", success=False, error="Permission denied")

    def test_tool_summary(self) -> None:
        """Test tool_summary renders summary."""
        renderer = self._make_renderer()
        renderer.tool_summary("read_file", duration=0.5)

    def test_tool_summary_no_duration(self) -> None:
        """Test tool_summary without duration."""
        renderer = self._make_renderer()
        renderer.tool_summary("write_file")

    def test_print_agent_content(self) -> None:
        """Test print_agent_content outputs content."""
        renderer = self._make_renderer()
        renderer.print_agent_content("Hello from agent")

    def test_agent_content_alias(self) -> None:
        """Test agent_content is alias for print_agent_content."""
        renderer = self._make_renderer()
        renderer.agent_content("Hello from agent")

    def test_thinking_method(self) -> None:
        """Test thinking renders thinking content."""
        renderer = self._make_renderer()
        renderer.thinking("I am thinking about...")

    def test_list_dict_keys(self) -> None:
        """Test list_dict_keys returns list of keys."""
        from henchman.cli.console import list_dict_keys

        result = list_dict_keys({"a": 1, "b": 2, "c": 3})
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_rule_method(self) -> None:
        """Test rule renders a horizontal rule."""
        renderer = self._make_renderer()
        renderer.rule("Section Title")

    def test_rule_no_title(self) -> None:
        """Test rule renders without title."""
        renderer = self._make_renderer()
        renderer.rule()

    def test_status_message_params(self) -> None:
        """Test StatusMessageParams dataclass works correctly."""
        from henchman.cli.console import StatusMessageParams, StatusType

        params = StatusMessageParams(message="Test message", status_type=StatusType.SUCCESS)
        assert params.message == "Test message"
        assert params.status_type == StatusType.SUCCESS


class TestAsyncOutputRenderer:
    """Tests for AsyncOutputRenderer class."""

    def _make_async_renderer(self):
        """Create an AsyncOutputRenderer."""
        from henchman.cli.console import DARK_THEME, AsyncOutputRenderer, OutputRenderer

        sync_renderer = OutputRenderer(theme=DARK_THEME)
        return AsyncOutputRenderer(sync_renderer)

    def test_init(self) -> None:
        """Test AsyncOutputRenderer initializes correctly."""
        renderer = self._make_async_renderer()
        assert renderer.renderer is not None
        assert renderer._async_methods is None

    def test_getattr_creates_wrapper(self) -> None:
        """Test __getattr__ creates wrapper for valid method."""
        renderer = self._make_async_renderer()
        method = renderer.success
        assert callable(method)

    def test_getattr_caches_wrapper(self) -> None:
        """Test __getattr__ caches wrapper after first access."""
        renderer = self._make_async_renderer()
        method1 = renderer.success
        method2 = renderer.success
        assert method1 is method2

    def test_getattr_missing_method_raises(self) -> None:
        """Test __getattr__ raises AttributeError for missing method."""
        renderer = self._make_async_renderer()
        with pytest.raises(AttributeError):
            _ = renderer.nonexistent_method

    def test_getattr_private_method_raises(self) -> None:
        """Test __getattr__ raises AttributeError for private method."""
        renderer = self._make_async_renderer()
        with pytest.raises(AttributeError):
            _ = renderer._private_method

    @pytest.mark.anyio
    async def test_async_wrapper_calls_sync(self) -> None:
        """Test async wrapper calls sync method."""
        renderer = self._make_async_renderer()
        with patch.object(renderer.renderer, "success") as mock_success:
            await renderer.success("test message")
        mock_success.assert_called_once_with("test message")

    @pytest.mark.anyio
    async def test_async_diff_wrapper(self) -> None:
        """Test async diff wrapper."""
        renderer = self._make_async_renderer()
        # Should be callable
        diff_method = renderer.diff
        assert callable(diff_method)


# ---------------------------------------------------------------------------
# console_helpers.py coverage tests
# ---------------------------------------------------------------------------


class TestConsoleHelpersCoverage:
    """Coverage tests for console_helpers.py missing lines."""

    def test_print_error_message_with_usage(self) -> None:
        """Test print_error_message includes usage when provided."""
        from henchman.cli.console_helpers import ConsoleHelper

        console = MagicMock()
        ConsoleHelper.print_error_message(console, "bad input", "/cmd <arg>")
        calls = [str(c) for c in console.print.call_args_list]
        assert any("bad input" in c for c in calls)
        assert any("/cmd <arg>" in c for c in calls)

    def test_print_error_message_no_usage(self) -> None:
        """Test print_error_message without usage."""
        from henchman.cli.console_helpers import ConsoleHelper

        console = MagicMock()
        ConsoleHelper.print_error_message(console, "bad input")
        calls = [str(c) for c in console.print.call_args_list]
        assert any("bad input" in c for c in calls)

    def test_print_usage_help(self) -> None:
        """Test print_usage_help formats commands list."""
        from henchman.cli.console_helpers import ConsoleHelper

        console = MagicMock()
        ConsoleHelper.print_usage_help(
            console,
            "/cmd [subcommand]",
            [("sub1", "First subcommand"), ("sub2", "Second subcommand")],
        )
        assert console.print.call_count >= 3

    def test_print_usage_help_no_commands(self) -> None:
        """Test print_usage_help with empty commands list."""
        from henchman.cli.console_helpers import ConsoleHelper

        console = MagicMock()
        ConsoleHelper.print_usage_help(console, "/cmd", [])
        console.print.assert_called()

    def test_print_parameter_list(self) -> None:
        """Test print_parameter_list formats parameters."""
        from henchman.cli.console_helpers import ConsoleHelper

        console = MagicMock()
        ConsoleHelper.print_parameter_list(
            console,
            [("param1 <value>", "Description 1"), ("param2 <value>", "Description 2")],
        )
        assert console.print.call_count >= 3


# ---------------------------------------------------------------------------
# core_init.py coverage tests
# ---------------------------------------------------------------------------


class TestCoreInitCoverage:
    """Coverage tests for core_init.py missing lines."""

    @pytest.mark.anyio
    async def test_initialize_mcp_with_manager(self) -> None:
        """Test initialize_mcp with MCP manager triggers background connect."""
        from henchman.cli.core_init import initialize_mcp

        mcp_manager = MagicMock()
        mcp_manager.clients = {}  # Not connected
        mcp_manager.connect_all = AsyncMock()
        mcp_manager.get_all_tools.return_value = []

        tool_registry = MagicMock()

        context = MagicMock()
        context.mcp_manager = mcp_manager
        context.tool_registry = tool_registry

        with patch("asyncio.create_task") as mock_task:
            initialize_mcp(context)
            mock_task.assert_called_once()
            mock_task.call_args.args[0].close()

    def test_initialize_mcp_no_manager(self) -> None:
        """Test initialize_mcp with no MCP manager does nothing."""
        from henchman.cli.core_init import initialize_mcp

        context = MagicMock()
        context.mcp_manager = None

        with patch("asyncio.create_task") as mock_task:
            initialize_mcp(context)
            mock_task.assert_not_called()

    def test_initialize_mcp_already_connected(self) -> None:
        """Test initialize_mcp with already-connected manager does nothing."""
        from henchman.cli.core_init import initialize_mcp

        mcp_manager = MagicMock()
        mcp_manager.clients = {"server1": MagicMock()}  # Already connected

        context = MagicMock()
        context.mcp_manager = mcp_manager

        with patch("asyncio.create_task") as mock_task:
            initialize_mcp(context)
            mock_task.assert_not_called()


# ---------------------------------------------------------------------------
# tool_manager.py coverage tests
# ---------------------------------------------------------------------------


class TestToolManagerCoverage:
    """Coverage tests for tool_manager.py missing lines."""

    def _make_tool_manager(self):
        """Create a ToolManager instance."""
        from henchman.cli.tool_manager import ToolManager

        settings = MagicMock()
        settings.ui = MagicMock()
        settings.tools = MagicMock()
        return ToolManager(settings=settings)

    def test_handle_confirmation_auto_approve(self) -> None:
        """Test handle_confirmation auto-approves when configured."""
        from henchman.tools.base import ConfirmationRequest

        async def _run():
            tm = self._make_tool_manager()
            tm.set_auto_approve(auto_approve=True)
            request = ConfirmationRequest(
                tool_name="shell",
                params={"command": "ls"},
                description="Run shell",
            )
            result = await tm.handle_confirmation(request)
            assert result is True

        import asyncio
        asyncio.run(_run())

    def test_handle_confirmation_default_false(self) -> None:
        """Test handle_confirmation returns False by default."""
        from henchman.tools.base import ConfirmationRequest

        async def _run():
            tm = self._make_tool_manager()
            tm.auto_approve = False
            tm._confirmation_handler = None
            request = ConfirmationRequest(
                tool_name="write_file",
                params={"path": "/tmp/x.txt"},
                description="Write file",
            )
            result = await tm.handle_confirmation(request)
            assert result is False

        import asyncio
        asyncio.run(_run())

    def test_handle_confirmation_custom_handler(self) -> None:
        """Test handle_confirmation uses custom handler."""
        from henchman.tools.base import ConfirmationRequest

        async def _run():
            tm = self._make_tool_manager()
            tm.auto_approve = False

            async def custom_handler(_req):
                return True

            tm._confirmation_handler = custom_handler
            request = ConfirmationRequest(
                tool_name="shell",
                params={"command": "echo hi"},
                description="Run shell",
            )
            result = await tm.handle_confirmation(request)
            assert result is True

        import asyncio
        asyncio.run(_run())

    def test_set_confirmation_handler(self) -> None:
        """Test set_confirmation_handler sets the handler."""
        async def _run():
            async def handler(_req):
                return True

            tm = self._make_tool_manager()
            tm.set_confirmation_handler(handler)
            assert tm._confirmation_handler is handler

        import asyncio
        asyncio.run(_run())

    def test_set_auto_approve(self) -> None:
        """Test set_auto_approve changes auto_approve flag."""
        tm = self._make_tool_manager()
        tm.set_auto_approve(auto_approve=True)
        assert tm.auto_approve is True
        tm.set_auto_approve(auto_approve=False)
        assert tm.auto_approve is False

    def test_set_plan_mode(self) -> None:
        """Test set_plan_mode sets plan mode on registry."""
        tm = self._make_tool_manager()
        # Replace registry with mock to verify call
        tm.registry = MagicMock()
        tm.set_plan_mode(plan_mode=True)
        tm.registry.set_plan_mode.assert_called_once_with(enabled=True)
