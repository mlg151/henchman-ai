"""Rendered checkpoint decisions use real shared revision/content authority."""

import asyncio
from threading import Event
from types import SimpleNamespace

import pytest
from textual.widgets import Button, Static, TextArea

from henchman.advanced.checkpoint_models import CheckpointOperation
from henchman.advanced.checkpoints import CheckpointService
from henchman.cli.textual_checkpoints import CheckpointReviewScreen
from henchman.cli.textual_widgets import HenchmanTextArea
from tests.cli.ui_scenarios import InteractionApp, settle_layout


def capture(root):
    path = root / "file.txt"
    path.write_text("first\nkeep\nlast\n")
    service = CheckpointService(root)
    record = service.begin(["file.txt"], actor="engineer",
                           operation=CheckpointOperation("operation", "run", "engineer", "edit_file"))
    path.write_text("FIRST\nkeep\nLAST\n")
    service.complete(record.checkpoint_id)
    return service, record.checkpoint_id


async def ready(pilot):
    await settle_layout(pilot)
    screen = pilot.app.screen
    if isinstance(screen, CheckpointReviewScreen) and screen._action_task is not None:
        await asyncio.wait_for(asyncio.shield(screen._action_task), 10)
    await settle_layout(pilot)
    return screen


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_keyboard_hunk_preview_apply_and_back_preserve_draft(tmp_path, monkeypatch, size):
    monkeypatch.chdir(tmp_path)
    service, identity = capture(tmp_path)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=size) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("Keep this\nunsent draft")
        composer.focus()
        await pilot.press("f8")
        screen = await ready(pilot)
        assert isinstance(screen, CheckpointReviewScreen)
        await pilot.press("enter")  # capture → files
        await ready(pilot)
        await pilot.press("enter", "n", "r")  # file → first hunk → reject preview
        await ready(pilot)
        assert (tmp_path / "file.txt").read_text() == "FIRST\nkeep\nLAST\n"
        assert screen._plan is not None and screen._plan.revision == service.review(identity).revision
        apply = screen.query_one("#checkpoint-apply", Button)
        assert not apply.disabled and apply.region.bottom <= size[1]
        assert screen.query_one("#checkpoint-content", TextArea).region.height > 0
        apply.focus()
        await pilot.press("enter")
        await ready(pilot)
        assert (tmp_path / "file.txt").read_text() == "first\nkeep\nLAST\n"
        assert "operation" in screen.query_one("#checkpoint-content", TextArea).text
        await pilot.press("escape", "escape", "escape")
        await ready(pilot)
        assert app.screen is not screen
        assert composer.text == "Keep this\nunsent draft" and app.focused is composer


async def test_apply_conflict_preserves_user_work_and_requires_new_preview(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "r")
        await ready(pilot)
        (tmp_path / "file.txt").write_text("intervening user edit")
        screen.query_one("#checkpoint-apply", Button).focus()
        await pilot.press("enter")
        await ready(pilot)
        assert (tmp_path / "file.txt").read_text() == "intervening user edit"
        assert "conflict" in str(screen.query_one("#checkpoint-status", Static).render()).lower()
        assert screen._plan is None and screen.query_one("#checkpoint-apply", Button).disabled


@pytest.mark.parametrize("busy", ["agent", "approval", "operation", "subagent", "background"])
async def test_apply_requires_current_runtime_idle(tmp_path, monkeypatch, busy):
    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "r")
        await ready(pilot)
        if busy == "agent":
            app.is_processing = True
        elif busy == "approval":
            app._tool_prompts._answer = asyncio.get_running_loop().create_future()
        elif busy == "background":
            from henchman.advanced.tasks import TaskService
            monkeypatch.setattr(TaskService, "has_active_work", classmethod(lambda _cls, _root: True))
        else:
            app.core_context = SimpleNamespace(orchestrator=SimpleNamespace(
                operation_runtime=SimpleNamespace(_inflight={"op": object()} if busy == "operation" else {}),
                subagents=SimpleNamespace(has_running_work=lambda: busy == "subagent")))
        screen.query_one("#checkpoint-apply", Button).focus()
        await pilot.press("enter")
        await ready(pilot)
        assert "idle" in str(screen.query_one("#checkpoint-status", Static).render()).lower()
        assert (tmp_path / "file.txt").read_text().startswith("FIRST")
        app.is_processing = False
        app.core_context = None
        if app._tool_prompts._answer is not None:
            app._tool_prompts._answer.cancel()
            app._tool_prompts._answer = None


