"""Real agent/controller regressions for interrupted orchestration turns."""

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from henchman.agents.orchestrator_execution import ExecutionController
from henchman.agents.orchestrator_tools import ToolController
from henchman.agents.orchestrator_types import AgentLoopParams
from henchman.agents.pool import AgentPool
from henchman.core.agent import Agent
from henchman.core.eventbus import EventBus
from henchman.core.events import EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.tools.base import Tool, ToolResult
from henchman.tools.registry import ToolRegistry
from henchman.utils.validation import validate_message_sequence


class ControlledProvider(ModelProvider):
    name = "controlled"

    def __init__(self, *, requests: bool = False, fail_after_requests: bool = False) -> None:
        self.requests = requests
        self.fail_after_requests = fail_after_requests
        self.closed = False
        self.waiting = asyncio.Event()
        self.calls = 0

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.calls += 1
        try:
            if self.requests and self.calls == 1:
                yield StreamChunk(tool_calls=[
                    ToolCall("first", "work", {}), ToolCall("second", "work", {}),
                ], finish_reason=FinishReason.TOOL_CALLS)
                if self.fail_after_requests:
                    raise RuntimeError("connection lost after tool requests")
            elif self.requests:
                yield StreamChunk(content="Completed.", finish_reason=FinishReason.STOP)
            else:
                yield StreamChunk(content="Starting")
                self.waiting.set()
                await asyncio.Event().wait()
        finally:
            self.closed = True


class ControlledTool(Tool):
    name = "work"
    description = "Work controlled by this test"

    def __init__(self, *, blocking: bool = False) -> None:
        self.started = asyncio.Event()
        self.blocking = blocking
        self.calls = 0
        self.content = "full tool output " * 100

    async def execute(self, **params: object) -> ToolResult:
        self.calls += 1
        self.started.set()
        if self.blocking:
            await asyncio.Event().wait()
        return ToolResult(self.content)


def execution_pool(agent: Agent) -> AgentPool:
    """Supply real execution claims for standalone controller regressions."""
    return AgentPool(
        configs={}, default_provider=agent.provider, provider_registry=None,
        parent_tool_registry=agent.tool_registry, event_bus=EventBus(),
    )


def build_loop(provider: ControlledProvider, tool: ControlledTool | None = None):
    registry = ToolRegistry()
    if tool is not None:
        registry.register(tool)
    agent = Agent(provider, tool_registry=registry, max_tokens=100000)
    validator = MagicMock()
    validator.check_thinking_pattern.return_value = None
    validator.check_stall_failure.return_value = None
    orchestrator = SimpleNamespace(
        metrics=MagicMock(), validator=validator, ledger=None, pool=execution_pool(agent),
    )
    orchestrator.tool_controller = ToolController(orchestrator)
    controller = ExecutionController(orchestrator)
    stream = controller.run_agent_loop(AgentLoopParams(agent=agent, input_text="Work"))
    return agent, stream


@pytest.mark.asyncio
async def test_closing_loop_closes_provider_immediately():
    provider = ControlledProvider()
    _, stream = build_loop(provider)
    assert (await anext(stream)).type == EventType.CONTENT
    await stream.aclose()
    assert provider.closed


@pytest.mark.asyncio
async def test_close_after_first_request_balances_all_announced_calls():
    provider = ControlledProvider(requests=True)
    tool = ControlledTool()
    agent, stream = build_loop(provider, tool)
    assert (await anext(stream)).type == EventType.TOOL_CALL_REQUEST
    await stream.aclose()
    assert provider.closed
    assert tool.calls == 0
    validate_message_sequence(agent.messages)
    results = [m for m in agent.messages if m.role == "tool"]
    assert {m.tool_call_id for m in results} == {"first", "second"}
    assert all("interrupt" in m.content.lower() for m in results)


