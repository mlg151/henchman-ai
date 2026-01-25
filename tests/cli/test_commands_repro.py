
import pytest

from henchman.cli.commands import Command, CommandContext, CommandRegistry


class TestCommandRegistryAttribute:
    def test_get_commands_method(self) -> None:
        """Test usage of get_commands() method."""
        registry = CommandRegistry()

        # Register a dummy command
        class DummyCommand(Command):
            @property
            def name(self) -> str: return "dummy"
            @property
            def description(self) -> str: return "dummy desc"
            @property
            def usage(self) -> str: return "/dummy"
            async def execute(self, ctx: CommandContext) -> None: pass

        registry.register(DummyCommand())

        # Verify get_commands works
        commands = registry.get_commands()
        assert len(commands) == 1
        assert commands[0].name == "dummy"

    def test_commands_attribute_still_missing(self) -> None:
        """Ensure .commands attribute is NOT exposed (we want to use the method)."""
        registry = CommandRegistry()
        with pytest.raises(AttributeError):
            _ = registry.commands