async def test_resize_keeps_selected_file_hunk_and_apply_requires_explicit_activation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "n", "n")
        selected = screen._hunk_index
        await pilot.resize_terminal(80, 24)
        await ready(pilot)
        assert screen._hunk_index == selected
        await pilot.press("a")
        await ready(pilot)
        assert screen._plan is not None
        await pilot.press("escape")
        assert screen._plan is None
        assert (tmp_path / "file.txt").read_text() == "FIRST\nkeep\nLAST\n"


async def test_checks_recheck_declared_files_without_rewriting_historical_pass(tmp_path, monkeypatch):
    from henchman.advanced.plans import PlanExecutionService

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    plans = PlanExecutionService(tmp_path)
    plan = plans.create_plan(title="Check file", steps=["Inspect"], checks=[{"kind": "file_exists", "path": "file.txt"}])
    await plans.verify_plan(plan.plan_id)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("v")
        await ready(pilot)
        text = screen.query_one(TextArea).text
        assert "Current status: pass" in text and "Historical result: recorded pass" in text
        assert "not bound to the selected checkpoint" in text
        saved = (tmp_path / ".henchman/plans/verification.json").read_bytes()
        (tmp_path / "file.txt").write_text("later external change")
        await pilot.press("f5")
        await ready(pilot)
        assert "Current status: stale" in screen.query_one(TextArea).text
        assert "Historical result: recorded pass" in screen.query_one(TextArea).text
        assert (tmp_path / ".henchman/plans/verification.json").read_bytes() == saved


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_selected_file_checks_show_declared_scope_and_current_plan_status(tmp_path, monkeypatch, size):
    from henchman.advanced.plans import PlanExecutionService

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    (tmp_path / "other.txt").write_text("other")
    plans = PlanExecutionService(tmp_path)
    unrelated = plans.create_plan(title="Other file", steps=["Inspect"],
                                  checks=[{"kind": "file_exists", "path": "other.txt"}])
    declared = plans.create_plan(title="Command with input", steps=["Inspect"],
                                 checks=[{"kind": "command", "argv": ["true"], "inputs": ["./file.txt"]}])
    implicit = plans.create_plan(title="Test target is not an input declaration", steps=["Inspect"],
                                 checks=[{"kind": "pytest", "path": "file.txt"}])
    relevant = plans.create_plan(title="Selected file", steps=["Inspect"],
                                 checks=[{"kind": "file_contains", "path": "file.txt", "text": "FIRST"}])
    await plans.verify_plan(relevant.plan_id)
    saved = (tmp_path / ".henchman/plans/verification.json").read_bytes()
    app = InteractionApp(tmp_path)
    async with app.run_test(size=size) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("preserved draft")
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "v")
        await ready(pilot)
        text = screen.query_one(TextArea).text
        assert "Selected file: file.txt" in text
        assert "Current status applies to the entire plan" in text
        assert f"[Declares selected file] {relevant.plan_id}" in text
        assert f"[Declares selected file] {declared.plan_id}" in text
        assert f"[No exact declared input] {unrelated.plan_id}" in text
        assert f"[No exact declared input] {implicit.plan_id}" in text
        assert text.index(relevant.plan_id) < text.index(unrelated.plan_id)
        assert "Current status: pass" in text and "Current status: not_run" in text
        (tmp_path / "file.txt").write_text("changed after verification")
        await pilot.press("f5")
        await ready(pilot)
        assert "Current status: stale" in screen.query_one(TextArea).text
        assert (tmp_path / ".henchman/plans/verification.json").read_bytes() == saved
        await pilot.press("escape")
        assert screen._stage == "detail" and "File: file.txt" in screen.query_one(TextArea).text
        await pilot.press("escape", "escape", "escape")
        await ready(pilot)
        assert composer.text == "preserved draft"


