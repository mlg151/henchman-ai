"""Rendered transcript density changes presentation, never runtime evidence."""

import asyncio
from pathlib import Path

import pytest
from textual.widgets import TextArea

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.textual_app import HenchmanTextualApp
from henchman.cli.textual_config import TextualConfig
from henchman.cli.textual_messages import (
    ToolActivityClosedMessage,
    ToolCallRequestMessage,
    ToolCallResultMessage,
)
from henchman.cli.textual_mixins import _NullProvider
from henchman.cli.textual_widgets import ChatPane, HenchmanTextArea, ToolMessage
from henchman.config.runtime import RuntimeSettingsState
from henchman.config.schema import Settings
from henchman.providers.base import ToolCall
from henchman.tools.base import ConfirmationRequest
from tests.cli.ui_scenarios import InteractionApp, populate_history, settle_layout

DENSITIES = ("compact", "normal", "detailed")


@pytest.fixture(autouse=True)
def isolated_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


class DensityApp(InteractionApp):
    """Production layout and message handling with no external services."""

    def __init__(self, root: Path, settings: Settings, *, state: RuntimeSettingsState | None = None) -> None:
        HenchmanTextualApp.__init__(
            self, provider=_NullProvider(), settings=settings, settings_state=state,
            config=TextualConfig(auto_save=False, history_file=root / "history"),
        )
        self.submitted = []


def request(app, identity="one", **arguments):
    app.post_message(ToolCallRequestMessage(
        ToolCall(identity, "write_file", arguments or {"path": "src/target.py"}),
        "worker", stream_id="density-stream",
    ))


def result(app, identity="one", **data):
    app.post_message(ToolCallResultMessage(
        {"tool_call_id": identity, "tool_name": "write_file", **data},
        "worker", stream_id="density-stream",
    ))


@pytest.mark.parametrize("density", [None, *DENSITIES])
@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_density_changes_rendered_spacing_and_initial_tool_details(tmp_path, density, size):
    settings = Settings() if density is None else Settings(ui={"detail_density": density})
    app = DensityApp(tmp_path, settings)
    async with app.run_test(size=size) as pilot:
        chat = app.query_one(ChatPane)
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Keep this\nmultiline draft")
        composer.move_cursor((1, 3))
        selection = composer.selection
        composer.focus()
        first = chat.add_user_message("One short message")
        second = chat.add_user_message("Another short message")
        request(app)
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        compact = density == "compact"
        assert first.region.height == (1 if compact else 3)
        assert second.virtual_region.y - first.virtual_region.bottom == (0 if compact else 1)
        assert card.content.display is (density == "detailed")
        assert "Requested" in str(card.header.render())
        assert "src/target.py" in str(card.header.render())
        assert "worker" in str(card.header.render())
        assert chat.follow_live
        assert app.focused is composer
        assert composer.text == "Keep this\nmultiline draft" and composer.selection == selection
        # The compatibility message path uses the same initial preference.
        legacy = chat.add_tool_message(tool_call=ToolCall("legacy", "read_file", {"path": "legacy.py"}))
        await settle_layout(pilot)
        assert legacy.content.display is (density == "detailed")


async def test_prelaunch_settings_are_captured_and_later_changes_need_new_tui(tmp_path):
    state = RuntimeSettingsState.from_settings(Settings())
    app = DensityApp(tmp_path, state.settings, state=state)
    state.update({"ui": {"detail_density": "detailed"}})
    async with app.run_test() as pilot:
        request(app, "before")
        await settle_layout(pilot)
        assert app.query_one(ToolMessage).content.display
        state.update({"ui": {"detail_density": "compact"}})
        request(app, "after")
        await settle_layout(pilot)
        assert all(card.content.display for card in app.query(ToolMessage))
        message = app.query_one(ChatPane).add_user_message("Still normal spacing")
        await settle_layout(pilot)
        assert message.region.height == 3
    restarted = DensityApp(tmp_path, state.settings, state=state)
    async with restarted.run_test() as pilot:
        request(restarted)
        await settle_layout(pilot)
        assert not restarted.query_one(ToolMessage).content.display
        message = restarted.query_one(ChatPane).add_user_message("Now compact")
        await settle_layout(pilot)
        assert message.region.height == 1


