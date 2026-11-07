"""Mounted tool evidence uses actual call identity, never implied acceptance."""


import pytest
from textual.widgets import TabbedContent, TextArea

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.textual_bridge import EventBridge
from henchman.cli.textual_widgets import HenchmanTextArea, ToolMessage
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall
from tests.cli.ui_scenarios import InteractionApp, settle_layout


async def test_tools_projection_counts_expanded_tabs_before_render_retention(app):
    from henchman.cli.textual_widgets import ToolPane

    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one(TabbedContent).active = "tab-tools"
        await send(app, [
            request(identity="one", path="file"), result(identity="one", success=False, result="\t" * 32000 + "end"),
            request(identity="two", path="file"), result(identity="two", success=False, result="\t" * 32000 + "end"),
        ])
        await settle_layout(pilot)
        pane = app.query_one(ToolPane)
        text = "\n".join(line.text for line in pane.lines)
        assert "Recent tool evidence" in text
        assert "omitted" in text.lower()
        assert len(pane.lines) < pane.max_lines


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return InteractionApp(tmp_path)


async def send(app, events):
    async def stream():
        for event in events:
            yield event
    await EventBridge(app).forward_events(stream())


def request(identity="call", agent="worker", **arguments):
    return AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall(identity, "write_file", arguments), agent)


def result(identity="call", agent="worker", **data):
    return AgentEvent(EventType.TOOL_CALL_RESULT, {"tool_call_id": identity, "tool_name": "write_file", **data}, agent)


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_correlated_compact_rows_keep_full_failure_and_keyboard_inspection(app, size):
    async with app.run_test(size=size) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("draft\nretained")
        composer.focus()
        await send(app, [request(path="src/long.py", content="large body " * 100),
                         result(success=False, result="failure detail\n" * 30 + "TAIL_EVIDENCE")])
        await settle_layout(pilot)
        cards = list(app.query(ToolMessage))
        assert len(cards) == 1
        card = cards[0]
        assert card.header.region.height <= 2
        assert "Failed" in str(card.header.render())
        assert "src/long.py" in str(card.header.render())
        assert "worker" in str(card.header.render())
        assert app.focused is composer and composer.text == "draft\nretained"
        card.focus()
        await pilot.press("enter")
        await settle_layout(pilot)
        inspector = app.screen.query_one("#tool-evidence", TextArea)
        assert inspector.read_only and "TAIL_EVIDENCE" in inspector.text
        assert "Call: call" in inspector.text and "Agent: worker" in inspector.text
        assert "request-to-result" in inspector.text
        assert "Requirements acceptance is not established" in inspector.text
        await pilot.press("escape")
        await settle_layout(pilot)
        assert app.focused is card and composer.text == "draft\nretained"


async def test_interleaved_agents_and_separate_streams_never_merge_calls(app):
    async with app.run_test() as pilot:
        await send(app, [request(agent="one", path="one.py"), request(agent="two", path="two.py"),
                         result(agent="two", success=False, result="two failure"),
                         result(agent="one", success=True, result="one finished")])
        await send(app, [request(agent="one", path="later.py"), result(agent="one", success=True, result="later finished")])
        await settle_layout(pilot)
        cards = list(app.query(ToolMessage))
        assert len(cards) == 3
        for card, expected in zip(cards, ["one finished", "two failure", "later finished"], strict=True):
            card.toggle_expansion()
            assert expected in str(card.render())


@pytest.mark.parametrize("success", [None, "true", 1, {"malformed": True}])
async def test_missing_or_invalid_success_stays_unknown(app, success):
    async with app.run_test() as pilot:
        data = {"result": "I verified every requirement"}
        if success is not None:
            data["success"] = success
        await send(app, [request(path="file"), result(**data)])
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        assert "Unknown" in str(card.header.render())
        assert "Succeeded" not in str(card.header.render())


async def test_duplicate_and_orphan_results_retain_chronology_without_extra_rows(app):
    async with app.run_test() as pilot:
        await send(app, [result(result="first evidence", success=False), result(result="later evidence", success=True)])
        await settle_layout(pilot)
        cards = list(app.query(ToolMessage))
        assert len(cards) == 1
        cards[0].toggle_expansion()
        text = str(cards[0].render())
        assert text.index("first evidence") < text.index("later evidence")
        assert "Unknown" in str(cards[0].header.render())
        assert "request not observed" in text.lower()
        assert "multiple results" in text.lower()


async def test_closed_stream_marks_unanswered_call_interrupted(app):
    async with app.run_test() as pilot:
        await send(app, [request(path="possibly-written.py")])
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        assert "Interrupted" in str(card.header.render())
        card.toggle_expansion()
        assert "no final result" in str(card.render()).lower()


async def test_rotation_reprojects_inspection_and_truncation_is_explicit(app):
    async with app.run_test() as pilot:
        await send(app, [request(path="file"), result(success=False, result="rotating-canary " + "x" * 150_000 + "OMITTED_TAIL")])
        await settle_layout(pilot)
        runtime_evidence_redactor(app).register_secret("rotating-canary")
        card = app.query_one(ToolMessage)
        card.focus()
        await pilot.press("enter")
        await settle_layout(pilot)
        text = app.screen.query_one("#tool-evidence", TextArea).text
        assert "rotating-canary" not in text
        assert "omitted" in text.lower() and "OMITTED_TAIL" not in text
        assert len(text) < 140_000


