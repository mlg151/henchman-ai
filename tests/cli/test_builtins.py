"""Tests for built-in slash commands."""

from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.builtins import (
    ClearCommand,
    HelpCommand,
    QuitCommand,
    ToolsCommand,
    get_builtin_commands,
)


class TestHelpCommand:
    """Tests for /help command."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    @pytest.fixture
    def ctx(self, console: Console) -> CommandContext:
        """Create a command context."""
        return CommandContext(console=console, args=[])

    def test_name(self) -> None:
        """Test command name."""
        cmd = HelpCommand()
        assert cmd.name == "help"

    def test_description(self) -> None:
        """Test command description."""
        cmd = HelpCommand()
        assert "help" in cmd.description.lower()

    def test_usage(self) -> None:
        """Test command usage."""
        cmd = HelpCommand()
        assert "/help" in cmd.usage

    @pytest.mark.anyio
    async def test_execute_shows_help(self, ctx: CommandContext) -> None:
        """Test that help command shows help text."""
        cmd = HelpCommand()
        await cmd.execute(ctx)
        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "help" in output.lower() or "command" in output.lower()


class TestQuitCommand:
    """Tests for /quit command."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    @pytest.fixture
    def ctx(self, console: Console) -> CommandContext:
        """Create a command context."""
        return CommandContext(console=console, args=[])

    def test_name(self) -> None:
        """Test command name."""
        cmd = QuitCommand()
        assert cmd.name == "quit"

    def test_description(self) -> None:
        """Test command description."""
        cmd = QuitCommand()
        assert "exit" in cmd.description.lower() or "quit" in cmd.description.lower()

    def test_usage(self) -> None:
        """Test command usage."""
        cmd = QuitCommand()
        assert "/quit" in cmd.usage

    @pytest.mark.anyio
    async def test_execute_raises_systemexit(self, ctx: CommandContext) -> None:
        """Test that quit command raises SystemExit."""
        cmd = QuitCommand()
        with pytest.raises(SystemExit):
            await cmd.execute(ctx)


class TestClearCommand:
    """Tests for /clear command."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    @pytest.fixture
    def ctx(self, console: Console) -> CommandContext:
        """Create a command context."""
        return CommandContext(console=console, args=[])

    def test_name(self) -> None:
        """Test command name."""
        cmd = ClearCommand()
        assert cmd.name == "clear"

    def test_description(self) -> None:
        """Test command description."""
        cmd = ClearCommand()
        assert "clear" in cmd.description.lower() or "screen" in cmd.description.lower()

    def test_usage(self) -> None:
        """Test command usage."""
        cmd = ClearCommand()
        assert "/clear" in cmd.usage

    @pytest.mark.anyio
    async def test_execute_clears_screen(self, ctx: CommandContext) -> None:
        """Test that clear command clears screen."""
        cmd = ClearCommand()
        # Just verify it doesn't raise
        await cmd.execute(ctx)


class TestToolsCommand:
    """Tests for /tools command."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    @pytest.fixture
    def ctx(self, console: Console) -> CommandContext:
        """Create a command context."""
        return CommandContext(console=console, args=[])

    def test_name(self) -> None:
        """Test command name."""
        cmd = ToolsCommand()
        assert cmd.name == "tools"

    def test_description(self) -> None:
        """Test command description."""
        cmd = ToolsCommand()
        assert "tool" in cmd.description.lower()

    def test_usage(self) -> None:
        """Test command usage."""
        cmd = ToolsCommand()
        assert "/tools" in cmd.usage

    @pytest.mark.anyio
    async def test_execute_lists_tools(self, ctx: CommandContext) -> None:
        """Test that tools command lists available tools."""
        cmd = ToolsCommand()
        await cmd.execute(ctx)
        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        # Should show some output about tools
        assert len(output) > 0


class TestGetBuiltinCommands:
    """Tests for get_builtin_commands function."""

    def test_returns_list_of_commands(self) -> None:
        """Test that get_builtin_commands returns a list of commands."""
        commands = get_builtin_commands()
        assert isinstance(commands, list)
        assert len(commands) > 0

    def test_includes_help(self) -> None:
        """Test that built-in commands include help."""
        commands = get_builtin_commands()
        names = [cmd.name for cmd in commands]
        assert "help" in names

    def test_includes_quit(self) -> None:
        """Test that built-in commands include quit."""
        commands = get_builtin_commands()
        names = [cmd.name for cmd in commands]
        assert "quit" in names

    def test_includes_clear(self) -> None:
        """Test that built-in commands include clear."""
        commands = get_builtin_commands()
        names = [cmd.name for cmd in commands]
        assert "clear" in names

    def test_includes_tools(self) -> None:
        """Test that built-in commands include tools."""
        commands = get_builtin_commands()
        names = [cmd.name for cmd in commands]
        assert "tools" in names
