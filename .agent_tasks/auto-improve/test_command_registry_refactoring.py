"""Tests for CommandRegistry refactoring to eliminate duplicate code smells."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from henchman.cli.commands import (
    Command,
    CommandContext,
    CommandRegistry,
    parse_command,
)


class TestCommandRegistryRefactoring:
    """Tests for refactored CommandRegistry to eliminate duplicate code."""

    def test_registry_inherits_from_base_registry(self) -> None:
        """Test that CommandRegistry properly inherits from Registry base class."""
        registry = CommandRegistry()
        
        # Test that it has the base registry methods
        assert hasattr(registry, 'register')
        assert hasattr(registry, 'get')
        assert hasattr(registry, 'list_items')
        assert hasattr(registry, 'list_names')
        
        # Test that it has CommandRegistry specific methods
        assert hasattr(registry, 'get_commands')
        assert hasattr(registry, 'execute')

    def test_register_with_duplicate_checking(self) -> None:
        """Test that register method still prevents duplicate commands."""
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

        cmd1 = TestCommand()
        cmd2 = TestCommand()  # Same name
        
        registry.register(cmd1)
        with pytest.raises(ValueError, match="Command 'test' is already registered"):
            registry.register(cmd2)

    def test_get_commands_returns_sorted_list(self) -> None:
        """Test that get_commands returns commands sorted by name."""
        registry = CommandRegistry()

        class CommandZ(Command):
            @property
            def name(self) -> str:
                return "zcommand"

            @property
            def description(self) -> str:
                return "Z command"

            @property
            def usage(self) -> str:
                return "/zcommand"

            async def execute(self, ctx: CommandContext) -> None:
                pass

        class CommandA(Command):
            @property
            def name(self) -> str:
                return "acommand"

            @property
            def description(self) -> str:
                return "A command"

            @property
            def usage(self) -> str:
                return "/acommand"

            async def execute(self, ctx: CommandContext) -> None:
                pass

        class CommandM(Command):
            @property
            def name(self) -> str:
                return "mcommand"

            @property
            def description(self) -> str:
                return "M command"

            @property
            def usage(self) -> str:
                return "/mcommand"

            async def execute(self, ctx: CommandContext) -> None:
                pass

        # Register in non-alphabetical order
        registry.register(CommandZ())
        registry.register(CommandA())
        registry.register(CommandM())

        commands = registry.get_commands()
        assert len(commands) == 3
        # Should be sorted alphabetically by name
        assert commands[0].name == "acommand"
        assert commands[1].name == "mcommand"
        assert commands[2].name == "zcommand"

    def test_get_commands_empty_registry(self) -> None:
        """Test that get_commands returns empty list for empty registry."""
        registry = CommandRegistry()
        commands = registry.get_commands()
        assert commands == []

    @pytest.mark.anyio
    async def test_execute_command_still_works(self) -> None:
        """Test that execute method still works after refactoring."""
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
        ctx = CommandContext(console=MagicMock(), args=["arg1", "arg2"])
        await registry.execute("exec", ctx)
        assert executed == [["arg1", "arg2"]]

    @pytest.mark.anyio
    async def test_execute_unknown_command_still_raises(self) -> None:
        """Test that executing unknown command still raises KeyError."""
        registry = CommandRegistry()
        ctx = CommandContext(console=MagicMock(), args=[])
        with pytest.raises(KeyError, match="Unknown command: unknown"):
            await registry.execute("unknown", ctx)

    def test_registry_maintains_backward_compatibility(self) -> None:
        """Test that all public methods from original CommandRegistry still exist."""
        registry = CommandRegistry()
        
        # Original public methods
        original_methods = ['register', 'get', 'get_commands', 'execute', 
                           'list_items', 'list_names']
        
        for method_name in original_methods:
            assert hasattr(registry, method_name), f"Missing method: {method_name}"


class TestParseCommandEdgeCases:
    """Additional edge case tests for parse_command function."""
    
    def test_parse_command_with_quotes(self) -> None:
        """Test parsing command with quoted arguments."""
        # Note: current implementation doesn't handle quotes specially
        name, args = parse_command('/model "gpt-4 turbo"')
        assert name == 'model'
        assert args == ['"gpt-4', 'turbo"']  # Current behavior splits on spaces
        
    def test_parse_command_with_special_chars(self) -> None:
        """Test parsing command with special characters."""
        name, args = parse_command('/chat save my-session_v1.2')
        assert name == 'chat'
        assert args == ['save', 'my-session_v1.2']
        
    def test_parse_command_empty_after_slash(self) -> None:
        """Test parsing command with only slash and whitespace."""
        result = parse_command('/   ')
        assert result is None
        
    def test_parse_command_multiple_spaces_between_args(self) -> None:
        """Test parsing command with multiple spaces between arguments."""
        name, args = parse_command('/model  gpt-4    turbo')
        assert name == 'model'
        assert args == ['gpt-4', 'turbo']


class TestCommandContextEdgeCases:
    """Additional edge case tests for CommandContext."""
    
    def test_context_with_none_values(self) -> None:
        """Test CommandContext with None values for optional fields."""
        console = MagicMock()
        ctx = CommandContext(
            console=console,
            args=[],
            settings=None,
            agent=None,
            tool_registry=None,
            session=None,
            repl=None,
            session_manager=None,
            project_hash=None,
            mcp_manager=None,
            registry=None
        )
        assert ctx.console is console
        assert ctx.args == []
        assert ctx.settings is None
        assert ctx.agent is None
        
    def test_context_default_values(self) -> None:
        """Test CommandContext with only required fields."""
        console = MagicMock()
        ctx = CommandContext(console=console)
        assert ctx.console is console
        assert ctx.args == []  # Should use default_factory
        assert ctx.settings is None
        assert ctx.agent is None