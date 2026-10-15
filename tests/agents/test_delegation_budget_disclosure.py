"""Specialists see current runtime budgets before their first provider request."""

from collections.abc import AsyncIterator
from copy import deepcopy

import pytest

from henchman.agents.delegation import DelegationRunner
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_types import DelegationParams
from henchman.config.schema import Settings
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk


class CapturingProvider(ModelProvider):
    name = "budget-disclosure-test"

    def __init__(self) -> None:
        self.requests: list[list[Message]] = []

    async def chat_completion_stream(
        self, messages, tools=None, **kwargs
    ) -> AsyncIterator[StreamChunk]:
        self.requests.append(deepcopy(messages))
        yield StreamChunk(
            content="The requested explanation is complete.", finish_reason=FinishReason.STOP
        )


async def delegate(orch: Orchestrator, task: str = "Explain the existing implementation") -> None:
    _ = [
        event
        async for event in orch.delegation_runner.run_delegation(
            DelegationParams(
                target_role="explorer",
                task=task,
                brief={"completion_requirement": "response"},
                depth=1,
            )
        )
    ]


def starting_input(provider: CapturingProvider) -> str:
    return (
        next(message.content for message in provider.requests[-1] if message.role == "user") or ""
    )


async def test_first_specialist_request_discloses_distinct_runtime_limits() -> None:
    provider = CapturingProvider()
    orch = Orchestrator(default_provider=provider, settings=Settings(context={"max_tokens": 32768}))
    orch.settings.agents.max_delegation_turns = 12
    agent = orch.pool.get_agent("explorer")
    agent.base_tool_iterations = 3
    agent.set_context_limit(12288, context_window=16384)
    original_system = [deepcopy(message) for message in agent.messages if message.role == "system"]

    await delegate(orch)

    text = starting_input(provider)
    assert "Tool-call stop threshold: 12" in text
    assert "individual requested calls" in text
    assert "including failed calls" in text
    assert "checked after the entire batch" in text
    assert "before another model response" in text
    assert "Tool-batch limit: 3" in text
    assert "final answer without tools" in text
    assert "Request context capacity: 16384 tokens" in text
    assert "Conversation compaction target: 12288 tokens" in text
    assert "not an exact remaining-token count" in text
    assert [message for message in agent.messages if message.role == "system"] == original_system
    assert agent.current_turn_messages[0].content == text


async def test_cached_agent_gets_fresh_limits_once_for_each_delegation() -> None:
    provider = CapturingProvider()
    orch = Orchestrator(default_provider=provider, settings=Settings(context={"max_tokens": 32768}))
    agent = orch.pool.get_agent("explorer")
    orch.settings.agents.max_delegation_turns = 12
    agent.base_tool_iterations = 3
    await delegate(orch, "First explanation")

    orch.settings.agents.max_delegation_turns = 9
    agent.base_tool_iterations = 2
    agent.set_context_limit(24000, context_window=32000)
    await delegate(orch, "Second explanation")

    text = starting_input(provider)
    assert orch.pool.get_agent("explorer") is agent
    assert text.count("## Runtime Limits") == 1
    assert "Tool-call stop threshold: 9" in text
    assert "Tool-call stop threshold: 12" not in text
    assert "Tool-batch limit: 2" in text
    assert "Request context capacity: 32000 tokens" in text
    assert "Conversation compaction target: 24000 tokens" in text
    assert "First explanation" not in text


@pytest.mark.parametrize("call_limit", [0, -1])
async def test_low_level_disabled_call_limit_and_zero_batches_are_distinct(call_limit: int) -> None:
    provider = CapturingProvider()
    orch = Orchestrator(default_provider=provider, settings=Settings(context={"max_tokens": 32768}))
    # Low-level callers can disable this cap; public Settings requires >=1.
    orch.settings.agents = orch.settings.agents.model_copy(
        update={"max_delegation_turns": call_limit}
    )
    agent = orch.pool.get_agent("explorer")
    agent.base_tool_iterations = 0
    agent.context_window = None
    await delegate(orch)
    text = starting_input(provider)
    assert "Tool-call stop threshold: disabled" in text
    assert "Tool-batch limit: 0" in text
    assert "no tool batch can execute" in text
    assert "Request context capacity: not explicitly configured" in text


def test_static_delegation_brief_is_unchanged() -> None:
    assert DelegationRunner._assemble_delegation_input("Explain", None) == "## Task\nExplain"
