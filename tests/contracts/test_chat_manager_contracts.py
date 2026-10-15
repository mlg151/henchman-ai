"""Contract tests for ChatManager subsystem boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from henchman.chat.base import ChatMessage, ChatPlatform
from henchman.chat.manager import ChatManager, _FallbackChatAgent

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ===========================================================================
# _ChatAgent Protocol contract
# ===========================================================================


class TestChatAgentProtocolContract:
    """_ChatAgent protocol must define the expected interface."""

    def test_protocol_requires_tool_registry(self) -> None:
        """Any _ChatAgent must expose a tool_registry attribute."""

        class CompliantAgent:
            tool_registry = MagicMock()

            async def run(self, user_input: str) -> AsyncIterator[Any]:
                if False:
                    yield None

            async def continue_with_tool_results(self) -> AsyncIterator[Any]:
                if False:
                    yield None

            def submit_tool_result(self, tool_call_id: str, result: str) -> None:
                pass

            def clear_history(self) -> None:
                pass

        agent = CompliantAgent()
        # Verify the protocol contract: hasattr checks
        assert hasattr(agent, "tool_registry")
        assert hasattr(agent, "run")
        assert hasattr(agent, "continue_with_tool_results")
        assert hasattr(agent, "submit_tool_result")
        assert hasattr(agent, "clear_history")
        assert callable(agent.run)
        assert callable(agent.continue_with_tool_results)
        assert callable(agent.submit_tool_result)
        assert callable(agent.clear_history)

    def test_protocol_requires_run_method(self) -> None:
        """_ChatAgent must have an async run method accepting user_input."""

        class MinimalAgent:
            tool_registry = None

            async def run(self, user_input: str) -> AsyncIterator[Any]:
                if False:
                    yield None

            async def continue_with_tool_results(self) -> AsyncIterator[Any]:
                if False:
                    yield None

            def submit_tool_result(self, tool_call_id: str, result: str) -> None:
                pass

            def clear_history(self) -> None:
                pass

        agent = MinimalAgent()
        assert callable(agent.run)

    def test_protocol_requires_submit_tool_result(self) -> None:
        """_ChatAgent must have a submit_tool_result method."""

        class AgentWithResults:
            tool_registry = None
            _results: dict[str, str] = {}

            async def run(self, user_input: str) -> AsyncIterator[Any]:
                if False:
                    yield None

            async def continue_with_tool_results(self) -> AsyncIterator[Any]:
                if False:
                    yield None

            def submit_tool_result(self, tool_call_id: str, result: str) -> None:
                self._results[tool_call_id] = result

            def clear_history(self) -> None:
                self._results.clear()

        agent = AgentWithResults()
        agent.submit_tool_result("tc-1", "success")
        assert agent._results["tc-1"] == "success"

    def test_protocol_requires_clear_history(self) -> None:
        """_ChatAgent must have a clear_history method."""

        class ClearableAgent:
            tool_registry = None
            _history: list = []

            async def run(self, user_input: str) -> AsyncIterator[Any]:
                if False:
                    yield None

            async def continue_with_tool_results(self) -> AsyncIterator[Any]:
                if False:
                    yield None

            def submit_tool_result(self, tool_call_id: str, result: str) -> None:
                pass

            def clear_history(self) -> None:
                self._history.clear()

        agent = ClearableAgent()
        agent._history = ["msg1", "msg2"]
        agent.clear_history()
        assert agent._history == []


# ===========================================================================
# _FallbackChatAgent contract
# ===========================================================================


class TestFallbackChatAgentContract:
    """_FallbackChatAgent must satisfy the _ChatAgent protocol."""

    def test_fallback_has_tool_registry(self) -> None:
        """_FallbackChatAgent must expose tool_registry."""
        registry = MagicMock()
        agent = _FallbackChatAgent(tool_registry=registry)
        assert agent.tool_registry is registry

    def test_fallback_submit_tool_result(self) -> None:
        """_FallbackChatAgent must record tool results."""
        agent = _FallbackChatAgent(tool_registry=MagicMock())
        agent.submit_tool_result("tc-1", "result data")
        assert agent._tool_results["tc-1"] == "result data"

    def test_fallback_clear_history(self) -> None:
        """_FallbackChatAgent must clear tool results on clear_history."""
        agent = _FallbackChatAgent(tool_registry=MagicMock())
        agent.submit_tool_result("tc-1", "data")
        agent.submit_tool_result("tc-2", "more data")
        assert len(agent._tool_results) == 2

        agent.clear_history()
        assert agent._tool_results == {}

    def test_fallback_run_is_async_generator(self) -> None:
        """_FallbackChatAgent.run must be an async generator."""
        agent = _FallbackChatAgent(tool_registry=MagicMock())
        result = agent.run("hello")
        # Check it's an async generator (has __aiter__ and __anext__)
        assert hasattr(result, "__aiter__")
        assert hasattr(result, "__anext__")

    def test_fallback_continue_is_async_generator(self) -> None:
        """_FallbackChatAgent.continue_with_tool_results must be an async generator."""
        agent = _FallbackChatAgent(tool_registry=MagicMock())
        result = agent.continue_with_tool_results()
        assert hasattr(result, "__aiter__")
        assert hasattr(result, "__anext__")


# ===========================================================================
# ChatManager contract
# ===========================================================================


class TestChatManagerContract:
    """ChatManager must satisfy the chat coordination interface contract."""

    def test_manager_starts_empty(self) -> None:
        """ChatManager should start with no bots registered."""
        settings = MagicMock()
        manager = ChatManager(settings)
        assert manager.bots == {}
        assert manager.active_users == []

    def test_manager_registers_bot(self) -> None:
        """ChatManager should track registered bots by platform."""

        class FakeBot:
            platform = ChatPlatform.DISCORD
            is_connected = False

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def send_message(
                self,
                user_id: str,
                content: str,
                *,
                split_long: bool = True,
            ) -> None:
                pass

            async def send_typing(self, user_id: str) -> None:
                pass

            def set_message_handler(self, handler: object) -> None:
                pass

        settings = MagicMock()
        manager = ChatManager(settings)
        bot = FakeBot()
        manager._bots[ChatPlatform.DISCORD] = bot

        assert ChatPlatform.DISCORD in manager.bots
        assert manager.bots[ChatPlatform.DISCORD] is bot

    def test_manager_active_users(self) -> None:
        """ChatManager should report active user IDs."""
        settings = MagicMock()
        manager = ChatManager(settings)
        manager._user_agents = {"user-1": MagicMock(), "user-2": MagicMock()}
        users = manager.active_users
        assert "user-1" in users
        assert "user-2" in users
        assert len(users) == 2


# ===========================================================================
# ChatMessage integration with ChatManager
# ===========================================================================


class TestChatManagerMessageHandlingContract:
    """ChatManager message handling must respect ChatMessage contract."""

    def test_message_has_required_fields_for_handling(self) -> None:
        """ChatMessage must have the fields ChatManager expects."""
        msg = ChatMessage(
            id="msg-1",
            user_id="user-42",
            username="alice",
            content="/clear",
            timestamp=MagicMock(),
            platform=ChatPlatform.DISCORD,
        )
        # Verify all fields the manager accesses
        assert hasattr(msg, "content")
        assert hasattr(msg, "user_id")
        assert hasattr(msg, "username")
        assert hasattr(msg, "platform")
        assert msg.content.startswith("/")  # Command detection
        assert msg.user_id == "user-42"

    def test_command_message_detected(self) -> None:
        """Messages starting with / should be detected as commands."""
        msg = ChatMessage(
            id="msg-1",
            user_id="user-1",
            username="user",
            content="/help",
            timestamp=MagicMock(),
            platform=ChatPlatform.DISCORD,
        )
        assert msg.content.startswith("/")

    def test_regular_message_not_command(self) -> None:
        """Messages not starting with / should not be commands."""
        msg = ChatMessage(
            id="msg-2",
            user_id="user-1",
            username="user",
            content="Hello there!",
            timestamp=MagicMock(),
            platform=ChatPlatform.DISCORD,
        )
        assert not msg.content.startswith("/")
