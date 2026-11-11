"""Pending decisions remain unanswered while bounded evidence is inspected/exported."""

from __future__ import annotations

import asyncio
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.widgets import Input, TextArea

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.textual_review import ReviewSnapshot, export_review
from henchman.cli.textual_widgets import ChatPane, HenchmanTextArea
from henchman.tools.base import ConfirmationRequest
from tests.cli.ui_scenarios import InteractionApp, settle_layout


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return InteractionApp(tmp_path)


async def open_review(app, pilot, request):
    task = asyncio.create_task(app._textual_confirm(request))
    await settle_layout(pilot)
    origin = app.screen
    await pilot.press("f10")
    await settle_layout(pilot)
    assert app.screen is not origin
    return task, origin, app.screen


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_long_approval_and_retained_plan_are_copyable_without_answering(app, size):
    link = "https://example.invalid/" + "long-path-" * 35
    plan = (
        "Plan with literal [red] markup\n" + "\n".join(f"step {n}" for n in range(70)) + "\n" + link
    )
    request = ConfirmationRequest(
        "shell",
        "Run proposed operation",
        {"command": "printf 'literal ; $()'", "diff": "+ added\n- removed"},
        "high",
    )
    async with app.run_test(size=size) as pilot:
        chat = app.query_one(ChatPane)
        chat.add_user_message(plan)
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("unsent\nretained draft")
        task, origin, review = await open_review(app, pilot, request)
        try:
            area = review.query_one("#review-content", TextArea)
            assert area.read_only and link in area.text and "step 69" in area.text
            assert "printf 'literal ; $()'" in area.text and "+ added" in area.text
            assert "not supplied" in area.text.lower()
            await pilot.click("#review-copy")
            await pilot.pause()
            assert link in app.clipboard
            assert "requested" in str(review.query_one("#review-status").render()).lower()
            assert not task.done() and request.params["command"] == "printf 'literal ; $()'"
            await pilot.press("escape")
            await settle_layout(pilot)
            assert app.screen is origin and not task.done()
            assert composer.text == "unsent\nretained draft"
            await pilot.press("n")
            assert await asyncio.wait_for(task, 2) is False
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_question_review_retains_answer_and_literal_long_link(app):
    async with app.run_test(size=(80, 24)) as pilot:
        task = asyncio.create_task(
            app._textual_question("Choose [blue] https://example.invalid/a?b=c")
        )
        await settle_layout(pilot)
        origin = app.screen
        origin.query_one(Input).value = "partial answer"
        await pilot.press("f10")
        await settle_layout(pilot)
        assert "Choose [blue]" in app.screen.query_one(TextArea).text
        await pilot.press("escape")
        await settle_layout(pilot)
        assert app.screen is origin
        assert origin.query_one(Input).value == "partial answer"
        await pilot.press("enter")
        assert await asyncio.wait_for(task, 2) == "partial answer"


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_long_pending_decision_keeps_visible_review_and_answer_controls(app, size):
    async with app.run_test(size=size) as pilot:
        task = asyncio.create_task(
            app._textual_question("\n".join(f"question line {index}" for index in range(100)))
        )
        await settle_layout(pilot)
        try:
            origin = app.screen
            # Visibility must not depend on autofocus scrolling an oversized
            # dialog into view after an arbitrary amount of animation time.
            for target in ("#question-dialog", "#tool-question", "#question-answer", "#question-actions"):
                assert origin.region.contains_region(origin.query_one(target).region), target
            assert await pilot.click("#decision-review")
            await settle_layout(pilot)
            assert app.screen is not origin
            assert "question line 99" in app.screen.query_one(TextArea).text
            await pilot.press("escape")
            await settle_layout(pilot)
            await pilot.resize_terminal(80, 24)
            await settle_layout(pilot)
            for target in ("#decision-review", "#question-submit", "#question-cancel", "#question-answer"):
                assert origin.region.contains_region(origin.query_one(target).region), target
            assert origin.query_one(Input).region.bottom <= 24
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_export_both_formats_uses_current_redaction_and_canonical_private_files(
    app, tmp_path
):
    raw = "rotated-review-private"
    request = ConfirmationRequest("fixture", "Inspect", {"command": raw}, "low")
    async with app.run_test(size=(120, 40)) as pilot:
        task, _origin, review = await open_review(app, pilot, request)
        try:
            # Newly known credentials must be projected at the actual action,
            # even before the screen's periodic refresh runs.
            runtime_evidence_redactor(app).register_secret(raw)
            for name, suffix in (("text", ".txt"), ("markdown", ".md")):
                await pilot.click(f"#review-export-{name}")
                assert review._export_task is not None
                await asyncio.wait_for(review._export_task, 10)
                await pilot.pause()
                paths = list((tmp_path / ".henchman" / "exports").glob(f"*{suffix}"))
                assert len(paths) == 1, str(review.query_one("#review-status").render())
                assert raw not in paths[0].read_text()
                assert "[REDACTED]" in paths[0].read_text()
                if os.name == "posix":
                    assert paths[0].stat().st_mode & 0o777 == 0o600
            assert not task.done() and request.params["command"] == raw
            await pilot.press("escape")
            await settle_layout(pilot)
            await pilot.press("n")
            assert await asyncio.wait_for(task, 2) is False
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_expired_decision_retires_copy_export_without_answering_replacement(app, tmp_path):
    async with app.run_test(size=(80, 24)) as pilot:
        task, _origin, review = await open_review(
            app, pilot, ConfirmationRequest("fixture", "Inspect")
        )
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await pilot.pause()
        await pilot.click("#review-export-text")
        await pilot.click("#review-copy")
        assert not (tmp_path / ".henchman" / "exports").exists()
        await pilot.press("escape")
        await settle_layout(pilot)
        assert len(app.screen_stack) == 1
        next_question = asyncio.create_task(app._textual_question("Next decision"))
        await settle_layout(pilot)
        assert not next_question.done()
        await pilot.press("escape")
        assert await next_question is None