@pytest.mark.parametrize("density", DENSITIES)
@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_manual_expansion_and_reading_anchor_survive_stream_results_and_resize(tmp_path, density, size):
    app = DensityApp(tmp_path, Settings(ui={"detail_density": density}))
    async with app.run_test(size=size) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        chat.begin_agent_stream("earlier")
        request(app)
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        populate_history(chat)
        await settle_layout(pilot)
        card.focus()
        await pilot.press("space")
        await settle_layout(pilot)
        expanded = density != "detailed"
        assert card.content.display is expanded
        scrolled = asyncio.Event()
        card.scroll_visible(top=True, animate=False, on_complete=scrolled.set)
        await asyncio.wait_for(scrolled.wait(), 5)
        await settle_layout(pilot)
        offset = card.region.y - chat.content_region.y
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Unsent\nselection stays")
        composer.move_cursor((1, 5))
        selection = composer.selection
        composer.focus()
        chat.append_agent_chunk("earlier", "Earlier content grew\n" * 5)
        result(app, success=False, result="Retained failure\n" * 20)
        request(app, "later")
        await settle_layout(pilot)
        await pilot.resize_terminal(120 if size[0] == 80 else 80, size[1])
        await settle_layout(pilot)
        assert card.content.display is expanded
        assert card.region.y - chat.content_region.y == offset
        assert not chat.follow_live and chat.new_activity
        assert app.focused is composer and composer.selection == selection
        assert composer.text == "Unsent\nselection stays"
        assert "Failed" in str(card.header.render())
        assert "Retained failure" in card.activity.evidence(runtime_evidence_redactor(app))


@pytest.mark.parametrize("density", DENSITIES)
async def test_all_tool_states_remain_labelled_without_inventing_success(tmp_path, density):
    app = DensityApp(tmp_path, Settings(ui={"detail_density": density}))
    async with app.run_test() as pilot:
        for identity in ("success", "failure", "unknown", "repeated", "unfinished"):
            request(app, identity)
        result(app, "success", success=True, result="Succeeded output")
        result(app, "failure", success=False, result="Failed output")
        result(app, "unknown", result="Missing outcome")
        result(app, "repeated", success=True, result="First outcome")
        result(app, "repeated", success=True, result="Repeated outcome")
        app.post_message(ToolActivityClosedMessage("density-stream"))
        await settle_layout(pilot)
        cards = list(app.query(ToolMessage))
        assert [card.activity.outcome for card in cards] == ["Succeeded", "Failed", "Unknown", "Unknown", "Interrupted"]
        for card in cards:
            assert card.activity.outcome in str(card.header.render())
            assert "src/target.py" in str(card.header.render())
            assert "worker" in str(card.header.render())
        assert "effects may have occurred" in cards[-1].activity.evidence(runtime_evidence_redactor(app))
        assert "Requirements acceptance is not established" in cards[0].activity.evidence(runtime_evidence_redactor(app))


@pytest.mark.parametrize("density", DENSITIES)
async def test_bounded_evidence_and_keyboard_inspection_keep_current_redaction(tmp_path, monkeypatch, density):
    from henchman.cli import textual_tool_activity

    monkeypatch.setattr(textual_tool_activity, "MAX_ENTRY_BYTES", 1024)
    app = DensityApp(tmp_path, Settings(ui={"detail_density": density}))
    policy = runtime_evidence_redactor(app)
    policy.register_secret("known-density-canary")
    async with app.run_test() as pilot:
        request(app, path="src/target.py", value="known-density-canary")
        result(app, success=False, result="late-density-canary " + "output " * 1000)
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        card.focus()
        await pilot.press("enter")
        await settle_layout(pilot)
        inspector = app.screen.query_one(TextArea)
        assert inspector.read_only
        assert "known-density-canary" not in inspector.text
        assert "late-density-canary" in inspector.text
        assert "omitted" in inspector.text.lower() and len(inspector.text) < 2500
        policy.register_secret("late-density-canary")
        app.screen.refresh_evidence()
        card._update_renderable()
        assert "late-density-canary" not in inspector.text
        assert "late-density-canary" not in str(card.render())
        assert "[REDACTED]" in inspector.text
        await pilot.press("escape")
        await settle_layout(pilot)
        assert app.focused is card
        assert card.content.display is (density == "detailed")


@pytest.mark.parametrize("density", DENSITIES)
async def test_pending_approval_remains_explicit_and_preserves_draft(tmp_path, density):
    app = DensityApp(tmp_path, Settings(ui={"detail_density": density}))
    async with app.run_test() as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Keep\nthis draft")
        approval = asyncio.create_task(app._textual_confirm(ConfirmationRequest(
            "write_file", "Write the proposed file", params={"path": "target.py"},
        )))
        try:
            await settle_layout(pilot)
            decision_screen = app.screen
            decision_focus = app.focused
            request(app)
            result(app, success=False, result="Failure while the decision is pending")
            await settle_layout(pilot)
            assert not approval.done()
            assert app.screen is decision_screen and app.focused is decision_focus
            await pilot.press("n")
            assert await approval is False
        finally:
            if not approval.done():
                approval.cancel()
                await asyncio.gather(approval, return_exceptions=True)
        await settle_layout(pilot)
        assert composer.text == "Keep\nthis draft" and app.focused is composer
        assert not app.submitted
