"""Whole requests fit estimates without sacrificing the current coding turn."""

from copy import deepcopy
from typing import Any

import pytest

from henchman.core.agent import Agent
from henchman.core.events import EventType
from henchman.providers.base import (
    ContextTooLargeError,
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.providers.request_budget import OutputBudget
from henchman.utils.validation import is_valid_message_sequence


class RecordingProvider(ModelProvider):
    """Deterministic accounting makes capacity boundaries explicit."""

    name = "recording"

    def __init__(self, output_tokens: int = 20) -> None:
        self.calls: list[dict[str, Any]] = []
        self.output_tokens = output_tokens

    def prepare_output_budget(self, default_max_tokens: int) -> OutputBudget:
        return OutputBudget(self.output_tokens, {"max_tokens": self.output_tokens})

    def estimate_input_tokens(self, messages, tools) -> int:
        return sum(len(m.content or "") + len(m.reasoning_content or "") for m in messages) + sum(
            len(t.description) for t in tools or []
        )

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.calls.append({"messages": list(messages), "tools": tools, **kwargs})
        yield StreamChunk(content="Done.", finish_reason=FinishReason.STOP)


def prepare(messages, *, tools=None, capacity=100, target=80, start=1):
    from henchman.core.request_budget import prepare_request

    return prepare_request(
        RecordingProvider(), messages, tools or [], context_window=capacity,
        conversation_limit=target, protect_from_index=start,
    )


@pytest.mark.parametrize("large_part", ["system", "user", "tools", "reasoning"])
def test_mandatory_request_cannot_be_silently_truncated(large_part: str) -> None:
    messages = [Message("system", "Rules"), Message("user", "Task")]
    tools = [ToolDeclaration("read", "Read", {})]
    if large_part == "tools":
        tools[0].description = "x" * 100
    elif large_part == "reasoning":
        messages.append(Message("assistant", "", reasoning_content="x" * 100))
    else:
        messages[0 if large_part == "system" else 1].content = "x" * 100
    original = deepcopy(messages)
    with pytest.raises(ContextTooLargeError, match="context window"):
        prepare(messages, tools=tools)
    assert messages == original


def test_old_tool_batches_pruned_atomically_without_mutating_history() -> None:
    messages = [
        Message("system", "Rules"), Message("user", "old" * 30),
        Message("assistant", "old", tool_calls=[ToolCall("a", "read", {}), ToolCall("b", "read", {})]),
        Message("tool", "a" * 20, tool_call_id="a"),
        Message("tool", "b" * 20, tool_call_id="b"),
        Message("user", "New task"),
    ]
    original = deepcopy(messages)
    request = prepare(messages, tools=[ToolDeclaration("read", "schema" * 5, {})], start=5)
    assert request.compacted
    assert request.messages == [messages[0], messages[-1]]
    assert is_valid_message_sequence(request.messages)
    assert request.estimated_input_tokens + request.output_tokens <= 100
    assert request.request_options == {"max_tokens": 20}
    assert messages == original


def test_conversation_target_is_soft_for_complete_current_turn() -> None:
    messages = [Message("system", "rules"), Message("user", "task" * 10)]
    request = prepare(messages, target=1)
    assert request.messages == messages
    assert not request.compacted


def test_stall_nudge_does_not_make_original_task_disposable() -> None:
    messages = [Message("system", "Rules"), Message("user", "x" * 90), Message("user", "Continue")]
    with pytest.raises(ContextTooLargeError):
        prepare(messages)


@pytest.mark.asyncio
async def test_oversized_agent_fails_before_any_model_call() -> None:
    provider = RecordingProvider()
    agent = Agent(provider, system_prompt="x" * 100, context_window=100, max_tokens=80)
    events = [event async for event in agent.run("Task")]
    assert not provider.calls
    assert any(event.type == EventType.ERROR and "context window" in str(event.data) for event in events)
    assert agent.messages[0].content == "x" * 100


@pytest.mark.asyncio
async def test_agent_uses_reserved_output_cap_and_retains_original_history() -> None:
    provider = RecordingProvider()
    agent = Agent(provider, system_prompt="Rules", context_window=100, max_tokens=80)
    agent.messages.extend([Message("user", "old" * 100), Message("assistant", "Old answer")])
    original = deepcopy(agent.messages)
    events = [event async for event in agent.run("New task")]
    assert not any(event.type == EventType.ERROR for event in events)
    assert len(provider.calls) == 1
    assert provider.calls[0]["max_tokens"] == 20
    assert provider.calls[0]["messages"] == [original[0], Message("user", "New task")]
    assert agent.messages[:len(original)] == original


@pytest.mark.asyncio
async def test_unconfigured_capacity_keeps_legacy_request_options() -> None:
    provider = RecordingProvider()
    agent = Agent(provider, max_tokens=100)
    _ = [event async for event in agent.run("Task")]
    assert "max_tokens" not in provider.calls[0]


@pytest.mark.asyncio
async def test_tool_scope_is_recounted_on_each_continuation(monkeypatch) -> None:
    provider = RecordingProvider()
    agent = Agent(provider, context_window=100, max_tokens=80)
    _ = [event async for event in agent.run("Task")]
    assert len(provider.calls) == 1
    monkeypatch.setattr(agent.tool_registry, "get_declarations", lambda: [
        ToolDeclaration("new_tool", "x" * 100, {}),
    ])
    events = [event async for event in agent.continue_with_tool_results()]
    assert len(provider.calls) == 1
    assert any(event.type == EventType.ERROR for event in events)


@pytest.mark.parametrize("invalid", [True, 0, -1, 1.5, "700000"])
def test_invalid_capacity_leaves_both_agent_limits_unchanged(invalid) -> None:
    agent = Agent(RecordingProvider(), context_window=100, max_tokens=80)
    with pytest.raises(ValueError, match="positive integer"):
        agent.set_context_limit(60, context_window=invalid)
    assert agent.max_tokens == 80
    assert agent.context_window == 100


def test_current_tool_results_are_never_dropped_to_fit() -> None:
    messages = [
        Message("system", "Rules"), Message("user", "Task"),
        Message("assistant", "", tool_calls=[ToolCall("current", "read", {})]),
        Message("tool", "x" * 90, tool_call_id="current"),
    ]
    with pytest.raises(ContextTooLargeError):
        prepare(messages)
    assert messages[-1].content == "x" * 90


def test_default_output_reservation_is_sent_to_unconfigured_provider() -> None:
    from henchman.core.request_budget import prepare_request

    class DefaultCapProvider(RecordingProvider):
        prepare_output_budget = ModelProvider.prepare_output_budget

    for capacity, expected in [(100, 25), (32768, 4096)]:
        request = prepare_request(
            DefaultCapProvider(), [Message("user", "Task")], [],
            context_window=capacity, conversation_limit=capacity, protect_from_index=0,
        )
        assert request.output_tokens == expected
        assert request.request_options == {"max_tokens": expected}
