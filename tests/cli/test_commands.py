"""Tests for slash command parsing and handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from henchman.cli.commands import (
    Command,
    CommandContext,
    CommandRegistry,
    parse_command,
)


class TestParseCommand:
    """Tests for parse_command function."""

    def test_simple_command(self) -> None:
        """Test parsing a simple command."""
        name, args = parse_command("/help")
        assert name == "help"
        assert args == []

    def test_command_with_args(self) -> None:
        """Test parsing a command with arguments."""
        name, args = parse_command("/model gpt-4")
        assert name == "model"
        assert args == ["gpt-4"]

    def test_command_with_multiple_args(self) -> None:
        """Test parsing a command with multiple arguments."""
        name, args = parse_command("/chat save my-session")
        assert name == "chat"
        assert args == ["save", "my-session"]

    def test_command_without_slash(self) -> None:
        """Test parsing input without slash returns None."""
        result = parse_command("hello world")
        assert result is None

    def test_empty_command(self) -> None:
        """Test parsing just a slash."""
        result = parse_command("/")
        assert result is None

    def test_command_with_extra_whitespace(self) -> None:
        """Test parsing command with extra whitespace."""
        name, args = parse_command("/model   gpt-4   turbo")
        assert name == "model"
        assert args == ["gpt-4", "turbo"]


class TestCommand:
    """Tests for Command base class."""

    def test_command_abstract_methods(self) -> None:
        """Test that Command requires implementation of abstract methods."""
        # Command is abstract, so we can't instantiate it directly
        with pytest.raises(TypeError):
            Command()  # type: ignore[abstract]


class TestCommandContext:
    """Tests for CommandContext dataclass."""

    def test_context_creation(self) -> None:
        """Test creating a command context."""
        console = MagicMock()
        ctx = CommandContext(
            console=console,
            args=["arg1", "arg2"],
        )
        assert ctx.console is console
        assert ctx.args == ["arg1", "arg2"]

    def test_context_with_all_fields(self) -> None:
        """Test command context with all fields."""
        console = MagicMock()
        settings = MagicMock()
        agent = MagicMock()
        ctx = CommandContext(
            console=console,
            args=["arg1"],
            settings=settings,
            agent=agent,
        )
        assert ctx.settings is settings
        assert ctx.agent is agent


class TestCommandRegistry:
    """Tests for CommandRegistry class."""

    def test_register_command(self) -> None:
        """Test registering a command."""
        registry = CommandRegistry()

        class TestCommand(Command):
            @property
            def name(self) -> str:
                return "test"

            @property
            def description(self) -> str:
                return "A test command"

            @property
            def usage(self) -> str:
                return "/test [arg]"

            async def execute(self, ctx: CommandContext) -> None:
                pass

        cmd = TestCommand()
        registry.register(cmd)
        assert "test" in registry.list_commands()

    def test_get_command(self) -> None:
        """Test getting a registered command."""
        registry = CommandRegistry()

        class TestCommand(Command):
            @property
            def name(self) -> str:
                return "mytest"

            @property
            def description(self) -> str:
                return "My test"

            @property
            def usage(self) -> str:
                return "/mytest"

            async def execute(self, ctx: CommandContext) -> None:
                pass

        cmd = TestCommand()
        registry.register(cmd)
        retrieved = registry.get("mytest")
        assert retrieved is cmd

    def test_get_unknown_command(self) -> None:
        """Test getting an unknown command returns None."""
        registry = CommandRegistry()
        assert registry.get("unknown") is None

    def test_list_commands(self) -> None:
        """Test listing registered commands."""
        registry = CommandRegistry()

        class Cmd1(Command):
            @property
            def name(self) -> str:
                return "cmd1"

            @property
            def description(self) -> str:
                return "Command 1"

            @property
            def usage(self) -> str:
                return "/cmd1"

            async def execute(self, ctx: CommandContext) -> None:
                pass

        class Cmd2(Command):
            @property
            def name(self) -> str:
                return "cmd2"

            @property
            def description(self) -> str:
                return "Command 2"

            @property
            def usage(self) -> str:
                return "/cmd2"

            async def execute(self, ctx: CommandContext) -> None:
                pass

        registry.register(Cmd1())
        registry.register(Cmd2())
        commands = registry.list_commands()
        assert "cmd1" in commands
        assert "cmd2" in commands

    @pytest.mark.anyio
    async def test_execute_command(self) -> None:
        """Test executing a command."""
        registry = CommandRegistry()
        executed = []

        class TestCommand(Command):
            @property
            def name(self) -> str:
                return "exec"

            @property
            def description(self) -> str:
                return "Execute test"

            @property
            def usage(self) -> str:
                return "/exec"

            async def execute(self, ctx: CommandContext) -> None:
                executed.append(ctx.args)

        registry.register(TestCommand())
        ctx = CommandContext(console=MagicMock(), args=["arg1"])
        await registry.execute("exec", ctx)
        assert executed == [["arg1"]]

    @pytest.mark.anyio
    async def test_execute_unknown_command_raises(self) -> None:
        """Test executing unknown command raises error."""
        registry = CommandRegistry()
        ctx = CommandContext(console=MagicMock(), args=[])
        with pytest.raises(KeyError):
            await registry.execute("unknown", ctx)
