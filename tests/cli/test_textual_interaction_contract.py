"""Rendered UI-0.1 state/key contracts; these are not native/AT qualification."""

import asyncio

import pytest
from textual import events
from textual.widgets import Button, Static

from henchman.cli.textual_widgets import ChatPane, HenchmanTextArea, StatusBar
from henchman.providers.base import ToolCall
from tests.cli.ui_scenarios import (
    VIEWPORTS,
    InteractionApp,
    SlowTranscript,
    populate_history,
    settle_layout,
)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return InteractionApp(tmp_path)


@pytest.mark.parametrize("size", VIEWPORTS)
async def test_reading_history_survives_streams_until_explicit_live(app, size):
    async with app.run_test(size=size) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        chat.append_agent_chunk("lead", "Initial live text\n")
        await settle_layout(pilot)
        composer = app.query_one(HenchmanTextArea)
        assert app.query_one("#chat-navigation").region.bottom <= composer.region.y
        assert composer.region.bottom <= size[1]
        assert chat.content_region.height > 0
        composer.load_text("Unsent\nmultiline draft")
        composer.focus()
        scrolled = asyncio.Event()
        chat.scroll_to(y=20, animate=False, force=True, on_complete=scrolled.set)
        await asyncio.wait_for(scrolled.wait(), timeout=5)
        await settle_layout(pilot)
        before = chat.scroll_y
        assert before == 20
        stream = SlowTranscript(app)
        task = asyncio.create_task(stream.run())
        try:
            for source in ("lead", "worker", "lead"):
                await stream.emit(source, "Additional live content\n")
                await settle_layout(pilot)
            assert chat.scroll_y == before
            assert not chat.follow_live
            assert chat.new_activity
            assert "New activity" in str(app.query_one("#chat-follow-state", Static).render())
            assert composer.text == "Unsent\nmultiline draft"
            assert app.focused is composer
            await pilot.press("alt+end")
            await pilot.pause()
            assert chat.follow_live and not chat.new_activity
            assert chat.scroll_y == chat.max_scroll_y
            assert composer.text == "Unsent\nmultiline draft"
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_expansion_resize_search_and_keyboard_return_preserve_reading_anchor(app):
    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        card = chat.add_tool_message(tool_call=ToolCall("read-1", "read_file", {"path": "long.py"}))
        card._result_text = "Retained tool evidence\n" * 30
        card._update_renderable()
        populate_history(chat)
        await settle_layout(pilot)
        scrolled = asyncio.Event()
        card.scroll_visible(top=True, animate=False, on_complete=scrolled.set)
        await asyncio.wait_for(scrolled.wait(), timeout=5)
        await settle_layout(pilot)
        card.toggle_expansion()
        await settle_layout(pilot)
        assert not chat.follow_live
        offset = card.region.y - chat.content_region.y
        await pilot.resize_terminal(80, 24)
        chat.append_agent_chunk("worker", "A later update\n")
        await settle_layout(pilot)
        assert card._is_expanded
        assert card.region.y - chat.content_region.y == offset
        assert card._result_text == "Retained tool evidence\n" * 30
        await pilot.resize_terminal(160, 50)
        await settle_layout(pilot)
        assert card.region.y - chat.content_region.y == offset
        button = app.query_one("#chat-return-live", Button)
        button.focus()
        await pilot.press("enter")
        await pilot.pause()
        assert chat.follow_live
        assert chat.scroll_y == chat.max_scroll_y


async def test_enter_newline_paste_and_history_keep_one_multiline_draft(app):
    async with app.run_test(size=(80, 24)) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.focus()
        app.post_message(events.Paste("first line\nsecond line\n"))
        await pilot.pause()
        assert composer.text == "first line\nsecond line\n"
        assert not app.submitted
        await pilot.press("shift+enter", "ctrl+j")
        await pilot.pause()
        assert composer.text == "first line\nsecond line\n\n\n"
        await pilot.press("enter")
        await pilot.pause()
        assert app.submitted == ["first line\nsecond line"]
        assert composer.text == ""
        composer.load_text("draft\nretained")
        app._navigate_history(-1)
        app._navigate_history(1)
        assert composer.text == "draft\nretained"
        await pilot.press("ctrl+enter")
        await pilot.pause()
        assert app.submitted == ["first line\nsecond line", "draft\nretained"]


async def test_composer_escape_acknowledges_before_cleanup_and_keeps_draft(app, monkeypatch):
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
    async with app.run_test(size=(80, 24)) as pilot:
        worker = app.process_user_input("Work")
        await asyncio.wait_for(started.wait(), 2)
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Keep this\ndraft")
        composer.focus()
        try:
            await pilot.press("escape")
            await pilot.pause()
            assert cleanup.is_set()
            assert app.is_processing
            assert app.query_one(StatusBar).status_text == "Cancelling..."
            assert composer.text == "Keep this\ndraft"
        finally:
            release.set()
            if not cleanup.is_set():
                app.current_agent_task.cancel()
            await asyncio.wait_for(worker.wait(), 2)
        assert not app.is_processing
        assert composer.text == "Keep this\ndraft"


async def test_history_keyboard_controls_do_not_steal_composer_focus(app):
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        await pilot.pause()
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("draft")
        composer.focus()
        await pilot.press("alt+pageup")
        await pilot.pause()
        assert not chat.follow_live
        assert chat.scroll_y < chat.max_scroll_y
        assert app.focused is composer
        assert composer.text == "draft"


async def test_user_scroll_wins_over_an_already_scheduled_live_refresh(app):
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        await pilot.pause()
        chat.append_agent_chunk("worker", "Queued for the next rendered frame")
        chat.scroll_to(y=20, animate=False, force=True, immediate=True)
        await pilot.pause()
        assert chat.scroll_y == 20
        assert not chat.follow_live


async def test_mouse_and_search_hold_until_explicit_end(app):
    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        await pilot.pause()
        await pilot._post_mouse_events([events.MouseScrollUp], chat, offset=(10, 5))
        await pilot.pause()
        assert not chat.follow_live
        assert chat.scroll_y < chat.max_scroll_y
        app._perform_search("module_10.py")
        app._current_match_index = 0
        app._scroll_to_match()
        await pilot.pause()
        position = chat.scroll_y
        chat.append_agent_chunk("worker", "New chunk while searching\n")
        await pilot.pause()
        assert chat.scroll_y == position
        chat.scroll_to(y=chat.max_scroll_y, animate=False)
        await pilot.pause()
        assert not chat.follow_live
        chat.focus()
        await pilot.press("end")
        await pilot.pause()
        assert chat.follow_live and not chat.new_activity
        assert chat.scroll_y == chat.max_scroll_y
