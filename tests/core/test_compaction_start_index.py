"""Tests for start_index correction after compaction.

Verifies that Agent._apply_compaction_if_needed updates
turn.start_index so subsequent compaction cycles don't use a
stale offset that could split assistant+tool sequences across the
protected/unprotected boundary.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.core.agent import Agent
from henchman.providers.base import Message, ModelProvider, ToolCall


def _make_agent(max_tokens: int = 500) -> Agent:
    """Create an Agent with a low token budget for easy compaction."""
    provider = MagicMock(spec=ModelProvider)
    provider.default_model = "test-model"
    agent = Agent(provider=provider, max_tokens=max_tokens, summarize_dropped=False)
    return agent


def _long(text: str, repeat: int = 200) -> str:
    """Produce a string that takes many tokens."""
    return f"{text} " + "word " * repeat


class TestStartIndexUpdatedAfterCompaction:
    """Ensure turn.start_index stays in sync after compaction."""

    @pytest.mark.anyio
    async def test_start_index_decreases_after_simple_compaction(self) -> None:
        """After simple compaction drops old messages, start_index must shift."""
        agent = _make_agent(max_tokens=500)

        # Build a history that exceeds the budget.
        # System (kept) + several old user/assistant pairs + current turn.
        agent.messages = [
            Message(role="system", content="sys"),
            Message(role="user", content=_long("old1")),
            Message(role="assistant", content=_long("resp1")),
            Message(role="user", content=_long("old2")),
            Message(role="assistant", content=_long("resp2")),
            # ---- current turn starts at index 5 ----
            Message(role="user", content="current"),
            Message(
                role="assistant",
                content="plan",
                tool_calls=[ToolCall(id="tc_1", name="read_file", arguments={})],
            ),
            Message(role="tool", content="file contents", tool_call_id="tc_1"),
        ]
        agent.turn.start_index = 5  # current turn starts at index 5

        compacted = await agent._apply_compaction_if_needed()

        assert compacted, "compaction should have been triggered"
        # Protected messages (indices 5-7, 3 messages) must be at the end
        assert agent.turn.start_index == len(agent.messages) - 3
        # The tool sequence must still be intact and valid
        from henchman.utils.validation import is_valid_message_sequence

        assert is_valid_message_sequence(agent.messages)

    @pytest.mark.anyio
    async def test_start_index_correct_after_summarization_compaction(self) -> None:
        """After summarization compaction, start_index accounts for the summary msg."""
        agent = _make_agent(max_tokens=500)
        agent.summarize_dropped = True

        agent.messages = [
            Message(role="system", content="sys"),
            Message(role="user", content=_long("old1")),
            Message(role="assistant", content=_long("resp1")),
            Message(role="user", content=_long("old2")),
            Message(role="assistant", content=_long("resp2")),
            # current turn at index 5
            Message(role="user", content="current"),
            Message(role="assistant", content="ok"),
        ]
        agent.turn.start_index = 5

        # Mock the provider used for summarization so it doesn't hit a real API
        mock_provider = AsyncMock()

        async def mock_stream(*_a, **_kw):
            from henchman.providers.base import FinishReason, StreamChunk

            yield StreamChunk(content="summary of conversation", finish_reason=FinishReason.STOP)

        mock_provider.chat_completion_stream = mock_stream
        agent.provider = mock_provider

        compacted = await agent._apply_compaction_if_needed()

        assert compacted
        # 2 protected messages (user + assistant at indices 5,6)
        assert agent.turn.start_index == len(agent.messages) - 2

    @pytest.mark.anyio
    async def test_subsequent_compaction_uses_correct_start_index(self) -> None:
        """A second compaction must use the updated start_index, not the stale one."""
        agent = _make_agent(max_tokens=400)

        agent.messages = [
            Message(role="system", content="sys"),
            Message(role="user", content=_long("old")),
            Message(role="assistant", content=_long("resp")),
            # current turn at index 3
            Message(role="user", content="new input"),
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id="tc_A", name="delegate_task", arguments={})],
            ),
            Message(role="tool", content="delegation result", tool_call_id="tc_A"),
        ]
        agent.turn.start_index = 3  # current turn @ index 3

        # First compaction — drops old messages
        compacted = await agent._apply_compaction_if_needed()
        assert compacted
        first_start = agent.turn.start_index

        # Now grow the history again (simulating more tool iterations)
        for i in range(8):
            agent.messages.append(Message(role="user", content=_long(f"more_{i}")))
            agent.messages.append(Message(role="assistant", content=_long(f"ans_{i}")))

        # Second compaction with updated start_index
        agent.turn.start_index = first_start  # keep existing (shouldn't need manual reset)
        compacted2 = await agent._apply_compaction_if_needed()
        if compacted2:
            # start_index must still be valid
            assert 0 <= agent.turn.start_index <= len(agent.messages)

        from henchman.utils.validation import is_valid_message_sequence

        assert is_valid_message_sequence(agent.messages)

    @pytest.mark.anyio
    async def test_no_compaction_leaves_start_index_unchanged(self) -> None:
        """When no compaction is needed, start_index remains untouched."""
        agent = _make_agent(max_tokens=100000)

        agent.messages = [
            Message(role="system", content="sys"),
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi"),
        ]
        agent.turn.start_index = 1

        compacted = await agent._apply_compaction_if_needed()
        assert not compacted
        assert agent.turn.start_index == 1
