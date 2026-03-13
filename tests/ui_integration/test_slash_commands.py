"""
Integration tests for slash commands.

Tests that verify all slash commands are properly connected to the UI
and execute correctly through the REPL.
"""

from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console

from henchman.cli.commands import parse_command
from henchman.cli.repl import Repl, ReplConfig
from henchman.core.agent import Agent
from henchman.core.session import Session


class TestSlashCommandIntegration:
    """Integration tests for slash command execution through REPL."""

    @pytest.fixture
    def mock_provider(self):
        """Mock provider for testing."""
        provider = Mock()
        provider.chat_completion = AsyncMock()
        return provider

    @pytest.fixture
    def console_with_recording(self):
        """Console that records output for verification."""
        return Console(record=True, width=80)

    @pytest.fixture
    def repl_instance(self, mock_provider, console_with_recording):
        """REPL instance with mock components."""
        repl = Repl(provider=mock_provider, console=console_with_recording, config=ReplConfig())

        # Create mock command that can be awaited
        mock_command = Mock()
        mock_command.execute = AsyncMock()

        # Mock command_registry.get to return our mock command
        repl.command_processor.command_registry.get = Mock(return_value=mock_command)
        repl.command_processor.command_registry.list_names = Mock(
            return_value=[
                "help",
                "quit",
                "clear",
                "tools",
                ("chat", "Start new chat"),
                ("extensions", "List extensions"),
                ("mcp", "MCP commands"),
                ("plan", "Planning mode"),
                ("skill", "Skill commands"),
            ]
        )

        # Store the mock command for verification
        repl._test_mock_command = mock_command

        # Mock agent
        repl.agent = Mock(spec=Agent)
        repl.agent.clear_history = Mock()

        # Mock renderer
        repl.renderer = Mock()
        repl.renderer.console = console_with_recording
        repl.renderer.success = Mock()
        repl.renderer.error = Mock()
        repl.renderer.muted = Mock()
        repl.renderer.info = Mock()

        # Also update the command_processor's output_handler to use the mocked renderer
        repl.command_processor.output_handler.renderer = repl.renderer

        # Mock session
        repl.session = Mock(spec=Session)
        repl.session.messages = []

        return repl

    @pytest.mark.asyncio
    async def test_slash_help_command_integration(self, repl_instance):
        """Test /help command integration through REPL."""
        # Execute /help command through REPL
        result = await repl_instance.process_input("/help")

        # Verify command was executed
        assert result is True
        repl_instance.command_processor.command_registry.get.assert_called_once_with("help")
        repl_instance._test_mock_command.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_slash_quit_command_integration(self, repl_instance):
        """Test /quit command integration through REPL."""
        # /quit is handled specially - it returns False directly without calling registry
        result = await repl_instance.process_input("/quit")

        # Verify REPL would exit
        assert result is False

    @pytest.mark.asyncio
    async def test_slash_clear_command_integration(self, repl_instance):
        """Test /clear command integration through REPL."""
        # /clear is handled specially by command_processor: clears agent history
        result = await repl_instance.process_input("/clear")

        # Verify command was handled
        assert result is True
        # Should clear agent history
        repl_instance.agent.clear_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_slash_tools_command_integration(self, repl_instance):
        """Test /tools command integration through REPL."""
        # Execute /tools command
        result = await repl_instance.process_input("/tools")

        # Verify command was executed
        assert result is True
        repl_instance.command_processor.command_registry.get.assert_called_with("tools")
        repl_instance._test_mock_command.execute.assert_called()

    @pytest.mark.asyncio
    async def test_slash_chat_command_integration(self, repl_instance):
        """Test /chat command integration through REPL."""
        # Execute /chat command
        result = await repl_instance.process_input("/chat")

        # Verify command was executed
        assert result is True
        repl_instance.command_processor.command_registry.get.assert_called_with("chat")

    @pytest.mark.asyncio
    async def test_slash_extensions_command_integration(self, repl_instance):
        """Test /extensions command integration through REPL."""
        # Execute /extensions command
        result = await repl_instance.process_input("/extensions")

        # Verify command was executed
        assert result is True
        repl_instance.command_processor.command_registry.get.assert_called_with("extensions")

    @pytest.mark.asyncio
    async def test_slash_mcp_command_integration(self, repl_instance):
        """Test /mcp command integration through REPL."""
        # Execute /mcp command
        result = await repl_instance.process_input("/mcp")

        # Verify command was executed
        assert result is True
        repl_instance.command_processor.command_registry.get.assert_called_with("mcp")

    @pytest.mark.asyncio
    async def test_slash_plan_command_integration(self, repl_instance):
        """Test /plan command integration through REPL."""
        # Execute /plan command
        result = await repl_instance.process_input("/plan")

        # Verify command was executed
        assert result is True
        repl_instance.command_processor.command_registry.get.assert_called_with("plan")

    @pytest.mark.asyncio
    async def test_slash_skill_command_integration(self, repl_instance):
        """Test /skill command integration through REPL."""
        # Execute /skill command
        result = await repl_instance.process_input("/skill")

        # Verify command was executed
        assert result is True
        repl_instance.command_processor.command_registry.get.assert_called_with("skill")

    @pytest.mark.asyncio
    async def test_unknown_slash_command_integration(self, repl_instance):
        """Test unknown slash command error handling."""
        # Mock command registry to return None for unknown commands
        repl_instance.command_processor.command_registry.get.return_value = None

        # Execute unknown command
        result = await repl_instance.process_input("/unknown")

        # Verify error handling
        assert result is True
        repl_instance.renderer.error.assert_called()

    @pytest.mark.asyncio
    async def test_slash_command_with_arguments_integration(self, repl_instance):
        """Test slash commands with arguments."""
        # Execute command with arguments
        result = await repl_instance.process_input("/chat new project")

        # Verify command was executed
        assert result is True
        repl_instance.command_processor.command_registry.get.assert_called_with("chat")
        # Check that execute was called with a context containing args
        call_args = repl_instance._test_mock_command.execute.call_args
        assert call_args is not None
        ctx = call_args[0][0]
        assert ctx.args == ["new", "project"]

    @pytest.mark.parametrize(
        "invalid_command",
        [
            "",  # Empty
            "help",  # Missing slash
            "/",  # Just slash - treated as slash command, parses to None
            " /help",  # Leading space - not detected as slash command
        ],
    )
    @pytest.mark.asyncio
    async def test_invalid_slash_commands(self, repl_instance, invalid_command):
        """Test handling of invalid slash command formats."""
        # Mock _run_agent to do nothing for non-slash inputs
        repl_instance._run_agent = AsyncMock()

        # These should return True (continue) but not execute slash commands
        result = await repl_instance.process_input(invalid_command)
        assert result is True


