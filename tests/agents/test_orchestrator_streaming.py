"""Nested team events obey consumer backpressure and close on interruption."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, cast

import pytest

from henchman.agents.ledger import DelegationStatus
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_execution import closing_event_stream
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.tools.base import Tool, ToolResult
from henchman.utils.validation import validate_message_sequence


class StreamingTeamProvider(ModelProvider):
    name = "streaming-team"

    def __init__(
        self,
        *,
        tools: bool = False,
        fail_first_child: bool = False,
    ) -> None:
        self.tools = tools
        self.fail_first_child = fail_first_child
        self.calls = 0
        self.child_chunks = 0
        self.closed: set[int] = set()
        self.waiting = asyncio.Event()
        self.release = asyncio.Event()

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.calls += 1
        call = self.calls
        try:
            if call == 1:
                yield StreamChunk(
                    tool_calls=[
                        ToolCall(
                            "parent",
                            "delegate_task",
                            {
                                "agent": "explorer",
                                "task": "Inspect source",
                                "completion_requirement": "actions" if self.tools else "response",
                            },
                        )
                    ],
                    finish_reason=FinishReason.TOOL_CALLS,
                )
            elif call == 2 and self.fail_first_child:
                raise RuntimeError("First child attempt failed")
            elif call == (3 if self.fail_first_child else 2):
                self.child_chunks += 1
                if self.tools:
                    yield StreamChunk(
                        tool_calls=[
                            ToolCall("child-one", "read_file", {"path": "one.py"}),
                            ToolCall("child-two", "read_file", {"path": "two.py"}),
                        ],
                        finish_reason=FinishReason.TOOL_CALLS,
                    )
                else:
                    yield StreamChunk(content="First child progress")
                    self.waiting.set()
                    await self.release.wait()
                    self.child_chunks += 1
                    yield StreamChunk(
                        content="Second child progress", finish_reason=FinishReason.STOP
                    )
            else:
                yield StreamChunk(content="Finished", finish_reason=FinishReason.STOP)
        finally:
            self.closed.add(call)


class CountingRead(Tool):
    name = "read_file"
    description = "Return fixture source"

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, **params: object) -> ToolResult:
        self.calls += 1
        return ToolResult("source contents")


def _team(*, tools: bool = False) -> tuple[Orchestrator, StreamingTeamProvider, CountingRead]:
    provider = StreamingTeamProvider(tools=tools)
    orchestrator = Orchestrator(default_provider=provider)
    orchestrator.settings.agents.max_delegation_retries = 0
    read = CountingRead()
    orchestrator.tool_registry.register(read)
    return orchestrator, provider, read


def _at_stage(event: AgentEvent, stage: str) -> bool:
    if stage == "delegated":
        return event.type == EventType.AGENT_DELEGATED
    if stage == "started":
        return event.type == EventType.AGENT_STARTED and event.data.get("agent") == "explorer"
    if stage == "content":
        return event.type == EventType.CONTENT and event.data == "First child progress"
    if stage == "request":
        return event.type == EventType.TOOL_CALL_REQUEST and event.data.id == "child-one"
    return (
        event.type == EventType.TOOL_CALL_RESULT and event.data.get("tool_call_id") == "child-one"
    )


@pytest.mark.parametrize("stage", ["delegated", "started", "content", "request", "result"])
async def test_closing_at_child_event_stops_work_and_balances_both_histories(stage: str) -> None:
    orchestrator, provider, read = _team(tools=stage in {"request", "result"})
    stream = cast("AsyncGenerator[AgentEvent, None]", orchestrator.run("Inspect source"))
    try:
        async with asyncio.timeout(2):
            async for event in stream:
                if _at_stage(event, stage):
                    break
            else:
                pytest.fail(f"missing child {stage} event")
        assert provider.calls == (1 if stage in {"delegated", "started"} else 2)
        assert read.calls == (1 if stage == "result" else 0)
        if stage == "content":
            assert provider.child_chunks == 1
            assert not provider.waiting.is_set()
    finally:
        await stream.aclose()

    assert provider.closed == set(range(1, provider.calls + 1))
    assert provider.calls == (1 if stage in {"delegated", "started"} else 2)
    assert read.calls == (1 if stage == "result" else 0)
    parent = orchestrator.tech_lead
    child = orchestrator.pool.get_agent("explorer")
    validate_message_sequence(parent.messages)
    validate_message_sequence(child.messages)
    parent_results = [message for message in parent.messages if message.role == "tool"]
    assert [message.tool_call_id for message in parent_results] == ["parent"]
    assert "interrupt" in (parent_results[0].content or "").lower()
    if stage in {"request", "result"}:
        child_results = [message for message in child.messages if message.role == "tool"]
        assert [message.tool_call_id for message in child_results] == ["child-one", "child-two"]
        assert "interrupt" in (child_results[-1].content or "").lower()
        assert child.turn.tool_count == (1 if stage == "result" else 0)
    assert orchestrator.ledger is not None
    assert orchestrator.ledger.delegations[0].status == DelegationStatus.FAILED
    assert "interrupt" in orchestrator.ledger.delegations[0].summary.lower()
    assert parent.turn.tool_count == 0
    assert orchestrator.last_completion_status.value == "failed"


async def test_child_progress_arrives_before_completion_and_pause_does_not_prefetch() -> None:
    orchestrator, provider, _read = _team()
    stream = cast("AsyncGenerator[AgentEvent, None]", orchestrator.run("Inspect source"))
    try:
        async with asyncio.timeout(2):
            async for event in stream:
                if _at_stage(event, "content"):
                    break
        assert provider.child_chunks == 1
        assert not provider.waiting.is_set()
        await asyncio.sleep(0)
        assert not provider.waiting.is_set()
        provider.release.set()
        remaining = [event async for event in stream]
        assert provider.child_chunks == 2
        assert remaining[-1].data["scope"] == "run"
        assert remaining[-1].data["status"] == "completed"
        assert orchestrator.tech_lead.turn.tool_count == 1
    finally:
        await stream.aclose()


async def test_cancellation_reaches_suspended_child_and_does_not_start_more_work() -> None:
    orchestrator, provider, _read = _team()
    stream = cast("AsyncGenerator[AgentEvent, None]", orchestrator.run("Inspect source"))
    events: list[AgentEvent] = []

    async def consume() -> None:
        async for event in stream:
            events.append(event)

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(provider.waiting.wait(), timeout=2)
        assert any(_at_stage(event, "content") for event in events)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert provider.closed == {1, 2}
    assert provider.calls == 2
    validate_message_sequence(orchestrator.tech_lead.messages)
    validate_message_sequence(orchestrator.pool.get_agent("explorer").messages)


class CancelledCloseIterator:
    def __aiter__(self) -> "CancelledCloseIterator":
        return self

    async def __anext__(self) -> AgentEvent:
        raise StopAsyncIteration

    async def aclose(self) -> None:
        raise asyncio.CancelledError("Cleanup cancelled")


async def test_cleanup_cancellation_preserves_original_consumer_error() -> None:
    primary = ValueError("Renderer failed")
    with pytest.raises(ValueError) as caught:
        async with closing_event_stream(CancelledCloseIterator()):
            raise primary
    assert caught.value is primary


async def test_cleanup_cancellation_without_primary_error_propagates() -> None:
    with pytest.raises(asyncio.CancelledError, match="Cleanup cancelled"):
        async with closing_event_stream(CancelledCloseIterator()):
            pass


async def test_interrupted_retry_fails_current_record_and_preserves_previous_failure() -> None:
    provider = StreamingTeamProvider(fail_first_child=True)
    orchestrator = Orchestrator(default_provider=provider)
    orchestrator.settings.agents.max_delegation_retries = 1
    stream = cast("AsyncGenerator[AgentEvent, None]", orchestrator.run("Inspect source"))
    try:
        async with asyncio.timeout(2):
            async for event in stream:
                if _at_stage(event, "content"):
                    break
            else:
                pytest.fail("Missing retry progress")
    finally:
        await stream.aclose()
    assert provider.calls == 3
    assert provider.closed == {1, 2, 3}
    assert orchestrator.ledger is not None
    first, retry = orchestrator.ledger.delegations
    assert first.status == DelegationStatus.FAILED
    assert "First child attempt failed" in first.summary
    assert retry.status == DelegationStatus.FAILED
    assert "interrupt" in retry.summary.lower()
    validate_message_sequence(orchestrator.tech_lead.messages)
    validate_message_sequence(orchestrator.pool.get_agent("explorer").messages)
