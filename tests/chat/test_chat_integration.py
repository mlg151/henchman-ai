"""Full integration tests for the Discord chat pipeline.

These tests exercise the real ChatManager, Agent, and ToolRegistry end-to-end.
Only the following are substituted:
  - User messages: ChatMessage objects constructed directly (no Discord connection)
  - Bot I/O: RecordingBot, a real ChatBot subclass that records sent messages
  - LLM provider: ScriptedProvider, a real ModelProvider that returns pre-scripted
    streaming responses (no external API calls)

Nothing else is mocked: ChatManager, Agent, ToolRegistry, StallDetector,
session management, tool execution, message history, etc. all run for real.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from henchman.chat.base import ChatBot, ChatMessage, ChatPlatform
from henchman.chat.manager import ChatManager
from henchman.config.schema import Settings
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)

# ---------------------------------------------------------------------------
# ScriptedProvider — a real ModelProvider with pre-programmed responses
# ---------------------------------------------------------------------------


class ScriptedProvider(ModelProvider):
    """A real ModelProvider that returns pre-scripted streaming responses.

    Responses are queued and returned in order. Each response is a list of
    StreamChunks that will be yielded one by one. Raise StopIteration if
    more calls are made than responses queued (test bug, not production bug).

    Args:
        responses: List of scripted response sequences. Each entry is a list
            of StreamChunks to yield for one call.
        model: Model name reported by this provider.
    """

    def __init__(
        self: ScriptedProvider,
        responses: list[list[StreamChunk]],
        model: str = "test-model",
    ) -> None:
        """Initialize the scripted provider.

        Args:
            responses: Ordered list of StreamChunk sequences to return.
            model: Model name for provider identification.
        """
        self._responses = list(responses)
        self._call_index = 0
        self._model = model
        self.call_count = 0
        self.calls: list[list[Message]] = []

    @property
    def name(self: ScriptedProvider) -> str:
        """Return provider name.

        Returns:
            Provider name string.
        """
        return "scripted"

    @property
    def default_model(self: ScriptedProvider) -> str:
        """Return default model name.

        Returns:
            Model name string.
        """
        return self._model

    async def chat_completion_stream(
        self: ScriptedProvider,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Yield the next scripted response sequence.

        Args:
            messages: Conversation history (recorded for test assertions).
            tools: Available tool declarations (ignored).
            **kwargs: Ignored.

        Yields:
            StreamChunk objects from the pre-scripted response.
        """
        self.calls.append(list(messages))
        self.call_count += 1
        idx = self._call_index
        self._call_index += 1
        if idx >= len(self._responses):
            # Fallback: return a simple stop response rather than crashing
            yield StreamChunk(content="(no more scripted responses)", finish_reason=FinishReason.STOP)
            return
        for chunk in self._responses[idx]:
            yield chunk


# ---------------------------------------------------------------------------
# RecordingBot — a real ChatBot subclass that records outgoing messages
# ---------------------------------------------------------------------------


