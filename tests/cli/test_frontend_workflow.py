"""Public frontend queues retain intent and require recovery after interruption."""

import asyncio
from io import StringIO
from unittest.mock import Mock

import pytest
from rich.console import Console
from textual.widgets import TextArea

from henchman.cli.repl import Repl, ReplConfig
from henchman.core.session_data import session_from_json
from tests.cli.test_textual_background_goals import app as app_fixture

app = app_fixture


async def test_repl_interrupt_retains_input_and_pending_intent_without_restart_dispatch(tmp_path):
    repl = Repl(provider=Mock(), console=Console(file=StringIO()),
                config=ReplConfig(history_file=tmp_path / "history", auto_save=False))
    repl.settings.operations.persistence = "durable"
    session = repl.session_manager.create_session("project")
    repl.set_session(session)
    started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    seen = []

    async def agent(message):
        seen.append(message)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()

    repl._run_agent = agent
    repl._interactive_loop_active = True
    try:
        await repl.submit_agent_input("first")
        await started.wait()
        await repl.submit_agent_input("second")
        assert [item.state for item in session.workflow_runtime.report().state.inputs] == ["started", "queued"]
        worker = repl._turn_worker
        repl.interrupt_agent()
        await cleaning.wait()
        assert session.workflow_runtime.has_active_dispatch()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await worker
        await asyncio.sleep(0)
        assert [item.state for item in session.workflow_runtime.report().state.inputs] == ["outcome_unknown", "queued"]
        restored = session_from_json(session.to_json())
        repl.set_session(restored)
        repl._ensure_turn_worker()
        await asyncio.sleep(0)
        assert seen == ["first"]
        assert repl._turn_worker is None or repl._turn_worker.done()
    finally:
        repl._interactive_loop_active = False
        release.set()
        await repl.aclose()


async def test_textual_preserves_composer_when_acceptance_save_fails(app, monkeypatch):
    async with app.run_test(size=(100, 40)):
        session = app.core_context.session_manager.current
        def fail(_session):
            raise OSError("disk full")
        session.workflow_runtime.save_session = fail
        calls = []
        async def route(text, _chat):
            calls.append(text)
        monkeypatch.setattr(app, "_route_input", route)
        widget = app.query_one("#input", TextArea)
        widget.load_text("keep this draft")
        app.action_submit_message()
        await asyncio.sleep(0.1)
        assert widget.text == "keep this draft"
        assert not calls


async def test_textual_cancellation_retains_pending_input_and_no_auto_dispatch(app, monkeypatch):
    started, release, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()
    seen = []
    async def route(text, _chat):
        seen.append(text)
        started.set()
        try:
            await release.wait()
        finally:
            stopped.set()
    monkeypatch.setattr(app, "_route_input", route)
    async with app.run_test(size=(100, 40)):
        session = app.core_context.session_manager.current
        worker = app.process_user_input("first")
        await started.wait()
        widget = app.query_one("#input", TextArea)
        widget.load_text("/chat resume another-session")
        app.action_submit_message()
        assert widget.text == "/chat resume another-session"
        assert len(session.workflow_runtime.report().state.inputs) == 1
        app.query_one("#input", TextArea).load_text("second")
        app.action_submit_message()
        app.action_cancel_or_clear()
        await worker.wait()
        assert stopped.is_set()
        assert [item.state for item in session.workflow_runtime.report().state.inputs] == ["outcome_unknown", "queued"]
        assert seen == ["first"]


async def test_repl_idle_session_command_does_not_hold_its_own_dispatch_permit(tmp_path):
    repl = Repl(provider=Mock(), console=Console(file=StringIO()),
                config=ReplConfig(history_file=tmp_path / "history", auto_save=False))
    original = repl.session_manager.create_session("project")
    target = repl.session_manager.create_session("project")
    repl.set_session(original)
    async def switch(_text, *_args):
        repl.set_session(target)
        return True
    repl.command_processor.handle_command = switch
    repl._interactive_loop_active = True
    try:
        await repl.process_input("/chat resume target")
        if repl._turn_worker is not None:
            await repl._turn_worker
        assert repl.session_manager.current is target
    finally:
        repl._interactive_loop_active = False
        await repl.aclose()


async def test_textual_idle_session_command_does_not_hold_its_own_permit(app, monkeypatch):
    async with app.run_test(size=(100, 40)):
        manager = app.core_context.session_manager
        target = manager.create_session(manager.current.project_hash)
        async def switch(_text, _chat):
            app.set_session(target)
        monkeypatch.setattr(app, "_handle_command", switch)
        worker = app.process_user_input("/chat resume target")
        await worker.wait()
        assert manager.current is target


async def test_repl_interrupt_cancels_worker_even_when_goal_pause_save_fails(tmp_path):
    from henchman.core.goals import GoalService

    repl = Repl(provider=Mock(), console=Console(file=StringIO()),
                config=ReplConfig(history_file=tmp_path / "history", auto_save=False))
    session = repl.session_manager.create_session("project")
    repl.set_session(session)
    GoalService().start(session, "goal")
    started, stopped = asyncio.Event(), asyncio.Event()
    async def agent(_message):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    repl._run_agent = agent
    repl._interactive_loop_active = True
    try:
        await repl.submit_agent_input("first")
        await started.wait()
        session.workflow_runtime.save_session = lambda _session: (_ for _ in ()).throw(OSError("disk full"))
        repl.interrupt_agent()
        await asyncio.wait_for(stopped.wait(), 1)
    finally:
        session.workflow_runtime.save_session = lambda _session: None
        repl._interactive_loop_active = False
        await repl.aclose()
