"""Control commands remain reachable without acquiring an input dispatch claim."""

import asyncio
import os
from io import StringIO
from unittest.mock import Mock

import pytest
from rich.console import Console
from textual.widgets import TextArea

from henchman.cli.repl import Repl, ReplConfig
from henchman.mcp.manager import McpManager
from tests.cli.test_textual_background_goals import app as app_fixture
from tests.mcp.context_fixture import context_peer

app = app_fixture


def make_repl(tmp_path):
    repl = Repl(provider=Mock(), console=Console(file=StringIO()),
                config=ReplConfig(history_file=tmp_path / "history", auto_save=False))
    repl.set_session(repl.session_manager.create_session("project"))
    repl._interactive_loop_active = True
    return repl


async def test_idle_repl_attach_consumes_local_preview_without_queue_or_provider(tmp_path):
    repl = make_repl(tmp_path)
    async with context_peer(tmp_path, "streamable_http") as peer:
        manager = McpManager({"source": peer.config})
        repl.mcp_manager = repl.command_processor.mcp_manager = manager
        try:
            await manager.connect_server("source")
            result = await manager.read_resource("source", "custom://fixture/readme")
            session = repl.session_manager.current
            manager.bind_context_preview(result.preview_id, session, repl.agent)
            requests = len(peer.requests())
            await repl.process_input(f"/mcp attach {result.preview_id}")
            if repl._turn_worker is not None:
                await repl._turn_worker
            assert len(session.messages) == 1
            assert session.messages[0].context_attachments[0]["preview_id"] == result.preview_id
            assert not session.workflow_runtime.report().state.inputs
            assert len(peer.requests()) == requests
            repl.provider.chat_completion_stream.assert_not_called()
        finally:
            repl._interactive_loop_active = False
            await repl.aclose()


@pytest.mark.parametrize("composer", [False, True])
async def test_idle_textual_attach_uses_real_command_and_existing_idle_guard(app, tmp_path, composer):
    async with context_peer(tmp_path, "streamable_http") as peer:
        manager = McpManager({"source": peer.config})
        async with app.run_test(size=(100, 40)) as pilot:
            app.core_context.mcp_manager = app.command_processor.mcp_manager = manager
            await manager.connect_server("source")
            result = await manager.read_resource("source", "custom://fixture/readme")
            session = app.core_context.session_manager.current
            manager.bind_context_preview(result.preview_id, session, app.core_context.agent)
            requests = len(peer.requests())
            command = f"/mcp attach {result.preview_id}"
            if composer:
                app.query_one("#input", TextArea).load_text(command)
                app.action_submit_message()
                await pilot.pause()
            else:
                await app.process_user_input(command).wait()
            assert len(session.messages) == 1
            assert session.messages[0].context_attachments[0]["preview_id"] == result.preview_id
            assert not session.workflow_runtime.report().state.inputs
            assert len(peer.requests()) == requests
            app.provider.chat_completion_stream.assert_not_called()


@pytest.mark.parametrize("command", ["/help", "/recovery status", "/mcp status", "/checkpoint list", "/model list", "/context stats", "/team status"])
async def test_textual_held_workflow_does_not_block_real_inspection_commands(app, monkeypatch, command):
    async with app.run_test(size=(100, 40)) as pilot:
        session = app.core_context.session_manager.current
        runtime = session.workflow_runtime
        runtime.submit("interrupted request")
        runtime.next_input()
        runtime.interrupt()
        calls = []
        original = app._handle_command
        async def handle(text, chat):
            calls.append(text)
            return await original(text, chat)
        monkeypatch.setattr(app, "_handle_command", handle)
        app.query_one("#input", TextArea).load_text(command)
        app.action_submit_message()
        await pilot.pause()
        assert calls == [command]
        assert len(runtime.report().state.inputs) == 1
        assert runtime.report().blocking_input_ids
        app.provider.chat_completion_stream.assert_not_called()