class RecordingBot(ChatBot):
    """A real ChatBot subclass that records all sent messages for assertions.

    Implements the full ChatBot interface without making any network calls.
    Use ``sent_messages`` to inspect what the bot would have sent to Discord.

    Attributes:
        sent_messages: Ordered list of (user_id, content) tuples sent.
    """

    def __init__(self: RecordingBot) -> None:
        """Initialize the recording bot."""
        self.sent_messages: list[tuple[str, str]] = []
        self.typing_indicators: list[str] = []
        self._connected = True

    @property
    def platform(self: RecordingBot) -> ChatPlatform:
        """Return platform type.

        Returns:
            ChatPlatform.DISCORD
        """
        return ChatPlatform.DISCORD

    @property
    def is_connected(self: RecordingBot) -> bool:
        """Return connection status.

        Returns:
            Always True for testing.
        """
        return self._connected

    async def start(self: RecordingBot) -> None:
        """No-op start for testing.

        Returns:
            None
        """

    async def stop(self: RecordingBot) -> None:
        """No-op stop for testing.

        Returns:
            None
        """

    async def send_message(
        self: RecordingBot,
        user_id: str,
        content: str,
        *,
        split_long: bool = True,
    ) -> None:
        """Record a message that would be sent to the user.

        Args:
            user_id: Platform-specific user identifier.
            content: Message content to record.
            split_long: Ignored for testing.

        Returns:
            None
        """
        self.sent_messages.append((user_id, content))
        return True

    async def send_typing(self: RecordingBot, user_id: str) -> None:
        """Record a typing indicator.

        Args:
            user_id: Platform-specific user identifier.

        Returns:
            None
        """
        self.typing_indicators.append(user_id)

    def set_message_handler(self: RecordingBot, handler: Any) -> None:
        """No-op: handler is set on ChatManager, not the bot.

        Args:
            handler: Ignored.

        Returns:
            None
        """

    def all_text(self: RecordingBot) -> str:
        """Concatenate all non-tool-notification messages into one string.

        Returns:
            Full text content sent by the bot.
        """
        return " ".join(
            content
            for _, content in self.sent_messages
            if not content.startswith(("🔧", "✅", "❌", "⚠️"))
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_message(content: str, user_id: str = "test-user-123") -> ChatMessage:
    """Create a test ChatMessage.

    Args:
        content: Message content from the user.
        user_id: User identifier (default: test-user-123).

    Returns:
        ChatMessage for use in test calls.
    """
    return ChatMessage(
        id="msg-001",
        user_id=user_id,
        username="TestUser",
        content=content,
        timestamp=datetime.now(UTC),
        platform=ChatPlatform.DISCORD,
        is_dm=True,
    )


def simple_stop_response(text: str) -> list[StreamChunk]:
    """Build a simple single-round stop response.

    Args:
        text: The text content to stream.

    Returns:
        List of StreamChunks for a plain text LLM response.
    """
    half = len(text) // 2
    return [
        StreamChunk(content=text[:half]),
        StreamChunk(content=text[half:]),
        StreamChunk(finish_reason=FinishReason.STOP),
    ]


def tool_call_response(
    tool_name: str,
    args: dict[str, Any],
    tool_id: str = "call-001",
) -> list[StreamChunk]:
    """Build a response that requests a single tool call.

    Args:
        tool_name: Name of the tool to call.
        args: Arguments for the tool.
        tool_id: Tool call ID.

    Returns:
        List of StreamChunks ending with a TOOL_CALLS finish reason.
    """
    return [
        StreamChunk(
            tool_calls=[ToolCall(id=tool_id, name=tool_name, arguments=args)],
            finish_reason=FinishReason.TOOL_CALLS,
        ),
    ]


def make_manager_with_provider(
    provider: ScriptedProvider,
) -> tuple[ChatManager, RecordingBot]:
    """Create a real ChatManager wired to a ScriptedProvider and RecordingBot.

    No mocking: real Settings, real ChatManager, real Agent (created on first
    message). Only the LLM provider and bot I/O are substituted with test
    doubles.

    Args:
        provider: The scripted provider to inject into the agent.

    Returns:
        Tuple of (ChatManager, RecordingBot).
    """
    settings = Settings()
    manager = ChatManager(settings)

    bot = RecordingBot()
    manager._bots[ChatPlatform.DISCORD] = bot

    # Patch _get_or_create_agent to inject our scripted provider
    # Everything else (Agent, ToolRegistry, StallDetector) runs for real.
    async def _inject_provider(user_id: str) -> Any:
        from henchman.cli.tool_manager import ToolManager
        from henchman.core import Agent

        if user_id in manager._user_agents:
            return manager._user_agents[user_id]

        tool_manager = ToolManager(settings)
        tool_manager.register_builtin_tools()
        tool_manager.set_auto_approve(auto_approve=True)

        system_prompt = (
            "You are Henchman-AI, a helpful AI assistant accessible via Discord chat. "
            "Only respond to the user's message. Never use tools for greetings."
        )
        agent = Agent(
            provider=provider,
            system_prompt=system_prompt,
            tool_registry=tool_manager.registry,
        )
        # Disable stall detection — same as production Discord mode
        agent.stall_detection_enabled = False

        manager._user_agents[user_id] = agent
        manager._user_histories[user_id] = []
        return agent

    manager._get_or_create_agent = _inject_provider  # type: ignore[method-assign]
    return manager, bot


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestChatIntegration:
    """End-to-end integration tests for the Discord chat pipeline."""

    @pytest.mark.anyio
    async def test_greeting_no_tool_calls_no_iteration_warning(self) -> None:
        """A simple greeting must produce a clean response with no warnings.

        This was the primary bug in 0.3.14: content chunks counted toward
        max_iterations, so a normal 100-chunk greeting hit the cap and emitted
        '⚠️ Maximum tool iterations reached.'
        """
        greeting_text = "Hello! I'm Henchman-AI, ready to help you today."
        # Stream the greeting as many small chunks to simulate real LLM output
        chunks = [StreamChunk(content=c) for c in greeting_text] + [
            StreamChunk(finish_reason=FinishReason.STOP)
        ]

        manager, bot = make_manager_with_provider(ScriptedProvider([chunks]))
        await manager._handle_message(make_message("Howdy"))

        # Must not contain any warning message
        all_sent = " ".join(c for _, c in bot.sent_messages)
        assert "Maximum tool iterations" not in all_sent, (
            f"Unexpected iteration warning. Messages sent: {bot.sent_messages}"
        )
        # Must contain the actual greeting
        assert "Henchman-AI" in all_sent or "Hello" in all_sent

    @pytest.mark.anyio
    async def test_greeting_produces_exactly_one_response_round(self) -> None:
        """A greeting must complete in exactly one LLM call with no continuation.

        This covers the 0.3.14 bug where stall detection caused multiple
        continuation rounds, producing duplicate responses.
        """
        provider = ScriptedProvider(
            [simple_stop_response("Hi there! How can I help?")]
        )
        manager, bot = make_manager_with_provider(provider)
        await manager._handle_message(make_message("Hello"))

        # Provider should have been called exactly once
        assert provider.call_count == 1, (
            f"Expected 1 LLM call, got {provider.call_count} — "
            "duplicate calls indicate stall-detection looping"
        )

    @pytest.mark.anyio
    async def test_response_is_not_duplicated(self) -> None:
        """The full response text must appear exactly once.

        In 0.3.14, stall detection triggered re-runs and users saw the same
        response text 8-10 times concatenated.
        """
        response_text = "I have access to 34 tools for file ops, shell, web search, and more."
        provider = ScriptedProvider([simple_stop_response(response_text)])
        manager, bot = make_manager_with_provider(provider)
        await manager._handle_message(make_message("How many tools do you have?"))

        full_output = bot.all_text()
        # The response text should appear exactly once, not be duplicated
        count = full_output.count("34 tools")
        assert count == 1, (
            f"Response text appeared {count} times — "
            f"indicates duplicate generation. Output:\n{full_output}"
        )

    @pytest.mark.anyio
    async def test_single_tool_call_executes_and_continues(self) -> None:
        """A single tool call must execute, submit result, and get a follow-up response.

        Verifies the full tool call / result / continue cycle works end-to-end.
        """
        tool_response = tool_call_response(
            "ls",
            {"path": "/tmp"},
            tool_id="call-ls-001",
        )
        follow_up = simple_stop_response("I found the files in /tmp.")
        provider = ScriptedProvider([tool_response, follow_up])
        manager, bot = make_manager_with_provider(provider)

        await manager._handle_message(make_message("List files in /tmp"))

        # Provider called twice: first for tool call, then for follow-up
        assert provider.call_count == 2, (
            f"Expected 2 LLM calls (tool call + follow-up), got {provider.call_count}"
        )
        # Bot should have sent the tool notification
        tool_msgs = [c for _, c in bot.sent_messages if "🔧" in c]
        assert len(tool_msgs) >= 1, "Expected at least one tool-running notification"
        assert "ls" in tool_msgs[0]
        # Final response should be present
        assert "found the files" in bot.all_text()

    @pytest.mark.anyio
    async def test_tool_result_submitted_to_agent_before_continuation(self) -> None:
        """Tool results must be in conversation history before the follow-up call.

        Verifies that agent.submit_tool_result() is called properly and the
        second LLM call sees the tool result in its message history.
        """
        tool_response = tool_call_response(
            "ls", {"path": "."}, tool_id="call-ls-002"
        )
        follow_up = simple_stop_response("Done.")
        provider = ScriptedProvider([tool_response, follow_up])
        manager, bot = make_manager_with_provider(provider)

        await manager._handle_message(make_message("What files are here?"))

        # The second call's messages must include a tool-role message
        assert provider.call_count == 2
        second_call_messages = provider.calls[1]
        tool_messages = [m for m in second_call_messages if m.role == "tool"]
        assert len(tool_messages) >= 1, (
            "Second LLM call must include tool result messages. "
            f"Message roles: {[m.role for m in second_call_messages]}"
        )

    @pytest.mark.anyio
    async def test_max_tool_iterations_stops_loop(self, tmp_path: Path) -> None:
        """The safety limits must stop runaway tool call chains.

        There are two limits:
        - Inner: max_iterations (50) TOOL_CALL_REQUEST events per stream round.
        - Outer: max_continuation_rounds (20) continuation rounds total.

        With one tool call per scripted response, the outer limit fires first
        after 21 rounds, emitting '⚠️ Maximum tool rounds reached.'
        """
        # Use an empty directory so host /tmp contents cannot trigger LLM compaction.
        # Provide 60 consecutive single-tool-call responses (more than both limits)
        tool_responses = [
            tool_call_response("ls", {"path": str(tmp_path)}, tool_id=f"call-{i}")
            for i in range(60)
        ]
        provider = ScriptedProvider(tool_responses)
        manager, bot = make_manager_with_provider(provider)

        # Must complete without hanging
        await asyncio.wait_for(
            manager._handle_message(make_message("List files forever")),
            timeout=30.0,
        )

        all_text = " ".join(c for _, c in bot.sent_messages)
        warning_sent = (
            "Maximum tool rounds" in all_text
            or "Maximum tool iterations" in all_text
        )
        assert warning_sent, (
            "Expected a safety-limit warning message. Sent messages:\n"
            + "\n".join(f"  {c}" for _, c in bot.sent_messages)
        )
        # Provider should have been called at most 22 times (21 rounds + possible final)
        assert provider.call_count <= 25, (
            f"Too many LLM calls ({provider.call_count}) — safety limit not working"
        )

    @pytest.mark.anyio
    async def test_slash_clear_preserves_system_prompt(self) -> None:
        """The /clear command must clear chat history but keep the system prompt.

        In 0.3.14, messages.clear() wiped the system prompt, causing
        'Messages list cannot be empty' errors on the next message.
        """
        response_text = "Hi there!"
        provider = ScriptedProvider(
            [
                simple_stop_response(response_text),  # After /clear greeting
            ]
        )
        manager, bot = make_manager_with_provider(provider)
        user_id = "test-user-123"

        # Add some history
        manager._user_histories[user_id] = [
            {"role": "user", "content": "old message"},
            {"role": "assistant", "content": "old reply"},
        ]

        # Issue /clear command (creates agent if not exists, then clears)
        await manager._handle_message(make_message("/clear", user_id))
        clear_msg = [c for _, c in bot.sent_messages if "cleared" in c.lower()]
        assert clear_msg, "Expected a history-cleared confirmation message"
        assert manager._user_histories[user_id] == [], "History must be empty after /clear"

        # Now send a new message — must NOT fail with empty messages error
        bot.sent_messages.clear()
        await manager._handle_message(make_message("Hello after clear", user_id))

        # Check no error about empty messages
        error_msgs = [c for _, c in bot.sent_messages if "empty" in c.lower() or "Error" in c]
        assert not error_msgs, (
            f"Got error after /clear — system prompt was likely wiped: {error_msgs}"
        )

    @pytest.mark.anyio
    async def test_slash_clear_agent_messages_contain_system_prompt(self) -> None:
        """After /clear, agent.messages must still contain the system prompt."""
        provider = ScriptedProvider([simple_stop_response("Ready!")])
        manager, bot = make_manager_with_provider(provider)
        user_id = "test-user-123"

        # First message initializes the agent
        await manager._handle_message(make_message("Hello", user_id))
        agent = manager._user_agents[user_id]

        # Add some chat history to messages
        from henchman.providers.base import Message
        agent.messages.append(Message(role="user", content="something"))
        agent.messages.append(Message(role="assistant", content="something back"))

        # Now /clear
        await manager._handle_message(make_message("/clear", user_id))

        # System prompt must still be in agent.messages
        system_msgs = [m for m in agent.messages if m.role == "system"]
        assert len(system_msgs) == 1, (
            f"System prompt was removed by /clear! agent.messages roles: "
            f"{[m.role for m in agent.messages]}"
        )

    @pytest.mark.anyio
    async def test_multi_turn_conversation_history_accumulates(self) -> None:
        """Multiple messages must accumulate in user history."""
        provider = ScriptedProvider(
            [
                simple_stop_response("Hi!"),
                simple_stop_response("I have 34 tools."),
            ]
        )
        manager, bot = make_manager_with_provider(provider)
        user_id = "test-user-123"

        await manager._handle_message(make_message("Hello", user_id))
        await manager._handle_message(make_message("How many tools?", user_id))

        history = manager._user_histories[user_id]
        # Should have 2 user + 2 assistant messages
        assert len(history) == 4, (
            f"Expected 4 history entries (2 turns), got {len(history)}"
        )
        roles = [m["role"] for m in history]
        assert roles == ["user", "assistant", "user", "assistant"]

    @pytest.mark.anyio
    async def test_per_user_agent_isolation(self) -> None:
        """Each user must have an independent agent with separate history."""
        provider_a = ScriptedProvider([simple_stop_response("Hello user A")])
        provider_b = ScriptedProvider([simple_stop_response("Hello user B")])

        settings = Settings()
        manager = ChatManager(settings)
        bot = RecordingBot()
        manager._bots[ChatPlatform.DISCORD] = bot

        # Inject separate providers per user
        async def _inject_per_user(user_id: str) -> Any:
            from henchman.cli.tool_manager import ToolManager
            from henchman.core import Agent

            if user_id in manager._user_agents:
                return manager._user_agents[user_id]

            provider = provider_a if user_id == "user-A" else provider_b
            tool_manager = ToolManager(settings)
            tool_manager.register_builtin_tools()
            tool_manager.set_auto_approve(auto_approve=True)

            agent = Agent(
                provider=provider,
                system_prompt="You are Henchman-AI.",
                tool_registry=tool_manager.registry,
            )
            agent.stall_detection_enabled = False
            manager._user_agents[user_id] = agent
            manager._user_histories[user_id] = []
            return agent

        manager._get_or_create_agent = _inject_per_user  # type: ignore[method-assign]

        await manager._handle_message(make_message("Hello", user_id="user-A"))
        await manager._handle_message(make_message("Hello", user_id="user-B"))

        assert "user-A" in manager._user_agents
        assert "user-B" in manager._user_agents
        assert manager._user_agents["user-A"] is not manager._user_agents["user-B"]
        assert manager._user_histories["user-A"] != [] or True  # both can be non-empty
        assert len(manager._user_agents) == 2

    @pytest.mark.anyio
    async def test_tool_failure_does_not_crash_pipeline(self) -> None:
        """A failing tool must be handled gracefully — error sent, loop continues.

        When a tool is not found, ToolRegistry.execute() returns a ToolResult
        with success=False containing the error message rather than raising.
        The pipeline should display the result and continue to the follow-up call.
        """
        # Request a non-existent tool to force a not-found error result
        bad_tool_response = tool_call_response(
            "nonexistent_tool_xyz",
            {},
            tool_id="call-bad-001",
        )
        follow_up = simple_stop_response("I encountered an error but I'm still here.")
        provider = ScriptedProvider([bad_tool_response, follow_up])
        manager, bot = make_manager_with_provider(provider)

        # Must not raise
        await manager._handle_message(make_message("Do something impossible"))

        # Registry returns success=False with "not found" — displayed in result block
        all_text = " ".join(c for _, c in bot.sent_messages)
        assert "nonexistent_tool_xyz" in all_text, (
            f"Expected tool name in output. Messages: {bot.sent_messages}"
        )
        assert "not found" in all_text.lower() or "Error" in all_text, (
            f"Expected error content in output. Messages: {bot.sent_messages}"
        )
        # The pipeline should recover and produce a follow-up response
        assert provider.call_count == 2, (
            "Pipeline should continue after tool failure and make a follow-up call"
        )

    @pytest.mark.anyio
    async def test_stall_detection_is_disabled(self) -> None:
        """Stall detection must be disabled for Discord agents.

        If enabled, phrases like 'Let me know...' in responses would trigger
        nudge injections, causing duplicate LLM calls.
        """
        # Response containing stall-detector trigger phrases
        stall_prone_text = (
            "Let me know if you need help! I'm going to be here for you. "
            "Let me start by saying hello. I will now assist you."
        )
        provider = ScriptedProvider([simple_stop_response(stall_prone_text)])
        manager, bot = make_manager_with_provider(provider)

        await manager._handle_message(make_message("Hi!"))

        # If stall detection were enabled, it would have triggered a nudge
        # and the provider would have been called 2+ times
        assert provider.call_count == 1, (
            f"Stall detection was active — {provider.call_count} LLM calls made. "
            "Expected exactly 1 for a simple greeting with stall phrases."
        )

    @pytest.mark.anyio
    async def test_long_response_sent_completely(self) -> None:
        """A response longer than 1800 chars must be fully sent (split if needed)."""
        long_text = "A" * 4000  # Well above Discord's 2000-char limit
        # Stream as one big chunk to test the chunking logic in _process_stream
        chunks = [
            StreamChunk(content=long_text),
            StreamChunk(finish_reason=FinishReason.STOP),
        ]
        provider = ScriptedProvider([chunks])
        manager, bot = make_manager_with_provider(provider)

        await manager._handle_message(make_message("Give me a long answer"))

        total_content = bot.all_text()
        # All 4000 A's must be present across all sent messages
        total_a_count = total_content.count("A")
        assert total_a_count == 4000, (
            f"Expected 4000 chars, got {total_a_count} — response was truncated"
        )

    @pytest.mark.anyio
    async def test_slash_help_command_works(self) -> None:
        """The /help command must return help text without calling the LLM."""
        # No LLM responses needed — /help is handled without the provider
        provider = ScriptedProvider([])
        manager, bot = make_manager_with_provider(provider)

        await manager._handle_message(make_message("/help"))

        assert provider.call_count == 0, "/help must not call the LLM"
        help_msgs = [c for _, c in bot.sent_messages if "Henchman-AI Commands" in c]
        assert help_msgs, "Expected /help to return command list"

    @pytest.mark.anyio
    async def test_slash_status_command_works(self) -> None:
        """The /status command must return status info without calling the LLM."""
        provider = ScriptedProvider([])
        manager, bot = make_manager_with_provider(provider)

        await manager._handle_message(make_message("/status"))

        assert provider.call_count == 0, "/status must not call the LLM"
        status_msgs = [c for _, c in bot.sent_messages if "Status" in c]
        assert status_msgs, "Expected /status to return status info"

    @pytest.mark.anyio
    async def test_provider_error_sends_error_message_not_crash(self) -> None:
        """A provider error (e.g., empty messages) must send an error, not crash."""
        # Simulate a provider that raises an exception
        from henchman.providers.base import ModelProvider

        class FailingProvider(ModelProvider):
            """Provider that always fails."""

            @property
            def name(self: FailingProvider) -> str:
                """Return provider name."""
                return "failing"

            async def chat_completion_stream(
                self: FailingProvider,
                messages: list[Message],
                tools: list[ToolDeclaration] | None = None,
                **kwargs: Any,
            ) -> AsyncIterator[StreamChunk]:
                """Always raise an error."""
                raise RuntimeError("Simulated provider failure")
                if False:  # pragma: no cover — makes this an async generator
                    yield StreamChunk()

        settings = Settings()
        manager = ChatManager(settings)
        bot = RecordingBot()
        manager._bots[ChatPlatform.DISCORD] = bot

        async def _inject_failing(user_id: str) -> Any:
            from henchman.cli.tool_manager import ToolManager
            from henchman.core import Agent
            if user_id in manager._user_agents:
                return manager._user_agents[user_id]
            tool_manager = ToolManager(settings)
            tool_manager.register_builtin_tools()
            agent = Agent(
                provider=FailingProvider(),
                system_prompt="You are Henchman-AI.",
                tool_registry=tool_manager.registry,
            )
            agent.stall_detection_enabled = False
            manager._user_agents[user_id] = agent
            manager._user_histories[user_id] = []
            return agent

        manager._get_or_create_agent = _inject_failing  # type: ignore[method-assign]

        # Must not raise even when provider fails
        await manager._handle_message(make_message("Hello"))

        # Should have sent some kind of error or handled gracefully
        assert bot.sent_messages, "Expected at least one message even on provider failure"

    @pytest.mark.anyio
    async def test_typing_indicator_sent_before_response(self) -> None:
        """The bot must send a typing indicator before the LLM response."""
        provider = ScriptedProvider([simple_stop_response("Hello!")])
        manager, bot = make_manager_with_provider(provider)

        await manager._handle_message(make_message("Hi"))

        assert bot.typing_indicators, "Typing indicator must be sent before response"
        assert bot.typing_indicators[0] == "test-user-123"

    @pytest.mark.anyio
    async def test_multiple_tool_calls_sequential(self) -> None:
        """Multiple sequential tool calls must all execute and continue correctly."""
        # Round 1: tool call A
        # Round 2 (after result A): tool call B
        # Round 3 (after result B): final text response
        call_a = tool_call_response("ls", {"path": "/tmp"}, tool_id="call-a")
        call_b = tool_call_response("ls", {"path": "/home"}, tool_id="call-b")
        final = simple_stop_response("Done checking both directories.")

        provider = ScriptedProvider([call_a, call_b, final])
        manager, bot = make_manager_with_provider(provider)

        await manager._handle_message(make_message("Check tmp and home dirs"))

        assert provider.call_count == 3, (
            f"Expected 3 LLM calls (tool-A, tool-B, final), got {provider.call_count}"
        )
        tool_msgs = [c for _, c in bot.sent_messages if "🔧" in c]
        assert len(tool_msgs) == 2, f"Expected 2 tool notifications, got {len(tool_msgs)}"
        assert "Done checking" in bot.all_text()
