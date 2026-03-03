"""Tests for UIRenderer delegation methods (previously uncovered)."""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

from henchman.cli.ui_renderer import UIRenderer


def _make_renderer() -> UIRenderer:
    """Create a UIRenderer with a test console."""
    console = Console(file=StringIO(), highlight=False)
    return UIRenderer(console=console)


class TestUIRendererDelegation:
    """Tests for UIRenderer methods that delegate to OutputRenderer."""

    def test_warning(self) -> None:
        """Test warning delegates to renderer.warning."""
        ui = _make_renderer()
        ui.renderer.warning = MagicMock()
        ui.warning("test warning")
        ui.renderer.warning.assert_called_once_with("test warning")

    def test_heading(self) -> None:
        """Test heading delegates to renderer.heading."""
        ui = _make_renderer()
        ui.renderer.heading = MagicMock()
        ui.heading("test heading")
        ui.renderer.heading.assert_called_once_with("test heading")

    def test_markdown(self) -> None:
        """Test markdown delegates to renderer.markdown."""
        ui = _make_renderer()
        ui.renderer.markdown = MagicMock()
        ui.markdown("# Hello")
        ui.renderer.markdown.assert_called_once_with("# Hello")

    def test_code(self) -> None:
        """Test code delegates to renderer.code."""
        ui = _make_renderer()
        ui.renderer.code = MagicMock()
        ui.code("print('hi')", "python")
        ui.renderer.code.assert_called_once_with("print('hi')", "python")

    def test_rule(self) -> None:
        """Test rule delegates to renderer.rule."""
        ui = _make_renderer()
        ui.renderer.rule = MagicMock()
        ui.rule("title")
        ui.renderer.rule.assert_called_once_with("title")

    def test_clear(self) -> None:
        """Test clear delegates to renderer.clear."""
        ui = _make_renderer()
        ui.renderer.clear = MagicMock()
        ui.clear()
        ui.renderer.clear.assert_called_once()

    def test_tool_call(self) -> None:
        """Test tool_call delegates to renderer.tool_call."""
        ui = _make_renderer()
        ui.renderer.tool_call = MagicMock()
        ui.tool_call("my_tool", {"key": "value"})
        ui.renderer.tool_call.assert_called_once_with("my_tool", {"key": "value"})

    def test_tool_result(self) -> None:
        """Test tool_result delegates to renderer.tool_result."""
        ui = _make_renderer()
        ui.renderer.tool_result = MagicMock()
        ui.tool_result("output", success=True, error=None)
        ui.renderer.tool_result.assert_called_once_with("output", success=True, error=None)

    def test_tool_summary(self) -> None:
        """Test tool_summary delegates to renderer.tool_summary."""
        ui = _make_renderer()
        ui.renderer.tool_summary = MagicMock()
        ui.tool_summary("my_tool", 1.5)
        ui.renderer.tool_summary.assert_called_once_with("my_tool", 1.5)

    def test_agent_content(self) -> None:
        """Test agent_content delegates to renderer.agent_content."""
        ui = _make_renderer()
        ui.renderer.agent_content = MagicMock()
        ui.agent_content("hello world")
        ui.renderer.agent_content.assert_called_once_with("hello world")

    def test_show_thinking(self) -> None:
        """Test show_thinking calls thinking which delegates."""
        ui = _make_renderer()
        ui.renderer.thinking = MagicMock()
        ui.show_thinking("deep thought")
        ui.renderer.thinking.assert_called_once_with("deep thought")

    @pytest.mark.anyio
    async def test_confirm_tool_execution(self) -> None:
        """Test confirm_tool_execution delegates to renderer."""
        ui = _make_renderer()
        ui.renderer.confirm_tool_execution = AsyncMock(return_value=True)
        result = await ui.confirm_tool_execution("Do this?")
        assert result is True
        ui.renderer.confirm_tool_execution.assert_called_once_with("Do this?")

    def test_start_task(self) -> None:
        """Test start_task delegates to progress_manager."""
        ui = _make_renderer()
        ui.progress_manager.start_task = MagicMock(return_value=MagicMock())
        ui.start_task("task1", "Loading...", 50)
        ui.progress_manager.start_task.assert_called_once_with("task1", "Loading...", 50)

    def test_update_task(self) -> None:
        """Test update_task delegates to progress_manager."""
        ui = _make_renderer()
        ui.progress_manager.update_task = MagicMock()
        ui.update_task("task1", advance=5, description="Still loading...")
        ui.progress_manager.update_task.assert_called_once_with("task1", advance=5, description="Still loading...")

    def test_complete_task(self) -> None:
        """Test complete_task delegates to progress_manager."""
        ui = _make_renderer()
        ui.progress_manager.complete_task = MagicMock()
        ui.complete_task("task1")
        ui.progress_manager.complete_task.assert_called_once_with("task1")

    def test_create_status(self) -> None:
        """Test create_status returns a Rich Status context manager."""
        ui = _make_renderer()
        status = ui.create_status("Working...", spinner="dots")
        assert status is not None


class TestUIRendererStatusMessage:
    """Tests for get_rich_status_message edge cases."""

    def test_status_message_exception_in_token_count(self) -> None:
        """Test that token counting exception is silently ignored."""
        ui = _make_renderer()
        mock_session = MagicMock()
        mock_session.plan_mode = False
        mock_agent = MagicMock()
        mock_agent.get_messages_for_api = MagicMock(side_effect=RuntimeError("oops"))

        # Should not raise
        msg = ui.get_rich_status_message(mock_session, mock_agent)
        assert isinstance(msg, str)
        # Tokens part should be missing due to exception
        assert "Tokens" not in msg

    def test_status_message_rag_indexing(self) -> None:
        """Test that RAG indexing status is included."""
        ui = _make_renderer()
        mock_session = MagicMock()
        mock_session.plan_mode = False
        mock_rag = MagicMock()
        mock_rag.is_indexing = True

        msg = ui.get_rich_status_message(mock_session, None, rag_system=mock_rag)
        assert "RAG" in msg
        assert "Indexing" in msg