@pytest.mark.parametrize("command", ["/mcp attach unused", "/checkpoint apply unused", "/checkpoint recover unused"])
async def test_active_textual_idle_controls_keep_draft_and_never_enter_queue(app, monkeypatch, command):
    entered, release = asyncio.Event(), asyncio.Event()
    async def route(_text, _chat):
        entered.set()
        await release.wait()
    monkeypatch.setattr(app, "_route_input", route)
    async with app.run_test(size=(100, 40)):
        worker = app.process_user_input("active work")
        await entered.wait()
        session = app.core_context.session_manager.current
        widget = app.query_one("#input", TextArea)
        widget.load_text(command)
        app.action_submit_message()
        assert widget.text == command
        assert len(session.workflow_runtime.report().state.inputs) == 1
        release.set()
        await worker.wait()


@pytest.mark.skipif(os.name != "posix", reason="This fixture uses the POSIX checkpoint backend")
async def test_textual_checkpoint_apply_is_reachable_while_input_recovery_is_held(app, tmp_path):
    from henchman.advanced.checkpoints import CheckpointService

    path = tmp_path / "restore.txt"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    checkpoint = service.begin(["restore.txt"], actor="engineer")
    path.write_text("after")
    service.complete(checkpoint.checkpoint_id)
    preview = service.preview(checkpoint.checkpoint_id, decision="reject")
    async with app.run_test(size=(100, 40)):
        runtime = app.core_context.session_manager.current.workflow_runtime
        runtime.submit("interrupted")
        runtime.next_input()
        runtime.interrupt()
        await app.process_user_input(f"/checkpoint apply {preview.plan_id}").wait()
        assert path.read_text() == "before"
        assert len(runtime.report().state.inputs) == 1
        assert runtime.report().blocking_input_ids
        app.provider.chat_completion_stream.assert_not_called()


@pytest.mark.parametrize("cancel", [False, True])
async def test_idle_command_owns_interval_and_cancellation_holds_newly_accepted_input(app, monkeypatch, cancel):
    entered, release, ran = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def control(_text, _chat):
        entered.set()
        await release.wait()
    async def route(_text, _chat):
        ran.set()
    monkeypatch.setattr(app, "_handle_command", control)
    monkeypatch.setattr(app, "_route_input", route)
    async with app.run_test(size=(100, 40)):
        worker = app.process_user_input("/checkpoint apply deliberate-test")
        await entered.wait()
        widget = app.query_one("#input", TextArea)
        widget.load_text("new user request")
        app.action_submit_message()
        await asyncio.sleep(0)
        assert not ran.is_set()
        if cancel:
            app.action_cancel_or_clear()
        else:
            release.set()
        await worker.wait()
        if cancel:
            await asyncio.sleep(.05)
            assert not ran.is_set()
            runtime = app.core_context.session_manager.current.workflow_runtime
            assert runtime.report().state.inputs[0].state == "queued"
            assert runtime.next_input() is None
        else:
            await asyncio.wait_for(ran.wait(), 1)


async def test_cancelled_repl_idle_command_does_not_send_pending_input(tmp_path):
    repl = make_repl(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []
    async def command(_text, *_args):
        entered.set()
        await release.wait()
        return True
    async def agent(text):
        calls.append(text)
    repl.command_processor.handle_command = command
    repl._run_agent = agent
    task = asyncio.create_task(repl.process_input("/checkpoint apply deliberate-test"))
    try:
        await entered.wait()
        await repl.submit_agent_input("accepted while command active")
        assert not calls
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        runtime = repl.session_manager.current.workflow_runtime
        assert runtime.next_input() is None
        assert runtime.report().state.inputs[0].state == "queued"
    finally:
        release.set()
        repl._interactive_loop_active = False
        await repl.aclose()


async def test_repl_shutdown_cancels_and_joins_owned_idle_command(tmp_path):
    repl = make_repl(tmp_path)
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def command(_text, *_args):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
    repl.command_processor.handle_command = command
    task = asyncio.create_task(repl.process_input("/checkpoint apply deliberate-test"))
    shutdown = None
    try:
        await entered.wait()
        shutdown = asyncio.create_task(repl.aclose())
        await asyncio.wait_for(cleaning.wait(), 1)
        assert not shutdown.done()
        release.set()
        await shutdown
        assert task.done()
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if shutdown is not None:
            await shutdown
