"""Actual project sessions are inspected without changing runtime authority."""

from __future__ import annotations

import asyncio
from threading import Event
from types import SimpleNamespace

import pytest
from textual.widgets import Input, OptionList, TextArea

from henchman.cli.session_manager import ReplSessionManager
from henchman.core.agent import Agent
from henchman.core.session import SessionManager, SessionMessage
from henchman.tools.registry import ToolRegistry
from tests.cli.ui_scenarios import InteractionApp, settle_layout


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = InteractionApp(tmp_path)
    app.config.agent_role = None
    core = SessionManager(data_dir=tmp_path / "sessions")
    manager = ReplSessionManager(core, auto_save=False, settings=app.settings)
    project = core.compute_project_hash(tmp_path)
    current = core.create_session(project, "current unsaved")
    actor = Agent(app.provider, system_prompt="held system")
    manager.set_session(current, history_agent=actor)
    candidate = core.create_session(project, "resume intended")
    candidate.messages.append(SessionMessage("user", "saved user history"))
    core.save(candidate)
    foreign = core.create_session("foreign-project", "FOREIGN-PRIVATE")
    core.save(foreign)
    return app, manager, actor, candidate


def bind(app, manager, actor, tmp_path):
    async def close():
        pass
    app.core_context = SimpleNamespace(
        session_manager=manager, project_root=tmp_path, agent=actor,
        orchestrator=SimpleNamespace(tech_lead=actor, pool=SimpleNamespace(_agents={}), subagents=None, aclose=close),
        background_tasks=[], mcp_manager=None,
    )


def test_shared_restore_failure_does_not_partially_switch_live_authority(runtime, monkeypatch):
    _app, manager, actor, candidate = runtime
    previous = manager.current
    registry = ToolRegistry()
    manager.bind_tool_registry(registry)
    failure = OSError("fixture grant retirement failed")
    monkeypatch.setattr(registry, "clear_grants", lambda: (_ for _ in ()).throw(failure))
    with pytest.raises(OSError) as caught:
        manager.set_session(candidate, history_agent=actor)
    assert caught.value is failure
    assert manager.current is previous
    assert manager.session_manager.current is previous


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_keyboard_project_search_inspect_back_and_explicit_resume(runtime, tmp_path, size):
    from henchman.cli.textual_widgets import HenchmanTextArea

    app, manager, actor, candidate = runtime
    async with app.run_test(size=size) as pilot:
        bind(app, manager, actor, tmp_path)
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("unsent preserved draft")
        composer.focus()
        app.action_session_browser()
        await settle_layout(pilot)
        screen = app.screen
        try:
            for _ in range(10):
                await pilot.pause()
                if not screen._busy:
                    break
            screen.query_one(Input).value = "intended"
            await pilot.pause()
            options = screen.query_one(OptionList)
            assert options.option_count == 1
            assert all(item.project_hash == manager.current.project_hash for item in screen._sessions)
            await pilot.press("tab")
            assert app.focused is options
            await pilot.press("enter")
            await settle_layout(pilot)
            assert manager.current.id != candidate.id
            assert "Persisted session" in screen.query_one(TextArea).text
            assert "FOREIGN-PRIVATE" not in screen.query_one(TextArea).text
            await pilot.click("#sessions-resume")
            await pilot.pause()
            assert manager.current.id != candidate.id
            await pilot.click("#sessions-without-save")
            await settle_layout(pilot)
            assert manager.current.id == candidate.id
            assert actor.messages[-1].content == "saved user history"
            assert composer.text == "unsent preserved draft"
            assert manager.workflow_runtime.next_input() is None
            await pilot.press("escape")
            await settle_layout(pilot)
            assert len(app.screen_stack) == 1 and app.focused is composer
            assert composer.text == "unsent preserved draft"
        finally:
            app.core_context = None


async def select_candidate(app, pilot):
    app.action_session_browser()
    await settle_layout(pilot)
    screen = app.screen
    if screen._action_task is not None:
        await screen._action_task
    screen.query_one(Input).value = "intended"
    await pilot.pause()
    screen.action_inspect()
    await screen._action_task
    await pilot.pause()
    return screen


