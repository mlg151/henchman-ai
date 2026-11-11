"""Mounted reduced motion behavior; no native or assistive-technology claim."""

import asyncio
from pathlib import Path

import pytest
from textual.screen import ModalScreen
from textual.widgets import Input, LoadingIndicator, TextArea

from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.cli.textual_messages import AgentContentMessage, AgentFinishedMessage
from henchman.cli.textual_mixins import _NullProvider
from henchman.cli.textual_widgets import ChatMessage, ChatPane, HenchmanTextArea, StatusBar
from henchman.config.runtime import RuntimeSettingsState
from henchman.config.schema import Settings
from henchman.tools.base import ConfirmationRequest
from tests.cli.ui_scenarios import InteractionApp, settle_layout


@pytest.fixture(autouse=True)
def isolated_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class MotionSettingsApp(InteractionApp):
    """Actual app layout and lifecycle without external runtime services."""

    def __init__(self, root: Path, settings: Settings, *, state: RuntimeSettingsState | None = None) -> None:
        HenchmanTextualApp.__init__(
            self, provider=_NullProvider(), settings=settings, settings_state=state,
            config=TextualConfig(auto_save=False, history_file=root / "history"),
        )
        self.submitted = []


@pytest.mark.parametrize("reduced", [None, False, True])
async def test_startup_reduced_motion_preserves_normal_defaults(tmp_path, reduced):
    settings = Settings() if reduced is None else Settings(ui={"reduced_motion": reduced})
    app = MotionSettingsApp(tmp_path, settings)
    original_level = app.animation_level
    async with app.run_test():
        assert app.animation_level == ("none" if reduced else original_level)
        assert app.query_one(HenchmanTextArea).cursor_blink is not bool(reduced)


@pytest.mark.parametrize("level", ["basic", "none"])
async def test_false_setting_does_not_override_caller_animation_restriction(tmp_path, level):
    app = MotionSettingsApp(tmp_path, Settings())
    app.animation_level = level
    async with app.run_test():
        assert app.animation_level == level


async def test_prelaunch_settings_update_is_captured_and_later_update_waits(tmp_path):
    state = RuntimeSettingsState.from_settings(Settings())
    app = MotionSettingsApp(tmp_path, state.settings, state=state)
    state.update({"ui": {"reduced_motion": True}})
    async with app.run_test() as pilot:
        assert app.animation_level == "none"
        state.update({"ui": {"reduced_motion": False}})
        assert app.animation_level == "none"
        question = asyncio.create_task(app._textual_question("Still reduced in this TUI?"))
        try:
            await settle_layout(pilot)
            assert app.screen.query_one(Input).cursor_blink is False
        finally:
            await pilot.press("escape")
            assert await question is None
    restarted = MotionSettingsApp(tmp_path, state.settings, state=state)
    expected = restarted.animation_level
    async with restarted.run_test():
        assert restarted.animation_level == expected
        assert restarted.query_one(HenchmanTextArea).cursor_blink is True


async def test_framework_animation_reaches_final_state_without_duration_wait(tmp_path):
    app = MotionSettingsApp(tmp_path, Settings(ui={"reduced_motion": True}))
    async with app.run_test():
        completed = asyncio.Event()
        bar = app.query_one(StatusBar)
        bar.styles.animate("opacity", 0.5, duration=60, on_complete=completed.set)
        await asyncio.wait_for(completed.wait(), timeout=2)
        assert bar.styles.opacity == 0.5


@pytest.mark.parametrize("reduced", [False, True])
async def test_actual_loading_overlay_stays_visible_and_blocks_input(tmp_path, reduced):
    app = MotionSettingsApp(tmp_path, Settings(ui={"reduced_motion": reduced}))
    async with app.run_test() as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Retain this draft")
        composer.focus()
        composer.loading = True
        await settle_layout(pilot)
        indicator = composer._cover_widget
        assert isinstance(indicator, LoadingIndicator)
        if reduced:
            assert str(indicator.render()) == "Loading..."
            assert indicator.auto_refresh is None
            assert indicator._auto_refresh_timer is None
        else:
            assert type(indicator) is LoadingIndicator
            assert indicator.auto_refresh == 1 / 16
        await pilot.press("x", "enter")
        assert composer.text == "Retain this draft" and app.submitted == []
        composer.loading = False
        await settle_layout(pilot)
        assert composer._cover_widget is None
        assert app.focused is composer and composer.text == "Retain this draft"


async def test_later_question_editor_and_approval_keep_focus_and_decision_semantics(tmp_path):
    app = MotionSettingsApp(tmp_path, Settings(ui={"reduced_motion": True}))
    async with app.run_test() as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Keep\nmy draft")
        question = asyncio.create_task(app._textual_question("Choose a target"))
        try:
            await settle_layout(pilot)
            field = app.screen.query_one(Input)
            assert app.focused is field and field.cursor_blink is False
            assert "Waiting for answer" in str(app.query_one(StatusBar).render())
            field.value = "chosen target"
            await pilot.press("enter")
            assert await question == "chosen target"
        finally:
            if not question.done():
                question.cancel()
                await asyncio.gather(question, return_exceptions=True)
        editor = TextArea("Editable evidence", id="later-editor")
        screen = ModalScreen()
        await app.push_screen(screen)
        await screen.mount(editor)
        editor.focus()
        await settle_layout(pilot)
        assert editor.cursor_blink is False and app.focused is editor
        await pilot.press("end", "!")
        assert editor.text == "Editable evidence!"
        await screen.dismiss()
        approval = asyncio.create_task(app._textual_confirm(ConfirmationRequest("shell", "Run check")))
        try:
            await settle_layout(pilot)
            assert not approval.done()
            assert "Waiting for approval" in str(app.query_one(StatusBar).render())
            await pilot.press("n")
            assert await approval is False
        finally:
            if not approval.done():
                approval.cancel()
                await asyncio.gather(approval, return_exceptions=True)
        await settle_layout(pilot)
        assert composer.text == "Keep\nmy draft" and app.focused is composer
        assert app.submitted == []


async def test_reduced_motion_keeps_streaming_and_owned_cancellation_status(tmp_path, monkeypatch):
    app = MotionSettingsApp(tmp_path, Settings(ui={"reduced_motion": True}))
    started, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def route(_text, _chat):
        app.post_message(AgentContentMessage("First ", "worker"))
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cleanup.set()
            await release.wait()
            app.post_message(AgentContentMessage("last", "worker"))
            app.post_message(AgentFinishedMessage("worker"))
            raise

    monkeypatch.setattr(app, "_route_input", route)
    async with app.run_test() as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Unsubmitted\ndraft")
        worker = app.process_user_input("work")
        try:
            await asyncio.wait_for(started.wait(), 3)
            await settle_layout(pilot)
            assert "First " in "".join(item._content_text for item in app.query_one(ChatPane).query(ChatMessage))
            assert "Running" in str(app.query_one(StatusBar).render())
            await pilot.press("escape")
            await asyncio.wait_for(cleanup.wait(), 3)
            await settle_layout(pilot)
            assert "Cancelling" in str(app.query_one(StatusBar).render())
        finally:
            release.set()
            await worker.wait()
        await settle_layout(pilot)
        assert "".join(
            item._content_text for item in app.query_one(ChatPane).query(ChatMessage)
            if "worker" in item._prefix
        ) == "First last"
        assert "Cancelled" in str(app.query_one(StatusBar).render())
        assert composer.text == "Unsubmitted\ndraft" and app.focused is composer
