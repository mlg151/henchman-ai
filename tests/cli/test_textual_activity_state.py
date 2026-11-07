"""Mounted lifecycle status follows owners, never incidental agent prose."""

import asyncio

import pytest
from textual.screen import ModalScreen
from textual.widgets import Button, Input

from henchman.cli.textual_messages import AgentStatusMessage
from henchman.cli.textual_widgets import HenchmanTextArea, StatusBar
from henchman.tools.base import ConfirmationRequest
from tests.cli.ui_scenarios import InteractionApp, settle_layout


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return InteractionApp(tmp_path)


def status(app):
    return str(app.query_one(StatusBar).render())


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_question_state_and_keyboard_action_use_existing_decision(app, size):
    async with app.run_test(size=size) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("keep\nmy draft")
        question = asyncio.create_task(app._textual_question("Choose a target"))
        await settle_layout(pilot)
        original = app.screen
        assert "Waiting for answer" in status(app)
        assert "F4" in status(app)
        assert "F4" in app.query_one(StatusBar).render_line(0).text
        app.screen.query_one("#question-cancel", Button).focus()
        await pilot.press("f4")
        await settle_layout(pilot)
        assert app.screen is original and len(app.screen_stack) == 2
        assert app.focused is original.query_one(Input) and not question.done()
        assert composer.text == "keep\nmy draft"
        original.query_one(Input).value = "exact answer"
        await pilot.press("enter")
        assert await question == "exact answer"
        await settle_layout(pilot)
        assert "Idle" in status(app)


async def test_approval_action_does_not_approve_and_preserves_overlay(app):
    async with app.run_test() as pilot:
        approval = asyncio.create_task(app._textual_confirm(ConfirmationRequest("shell", "Run check")))
        await settle_layout(pilot)
        original = app.screen
        assert "Waiting for approval" in status(app)
        overlay = ModalScreen()
        await app.push_screen(overlay)
        await pilot.press("f4")
        await settle_layout(pilot)
        assert app.screen is overlay and not approval.done()
        await overlay.dismiss()
        await settle_layout(pilot)
        await pilot.press("f4")
        await settle_layout(pilot)
        assert app.screen is original and not approval.done()
        await pilot.press("n")
        assert await approval is False


async def test_cancellation_remains_authoritative_until_joined_cleanup(app, monkeypatch):
    started, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def route(_text, _chat):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleanup.set()
            await release.wait()
            raise
    monkeypatch.setattr(app, "_route_input", route)
    async with app.run_test() as pilot:
        worker = app.process_user_input("work")
        await asyncio.wait_for(started.wait(), 3)
        try:
            assert "Running" in status(app)
            app.action_cancel_or_clear()
            await asyncio.wait_for(cleanup.wait(), 3)
            app.post_message(AgentStatusMessage("Background work completed", "other"))
            await settle_layout(pilot)
            assert "Cancelling" in status(app) and "completed" not in status(app)
        finally:
            release.set()
        await worker.wait()
        await settle_layout(pilot)
        assert "Cancelled" in status(app)


async def test_terminal_error_survives_provider_refresh_and_late_status(app, monkeypatch):
    async def failed(_text, _chat):
        raise ValueError("actual failure")
    monkeypatch.setattr(app, "_route_input", failed)
    async with app.run_test() as pilot:
        worker = app.process_user_input("work")
        await worker.wait()
        app._update_status_bar()
        app.post_message(AgentStatusMessage("Everything succeeded", "late"))
        await settle_layout(pilot)
        assert "Stopped with error" in status(app)
        assert "succeeded" not in status(app)


async def test_serial_prompt_queue_and_cancelled_overlay_never_advertise_expired_answer(app):
    async with app.run_test() as pilot:
        first = asyncio.create_task(app._textual_question("First"))
        await settle_layout(pilot)
        second = asyncio.create_task(app._textual_question("Second"))
        await settle_layout(pilot)
        assert "1 queued decision" in status(app)
        overlay = ModalScreen()
        await app.push_screen(overlay)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        await settle_layout(pilot)
        assert "Close the current dialog" in status(app)
        assert "Waiting for answer" not in status(app)
        await pilot.press("f4")
        assert app.screen is overlay and not second.done()
        await overlay.dismiss()
        await settle_layout(pilot)
        assert "Waiting for answer" in status(app)
        await pilot.press("escape")
        assert await second is None


async def test_stale_prompt_removal_cannot_clear_newer_question(app):
    async with app.run_test() as pilot:
        first = asyncio.create_task(app._textual_question("First"))
        await settle_layout(pilot)
        stale = app.screen.removed_callback
        await pilot.press("escape")
        assert await first is None
        second = asyncio.create_task(app._textual_question("Second"))
        await settle_layout(pilot)
        current = app.screen
        stale()
        await settle_layout(pilot)
        assert "Waiting for answer" in status(app)
        await pilot.press("f4")
        assert app.screen is current and app.focused is current.query_one(Input)
        await pilot.press("escape")
        assert await second is None


async def test_late_worker_completion_cannot_clear_newer_owner(app):
    from henchman.cli.textual_activity_state import activity_for

    async with app.run_test() as pilot:
        state = activity_for(app)
        old = state.begin()
        state.finish(old, "idle")
        current = state.begin()
        state.finish(old, "failed")
        await settle_layout(pilot)
        assert "Running" in status(app) and "error" not in status(app)
        state.cancel(current)
        state.finish(old, "idle")
        await settle_layout(pilot)
        assert "Cancelling" in status(app)
        state.finish(current, "cancelled")


