"""Mounted queue controls use real workflow revisions, never display text."""

import asyncio
import sqlite3
from threading import Event

import pytest
from textual.widgets import Button, OptionList, Static, TextArea

from henchman.cli.textual_queue import QueueScreen
from henchman.cli.textual_widgets import HenchmanTextArea
from tests.cli.ui_scenarios import InteractionApp, settle_layout
from tests.core.test_session_workflow import controller


@pytest.fixture
def queue_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runtime, session, _ = controller(tmp_path)
    app = InteractionApp(tmp_path)
    monkeypatch.setattr(app, "_workflow", lambda: runtime)
    monkeypatch.setattr(app, "_goal_session", lambda: session)
    app._evidence_redactor = session.evidence_redactor
    return app, runtime, session


async def ready(pilot):
    await settle_layout(pilot)
    screen = pilot.app.screen
    if isinstance(screen, QueueScreen) and screen._action_task is not None:
        await asyncio.wait_for(asyncio.shield(screen._action_task), 5)
    await settle_layout(pilot)
    return screen


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_f9_edit_holds_exact_text_and_back_preserves_composer(queue_app, size):
    app, runtime, _ = queue_app
    item = runtime.submit("original request")
    runtime.hold_pending()
    async with app.run_test(size=size) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Unsent\ncomposer draft")
        composer.focus()
        await pilot.press("f9")
        screen = await ready(pilot)
        assert isinstance(screen, QueueScreen)
        await pilot.press("enter")
        await ready(pilot)
        assert "Held" in screen.query_one("#queue-content", TextArea).text
        screen.query_one("#queue-edit", Button).focus()
        await pilot.press("enter")
        editor = screen.query_one("#queue-content", TextArea)
        assert editor.text == "original request" and not editor.read_only
        editor.load_text('Exact  spacing\nand "quotes"')
        screen.query_one("#queue-save", Button).focus()
        await pilot.press("enter")
        await ready(pilot)
        current = runtime.report().state.inputs[0]
        assert current.id == item.id and current.text == 'Exact  spacing\nand "quotes"'
        assert runtime.next_input() is None
        assert screen.query_one("#queue-back", Button).region.bottom <= size[1]
        await pilot.press("escape", "escape")
        await ready(pilot)
        assert app.screen is not screen
        assert composer.text == "Unsent\ncomposer draft" and app.focused is composer


async def test_send_is_explicit_once_and_executes_original_live_sensitive_input(queue_app):
    app, runtime, session = queue_app
    secret = "live-queue-secret"
    session.evidence_redactor.register_secret(secret)
    runtime.submit(f"use {secret} exactly")
    runtime.hold_pending()
    async with app.run_test() as pilot:
        await pilot.press("f9", "enter")
        screen = await ready(pilot)
        if screen._stage == "list":
            await pilot.press("enter")
        assert secret not in screen.query_one("#queue-content", TextArea).text
        assert app.submitted == []
        screen.action_send()
        screen.action_send()
        await ready(pilot)
        worker = getattr(app, "current_agent_task", None)
        if worker is not None:
            await asyncio.wait_for(asyncio.shield(worker), 3)
        assert app.submitted == [f"use {secret} exactly"]
        assert runtime.report().state.inputs[0].state == "completed"


async def test_stale_editor_never_overwrites_new_revision_and_retains_unsaved_edit(queue_app, tmp_path):
    from henchman.core.session_data import session_from_json

    app, runtime, session = queue_app
    item = runtime.submit("original")
    runtime.hold_pending()
    async with app.run_test() as pilot:
        await pilot.press("f9")
        screen = await ready(pilot)
        await pilot.press("enter")
        screen.action_edit()
        editor = screen.query_one("#queue-content", TextArea)
        editor.load_text("my unsaved replacement")
        other, _, _ = controller(tmp_path, session=session_from_json(session.to_json()))
        other.edit(item.id, item.revision, "other runtime edit")
        screen.action_save()
        await ready(pilot)
        assert runtime.report().state.inputs[0].text == "other runtime edit"
        assert "revision_conflict" in str(screen.query_one("#queue-status", Static).render())
        assert editor.text == "my unsaved replacement"
        assert screen.query_one("#queue-save", Button).disabled


