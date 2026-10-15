"""Structured headless runs use the same team runtime as interactive sessions."""

import asyncio
from collections.abc import AsyncIterator
from functools import partial
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import anyio
import click
import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.cli import app
from henchman.config.schema import AgentSettings, Settings
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.tools.builtins.file_read import ReadFileTool


def _orchestrator(chunks: list[StreamChunk]) -> Orchestrator:
    provider = MagicMock(spec=ModelProvider)
    provider.estimate_input_tokens.side_effect = partial(ModelProvider.estimate_input_tokens, provider)
    provider.prepare_output_budget.side_effect = partial(ModelProvider.prepare_output_budget, provider)
    responses = iter(chunks)

    async def stream(*_args: object, **_kwargs: object) -> AsyncIterator[StreamChunk]:
        yield next(responses)

    provider.chat_completion_stream.side_effect = stream
    return Orchestrator(
        default_provider=provider,
        settings=Settings(agents=AgentSettings(max_delegation_retries=0)),
    )


async def test_headless_executes_real_delegation_and_finishes_once() -> None:
    orchestrator = _orchestrator([
        StreamChunk(tool_calls=[ToolCall("advice", "delegate_task", {
            "agent": "explorer", "task": "Explain tests",
            "completion_requirement": "response",
        })], finish_reason=FinishReason.TOOL_CALLS),
        StreamChunk(content="Use focused tests.", finish_reason=FinishReason.STOP),
        StreamChunk(content="Advice received.", finish_reason=FinishReason.STOP),
    ])
    repl = SimpleNamespace(
        orchestrator=orchestrator, agent=orchestrator.tech_lead,
        tool_registry=orchestrator.tech_lead.tool_registry,
    )
    events: list[AgentEvent] = []

    assert await app._run_headless_json_mode(repl, "Get advice", events.append)

    assert any(event.type == EventType.AGENT_DELEGATED for event in events)
    result = next(event.data for event in events if event.type == EventType.TOOL_CALL_RESULT)
    assert result["tool_call_id"] == "advice"
    assert result["success"] is True
    assert orchestrator.ledger is not None
    assert [event.type for event in events].count(EventType.FINISHED) == 1
    assert events[-1].data["status"] == "completed"
    assert events[-1].data["task_verified"] is False
    assert events[-1].data["scope"] == "run"


async def test_direct_role_uses_existing_pool_and_provider() -> None:
    orchestrator = _orchestrator([
        StreamChunk(content="Architectural explanation.", finish_reason=FinishReason.STOP),
    ])
    events: list[AgentEvent] = []
    repl = SimpleNamespace(orchestrator=orchestrator, agent=orchestrator.tech_lead)

    assert await app._run_headless_json_mode(
        repl, "Explain this design", events.append, agent_role="explorer",
    )

    assert events[0].data["agent"] == "explorer"
    assert events[-1].data["agent"] == "explorer"
    assert events[-1].data["status"] == "responded"
    assert orchestrator.pool.get_agent("explorer").messages[-1].content
    assert not any(message.role == "user" for message in orchestrator.tech_lead.messages)


async def test_team_round_limit_is_a_failed_headless_terminal(tmp_path: Path) -> None:
    target = tmp_path / "source.py"
    target.write_text("value = 1", encoding="utf-8")
    chunks = [StreamChunk(tool_calls=[ToolCall(
        str(index), "read_file", {"path": str(target)},
    )], finish_reason=FinishReason.TOOL_CALLS) for index in range(2)]
    chunks.append(StreamChunk(content="Would finish", finish_reason=FinishReason.STOP))
    orchestrator = _orchestrator(chunks)
    orchestrator.tool_registry.register(ReadFileTool())
    orchestrator.tech_lead.base_tool_iterations = 1
    repl = SimpleNamespace(orchestrator=orchestrator, agent=orchestrator.tech_lead)
    events: list[AgentEvent] = []

    assert not await app._run_headless_json_mode(repl, "Read source", events.append)

    assert events[-1].data["status"] == "timed_out"
    assert [event.type for event in events].count(EventType.FINISHED) == 1
    assert orchestrator.tech_lead.turn.tool_count == 1
    assert orchestrator.tech_lead.turn.iteration == 1
    results = [event.data for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert [result["success"] for result in results] == [True, False]


@pytest.mark.parametrize("format_name", ["json", "stream-json", "json-complete"])
def test_dispatch_preserves_requested_role(
    monkeypatch: pytest.MonkeyPatch, format_name: str,
) -> None:
    run = MagicMock()
    monkeypatch.setattr(anyio, "run", run)
    app._dispatch_headless_format(object(), app.RunConfig(
        prompt="Explain", output_format=format_name, agent_role="architect",
    ))
    assert run.call_args.args[-1] == "architect"


def _scripted_repl(stream: AsyncIterator[AgentEvent]) -> SimpleNamespace:
    orchestrator = Orchestrator.__new__(Orchestrator)
    orchestrator.run = MagicMock(return_value=stream)  # type: ignore[method-assign]
    fallback = MagicMock()
    fallback.run.side_effect = AssertionError("must reuse the orchestrator")
    return SimpleNamespace(orchestrator=orchestrator, agent=fallback)


@pytest.mark.parametrize("status", [
    "completed", "responded", "failed", "stalled", "no_work_done", "timed_out",
    "unexpected", None,
])
async def test_only_authoritative_root_status_decides_success(status: str | None) -> None:
    async def stream() -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "stop"})
        yield AgentEvent(EventType.AGENT_COMPLETED, {
            "agent": "explorer", "status": "completed",
        }, source_agent="orchestrator")
        yield AgentEvent(EventType.ERROR, "A specialist retry was needed")
        yield AgentEvent(EventType.AGENT_COMPLETED, {
            "agent": "tech_lead", "status": status, "scope": "run",
            "task_verified": False, "evidence": {"successful_tool_calls": 1},
        }, source_agent="orchestrator")

    events: list[AgentEvent] = []
    success = await app._run_headless_json_mode(_scripted_repl(stream()), "task", events.append)
    assert success is (status in {"completed", "responded"})
    assert events[-1].type == EventType.FINISHED
    assert [event.type for event in events].count(EventType.FINISHED) == 1
    assert events[-1].data["task_verified"] is False


