"""Mouse preference reaches the driver; Pilot does not qualify host gestures."""

from pathlib import Path

import pytest
from textual.widgets import Label

from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.cli.textual_mixins import _NullProvider
from henchman.cli.textual_screens import HelpScreen
from henchman.cli.textual_widgets import ChatPane, HenchmanTextArea
from henchman.config.runtime import RuntimeSettingsState
from henchman.config.schema import Settings
from tests.cli.ui_scenarios import InteractionApp, populate_history, settle_layout


@pytest.fixture(autouse=True)
def isolated_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class MouseSettingsApp(InteractionApp):
    """Reuse the actual layout/actions with external services disabled."""

    def __init__(self, root: Path, settings: Settings, *, state: RuntimeSettingsState | None = None) -> None:
        HenchmanTextualApp.__init__(
            self, provider=_NullProvider(), settings=settings, settings_state=state,
            config=TextualConfig(auto_save=False, history_file=root / "history"),
        )
        self.submitted = []


@pytest.mark.parametrize("capture", [None, False, True])
async def test_mounted_driver_honors_effective_mouse_setting(tmp_path, capture):
    settings = Settings() if capture is None else Settings(ui={"mouse_capture": capture})
    app = MouseSettingsApp(tmp_path, settings)
    async with app.run_test():
        assert app._driver._mouse is (capture is not False)


async def test_held_runtime_settings_win_at_driver_start(tmp_path):
    state = RuntimeSettingsState.from_settings(Settings())
    app = MouseSettingsApp(tmp_path, Settings(ui={"mouse_capture": True}), state=state)
    state.update({"ui": {"mouse_capture": False}})
    async with app.run_test():
        assert app.settings is state.settings
        assert app._driver._mouse is False


async def test_mouse_setting_change_applies_to_the_next_tui_driver(tmp_path):
    state = RuntimeSettingsState.from_settings(Settings(ui={"mouse_capture": False}))
    app = MouseSettingsApp(tmp_path, state.settings, state=state)
    async with app.run_test():
        driver = app._driver
        assert driver._mouse is False
        state.update({"ui": {"mouse_capture": True}})
        assert app._driver is driver and driver._mouse is False
    restarted = MouseSettingsApp(tmp_path, state.settings, state=state)
    async with restarted.run_test():
        assert restarted._driver._mouse is True


@pytest.mark.parametrize("capture", [False, True])
async def test_explicit_api_mouse_false_remains_restrictive(tmp_path, capture):
    app = MouseSettingsApp(tmp_path, Settings(ui={"mouse_capture": capture}))
    observed = []

    async def inspect(pilot):
        observed.append(pilot.app._driver._mouse)
        app.exit()

    await app.run_async(headless=True, mouse=False, auto_pilot=inspect)
    assert observed == [False]


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_mouse_disabled_keeps_keyboard_reading_selection_and_draft(tmp_path, size):
    app = MouseSettingsApp(tmp_path, Settings(ui={"mouse_capture": False}))
    async with app.run_test(size=size) as pilot:
        assert app._driver._mouse is False
        chat = app.query_one(ChatPane)
        populate_history(chat)
        await settle_layout(pilot)
        composer = app.query_one(HenchmanTextArea)
        draft = "first\nsecond"
        composer.load_text(draft)
        composer.focus()
        await pilot.press("f6")
        assert composer.selected_text == "first"
        await pilot.press("f7")
        assert composer.selected_text == draft
        await pilot.press("alt+pageup")
        await settle_layout(pilot)
        assert not chat.follow_live and chat.scroll_y < chat.max_scroll_y
        position = chat.scroll_y
        chat.append_agent_chunk("worker", "New output while reading\n")
        await settle_layout(pilot)
        assert chat.scroll_y == position and chat.new_activity
        await pilot.press("alt+pagedown")
        await settle_layout(pilot)
        assert chat.scroll_y >= position and not chat.follow_live
        await pilot.press("alt+end")
        await settle_layout(pilot)
        assert chat.follow_live and chat.scroll_y == chat.max_scroll_y
        assert composer.text == draft and composer.selected_text == draft
        assert app.focused is composer and app.submitted == []


async def test_help_exposes_keyboard_transcript_fallback_with_capture_disabled(tmp_path):
    app = MouseSettingsApp(tmp_path, Settings(ui={"mouse_capture": False}))
    async with app.run_test(size=(80, 24)) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Unsubmitted\ndraft")
        composer.focus()
        await pilot.press("f1")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        labels = "\n".join(str(item.render()) for item in app.screen.query(Label))
        assert "Alt+PageUp" in labels and "Alt+PageDown" in labels
        assert "Alt+End" in labels and "Return to live" in labels
        assert "Ctrl+F" in labels and "F3" in labels and "Shift+F3" in labels
        await pilot.press("escape")
        await pilot.pause()
        assert composer.text == "Unsubmitted\ndraft"
        assert app.focused is composer and app.submitted == []
