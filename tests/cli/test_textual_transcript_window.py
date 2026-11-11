"""Bounded ordinary transcript widgets retain searchable chronological evidence."""

import gc
import weakref

import pytest

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.textual_widgets import ChatMessage, ChatPane, HenchmanTextArea
from tests.cli.ui_scenarios import InteractionApp, settle_layout


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return InteractionApp(tmp_path)


async def test_thousand_finished_rows_keep_bounded_dom_and_release_evicted_widgets(app):
    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        first = chat.add_user_message("chronological message 0000")
        evicted = weakref.ref(first)
        del first
        for index in range(1, 1000):
            chat.add_user_message(f"chronological message {index:04d}")
        await settle_layout(pilot)
        assert len(chat.query(ChatMessage)) <= 128
        rows = list(chat.iter_transcript_rows())
        assert [row.content for row in rows] == [
            f"chronological message {index:04d}" for index in range(1000)
        ]
        assert len({row.row_id for row in rows}) == 1000
        gc.collect()  # Test-only reachability oracle; production must not collect.
        assert evicted() is None


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_explicit_history_pages_search_and_live_keep_draft_focus_and_rotation(app, size):
    async with app.run_test(size=size) as pilot:
        chat = app.query_one(ChatPane)
        for index in range(260):
            chat.add_user_message(f"row {index:03d} retained-canary")
        await settle_layout(pilot)
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("unsent\nmultiline draft")
        composer.focus()
        assert len(chat.query(ChatMessage)) <= 128
        chat.action_previous_history()
        await settle_layout(pilot)
        assert not chat.follow_live
        assert any("row 005 " in row._content_text for row in chat.query(ChatMessage))
        assert composer.text == "unsent\nmultiline draft"
        assert app.focused is composer
        runtime_evidence_redactor(app).register_secret("retained-canary")
        app._perform_search("row 259")
        app._current_match_index = 0
        app._scroll_to_match()
        await settle_layout(pilot)
        assert any("row 259 " in row._content_text for row in chat.query(ChatMessage))
        assert all("retained-canary" not in row.content for row in chat.iter_transcript_rows())
        assert not chat.follow_live
        chat.return_to_live()
        await settle_layout(pilot)
        assert chat.follow_live
        assert composer.text == "unsent\nmultiline draft"
        assert app.focused is composer


async def test_held_page_does_not_advance_as_finished_messages_arrive(app):
    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        for index in range(140):
            chat.add_user_message(f"held row {index:03d}")
        await settle_layout(pilot)
        chat.hold_reading_position()
        before = [row._content_text for row in chat.query(ChatMessage)]
        for index in range(140, 280):
            chat.add_user_message(f"held row {index:03d}")
        await settle_layout(pilot)
        assert [row._content_text for row in chat.query(ChatMessage)] == before
        assert not chat.follow_live and chat.new_activity


async def test_search_projection_does_not_rewrite_original_private_snapshots(app):
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        chat.add_user_message("kept original credential-canary")
        await settle_layout(pilot)
        original = next(iter(chat._transcript.records.values()))
        runtime_evidence_redactor(app).register_secret("credential-canary")
        chat._transcript.project()
        app._perform_search("kept")
        await settle_layout(pilot)
        assert next(iter(chat._transcript.records.values())) == original
        assert "credential-canary" not in next(chat.iter_transcript_rows()).content


async def test_clear_invalidates_an_awaited_mount_without_resurrecting_rows(app, monkeypatch):
    import asyncio

    entered, release = asyncio.Event(), asyncio.Event()
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        mount = chat.mount

        async def delayed_mount(*widgets, **kwargs):
            if any(isinstance(widget, ChatMessage) and widget._content_text == "stale row" for widget in widgets):
                entered.set()
                await release.wait()
            return await mount(*widgets, **kwargs)

        monkeypatch.setattr(chat, "mount", delayed_mount)
        chat.add_user_message("stale row")
        await asyncio.wait_for(entered.wait(), 2)
        chat.clear_messages()
        chat.add_user_message("current row")
        release.set()
        await settle_layout(pilot)
        assert [row._content_text for row in chat.query(ChatMessage)] == ["current row"]
        assert [row.content for row in chat.iter_transcript_rows()] == ["current row"]