async def test_selected_file_checks_do_not_infer_scope_from_redacted_plan(tmp_path, monkeypatch):
    from henchman.advanced.plans import PlanExecutionService
    from henchman.cli.evidence import runtime_evidence_redactor

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    secret = "later-registered-check-secret"
    plans = PlanExecutionService(tmp_path)
    plan = plans.create_plan(title="Sensitive check", steps=["Inspect"],
                             checks=[{"kind": "file_contains", "path": "file.txt", "text": secret}])
    runtime_evidence_redactor(app).register_secret(secret)
    async with app.run_test() as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "v")
        await ready(pilot)
        text = screen.query_one(TextArea).text
        assert f"[Inputs unavailable] {plan.plan_id}" in text
        assert secret not in text
        assert "Current status: unavailable" in text


@pytest.mark.parametrize("state", ["pass", "fail", "not_run", "unavailable", "incomplete"])
async def test_checks_show_shared_current_status_without_executing_or_saving(tmp_path, monkeypatch, state):
    from henchman.advanced import acceptance_checks
    from henchman.advanced.plans import PlanExecutionService
    from henchman.cli.evidence import runtime_evidence_redactor

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    policy = runtime_evidence_redactor(app)
    service = PlanExecutionService(tmp_path, settings=app.settings, redactor=policy)
    secret = "later-known-check-private"
    check = {"kind": "file_contains", "path": "file.txt", "text": "FIRST" if state != "fail" else "absent"}
    if state == "unavailable":
        check["text"] = secret
    if state == "incomplete":
        check = {"kind": "command", "argv": ["offline-unavailable"], "inputs": ["file.txt"]}
        async def unavailable(*_args):
            raise FileNotFoundError("Owned fixture executable unavailable")
        monkeypatch.setattr(acceptance_checks, "_command_result", unavailable)
    plan = service.create_plan(title="Inspect declared scope", steps=["Check"], checks=[check])
    if state not in {"not_run", "unavailable"}:
        await service.verify_plan(plan.plan_id)
    if state == "unavailable":
        policy.register_secret(secret)
    assert service.verification_status(plan.plan_id)["status"] == state
    index = tmp_path / ".henchman/plans/verification.json"
    before = index.read_bytes()
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("Read-only Checks must not execute verification")
    monkeypatch.setattr(PlanExecutionService, "verify_plan", forbidden)
    async with app.run_test() as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("keep unsent draft")
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("v")
        await ready(pilot)
        text = screen.query_one(TextArea).text
        assert f"Current status: {state}" in text
        assert "Historical result:" in text and "Task acceptance is not established" in text
        assert secret not in text and index.read_bytes() == before
        assert screen._plan is None and screen.query_one("#checkpoint-apply", Button).disabled
        await pilot.press("escape", "escape")
        await ready(pilot)
        assert composer.text == "keep unsent draft" and not app.submitted


async def test_checks_use_held_context_settings_and_detect_required_config_changes(tmp_path, monkeypatch):
    from henchman.advanced.plans import PlanExecutionService
    from henchman.config.schema import Settings

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    settings = Settings(verification={"checks": [{"kind": "file_exists", "path": "file.txt"}]})
    service = PlanExecutionService(tmp_path, settings=settings)
    plan = service.create_plan(steps=["Check"])
    await service.verify_plan(plan.plan_id)
    app = InteractionApp(tmp_path)
    async def close():
        pass
    async with app.run_test() as pilot:
        app.core_context = SimpleNamespace(
            settings=settings, project_root=tmp_path, session_manager=SimpleNamespace(current=object()),
            orchestrator=SimpleNamespace(aclose=close), background_tasks=[], mcp_manager=None,
        )
        try:
            await pilot.press("f8")
            screen = await ready(pilot)
            await pilot.press("v")
            await ready(pilot)
            assert "Current status: pass" in screen.query_one(TextArea).text
            settings.verification.checks = [{"kind": "file_contains", "path": "file.txt", "text": "FIRST"}]
            await pilot.press("f5")
            await ready(pilot)
            text = screen.query_one(TextArea).text
            assert "Current status: stale" in text and "configuration: changed" in text
            assert "Historical result: recorded pass" in text
        finally:
            app.core_context = None


