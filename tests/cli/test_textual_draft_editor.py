"""Mounted external composition preserves user authority and draft ownership."""
import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from textual.widgets import TextArea

from henchman.cli import textual_editor
from henchman.cli.textual_questions import QuestionScreen
from tests.cli.ui_scenarios import InteractionApp, settle_layout


@contextmanager
def suspended():
    yield


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_editor_returns_only_to_draft_and_restores_focus(tmp_path, monkeypatch, size):
    app = InteractionApp(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    async def edit(text, *, cwd, authorize):
        assert cwd.is_dir()
        authorize()
        assert text == "raw café\nsecond"
        entered.set()
        await release.wait()
        authorize()
        return text + "\nedited"
    monkeypatch.setattr(textual_editor, "edit_draft", edit)
    monkeypatch.setattr(app, "suspend", suspended)
    async with app.run_test(size=size) as pilot:
        composer = app.query_one("#input", TextArea)
        composer.load_text("raw café\nsecond")
        composer.focus()
        await pilot.press("f11")
        await asyncio.wait_for(entered.wait(), 3)
        assert composer.read_only
        assert not app.submitted
        release.set()
        await app._draft_editor.task
        await settle_layout(pilot)
        assert composer.text == "raw café\nsecond\nedited"
        assert not composer.read_only and app.focused is composer
        assert not app.submitted and not app._queued_inputs()


async def test_modal_and_work_refuse_without_disturbing_draft(tmp_path, monkeypatch):
    app = InteractionApp(tmp_path)
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("must not launch")
    monkeypatch.setattr(textual_editor, "edit_draft", forbidden)
    async with app.run_test() as pilot:
        composer = app.query_one("#input", TextArea)
        composer.load_text("keep")
        screen = QuestionScreen("existing decision")
        app.push_screen(screen)
        await settle_layout(pilot)
        textual_editor.start_external_editor(app)
        assert app.screen is screen and composer.text == "keep"
        screen.dismiss(None)
        await settle_layout(pilot)
        app.is_processing = True
        textual_editor.start_external_editor(app)
        assert composer.text == "keep" and getattr(app, "_draft_editor", None) is None
        app.is_processing = False


async def test_changed_draft_is_held_for_explicit_recovery(tmp_path, monkeypatch):
    app = InteractionApp(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    async def edit(_text, **_kwargs):
        entered.set()
        await release.wait()
        return "edited private draft"
    monkeypatch.setattr(textual_editor, "edit_draft", edit)
    monkeypatch.setattr(app, "suspend", suspended)
    async with app.run_test(size=(80, 24)) as pilot:
        composer = app.query_one("#input", TextArea)
        composer.load_text("original")
        textual_editor.start_external_editor(app)
        await entered.wait()
        composer.load_text("newer draft")
        release.set()
        await app._draft_editor.task
        assert composer.text == "newer draft"
        textual_editor.start_external_editor(app)
        await settle_layout(pilot)
        assert isinstance(app.screen, textual_editor.DraftRecoveryScreen)
        await pilot.press("escape")
        await settle_layout(pilot)
        assert composer.text == "newer draft" and app._draft_editor.recovery is not None
        textual_editor.start_external_editor(app)
        await settle_layout(pilot)
        await pilot.click("#draft-recovery-use")
        await settle_layout(pilot)
        assert composer.text == "edited private draft" and not app.submitted
        assert app._draft_editor.recovery is None


async def test_shutdown_joins_cleanup_and_preserves_first_caller_cancel(tmp_path, monkeypatch):
    app = InteractionApp(tmp_path)
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def edit(_text, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
    monkeypatch.setattr(textual_editor, "edit_draft", edit)
    monkeypatch.setattr(app, "suspend", suspended)
    async with app.run_test():
        composer = app.query_one("#input", TextArea)
        composer.load_text("original")
        textual_editor.start_external_editor(app)
        await entered.wait()
        close = asyncio.create_task(textual_editor.close_external_editor(app))
        await cleaning.wait()
        close.cancel("first shutdown")
        await asyncio.sleep(0)
        close.cancel("second shutdown")
        await asyncio.sleep(0)
        assert not close.done()
        release.set()
        with pytest.raises(asyncio.CancelledError, match="first shutdown"):
            await close
        await textual_editor.close_external_editor(app)
        assert app._draft_editor.task.done() and not composer.read_only
        assert composer.text == "original"


async def test_suspend_context_resumes_normally_on_editor_failure(tmp_path, monkeypatch):
    app = InteractionApp(tmp_path)
    resumed = []
    @contextmanager
    def vulnerable_suspend():
        yield
        resumed.append(True)  # Textual's suspend resumes after yield, not finally.
    async def fail(*_args, **_kwargs):
        raise RuntimeError("private exception canary")
    monkeypatch.setattr(app, "suspend", vulnerable_suspend)
    monkeypatch.setattr(textual_editor, "edit_draft", fail)
    async with app.run_test():
        composer = app.query_one("#input", TextArea)
        composer.load_text("keep")
        textual_editor.start_external_editor(app)
        await app._draft_editor.task
        assert resumed == [True] and composer.text == "keep"
        assert not composer.read_only


async def test_current_policy_revocation_and_session_change_never_replace_draft(tmp_path, monkeypatch):
    app = InteractionApp(tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    async def edit(_text, *, authorize, **_kwargs):
        authorize()
        entered.set()
        await release.wait()
        authorize()
        return "must not apply"
    monkeypatch.setattr(textual_editor, "edit_draft", edit)
    monkeypatch.setattr(app, "suspend", suspended)
    async with app.run_test() as pilot:
        composer = app.query_one("#input", TextArea)
        composer.load_text("keep")
        await pilot.press("f11")
        await entered.wait()
        app.settings.tools.network_access = "disabled"
        release.set()
        await app._draft_editor.task
        assert composer.text == "keep" and not composer.read_only
        assert not app.submitted


async def test_visible_button_cancel_priority_and_composer_selection_keys(tmp_path, monkeypatch):
    app = InteractionApp(tmp_path)
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def edit(_text, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
    monkeypatch.setattr(textual_editor, "edit_draft", edit)
    monkeypatch.setattr(app, "suspend", suspended)
    async with app.run_test(size=(120, 40)) as pilot:
        composer = app.query_one("#input", TextArea)
        composer.load_text("line one\nline two")
        composer.focus()
        await pilot.press("f6")
        assert composer.selected_text == "line one"
        await pilot.press("f7")
        assert composer.selected_text == "line one\nline two"
        await pilot.click("#external-editor")
        await entered.wait()
        app.action_cancel_or_clear()
        await cleaning.wait()
        app.action_cancel_or_clear()
        assert not app._draft_editor.task.done() and composer.text == "line one\nline two"
        release.set()
        await app._draft_editor.task
        assert composer.selected_text == "line one\nline two"
        assert not app.submitted


async def test_actual_unmount_waits_for_editor_before_core_cleanup(tmp_path, monkeypatch):
    app = InteractionApp(tmp_path)
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    order = []
    async def edit(_text, **_kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()
            order.append("editor")
    class OwnedOrchestrator:
        async def aclose(self):
            order.append("orchestrator")
    monkeypatch.setattr(textual_editor, "edit_draft", edit)
    monkeypatch.setattr(app, "suspend", suspended)
    async with app.run_test() as pilot:
        app.core_context = SimpleNamespace(orchestrator=OwnedOrchestrator(), background_tasks=[], mcp_manager=None, session_manager=None)
        await pilot.press("f11")
        await entered.wait()
        teardown = asyncio.create_task(app.on_unmount())
        await cleaning.wait()
        assert not teardown.done() and order == []
        release.set()
        await teardown
        assert order[:2] == ["editor", "orchestrator"]
        assert not app._draft_editor.task.cancelled()


@pytest.mark.parametrize("change", ["configured_root", "replaced_root", "symlink_root", "manager"])
async def test_editor_rechecks_original_context_and_physical_root(tmp_path, monkeypatch, change):
    project = tmp_path / "project"
    project.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    app = InteractionApp(project)
    entered, release = asyncio.Event(), asyncio.Event()
    async def edit(_text, *, authorize, **_kwargs):
        authorize()
        entered.set()
        await release.wait()
        authorize()
        return "must not replace original"
    monkeypatch.setattr(textual_editor, "edit_draft", edit)
    monkeypatch.setattr(app, "suspend", suspended)
    async with app.run_test() as pilot:
        manager = SimpleNamespace(current=object())
        context = SimpleNamespace(project_root=project, session_manager=manager, settings=app.settings)
        app.core_context = context
        composer = app.query_one("#input", TextArea)
        composer.load_text("original")
        await pilot.press("f11")
        await entered.wait()
        if change == "configured_root":
            context.project_root = other
        elif change == "manager":
            context.session_manager = SimpleNamespace(current=manager.current)
        else:
            project.rename(tmp_path / "old")
            if change == "replaced_root":
                project.mkdir()
            else:
                try:
                    project.symlink_to(tmp_path / "old", target_is_directory=True)
                except OSError:
                    release.set()
                    await app._draft_editor.task
                    app.core_context = None
                    pytest.skip("Symlink privilege is unavailable")
        release.set()
        await app._draft_editor.task
        assert composer.text == "original" and not app.submitted
        app.core_context = None