async def test_current_projection_guards_inherited_selection_copy_and_clipboard_failure(
    app, monkeypatch
):
    raw = "late-review-token"
    async with app.run_test(size=(80, 24)) as pilot:
        task, _origin, review = await open_review(app, pilot, ConfirmationRequest("fixture", raw))
        try:
            area = review.query_one(TextArea)
            area.action_select_all()
            runtime_evidence_redactor(app).register_secret(raw)
            area.action_copy()
            assert raw not in app.clipboard and "select text again" in str(
                review.query_one("#review-status").render()
            )

            def fail(_text):
                raise OSError("clipboard unavailable " + raw)

            monkeypatch.setattr(app, "copy_to_clipboard", fail)
            review.copy_evidence()
            status = str(review.query_one("#review-status").render())
            assert "clipboard unavailable" in status and raw not in status
            assert not task.done()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_stale_runtime_refuses_export_and_does_not_answer(app, tmp_path):
    async with app.run_test(size=(80, 24)) as pilot:
        task, _origin, review = await open_review(
            app, pilot, ConfirmationRequest("fixture", "Inspect")
        )
        try:
            app.core_context = SimpleNamespace(
                project_root=tmp_path, session_manager=SimpleNamespace(current=object())
            )
            review.copy_evidence()
            review._export("text")
            await pilot.pause()
            assert not (tmp_path / ".henchman" / "exports").exists()
            assert not task.done()
        finally:
            app.core_context = None
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("cancel_close", [False, True])
async def test_back_joins_export_worker_and_retains_pending_decision(app, tmp_path, monkeypatch, cancel_close):
    from henchman.cli import textual_review

    entered, release, exited = threading.Event(), threading.Event(), threading.Event()
    original = textual_review.export_review

    def delayed(*args):
        entered.set()
        try:
            assert release.wait(3)
            return original(*args)
        finally:
            exited.set()

    monkeypatch.setattr(textual_review, "export_review", delayed)
    async with app.run_test(size=(80, 24)) as pilot:
        task, origin, review = await open_review(
            app, pilot, ConfirmationRequest("fixture", "Inspect")
        )
        try:
            review._export("text")
            assert await asyncio.to_thread(entered.wait, 2)
            close = asyncio.create_task(review.action_back())
            await asyncio.sleep(0)
            assert not close.done() and not task.done()
            if cancel_close:
                close.cancel("first close interruption")
                await asyncio.sleep(0)
                close.cancel("second close interruption")
                await asyncio.sleep(0)
                assert not close.done() and not exited.is_set()
            release.set()
            if cancel_close:
                with pytest.raises(asyncio.CancelledError) as cancelled:
                    await asyncio.wait_for(close, 2)
                assert cancelled.value.args == ("first close interruption",)
                assert exited.is_set()
                assert review._export_task.done()
                await review.action_back()
            else:
                await asyncio.wait_for(close, 2)
            await settle_layout(pilot)
            assert exited.is_set() and app.screen is origin
            assert not list((tmp_path / ".henchman" / "exports").glob("*"))
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_export_completion_does_not_refresh_closing_screen(app, tmp_path, monkeypatch):
    from henchman.cli import textual_review

    entered, release = threading.Event(), threading.Event()

    def delayed(*_args):
        entered.set()
        assert release.wait(5)
        return tmp_path / "unused"

    monkeypatch.setattr(textual_review, "export_review", delayed)
    async with app.run_test(size=(80, 24)) as pilot:
        task, _origin, review = await open_review(app, pilot, ConfirmationRequest("fixture", "Inspect"))
        after_close = []
        original = review.refresh_evidence

        def observed():
            if review._review_closing:
                after_close.append(True)
            else:
                original()

        monkeypatch.setattr(review, "refresh_evidence", observed)
        try:
            review._export("text")
            assert await asyncio.to_thread(entered.wait, 2)
            closing = asyncio.create_task(review.action_back())
            await asyncio.sleep(0)
            release.set()
            await asyncio.wait_for(closing, 5)
            await asyncio.sleep(0)
            assert not after_close
        finally:
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_export_completion_tolerates_removed_status_widget(app, tmp_path, monkeypatch):
    from textual.css.query import NoMatches

    from henchman.cli import textual_review

    entered, release = threading.Event(), threading.Event()

    def delayed(*_args):
        entered.set()
        assert release.wait(5)
        return tmp_path / "published"

    monkeypatch.setattr(textual_review, "export_review", delayed)
    async with app.run_test(size=(80, 24)) as pilot:
        task, _origin, review = await open_review(app, pilot, ConfirmationRequest("fixture", "Inspect"))
        original = review.query_one
        try:
            review._export("text")
            assert await asyncio.to_thread(entered.wait, 2)

            def missing_status(selector, *args, **kwargs):
                if selector == "#review-status":
                    raise NoMatches("removed during teardown")
                return original(selector, *args, **kwargs)

            monkeypatch.setattr(review, "query_one", missing_status)
            monkeypatch.setattr(review, "_valid", lambda: False)
            release.set()
            await asyncio.wait_for(review._export_task, 5)
        finally:
            monkeypatch.setattr(review, "query_one", original)
            release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def snapshot_at(root: Path) -> ReviewSnapshot:
    info = root.stat()
    return ReviewSnapshot("safe snapshot", root.resolve(), (info.st_dev, info.st_ino))


