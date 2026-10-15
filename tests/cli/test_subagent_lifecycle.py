"""CLI exit and conversation changes join owned background agents."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from rich.console import Console

from henchman.cli import app
from henchman.cli.headless import run_orchestrator_json
from henchman.cli.repl import Repl, ReplConfig
from henchman.cli.textual_app import HenchmanTextualApp
from henchman.core.events import AgentEvent, EventType


class BackgroundWork:
    """Own a real pending task so cleanup assertions observe cancellation."""

    def __init__(self) -> None:
        self.stopped = asyncio.Event()
        self.task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        try:
            await asyncio.Event().wait()
        finally:
            self.stopped.set()

    async def close(self) -> None:
        self.task.cancel()
        with suppress(asyncio.CancelledError):
            await self.task


@pytest.fixture
def repl(tmp_path: Path) -> Repl:
    return Repl(
        provider=Mock(),
        console=Console(file=StringIO()),
        config=ReplConfig(auto_save=False, history_file=tmp_path / "history"),
    )


async def test_repl_exit_joins_subagents_before_disconnecting_mcp(repl, monkeypatch):
    work = BackgroundWork()
    await asyncio.sleep(0)
    monkeypatch.setattr(repl.orchestrator, "aclose", work.close, raising=False)
    repl._get_input = AsyncMock(return_value="/quit")

    async def disconnect():
        assert work.stopped.is_set()
        assert work.task.done()

    repl.mcp_manager = SimpleNamespace(disconnect_all=disconnect)
    repl.initialize_mcp = AsyncMock()
    try:
        await repl.run()
        assert work.stopped.is_set()
    finally:
        await work.close()


async def test_repl_initialization_failure_still_closes_subagents(repl, monkeypatch):
    close = AsyncMock()
    monkeypatch.setattr(repl.orchestrator, "aclose", close, raising=False)
    repl.initialize_mcp = AsyncMock(side_effect=RuntimeError("connection failed"))
    with pytest.raises(RuntimeError, match="connection failed"):
        await repl.run()
    close.assert_awaited_once()


@pytest.mark.parametrize("cancel", [False, True])
async def test_headless_text_closes_runtime_after_success_or_cancellation(
    repl,
    monkeypatch,
    cancel,
):
    close = AsyncMock()
    monkeypatch.setattr(repl.orchestrator, "aclose", close, raising=False)
    repl.initialize_mcp = AsyncMock()
    repl.rag_system = None
    repl.process_input = AsyncMock(
        side_effect=asyncio.CancelledError if cancel else None,
    )
    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await app._run_headless_text(repl, "work")
    else:
        await app._run_headless_text(repl, "work")
    close.assert_awaited_once()


@pytest.mark.parametrize("renderer_error", [False, True])
async def test_headless_json_joins_subagents_even_when_rendering_fails(renderer_error):
    work = BackgroundWork()
    await asyncio.sleep(0)

    async def events(_prompt):
        yield AgentEvent(EventType.CONTENT, "Result")
        yield AgentEvent(
            EventType.AGENT_COMPLETED,
            {
                "agent": "tech_lead",
                "scope": "run",
                "status": "responded",
            },
            source_agent="orchestrator",
        )

    def render(_event):
        if renderer_error:
            raise RuntimeError("broken renderer")

    orchestrator = SimpleNamespace(run=events, aclose=work.close)
    try:
        if renderer_error:
            with pytest.raises(RuntimeError, match="broken renderer"):
                await run_orchestrator_json(orchestrator, "work", render)
        else:
            assert await run_orchestrator_json(orchestrator, "work", render)
        assert work.stopped.is_set()
        assert work.task.done()
    finally:
        await work.close()


async def test_textual_unmount_joins_children_before_mcp_and_session_save():
    work = BackgroundWork()
    await asyncio.sleep(0)
    order = []

    async def disconnect():
        assert work.stopped.is_set()
        order.append("disconnect")

    context = SimpleNamespace(
        orchestrator=SimpleNamespace(aclose=work.close),
        mcp_manager=SimpleNamespace(disconnect_all=disconnect),
        background_tasks=set(),
        session_manager=SimpleNamespace(auto_save_session=lambda: order.append("save")),
    )
    tui = SimpleNamespace(
        core_context=context,
        _cleanup_confirm_futures=lambda: order.append("questions"),
        _queued_inputs=lambda: [],
        _pause_active_goal=lambda: None,
    )
    try:
        await HenchmanTextualApp.on_unmount(tui)
        assert work.task.done()
        assert order == ["questions", "disconnect", "save"]
    finally:
        await work.close()


@pytest.mark.parametrize(
    "command", ["/clear", "/team reset", "/chat resume saved", "/chat RESUME saved"]
)
async def test_history_commands_join_subagents_before_changing_history(
    repl,
    monkeypatch,
    command,
):
    work = BackgroundWork()
    await asyncio.sleep(0)
    cancel = AsyncMock(side_effect=work.close)
    monkeypatch.setattr(repl.orchestrator, "cancel_subagents", cancel, raising=False)
    original_clear = repl.agent.clear_history

    def clear():
        assert work.stopped.is_set()
        original_clear()

    monkeypatch.setattr(repl.agent, "clear_history", clear)
    # Route non-clear commands through a deterministic command fixture; lifecycle
    # dispatch must complete before any handler can replace conversation state.
    if command != "/clear":
        handler = Mock()
        handler.execute = AsyncMock(side_effect=lambda _ctx: clear())
        monkeypatch.setattr(repl.command_processor.command_registry, "get", lambda _name: handler)
    try:
        assert await repl.command_processor.handle_command(command, repl.agent, repl)
        cancel.assert_awaited_once()
        assert work.task.done()
    finally:
        await work.close()


async def test_textual_real_unmount_joins_background_agent(tmp_path, monkeypatch):
    from henchman.cli.textual_config import TextualConfig
    from henchman.config.schema import Settings

    monkeypatch.chdir(tmp_path)
    provider = Mock()
    provider.name = "test"
    tui = HenchmanTextualApp(
        provider=provider,
        settings=Settings(),
        config=TextualConfig(auto_save=False, history_file=tmp_path / "history"),
    )
    work = BackgroundWork()
    await asyncio.sleep(0)
    try:
        async with tui.run_test(size=(100, 40)):
            monkeypatch.setattr(tui.core_context.orchestrator, "aclose", work.close, raising=False)
        assert work.stopped.is_set()
        assert work.task.done()
    finally:
        await work.close()


@pytest.mark.parametrize("command", ["/chat save", "/chat list", "/team status"])
async def test_read_and_save_commands_keep_background_work(repl, monkeypatch, command):
    cancel = AsyncMock()
    monkeypatch.setattr(repl.orchestrator, "cancel_subagents", cancel, raising=False)
    handler = Mock(execute=AsyncMock())
    monkeypatch.setattr(repl.command_processor.command_registry, "get", lambda _name: handler)
    assert await repl.command_processor.handle_command(command, repl.agent, repl)
    cancel.assert_not_awaited()


@pytest.mark.parametrize("boundary", ["repl-exit", "headless-exit", "history-reset"])
async def test_cli_boundaries_close_real_owned_subagent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    """Exercise actual manager, agent loop, and stream finalization together."""
    from henchman.providers.base import FinishReason, StreamChunk
    from henchman.providers.ollama import OllamaProvider

    entered, stopped = asyncio.Event(), asyncio.Event()

    async def stream(messages, **_kwargs):
        del messages
        entered.set()
        try:
            await asyncio.Event().wait()
            yield StreamChunk(content="unreachable", finish_reason=FinishReason.STOP)
        finally:
            stopped.set()

    provider = OllamaProvider()
    monkeypatch.setattr(provider, "chat_completion_stream", stream)
    runtime = Repl(
        provider=provider,
        console=Console(file=StringIO()),
        config=ReplConfig(auto_save=False, history_file=tmp_path / "history"),
    )
    runtime.initialize_mcp = AsyncMock()
    runtime.rag_system = None
    record = runtime.orchestrator.subagents.spawn(
        "Wait for cancellation",
        role="lifecycle fixture",
        system_prompt="Wait",
        tools=[],
    )
    try:
        await asyncio.wait_for(entered.wait(), 2)
        if boundary == "repl-exit":
            runtime._get_input = AsyncMock(return_value="/quit")
            await runtime.run()
        elif boundary == "headless-exit":
            runtime.process_input = AsyncMock()
            await app._run_headless_text(runtime, "Finish")
        else:
            await runtime.command_processor.handle_command("/clear", runtime.agent, runtime)
        assert stopped.is_set()
        assert not runtime.orchestrator.subagents.has_running_work()
        closed = runtime.orchestrator.subagents.get(record.conversation_id)
        assert closed.status == "done"
        assert closed.cancelled
    finally:
        await runtime.aclose()


async def test_textual_clear_resets_agent_and_flushes_command_output(tmp_path, monkeypatch):
    from henchman.cli.textual_config import TextualConfig
    from henchman.cli.textual_widgets import ChatPane
    from henchman.config.schema import Settings
    from henchman.providers.base import Message

    monkeypatch.chdir(tmp_path)
    provider = Mock()
    provider.name = "test"
    tui = HenchmanTextualApp(
        provider=provider,
        settings=Settings(),
        config=TextualConfig(auto_save=False, history_file=tmp_path / "history"),
    )
    async with tui.run_test(size=(100, 40)):
        tui.core_context.agent.messages.append(Message(role="user", content="old task"))
        cancel = AsyncMock()
        monkeypatch.setattr(tui.core_context.orchestrator, "cancel_subagents", cancel)
        flush = Mock()
        monkeypatch.setattr(tui._tui_adapter, "flush_to_chat", flush)
        await tui._handle_command("/clear", tui.query_one("#chat-pane", ChatPane))
        cancel.assert_awaited_once()
        assert not any(message.content == "old task" for message in tui.core_context.agent.messages)
        flush.assert_called_once()