async def test_inspector_preserves_multiline_output_and_rechecks_rotation_while_open(app):
    async with app.run_test() as pilot:
        await send(app, [request(path="file"), result(success=False, result="first line\nlate-known-canary\nlast line")])
        await settle_layout(pilot)
        app.query_one(ToolMessage).focus()
        await pilot.press("enter")
        await settle_layout(pilot)
        area = app.screen.query_one("#tool-evidence", TextArea)
        assert "first line\nlate-known-canary\nlast line" in area.text
        runtime_evidence_redactor(app).register_secret("late-known-canary")
        app.screen.refresh_evidence()
        assert "late-known-canary" not in area.text


async def test_rotation_masks_previously_clipped_target_prefix(app):
    secret = "long-target-canary-" + "z" * 300
    async with app.run_test() as pilot:
        await send(app, [request(path=secret), result(success=True, result="finished")])
        await settle_layout(pilot)
        runtime_evidence_redactor(app).register_secret(secret)
        card = app.query_one(ToolMessage)
        card.focus()
        await pilot.press("enter")
        await settle_layout(pilot)
        assert "long-target-canary" not in app.screen.query_one("#tool-evidence", TextArea).text
        assert "long-target-canary" not in str(card.header.render())


async def test_stream_close_uses_private_identity_even_when_display_id_is_redacted(app, monkeypatch):
    from types import SimpleNamespace

    from henchman.cli import textual_bridge

    monkeypatch.setattr(textual_bridge, "uuid4", lambda: SimpleNamespace(hex="private-stream-canary"))
    runtime_evidence_redactor(app).register_secret("private-stream-canary")
    async with app.run_test() as pilot:
        await send(app, [request(path="file")])
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        assert "Interrupted" in str(card.header.render())
        card.toggle_expansion()
        assert "private-stream-canary" not in str(card.render())


async def test_retention_omits_old_evidence_without_losing_row_correlation(app, monkeypatch):
    from henchman.cli import textual_tool_activity

    monkeypatch.setattr(textual_tool_activity, "MAX_EVIDENCE_BYTES", 1800)
    async with app.run_test() as pilot:
        await send(app, [request("one", path="one.py"), result("one", success=False, result="old evidence " * 100),
                         request("two", path="two.py"), result("two", success=True, result="new evidence " * 100),
                         result("one", success=False, result="later observation")])
        await settle_layout(pilot)
        cards = list(app.query(ToolMessage))
        assert len(cards) == 2
        cards[0].toggle_expansion()
        assert "omitted" in str(cards[0].render()).lower()
        assert "later observation" in str(cards[0].render())
        assert "old evidence" not in str(cards[0].render())
        assert "Unknown" in str(cards[0].header.render())


async def test_missing_identity_results_do_not_borrow_the_nearest_request(app):
    async with app.run_test() as pilot:
        await send(app, [request(path="original.py"),
                         AgentEvent(EventType.TOOL_CALL_RESULT, {"result": "orphan", "success": False}, "worker")])
        await settle_layout(pilot)
        cards = list(app.query(ToolMessage))
        assert len(cards) == 2
        assert "Interrupted" in str(cards[0].header.render())
        cards[1].toggle_expansion()
        assert "request not observed" in str(cards[1].render()).lower()
        assert "Elapsed: unknown" in str(cards[1].render())


async def test_known_credentials_project_before_large_output_cutoff(app):
    secret = "stream-secret-" + "x" * 80
    policy = runtime_evidence_redactor(app)
    policy.register_secret(secret)
    async with app.run_test() as pilot:
        await send(app, [request(path="file"), result(success=False, result="a" * 32760 + secret)])
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        card.toggle_expansion()
        assert "stream-secret" not in str(card.render())
        assert "omitted" in str(card.render()).lower()


async def test_reading_anchor_and_composer_draft_survive_inspection_resize_and_new_results(app):
    from henchman.cli.textual_widgets import ChatPane
    from tests.cli.ui_scenarios import populate_history

    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        populate_history(chat)
        await send(app, [request(path="file"), result(success=False, result="retained failure")])
        await settle_layout(pilot)
        card = app.query_one(ToolMessage)
        card.focus()
        await pilot.press("enter")
        await settle_layout(pilot)
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("unsent multiline\ndraft")
        inspector = app.screen.query_one("#tool-evidence", TextArea)
        await pilot.resize_terminal(80, 24)
        await send(app, [request("later", path="later.py"), result("later", success=True, result="new evidence")])
        await settle_layout(pilot)
        assert app.focused is inspector
        assert "retained failure" in inspector.text
        await pilot.press("escape")
        await settle_layout(pilot)
        assert app.focused is card and not chat.follow_live
        assert composer.text == "unsent multiline\ndraft"


def tool_tab_text(pane):
    return "\n".join(line.text for line in pane.lines)