@pytest.mark.parametrize("component", [".henchman", "exports"])
def test_exports_refuse_linked_directories(tmp_path, component):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / ".henchman"
    if component == "exports":
        link.mkdir()
        link /= "exports"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlink creation unavailable: {error}")
    with pytest.raises(OSError):
        export_review(snapshot_at(root), "safe", "text", lambda: True)
    assert not list(outside.iterdir())


def test_exports_never_overwrite_and_failed_partial_write_cleans_up(tmp_path, monkeypatch):
    from henchman.cli import textual_review

    root = tmp_path.resolve()
    snapshot = snapshot_at(root)
    monkeypatch.setattr(textual_review, "uuid4", lambda: SimpleNamespace(hex="fixed"))
    first = export_review(snapshot, "first complete copy", "text", lambda: True)
    with pytest.raises(FileExistsError):
        export_review(snapshot, "replacement", "text", lambda: True)
    assert first.read_text() == "first complete copy"
    monkeypatch.setattr(textual_review, "uuid4", lambda: SimpleNamespace(hex="second"))
    failure = OSError("fixture write failed")

    def fail(output, data):
        output.write(data[:3])
        raise failure

    monkeypatch.setattr(textual_review, "write_evidence", fail)
    with pytest.raises(OSError) as caught:
        export_review(snapshot, "partial write", "text", lambda: True)
    assert caught.value is failure
    assert list(first.parent.iterdir()) == [first]