@pytest.mark.parametrize("change", ["cwd", "settings", "policy", "provider", "session", "saved-file"])
async def test_stale_browser_cannot_activate_old_selection(runtime, tmp_path, monkeypatch, change):
    from henchman.config.schema import Settings

    app, manager, actor, candidate = runtime
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            screen = await select_candidate(app, pilot)
            previous = manager.current
            screen._confirm()
            if change == "cwd":
                other = tmp_path / "other"
                other.mkdir()
                monkeypatch.chdir(other)
            elif change == "settings":
                app.settings = Settings()
            elif change == "policy":
                app.settings.tools.network_access = "disabled"
            elif change == "provider":
                actor.provider = SimpleNamespace(name="replacement", model="replacement")
            elif change == "session":
                previous = manager.create_session(previous.project_hash, "another")
                manager.set_session(previous, history_agent=actor)
            else:
                candidate.messages.append(SessionMessage("user", "changed after inspection"))
                manager.save(candidate)
            screen._activate(save=False)
            await screen._action_task
            assert manager.current is previous
            assert "changed" in screen._status.lower()
            assert not screen._resume_completed
        finally:
            app.core_context = None


@pytest.mark.parametrize("ack_loss", [False, True])
async def test_save_failure_keeps_selection_and_never_claims_resume(runtime, tmp_path, monkeypatch, ack_loss):
    app, manager, actor, _candidate = runtime
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            screen = await select_candidate(app, pilot)
            previous = manager.current
            original = manager.save
            def fail(session):
                if ack_loss:
                    original(session)
                raise OSError("disk save acknowledgement unavailable")
            monkeypatch.setattr(manager, "save", fail)
            screen._confirm()
            screen._activate(save=True)
            await screen._action_task
            assert manager.current is previous and not screen._resume_completed
            assert "acknowledgement unavailable" in screen._status
        finally:
            app.core_context = None


async def test_cancelled_read_is_joined_and_preserves_first_control(runtime, tmp_path, monkeypatch):
    app, manager, actor, _candidate = runtime
    entered, release, exited = Event(), Event(), Event()
    original = manager.list_sessions
    def delayed(project):
        entered.set()
        try:
            assert release.wait(5)
            return original(project)
        finally:
            exited.set()
    monkeypatch.setattr(manager, "list_sessions", delayed)
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            previous = manager.current
            app.action_session_browser()
            await settle_layout(pilot)
            screen = app.screen
            assert await asyncio.to_thread(entered.wait, 2)
            closing = asyncio.create_task(screen.action_cancel())
            await asyncio.sleep(0)
            closing.cancel("first caller cancellation")
            await asyncio.sleep(0)
            closing.cancel("second caller cancellation")
            await asyncio.sleep(0)
            assert not closing.done() and not exited.is_set()
            release.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await closing
            assert caught.value.args == ("first caller cancellation",)
            assert exited.is_set() and manager.current is previous
            await screen.action_cancel()
        finally:
            release.set()
            app.core_context = None


async def test_saved_current_cannot_replace_its_unsaved_live_history(runtime, tmp_path):
    app, manager, actor, _candidate = runtime
    manager.save()
    previous = manager.current
    previous.messages.append(SessionMessage("user", "unsaved current change"))
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            screen = await select_candidate(app, pilot)
            screen.query_one(Input).value = "current unsaved"
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            screen._confirm()
            assert "current" in screen._status.lower()
            screen._activate(save=False)
            if screen._action_task is not None:
                await screen._action_task
            assert manager.current is previous
            assert previous.messages[-1].content == "unsaved current change"
        finally:
            app.core_context = None


async def test_candidate_changed_during_current_save_requires_new_inspection(runtime, tmp_path, monkeypatch):
    app, manager, actor, candidate = runtime
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            screen = await select_candidate(app, pilot)
            previous = manager.current
            original = manager.save
            def save_then_replace(session):
                path = original(session)
                candidate.messages.append(SessionMessage("user", "external change during save"))
                manager.session_manager.save(candidate)
                return path
            monkeypatch.setattr(manager, "save", save_then_replace)
            screen._confirm()
            screen._activate(save=True)
            await screen._action_task
            assert manager.current is previous
            assert "changed" in screen._status.lower() and not screen._resume_completed
        finally:
            app.core_context = None


async def test_pending_decision_keeps_priority_and_busy_resume_refuses(runtime, tmp_path):
    from henchman.tools.base import ConfirmationRequest

    app, manager, actor, _candidate = runtime
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        prompt = asyncio.create_task(app._textual_confirm(ConfirmationRequest("fixture", "Decide")))
        try:
            await settle_layout(pilot)
            origin = app.screen
            app.action_session_browser()
            await pilot.pause()
            assert app.screen is origin and not prompt.done()
            await pilot.press("n")
            assert await prompt is False
            screen = await select_candidate(app, pilot)
            previous = manager.current
            app.is_processing = True
            screen._confirm()
            screen._activate(save=False)
            await screen._action_task
            assert manager.current is previous and not screen._resume_completed
            assert "idle" in screen._status.lower()
        finally:
            app.is_processing = False
            prompt.cancel()
            await asyncio.gather(prompt, return_exceptions=True)
            app.core_context = None