async def test_same_role_child_completion_cannot_replace_missing_root_event() -> None:
    async def stream() -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.AGENT_COMPLETED, {
            "agent": "tech_lead", "status": "completed",
        }, source_agent="orchestrator")
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "stop"})

    events: list[AgentEvent] = []
    assert not await app._run_headless_json_mode(_scripted_repl(stream()), "task", events.append)
    assert events[-1].data["finish_reason"] == "error"


async def test_empty_exception_after_completion_still_reports_failed_status() -> None:
    async def stream() -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.AGENT_COMPLETED, {
            "agent": "tech_lead", "status": "completed", "scope": "run",
        }, source_agent="orchestrator")
        raise RuntimeError

    events: list[AgentEvent] = []
    assert not await app._run_headless_json_mode(_scripted_repl(stream()), "task", events.append)
    assert events[-1].data["status"] == "failed"


async def test_mock_orchestrator_attribute_does_not_disable_standalone_loop() -> None:
    async def stream() -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.FINISHED, {"finish_reason": "stop"})

    repl = MagicMock(orchestrator=MagicMock(spec=Orchestrator))
    repl.agent.run.return_value = stream()
    events: list[AgentEvent] = []
    assert await app._run_headless_json_mode(repl, "task", events.append)
    repl.agent.run.assert_called_once_with("task")
    repl.orchestrator.run.assert_not_called()


async def test_render_failure_closes_stream_and_preserves_original_error() -> None:
    closed = []
    failure = ValueError("renderer failed")

    async def stream() -> AsyncIterator[AgentEvent]:
        try:
            yield AgentEvent(EventType.CONTENT, "answer")
        finally:
            closed.append(True)
            raise RuntimeError("cleanup failed")

    def render(_event: AgentEvent) -> None:
        raise failure

    with pytest.raises(ValueError) as error:
        await app._run_headless_json_mode(_scripted_repl(stream()), "task", render)
    assert error.value is failure
    assert closed == [True]


@pytest.mark.parametrize("format_name", ["json", "stream-json", "json-complete"])
async def test_execution_exception_produces_terminal_failure(
    monkeypatch: pytest.MonkeyPatch, format_name: str,
) -> None:
    async def stream() -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.CONTENT, "partial")
        raise OSError("transport unavailable")

    renderer = MagicMock()
    monkeypatch.setattr(app, "_initialize_json_processing", AsyncMock(return_value=renderer))
    repl = _scripted_repl(stream())
    with pytest.raises(click.ClickException):
        if format_name == "json-complete":
            await app._run_headless_json_complete(repl, "task")
        else:
            await app._run_headless_json_format(repl, "task", format_name)
    if format_name == "json-complete":
        events = renderer.render_final_json.call_args.args[0]
    else:
        render = renderer.render if format_name == "json" else renderer.render_stream_json
        events = [call.args[0] for call in render.call_args_list]
    assert events[-2].type == EventType.ERROR
    assert "transport unavailable" in events[-2].data
    assert events[-1].type == EventType.FINISHED
    assert events[-1].data["finish_reason"] == "error"


async def test_cancellation_closes_real_provider_without_success() -> None:
    entered = asyncio.Event()
    closed = asyncio.Event()
    provider = MagicMock(spec=ModelProvider)
    provider.estimate_input_tokens.side_effect = partial(ModelProvider.estimate_input_tokens, provider)
    provider.prepare_output_budget.side_effect = partial(ModelProvider.prepare_output_budget, provider)

    async def stream(*_args: object, **_kwargs: object) -> AsyncIterator[StreamChunk]:
        try:
            entered.set()
            await asyncio.Event().wait()
            yield StreamChunk(content="unreachable")
        finally:
            closed.set()

    provider.chat_completion_stream.side_effect = stream
    orchestrator = Orchestrator(default_provider=provider)
    repl = SimpleNamespace(orchestrator=orchestrator, agent=orchestrator.tech_lead)
    events: list[AgentEvent] = []
    task = asyncio.create_task(app._run_headless_json_mode(repl, "task", events.append))
    await asyncio.wait_for(entered.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()
    assert not any(event.type == EventType.FINISHED for event in events)
