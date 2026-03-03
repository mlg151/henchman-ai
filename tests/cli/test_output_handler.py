"""Tests for the OutputHandler component."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.status import Status

from henchman.cli.output_handler import OutputHandler
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_manager import ToolManager
from henchman.cli.ui_renderer import UIRenderer
from henchman.core.agent import Agent
from henchman.core.session import Session
from henchman.mcp.manager import McpManager
from henchman.providers.base import ModelProvider


class TestOutputHandler:
    """Tests for OutputHandler class."""

    def test_initialization(self) -> None:
        """Test OutputHandler initialization."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        assert handler.renderer == renderer
        assert handler.tool_manager == tool_manager
        assert handler.session_manager == session_manager
        assert handler.provider == provider
        assert handler.settings is None
        assert handler.rag_system is None
        assert handler.mcp_manager is None

    def test_initialization_with_optional_args(self) -> None:
        """Test OutputHandler initialization with optional arguments."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)
        settings = MagicMock()
        rag_system = MagicMock()
        mcp_manager = MagicMock(spec=McpManager)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            settings=settings,
            rag_system=rag_system,
            mcp_manager=mcp_manager,
        )

        assert handler.settings == settings
        assert handler.rag_system == rag_system
        assert handler.mcp_manager == mcp_manager

    def test_get_toolbar_status_basic(self) -> None:
        """Test get_toolbar_status with basic configuration."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        # Mock session with plan_mode=False
        mock_session = MagicMock(spec=Session)
        mock_session.plan_mode = False
        session_manager.current = mock_session

        # Mock provider name
        provider.__class__.__name__ = "OpenAIProvider"
        provider.default_model = "gpt-4"

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        status = handler.get_toolbar_status()

        # Should have at least CHAT mode and provider info
        assert len(status) >= 2
        assert any("CHAT" in text for _, text in status)
        assert any("OpenAI:gpt-4" in text for _, text in status)

    def test_get_toolbar_status_plan_mode(self) -> None:
        """Test get_toolbar_status with plan mode enabled."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        # Mock session with plan_mode=True
        mock_session = MagicMock(spec=Session)
        mock_session.plan_mode = True
        session_manager.current = mock_session

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        status = handler.get_toolbar_status()

        # Should have PLAN MODE
        assert any("PLAN MODE" in text for _, text in status)

    def test_get_toolbar_status_with_tokens(self) -> None:
        """Test get_toolbar_status with token counting."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        # Mock session
        mock_session = MagicMock(spec=Session)
        mock_session.plan_mode = False
        session_manager.current = mock_session

        # Mock agent with messages
        agent = MagicMock(spec=Agent)
        agent.get_messages_for_api.return_value = [{"role": "user", "content": "test"}]

        # Mock settings with context
        settings = MagicMock()
        settings.context = MagicMock()
        settings.context.max_tokens = 4000

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            settings=settings,
        )

        with patch("henchman.utils.tokens.TokenCounter") as mock_counter:
            mock_counter.count_messages.return_value = 1000

            status = handler.get_toolbar_status(agent)

            # Should have token percentage (1000/4000 = 25%)
            assert any("25%" in text for _, text in status)

    def test_get_toolbar_status_with_tool_count(self) -> None:
        """Test get_toolbar_status with tool count."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        # Mock session
        mock_session = MagicMock(spec=Session)
        mock_session.plan_mode = False
        session_manager.current = mock_session

        # Mock tool registry
        mock_registry = MagicMock()
        mock_registry.list_tools.return_value = ["tool1", "tool2", "tool3"]
        tool_manager.registry = mock_registry

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        status = handler.get_toolbar_status()

        # Should have tool count
        assert any("Tools: 3" in text for _, text in status)

    def test_get_toolbar_status_with_mcp(self) -> None:
        """Test get_toolbar_status with MCP connections."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)
        mcp_manager = MagicMock(spec=McpManager)

        # Mock session
        mock_session = MagicMock(spec=Session)
        mock_session.plan_mode = False
        session_manager.current = mock_session

        # Mock MCP clients
        mock_client1 = MagicMock()
        mock_client1.is_connected = True
        mock_client2 = MagicMock()
        mock_client2.is_connected = False
        mcp_manager.clients = {"client1": mock_client1, "client2": mock_client2}

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            mcp_manager=mcp_manager,
        )

        status = handler.get_toolbar_status()

        # Should have MCP status
        assert any("MCP: 1/2" in text for _, text in status)

    def test_get_toolbar_status_with_rag_indexing(self) -> None:
        """Test get_toolbar_status with RAG indexing."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)
        rag_system = MagicMock()

        # Mock session
        mock_session = MagicMock(spec=Session)
        mock_session.plan_mode = False
        session_manager.current = mock_session

        # Mock RAG system indexing
        rag_system.is_indexing = True

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            rag_system=rag_system,
        )

        status = handler.get_toolbar_status()

        # Should have RAG indexing status
        assert any("RAG: Indexing..." in text for _, text in status)

    def test_get_rich_status_message(self) -> None:
        """Test get_rich_status_message method."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        agent = MagicMock(spec=Agent)

        renderer.get_rich_status_message.return_value = "Status message"

        result = handler.get_rich_status_message(agent)

        renderer.get_rich_status_message.assert_called_once_with(
            session_manager.current, agent, None
        )
        assert result == "Status message"

    def test_delegation_methods(self) -> None:
        """Test delegation methods to renderer."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        # Test each delegation method
        handler.print_welcome()
        renderer.print_welcome.assert_called_once()

        handler.print_goodbye()
        renderer.print_goodbye.assert_called_once()

        handler.print_newline()
        renderer.print_newline.assert_called_once()

        handler.success("Success!")
        renderer.success.assert_called_once_with("Success!")

        handler.error("Error!")
        renderer.error.assert_called_once_with("Error!")

        handler.warning("Warning!")
        renderer.warning.assert_called_once_with("Warning!")

        handler.muted("Muted!")
        renderer.muted.assert_called_once_with("Muted!")

        handler.thinking("Thinking...")
        renderer.thinking.assert_called_once_with("Thinking...")

        handler.print_agent_content("Content")
        renderer.print_agent_content.assert_called_once_with("Content")

    def test_create_status(self) -> None:
        """Test create_status method."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        mock_status = MagicMock(spec=Status)
        renderer.create_status.return_value = mock_status

        result = handler.create_status("Processing...", spinner="dots")

        renderer.create_status.assert_called_once_with("Processing...", spinner="dots")
        assert result == mock_status

    def test_show_turn_status(self) -> None:
        """Test show_turn_status method."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        agent = MagicMock(spec=Agent)
        agent.turn = MagicMock()
        agent.turn.get_status_string.return_value = "Turn 1/10"
        agent.turn.is_spinning.return_value = False
        agent.turn.is_approaching_limit.return_value = False
        agent.max_tokens = 4000

        handler.show_turn_status(agent, base_iterations=10)

        agent.turn.get_status_string.assert_called_once_with(
            base_limit=10,
            max_tokens=4000,
        )
        # Should call muted since not spinning or approaching limit
        renderer.muted.assert_called_once_with("Turn 1/10")

    def test_show_turn_status_spinning(self) -> None:
        """Test show_turn_status when agent is spinning."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        agent = MagicMock(spec=Agent)
        agent.turn = MagicMock()
        agent.turn.get_status_string.return_value = "Turn 5/10 - Spinning"
        agent.turn.is_spinning.return_value = True
        agent.turn.is_approaching_limit.return_value = False

        handler.show_turn_status(agent, base_iterations=10)

        # Should call warning when spinning
        renderer.warning.assert_called_once_with("Turn 5/10 - Spinning")

    def test_show_turn_status_approaching_limit(self) -> None:
        """Test show_turn_status when approaching limit."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        agent = MagicMock(spec=Agent)
        agent.turn = MagicMock()
        agent.turn.get_status_string.return_value = "Turn 8/10"
        agent.turn.is_spinning.return_value = False
        agent.turn.is_approaching_limit.return_value = True

        handler.show_turn_status(agent, base_iterations=10)

        # Should call warning when approaching limit
        renderer.warning.assert_called_once_with("Turn 8/10")

    @pytest.mark.asyncio
    async def test_start_background_indexing(self) -> None:
        """Test start_background_indexing method."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)
        rag_system = MagicMock()

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            rag_system=rag_system,
        )

        # Mock async method
        rag_system.index_async = AsyncMock()

        with patch("asyncio.create_task") as mock_create_task:
            handler.start_background_indexing()

            rag_system.index_async.assert_called_once()
            # Check that create_task was called with the async method
            assert mock_create_task.call_count == 1
            # Get the actual coroutine that was passed
            call_args = mock_create_task.call_args[0]
            assert len(call_args) == 1
            # The coroutine should be from rag_system.index_async()
            # We can't compare coroutine objects directly, but we know
            # it should have been called

    def test_start_background_indexing_no_rag(self) -> None:
        """Test start_background_indexing without RAG system."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
        )

        # Should not raise error when no RAG system
        handler.start_background_indexing()

    def test_start_background_indexing_no_index_async(self) -> None:
        """Test start_background_indexing when RAG system has no index_async method."""
        renderer = MagicMock()
        tool_manager = MagicMock(spec=ToolManager)
        session_manager = MagicMock(spec=ReplSessionManager)
        provider = MagicMock(spec=ModelProvider)
        rag_system = MagicMock()

        handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            rag_system=rag_system,
        )

        # RAG system doesn't have index_async method
        delattr(rag_system, "index_async")

        # Should not raise error
        handler.start_background_indexing()