@pytest.mark.parametrize("replacement", ["directory", "temporary"])
def test_export_refuses_replaced_directory_or_temporary_before_publication(
    tmp_path, monkeypatch, replacement
):
    from henchman.cli import textual_review

    snapshot = snapshot_at(tmp_path)
    original = textual_review.write_evidence
    moved = tmp_path / "retired-exports"
    outside = tmp_path / "unrelated"
    outside.write_text("unchanged unrelated source")

    def replace_after_write(output, data):
        original(output, data)
        directory = tmp_path / ".henchman" / "exports"
        if replacement == "directory":
            directory.rename(moved)
            directory.mkdir()
        else:
            temporary = next(directory.glob(".*.tmp"))
            temporary.unlink()
            try:
                temporary.symlink_to(outside)
            except OSError as error:
                pytest.skip(f"Symlink creation unavailable: {error}")

    monkeypatch.setattr(textual_review, "write_evidence", replace_after_write)
    with pytest.raises((ValueError, OSError)):
        export_review(snapshot, "safe copy", "text", lambda: True)
    assert outside.read_text() == "unchanged unrelated source"
    assert not list((tmp_path / ".henchman" / "exports").iterdir())
    if moved.exists():
        assert not list(moved.iterdir())


def test_export_refreshes_projection_after_filesystem_wait_and_before_publish(
    tmp_path, monkeypatch
):
    from henchman.cli import textual_review
    from henchman.utils.evidence_redaction import EvidenceRedactor

    secret = "credential-learned-during-write"
    policy = EvidenceRedactor()
    original = textual_review.write_evidence
    writes = 0

    def learn_after_write(output, data):
        nonlocal writes
        writes += 1
        original(output, data)
        policy.register_secret(secret)

    monkeypatch.setattr(textual_review, "write_evidence", learn_after_write)
    path = export_review(snapshot_at(tmp_path), lambda: policy.text(secret), "text", lambda: True)
    assert path.read_text() == "[REDACTED]"
    assert writes == 2
    assert not list(path.parent.glob(".*.tmp"))


def test_export_refuses_projection_change_during_final_link(tmp_path, monkeypatch):
    from henchman.cli import textual_review
    from henchman.utils.evidence_redaction import EvidenceRedactor

    secret = "credential-learned-during-publication"
    policy = EvidenceRedactor()
    original = os.link

    def learn_and_link(*args, **kwargs):
        policy.register_secret(secret)
        return original(*args, **kwargs)

    monkeypatch.setattr(textual_review.os, "link", learn_and_link)
    with pytest.raises(ValueError, match="projection changed"):
        export_review(snapshot_at(tmp_path), lambda: policy.text(secret), "text", lambda: True)
    assert not list((tmp_path / ".henchman" / "exports").iterdir())


async def test_actual_control_c_copies_selection_and_keeps_decision_pending(app):
    async with app.run_test(size=(80, 24)) as pilot:
        task, _origin, review = await open_review(app, pilot, ConfirmationRequest("fixture", "literal review"))
        try:
            area = review.query_one(TextArea)
            area.action_select_all()
            await pilot.press("ctrl+c")
            await settle_layout(pilot)
            assert app.screen is review and not task.done()
            assert app.clipboard == area.text and "literal review" in app.clipboard
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("source", ["question", "transcript"])
async def test_later_credential_learning_cannot_leave_a_cutoff_prefix(app, source):
    prefix = "CUTOFF-PRIVATE-PREFIX"
    raw = prefix + "-remaining-sensitive-value"
    limit = 26000 if source == "question" else 8192
    text = "x" * (limit - len(prefix) - 50) + raw + "z" * 200
    async with app.run_test(size=(80, 24)) as pilot:
        if source == "question":
            task = asyncio.create_task(app._textual_question(text))
            await settle_layout(pilot)
            await pilot.press("f10")
            await settle_layout(pilot)
            review = app.screen
        else:
            app.query_one(ChatPane).add_user_message(text)
            task, _origin, review = await open_review(app, pilot, ConfirmationRequest("fixture", "Inspect"))
        try:
            runtime_evidence_redactor(app).register_secret(raw)
            review.copy_evidence()
            assert prefix not in app.clipboard
            assert "omitted" in app.clipboard.lower()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("label", ["agent", "call", "name", "target", "entry"])