async def test_pinned_stream_tool_and_thought_keep_chronology_and_copy_from_older_page(app):
    from henchman.cli.textual_review import _transcript
    from henchman.cli.textual_widgets import ThinkingMessage, ToolMessage
    from henchman.providers.base import ToolCall

    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        for index in range(140):
            chat.add_user_message(f"before {index:03d}")
        active = chat.begin_agent_stream("worker")
        chat.append_agent_chunk("worker", "first-stream-part")
        tool = chat.add_tool_message(tool_call=ToolCall("real-call", "read_file", {"path": "test.py"}))
        thought = chat.add_thinking_message("retained thought")
        for index in range(140):
            chat.add_user_message(f"after {index:03d}")
        await settle_layout(pilot)
        assert tool in chat.query(ToolMessage) and thought in chat.query(ThinkingMessage)
        assert active.is_mounted
        assert len(chat.query(ChatMessage)) == 129  # 128 finished + active stream.
        chat.action_previous_history()
        await settle_layout(pilot)
        assert active.is_mounted and tool.is_mounted and thought.is_mounted
        chat.append_agent_chunk("worker", " second-stream-part")
        chat.finish_agent_stream("worker")
        await settle_layout(pilot)
        rows = list(chat.iter_transcript_rows())
        assert rows[140].content == "first-stream-part second-stream-part"
        assert rows[141].kind == "ToolMessage" and rows[142].kind == "ThinkingMessage"
        copied = _transcript(app, runtime_evidence_redactor(app))
        assert "after 139" in copied
        assert "Earlier retained rows omitted." in copied
        assert len(chat.query(ChatMessage)) <= 128


async def test_previous_next_buttons_and_boundary_keys_preserve_control_focus(app):
    from textual.widgets import Button

    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        for index in range(300):
            chat.add_user_message(f"page row {index:03d}")
        await settle_layout(pilot)
        previous = chat.query_one("#transcript-earlier", Button)
        previous.focus()
        await settle_layout(pilot)
        await pilot.press("enter")
        await settle_layout(pilot)
        assert app.focused is chat.query_one("#transcript-earlier", Button)
        later = chat.query_one("#transcript-later", Button)
        later.focus()
        await settle_layout(pilot)
        await pilot.press("enter")
        await settle_layout(pilot)
        assert not chat.follow_live
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("preserved draft")
        composer.focus()
        chat.scroll_to(y=0, animate=False, immediate=True)
        await settle_layout(pilot)
        before = [row._content_text for row in chat.query(ChatMessage)]
        await pilot.press("alt+pageup")
        await settle_layout(pilot)
        assert [row._content_text for row in chat.query(ChatMessage)] != before
        assert composer.text == "preserved draft" and app.focused is composer


async def test_credential_projection_preserves_rich_syntax_and_private_stream_source(app):
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        policy = runtime_evidence_redactor(app)
        policy.register_secret("bold")
        policy.register_secret("private-stream-canary")
        chat.add_user_message("visible ordinary text")
        chat.add_system_message("[bold]Notice[/] private-stream-canary")
        chat.begin_agent_stream("worker")
        chat.append_agent_chunk("worker", "private-stream-canary")
        await settle_layout(pilot)
        chat.append_agent_chunk("worker", " appended later")
        await settle_layout(pilot)
        record = list(chat._transcript.records.values())[-1]
        assert record.content == "private-stream-canary appended later"
        assert "private-stream-canary" not in next(chat.iter_transcript_rows(reverse=True)).content
        # Rendering the plain textual prefix must not redact markup tag syntax.
        assert "You:" in str(chat.query(ChatMessage).first().renderable)


async def test_rotated_credential_in_trusted_link_metadata_is_not_remounted(app):
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        secret = "private-link-target"
        chat.add_system_message(f'[link="https://example.invalid/{secret}"]inspect[/link]')
        await settle_layout(pilot)
        runtime_evidence_redactor(app).register_secret(secret)
        chat._transcript.project()
        rendered = str(chat.query(ChatMessage).first().renderable)
        assert secret not in rendered
        assert "inspect" in rendered


async def test_older_anchor_survives_resize_new_stream_and_return_live(app):
    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        for index in range(400):
            chat.add_user_message(f"archive {index:03d} " + "wrapped content " * 20)
        await settle_layout(pilot)
        target = next(row.row_id for row in chat.iter_transcript_rows() if row.content.startswith("archive 050 "))
        chat.reveal_transcript_row(target)
        await settle_layout(pilot)
        anchor = next(row for row in chat.query(ChatMessage) if row._content_text.startswith("archive 050 "))
        offset = anchor.region.y - chat.content_region.y
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("held draft")
        composer.focus()
        await pilot.resize_terminal(80, 24)
        chat.append_agent_chunk("background", "new background observation")
        chat.add_user_message("new finished row")
        await settle_layout(pilot)
        assert anchor.is_mounted
        assert anchor.region.y - chat.content_region.y == offset
        assert composer.text == "held draft" and app.focused is composer
        assert not chat.follow_live
        chat.return_to_live()
        await settle_layout(pilot)
        assert chat.follow_live and chat.scroll_y == chat.max_scroll_y
        assert any(row._content_text == "new finished row" for row in chat.query(ChatMessage))