async def test_tools_tab_reprojects_credentials_from_shared_store(app):
    from textual.widgets import TabbedContent

    from henchman.cli.textual_widgets import ToolPane

    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one(TabbedContent).active = "tab-tools"
        await send(app, [request(path="file"), result(success=False, result="late-tools-canary")])
        await settle_layout(pilot)
        pane = app.query_one(ToolPane)
        assert "late-tools-canary" in tool_tab_text(pane)
        runtime_evidence_redactor(app).register_secret("late-tools-canary")
        pane.refresh()
        await settle_layout(pilot)
        assert "late-tools-canary" not in tool_tab_text(pane)
        assert "[REDACTED]" in tool_tab_text(pane)
        assert pane.max_lines is not None


async def test_tools_tab_follows_retention_and_transcript_clear(app, monkeypatch):
    from textual.widgets import TabbedContent

    from henchman.cli import textual_tool_activity
    from henchman.cli.textual_widgets import ChatPane, ToolPane

    monkeypatch.setattr(textual_tool_activity, "MAX_EVIDENCE_BYTES", 1500)
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one(TabbedContent).active = "tab-tools"
        await send(app, [request("first", path="first.py"), result("first", success=False, result="EVICTED_CANARY " * 70),
                         request("second", path="second.py"), result("second", success=True, result="latest output " * 70)])
        await settle_layout(pilot)
        pane = app.query_one(ToolPane)
        assert "EVICTED_CANARY" not in tool_tab_text(pane)
        assert "omitted" in tool_tab_text(pane).lower()
        assert "latest output" in tool_tab_text(pane)
        app.query_one(ChatPane).clear_messages()
        pane.refresh()
        await settle_layout(pilot)
        assert "latest output" not in tool_tab_text(pane)
        assert "second.py" not in tool_tab_text(pane)
        assert not list(app.query(ToolMessage))


async def test_tools_tab_clear_holds_until_new_observation(app):
    from textual.widgets import TabbedContent

    from henchman.cli.textual_widgets import ToolPane

    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one(TabbedContent).active = "tab-tools"
        await send(app, [request(path="old.py"), result(success=True, result="OLD_VIEW")])
        await settle_layout(pilot)
        pane = app.query_one(ToolPane)
        app.action_clear_tool_pane()
        pane.refresh()
        await settle_layout(pilot)
        assert "OLD_VIEW" not in tool_tab_text(pane)
        await send(app, [request(path="new.py"), result(success=True, result="NEW_VIEW")])
        await settle_layout(pilot)
        assert "NEW_VIEW" in tool_tab_text(pane) and "OLD_VIEW" not in tool_tab_text(pane)


async def test_hidden_tools_tab_rotates_before_activation_without_accumulating_views(app, monkeypatch):
    from textual.widgets import TabbedContent

    from henchman.cli import textual_tool_activity
    from henchman.cli.textual_widgets import ToolPane

    monkeypatch.setattr(textual_tool_activity, "MAX_TOOL_VIEW_BYTES", 1800)
    async with app.run_test(size=(80, 24)) as pilot:
        await send(app, [request("old", path="old.py"), result("old", success=False, result="older " * 1000),
                         request("new", path="new.py"), result("new", success=True, result="hidden-tools-canary")])
        await settle_layout(pilot)
        runtime_evidence_redactor(app).register_secret("hidden-tools-canary")
        app.query_one(TabbedContent).active = "tab-tools"
        await settle_layout(pilot)
        pane = app.query_one(ToolPane)
        text = tool_tab_text(pane)
        assert "hidden-tools-canary" not in text and "[REDACTED]" in text
        assert "omitted" in text.lower() and len(text) < 4000
        before = len(pane.lines)
        for _ in range(5):
            pane.refresh()
            await settle_layout(pilot)
        assert len(pane.lines) == before


async def test_clearing_transcript_drops_payload_held_by_open_inspector(app):
    from henchman.cli.textual_widgets import ChatPane

    async with app.run_test() as pilot:
        chat = app.query_one(ChatPane)
        await send(app, [request(path="file"), result(success=False, result="CLEAR_HELD_PAYLOAD")])
        await settle_layout(pilot)
        app.query_one(ToolMessage).focus()
        await pilot.press("enter")
        await settle_layout(pilot)
        screen = app.screen
        assert "CLEAR_HELD_PAYLOAD" in screen.query_one("#tool-evidence", TextArea).text
        chat.clear_messages()
        screen.refresh_evidence()
        assert "CLEAR_HELD_PAYLOAD" not in screen.query_one("#tool-evidence", TextArea).text
        assert "Display stream" not in screen.query_one("#tool-evidence", TextArea).text


async def test_tools_tab_line_limit_has_visible_omission_notice(app):
    from textual.widgets import TabbedContent

    from henchman.cli.textual_widgets import ToolPane

    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one(TabbedContent).active = "tab-tools"
        await send(app, [request(path="file"), result(success=False, result="row\n" * 5000)])
        await settle_layout(pilot)
        pane = app.query_one(ToolPane)
        assert "omitted" in tool_tab_text(pane).lower()
        assert len(pane.lines) < pane.max_lines
