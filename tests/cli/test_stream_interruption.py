"""Interactive stream failures must preserve transcripts without executing queued work."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_executor import ToolExecutor
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import SessionManager
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry
from henchman.utils.validation import validate_message_sequence


class MarkerTool(Tool):
    name = "mark"
    description = "Write a test marker"
    kind = ToolKind.WRITE

    def __init__(self, path):
        self.path = path

    async def execute(self, **kwargs):
        self.path.write_text("executed")
        return ToolResult("written")


def setup_runtime(tmp_path, provider):
    marker = tmp_path / "marker"
    registry = ToolRegistry()
    registry.register(MarkerTool(marker))
    registry.add_auto_approve_policy("mark")
    agent = Agent(provider=provider, tool_registry=registry)
    sessions = ReplSessionManager(SessionManager(data_dir=tmp_path / "sessions"))
    session = sessions.create_session("project")
    sessions.set_session(session)
    sessions.record_user_message("Work")
    output = MagicMock(session_manager=sessions)
    executor = ToolExecutor(output, SimpleNamespace(registry=registry), provider)
    return marker, agent, sessions, executor


@pytest.mark.parametrize("prior_call", [False, True])
async def test_provider_error_does_not_execute_queued_tools(tmp_path, prior_call):
    class FailingProvider(ModelProvider):
        name = "failing"
        attempts = 0

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            self.attempts += 1
            if self.attempts > 1:
                yield StreamChunk(content="Done", finish_reason=FinishReason.STOP)
                return
            yield StreamChunk(
                tool_calls=[ToolCall("one", "mark", {})], finish_reason=FinishReason.TOOL_CALLS,
            )
            raise ConnectionError("Disconnected before stream completed")

    provider = FailingProvider()
    marker, agent, sessions, executor = setup_runtime(tmp_path, provider)
    if prior_call:
        agent.messages.extend([
            Message(role="assistant", tool_calls=[ToolCall("one", "mark", {})]),
            Message(role="tool", tool_call_id="one", content="Completed in a prior turn"),
        ])
    await executor.process_agent_stream(agent.run("Work"), agent)

    assert not marker.exists()
    assert provider.attempts == 1
    assert agent.messages[-1].role == "tool"
    assert "cancel" in agent.messages[-1].content.lower()
    sessions.save()
    restored = sessions.load(sessions.session.id)
    assert [message.role for message in restored.messages] == ["user", "assistant", "tool"]
    assert restored.messages[-1].tool_call_id == "one"


async def test_cancel_during_stream_flushes_unexecuted_calls(tmp_path):
    waiting = asyncio.Event()
    closed = asyncio.Event()

    class WaitingProvider(ModelProvider):
        name = "waiting"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            try:
                yield StreamChunk(
                    tool_calls=[ToolCall("one", "mark", {})], finish_reason=FinishReason.TOOL_CALLS,
                )
                waiting.set()
                await asyncio.Event().wait()
            finally:
                closed.set()

    marker, agent, sessions, executor = setup_runtime(tmp_path, WaitingProvider())
    task = asyncio.create_task(executor.process_agent_stream(agent.run("Work"), agent))
    await asyncio.wait_for(waiting.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert closed.is_set()
    assert not marker.exists()
    assert agent.messages[-1].role == "tool"
    sessions.save()
    restored = sessions.load(sessions.session.id)
    assert [message.role for message in restored.messages] == ["user", "assistant", "tool"]
    assert restored.messages[-1].tool_call_id == "one"


async def test_two_tool_rounds_preserve_each_session_declaration(tmp_path):
    marker, agent, sessions, executor = setup_runtime(tmp_path, MagicMock())

    async def stream():
        for call_id in ("one", "two"):
            yield AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall(call_id, "mark", {}))
            yield AgentEvent(EventType.TOOL_CALL_RESULT, {
                "tool_call_id": call_id, "result": f"completed {call_id}", "success": True,
            })
        yield AgentEvent(EventType.CONTENT, "Finished both rounds")
        yield AgentEvent(EventType.FINISHED, "stop")

    await executor.process_agent_stream(stream(), agent)
    sessions.save()
    restored = sessions.load(sessions.session.id)

    assert not marker.exists(), "Already executed orchestrator tools must not execute twice"
    assert [message.role for message in restored.messages] == [
        "user", "assistant", "tool", "assistant", "tool", "assistant",
    ]
    assert [message.tool_calls[0]["id"] for message in restored.messages if message.tool_calls] == ["one", "two"]


@pytest.mark.parametrize("interrupt", ["error", "cancel", "render_error"])
async def test_orchestrator_and_cli_reconcile_results_without_duplicates(tmp_path, interrupt):
    from henchman.agents.orchestrator import Orchestrator
    from henchman.agents.presets import get_default_team
    from henchman.config.schema import Settings
    from tests.agents.test_orchestrator_interruption import ControlledProvider, ControlledTool

    class SecondToolBlocks(ControlledTool):
        async def execute(self, **kwargs):
            self.calls += 1
            if self.calls == 2 and interrupt == "cancel":
                self.started.set()
                await asyncio.Event().wait()
            return ToolResult("Actual first result")

    provider = ControlledProvider(requests=True, fail_after_requests=interrupt == "error")
    _, original_agent, sessions, executor = setup_runtime(tmp_path, provider)
    registry = original_agent.tool_registry
    tool = SecondToolBlocks()
    registry.register(tool)
    settings = Settings()
    settings.agents.agents["tech_lead"] = get_default_team()["tech_lead"].model_copy(
        update={"tools": ["work"]},
    )
    orchestrator = Orchestrator(provider, tool_registry=registry, settings=settings)
    agent = orchestrator.tech_lead
    if interrupt == "render_error":
        def render(text):
            if "[result]" in text:
                raise RuntimeError("output disconnected")

        executor.output_handler.muted.side_effect = render
    task = asyncio.create_task(executor.process_agent_stream(orchestrator.run("Work"), agent))
    if interrupt == "cancel":
        await asyncio.wait_for(tool.started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif interrupt == "render_error":
        with pytest.raises(RuntimeError, match="output disconnected"):
            await asyncio.wait_for(task, timeout=2)
        assert tool.calls == 1
        assert agent.messages[-1].tool_call_id == "second"
        assert "cancelled" in agent.messages[-1].content
    else:
        await asyncio.wait_for(task, timeout=2)

    validate_message_sequence(agent.messages)
    results = [message for message in agent.messages if message.role == "tool"]
    assert [message.tool_call_id for message in results] == ["first", "second"]
    if interrupt in {"cancel", "render_error"}:
        assert results[0].content == "Actual first result"
    sessions.save()
    restored = sessions.load(sessions.session.id)
    saved_results = [message for message in restored.messages if message.role == "tool"]
    assert [message.tool_call_id for message in saved_results] == ["first", "second"]
    assert [message.content for message in saved_results] == [message.content for message in results]