async def test_already_clipped_tool_observation_is_explicitly_omitted(app, label):
    from henchman.core.events import AgentEvent, EventType
    from henchman.providers.base import ToolCall
    from tests.cli.test_textual_tool_activity import send

    prefix = "retained-tool-private-prefix-"
    secret = prefix + "z" * 300
    agent = secret if label == "agent" else "worker"
    call = secret if label == "call" else "call"
    name = secret if label == "name" else "write_file"
    path = secret if label == "target" else "file"
    result = "x" * 33000 if label == "entry" else "finished"
    async with app.run_test(size=(80, 24)) as pilot:
        await send(app, [
            AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall(call, name, {"path": path}), agent),
            AgentEvent(EventType.TOOL_CALL_RESULT, {
                "tool_call_id": call, "tool_name": name, "success": True, "result": result,
            }, agent),
        ])
        await settle_layout(pilot)
        task, _origin, review = await open_review(app, pilot, ConfirmationRequest("fixture", "Inspect"))
        try:
            runtime_evidence_redactor(app).register_secret(secret)
            review.copy_evidence()
            assert prefix not in app.clipboard
            assert "already-clipped tool observation omitted" in app.clipboard.lower()
            review._export("text")
            # Export joins a real filesystem worker, including fsync. Allow for
            # slow native storage while still requiring a completed publication.
            await asyncio.wait_for(review._export_task, 10)
            exports = list((review.snapshot.root / ".henchman" / "exports").glob("*.txt"))
            assert len(exports) == 1
            assert prefix not in exports[0].read_text()
            assert not task.done()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_review_returns_focus_and_preserves_held_viewport_during_new_chunks(app):
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        for index in range(35):
            chat.add_user_message(f"history {index}\n" + "context " * 30)
        await settle_layout(pilot)
        chat.scroll_to(y=20, animate=False)
        chat.hold_reading_position()
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("draft line one\nline two")
        await settle_layout(pilot)
        previous_y = chat.scroll_offset.y
        task, origin, review = await open_review(
            app, pilot, ConfirmationRequest("fixture", "Inspect")
        )
        try:
            frozen_text = review.query_one(TextArea).text
            chat.add_user_message("new content after captured snapshot")
            await pilot.resize_terminal(120, 40)
            await settle_layout(pilot)
            assert review.query_one(TextArea).text == frozen_text
            await pilot.press("y", "ctrl+enter", "n")
            assert not task.done()
            await pilot.press("escape")
            await settle_layout(pilot)
            assert app.screen is origin and app.focused.id == "btn-no"
            assert composer.text == "draft line one\nline two" and not chat.follow_live
            # A width change may reflow earlier rows; its retained anchor is
            # authoritative, rather than requiring the old numeric y position.
            assert previous_y > 0 and chat.scroll_offset.y < chat.max_scroll_y
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_fallback_project_change_blocks_old_review_export(app, tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    async with app.run_test(size=(80, 24)) as pilot:
        task, _origin, review = await open_review(
            app, pilot, ConfirmationRequest("fixture", "Inspect")
        )
        try:
            monkeypatch.chdir(other)
            review._export("text")
            review.copy_evidence()
            await pilot.pause()
            assert not (other / ".henchman").exists()
            assert not (tmp_path / ".henchman" / "exports").exists()
            assert not task.done()
        finally:
            monkeypatch.chdir(tmp_path)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_selected_session_and_actor_credentials_are_refreshed_for_review(app, tmp_path):
    from henchman.core.session_data import Session

    previous, current = "retained-session-private", "selected-actor-private"
    now = datetime.now(UTC)
    session = Session(
        id="review-session", project_hash="fixture-project", started=now, last_updated=now
    )
    session.evidence_redactor.register_secret(previous)
    actor_provider = SimpleNamespace(name="fixture", model="local", api_key=current)
    actor = SimpleNamespace(provider=actor_provider)
    context = SimpleNamespace(
        project_root=tmp_path,
        session_manager=SimpleNamespace(current=session),
        agent=actor,
        orchestrator=SimpleNamespace(pool=SimpleNamespace(_agents={app.config.agent_role: actor})),
    )
    async with app.run_test(size=(80, 24)) as pilot:
        app.core_context = context
        task, _origin, review = await open_review(
            app, pilot, ConfirmationRequest("fixture", f"{previous} {current}")
        )
        try:
            text = review.query_one(TextArea).text
            assert previous not in text and current not in text
            rotated = "rotated-session-private"
            session.evidence_redactor.register_secret(rotated)
            # Existing captured text contains only projected evidence; a new
            # selection must not acquire the old review's copy/export controls.
            context.session_manager.current = Session(
                id="new-selection", project_hash="fixture-project", started=now, last_updated=now
            )
            review._export("text")
            review.copy_evidence()
            assert not (tmp_path / ".henchman" / "exports").exists()
            assert not task.done()
        finally:
            app.core_context = None
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_clipboard_failure_retains_original_policy_if_runtime_policy_changes(
    app, tmp_path, monkeypatch
):
    from henchman.utils.evidence_redaction import EvidenceRedactor

    raw = "old-review-policy-private"
    manager = SimpleNamespace(evidence_redactor=EvidenceRedactor([raw]), current=None)
    context = SimpleNamespace(project_root=tmp_path, session_manager=manager)
    async with app.run_test(size=(80, 24)) as pilot:
        app.core_context = context
        task, _origin, review = await open_review(
            app, pilot, ConfirmationRequest("fixture", "Inspect")
        )
        try:

            def fail(_text):
                manager.evidence_redactor = EvidenceRedactor()
                raise OSError("clipboard failed " + raw)

            monkeypatch.setattr(app, "copy_to_clipboard", fail)
            review.copy_evidence()
            status = str(review.query_one("#review-status").render())
            assert raw not in status and "clipboard failed" in status
            assert not task.done()
        finally:
            app.core_context = None
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("shape", ["wide", "deep", "cycle", "unsupported"])
async def test_request_is_bounded_before_recursive_projection_or_serialization(app, shape):
    class Unprintable:
        def __str__(self):
            raise AssertionError("unbounded display must not stringify unknown objects")

    if shape == "wide":
        params = {f"field-{n}": "value" for n in range(5000)}
    elif shape == "deep":
        params = {}
        current = params
        for _ in range(50):
            current["nested"] = {}
            current = current["nested"]
    elif shape == "cycle":
        params = {}
        params["cycle"] = params
    else:
        params = {"object": Unprintable()}
    request = ConfirmationRequest("fixture", "Inspect", params)
    async with app.run_test(size=(80, 24)) as pilot:
        task = asyncio.create_task(app._textual_confirm(request))
        try:
            await settle_layout(pilot)
            assert not task.done(), task.exception() if task.done() else None
            await pilot.press("f10")
            await settle_layout(pilot)
            text = app.screen.query_one(TextArea).text
            assert "omitted" in text.lower() and len(text.encode()) <= 65536
            assert request.params is params
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_snapshot_has_explicit_bounds_and_wrapping_does_not_change_source(app):
    async with app.run_test(size=(80, 24)) as pilot:
        chat = app.query_one(ChatPane)
        for n in range(90):
            chat.add_user_message(f"row {n}\n" + "x" * 1000)
        task, _origin, review = await open_review(
            app, pilot, ConfirmationRequest("fixture", "Inspect", {"large": "a" * 100000})
        )
        try:
            text = review.query_one(TextArea).text
            assert len(text.encode()) <= 65536
            assert "omitted" in text.lower()
            await pilot.resize_terminal(120, 40)
            await settle_layout(pilot)
            assert review.query_one(TextArea).text == text
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