@pytest.mark.parametrize("change", ["session", "settings", "project", "configuration", "close"])
async def test_checks_join_reads_and_refuse_stale_runtime_publication(tmp_path, monkeypatch, change):
    from henchman.advanced.plans import PlanExecutionService
    from henchman.config.schema import Settings

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    PlanExecutionService(tmp_path).create_plan(steps=["Observe"], checks=[{"kind": "file_exists", "path": "file.txt"}])
    entered, release, finished = Event(), Event(), Event()
    original = PlanExecutionService.verification_status
    def blocked(service, plan_id):
        entered.set()
        assert release.wait(10), "Test failed to release the owned read"
        try:
            return original(service, plan_id)
        finally:
            finished.set()
    monkeypatch.setattr(PlanExecutionService, "verification_status", blocked)
    app = InteractionApp(tmp_path)
    async def close():
        pass
    async with app.run_test() as pilot:
        context = SimpleNamespace(
            settings=app.settings, project_root=tmp_path, session_manager=SimpleNamespace(current=object()),
            orchestrator=SimpleNamespace(aclose=close), background_tasks=[], mcp_manager=None,
        )
        app.core_context = context
        closing = None
        try:
            await pilot.press("f8")
            screen = await ready(pilot)
            screen.action_checks()
            assert await asyncio.to_thread(entered.wait, 5)
            if change == "session":
                context.session_manager.current = object()
            elif change == "settings":
                context.settings = Settings()
            elif change == "project":
                context.project_root = tmp_path / "different-project"
            elif change == "configuration":
                context.settings.verification.checks = [{"kind": "file_exists", "path": "file.txt"}]
            else:
                async def pop():
                    await app.pop_screen()
                closing = asyncio.create_task(pop())
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert not finished.is_set() and not closing.done()
            release.set()
            if closing is not None:
                await asyncio.wait_for(closing, 10)
            else:
                await ready(pilot)
                assert "changed" in str(screen.query_one("#checkpoint-status", Static).render()).lower()
            assert finished.is_set() and screen._checks == ""
        finally:
            release.set()
            app.core_context = None


async def test_removed_screen_refuses_checks_before_delayed_unmount(tmp_path, monkeypatch):
    """Screen removal revokes publication before Textual delivers Unmount."""
    from henchman.advanced.plans import PlanExecutionService

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    PlanExecutionService(tmp_path).create_plan(
        steps=["Observe"], checks=[{"kind": "file_exists", "path": "file.txt"}],
    )
    entered, release, finished = Event(), Event(), Event()
    original = PlanExecutionService.verification_status

    def blocked(service, plan_id):
        entered.set()
        assert release.wait(10), "Test failed to release the owned read"
        try:
            return original(service, plan_id)
        finally:
            finished.set()

    monkeypatch.setattr(PlanExecutionService, "verification_status", blocked)
    app = InteractionApp(tmp_path)

    async def close():
        pass

    async with app.run_test() as pilot:
        app.core_context = SimpleNamespace(
            settings=app.settings, project_root=tmp_path,
            session_manager=SimpleNamespace(current=object()),
            orchestrator=SimpleNamespace(aclose=close), background_tasks=[], mcp_manager=None,
        )
        closing = None
        unmount_allowed, close_started = asyncio.Event(), asyncio.Event()
        try:
            await pilot.press("f8")
            screen = await ready(pilot)
            screen.action_checks()
            assert await asyncio.to_thread(entered.wait, 5)
            original_replace = app._replace_screen

            async def delayed_replace(previous):
                if previous is screen:
                    close_started.set()
                    await unmount_allowed.wait()
                await original_replace(previous)

            monkeypatch.setattr(app, "_replace_screen", delayed_replace)

            async def pop():
                await app.pop_screen()

            closing = asyncio.create_task(pop())
            await asyncio.wait_for(close_started.wait(), 5)
            assert app.screen is not screen and not screen._review_closing
            assert not finished.is_set() and not closing.done()
            release.set()
            await asyncio.wait_for(asyncio.shield(screen._action_task), 5)
            assert finished.is_set() and screen._checks == ""
        finally:
            release.set()
            unmount_allowed.set()
            if closing is not None:
                await asyncio.wait_for(closing, 5)
            app.core_context = None


