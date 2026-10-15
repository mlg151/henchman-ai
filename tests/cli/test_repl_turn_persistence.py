"""REPL turns settle their real streams before persisting resumable history."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import asdict
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.output_handler import OutputHandler
from henchman.cli.repl import Repl, ReplConfig, _with_first_visible_activity_callback
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.tool_manager import ToolManager
from henchman.cli.ui_renderer import UIRenderer
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import SessionManager, SessionMessage
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk


class TurnProvider(ModelProvider):
    """Script the external transport, keeping agent/orchestrator/persistence real."""

    name = "turn-provider"

    def __init__(self, *, wait: bool = False) -> None:
        self.wait = wait
        self.waiting = asyncio.Event()
        self.closed = False
        self.task: asyncio.Task | None = None

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.task = asyncio.current_task()
        try:
            yield StreamChunk(content="Answer", thinking="Reasoning")
            if self.wait:
                self.waiting.set()
                await asyncio.Event().wait()
            yield StreamChunk(finish_reason=FinishReason.STOP)
        finally:
            self.closed = True


class InputMonitor:
    """Replace terminal input polling while using the real monitor bridge."""

    def __init__(self) -> None:
        self.exit_requested = False
        self.stop_requested = False
        self._stop_event = asyncio.Event()

    async def monitor(self) -> None:
        await self._stop_event.wait()


def build_repl(tmp_path: Path, provider: ModelProvider) -> Repl:
    repl = Repl.__new__(Repl)
    repl.config = ReplConfig()
    repl.running = True
    repl.provider = provider
    repl.renderer = UIRenderer(console=Console(file=StringIO()))
    repl.tool_manager = ToolManager()
    repl.orchestrator = Orchestrator(
        default_provider=provider, tool_registry=repl.tool_manager.registry,
    )
    repl.agent = repl.orchestrator.tech_lead
    repl.session_manager = ReplSessionManager(SessionManager(data_dir=tmp_path / "sessions"))
    session = repl.session_manager.create_session("project")
    session.messages = [SessionMessage(role="user", content="Archived earlier turn")]
    repl.session_manager.set_session(session)
    # The archived transcript has already been compacted out of active context.
    repl.agent.messages.append(Message(role="system", content="Earlier conversation summary"))
    repl.output_handler = OutputHandler(
        repl.renderer, repl.tool_manager, repl.session_manager, provider,
    )
    repl.tool_executor = ToolExecutor(repl.output_handler, repl.tool_manager, provider)
    return repl


def assert_saved_turn(repl: Repl, *, direct: bool) -> None:
    session = repl.session_manager.current
    assert session is not None
    loaded = repl.session_manager.load(session.id)
    agent = repl.orchestrator.pool.get_agent("explorer") if direct else repl.agent
    assert loaded.messages[0].content == "Archived earlier turn"
    expected = agent.messages[agent.turn.start_index:]
    assert expected[0].role == "user"
    assert expected[0].content == "Continue"
    assert [asdict(message) for message in loaded.messages[1:]] == [
        asdict(SessionMessage(**asdict(message))) for message in expected
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("direct", [False, True])
async def test_completed_turn_saves_authoritative_history(tmp_path, monkeypatch, direct):
    provider = TurnProvider()
    repl = build_repl(tmp_path, provider)
    monitor = InputMonitor()
    monkeypatch.setattr("henchman.cli.input.KeyMonitor", lambda: monitor)

    if direct:
        await repl._run_agent_direct("explorer", "Continue")
    else:
        await repl._run_agent("Continue")

    assert provider.closed
    assert_saved_turn(repl, direct=direct)
    session = repl.session_manager.current
    assert any(message.reasoning_content == "Reasoning" for message in session.messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("interruption", ["stop", "exit", "outer"])
async def test_cancelled_turn_closes_before_save(tmp_path, monkeypatch, direct, interruption):
    provider = TurnProvider(wait=True)
    repl = build_repl(tmp_path, provider)
    monitor = InputMonitor()
    monkeypatch.setattr("henchman.cli.input.KeyMonitor", lambda: monitor)
    operation = (
        repl._run_agent_direct("explorer", "Continue") if direct else repl._run_agent("Continue")
    )
    task = asyncio.create_task(operation)
    try:
        await asyncio.wait_for(provider.waiting.wait(), timeout=2)
        if interruption == "outer":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            setattr(monitor, f"{interruption}_requested", True)
            await asyncio.wait_for(task, timeout=2)
        assert provider.closed, "No agent work may outlive the persisted turn snapshot"
        assert_saved_turn(repl, direct=direct)
        assert repl.running is (interruption != "exit")
    finally:
        # Also clean up the demonstrated orphan on the unpatched implementation.
        for pending in (task, provider.task):
            if pending is not None and not pending.done():
                pending.cancel()
                with suppress(asyncio.CancelledError):
                    await pending


@pytest.mark.asyncio
async def test_visible_activity_wrapper_closes_source_when_consumer_stops():
    closed = False

    async def source() -> AsyncIterator[AgentEvent]:
        nonlocal closed
        try:
            yield AgentEvent(EventType.CONTENT, "answer")
        finally:
            closed = True

    stream = _with_first_visible_activity_callback(source(), lambda: None)
    await anext(stream)
    await stream.aclose()
    assert closed


@pytest.mark.asyncio
async def test_configured_direct_agent_resumes_and_persists_selected_history(tmp_path, monkeypatch):
    provider = TurnProvider()
    repl = build_repl(tmp_path, provider)
    repl.config.agent_role = "explorer"
    session = repl.session_manager.current
    repl.set_session(session)
    specialist = repl.orchestrator.pool.get_agent("explorer")
    assert specialist.messages[-1].content == "Archived earlier turn"
    lead_history = list(repl.agent.messages)
    monkeypatch.setattr("henchman.cli.input.KeyMonitor", InputMonitor)

    await repl._run_agent("Continue")

    assert repl.agent.messages == lead_history
    assert_saved_turn(repl, direct=True)
