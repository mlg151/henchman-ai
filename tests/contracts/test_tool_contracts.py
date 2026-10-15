"""Contract tests for tools."""

from __future__ import annotations

import pytest

from henchman.tools.base import Tool, ToolKind, ToolResult


def test_tool_is_abstract() -> None:
    """Tool should be an abstract base class."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class Tool"):
        Tool()


def test_tool_contract_methods() -> None:
    """Concrete tools must provide required methods and properties."""

    class IncompleteTool(Tool):
        pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompleteTool"):
        IncompleteTool()

    class ValidTool(Tool):
        @property
        def name(self) -> str:
            return "valid_tool"

        @property
        def description(self) -> str:
            return "A valid tool"

        async def execute(self, **params) -> ToolResult:
            return ToolResult(content="ok")

    # Should instantiate without error
    tool = ValidTool()
    assert tool.name == "valid_tool"
    assert tool.description == "A valid tool"
    assert tool.kind == ToolKind.READ  # Default behavior
    assert tool.parameters == {}  # Default behavior
    assert tool.needs_confirmation({}) is None
    assert tool.to_declaration().name == "valid_tool"
    assert tool.to_declaration().description == "A valid tool"


def test_tool_confirmation_contract() -> None:
    """Tools should correctly identify when they need user confirmation based on their kind."""

    class WriteTool(Tool):
        @property
        def name(self) -> str:
            return "write_tool"

        @property
        def description(self) -> str:
            return "A write tool"

        @property
        def kind(self) -> ToolKind:
            return ToolKind.WRITE

        async def execute(self, **params) -> ToolResult:
            return ToolResult(content="ok")

    tool = WriteTool()
    confirmation = tool.needs_confirmation({"file": "test.txt"})
    assert confirmation is not None
    assert confirmation.tool_name == "write_tool"
    assert confirmation.risk_level == "medium"