async def test_details_selection_copy_refreshes_rotated_credentials(runtime, tmp_path):
    from henchman.cli.evidence import runtime_evidence_redactor

    app, manager, actor, candidate = runtime
    secret = "later-known-session-private"
    candidate.tag = "resume intended " + secret
    manager.save(candidate)
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            screen = await select_candidate(app, pilot)
            area = screen.query_one(TextArea)
            area.focus()
            area.action_select_all()
            runtime_evidence_redactor(app).register_secret(secret)
            area.action_copy()
            assert secret not in app.clipboard
            await pilot.press("ctrl+c")
            assert secret not in app.clipboard
            assert secret not in area.text
        finally:
            app.core_context = None


async def test_browse_preserves_files_and_durable_resume_holds_saved_inputs(runtime, tmp_path):
    from henchman.core.session_workflow import SessionWorkflow

    app, manager, actor, candidate = runtime
    app.settings.operations.persistence = "durable"
    writer = SessionWorkflow(app.settings, lambda: candidate, manager.session_manager.save, tmp_path / "ops.db")
    writer.attach(candidate)
    queued = writer.submit("never automatically send")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            previous = manager.current
            screen = await select_candidate(app, pilot)
            assert manager.current is previous
            assert all(path.read_bytes() == data for path, data in before.items())
            assert "durable" in screen.query_one(TextArea).text
            screen._confirm()
            screen._activate(save=False)
            await screen._action_task
            assert manager.current.id == candidate.id
            report = manager.workflow_runtime.report()
            assert report.state.inputs[0].id == queued.id
            assert manager.workflow_runtime.next_input() is None
        finally:
            app.core_context = None


async def test_visible_sessions_button_and_successful_save_preserve_draft(runtime, tmp_path):
    from textual.widgets import TabbedContent

    from henchman.cli.textual_widgets import HenchmanTextArea

    app, manager, actor, candidate = runtime
    previous = manager.current
    previous.messages.append(SessionMessage("user", "persist this current turn"))
    async with app.run_test(size=(80, 24)) as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            app.query_one(HenchmanTextArea).load_text("draft must not be saved")
            app.query_one(TabbedContent).active = "tab-context"
            await settle_layout(pilot)
            assert await pilot.click("#context-sessions")
            await settle_layout(pilot)
            screen = app.screen
            await screen._action_task
            screen.query_one(Input).value = "intended"
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            screen._confirm()
            screen._activate(save=True)
            await screen._action_task
            assert manager.current.id == candidate.id
            saved = manager.load(previous.id, project_hash=previous.project_hash)
            assert [m.content for m in saved.messages] == ["persist this current turn"]
            assert "Current session saved" in screen._status
            assert app.query_one(HenchmanTextArea).text == "draft must not be saved"
        finally:
            app.core_context = None


async def test_explicit_resume_does_not_begin_or_double_count_durable_usage(runtime, tmp_path):
    from henchman.core.run_budget import RequestEstimate
    from henchman.core.session_run_accounting import SessionRunAccounting
    from henchman.providers.usage import UsageReport
    from tests.agents.test_agent_budget_scope import AccountingProvider

    app, manager, actor, candidate = runtime
    app.settings.usage.persistence = "durable"
    stored = SessionRunAccounting(app.settings, lambda: candidate, manager.session_manager.save, tmp_path / "ops.db")
    scope = stored.begin(AccountingProvider())
    request = scope.ledger.reserve(RequestEstimate(4, 2), provider="test", model="test-model")
    assert scope.ledger.start(request.request_id)
    scope.ledger.reconcile(request.request_id, UsageReport(prompt_tokens=4, completion_tokens=1, source="reported"), final=True)
    before = scope.ledger.snapshot()
    live = SessionRunAccounting(app.settings, lambda: manager.current, manager.session_manager.save, tmp_path / "ops.db")
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        app.core_context.orchestrator.accounting_runtime = live
        try:
            screen = await select_candidate(app, pilot)
            screen._confirm()
            screen._activate(save=False)
            await screen._action_task
            after = live.usage_snapshot(manager.current)
            assert manager.current.id == candidate.id
            assert after.run_id == before.run_id
            assert after.consumed_requests == before.consumed_requests == 1
            assert after.settled_tokens == before.settled_tokens == 5
            assert [item.request_id for item in after.records] == [request.request_id]
        finally:
            app.core_context = None


