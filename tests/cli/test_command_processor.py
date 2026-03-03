"""Tests for the CommandProcessor component."""

from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.command_processor import CommandProcessor
from henchman.cli.commands import Command, CommandContext, CommandRegistry
from henchman.cli.output_handler import OutputHandler
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_manager import ToolManager
from henchman.core.agent import Agent
from henchman.mcp.manager import McpManager
from henchman.providers.base import ModelProvider


class MockCommand(Command):
    """Mock command for testing."""

    def __init__(self, name: str = "test", execute_result: bool = True):
        self._name = name
        self._description = "Test command"
        self._usage = f"/{name} [args]"
        self.execute_result = execute_result
        self.executed = False
        self.last_ctx = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def usage(self) -> str:
        return self._usage

    async def execute(self, ctx: CommandContext) -> None:
        self.executed = True
        self.last_ctx = ctx
        if not self.execute_result:
            raise Exception("Command failed")


class TestCommandProcessor:
    """Tests for CommandProcessor class."""

    def _create_mocks(self) -> tuple:
        """Create properly configured mocks for testing."""
        output_handler = MagicMock()
        output_handler.renderer = MagicMock()
        output_handler.renderer.console = MagicMock()

        tool_manager = MagicMock(spec=ToolManager)
        tool_manager.registry = MagicMock()

        session_manager = MagicMock(spec=ReplSessionManager)
        session_manager.current = MagicMock()
        session_manager.compute_project_hash.return_value = "test_hash"

        provider = MagicMock(spec=ModelProvider)

        return output_handler, tool_manager, session_manager, provider

    def test_initialization(self) -> None:
        """Test CommandProcessor initialization."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        assert processor.output_handler == output_handler
        assert processor.tool_manager == tool_manager
        assert processor.session_manager == session_manager
        assert processor.provider == provider
        assert processor.mcp_manager is None
        assert isinstance(processor.command_registry, CommandRegistry)

    def test_initialization_with_mcp_manager(self) -> None:
        """Test CommandProcessor initialization with MCP manager."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()
        mcp_manager = MagicMock(spec=McpManager)

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            mcp_manager=mcp_manager,
        )

        assert processor.mcp_manager == mcp_manager

    @pytest.mark.asyncio
    async def test_handle_command_quit(self) -> None:
        """Test handle_command with /quit command."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        # /quit should return False to exit
        result = await processor.handle_command("/quit", agent, repl)
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_command_clear(self) -> None:
        """Test handle_command with /clear command."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        result = await processor.handle_command("/clear", agent, repl)

        assert result is True
        agent.clear_history.assert_called_once()
        output_handler.success.assert_called_once_with("History cleared")

    @pytest.mark.asyncio
    async def test_handle_command_unknown(self) -> None:
        """Test handle_command with unknown command."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        result = await processor.handle_command("/unknown", agent, repl)

        assert result is True
        output_handler.error.assert_called_once_with("Unknown command: /unknown")
        output_handler.muted.assert_called_once_with("Type /help for available commands")

    @pytest.mark.asyncio
    async def test_handle_command_registered(self) -> None:
        """Test handle_command with registered command."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        # Add a mock command to the registry
        mock_command = MockCommand("test")
        processor.command_registry.register(mock_command)

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        result = await processor.handle_command("/test arg1 arg2", agent, repl)

        assert result is True
        assert mock_command.executed is True
        assert mock_command.last_ctx is not None
        assert mock_command.last_ctx.agent == agent
        assert mock_command.last_ctx.repl == repl
        assert mock_command.last_ctx.args == ["arg1", "arg2"]

    @pytest.mark.asyncio
    async def test_handle_command_with_args(self) -> None:
        """Test handle_command with command arguments."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        # Add a mock command to the registry
        mock_command = MockCommand("test")
        processor.command_registry.register(mock_command)

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        result = await processor.handle_command("/test with multiple args", agent, repl)

        assert result is True
        assert mock_command.executed is True
        assert mock_command.last_ctx.args == ["with", "multiple", "args"]

    @pytest.mark.asyncio
    async def test_handle_command_empty_args(self) -> None:
        """Test handle_command with empty arguments."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        # Add a mock command to the registry
        mock_command = MockCommand("test")
        processor.command_registry.register(mock_command)

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        result = await processor.handle_command("/test", agent, repl)

        assert result is True
        assert mock_command.executed is True
        assert mock_command.last_ctx.args == []

    @pytest.mark.asyncio
    async def test_handle_command_invalid_parse(self) -> None:
        """Test handle_command with invalid command parsing."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        # Mock parse_command to return None (invalid command)
        with patch("henchman.cli.command_processor.parse_command", return_value=None):
            result = await processor.handle_command("/", agent, repl)

            assert result is True
            # Should not call error since parse_command returned None

    @pytest.mark.asyncio
    async def test_handle_command_exception(self) -> None:
        """Test handle_command when command execution raises exception."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        # Add a mock command that raises exception
        mock_command = MockCommand("test", execute_result=False)
        processor.command_registry.register(mock_command)

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        # Exception should be caught and handled, not propagated
        result = await processor.handle_command("/test", agent, repl)
        assert result is True
        assert mock_command.executed is True
        # Verify error was logged
        output_handler.error.assert_called_once()
        call_args = output_handler.error.call_args[0][0]
        assert "Error executing command /test" in call_args
        assert "Command failed" in call_args

    def test_get_command_registry(self) -> None:
        """Test get_command_registry method."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        registry = processor.get_command_registry()

        assert registry is processor.command_registry
        assert isinstance(registry, CommandRegistry)

    @pytest.mark.asyncio
    async def test_handle_command_context_attributes(self) -> None:
        """Test that CommandContext has all required attributes."""
        output_handler, tool_manager, session_manager, provider = self._create_mocks()

        processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        # Add a mock command to inspect context
        captured_ctx = []

        class InspectCommand(Command):
            def __init__(self):
                self._name = "inspect"
                self._description = "Inspect context"
                self._usage = "/inspect"

            @property
            def name(self) -> str:
                return self._name

            @property
            def description(self) -> str:
                return self._description

            @property
            def usage(self) -> str:
                return self._usage

            async def execute(self, ctx: CommandContext) -> None:
                captured_ctx.append(ctx)

        inspect_cmd = InspectCommand()
        processor.command_registry.register(inspect_cmd)

        agent = MagicMock(spec=Agent)
        repl = MagicMock()

        await processor.handle_command("/inspect", agent, repl)

        assert len(captured_ctx) == 1
        ctx = captured_ctx[0]

        # Check required attributes
        assert ctx.console == output_handler.renderer.console
        assert ctx.agent == agent
        assert ctx.tool_registry == tool_manager.registry
        assert ctx.session == session_manager.current
        assert ctx.repl == repl
        assert ctx.args == []

        # Check optional attributes added by CommandProcessor
        assert ctx.session_manager == session_manager
        assert ctx.project_hash == "test_hash"
        assert ctx.mcp_manager is None  # Not provided in this test