async def test_checks_bound_additional_freshness_reads_and_make_omission_explicit(tmp_path, monkeypatch):
    from henchman.advanced.plans import PlanExecutionService
    from henchman.cli import textual_checkpoints

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    service = PlanExecutionService(tmp_path)
    plans = [service.create_plan(title=f"Plan {number}", steps=["Check"],
                                 checks=[{"kind": "file_exists", "path": "file.txt"}])
             for number in range(3)]
    observed = []
    original = PlanExecutionService.verification_status
    def inspect(service, plan_id):
        observed.append(plan_id)
        return original(service, plan_id)
    monkeypatch.setattr(PlanExecutionService, "verification_status", inspect)
    monkeypatch.setattr(textual_checkpoints, "_CHECK_PLAN_LIMIT", 2)
    app = InteractionApp(tmp_path)
    async with app.run_test() as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("v")
        await ready(pilot)
        assert observed == [plan.plan_id for plan in plans[-2:]]
        assert "1 earlier plan(s) omitted" in screen.query_one(TextArea).text
        assert "Plan 0" not in screen.query_one(TextArea).text


async def test_checks_refuse_initial_root_mismatch_before_plan_inspection(tmp_path, monkeypatch):
    from henchman.advanced.plans import PlanExecutionService

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    bound_root = tmp_path / "bound-project"
    bound_root.mkdir()
    reads = []
    monkeypatch.setattr(PlanExecutionService, "list_plans", lambda _service: reads.append(True) or [])
    app = InteractionApp(tmp_path)
    async def close():
        pass
    async with app.run_test() as pilot:
        app.core_context = SimpleNamespace(
            settings=app.settings, project_root=bound_root, session_manager=None,
            orchestrator=SimpleNamespace(aclose=close), background_tasks=[], mcp_manager=None,
        )
        try:
            await pilot.press("f8")
            screen = await ready(pilot)
            await pilot.press("v")
            await ready(pilot)
            assert reads == []
            assert screen._checks == ""
            assert "project" in str(screen.query_one("#checkpoint-status", Static).render()).lower()
        finally:
            app.core_context = None


async def test_revision_changed_before_preview_requires_refresh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    original = CheckpointService.preview
    switched = False

    def changed(service, identity, **kwargs):
        nonlocal switched
        if not switched:
            switched = True
            other = original(service, identity, decision="accept", paths=["file.txt"])
            service.apply(other.plan_id)
        return original(service, identity, **kwargs)

    monkeypatch.setattr(CheckpointService, "preview", changed)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "r")
        await ready(pilot)
        assert screen._plan is None
        assert "revision changed" in str(screen.query_one("#checkpoint-status", Static).render())
        assert (tmp_path / "file.txt").read_text().startswith("FIRST")


async def test_rotated_secret_is_not_shown_or_restored_from_preview(tmp_path, monkeypatch):
    from henchman.cli.evidence import runtime_evidence_redactor

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "r")
        await ready(pilot)
        runtime_evidence_redactor(app).register_secret("FIRST")
        screen.query_one("#checkpoint-apply", Button).focus()
        await pilot.press("enter")
        await ready(pilot)
        assert (tmp_path / "file.txt").read_text().startswith("FIRST")
        assert "FIRST" not in screen.query_one(TextArea).text
        assert screen._plan is None


async def test_unmount_joins_apply_worker_and_preserves_actual_result(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    entered, release, finished = Event(), Event(), Event()
    original = CheckpointService.apply

    def blocked(service, identity):
        entered.set()
        assert release.wait(10), "test did not release restore"
        try:
            return original(service, identity)
        finally:
            finished.set()

    monkeypatch.setattr(CheckpointService, "apply", blocked)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "r")
        await ready(pilot)
        screen.query_one("#checkpoint-apply", Button).focus()
        await pilot.press("enter")
        closing = None
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            async def close():
                await app.pop_screen()
            closing = asyncio.create_task(close())
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert not finished.is_set() and not closing.done()
        finally:
            release.set()
            if closing is not None:
                await asyncio.wait_for(closing, 10)
        assert finished.is_set()
        assert (tmp_path / "file.txt").read_text() == "first\nkeep\nlast\n"


async def test_review_shortcuts_do_not_submit_underlying_draft_or_follow_stream(tmp_path, monkeypatch):
    from henchman.cli.textual_widgets import ChatPane
    from tests.cli.ui_scenarios import populate_history

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("private unsent draft")
        chat = app.query_one(ChatPane)
        populate_history(chat)
        await ready(pilot)
        chat.scroll_to(y=20, animate=False, force=True, immediate=True)
        await ready(pilot)
        before = chat.scroll_y
        composer.focus()
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "ctrl+enter")
        await ready(pilot)
        chat.append_agent_chunk("worker", "Later activity\n")
        await ready(pilot)
        assert app.submitted == [] and composer.text == "private unsent draft"
        assert app.screen is screen and app.focused is screen.query_one(TextArea)
        await pilot.press("escape", "escape", "escape")
        await ready(pilot)
        assert chat.scroll_y == before and not chat.follow_live
        assert app.focused is composer


