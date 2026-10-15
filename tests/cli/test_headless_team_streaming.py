"""Nested team progress reaches a consumer before the specialist finishes."""

import asyncio
from types import SimpleNamespace

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.app import _run_headless_json_mode
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.utils.validation import validate_message_sequence


class HeldSpecialistProvider(ModelProvider):
    name = "held-specialist"

    def __init__(self) -> None:
        self.calls = 0
        self.release = asyncio.Event()
        self.closed = asyncio.Event()

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.calls += 1
        if self.calls == 1:
            yield StreamChunk(tool_calls=[ToolCall("research", "delegate_task", {
                "agent": "explorer", "task": "Explain the supplied task",
                "completion_requirement": "response",
            })], finish_reason=FinishReason.TOOL_CALLS)
        elif self.calls == 2:
            try:
                yield StreamChunk(content="Specialist progress is visible")
                await self.release.wait()
                yield StreamChunk(content=" and research finished.", finish_reason=FinishReason.STOP)
            finally:
                self.closed.set()
        else:
            yield StreamChunk(content="Research received.", finish_reason=FinishReason.STOP)


async def test_headless_renders_child_progress_before_child_finishes() -> None:
    provider = HeldSpecialistProvider()
    orch = Orchestrator(default_provider=provider)
    rendered = asyncio.Event()
    events = []

    def render(event):
        events.append(event)
        if event.type == EventType.CONTENT and event.source_agent == "explorer":
            rendered.set()

    task = asyncio.create_task(_run_headless_json_mode(
        SimpleNamespace(orchestrator=orch), "Research the supplied task", render,
    ))
    try:
        await asyncio.wait_for(rendered.wait(), 2)
        assert not task.done()
        assert not provider.closed.is_set()
        assert provider.calls == 2
        provider.release.set()
        assert await asyncio.wait_for(task, 2)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert provider.closed.is_set()
    assert [event.type for event in events].count(EventType.FINISHED) == 1


async def test_renderer_failure_closes_active_child_without_later_work() -> None:
    provider = HeldSpecialistProvider()
    orch = Orchestrator(default_provider=provider)
    events = []

    def broken_renderer(event):
        events.append(event)
        if event.type == EventType.CONTENT and event.source_agent == "explorer":
            raise RuntimeError("Consumer disconnected")

    async with asyncio.timeout(2):
        with pytest.raises(RuntimeError, match="Consumer disconnected"):
            await _run_headless_json_mode(
                SimpleNamespace(orchestrator=orch), "Research the supplied task", broken_renderer,
            )
    assert provider.closed.is_set()
    assert provider.calls == 2
    assert orch.ledger.delegations[0].status.value == "failed"
    assert "interrupt" in orch.ledger.delegations[0].summary.lower()
    assert not any(event.type == EventType.FINISHED for event in events)
    validate_message_sequence(orch.tech_lead.messages)
    validate_message_sequence(orch.pool.get_agent("explorer").messages)
    results = [message for message in orch.tech_lead.messages if message.role == "tool"]
    assert len(results) == 1 and results[0].tool_call_id == "research"