async def test_reorder_and_remove_do_not_rearm_or_dispatch(queue_app):
    app, runtime, _ = queue_app
    first = runtime.submit("first")
    second = runtime.submit("second")
    runtime.hold_pending()
    async with app.run_test() as pilot:
        await pilot.press("f9")
        screen = await ready(pilot)
        screen.query_one(OptionList).highlighted = 1
        await pilot.press("enter")
        screen.action_move(-1)
        await ready(pilot)
        records = sorted(runtime.report().state.inputs, key=lambda item: item.order)
        assert [item.id for item in records] == [second.id, first.id]
        assert not runtime.queue_view().eligible
        screen.action_remove()
        assert runtime.report().state.inputs[1].state == "queued"
        screen.action_confirm_remove()
        await ready(pilot)
        assert next(item for item in runtime.report().state.inputs if item.id == second.id).state == "cancelled"
        assert app.submitted == []
        assert "removed" in str(screen.query_one("#queue-status", Static).render()).lower()


async def test_f9_keeps_pending_question_current_and_draft_untouched(queue_app):
    app, runtime, _ = queue_app
    runtime.submit("pending input")
    runtime.hold_pending()
    async with app.run_test() as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("draft")
        answer = asyncio.create_task(app._textual_question("Keep this decision"))
        await settle_layout(pilot)
        question = app.screen
        await pilot.press("f9")
        await settle_layout(pilot)
        assert app.screen is question and not answer.done()
        assert composer.text == "draft"
        await pilot.press("escape")
        assert await answer is None


async def test_queue_rotation_reprojects_list_and_evidence_without_editing_input(queue_app):
    app, runtime, session = queue_app
    secret = "newly-known-queue-canary"
    runtime.submit(f"original {secret}")
    runtime.hold_pending()
    async with app.run_test() as pilot:
        await pilot.press("f9")
        screen = await ready(pilot)
        await pilot.press("enter")
        session.evidence_redactor.register_secret(secret)
        screen._project_current()
        await settle_layout(pilot)
        assert secret not in screen.query_one("#queue-content", TextArea).text
        assert secret not in str(screen.query_one(OptionList).get_option_at_index(0).prompt)
        screen.action_edit()
        assert screen.query_one("#queue-content", TextArea).text == ""
        assert runtime.next_input() is None


async def test_back_joins_waiting_store_and_never_dispatches_after_screen_closes(queue_app, monkeypatch, tmp_path):
    app, runtime, _ = queue_app
    item = runtime.submit("held")
    runtime.hold_pending()
    store = next(iter(runtime._bindings.values())).journal.store
    entered = Event()
    original = store._change

    def wait(*args, **kwargs):
        entered.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "_change", wait)
    async with app.run_test() as pilot:
        await pilot.press("f9")
        screen = await ready(pilot)
        await pilot.press("enter")
        lock = sqlite3.connect(tmp_path / "ops.db")
        lock.execute("BEGIN IMMEDIATE")
        screen.action_send()
        closing = None
        try:
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 3), 4)
            closing = asyncio.create_task(screen.action_back())
            await asyncio.sleep(0)
            if closing.done():
                assert screen._action_task.done()
            else:
                assert screen in app.screen_stack
        finally:
            lock.rollback()
            lock.close()
        await asyncio.wait_for(closing, 4)
        await settle_layout(pilot)
        assert screen not in app.screen_stack and app.submitted == []
        assert runtime.report().state.inputs[0].revision == item.revision
        assert runtime.next_input() is None


