"""Tests for the REPL main loop."""

from io import StringIO
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from rich.console import Console

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message, ModelProvider


class MockProvider(ModelProvider):
    """Mock provider for testing."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = responses or ["Hello!"]
        self._call_count = 0

    @property
    def name(self) -> str:
        return "mock"

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[Any] | None = None, **kwargs: Any
    ) -> Any:
        from henchman.providers.base import FinishReason, StreamChunk

        response = self.responses[min(self._call_count, len(self.responses) - 1)]
        self._call_count += 1
        yield StreamChunk(content=response, finish_reason=FinishReason.STOP)


class TestReplConfig:
    """Tests for ReplConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ReplConfig()
        assert config.prompt == "❯ "
        assert config.system_prompt == ""
        assert config.auto_save is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = ReplConfig(prompt="> ", system_prompt="You are helpful", auto_save=False)
        assert config.prompt == "> "
        assert config.system_prompt == "You are helpful"
        assert config.auto_save is False


class TestRepl:
    """Tests for Repl class."""

    @pytest.fixture(autouse=True)
    def mock_create_session(self):
        with patch("henchman.cli.repl.create_session") as mock:
            mock.return_value = AsyncMock()
            mock.return_value.prompt_async.return_value = "mock input"
            yield mock

    @pytest.fixture
    def mock_provider(self) -> MockProvider:
        """Create a mock provider."""
        return MockProvider()

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True)

    def test_repl_init(self, mock_provider: MockProvider, console: Console) -> None:
        """Test REPL initialization."""
        repl = Repl(provider=mock_provider, console=console)
        assert repl.provider is mock_provider
        assert repl.running is False

    def test_repl_with_config(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test REPL with custom config."""
        config = ReplConfig(prompt=">> ", system_prompt="Be helpful")
        repl = Repl(provider=mock_provider, console=console, config=config)
        assert repl.agent.system_prompt == "Be helpful"

    @pytest.mark.anyio
    async def test_process_input_regular_message(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test processing regular user input."""
        repl = Repl(provider=mock_provider, console=console)
        result = await repl.process_input("Hello")
        assert result is True  # Should continue running
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Hello!" in output

    @pytest.mark.anyio
    async def test_process_input_quit_command(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test /quit command exits REPL."""
        repl = Repl(provider=mock_provider, console=console)
        result = await repl.process_input("/quit")
        assert result is False  # Should stop running

    @pytest.mark.anyio
    async def test_process_input_clear_command(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test /clear command clears history."""
        repl = Repl(provider=mock_provider, console=console)
        # Add something to history first
        await repl.process_input("Hello")
        assert len(repl.agent.history) > 0

        # Clear history
        result = await repl.process_input("/clear")
        assert result is True
        assert len(repl.agent.history) == 0

    @pytest.mark.anyio
    async def test_process_input_help_command(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test /help command shows help."""
        repl = Repl(provider=mock_provider, console=console)
        result = await repl.process_input("/help")
        assert result is True
        output = console.file.getvalue()  # type: ignore[union-attr]
        # Should show available commands
        assert "quit" in output.lower() or "help" in output.lower()

    @pytest.mark.anyio
    async def test_process_input_empty(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test empty input is ignored."""
        repl = Repl(provider=mock_provider, console=console)
        result = await repl.process_input("")
        assert result is True
        # Provider shouldn't be called
        assert mock_provider._call_count == 0

    @pytest.mark.anyio
    async def test_process_input_whitespace(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test whitespace-only input is ignored."""
        repl = Repl(provider=mock_provider, console=console)
        result = await repl.process_input("   ")
        assert result is True
        assert mock_provider._call_count == 0

    @pytest.mark.anyio
    async def test_process_input_at_reference(
        self, mock_provider: MockProvider, console: Console, tmp_path: Any
    ) -> None:
        """Test @file reference expansion."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("file contents")

        repl = Repl(provider=mock_provider, console=console)
        # Process with @ reference
        with patch("henchman.cli.repl.expand_at_references") as mock_expand:
            mock_expand.return_value = "Check this: file contents"
            await repl.process_input(f"Check @{test_file}")
            mock_expand.assert_called_once()

    @pytest.mark.anyio
    async def test_process_tool_call(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test processing a tool call from the agent."""
        from henchman.providers.base import FinishReason, StreamChunk, ToolCall

        call_count = 0

        # Set up provider to return a tool call on first call, then content
        async def mock_stream(
            *args: Any, **kwargs: Any  # noqa: ARG001
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield StreamChunk(
                    content=None,
                    tool_calls=[ToolCall(id="tc_1", name="mock_tool", arguments={"input": "test"})],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            else:
                yield StreamChunk(content="Done!", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream  # type: ignore[method-assign]

        repl = Repl(provider=mock_provider, console=console)
        # Register a mock tool (different from built-in read_file)
        from henchman.tools.base import Tool, ToolKind, ToolResult

        class MockTool(Tool):
            @property
            def name(self) -> str:
                return "mock_tool"

            @property
            def description(self) -> str:
                return "A mock tool"

            @property
            def parameters(self) -> dict[str, object]:
                return {"type": "object", "properties": {"input": {"type": "string"}}}

            @property
            def kind(self) -> ToolKind:
                return ToolKind.READ

            async def execute(self, **params: object) -> ToolResult:
                return ToolResult(content="mock result")

        repl.tool_registry.register(MockTool())

        # Process input - should trigger tool call
        await repl.process_input("Do something")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "mock_tool" in output or "Done!" in output

    @pytest.mark.anyio
    async def test_unknown_command(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test unknown command shows error."""
        repl = Repl(provider=mock_provider, console=console)
        result = await repl.process_input("/nonexistent")
        assert result is True
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "unknown" in output.lower() or "not found" in output.lower()

    @pytest.mark.anyio
    async def test_agent_error_handling(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test handling of agent errors in _run_agent."""
        repl = Repl(provider=mock_provider, console=console)

        # Make _handle_agent_event raise an exception
        async def raise_error(event: Any) -> None:  # noqa: ARG001
            raise RuntimeError("Handler error")

        repl._handle_agent_event = raise_error  # type: ignore[method-assign]

        await repl._run_agent("Hello")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "error" in output.lower()

    @pytest.mark.anyio
    async def test_thought_event_handling(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test handling of thought events."""
        from henchman.providers.base import FinishReason, StreamChunk

        async def thinking_stream(
            *args: Any, **kwargs: Any  # noqa: ARG001
        ) -> Any:
            yield StreamChunk(thinking="Thinking about this...")
            yield StreamChunk(content="Answer", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = thinking_stream  # type: ignore[method-assign]

        repl = Repl(provider=mock_provider, console=console)
        await repl.process_input("Hello")
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "thinking" in output.lower()

    @pytest.mark.anyio
    async def test_error_event_handling(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test handling of error events from agent."""

        repl = Repl(provider=mock_provider, console=console)
        await repl._handle_agent_event(AgentEvent(type=EventType.ERROR, data="Test error"))
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "test error" in output.lower()

    @pytest.mark.anyio
    async def test_invalid_tool_call_type(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test handling of invalid tool call type."""
        repl = Repl(provider=mock_provider, console=console)
        # Pass something that isn't a ToolCall - should be silently ignored
        await repl._handle_tool_call("not a tool call")  # type: ignore[arg-type]
        # No error should occur

    @pytest.mark.anyio
    async def test_tool_call_failure(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test handling of tool call that fails."""
        from henchman.providers.base import FinishReason, StreamChunk, ToolCall

        call_count = 0

        async def mock_stream(
            *args: Any, **kwargs: Any  # noqa: ARG001
        ) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield StreamChunk(
                    content=None,
                    tool_calls=[ToolCall(id="tc_1", name="nonexistent_tool", arguments={})],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            else:
                yield StreamChunk(content="OK", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream  # type: ignore[method-assign]

        repl = Repl(provider=mock_provider, console=console)
        await repl.process_input("Do something")
        output = console.file.getvalue()  # type: ignore[union-attr]
        # Should show error for nonexistent tool
        assert "not found" in output.lower() or "error" in output.lower()

    @pytest.mark.anyio
    async def test_slash_only_command(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test slash command that parses to None."""
        repl = Repl(provider=mock_provider, console=console)
        # "/ " is a slash command (starts with / and has content), but parses to None
        result = await repl._handle_command("/ ")
        assert result is True
        # Should not crash, just return

    @pytest.mark.anyio
    async def test_get_input_method(
        self, mock_provider: MockProvider, console: Console
    ) -> None:
        """Test the _get_input method."""
        repl = Repl(provider=mock_provider, console=console)
        # We need to verify it calls prompt_async
        # The mock is already set up by autouse fixture
        # But we need to make sure Repl uses it

        result = await repl._get_input()
        assert result == "mock input"


class TestReplRun:
    """Tests for the run loop."""

    @pytest.fixture(autouse=True)
    def mock_create_session(self):
        with patch("henchman.cli.repl.create_session") as mock:
            mock.return_value = AsyncMock()
            mock.return_value.prompt_async.return_value = "mock input"
            yield mock

    @pytest.mark.anyio
    async def test_run_single_turn(self) -> None:
        """Test running a single turn."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider(["Hello!"])

        repl = Repl(provider=provider, console=console)

        # Mock input to return one message then /quit
        inputs = iter(["Hello", "/quit"])
        async def get_input():
            return next(inputs)

        with patch("henchman.cli.repl.Repl._get_input", side_effect=get_input):
            await repl.run()

        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "Hello!" in output

    @pytest.mark.anyio
    async def test_run_exits_via_running_flag(self) -> None:
        """Test that the run loop exits when running flag is set to False."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider(["Hello!"])

        repl = Repl(provider=provider, console=console)

        # On first input, set running to False to exit the loop naturally
        async def get_input_and_stop() -> str:
            repl.running = False
            return ""  # Empty input to be skipped

        with patch("henchman.cli.repl.Repl._get_input", side_effect=get_input_and_stop):
            await repl.run()

        assert repl.running is False

    @pytest.mark.anyio
    async def test_run_handles_keyboard_interrupt(self) -> None:
        """Test graceful handling of Ctrl+C."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()

        repl = Repl(provider=provider, console=console)

        # Raise KeyboardInterrupt then EOFError to exit
        with patch("henchman.cli.repl.Repl._get_input", side_effect=[KeyboardInterrupt, EOFError]):
            await repl.run()

        # Should exit gracefully
        assert repl.running is False

    @pytest.mark.anyio
    async def test_run_handles_eof(self) -> None:
        """Test graceful handling of EOF (Ctrl+D)."""
        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()

        repl = Repl(provider=provider, console=console)

        with patch("henchman.cli.repl.Repl._get_input", side_effect=EOFError):
            await repl.run()

        assert repl.running is False


class TestSessionAutoSave:
    """Tests for session auto-save functionality."""

    @pytest.fixture(autouse=True)
    def mock_create_session(self):
        with patch("henchman.cli.repl.create_session") as mock:
            mock.return_value = AsyncMock()
            mock.return_value.prompt_async.return_value = "mock input"
            yield mock

    @pytest.mark.anyio
    async def test_auto_save_enabled_saves_session_on_exit(
        self, tmp_path: Any
    ) -> None:
        """Test that session is saved on graceful exit when auto_save is True."""
        from henchman.core.session import SessionManager

        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider(["Hello!"])
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        manager = SessionManager(data_dir=session_dir)
        config = ReplConfig(auto_save=True)

        repl = Repl(provider=provider, console=console, config=config)
        repl.session_manager = manager
        repl.session = manager.create_session(project_hash="test-project")

        # Add a message to the session
        from henchman.core.session import SessionMessage

        repl.session.messages.append(SessionMessage(role="user", content="Hello"))

        # Run with /quit to exit gracefully
        inputs = iter(["/quit"])
        async def get_input():
            return next(inputs)

        with patch("henchman.cli.repl.Repl._get_input", side_effect=get_input):
            await repl.run()

        # Verify session was saved
        saved_sessions = list(session_dir.glob("*.json"))
        assert len(saved_sessions) == 1

    @pytest.mark.anyio
    async def test_auto_save_disabled_does_not_save(self, tmp_path: Any) -> None:
        """Test that session is not saved when auto_save is False."""
        from henchman.core.session import SessionManager

        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider(["Hello!"])
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        manager = SessionManager(data_dir=session_dir)
        config = ReplConfig(auto_save=False)

        repl = Repl(provider=provider, console=console, config=config)
        repl.session_manager = manager
        repl.session = manager.create_session(project_hash="test-project")

        # Add a message to the session
        from henchman.core.session import SessionMessage

        repl.session.messages.append(SessionMessage(role="user", content="Hello"))

        # Run with /quit
        inputs = iter(["/quit"])
        async def get_input():
            return next(inputs)

        with patch("henchman.cli.repl.Repl._get_input", side_effect=get_input):
            await repl.run()

        # Verify session was NOT saved
        saved_sessions = list(session_dir.glob("*.json"))
        assert len(saved_sessions) == 0

    @pytest.mark.anyio
    async def test_auto_save_on_keyboard_interrupt(self, tmp_path: Any) -> None:
        """Test that session is saved on Ctrl+C when auto_save is True."""
        from henchman.core.session import SessionManager

        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        manager = SessionManager(data_dir=session_dir)
        config = ReplConfig(auto_save=True)

        repl = Repl(provider=provider, console=console, config=config)
        repl.session_manager = manager
        repl.session = manager.create_session(project_hash="test-project")

        # Add a message
        from henchman.core.session import SessionMessage

        repl.session.messages.append(SessionMessage(role="user", content="Hello"))

        # Simulate Ctrl+C then EOF
        with patch("henchman.cli.repl.Repl._get_input", side_effect=[KeyboardInterrupt, EOFError]):
            await repl.run()

        # Verify session was saved
        saved_sessions = list(session_dir.glob("*.json"))
        assert len(saved_sessions) == 1

    @pytest.mark.anyio
    async def test_auto_save_skips_empty_session(self, tmp_path: Any) -> None:
        """Test that empty sessions are not saved."""
        from henchman.core.session import SessionManager

        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider()
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        manager = SessionManager(data_dir=session_dir)
        config = ReplConfig(auto_save=True)

        repl = Repl(provider=provider, console=console, config=config)
        repl.session_manager = manager
        repl.session = manager.create_session(project_hash="test-project")
        # Don't add any messages

        # Run with /quit
        inputs = iter(["/quit"])
        async def get_input():
            return next(inputs)

        with patch("henchman.cli.repl.Repl._get_input", side_effect=get_input):
            await repl.run()

        # Verify empty session was NOT saved
        saved_sessions = list(session_dir.glob("*.json"))
        assert len(saved_sessions) == 0

    @pytest.mark.anyio
    async def test_session_messages_recorded_during_conversation(
        self, tmp_path: Any
    ) -> None:
        """Test that messages are recorded to session during conversation."""
        from henchman.core.session import SessionManager

        console = Console(file=StringIO(), force_terminal=True)
        provider = MockProvider(["I'm here to help!"])
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()

        manager = SessionManager(data_dir=session_dir)
        config = ReplConfig(auto_save=True)

        repl = Repl(provider=provider, console=console, config=config)
        repl.session_manager = manager
        repl.session = manager.create_session(project_hash="test-project")

        # Run a conversation then quit
        inputs = iter(["Hello assistant", "/quit"])
        async def get_input():
            return next(inputs)

        with patch("henchman.cli.repl.Repl._get_input", side_effect=get_input):
            await repl.run()

        # Load the saved session and check messages
        saved_sessions = list(session_dir.glob("*.json"))
        assert len(saved_sessions) == 1

        import json

        with open(saved_sessions[0]) as f:
            session_data = json.load(f)

        assert len(session_data["messages"]) >= 2
        # First message should be user
        assert session_data["messages"][0]["role"] == "user"
        assert session_data["messages"][0]["content"] == "Hello assistant"
