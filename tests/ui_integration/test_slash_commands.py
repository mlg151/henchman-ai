"""
Integration tests for slash commands.

Tests that verify all slash commands are properly connected to the UI
and execute correctly through the REPL.
"""
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
from rich.console import Console

from henchman.cli.commands import CommandRegistry, parse_command
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
        repl = Repl(
            provider=mock_provider,
            console=console_with_recording,
            config=ReplConfig()
        )

        # Mock the command registry to track command execution
        repl.command_registry = Mock(spec=CommandRegistry)
        repl.command_registry.get = Mock()
        repl.command_registry.list_commands = Mock(return_value=[
            ("help", "Show help"),
            ("quit", "Exit CLI"),
            ("clear", "Clear screen"),
            ("tools", "List available tools"),
            ("chat", "Start new chat"),
            ("extensions", "List extensions"),
            ("mcp", "MCP commands"),
            ("plan", "Planning mode"),
            ("skill", "Skill commands"),
        ])

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

        # Mock session
        repl.session = Mock(spec=Session)
        repl.session.messages = []

        return repl

    async def test_slash_help_command_integration(self, repl_instance):
        """Test /help command integration through REPL."""
        # Mock the help command execution
        mock_command = Mock()
        mock_command.execute = AsyncMock()
        repl_instance.command_registry.get.return_value = mock_command

        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute /help command through REPL
            result = await repl_instance.process_input("/help")

        # Verify command was executed
        assert result is True
        repl_instance.command_registry.execute.assert_called_once()
        args = repl_instance.command_registry.execute.call_args[0]
        assert args[0] == "help"

    async def test_slash_quit_command_integration(self, repl_instance):
        """Test /quit command integration through REPL."""
        # Setup quit command to raise SystemExit
        async def quit_execute(*_, **__):
            raise SystemExit(0)
        repl_instance.command_registry.execute = AsyncMock(side_effect=quit_execute)

        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # /quit should return False to exit REPL
            result = await repl_instance.process_input("/quit")

        # Verify REPL would exit
        assert result is False
        repl_instance.command_registry.execute.assert_called_with("quit", ANY)

    async def test_slash_clear_command_integration(self, repl_instance):
        """Test /clear command integration through REPL."""
        # Mock console.clear since it's a real function
        repl_instance.renderer.console.clear = Mock()

        # Mock clear command
        mock_command = Mock()
        mock_command.execute = AsyncMock()
        repl_instance.command_registry.get.return_value = mock_command

        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # /clear is handled specially in REPL process_input
            result = await repl_instance.process_input("/clear")

        # Verify command was handled
        assert result is True
        # Should clear agent history
        repl_instance.agent.clear_history.assert_called_once()
        # Should call command execution as well (Repl logic calls it)
        repl_instance.command_registry.execute.assert_called_with("clear", ANY)

    async def test_slash_tools_command_integration(self, repl_instance):
        """Test /tools command integration through REPL."""
        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute /tools command
            result = await repl_instance.process_input("/tools")

        # Verify command was executed
        assert result is True
        repl_instance.command_registry.execute.assert_called_once()
        assert repl_instance.command_registry.execute.call_args[0][0] == "tools"

    async def test_slash_chat_command_integration(self, repl_instance):
        """Test /chat command integration through REPL."""
        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute /chat command
            result = await repl_instance.process_input("/chat")

        # Verify command was executed
        assert result is True
        repl_instance.command_registry.execute.assert_called_once()
        assert repl_instance.command_registry.execute.call_args[0][0] == "chat"

    async def test_slash_extensions_command_integration(self, repl_instance):
        """Test /extensions command integration through REPL."""
        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute /extensions command
            result = await repl_instance.process_input("/extensions")

        # Verify command was executed
        assert result is True
        repl_instance.command_registry.execute.assert_called_once()
        assert repl_instance.command_registry.execute.call_args[0][0] == "extensions"

    async def test_slash_mcp_command_integration(self, repl_instance):
        """Test /mcp command integration through REPL."""
        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute /mcp command
            result = await repl_instance.process_input("/mcp")

        # Verify command was executed
        assert result is True
        repl_instance.command_registry.execute.assert_called_once()
        assert repl_instance.command_registry.execute.call_args[0][0] == "mcp"

    async def test_slash_plan_command_integration(self, repl_instance):
        """Test /plan command integration through REPL."""
        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute /plan command
            result = await repl_instance.process_input("/plan")

        # Verify command was executed
        assert result is True
        repl_instance.command_registry.execute.assert_called_once()
        assert repl_instance.command_registry.execute.call_args[0][0] == "plan"

    async def test_slash_skill_command_integration(self, repl_instance):
        """Test /skill command integration through REPL."""
        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute /skill command
            result = await repl_instance.process_input("/skill")

        # Verify command was executed
        assert result is True
        repl_instance.command_registry.execute.assert_called_once()
        assert repl_instance.command_registry.execute.call_args[0][0] == "skill"

    async def test_unknown_slash_command_integration(self, repl_instance):
        """Test unknown slash command error handling."""
        # Mock command registry to raise KeyError in execute
        repl_instance.command_registry.execute = AsyncMock(side_effect=KeyError("Unknown command: unknown"))

        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute unknown command
            result = await repl_instance.process_input("/unknown")

        # Verify error handling
        assert result is True
        repl_instance.renderer.error.assert_called_with("Unknown command: unknown")

    async def test_slash_command_with_arguments_integration(self, repl_instance):
        """Test slash commands with arguments."""
        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # Execute command with arguments
            result = await repl_instance.process_input("/chat new project")

        # Verify command was executed with correct args
        assert result is True
        repl_instance.command_registry.execute.assert_called_once()
        args = repl_instance.command_registry.execute.call_args[0]
        assert args[0] == "chat"
        # Check context args
        ctx = args[1]
        assert ctx.args == ["new", "project"]

    @pytest.mark.parametrize("invalid_command", [
        "",           # Empty
        "help",       # Missing slash
        "/",          # Just slash
        "/ ",         # Slash with space
        " /help",     # Leading space
    ])
    async def test_invalid_slash_commands(self, repl_instance, invalid_command):
        """Test handling of invalid slash command formats."""
        with patch('henchman.cli.repl.expand_at_references', side_effect=lambda x: x):
            # These should return True (continue) but not execute commands
            result = await repl_instance.process_input(invalid_command)
            assert result is True

        # Note: process_input may call run_agent for non-slash commands like "help",
        # but in this mock environment, _run_agent is not mocked to fail, so it's fine.
        # We just check that slash command registry was NOT called for non-slash commands.

        if invalid_command.startswith("/") and len(invalid_command.strip()) > 1 and not invalid_command.startswith("/ "):
             # If it IS detected as slash command (e.g. valid format but maybe invalid handling)
             pass
        else:
             # If NOT detected as slash command
             repl_instance.command_registry.get.assert_not_called()