async def test_shutdown_cancels_owned_pending_window_callback(app, monkeypatch):
    import asyncio

    entered, release = asyncio.Event(), asyncio.Event()

    async def run():
        async with app.run_test(size=(80, 24)):
            chat = app.query_one(ChatPane)
            mount = chat.mount

            async def delayed_mount(*widgets, **kwargs):
                entered.set()
                await release.wait()
                return await mount(*widgets, **kwargs)

            monkeypatch.setattr(chat, "mount", delayed_mount)
            chat.add_user_message("pending row")
            await asyncio.wait_for(entered.wait(), 2)

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(asyncio.shield(task), 3)
    finally:
        release.set()
        await asyncio.wait_for(task, 3)


async def test_late_credential_search_navigation_and_copy_use_current_records(app):
    from henchman.cli.textual_review import _transcript

    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        chat.add_user_message("find-this late-search-credential")
        await settle_layout(pilot)
        app._perform_search("find-this")
        runtime_evidence_redactor(app).register_secret("late-search-credential")
        app._current_match_index = 0
        app._scroll_to_match()
        await settle_layout(pilot)
        assert "late-search-credential" not in repr(app._search_matches)
        assert "late-search-credential" not in _transcript(app, runtime_evidence_redactor(app))
        assert "late-search-credential" not in str(chat.query(ChatMessage).first().renderable)


async def test_literal_unmatched_markup_diagnostic_remains_renderable_after_rotation(app):
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        chat.add_user_message("literal [/missing] diagnostic-token")
        await settle_layout(pilot)
        runtime_evidence_redactor(app).register_secret("diagnostic-token")
        chat._transcript.project()
        await settle_layout(pilot)
        assert "[/missing]" in next(chat.iter_transcript_rows()).content
        assert "diagnostic-token" not in str(chat.query(ChatMessage).first().renderable)


async def test_close_joins_worker_cancelled_before_it_started(app):
    import asyncio

    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        await settle_layout(pilot)
        entered = asyncio.Event()

        async def queued():
            entered.set()
            await asyncio.Event().wait()

        worker = chat.run_worker(queued, group="transcript-window")
        chat._transcript._worker = worker
        worker.cancel()  # App shutdown can cancel before the first task step.
        await chat._transcript.close()
        assert not entered.is_set()
        assert worker._task.done()


async def test_close_preserves_first_caller_cancel_and_joins_render_cleanup(app):
    import asyncio

    entered, cleanup, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        await settle_layout(pilot)

        async def held():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup.set()
                await release.wait()

        chat._transcript._worker = chat.run_worker(held, group="transcript-window")
        await asyncio.wait_for(entered.wait(), 2)
        closing = asyncio.create_task(chat._transcript.close())
        await asyncio.wait_for(cleanup.wait(), 2)
        closing.cancel("first caller cancellation")
        await pilot.pause()
        closing.cancel("later caller cancellation")
        await pilot.pause()
        assert not closing.done()
        release.set()
        with pytest.raises(asyncio.CancelledError, match="first caller cancellation"):
            await closing
        assert chat._transcript._worker._task.done()


async def test_credential_rotation_while_mount_waits_is_projected_before_mount_publication(app, monkeypatch):
    import asyncio

    entered, release = asyncio.Event(), asyncio.Event()
    observed = []
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        await settle_layout(pilot)
        mount = chat.mount

        async def gated_mount(*widgets, **kwargs):
            if any(isinstance(widget, ChatMessage) for widget in widgets):
                entered.set()
                await release.wait()
                result = await mount(*widgets, **kwargs)
                observed.extend(str(widget.renderable) for widget in widgets if isinstance(widget, ChatMessage))
                return result
            return await mount(*widgets, **kwargs)

        monkeypatch.setattr(chat, "mount", gated_mount)
        chat.add_user_message("mount-rotation-credential")
        await asyncio.wait_for(entered.wait(), 2)
        # Keep this admission-boundary oracle independent of the periodic timer.
        monkeypatch.setattr(chat._transcript, "project", lambda: None)
        runtime_evidence_redactor(app).register_secret("mount-rotation-credential")
        release.set()
        await settle_layout(pilot)
        assert observed and all("mount-rotation-credential" not in text for text in observed)