async def test_cancel_queued_question_keeps_active_decision_and_count_truthful(app):
    async with app.run_test() as pilot:
        first = asyncio.create_task(app._textual_question("First"))
        await settle_layout(pilot)
        second = asyncio.create_task(app._textual_question("Second"))
        await settle_layout(pilot)
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
        await settle_layout(pilot)
        assert "Waiting for answer" in status(app) and "queued decision" not in status(app)
        await pilot.press("escape")
        assert await first is None


async def test_failed_prompt_mount_clears_wait_and_next_prompt_works(app, monkeypatch):
    async with app.run_test() as pilot:
        with monkeypatch.context() as patch:
            def fail(*_args, **_kwargs):
                raise RuntimeError("UI unavailable")
            patch.setattr(app, "push_screen", fail)
            with pytest.raises(RuntimeError, match="UI unavailable"):
                await app._textual_question("Failed mount")
        await settle_layout(pilot)
        assert "Idle" in status(app) and not app.query_one(StatusBar).decision_action
        task = asyncio.create_task(app._textual_question("Next"))
        await settle_layout(pilot)
        assert "Waiting for answer" in status(app)
        await pilot.press("escape")
        assert await task is None


async def test_shutdown_wins_over_prompt_cleanup_and_late_worker_completion(app):
    from henchman.cli.textual_activity_state import activity_for

    async with app.run_test() as pilot:
        state = activity_for(app)
        owner = state.begin()
        first = asyncio.create_task(app._textual_question("First"))
        second = asyncio.create_task(app._textual_question("Second"))
        await settle_layout(pilot)
        app._cleanup_confirm_futures()
        for task in (first, second):
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 3)
        state.finish(owner, "failed")
        app.post_message(AgentStatusMessage("Running another task", "late"))
        await settle_layout(pilot)
        assert "Closing" in status(app)
        assert not app.query_one(StatusBar).decision_action


async def test_queued_followup_does_not_replace_pending_prompt_or_claim_immediate_execution(app, monkeypatch):
    seen = []
    async def route(text, _chat):
        seen.append(text)
        if text == "first":
            await app._textual_question("Question")
    monkeypatch.setattr(app, "_route_input", route)
    async with app.run_test() as pilot:
        worker = app.process_user_input("first")
        await settle_layout(pilot)
        queued = app.process_user_input("second")
        await queued.wait()
        await settle_layout(pilot)
        assert "Waiting for answer" in status(app)
        assert seen == ["first"]
        await pilot.press("escape")
        await worker.wait()
        await settle_layout(pilot)
        assert seen == ["first", "second"] and "Idle" in status(app)


async def test_actual_run_failure_events_set_terminal_status_without_self_certification(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from henchman.cli.textual_app import HenchmanTextualApp
    from henchman.cli.textual_config import TextualConfig
    from henchman.config.schema import Settings
    from henchman.core.events import AgentEvent, EventType

    monkeypatch.chdir(tmp_path)
    provider = MagicMock()
    provider.name = "test"
    runtime = HenchmanTextualApp(provider=provider, settings=Settings(),
        config=TextualConfig(auto_save=False, history_file=tmp_path / "history"))
    async with runtime.run_test(size=(80, 24)) as pilot:
        async def failed(_text):
            yield AgentEvent(EventType.AGENT_COMPLETED, {"scope": "run", "status": "failed", "agent": "lead"}, "orchestrator")
        monkeypatch.setattr(runtime.core_context.orchestrator, "run", failed)
        monkeypatch.setattr(runtime, "_route_input", runtime._run_orchestrator)
        await runtime.process_user_input("work").wait()
        await settle_layout(pilot)
        assert "Stopped with error" in status(runtime)
        async def finished(_text):
            yield AgentEvent(EventType.AGENT_COMPLETED, {"scope": "run", "status": "completed", "agent": "lead", "summary": "Everything verified"}, "orchestrator")
        monkeypatch.setattr(runtime.core_context.orchestrator, "run", finished)
        await runtime.process_user_input("new work").wait()
        await settle_layout(pilot)
        assert "Idle" in status(runtime)
        assert "verified" not in status(runtime).lower()


async def test_prompt_timeout_clears_action_without_fabricating_an_answer(app):
    async with app.run_test() as pilot:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(app._textual_question("Timed question"), 0.1)
        await settle_layout(pilot)
        assert "Idle" in status(app)
        assert not app.query_one(StatusBar).decision_action
        assert len(app.screen_stack) == 1


async def test_lifecycle_label_preserves_explicit_search_feedback(app):
    async with app.run_test(size=(80, 24)) as pilot:
        app.action_search()
        await settle_layout(pilot)
        assert "Idle" in status(app) and "Search:" in status(app)
        app.action_clear_search()
        await settle_layout(pilot)
        assert "Idle" in status(app) and "Search:" not in status(app)


async def test_explicit_status_notice_uses_current_credential_projection(app):
    from henchman.cli.evidence import runtime_evidence_redactor

    async with app.run_test() as pilot:
        app.action_search()
        app._search_query = "later-known-status-credential"
        app._update_search_status()
        await settle_layout(pilot)
        assert "later-known-status-credential" in status(app)
        runtime_evidence_redactor(app).register_secret("later-known-status-credential")
        app.query_one(StatusBar).refresh()
        await settle_layout(pilot)
        assert "later-known-status-credential" not in status(app)
