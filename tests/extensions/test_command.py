"""Tests for /extensions command."""

from io import StringIO

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.extensions import ExtensionsCommand
from henchman.extensions.base import Extension
from henchman.extensions.manager import ExtensionManager


class TestExtension(Extension):
    """Test extension."""

    @property
    def name(self) -> str:
        return "test_ext"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "A test extension"


class TestExtensionsCommand:
    """Tests for ExtensionsCommand."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a console for testing."""
        return Console(file=StringIO(), force_terminal=True)

    @pytest.fixture
    def manager(self) -> ExtensionManager:
        """Create an extension manager."""
        return ExtensionManager()

    def test_command_name(self) -> None:
        """Test command name."""
        cmd = ExtensionsCommand(ExtensionManager())
        assert cmd.name == "extensions"

    def test_command_description(self) -> None:
        """Test command description."""
        cmd = ExtensionsCommand(ExtensionManager())
        assert "extension" in cmd.description.lower()

    def test_command_usage(self) -> None:
        """Test command usage."""
        cmd = ExtensionsCommand(ExtensionManager())
        assert "/extensions" in cmd.usage

    @pytest.mark.anyio
    async def test_list_no_extensions(self, console: Console, manager: ExtensionManager) -> None:
        """Test listing with no extensions."""
        cmd = ExtensionsCommand(manager)
        ctx = CommandContext(console=console)
        await cmd.execute(ctx)
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "No extensions" in output or "0" in output

    @pytest.mark.anyio
    async def test_list_with_extensions(self, console: Console, manager: ExtensionManager) -> None:
        """Test listing with extensions."""
        manager.register(TestExtension())
        cmd = ExtensionsCommand(manager)
        ctx = CommandContext(console=console)
        await cmd.execute(ctx)
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "test_ext" in output
        # Check version parts separately due to ANSI codes
        assert "v1." in output
        assert "0.0" in output