async def test_actual_restore_failure_is_visible_without_successful_switch(runtime, tmp_path, monkeypatch):
    app, manager, actor, _candidate = runtime
    registry = ToolRegistry()
    manager.bind_tool_registry(registry)
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            screen = await select_candidate(app, pilot)
            previous, messages = manager.current, list(actor.messages)
            monkeypatch.setattr(registry, "clear_grants", lambda: (_ for _ in ()).throw(OSError("activation retirement failed")))
            screen._confirm()
            screen._activate(save=False)
            await screen._action_task
            assert manager.current is previous and manager.session_manager.current is previous
            assert actor.messages == messages
            assert "activation retirement failed" in screen._status
            assert not screen._resume_completed
        finally:
            app.core_context = None


async def test_oversized_tag_does_not_hide_searchable_session_identity(runtime, tmp_path):
    app, manager, actor, candidate = runtime
    candidate.tag = "x" * 5000
    manager.save(candidate)
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            app.action_session_browser()
            await settle_layout(pilot)
            screen = app.screen
            await screen._action_task
            screen.query_one(Input).value = candidate.id
            await pilot.pause()
            assert screen.query_one(OptionList).option_count == 1
            assert "omitted" in screen._labels[0].lower()
            assert candidate.id in screen._labels[0]
        finally:
            app.core_context = None


@pytest.mark.parametrize("phase", ["inspect", "activate", "save"])
async def test_selection_changes_during_owned_reads_never_publish_or_activate_old_candidate(runtime, tmp_path, monkeypatch, phase):
    app, manager, actor, candidate = runtime
    other = manager.create_session(candidate.project_hash, "other candidate")
    manager.save(other)
    entered, release = Event(), Event()
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            screen = await select_candidate(app, pilot)
            previous = manager.current
            original = manager.save if phase == "save" else manager.load
            def waiting(*args, **kwargs):
                entered.set()
                assert release.wait(5)
                return original(*args, **kwargs)
            monkeypatch.setattr(manager, "save" if phase == "save" else "load", waiting)
            if phase == "inspect":
                screen.action_inspect()
            else:
                screen._confirm()
                screen._activate(save=phase == "save")
            assert await asyncio.to_thread(entered.wait, 2)
            screen.query_one(Input).value = "other candidate"
            await pilot.pause()
            release.set()
            await screen._action_task
            assert screen._ids == [other.id] and screen._candidate is None
            assert manager.current is previous and not screen._resume_completed
        finally:
            release.set()
            app.core_context = None


async def test_changed_secret_bytes_cannot_hide_behind_equal_redacted_candidate(runtime, tmp_path):
    import json

    app, manager, actor, candidate = runtime
    old, new = "candidate-secret-old", "candidate-secret-new"
    candidate.tag = "resume intended " + old
    path = manager.save(candidate)
    manager.session_manager.evidence_redactor.register_secret(old)
    manager.session_manager.evidence_redactor.register_secret(new)
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            screen = await select_candidate(app, pilot)
            previous = manager.current
            raw = path.read_bytes()
            assert old.encode() in raw
            # A valid legacy generation has no integrity envelope. Both parsed
            # sessions project identically, while their exact storage differs.
            payload = json.loads(raw)
            payload.pop("_storage")
            payload["tag"] = payload["tag"].replace(old, new)
            path.write_text(json.dumps(payload))
            changed = manager.load(candidate.id, project_hash=candidate.project_hash)
            assert changed.to_json() == screen._candidate.to_json()
            screen._confirm()
            screen._activate(save=False)
            await screen._action_task
            assert manager.current is previous and not screen._resume_completed
            assert "changed" in screen._status.lower()
        finally:
            app.core_context = None


async def test_prior_generation_recovery_notice_is_visible_before_resume(runtime, tmp_path):
    app, manager, actor, candidate = runtime
    candidate.messages.append(SessionMessage("user", "newer possibly lost turn"))
    path = manager.save(candidate)
    path.write_bytes(b"corrupt current copy")
    async with app.run_test() as pilot:
        bind(app, manager, actor, tmp_path)
        try:
            with pytest.warns(UserWarning, match="Recovered prior session"):
                screen = await select_candidate(app, pilot)
            details = screen.query_one(TextArea).text
            assert "Recovered prior session" in details
            assert "Recent changes may be missing" in details
            assert manager.current.id != candidate.id
        finally:
            app.core_context = None
