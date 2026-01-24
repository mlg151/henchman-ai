"""Tests for Extension base class."""

import pytest

from henchman.cli.commands import Command, CommandContext
from henchman.extensions.base import Extension
from henchman.tools.base import Tool, ToolKind, ToolResult


class DummyTool(Tool):
    """A dummy tool for testing."""

    @property
    def name(self) -> str:
        return "dummy_tool"

    @property
    def description(self) -> str:
        return "A dummy tool"

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="dummy result")


class DummyCommand(Command):
    """A dummy command for testing."""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def description(self) -> str:
        return "A dummy command"

    @property
    def usage(self) -> str:
        return "/dummy"

    async def execute(self, ctx: CommandContext) -> None:
        ctx.console.print("Dummy executed")


class TestExtension(Extension):
    """A test extension implementation."""

    @property
    def name(self) -> str:
        return "test_extension"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "A test extension"

    def get_tools(self) -> list[Tool]:
        return [DummyTool()]

    def get_commands(self) -> list[Command]:
        return [DummyCommand()]

    def get_context(self) -> str:
        return "Test extension context"


class MinimalExtension(Extension):
    """A minimal extension with only required methods."""

    @property
    def name(self) -> str:
        return "minimal"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Minimal extension"


class TestExtensionBase:
    """Tests for Extension ABC."""

    def test_extension_name(self) -> None:
        """Test extension name property."""
        ext = TestExtension()
        assert ext.name == "test_extension"

    def test_extension_version(self) -> None:
        """Test extension version property."""
        ext = TestExtension()
        assert ext.version == "1.0.0"

    def test_extension_description(self) -> None:
        """Test extension description property."""
        ext = TestExtension()
        assert ext.description == "A test extension"

    def test_get_tools(self) -> None:
        """Test get_tools returns tool list."""
        ext = TestExtension()
        tools = ext.get_tools()
        assert len(tools) == 1
        assert tools[0].name == "dummy_tool"

    def test_get_commands(self) -> None:
        """Test get_commands returns command list."""
        ext = TestExtension()
        commands = ext.get_commands()
        assert len(commands) == 1
        assert commands[0].name == "dummy"

    def test_get_context(self) -> None:
        """Test get_context returns context string."""
        ext = TestExtension()
        assert ext.get_context() == "Test extension context"

    def test_minimal_extension_defaults(self) -> None:
        """Test minimal extension has sensible defaults."""
        ext = MinimalExtension()
        assert ext.name == "minimal"
        assert ext.version == "0.1.0"
        assert ext.get_tools() == []
        assert ext.get_commands() == []
        assert ext.get_context() == ""

    def test_extension_is_abstract(self) -> None:
        """Test Extension cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Extension()  # type: ignore[abstract]