async def test_created_file_contents_are_inspectable_without_supported_text_hunks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = CheckpointService(tmp_path)
    record = service.begin(["created.txt"], actor="engineer")
    (tmp_path / "created.txt").write_text("new file evidence\n")
    service.complete(record.checkpoint_id)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        assert "new file evidence" in screen.query_one(TextArea).text
        assert "missing" in screen.query_one(TextArea).text
        assert not screen.query_one("#checkpoint-reject", Button).disabled


async def test_nonrestorable_and_interrupted_restore_are_explicit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    service = CheckpointService(tmp_path)
    (tmp_path / "binary").write_bytes(b"a\x00b")
    record = service.begin(["binary"], actor="engineer")
    service.complete(record.checkpoint_id)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "r")
        await ready(pilot)
        assert "non-restorable" in screen.query_one(TextArea).text
        assert screen._plan is None and screen.query_one("#checkpoint-reject", Button).disabled
        _, identity = capture(tmp_path)
        plan = service.preview(identity, decision="reject")
        service._fault = lambda stage: (_ for _ in ()).throw(RuntimeError("interrupted")) if stage == "prepared" else None
        with pytest.raises(RuntimeError):
            service.apply(plan.plan_id)
        await pilot.press("f5")
        await ready(pilot)
        assert plan.plan_id in screen._status and "/checkpoint recover" in screen._status


async def test_refresh_read_errors_are_visible_and_leave_apply_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        def failed(_service):
            raise OSError("checkpoint index unavailable")
        monkeypatch.setattr(CheckpointService, "list_checkpoints", failed)
        await pilot.press("f5")
        await ready(pilot)
        assert "checkpoint index unavailable" in screen._status
        assert screen.query_one("#checkpoint-apply", Button).disabled


async def test_apply_rechecks_idle_after_shared_mutation_lock_wait(tmp_path, monkeypatch):
    from henchman.tools.registry import ToolRegistry

    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    registry = ToolRegistry()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("f8")
        screen = await ready(pilot)
        await pilot.press("enter")
        await ready(pilot)
        await pilot.press("enter", "r")
        await ready(pilot)
        app.core_context = SimpleNamespace(tool_registry=registry)
        try:
            async with registry._effective_formatter._lock:
                screen.query_one("#checkpoint-apply", Button).focus()
                await pilot.press("enter")
                assert screen._busy
                assert (tmp_path / "file.txt").read_text().startswith("FIRST")
                app.is_processing = True
            await ready(pilot)
            assert "idle" in screen._status
            assert (tmp_path / "file.txt").read_text().startswith("FIRST")
        finally:
            app.is_processing = False
            app.core_context = None


