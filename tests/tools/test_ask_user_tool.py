"""Tests for the ask_user tool."""

from __future__ import annotations

import pytest

from henchman.tools.builtins.ask_user import AskUserTool


class TestAskUserTool:
    """Test the AskUserTool class."""

    @pytest.fixture
    def tool(self) -> AskUserTool:
        """Return an AskUserTool instance."""
        return AskUserTool()

    def test_name(self, tool: AskUserTool) -> None:
        """Test the tool name."""
        assert tool.name == "ask_user"

    def test_description(self, tool: AskUserTool) -> None:
        """Test the tool description."""
        assert "ask the user" in tool.description.lower()

    def test_kind(self, tool: AskUserTool) -> None:
        """Test the tool kind."""
        from henchman.tools.base import ToolKind

        assert tool.kind == ToolKind.READ

    def test_parameters(self, tool: AskUserTool) -> None:
        """Test the tool parameters schema."""
        params = tool.parameters
        assert params["type"] == "object"
        assert "question" in params["properties"]
        assert "timeout" in params["properties"]
        assert "question" in params["required"]

    def test_needs_confirmation(self, tool: AskUserTool) -> None:
        """Test that ask_user never needs confirmation."""
        assert tool.needs_confirmation({"question": "test"}) is None

    @pytest.mark.asyncio
    async def test_execute_success(self, tool: AskUserTool) -> None:
        """Test successful execution."""
        result = await tool.execute(question="What is your name?")
        assert result.success
        assert "User input would be collected" in result.content
        assert result.display is not None
        assert "🤔" in result.display

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, tool: AskUserTool) -> None:
        """Test execution with timeout parameter."""
        result = await tool.execute(question="What is your name?", timeout=10)
        assert result.success
        assert "User input would be collected" in result.content

    @pytest.mark.asyncio
    async def test_execute_empty_question(self, tool: AskUserTool) -> None:
        """Test execution with empty question."""
        result = await tool.execute(question="")
        assert result.success
        assert "User input would be collected" in result.content
