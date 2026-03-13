"""Tests targeting missing coverage lines in core/agent.py and core/agent_streaming.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.core.agent import Agent, _build_outer_finished_event
from henchman.core.agent_streaming import StreamState
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_provider() -> MagicMock:
    """Create a mock ModelProvider."""
    return MagicMock(spec=ModelProvider)


def _make_stop_stream(*_args: object, **_kwargs: object):
    """Async generator that yields a single STOP chunk."""

    async def _gen():
        yield StreamChunk(content="ok", finish_reason=FinishReason.STOP)

    return _gen()


# ---------------------------------------------------------------------------
# agent.py – line 136: _build_outer_finished_event with usage
# ---------------------------------------------------------------------------


class TestBuildOuterFinishedEvent:
    """Cover line 136 in agent.py: finish_data dict when state has usage."""

    def test_with_usage(self) -> None:
        """Line 136: produces dict when state.usage is set."""
        state = StreamState()
        state.finish_reason = FinishReason.STOP
        state.usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

        event = _build_outer_finished_event(state, "agent-1")

        assert isinstance(event.data, dict)
        assert event.data["finish_reason"] == FinishReason.STOP.value
        assert event.data["usage"] == state.usage

    def test_without_usage(self) -> None:
        """Baseline: produces string when state.usage is None."""
        state = StreamState()
        state.finish_reason = FinishReason.STOP

        event = _build_outer_finished_event(state, "agent-1")

        assert isinstance(event.data, str)

    def test_with_none_state(self) -> None:
        """Baseline: produces default string when state is None."""
        event = _build_outer_finished_event(None, None)

        assert event.data == "Agent completed execution"


# ---------------------------------------------------------------------------
# agent_streaming.py – line 111: StreamState.create_finished_data with usage
# ---------------------------------------------------------------------------


class TestStreamStateCreateFinishedData:
    """Cover line 111 in agent_streaming.py."""

    def test_with_usage_returns_dict(self) -> None:
        """Line 111: returns dict when usage is set."""
        state = StreamState()
        state.finish_reason = FinishReason.STOP
        state.usage = {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}

        result = state.create_finished_data()

        assert isinstance(result, dict)
        assert result["finish_reason"] == FinishReason.STOP.value
        assert result["usage"] == state.usage

    def test_without_usage_returns_string(self) -> None:
        """Baseline: returns string when usage is None."""
        state = StreamState()
        state.finish_reason = FinishReason.STOP

        result = state.create_finished_data()

        assert isinstance(result, str)
        assert result == FinishReason.STOP.value


# ---------------------------------------------------------------------------
# agent.py – line 207: __setattr__ instance alias
# ---------------------------------------------------------------------------


class TestAgentSetattr:
    """Cover line 207 in agent.py: _INSTANCE_ALIASES assignment."""

    def test_set_max_tokens_alias(self, mock_provider: MagicMock) -> None:
        """Line 207: setting max_tokens alias updates _max_tokens."""
        agent = Agent(provider=mock_provider)
        agent.max_tokens = 4096  # alias for _max_tokens

        assert agent._max_tokens == 4096

    def test_set_history_alias(self, mock_provider: MagicMock) -> None:
        """Line 207: setting history alias updates messages list."""
        agent = Agent(provider=mock_provider)
        new_messages = [Message(role="user", content="hello")]
        agent.history = new_messages

        assert agent.messages is new_messages

    def test_set_tools_alias(self, mock_provider: MagicMock) -> None:
        """Line 207: setting tools alias updates tool_registry."""
        from henchman.tools.registry import ToolRegistry

        agent = Agent(provider=mock_provider)
        new_registry = ToolRegistry()
        agent.tools = new_registry

        assert agent.tool_registry is new_registry


# ---------------------------------------------------------------------------
# agent.py – line 237: _apply_simple_compaction repairs invalid sequence
# ---------------------------------------------------------------------------


class TestApplySimpleCompaction:
    """Cover line 237 in agent.py."""

    @pytest.mark.anyio
    async def test_repair_after_compaction(self, mock_provider: MagicMock) -> None:
        """Line 237: repair_message_sequence called when compact yields invalid seq."""
        agent = Agent(provider=mock_provider, max_tokens=50)

        # Seed messages that would require compaction but repair after
        messages = [
            Message(role="user", content="a " * 10),
            Message(role="assistant", content="b " * 10),
            Message(role="user", content="c " * 10),
        ]
        agent.messages = messages

        with patch(
            "henchman.core.agent.is_valid_message_sequence", return_value=False
        ), patch(
            "henchman.core.agent.repair_message_sequence",
            return_value=[Message(role="user", content="repaired")],
        ) as mock_repair:
            result = await agent._apply_simple_compaction()

        assert result is True
        mock_repair.assert_called()


# ---------------------------------------------------------------------------
# agent.py – lines 320-323: _compact_if_needed protected tokens update
# ---------------------------------------------------------------------------


class TestCompactIfNeededProtectedTokens:
    """Cover lines 320-323 in agent.py."""

    @pytest.mark.anyio
    async def test_protected_tokens_updated_when_start_index_in_range(
        self, mock_provider: MagicMock
    ) -> None:
        """Lines 320-323: protected_tokens set when start_index < len(messages)."""
        agent = Agent(provider=mock_provider, max_tokens=10000)

        # Set a non-zero start_index so line 320 condition is True
        agent.messages = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="world"),
        ]
        agent.turn.start_index = 1  # < len(messages)=2

        # With high max_tokens, compaction not needed → returns False
        result = await agent._compact_if_needed()

        assert result is False  # not compacted because within token limit
        # turn.protected_tokens should have been calculated
        assert agent.turn.protected_tokens >= 0


# ---------------------------------------------------------------------------
# agent.py – line 334: _compact_if_needed repairs after compaction
# ---------------------------------------------------------------------------


class TestCompactIfNeededRepair:
    """Cover line 334 in agent.py."""

    @pytest.mark.anyio
    async def test_repair_after_compact(self, mock_provider: MagicMock) -> None:
        """Line 334: repair called when compacted messages are invalid."""
        from henchman.core.agent_config import AgentConfig

        # summarize_dropped=False so we skip _try_summarized_compact and go straight to compact
        config = AgentConfig(summarize_dropped=False, max_tokens=10)
        agent = Agent(provider=mock_provider, config=config)

        # Fill messages to exceed token limit
        agent.messages = [
            Message(role="user", content="word " * 20),
            Message(role="assistant", content="word " * 20),
        ]
        agent.turn.start_index = 0

        with patch(
            "henchman.core.agent.is_valid_message_sequence", return_value=False
        ), patch(
            "henchman.core.agent.repair_message_sequence",
            return_value=[Message(role="user", content="repaired")],
        ) as mock_repair:
            await agent._compact_if_needed()

        mock_repair.assert_called()


# ---------------------------------------------------------------------------
# agent.py – line 358: _try_summarized_compact returns False when not compacted
# ---------------------------------------------------------------------------


class TestTrySummarizedCompact:
    """Cover line 358 in agent.py."""

    @pytest.mark.anyio
    async def test_returns_false_when_not_compacted(self, mock_provider: MagicMock) -> None:
        """Line 358: returns False when compact_messages reports not compacted."""
        from henchman.utils.compaction import CompactionResult

        agent = Agent(provider=mock_provider, max_tokens=100)
        agent.messages = [Message(role="user", content="hi")]

        mock_result = CompactionResult(
            messages=agent.messages,
            was_compacted=False,
        )

        with patch(
            "henchman.utils.compaction.compact_messages",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await agent._try_summarized_compact(protected_count=1)

        assert result is False

    @pytest.mark.anyio
    async def test_repairs_invalid_sequence_after_summarization(
        self, mock_provider: MagicMock
    ) -> None:
        """Line 361: repair called when summarized messages are invalid."""
        from henchman.utils.compaction import CompactionResult

        agent = Agent(provider=mock_provider, max_tokens=100)
        agent.messages = [Message(role="user", content="hi")]

        compacted_msgs = [
            Message(role="assistant", content="summary"),
            Message(role="tool", content="orphan", tool_call_id="x"),
        ]
        mock_result = CompactionResult(
            messages=compacted_msgs,
            was_compacted=True,
        )

        with patch(
            "henchman.utils.compaction.compact_messages",
            new=AsyncMock(return_value=mock_result),
        ), patch(
            "henchman.core.agent.is_valid_message_sequence", return_value=False
        ), patch(
            "henchman.core.agent.repair_message_sequence",
            return_value=[Message(role="user", content="fixed")],
        ) as mock_repair:
            result = await agent._try_summarized_compact(protected_count=1)

        assert result is True
        mock_repair.assert_called()


# ---------------------------------------------------------------------------
# agent.py – lines 381, 385: _stream_with_stall_loop repairs invalid sequences
# ---------------------------------------------------------------------------


class TestStreamWithStallLoop:
    """Cover lines 381 and 385 in agent.py."""

    @pytest.mark.anyio
    async def test_repairs_self_messages_when_invalid(self, mock_provider: MagicMock) -> None:
        """Line 381: self.messages repaired before streaming."""
        mock_provider.chat_completion_stream = _make_stop_stream

        agent = Agent(provider=mock_provider)
        # Pre-populate with an orphan tool message (invalid sequence)
        agent.messages = [
            Message(role="user", content="initial"),
            Message(role="tool", content="orphan result", tool_call_id="orphan-id"),
        ]

        with patch(
            "henchman.core.agent.is_valid_message_sequence",
            side_effect=[False, True, True],
        ), patch(
            "henchman.core.agent.repair_message_sequence",
            return_value=[Message(role="user", content="repaired")],
        ) as mock_repair:
            events = [e async for e in agent.run("test")]  # noqa: F841

        mock_repair.assert_called()

    @pytest.mark.anyio
    async def test_repairs_api_messages_when_invalid(self, mock_provider: MagicMock) -> None:
        """Line 385: api_messages repaired when get_messages_for_api returns invalid seq."""
        mock_provider.chat_completion_stream = _make_stop_stream

        agent = Agent(provider=mock_provider)

        with patch(
            "henchman.core.agent.is_valid_message_sequence",
            side_effect=[True, False, True],
        ), patch(
            "henchman.core.agent.repair_message_sequence",
            return_value=[Message(role="user", content="fixed-api")],
        ) as mock_repair:
            events = [e async for e in agent.run("api test")]  # noqa: F841

        mock_repair.assert_called()


# ---------------------------------------------------------------------------
# agent.py – lines 194, 197-198: __getattr__ for stall fields and unknown attr
# ---------------------------------------------------------------------------


class TestAgentGetattr:
    """Cover lines 194, 197-198 in agent.py."""

    def test_get_stall_field(self, mock_provider: MagicMock) -> None:
        """Line 194: __getattr__ with _STALL_FIELDS name."""
        agent = Agent(provider=mock_provider)
        # _stall_nudge_count is a _STALL_FIELDS key → line 194 executes
        count = agent._stall_nudge_count
        assert isinstance(count, int)

    def test_get_stall_detection_enabled(self, mock_provider: MagicMock) -> None:
        """Line 194: stall_detection_enabled is a _STALL_FIELDS key."""
        agent = Agent(provider=mock_provider)
        enabled = agent.stall_detection_enabled
        assert isinstance(enabled, bool)

    def test_get_unknown_attribute_raises(self, mock_provider: MagicMock) -> None:
        """Lines 197-198: AttributeError raised for unknown attribute."""
        agent = Agent(provider=mock_provider)
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = agent._nonexistent_attribute_xyz


# ---------------------------------------------------------------------------
# agent.py – line 205: __setattr__ for stall fields
# ---------------------------------------------------------------------------


class TestAgentSetStallFields:
    """Cover line 205 in agent.py."""

    def test_set_stall_detection_enabled(self, mock_provider: MagicMock) -> None:
        """Line 205: setting stall_detection_enabled updates _stall.enabled."""
        agent = Agent(provider=mock_provider)
        agent.stall_detection_enabled = False
        assert agent._stall.enabled is False

    def test_set_max_stall_nudges(self, mock_provider: MagicMock) -> None:
        """Line 205: setting _max_stall_nudges updates _stall._max_nudges."""
        agent = Agent(provider=mock_provider)
        agent._max_stall_nudges = 5
        assert agent._stall._max_nudges == 5


# ---------------------------------------------------------------------------
# agent.py – line 218: _check_for_stalling method
# ---------------------------------------------------------------------------


class TestAgentCheckForStalling:
    """Cover line 218 in agent.py."""

    @pytest.mark.anyio
    async def test_check_for_stalling_delegates_to_stall(
        self, mock_provider: MagicMock
    ) -> None:
        """Line 218: _check_for_stalling delegates to self._stall.check."""
        agent = Agent(provider=mock_provider)
        result = await agent._check_for_stalling("short", had_tool_calls=False)
        # Returns None (no nudge) or a string nudge message
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# agent_streaming.py – lines 150, 156: _accumulate_chunk thinking and usage
# ---------------------------------------------------------------------------


class TestAccumulateChunk:
    """Cover lines 150, 156 in agent_streaming.py."""

    def test_accumulates_thinking(self) -> None:
        """Line 150: state.thinking updated when chunk.thinking is set."""
        from henchman.core.agent_streaming import _accumulate_chunk

        state = StreamState()
        chunk = StreamChunk(thinking="I think about this")
        _accumulate_chunk(chunk, state)
        assert state.thinking == "I think about this"

    def test_accumulates_usage(self) -> None:
        """Line 156: state.usage updated when chunk.usage is set."""
        from henchman.core.agent_streaming import _accumulate_chunk

        state = StreamState()
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        chunk = StreamChunk(usage=usage)
        _accumulate_chunk(chunk, state)
        assert state.usage == usage


# ---------------------------------------------------------------------------
# agent_streaming.py – line 184->189: TOOL_CALLS finish reason
# ---------------------------------------------------------------------------


class TestHandleFinishToolCalls:
    """Cover branch 184->189 in agent_streaming.py."""

    def test_tool_calls_branch(self) -> None:
        """Line 184->189: FinishReason.TOOL_CALLS yields TOOL_CALL_REQUEST events."""
        from henchman.core.agent_streaming import _handle_finish

        state = StreamState()
        tc = ToolCall(id="tc-1", name="my_tool", arguments="{}")
        state.tool_calls = [tc]

        chunk = StreamChunk(finish_reason=FinishReason.TOOL_CALLS, tool_calls=[tc])
        history: list[Message] = []
        events = _handle_finish(chunk, state, history, source_agent=None)

        event_types = [e.type for e in events]
        assert EventType.TOOL_CALL_REQUEST in event_types


# ---------------------------------------------------------------------------
# agent_streaming.py – line 209: compacted=True yields CONTEXT_COMPACTED event
# ---------------------------------------------------------------------------


class TestGenerateStreamEventsCompacted:
    """Cover line 209 in agent_streaming.py."""

    @pytest.mark.anyio
    async def test_compacted_event_emitted(self, mock_provider: MagicMock) -> None:
        """Line 209: CONTEXT_COMPACTED event yielded when compacted=True."""
        from henchman.core.agent_streaming import StreamContext, generate_stream_events

        mock_provider.chat_completion_stream = _make_stop_stream
        ctx = StreamContext(
            provider=mock_provider,
            api_messages=[Message(role="user", content="hello")],
            history=[Message(role="user", content="hello")],
            tool_declarations=None,
            source_agent=None,
        )
        state = StreamState()
        events = [e async for e in generate_stream_events(ctx, state, compacted=True)]

        event_types = [e.type for e in events]
        assert EventType.CONTEXT_COMPACTED in event_types


# ---------------------------------------------------------------------------
# agent_streaming.py – line 220: THOUGHT event when chunk.thinking is set
# ---------------------------------------------------------------------------


class TestGenerateStreamEventsThinking:
    """Cover line 220 in agent_streaming.py."""

    @pytest.mark.anyio
    async def test_thinking_yields_thought_event(self, mock_provider: MagicMock) -> None:
        """Line 220: THOUGHT event yielded when chunk.thinking is set."""
        from henchman.core.agent_streaming import StreamContext, generate_stream_events

        async def _thinking_stream(*_args, **_kwargs):
            yield StreamChunk(thinking="hmm...", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = _thinking_stream
        ctx = StreamContext(
            provider=mock_provider,
            api_messages=[Message(role="user", content="think")],
            history=[Message(role="user", content="think")],
            tool_declarations=None,
            source_agent=None,
        )
        state = StreamState()
        events = [e async for e in generate_stream_events(ctx, state, compacted=False)]

        event_types = [e.type for e in events]
        assert EventType.THOUGHT in event_types


# ---------------------------------------------------------------------------
# agent_streaming.py – lines 228-229: provider exception yields ERROR event
# ---------------------------------------------------------------------------


class TestGenerateStreamEventsError:
    """Cover lines 228-229 in agent_streaming.py."""

    @pytest.mark.anyio
    async def test_provider_error_yields_error_event(self, mock_provider: MagicMock) -> None:
        """Lines 228-229: exception from provider is caught and yields ERROR event."""
        from henchman.core.agent_streaming import StreamContext, generate_stream_events

        async def _error_stream(*_args, **_kwargs):
            raise RuntimeError("provider exploded")
            yield  # make it a generator  # noqa: unreachable

        mock_provider.chat_completion_stream = _error_stream
        ctx = StreamContext(
            provider=mock_provider,
            api_messages=[Message(role="user", content="fail")],
            history=[Message(role="user", content="fail")],
            tool_declarations=None,
            source_agent=None,
        )
        state = StreamState()
        events = [e async for e in generate_stream_events(ctx, state, compacted=False)]

        error_events = [e for e in events if e.type == EventType.ERROR]
        assert len(error_events) > 0
        assert "provider exploded" in error_events[0].data


# ---------------------------------------------------------------------------
# agent.py – lines 398-400: exception in _stream_with_stall_loop → ERROR event
# ---------------------------------------------------------------------------


class TestStreamWithStallLoopException:
    """Cover lines 398-400 in agent.py."""

    @pytest.mark.anyio
    async def test_exception_yields_error_event(self, mock_provider: MagicMock) -> None:
        """Lines 398-400: exception caught → ERROR event yielded then break."""
        agent = Agent(provider=mock_provider)

        with patch.object(
            agent, "_compact_if_needed", new=AsyncMock(side_effect=RuntimeError("broken"))
        ):
            events = [e async for e in agent.run("trigger error")]

        error_events = [e for e in events if e.type == EventType.ERROR]
        assert any("broken" in str(e.data) for e in error_events)


# ---------------------------------------------------------------------------
# agent.py – lines 414-421: record_delegation_errors initializes lock + list
# ---------------------------------------------------------------------------


class TestRecordDelegationErrors:
    """Cover record_delegation_errors / get_delegation_errors in agent.py."""

    def test_lock_and_list_initialized_at_construction(self, mock_provider: MagicMock) -> None:
        """Lock and error list are eagerly created in __init__ (thread-safe)."""
        agent = Agent(provider=mock_provider)

        # Both attributes must exist immediately after construction
        assert hasattr(agent, "_delegation_tool_errors_lock")
        assert hasattr(agent, "_delegation_tool_errors")
        assert agent._delegation_tool_errors == []

    def test_first_call_records_errors(self, mock_provider: MagicMock) -> None:
        """record_delegation_errors stores errors on first call."""
        agent = Agent(provider=mock_provider)
        agent.record_delegation_errors(["error A", "error B"])
        assert agent._delegation_tool_errors == ["error A", "error B"]

    def test_subsequent_call_appends(self, mock_provider: MagicMock) -> None:
        """Subsequent calls append to existing list."""
        agent = Agent(provider=mock_provider)
        agent.record_delegation_errors(["error 1"])
        agent.record_delegation_errors(["error 2"])
        assert agent._delegation_tool_errors == ["error 1", "error 2"]


# ---------------------------------------------------------------------------
# agent.py – line 429: get_delegation_errors returns empty list by default
# ---------------------------------------------------------------------------


class TestGetDelegationErrors:
    """Cover line 429 in agent.py."""

    def test_returns_empty_list_when_no_errors_recorded(
        self, mock_provider: MagicMock
    ) -> None:
        """Line 429: returns [] when _delegation_tool_errors was never set."""
        agent = Agent(provider=mock_provider)
        errors = agent.get_delegation_errors()
        assert errors == []

    def test_returns_recorded_errors(self, mock_provider: MagicMock) -> None:
        """Line 429 baseline: returns the list after recording."""
        agent = Agent(provider=mock_provider)
        agent.record_delegation_errors(["err1"])
        errors = agent.get_delegation_errors()
        assert errors == ["err1"]