async def test_workspace_entry_and_existing_composer_selection_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    capture(tmp_path)
    app = InteractionApp(tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("first\nsecond")
        composer.focus()
        await pilot.press("f6")
        assert app.screen.id == "_default" and composer.selected_text == "first"
        button = app.query_one("#workspace-review", Button)
        button.press()
        screen = await ready(pilot)
        assert isinstance(screen, CheckpointReviewScreen)
        await pilot.press("escape")
        await ready(pilot)
        assert composer.text == "first\nsecond"


@pytest.fixture
def copy_review(tmp_path, monkeypatch):
    from henchman.core.session import Session

    monkeypatch.chdir(tmp_path)
    secret = "checkpoint-copy-later-private"
    path = tmp_path / "copy.txt"
    path.write_text("before")
    service = CheckpointService(tmp_path)
    record = service.begin([path.name], actor="fixture")
    path.write_text("after " + secret)
    service.complete(record.checkpoint_id)
    app = InteractionApp(tmp_path)
    session = Session("copy-session", "project", "now", "now")
    actor = SimpleNamespace(provider=SimpleNamespace(api_key=""))
    context = SimpleNamespace(
        settings=app.settings, project_root=tmp_path, agent=actor,
        session_manager=SimpleNamespace(current=session), orchestrator=None,
        background_tasks=[], mcp_manager=None,
    )
    return SimpleNamespace(app=app, context=context, actor=actor, session=session, secret=secret, path=path)


async def open_copy_review(case, pilot):
    case.app.core_context = case.context
    composer = case.app.query_one(HenchmanTextArea)
    composer.load_text("keep unsent draft")
    composer.focus()
    await pilot.press("f8")
    screen = await ready(pilot)
    await pilot.press("enter")
    await ready(pilot)
    await pilot.press("enter")
    await ready(pilot)
    return screen, screen.query_one("#checkpoint-content", TextArea), composer


@pytest.mark.parametrize("rotation", ["registered", "session", "actor"])
async def test_checkpoint_copy_reprojects_before_selection_and_retains_known_values(copy_review, monkeypatch, rotation):
    from henchman.cli.evidence import runtime_evidence_redactor
    from henchman.utils.evidence_redaction import EvidenceRedactor

    case = copy_review
    copied = []
    monkeypatch.setattr(case.app, "copy_to_clipboard", copied.append)
    async with case.app.run_test() as pilot:
        try:
            screen, area, composer = await open_copy_review(case, pilot)
            review = screen._review
            assert case.secret in area.text
            saved = {path: path.read_bytes() for path in (case.path.parent / ".henchman").rglob("*") if path.is_file()}
            def forbidden(*_args, **_kwargs):
                raise AssertionError("Copy must not read or mutate checkpoint authority")
            monkeypatch.setattr(CheckpointService, "review", forbidden)
            monkeypatch.setattr(CheckpointService, "apply", forbidden)
            area.select_all()
            if rotation == "registered":
                runtime_evidence_redactor(case.app).register_secret(case.secret)
            elif rotation == "session":
                case.session.evidence_redactor.register_secret(case.secret)
            else:
                case.actor.provider.api_key = case.secret
            # No render/timer opportunity between credential learning and copy.
            area.action_copy()
            assert copied == []
            assert case.secret not in area.text and "[REDACTED]" in area.text
            assert "select text again" in str(screen.query_one("#checkpoint-status", Static).render()).lower()
            area.select_all()
            await pilot.press("ctrl+c")
            assert copied == [area.text]
            assert "Before" in copied[-1] and "After" in copied[-1]
            assert screen._review is review and case.path.read_text() == "after " + case.secret
            assert all(path.read_bytes() == data for path, data in saved.items())
            assert case.app.screen is screen and case.app.is_running and composer.text == "keep unsent draft"
            case.actor.provider.api_key = ""
            case.session.evidence_redactor = EvidenceRedactor()
            case.app._evidence_redactor = EvidenceRedactor()
            screen._render_view()
            area.select_all()
            area.action_copy()
            assert case.secret not in copied[-1] and "[REDACTED]" in copied[-1]
            await pilot.press("escape", "escape", "escape")
            await ready(pilot)
            assert case.app.focused is composer and composer.text == "keep unsent draft"
        finally:
            case.app.core_context = None


@pytest.mark.parametrize("change", ["session", "actor", "project", "initial_project", "cwd", "root_replaced", "closed", "busy"])
async def test_checkpoint_copy_refuses_stale_selected_runtime_or_project(copy_review, monkeypatch, change):
    case = copy_review
    copied = []
    monkeypatch.setattr(case.app, "copy_to_clipboard", copied.append)
    async with case.app.run_test() as pilot:
        try:
            if change == "initial_project":
                other = case.path.parent / "different"
                other.mkdir()
                case.context.project_root = other
            screen, area, composer = await open_copy_review(case, pilot)
            area.select_all()
            root = case.path.parent
            if change == "session":
                case.context.session_manager.current = object()
            elif change == "actor":
                case.context.agent = SimpleNamespace(provider=SimpleNamespace(api_key=""))
            elif change == "project":
                case.context.project_root = root / "different"
            elif change == "cwd":
                other = root / "different"
                other.mkdir()
                monkeypatch.chdir(other)
            elif change == "root_replaced":
                original_root = root.resolve()
                original_identity = (root.stat().st_dev, root.stat().st_ino)
                monkeypatch.chdir(root.parent)
                root.rename(root.with_name(root.name + "-old"))
                root.mkdir()
                monkeypatch.chdir(root)
                assert root.resolve() == original_root
                assert (root.stat().st_dev, root.stat().st_ino) != original_identity
            elif change == "closed":
                screen._review_closing = True
            elif change == "busy":
                screen._busy = True
            area.action_copy()
            assert copied == []
            assert "reopen" in str(screen.query_one("#checkpoint-status", Static).render()).lower()
            assert composer.text == "keep unsent draft" and case.app.is_running
        finally:
            case.app.core_context = None


async def test_checkpoint_copy_reprojects_full_capture_before_display_clipping(copy_review, monkeypatch):
    from henchman.cli import textual_checkpoints

    case = copy_review
    copied = []
    monkeypatch.setattr(case.app, "copy_to_clipboard", copied.append)
    async with case.app.run_test() as pilot:
        try:
            screen, area, _composer = await open_copy_review(case, pilot)
            prefix = case.secret[:len(case.secret) // 2]
            monkeypatch.setattr(textual_checkpoints, "_TEXT_LIMIT", area.text.index(case.secret) + len(prefix))
            screen._render_view()
            assert prefix in area.text and case.secret not in area.text
            area.select_all()
            case.session.evidence_redactor.register_secret(case.secret)
            area.action_copy()
            assert copied == [] and prefix not in area.text
            area.select_all()
            await pilot.press("ctrl+c")
            assert copied == [area.text] and prefix not in copied[-1]
            assert case.secret in screen._detail() and case.path.read_text() == "after " + case.secret
        finally:
            case.app.core_context = None


async def test_checkpoint_copy_preserves_native_selection_and_projects_clipboard_failure(copy_review, monkeypatch):
    from textual.document._document import Selection

    from henchman.cli.evidence import runtime_evidence_redactor

    case = copy_review
    copied = []
    monkeypatch.setattr(case.app, "copy_to_clipboard", copied.append)
    async with case.app.run_test() as pilot:
        try:
            screen, area, _composer = await open_copy_review(case, pilot)
            area.selection = Selection((0, 0), (0, 4))
            await pilot.press("ctrl+c")
            assert copied == ["File"] and area.selected_text == "File"
            assert "requested" in str(screen.query_one("#checkpoint-status", Static).render()).lower()
            secret = "clipboard-failure-private"
            runtime_evidence_redactor(case.app).register_secret(secret)
            def fail(_text):
                raise OSError("clipboard unavailable " + secret)
            monkeypatch.setattr(case.app, "copy_to_clipboard", fail)
            area.action_copy()
            status = str(screen.query_one("#checkpoint-status", Static).render())
            assert "unavailable" in status and secret not in status
            assert area.selected_text == "File" and case.app.screen is screen
        finally:
            case.app.core_context = None


async def test_checkpoint_copy_reprojects_retained_check_history_without_reinspection(copy_review, monkeypatch):
    from henchman.advanced.plans import PlanExecutionService

    case = copy_review
    service = PlanExecutionService(case.path.parent, settings=case.app.settings)
    plan = service.create_plan(title=case.secret, steps=["Check"], checks=[{"kind": "file_exists", "path": case.path.name}])
    await service.verify_plan(plan.plan_id)
    saved = (case.path.parent / ".henchman/plans/verification.json").read_bytes()
    copied = []
    monkeypatch.setattr(case.app, "copy_to_clipboard", copied.append)
    async with case.app.run_test() as pilot:
        try:
            screen, area, _composer = await open_copy_review(case, pilot)
            await pilot.press("v")
            await ready(pilot)
            assert "Historical result: recorded pass" in area.text and case.secret in area.text
            def forbidden(*_args, **_kwargs):
                raise AssertionError("Copy must not inspect or execute checks")
            monkeypatch.setattr(PlanExecutionService, "verification_status", forbidden)
            monkeypatch.setattr(PlanExecutionService, "verify_plan", forbidden)
            case.path.write_text("changed after observation")
            area.select_all()
            case.session.evidence_redactor.register_secret(case.secret)
            area.action_copy()
            assert copied == []
            assert case.secret not in area.text
            area.select_all()
            await pilot.press("ctrl+c")
            assert copied == [area.text] and "Historical result: recorded pass" in copied[-1]
            assert (case.path.parent / ".henchman/plans/verification.json").read_bytes() == saved
        finally:
            case.app.core_context = None
