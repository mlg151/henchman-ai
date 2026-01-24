"""Tests for ToolRegistry."""

import pytest

from henchman.tools.base import (
    ConfirmationRequest,
    Tool,
    ToolKind,
    ToolResult,
)
from henchman.tools.registry import ToolRegistry


class MockReadTool(Tool):
    """A mock read-only tool for testing."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "read_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Read a file"

    @property
    def parameters(self) -> dict:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """Read-only tool."""
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool."""
        path = params.get("path", "")
        return ToolResult(content=f"Contents of {path}")


class MockWriteTool(Tool):
    """A mock write tool for testing."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "write_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Write to a file"

    @property
    def parameters(self) -> dict:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        }

    @property
    def kind(self) -> ToolKind:
        """Write tool."""
        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool."""
        path = params.get("path", "")
        return ToolResult(content=f"Wrote to {path}")


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_empty_registry(self) -> None:
        """New registry has no tools."""
        registry = ToolRegistry()
        assert registry.list_tools() == []
        assert registry.get_declarations() == []

    def test_register_tool(self) -> None:
        """Can register a tool."""
        registry = ToolRegistry()
        tool = MockReadTool()
        registry.register(tool)
        assert "read_file" in registry.list_tools()

    def test_register_multiple_tools(self) -> None:
        """Can register multiple tools."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        registry.register(MockWriteTool())
        tools = registry.list_tools()
        assert "read_file" in tools
        assert "write_file" in tools
        assert len(tools) == 2

    def test_get_tool(self) -> None:
        """Can retrieve a registered tool."""
        registry = ToolRegistry()
        tool = MockReadTool()
        registry.register(tool)
        retrieved = registry.get("read_file")
        assert retrieved is tool

    def test_get_nonexistent_tool(self) -> None:
        """Getting nonexistent tool returns None."""
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_get_declarations(self) -> None:
        """Can get tool declarations for LLM."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        registry.register(MockWriteTool())
        declarations = registry.get_declarations()
        assert len(declarations) == 2
        names = {d.name for d in declarations}
        assert names == {"read_file", "write_file"}

    def test_duplicate_registration_raises(self) -> None:
        """Registering duplicate tool name raises error."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(MockReadTool())

    def test_unregister_tool(self) -> None:
        """Can unregister a tool."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        assert "read_file" in registry.list_tools()
        registry.unregister("read_file")
        assert "read_file" not in registry.list_tools()

    def test_unregister_nonexistent_silent(self) -> None:
        """Unregistering nonexistent tool is silent."""
        registry = ToolRegistry()
        registry.unregister("nonexistent")  # Should not raise


class TestToolRegistryExecution:
    """Tests for tool execution through registry."""

    async def test_execute_read_tool(self) -> None:
        """Execute a read tool through registry."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        result = await registry.execute("read_file", {"path": "/test.txt"})
        assert result.content == "Contents of /test.txt"
        assert result.success is True

    async def test_execute_nonexistent_tool(self) -> None:
        """Executing nonexistent tool returns error result."""
        registry = ToolRegistry()
        result = await registry.execute("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_execute_write_tool_without_confirmation(self) -> None:
        """Write tool executes when no confirmation handler set."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())
        result = await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert result.success is True

    async def test_execute_with_confirmation_handler_approved(self) -> None:
        """Tool executes when confirmation handler approves."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        async def approve_handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            return True

        registry.set_confirmation_handler(approve_handler)
        result = await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert result.success is True
        assert result.content == "Wrote to /x"

    async def test_execute_with_confirmation_handler_denied(self) -> None:
        """Tool does not execute when confirmation handler denies."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        async def deny_handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            return False

        registry.set_confirmation_handler(deny_handler)
        result = await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert result.success is False
        assert "denied" in result.content.lower() or "denied" in result.error.lower()

    async def test_read_tool_skips_confirmation(self) -> None:
        """Read tools skip confirmation even with handler set."""
        registry = ToolRegistry()
        registry.register(MockReadTool())

        handler_called = False

        async def handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            nonlocal handler_called
            handler_called = True
            return False  # Would deny if called

        registry.set_confirmation_handler(handler)
        result = await registry.execute("read_file", {"path": "/test.txt"})
        assert result.success is True  # Still executed
        assert not handler_called  # Handler not invoked


class TestToolRegistryPolicyEngine:
    """Tests for PolicyEngine integration."""

    async def test_policy_auto_approve(self) -> None:
        """PolicyEngine can auto-approve tools."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        # Add policy that auto-approves write_file
        registry.add_auto_approve_policy("write_file")

        handler_called = False

        async def handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            nonlocal handler_called
            handler_called = True
            return False

        registry.set_confirmation_handler(handler)
        result = await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert result.success is True
        assert not handler_called  # Skipped due to policy

    async def test_policy_can_be_removed(self) -> None:
        """Auto-approve policies can be removed."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        registry.add_auto_approve_policy("write_file")
        registry.remove_auto_approve_policy("write_file")

        handler_called = False

        async def handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            nonlocal handler_called
            handler_called = True
            return True

        registry.set_confirmation_handler(handler)
        await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert handler_called  # Handler invoked after policy removed

    def test_list_auto_approve_policies(self) -> None:
        """Can list auto-approve policies."""
        registry = ToolRegistry()
        registry.add_auto_approve_policy("write_file")
        registry.add_auto_approve_policy("shell")
        policies = registry.list_auto_approve_policies()
        assert "write_file" in policies
        assert "shell" in policies
