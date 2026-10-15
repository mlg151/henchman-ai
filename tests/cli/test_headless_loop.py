"""Headless execution must finish truthfully and bound external work."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import click
import pytest

from henchman.cli.app import _run_headless_json_mode
from henchman.core.agent import Agent, AgentConfig
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.tools.base import ToolResult
from henchman.tools.registry import ToolRegistry


class LoopProvider(ModelProvider):
    """Keep asking for work to exercise the public loop limit."""

    name = "loop-test"

    def __init__(self):
        self.calls = 0

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        await asyncio.sleep(0)
        self.calls += 1
        yield StreamChunk(
            tool_calls=[ToolCall(str(self.calls), "read_file", {"path": "file.py"})],
            finish_reason=FinishReason.TOOL_CALLS,
        )


async def test_runaway_tool_loop_is_bounded_and_balanced():
    provider = LoopProvider()
    registry = ToolRegistry()
    registry.execute = AsyncMock(return_value=ToolResult("contents"))
    agent = Agent(provider=provider, tool_registry=registry, config=AgentConfig(base_tool_iterations=2))
    events = []
    async with asyncio.timeout(2):
        success = await _run_headless_json_mode(
            SimpleNamespace(agent=agent, tool_registry=registry), "Read file", events.append
        )
    assert success is False
    assert registry.execute.await_count == 2
    assert provider.calls == 3
    assert agent.turn.iteration == 2
    assert agent.turn.tool_count == 2
    requests = [event.data.id for event in events if event.type == EventType.TOOL_CALL_REQUEST]
    results = [event.data for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert requests == [result["tool_call_id"] for result in results]
    assert results[-1]["success"] is False
    assert [m.tool_call_id for m in agent.messages if m.role == "tool"] == requests
    assert [event.type for event in events].count(EventType.FINISHED) == 1
    assert events[-1].data["finish_reason"] == "error"


async def test_error_discards_queued_tools_and_closes_stream():
    closed = []

    async def broken_stream():
        try:
            yield AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall("one", "shell", {}))
            yield AgentEvent(EventType.ERROR, "connection lost")
            await asyncio.sleep(10)
        finally:
            closed.append(True)

    agent = SimpleNamespace(run=lambda _: broken_stream(), submit_tool_result=lambda *_args: None)
    registry = SimpleNamespace(execute=AsyncMock())
    agent.tool_registry = registry
    events = []
    async with asyncio.timeout(1):
        success = await _run_headless_json_mode(
            SimpleNamespace(agent=agent, tool_registry=registry), "work", events.append
        )
    assert not success
    assert closed == [True]
    registry.execute.assert_not_awaited()
    assert events[-2].data["tool_call_id"] == "one"
    assert events[-2].data["success"] is False
    assert events[-1].data["finish_reason"] == "error"


async def test_cancel_during_tool_balances_pending_calls():
    async def stream():
        yield AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall("one", "shell", {}))
        yield AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall("two", "shell", {}))
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "tool_calls"})

    submitted = []
    agent = SimpleNamespace(
        run=lambda _: stream(), base_tool_iterations=2,
        submit_tool_result=lambda *args: submitted.append(args),
    )
    registry = SimpleNamespace(execute=AsyncMock(side_effect=asyncio.CancelledError))
    agent.tool_registry = registry
    events = []
    with pytest.raises(asyncio.CancelledError):
        await _run_headless_json_mode(
            SimpleNamespace(agent=agent, tool_registry=registry), "work", events.append
        )
    assert [item[0] for item in submitted] == ["one", "two"]
    assert registry.execute.await_count == 1
    assert not any(event.type == EventType.FINISHED for event in events)


@pytest.mark.parametrize("mode", ["json", "stream-json", "json-complete"])
async def test_json_failure_renders_terminal_error_before_nonzero_exit(monkeypatch, mode):
    from unittest.mock import MagicMock

    from henchman.cli import app

    async def failed_stream():
        yield AgentEvent(EventType.ERROR, "Provider disconnected")

    repl = SimpleNamespace(agent=SimpleNamespace(run=lambda _: failed_stream()))
    renderer = MagicMock()
    monkeypatch.setattr(app, "_initialize_json_processing", AsyncMock(return_value=renderer))
    with pytest.raises(click.ClickException) as failure:
        if mode == "json-complete":
            await app._run_headless_json_complete(repl, "work")
        else:
            await app._run_headless_json_format(repl, "work", mode)
    assert failure.value.exit_code == 1
    if mode == "json-complete":
        events = renderer.render_final_json.call_args.args[0]
    else:
        render = renderer.render if mode == "json" else renderer.render_stream_json
        events = [call.args[0] for call in render.call_args_list]
    assert [event.type for event in events] == [EventType.ERROR, EventType.FINISHED]
    assert events[-1].data == {"finish_reason": "error"}


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls", "error", None])
@pytest.mark.parametrize("with_usage", [False, True])
async def test_incomplete_model_response_is_not_success(reason, with_usage):
    async def incomplete_stream():
        yield AgentEvent(EventType.CONTENT, "Partial answer")
        yield AgentEvent(EventType.FINISHED, {"finish_reason": reason, "usage": {}} if with_usage else reason)

    repl = SimpleNamespace(agent=SimpleNamespace(run=lambda _: incomplete_stream()))
    events = []
    assert not await _run_headless_json_mode(repl, "work", events.append)
    assert events[-2].type == EventType.ERROR
    assert events[-1].data == {"finish_reason": "error"}


@pytest.mark.parametrize("with_usage", [False, True])
async def test_stop_response_is_success(with_usage):
    async def completed_stream():
        yield AgentEvent(EventType.CONTENT, "Completed")
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "stop", "usage": {}} if with_usage else "stop")

    repl = SimpleNamespace(agent=SimpleNamespace(run=lambda _: completed_stream()))
    events = []
    assert await _run_headless_json_mode(repl, "work", events.append)
    assert [event.type for event in events] == [EventType.CONTENT, EventType.FINISHED]