class TestCommandParsingEdgeCases:
    """Tests for edge cases in command parsing."""

    def test_parse_command_quoted_arguments(self):
        """Test parsing commands with quoted arguments."""
        test_cases = [
            ('/chat "new project"', ("chat", ['"new', 'project"'])),
            ('/tools "list all" verbose', ("tools", ['"list', 'all"', "verbose"])),
            ("/skill 'test skill'", ("skill", ["'test", "skill'"])),
        ]

        for input_cmd, expected in test_cases:
            parsed = parse_command(input_cmd)
            assert parsed == expected, (
                f"Failed to parse: {input_cmd}. Got: {parsed}, Expected: {expected}"
            )

    def test_parse_command_special_characters(self):
        """Test parsing commands with special characters."""
        test_cases = [
            ("/chat test-project", ("chat", ["test-project"])),
            ("/tools list --verbose", ("tools", ["list", "--verbose"])),
            ("/mcp server:8080", ("mcp", ["server:8080"])),
        ]

        for input_cmd, expected in test_cases:
            parsed = parse_command(input_cmd)
            assert parsed == expected, f"Failed to parse: {input_cmd}"

    def test_parse_command_empty_arguments(self):
        """Test parsing commands with empty arguments."""
        parsed = parse_command("/help ")
        assert parsed == ("help", [])

        parsed = parse_command("/help    ")
        assert parsed == ("help", [])

    def test_is_slash_command_detection(self):
        """Test slash command detection logic."""
        from henchman.cli.input import is_slash_command

        assert is_slash_command("/help") is True
        assert is_slash_command("/tools list") is True
        assert is_slash_command("/chat") is True

        assert is_slash_command("help") is False
        assert is_slash_command("read file.txt") is False
        assert is_slash_command("") is False
        assert is_slash_command(" ") is False


class TestREPLSlashCommandRouting:
    """Test that REPL properly routes slash commands."""

    @pytest.fixture
    def repl_with_mock_handler(self):
        """Create REPL with mocked command processor for routing tests."""
        console = Console(record=True)
        repl = Repl(provider=Mock(), console=console, config=ReplConfig())
        return repl

    @pytest.mark.asyncio
    async def test_repl_routes_slash_commands(self, repl_with_mock_handler):
        """Test REPL routes slash commands to handler."""
        repl = repl_with_mock_handler
        repl.command_processor.handle_command = AsyncMock(return_value=True)

        result = await repl.process_input("/help")

        assert result is True
        repl.command_processor.handle_command.assert_called_once_with("/help", repl.agent, repl)

    @pytest.mark.asyncio
    async def test_repl_continues_after_slash_command(self, repl_with_mock_handler):
        """Test REPL continues after slash command execution."""
        repl = repl_with_mock_handler
        repl.command_processor.handle_command = AsyncMock(return_value=True)

        result = await repl.process_input("/help")

        assert result is True

    @pytest.mark.asyncio
    async def test_repl_exits_after_quit_command(self, repl_with_mock_handler):
        """Test REPL exits after /quit command."""
        repl = repl_with_mock_handler
        repl.command_processor.handle_command = AsyncMock(return_value=False)

        result = await repl.process_input("/quit")

        assert result is False
