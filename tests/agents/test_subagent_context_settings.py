"""Dynamic conversations inherit the caller's complete context policy."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.agents.subagents import subagent_actor
from henchman.config.schema import Settings
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk


class RecordingProvider(ModelProvider):
    """A local scripted provider retaining actual request history."""

    name = "recording"

    def __init__(self) -> None:
        self.calls: list[list[Message]] = []

    async def chat_completion_stream(
        self, messages: list[Message], tools: Any = None, **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.calls.append(deepcopy(messages))
        yield StreamChunk(content="Completed review.", finish_reason=FinishReason.STOP)


async def test_dynamic_children_keep_context_policy_and_restored_history() -> None:
    provider = RecordingProvider()
    settings = Settings(context={
        "max_tokens": 32768, "compaction_threshold": 0, "auto_compact": False,
        "intelligent_context": True, "importance_threshold": 0.25,
        "cluster_similarity_threshold": 0.9, "adaptive_compression": False,
    })
    orch = Orchestrator(provider, settings=settings)
    # These standalone knobs are also part of the effective parent's policy.
    orch.tech_lead.summarize_dropped = False
    orch.tech_lead.max_protected_ratio = 0.6
    try:
        record = orch.subagents.spawn(
            "new task", role="child", system_prompt="child rules", tools=["invoke_subagent"],
        )
        child = orch.subagents._conversations[record.conversation_id].agent
        child.messages.extend([Message("user", "restored old task"),
                               Message("assistant", "restored old answer")])
        original = deepcopy(child.messages)
        expected = {
            "auto_compact": False, "intelligent_context": True, "importance_threshold": 0.25,
            "cluster_similarity_threshold": 0.9, "adaptive_compression": False,
            "summarize_dropped": False, "max_protected_ratio": 0.6,
            "max_tokens": 1, "context_window": 32768,
        }
        assert {name: getattr(child, name) for name in expected} == expected
        await asyncio.wait_for(orch.subagents.wait_for_notification(), 2)
        assert provider.calls == [[*original, Message("user", "new task")]]
        assert child.messages[:len(original)] == original

        # A nested conversation follows its immediate caller's live policy.
        child.importance_threshold = 0.4
        with subagent_actor(record.conversation_id):
            nested = orch.subagents.spawn(
                "nested task", role="nested", system_prompt="nested rules", tools=[],
            )
        grandchild = orch.subagents._conversations[nested.conversation_id].agent
        assert grandchild.auto_compact is False
        assert grandchild.importance_threshold == 0.4
        assert grandchild.summarize_dropped is False
        assert grandchild.max_tokens == 1
        with subagent_actor(record.conversation_id):
            await asyncio.wait_for(orch.subagents.wait_for_notification(), 2)
    finally:
        await orch.aclose()


@pytest.mark.parametrize("auto_compact", [False, True])
async def test_dynamic_child_uses_parent_hard_capacity(auto_compact: bool) -> None:
    provider = RecordingProvider()
    orch = Orchestrator(provider, settings=Settings(context={
        "max_tokens": 128, "compaction_threshold": 0.5, "auto_compact": auto_compact,
    }))
    try:
        record = orch.subagents.spawn(
            "task", role="child", system_prompt="child rules", tools=[],
        )
        child = orch.subagents._conversations[record.conversation_id].agent
        child.messages.extend([Message("user", "old task " * 300), Message("assistant", "answer")])
        await asyncio.wait_for(orch.subagents.wait_for_notification(), 2)
        if auto_compact:
            assert provider.calls == [[Message("system", "child rules"), Message("user", "task")]]
        else:
            assert not provider.calls
            assert "automatic compaction is disabled" in str(orch.subagents.get(record.conversation_id))
        assert child.messages[1].content == "old task " * 300
    finally:
        await orch.aclose()