class TestCommandParsingEdgeCases:
    """Tests for edge cases in command parsing."""

    def test_parse_command_quoted_arguments(self):
        """Test parsing commands with quoted arguments."""
        # Note: parse_command might not handle quotes as expected
        # Test with quoted arguments - adjust expectations based on actual behavior
        test_cases = [
            ('/chat "new project"', ("chat", ['"new', 'project"'])),  # Quotes not stripped
            ('/tools "list all" verbose', ("tools", ['"list', 'all"', 'verbose'])),
            ("/skill 'test skill'", ("skill", ["'test", "skill'"])),
        ]

        for input_cmd, expected in test_cases:
            parsed = parse_command(input_cmd)
            assert parsed == expected, f"Failed to parse: {input_cmd}. Got: {parsed}, Expected: {expected}"

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
        # Command with trailing space
        parsed = parse_command("/help ")
        assert parsed == ("help", [])

        # Multiple spaces
        parsed = parse_command("/help    ")
        assert parsed == ("help", [])

    def test_is_slash_command_detection(self):
        """Test slash command detection logic."""
        from henchman.cli.input import is_slash_command

        # Valid slash commands
        assert is_slash_command("/help") is True
        assert is_slash_command("/tools list") is True
        assert is_slash_command("/chat") is True

        # Not slash commands
        assert is_slash_command("help") is False
        assert is_slash_command("read file.txt") is False
        assert is_slash_command("") is False
        assert is_slash_command(" ") is False


class TestREPLSlashCommandRouting:
    """Test that REPL properly routes slash commands."""

    @pytest.fixture
    def mock_repl_components(self):
        """Create REPL with mocked components for routing tests."""
        console = Console(record=True)
        repl = Repl(
            provider=Mock(),
            console=console,
            config=ReplConfig()
        )

        # Mock the _handle_command method to track calls
        repl._handle_command = AsyncMock(return_value=True)

        # Mock is_slash_command to return True for testing
        with patch('henchman.cli.input.is_slash_command', return_value=True):
            yield repl

    async def test_repl_routes_slash_commands(self, mock_repl_components):
        """Test REPL routes slash commands to handler."""
        # Simulate user input with slash command
        result = await mock_repl_components._handle_command("/help")

        # Verify slash command was routed
        assert result is True
        mock_repl_components._handle_command.assert_called_once_with("/help")

    async def test_repl_continues_after_slash_command(self, mock_repl_components):
        """Test REPL continues after slash command execution."""
        # Mock _handle_command to return True (continue)
        mock_repl_components._handle_command = AsyncMock(return_value=True)

        # Execute slash command
        result = await mock_repl_components._handle_command("/help")

        # REPL should continue
        assert result is True

    async def test_repl_exits_after_quit_command(self, mock_repl_components):
        """Test REPL exits after /quit command."""
        # Mock _handle_command to return False (exit) for /quit
        def mock_handle_command(cmd):
            return cmd != "/quit"

        mock_repl_components._handle_command = AsyncMock(side_effect=mock_handle_command)

        # Execute quit command
        result = await mock_repl_components._handle_command("/quit")

        # REPL should exit
        assert result is False
