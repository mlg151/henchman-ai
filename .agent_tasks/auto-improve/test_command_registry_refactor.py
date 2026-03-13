"""Test CommandRegistry refactoring."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from henchman.cli.commands import Command, CommandContext, CommandRegistry


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


class AnotherCommand(Command):
    @property
    def name(self) -> str:
        return "another"

    @property
    def description(self) -> str:
        return "Another test command"

    @property
    def usage(self) -> str:
        return "/another"

    async def execute(self, ctx: CommandContext) -> None:
        pass


def test_current_behavior() -> None:
    """Test current behavior of CommandRegistry."""
    registry = CommandRegistry()
    
    # Test register and get
    cmd1 = TestCommand()
    registry.register(cmd1)
    assert registry.get("test") is cmd1
    
    # Test get_commands returns Command objects
    cmd2 = AnotherCommand()
    registry.register(cmd2)
    commands = registry.get_commands()
    assert len(commands) == 2
    assert cmd1 in commands
    assert cmd2 in commands
    
    # Test list_commands returns strings
    names = registry.list_commands()
    assert len(names) == 2
    assert "test" in names
    assert "another" in names
    
    # Test list_names (inherited from Registry)
    list_names_result = registry.list_names()
    assert list_names_result == names
    
    # Test list_items (inherited from Registry)
    list_items_result = registry.list_items()
    assert list_items_result == commands


if __name__ == "__main__":
    test_current_behavior()
    print("All tests passed!")