async def test_first_close_cancellation_survives_secondary_worker_failure():
    import asyncio
    from types import SimpleNamespace

    pane = ChatPane()
    cleanup, release = asyncio.Event(), asyncio.Event()

    async def owned_work():
        try:
            await asyncio.Event().wait()
        finally:
            cleanup.set()
            await release.wait()
            raise RuntimeError("secondary render cleanup failure")

    task = asyncio.create_task(owned_work())
    started = asyncio.Event()
    asyncio.get_running_loop().call_soon(started.set)
    await started.wait()

    async def wait():
        return await task

    pane._transcript._worker = SimpleNamespace(is_cancelled=False, cancel=task.cancel, wait=wait)
    closing = asyncio.create_task(pane._transcript.close())
    await asyncio.wait_for(cleanup.wait(), 2)
    closing.cancel("original close cancellation")
    resumed = asyncio.Event()
    asyncio.get_running_loop().call_soon(resumed.set)
    await resumed.wait()
    release.set()
    with pytest.raises(asyncio.CancelledError, match="original close cancellation"):
        await closing
    assert task.done()


@pytest.mark.parametrize("location", ["content", "prefix"])
async def test_split_markup_credential_rotation_projects_visible_text_and_retained_rows(app, location):
    from textual.content import Content

    from henchman.cli.textual_review import _transcript

    secret = "rotation-markup-private"
    markup = "[bold]rotation-[/bold]markup-private"
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        if location == "content":
            chat.add_system_message(markup)
        else:
            chat._add_message_widget(ChatMessage, markup, "ordinary body")
        await settle_layout(pilot)
        original = dict(chat._transcript.records)
        runtime_evidence_redactor(app).register_secret(secret)
        chat._transcript.project()
        await settle_layout(pilot)
        visible = Content.from_markup(str(chat.query(ChatMessage).first().renderable)).plain
        assert secret not in visible
        rows = list(chat.iter_transcript_rows())
        assert all(secret not in Content.from_markup(row.content).plain for row in rows)
        if location == "content":
            app._perform_search("markup-private")
            assert not app._search_matches
            assert "rotation-" not in _transcript(app, runtime_evidence_redactor(app))
        assert chat._transcript.records == original


async def test_clear_thinking_retires_pending_unmounted_rows(app):
    from henchman.cli.textual_widgets import ThinkingMessage

    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        await settle_layout(pilot)
        chat.add_user_message("keep ordinary history")
        chat.add_thinking_message("retired before mount")
        chat.clear_thinking_messages()
        await settle_layout(pilot)
        assert not list(chat.query(ThinkingMessage))
        assert [row.content for row in chat.iter_transcript_rows()] == ["keep ordinary history"]


@pytest.mark.parametrize("boundary", ["row_mount", "control_remove", "control_mount"])
async def test_discarded_thought_cannot_publish_or_rejoin_after_awaited_boundaries(app, monkeypatch, boundary):
    import asyncio

    from henchman.cli.textual_transcript import HistoryButton
    from henchman.cli.textual_widgets import ThinkingMessage

    entered, release = asyncio.Event(), asyncio.Event()
    observed = []
    async with app.run_test(size=(120, 40)) as pilot:
        chat = app.query_one(ChatPane)
        if boundary != "row_mount":
            for index in range(120 if boundary == "control_mount" else 260):
                chat.add_user_message(f"kept ordinary {index:03d}")
            thought = chat.add_thinking_message("retire this thought")
            await settle_layout(pilot)
        controls = tuple(chat._transcript._controls)
        mount, remove = chat.mount, chat.remove_children

        async def gated_mount(*widgets, **kwargs):
            target = any(isinstance(widget, ThinkingMessage if boundary == "row_mount" else HistoryButton) for widget in widgets)
            if boundary != "control_remove" and target and not entered.is_set():
                entered.set()
                await release.wait()
                result = await mount(*widgets, **kwargs)
                observed.extend(widget.display for widget in widgets if isinstance(widget, ThinkingMessage))
                return result
            return await mount(*widgets, **kwargs)

        async def gated_remove(widgets="*"):
            if boundary == "control_remove" and any(widget in controls for widget in widgets) and not entered.is_set():
                entered.set()
                await release.wait()
            return await remove(widgets)

        monkeypatch.setattr(chat, "mount", gated_mount)
        monkeypatch.setattr(chat, "remove_children", gated_remove)
        if boundary == "row_mount":
            thought = chat.add_thinking_message("retire this thought")
        elif boundary == "control_remove":
            chat.action_previous_history()
        else:
            for index in range(120, 140):
                chat.add_user_message(f"kept ordinary {index:03d}")
        try:
            await asyncio.wait_for(entered.wait(), 3)
            chat.clear_thinking_messages()
        finally:
            release.set()
        await settle_layout(pilot)
        assert not list(chat.query(ThinkingMessage))
        assert all(row.kind != "ThinkingMessage" for row in chat.iter_transcript_rows())
        assert not any(observed), "A retired thought became visible during mount"
        assert not thought.display
        for button in chat.query(HistoryButton):
            assert "retained" in str(button.label)
