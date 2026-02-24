"""Comprehensive tests for ask_user tool."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.tools.builtins.ask_user import AskUserTool


class TestAskUserTool:
    """Comprehensive tests for AskUserTool."""
    
    def test_properties(self) -> None:
        """Test tool properties."""
        tool = AskUserTool()
        
        assert tool.name == "ask_user"
        assert "Ask the user a question" in tool.description
        assert tool.kind.name == "READ"  # ToolKind.READ
        
        # Check parameters schema
        params = tool.parameters
        assert params["type"] == "object"
        assert "question" in params["properties"]
        assert "timeout" in params["properties"]
        assert "question" in params["required"]
    
    @pytest.mark.anyio
    async def test_execute_basic(self) -> None:
        """Test basic execution with user response."""
        tool = AskUserTool()
        
        result = await tool.execute(question="What is your name?")
        
        assert "[User input would be collected here" in result.content
        assert "🤔 Question: What is your name?" in result.display
        assert result.success is True
    
    @pytest.mark.anyio
    async def test_execute_with_timeout(self) -> None:
        """Test execution with timeout."""
        tool = AskUserTool()
        
        result = await tool.execute(question="Test", timeout=30)
        
        # Timeout parameter is accepted but not used in current implementation
        assert "[User input would be collected here" in result.content
    
    @pytest.mark.anyio
    async def test_execute_empty_question(self) -> None:
        """Test execution with empty question."""
        tool = AskUserTool()
        
        result = await tool.execute(question="")
        
        assert "[User input would be collected here" in result.content
        assert "🤔 Question: " in result.display
    
    def test_str_representation(self) -> None:
        """Test string representation of tool result."""
        from henchman.tools.base import ToolResult
        
        result = ToolResult(content="Test answer")
        assert "Test answer" in str(result)
    
    def test_tool_registration(self) -> None:
        """Test that tool can be registered in registry."""
        from henchman.tools.registry import ToolRegistry
        
        registry = ToolRegistry()
        tool = AskUserTool()
        registry.register(tool)
        
        # Check tool is registered
        declarations = registry.get_declarations()
        tool_names = [d.name for d in declarations]
        assert "ask_user" in tool_names
        
        # Check tool declaration matches
        for decl in declarations:
            if decl.name == "ask_user":
                assert "Ask the user a question" in decl.description
                break
    
    @pytest.mark.anyio
    async def test_execute_method_is_async(self) -> None:
        """Test the execute method exists and is async."""
        tool = AskUserTool()

        assert hasattr(tool, "execute")
        assert asyncio.iscoroutinefunction(tool.execute)