async def test_pending_decision_revokes_waiting_queue_action_even_after_prompt_closes(queue_app, monkeypatch, tmp_path):
    app, runtime, _ = queue_app
    item = runtime.submit("held")
    runtime.hold_pending()
    store = next(iter(runtime._bindings.values())).journal.store
    entered = Event()
    original = store._change

    def wait(*args, **kwargs):
        entered.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(store, "_change", wait)
    async with app.run_test() as pilot:
        await pilot.press("f9")
        screen = await ready(pilot)
        await pilot.press("enter")
        lock = sqlite3.connect(tmp_path / "ops.db")
        lock.execute("BEGIN IMMEDIATE")
        screen.action_send()
        try:
            assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 3), 4)
            answer = asyncio.create_task(app._textual_question("Actual pending question"))
            await settle_layout(pilot)
            await pilot.press("escape")
            assert await answer is None
            await settle_layout(pilot)
            assert app.screen is screen
        finally:
            lock.rollback()
            lock.close()
        await asyncio.gather(screen._action_task, return_exceptions=True)
        await settle_layout(pilot)
        assert app.submitted == []
        assert runtime.report().state.inputs[0].revision == item.revision
        assert screen.query_one("#queue-send", Button).disabled


async def test_screen_unmount_joins_storage_and_does_not_publish_dispatch(queue_app):
    app, runtime, _ = queue_app
    item = runtime.submit("held")
    runtime.hold_pending()
    store = next(iter(runtime._bindings.values())).journal.store
    reached, release = Event(), Event()

    def checkpoint(stage):
        if stage == "queue_control:before_commit":
            reached.set()
            assert release.wait(5)

    store._checkpoint = checkpoint
    async with app.run_test() as pilot:
        await pilot.press("f9")
        screen = await ready(pilot)
        await pilot.press("enter")
        screen.action_send()
        closing = None
        try:
            assert await asyncio.wait_for(asyncio.to_thread(reached.wait, 3), 4)

            async def pop():
                await app.pop_screen()

            closing = asyncio.create_task(pop())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not closing.done()
        finally:
            release.set()
            if closing is not None:
                await asyncio.wait_for(closing, 4)
        await settle_layout(pilot)
        assert screen._action_task.done()
        assert runtime.report().state.inputs[0].revision == item.revision
        assert runtime.next_input() is None and app.submitted == []


async def test_back_requires_discard_decision_and_editor_never_submits_composer(queue_app):
    app, runtime, _ = queue_app
    runtime.submit("original")
    runtime.hold_pending()
    async with app.run_test() as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("untouched composer")
        await pilot.press("f9")
        screen = await ready(pilot)
        await pilot.press("enter")
        screen.action_edit()
        editor = screen.query_one("#queue-content", TextArea)
        editor.load_text("unsaved replacement")
        await pilot.press("escape")
        assert screen._stage == "discard-edit" and editor.text == "unsaved replacement"
        await pilot.press("escape")
        assert screen._stage == "edit" and editor.text == "unsaved replacement"
        editor.focus()
        await pilot.press("ctrl+enter")
        await ready(pilot)
        assert runtime.report().state.inputs[0].text == "unsaved replacement"
        assert composer.text == "untouched composer" and not app.submitted


async def test_held_after_restore_and_unknown_effects_are_not_replayed(queue_app):
    app, runtime, session = queue_app
    runtime.submit("active original")
    runtime.next_input()
    runtime.interrupt()
    runtime.submit("pending original")
    runtime.attach(session, restored=True)
    async with app.run_test() as pilot:
        await pilot.press("f9")
        screen = await ready(pilot)
        await pilot.press("enter")
        assert "Uncertain effects" in screen.query_one("#queue-content", TextArea).text
        assert screen.query_one("#queue-send", Button).disabled
        screen.action_send()
        await ready(pilot)
        assert not app.submitted and runtime.next_input() is None


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_queue_shortcut_preserves_composer_line_and_document_selection(queue_app, size):
    app, runtime, _ = queue_app
    runtime.submit("held")
    runtime.hold_pending()
    async with app.run_test(size=size) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("first line\nsecond line")
        composer.move_cursor((0, 0))
        composer.focus()
        await pilot.press("f6")
        assert composer.selected_text.startswith("first line")
        await pilot.press("f7")
        assert composer.selected_text == "first line\nsecond line"
        assert len(app.screen_stack) == 1
        await pilot.press("f9")
        screen = await ready(pilot)
        assert isinstance(screen, QueueScreen)
        await pilot.press("escape")
        await ready(pilot)
        assert composer.selected_text == "first line\nsecond line"
        assert app.focused is composer