@pytest.mark.asyncio
async def test_cancel_during_tool_balances_requests_without_running_next_tool():
    provider = ControlledProvider(requests=True)
    tool = ControlledTool(blocking=True)
    agent, stream = build_loop(provider, tool)

    async def consume():
        return [event async for event in stream]

    task = asyncio.create_task(consume())
    await asyncio.wait_for(tool.started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert tool.calls == 1
    assert provider.closed
    validate_message_sequence(agent.messages)
    assert len([m for m in agent.messages if m.role == "tool"]) == 2


@pytest.mark.asyncio
async def test_provider_error_skips_queued_tools_and_continuation():
    provider = ControlledProvider(requests=True, fail_after_requests=True)
    tool = ControlledTool()
    agent, stream = build_loop(provider, tool)
    events = [event async for event in stream]
    assert any(event.type == EventType.ERROR for event in events)
    assert tool.calls == 0
    assert provider.calls == 1
    validate_message_sequence(agent.messages)
    results = [event.data for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert len(results) == 2
    assert all(result["success"] is False for result in results)


@pytest.mark.asyncio
async def test_tool_events_retain_complete_output_for_session_consumers():
    provider = ControlledProvider(requests=True)
    tool = ControlledTool()
    agent, stream = build_loop(provider, tool)
    events = [event async for event in stream]
    results = [event.data for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert len(results) == 2
    assert all(result["result"] == tool.content for result in results)
    validate_message_sequence(agent.messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("direct", [False, True])
async def test_public_orchestrator_close_reaches_provider_and_balances_history(direct):
    from henchman.agents.orchestrator import Orchestrator

    provider = ControlledProvider(requests=True)
    orchestrator = Orchestrator(default_provider=provider)
    stream = orchestrator.run_direct("explorer", "Work") if direct else orchestrator.run("Work")
    async for event in stream:
        if event.type == EventType.TOOL_CALL_REQUEST:
            break
    await stream.aclose()
    assert provider.closed
    agent = orchestrator.pool.get_agent("explorer") if direct else orchestrator.tech_lead
    validate_message_sequence(agent.messages)
    assert len([m for m in agent.messages if m.role == "tool"]) == 2


@pytest.mark.asyncio
async def test_cancel_waiting_for_provider_closes_stream():
    provider = ControlledProvider()
    _, stream = build_loop(provider)

    async def consume():
        return [event async for event in stream]

    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.waiting.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert provider.closed


@pytest.mark.asyncio
async def test_close_after_first_tool_keeps_result_and_skips_unexecuted_work():
    provider = ControlledProvider(requests=True)
    tool = ControlledTool()
    agent, stream = build_loop(provider, tool)
    async for event in stream:
        if event.type == EventType.TOOL_CALL_RESULT:
            break
    await stream.aclose()
    validate_message_sequence(agent.messages)
    results = [m for m in agent.messages if m.role == "tool"]
    assert len(results) == 2
    assert results[0].content == tool.content
    assert "interrupt" in results[1].content.lower()
    assert tool.calls == 1
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_closing_public_delegation_releases_specialist_stream():
    from henchman.agents.orchestrator import Orchestrator
    from henchman.agents.orchestrator_types import DelegationParams

    provider = ControlledProvider(requests=True)
    orchestrator = Orchestrator(default_provider=provider)
    stream = orchestrator.delegation_runner.run_delegation(
        DelegationParams(target_role="explorer", task="Work"),
    )
    async for event in stream:
        if event.type == EventType.TOOL_CALL_REQUEST:
            break
    await stream.aclose()
    assert provider.closed
    agent = orchestrator.pool.get_agent("explorer")
    validate_message_sequence(agent.messages)
    assert len([m for m in agent.messages if m.role == "tool"]) == 2


@pytest.mark.asyncio
async def test_primary_stream_exception_survives_cleanup_failure(monkeypatch):
    provider = ControlledProvider()
    agent, unused_stream = build_loop(provider)
    await unused_stream.aclose()

    class BrokenIterator:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise ValueError("primary failure")

        async def aclose(self):
            raise RuntimeError("cleanup failure")

    monkeypatch.setattr(agent, "run", lambda _: BrokenIterator())
    controller = ExecutionController(SimpleNamespace(pool=execution_pool(agent)))
    stream = controller.run_agent_loop(AgentLoopParams(agent=agent, input_text="Work"))
    with pytest.raises(ValueError, match="primary failure"):
        await anext(stream)


class DelegatingProvider(ModelProvider):
    name = "delegating"

    def __init__(self, *, fail_specialist: bool = False) -> None:
        self.calls = 0
        self.fail_specialist = fail_specialist
        self.content = "Specialist completed the requested investigation. " * 40

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        self.calls += 1
        if self.calls == 1:
            yield StreamChunk(tool_calls=[ToolCall(
                "delegate", "delegate_task", {"agent": "explorer", "task": "Investigate"},
            )], finish_reason=FinishReason.TOOL_CALLS)
        elif self.calls == 2:
            if self.fail_specialist:
                raise RuntimeError("specialist provider unavailable")
            yield StreamChunk(content=self.content, finish_reason=FinishReason.STOP)
        else:
            yield StreamChunk(content="Task resolved.", finish_reason=FinishReason.STOP)


@pytest.mark.asyncio
async def test_delegation_result_event_preserves_submitted_result():
    from henchman.agents.orchestrator import Orchestrator

    provider = DelegatingProvider()
    orchestrator = Orchestrator(default_provider=provider)
    events = [event async for event in orchestrator.run("Investigate")]
    event_result = next(
        event.data["result"] for event in events
        if event.type == EventType.TOOL_CALL_RESULT and event.data["tool_call_id"] == "delegate"
    )
    submitted = next(
        message.content for message in orchestrator.tech_lead.messages
        if message.role == "tool" and message.tool_call_id == "delegate"
    )
    assert event_result == submitted
    assert len(event_result) > 500


@pytest.mark.asyncio
async def test_specialist_provider_error_does_not_abort_parent_recovery():
    from henchman.agents.orchestrator import Orchestrator
    from henchman.config.schema import Settings

    provider = DelegatingProvider(fail_specialist=True)
    settings = Settings()
    settings.agents.max_delegation_retries = 0
    orchestrator = Orchestrator(default_provider=provider, settings=settings)
    events = [event async for event in orchestrator.run("Investigate")]
    assert any(event.type == EventType.ERROR for event in events)
    assert any(event.type == EventType.CONTENT and event.data == "Task resolved." for event in events)
    assert provider.calls == 3
    validate_message_sequence(orchestrator.tech_lead.messages)


@pytest.mark.asyncio
async def test_cleanup_failure_is_not_suppressed_by_callers_exception_handler(monkeypatch):
    provider = ControlledProvider()
    agent, unused_stream = build_loop(provider)
    await unused_stream.aclose()

    class CleanupFailureIterator:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

        async def aclose(self):
            raise RuntimeError("cleanup failed without primary error")

    monkeypatch.setattr(agent, "run", lambda _: CleanupFailureIterator())
    validator = MagicMock()
    validator.check_thinking_pattern.return_value = None
    validator.check_stall_failure.return_value = None
    controller = ExecutionController(SimpleNamespace(
        validator=validator, pool=execution_pool(agent),
    ))
    stream = controller.run_agent_loop(AgentLoopParams(agent=agent, input_text="Work"))
    try:
        raise ValueError("unrelated caller failure")
    except ValueError:
        with pytest.raises(RuntimeError, match="cleanup failed without primary error"):
            await anext(stream)
