"""Tests for /chat command."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.chat import ChatCommand
from henchman.core.session import SessionManager, SessionMessage


class TestChatCommand:
    """Tests for /chat command."""

    @pytest.fixture
    def console(self) -> Console:
        """Create a test console."""
        return Console(file=StringIO(), force_terminal=True, width=80)

    @pytest.fixture
    def temp_data_dir(self, tmp_path: Path) -> Path:
        """Create a temporary data directory."""
        data_dir = tmp_path / "sessions"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def session_manager(self, temp_data_dir: Path) -> SessionManager:
        """Create a session manager."""
        return SessionManager(data_dir=temp_data_dir)

    @pytest.fixture
    def ctx(self, console: Console, session_manager: SessionManager) -> CommandContext:
        """Create a command context."""
        ctx = CommandContext(console=console, args=[])
        ctx.session_manager = session_manager  # type: ignore[attr-defined]
        return ctx

    def test_name(self) -> None:
        """Test command name."""
        cmd = ChatCommand()
        assert cmd.name == "chat"

    def test_description(self) -> None:
        """Test command description."""
        cmd = ChatCommand()
        assert "session" in cmd.description.lower() or "chat" in cmd.description.lower()

    def test_usage(self) -> None:
        """Test command usage."""
        cmd = ChatCommand()
        assert "/chat" in cmd.usage

    @pytest.mark.anyio
    async def test_chat_no_args_shows_help(self, ctx: CommandContext) -> None:
        """Test /chat with no args shows help."""
        cmd = ChatCommand()
        await cmd.execute(ctx)
        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "save" in output.lower() or "list" in output.lower()

    @pytest.mark.anyio
    async def test_chat_save(self, ctx: CommandContext) -> None:
        """Test /chat save creates a session."""
        # Create a current session
        session = ctx.session_manager.create_session(project_hash="test")  # type: ignore[attr-defined]
        session.messages.append(SessionMessage(role="user", content="Hello"))
        ctx.session_manager.set_current(session)  # type: ignore[attr-defined]

        ctx.args = ["save", "my-session"]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "saved" in output.lower() or "my-session" in output

    @pytest.mark.anyio
    async def test_chat_save_no_tag(self, ctx: CommandContext) -> None:
        """Test /chat save without tag uses auto-generated name."""
        session = ctx.session_manager.create_session(project_hash="test")  # type: ignore[attr-defined]
        ctx.session_manager.set_current(session)  # type: ignore[attr-defined]

        ctx.args = ["save"]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "saved" in output.lower()

    @pytest.mark.anyio
    async def test_chat_save_no_session(self, ctx: CommandContext) -> None:
        """Test /chat save with no current session shows error."""
        ctx.args = ["save", "my-session"]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "no" in output.lower() or "session" in output.lower()

    @pytest.mark.anyio
    async def test_chat_list(self, ctx: CommandContext) -> None:
        """Test /chat list shows saved sessions."""
        # Create and save sessions
        s1 = ctx.session_manager.create_session(project_hash="test", tag="session1")  # type: ignore[attr-defined]
        s2 = ctx.session_manager.create_session(project_hash="test", tag="session2")  # type: ignore[attr-defined]
        ctx.session_manager.save(s1)  # type: ignore[attr-defined]
        ctx.session_manager.save(s2)  # type: ignore[attr-defined]

        ctx.args = ["list"]
        ctx.project_hash = "test"  # type: ignore[attr-defined]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "session1" in output or "session2" in output

    @pytest.mark.anyio
    async def test_chat_list_empty(self, ctx: CommandContext) -> None:
        """Test /chat list with no sessions."""
        ctx.args = ["list"]
        ctx.project_hash = "test"  # type: ignore[attr-defined]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "no" in output.lower() or "empty" in output.lower() or len(output) > 0

    @pytest.mark.anyio
    async def test_chat_resume(self, ctx: CommandContext) -> None:
        """Test /chat resume loads a session."""
        # Create and save a session
        session = ctx.session_manager.create_session(project_hash="test", tag="my-session")  # type: ignore[attr-defined]
        session.messages.append(SessionMessage(role="user", content="Hello"))
        ctx.session_manager.save(session)  # type: ignore[attr-defined]

        ctx.args = ["resume", "my-session"]
        ctx.project_hash = "test"  # type: ignore[attr-defined]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "resumed" in output.lower() or "loaded" in output.lower() or "my-session" in output

    @pytest.mark.anyio
    async def test_chat_resume_not_found(self, ctx: CommandContext) -> None:
        """Test /chat resume with nonexistent session."""
        ctx.args = ["resume", "nonexistent"]
        ctx.project_hash = "test"  # type: ignore[attr-defined]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "not found" in output.lower() or "error" in output.lower()

    @pytest.mark.anyio
    async def test_chat_unknown_subcommand(self, ctx: CommandContext) -> None:
        """Test /chat with unknown subcommand."""
        ctx.args = ["unknown"]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert len(output) > 0  # Should show some output

    @pytest.mark.anyio
    async def test_chat_save_no_manager(self, console: Console) -> None:
        """Test /chat save without session manager."""
        ctx = CommandContext(console=console, args=["save", "test"])
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "not available" in output.lower()

    @pytest.mark.anyio
    async def test_chat_list_no_manager(self, console: Console) -> None:
        """Test /chat list without session manager."""
        ctx = CommandContext(console=console, args=["list"])
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "not available" in output.lower()

    @pytest.mark.anyio
    async def test_chat_resume_no_manager(self, console: Console) -> None:
        """Test /chat resume without session manager."""
        ctx = CommandContext(console=console, args=["resume", "test"])
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "not available" in output.lower()

    @pytest.mark.anyio
    async def test_chat_resume_no_tag(self, ctx: CommandContext) -> None:
        """Test /chat resume without specifying a tag."""
        ctx.args = ["resume"]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        output = ctx.console.file.getvalue()  # type: ignore[union-attr]
        assert "usage" in output.lower()

    @pytest.mark.anyio
    async def test_chat_resume_restores_agent_history(self, ctx: CommandContext) -> None:
        """Test /chat resume restores session messages to agent history."""
        from unittest.mock import AsyncMock, Mock

        from henchman.core.agent import Agent

        # Create a mock agent
        mock_provider = Mock()
        mock_provider.chat_completion_stream = AsyncMock()
        agent = Agent(provider=mock_provider)
        ctx.agent = agent

        # Create and save a session with messages
        session = ctx.session_manager.create_session(project_hash="test", tag="history-test")  # type: ignore[attr-defined]
        session.messages.append(SessionMessage(role="user", content="Hello"))
        session.messages.append(SessionMessage(role="assistant", content="Hi there!"))
        ctx.session_manager.save(session)  # type: ignore[attr-defined]

        ctx.args = ["resume", "history-test"]
        ctx.project_hash = "test"  # type: ignore[attr-defined]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        # Verify agent history was restored
        assert len(agent.messages) == 2
        assert agent.messages[0].role == "user"
        assert agent.messages[0].content == "Hello"
        assert agent.messages[1].role == "assistant"
        assert agent.messages[1].content == "Hi there!"

    @pytest.mark.anyio
    async def test_chat_resume_restores_tool_calls(self, ctx: CommandContext) -> None:
        """Test /chat resume correctly restores sessions with tool calls."""
        from unittest.mock import AsyncMock, Mock

        from henchman.core.agent import Agent

        # Create a mock agent
        mock_provider = Mock()
        mock_provider.chat_completion_stream = AsyncMock()
        agent = Agent(provider=mock_provider)
        ctx.agent = agent

        # Create and save a session with tool calls
        session = ctx.session_manager.create_session(project_hash="test", tag="tool-test")  # type: ignore[attr-defined]
        session.messages.append(SessionMessage(role="user", content="Read file.txt"))
        session.messages.append(
            SessionMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    {"id": "call_123", "name": "read_file", "arguments": {"path": "file.txt"}}
                ],
            )
        )
        session.messages.append(
            SessionMessage(role="tool", content="File content here", tool_call_id="call_123")
        )
        session.messages.append(SessionMessage(role="assistant", content="The file contains: ..."))
        ctx.session_manager.save(session)  # type: ignore[attr-defined]

        ctx.args = ["resume", "tool-test"]
        ctx.project_hash = "test"  # type: ignore[attr-defined]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        # Verify agent history was restored correctly
        assert len(agent.messages) == 4

        # User message
        assert agent.messages[0].role == "user"
        assert agent.messages[0].content == "Read file.txt"

        # Assistant with tool_calls
        assert agent.messages[1].role == "assistant"
        assert agent.messages[1].tool_calls is not None
        assert len(agent.messages[1].tool_calls) == 1
        assert agent.messages[1].tool_calls[0].id == "call_123"
        assert agent.messages[1].tool_calls[0].name == "read_file"

        # Tool result
        assert agent.messages[2].role == "tool"
        assert agent.messages[2].content == "File content here"
        assert agent.messages[2].tool_call_id == "call_123"

        # Final assistant response
        assert agent.messages[3].role == "assistant"
        assert "file contains" in agent.messages[3].content.lower()

    @pytest.mark.anyio
    async def test_chat_resume_validates_restored_history(self, ctx: CommandContext) -> None:
        """Test that restored session history passes message validation."""
        from unittest.mock import AsyncMock, Mock

        from henchman.core.agent import Agent
        from henchman.utils.validation import validate_message_sequence

        # Create a mock agent
        mock_provider = Mock()
        mock_provider.chat_completion_stream = AsyncMock()
        agent = Agent(provider=mock_provider)
        ctx.agent = agent

        # Create session with complete tool call sequence
        session = ctx.session_manager.create_session(project_hash="test", tag="validate-test")  # type: ignore[attr-defined]
        session.messages.append(SessionMessage(role="user", content="List files"))
        session.messages.append(
            SessionMessage(
                role="assistant",
                content=None,
                tool_calls=[
                    {"id": "call_1", "name": "ls", "arguments": {"path": "."}},
                    {"id": "call_2", "name": "glob", "arguments": {"pattern": "*.py"}},
                ],
            )
        )
        session.messages.append(
            SessionMessage(role="tool", content="file1.py\nfile2.py", tool_call_id="call_1")
        )
        session.messages.append(
            SessionMessage(role="tool", content="test.py", tool_call_id="call_2")
        )
        session.messages.append(SessionMessage(role="assistant", content="Found these files..."))
        ctx.session_manager.save(session)  # type: ignore[attr-defined]

        ctx.args = ["resume", "validate-test"]
        ctx.project_hash = "test"  # type: ignore[attr-defined]
        cmd = ChatCommand()
        await cmd.execute(ctx)

        # Validate the restored message sequence
        # This should NOT raise ValueError
        validate_message_sequence(agent.messages)
