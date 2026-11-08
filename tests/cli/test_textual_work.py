"""Live owner-backed work inspection preserves execution and frontend state."""
from __future__ import annotations

import asyncio
import sys
from contextlib import suppress
from threading import Event
from types import SimpleNamespace

import pytest
from textual.widgets import Button, OptionList, TextArea

from henchman.advanced.tasks import TaskService
from henchman.agents.delegation_admission import DelegationAdmission
from henchman.agents.subagents import BackgroundSubagentManager
from henchman.cli.session_manager import ReplSessionManager
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent, EventType
from henchman.core.session import SessionManager
from henchman.tools.builtins.tier6_tools import TaskGetTool
from henchman.tools.registry import ToolRegistry
from tests.cli.ui_scenarios import InteractionApp, settle_layout


@pytest.fixture
async def work(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = InteractionApp(tmp_path)
    app.config.agent_role = None
    manager = ReplSessionManager(SessionManager(data_dir=tmp_path / "sessions"), settings=app.settings, auto_save=False)
    actor = Agent(app.provider)
    manager.set_session(manager.create_session(manager.compute_project_hash(tmp_path)), history_agent=actor)
    registry = ToolRegistry()
    tool = TaskGetTool()
    tool.bind_runtime(tool_registry=registry, project_root=tmp_path)
    registry.register(tool)
    service = tool._task_service
    release = asyncio.Event()
    async def runner(_agent, prompt):
        if prompt == "fail":
            raise ValueError("child failed evidence")
        if prompt == "block":
            await agents.request_input("Which target?")
        else:
            await release.wait()
        yield AgentEvent(EventType.CONTENT, "retained child output")
    def factory(_role, _prompt, _tools, _identity):
        return Agent(SimpleNamespace(name="actual-adapter", _accounting_provider_name="actual-alias", model="actual-model", api_key="actor-key"))
    agents = BackgroundSubagentManager(factory, runner, available_tools=lambda _: [],
                                       admission=DelegationAdmission(allowed=True))
    records = [agents.spawn(prompt, role=prompt, system_prompt="OPAQUE-SYSTEM-DO-NOT-DISPLAY", tools=[])
               for prompt in ("run", "fail", "block")]
    async def close():
        pass
    context = SimpleNamespace(session_manager=manager, project_root=tmp_path, agent=actor, tool_registry=registry,
                              orchestrator=SimpleNamespace(tech_lead=actor, subagents=agents, pool=SimpleNamespace(_agents={}), aclose=close),
                              background_tasks=[], mcp_manager=None)
    value = SimpleNamespace(app=app, manager=manager, actor=actor, registry=registry, service=service,
                            agents=agents, records=records, root=tmp_path, context=context, tasks=[])
    await asyncio.sleep(0)
    yield value
    release.set()
    await agents.close()
    for task_id in value.tasks:
        with suppress(KeyError, RuntimeError):
            await service.stop_task(task_id)


async def opened(work, pilot):
    from henchman.cli.textual_work import open_work_inspector
    work.app.core_context = work.context
    open_work_inspector(work.app)
    await settle_layout(pilot)
    screen = work.app.screen
    if screen._action_task is not None:
        await screen._action_task
    await pilot.pause()
    return screen


@pytest.mark.parametrize("size", [(80, 24), (120, 40)])
async def test_actual_agents_keyboard_inspection_back_and_draft_preserved(work, size):
    from henchman.cli.textual_widgets import HenchmanTextArea
    app = work.app
    async with app.run_test(size=size) as pilot:
        composer = app.query_one(HenchmanTextArea)
        composer.load_text("untouched draft")
        composer.focus()
        try:
            screen = await opened(work, pilot)
            assert {row.state for row in screen._rows if row.kind == "agent"} == {"running", "errored", "waiting_for_input"}
            options = screen.query_one(OptionList)
            options.focus()
            await pilot.press("enter")
            await pilot.pause()
            text = screen.query_one(TextArea).text
            assert work.records[0].conversation_id in text
            assert "actual-alias" in text and "actual-model" in text
            assert "OPAQUE-SYSTEM" not in text
            assert "process-only" in text and "not task verification" in text
            assert screen.query_one(TextArea).display
            assert options.display is (size[0] >= 100)
            await pilot.press("escape")
            assert app.screen is screen and options.has_focus
            await pilot.press("escape")
            await pilot.pause()
            assert len(app.screen_stack) == 1 and composer.has_focus
            assert composer.text == "untouched draft" and not app.submitted
            assert work.agents.get(work.records[0].conversation_id).status == "running"
            assert work.agents.get(work.records[2].conversation_id).status == "waiting_for_input"
        finally:
            app.core_context = None


async def test_real_failed_task_evidence_and_current_process_remain_untouched(work):
    failed = await work.service.start_task(argv=[sys.executable, "-c", "print('task failure output'); raise SystemExit(3)"], title="failed fixture")
    await work.service.wait_for_task(failed.task_id, timeout=5)
    running = await work.service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"], title="running fixture")
    work.tasks.append(running.task_id)
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            rows = {row.identity: row for row in screen._rows if row.kind == "task"}
            assert rows[failed.task_id].state == "failed" and rows[running.task_id].state == "running"
            before = work.service._index_path.read_bytes()
            screen.query_one(OptionList).highlighted = screen._rows.index(rows[failed.task_id])
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            assert "task failure output" in screen.query_one(TextArea).text
            assert "Return code: 3" in screen.query_one(TextArea).text
            assert work.service._index_path.read_bytes() == before
            assert work.service._runtime.processes[running.task_id].returncode is None
        finally:
            work.app.core_context = None


async def test_recovered_running_task_is_unknown_and_never_adopts_pid(work):
    from tests.advanced.test_task_store import record
    store = work.service._store
    raw = store.create(record())
    raw = store.replace(dict(raw, status="started", started_at=raw["created_at"]), expected_revision=raw["revision"], owner_id="owner-a")
    store.replace(dict(raw, status="running", pid=987654), expected_revision=raw["revision"], owner_id="owner-a")
    before = store.path.read_bytes()
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            row = next(row for row in screen._rows if row.identity == raw["task_id"])
            assert row.state == "outcome_unknown"
            screen.query_one(OptionList).highlighted = screen._rows.index(row)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            assert "no PID is adopted" in screen.query_one(TextArea).text
            assert screen.query_one("#work-stop", Button).disabled
            assert store.path.read_bytes() == before
            assert raw["task_id"] not in work.service._runtime.processes
        finally:
            work.app.core_context = None


@pytest.mark.parametrize("change", ["session", "cwd", "owner", "selection"])
async def test_late_read_never_publishes_for_replaced_identity(work, monkeypatch, change):
    import henchman.cli.textual_work as module
    finished = await work.service.start_task(argv=[sys.executable, "-c", "print('old private project output')"])
    await work.service.wait_for_task(finished.task_id, timeout=5)
    entered, release = Event(), Event()
    original = module._task_details
    def blocked(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.query_one(OptionList).highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == finished.task_id)
            await pilot.pause()
            monkeypatch.setattr(module, "_task_details", blocked)
            screen.action_inspect()
            assert await asyncio.to_thread(entered.wait, 2)
            if change == "session":
                work.manager.set_session(work.manager.create_session(work.manager.current.project_hash), history_agent=work.actor)
            elif change == "cwd":
                other = work.root / "elsewhere"
                other.mkdir()
                monkeypatch.chdir(other)
            elif change == "owner":
                work.registry.unregister("task_get")
            else:
                screen.query_one(OptionList).highlighted = 0
                await pilot.pause()
            release.set()
            await screen._action_task
            assert "old private project output" not in screen.query_one(TextArea).text
            assert "changed" in screen._status.lower()
        finally:
            release.set()
            work.app.core_context = None


async def test_back_joins_blocked_read_and_preserves_first_caller_cancellation(work, monkeypatch):
    entered, release = Event(), Event()
    original = work.service.list_tasks
    def blocked():
        entered.set()
        assert release.wait(5)
        return original()
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            monkeypatch.setattr(work.service, "list_tasks", blocked)
            screen.action_refresh()
            assert await asyncio.to_thread(entered.wait, 2)
            closing = asyncio.create_task(screen.action_back())
            await asyncio.sleep(0)
            closing.cancel("first inspector close")
            await asyncio.sleep(0)
            closing.cancel("later inspector close")
            assert not closing.done()
            release.set()
            with pytest.raises(asyncio.CancelledError) as caught:
                await closing
            assert caught.value.args == ("first inspector close",)
            assert screen._action_task.done()
        finally:
            release.set()
            work.app.core_context = None


async def test_rotated_actor_policy_refreshes_copy_and_omits_clipped_observations(work, monkeypatch):
    from dataclasses import replace
    copied = []
    conversation = work.agents._conversations[work.records[1].conversation_id]
    conversation.record = replace(conversation.record, output="old-key / new-key", error="safe failure")
    conversation.agent.provider.api_key = "old-key"
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.query_one(OptionList).highlighted = 1
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            monkeypatch.setattr(work.app, "copy_to_clipboard", copied.append)
            conversation.agent.provider.api_key = "new-key"
            screen.action_copy()
            assert "old-key" not in copied[-1] and "new-key" not in copied[-1]
            assert "safe failure" in copied[-1] and "unconfirmed" in screen._status
            conversation.record = replace(conversation.record, output="late-clipped-private-prefix", output_truncated=True)
            screen.action_inspect()
            await screen._action_task
            screen.action_copy()
            assert "late-clipped" not in copied[-1] and "clipped" in copied[-1]
            assert conversation.record.output == "late-clipped-private-prefix"
        finally:
            work.app.core_context = None


async def test_unbound_task_owner_never_initializes_storage_and_decisions_keep_priority(work, monkeypatch):
    from henchman.cli.textual_work import open_work_inspector
    work.registry.unregister("task_get")
    monkeypatch.setattr(TaskService, "__init__", lambda *_a, **_k: pytest.fail("inspection created a task owner"))
    async with work.app.run_test() as pilot:
        try:
            work.app.core_context = work.context
            answer = asyncio.get_running_loop().create_future()
            work.app._tool_prompts._answer = answer
            open_work_inspector(work.app)
            await pilot.pause()
            assert len(work.app.screen_stack) == 1 and not answer.done()
            work.app._tool_prompts._answer = None
            screen = await opened(work, pilot)
            assert "task service unavailable" in screen._status
        finally:
            work.app._tool_prompts._answer = None
            work.app.core_context = None


async def test_actor_specific_credential_is_projected_before_list_label(work):
    from dataclasses import replace
    item = work.agents._conversations[work.records[0].conversation_id]
    item.agent.provider.api_key = "exclusive-agent-label-canary"
    item.record = replace(item.record, role="exclusive-agent-label-canary")
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            assert "exclusive-agent-label-canary" not in "\n".join(screen._labels)
            assert "REDACTED" in "\n".join(screen._labels)
            assert item.record.role == "exclusive-agent-label-canary"
        finally:
            work.app.core_context = None


async def test_workspace_button_copies_selected_safe_evidence_without_quitting(work, monkeypatch):
    from textual.document._document import Selection
    from textual.widgets import TabbedContent

    from henchman.cli.textual_widgets import HenchmanTextArea
    copied = []
    async with work.app.run_test(size=(80, 24)) as pilot:
        work.app.core_context = work.context
        try:
            work.app.query_one(HenchmanTextArea).load_text("kept unsent")
            work.app.query_one(TabbedContent).active = "tab-workspace"
            await settle_layout(pilot)
            assert await pilot.click("#workspace-inspect")
            await settle_layout(pilot)
            screen = work.app.screen
            await screen._action_task
            await pilot.press("enter")
            await pilot.pause()
            area = screen.query_one(TextArea)
            area.selection = Selection((0, 0), (0, len(area.document.get_line(0))))
            monkeypatch.setattr(work.app, "copy_to_clipboard", copied.append)
            await pilot.press("ctrl+c")
            assert copied and work.records[0].conversation_id in copied[-1]
            assert work.app.is_running and work.app.query_one(HenchmanTextArea).text == "kept unsent"
        finally:
            work.app.core_context = None


async def test_oversized_and_sensitive_log_read_is_bounded_and_never_rewritten(work):
    record = await work.service.start_task(argv=[sys.executable, "-c", "print('ordinary')"])
    await work.service.wait_for_task(record.task_id, timeout=5)
    path = work.service.get_task(record.task_id).output_path
    raw = b"not-yet-known-private-prefix" + b"x" * 40000
    path.write_bytes(raw)
    before = work.service._index_path.read_bytes()
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.query_one(OptionList).highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == record.task_id)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            text = screen.query_one(TextArea).text
            assert record.task_id in text and "exceeds 32 KiB" in text
            assert "private-prefix" not in text and len(text.encode()) <= 65536
            assert path.read_bytes() == raw and work.service._index_path.read_bytes() == before
        finally:
            work.app.core_context = None


async def test_symlink_log_failure_cannot_display_previous_selection(work):
    record = await work.service.start_task(argv=[sys.executable, "-c", "print('ordinary')"])
    await work.service.wait_for_task(record.task_id, timeout=5)
    path = work.service.get_task(record.task_id).output_path
    private = work.root / "outside-task-log"
    private.write_text("must-not-follow")
    path.unlink()
    try:
        path.symlink_to(private)
    except OSError:
        pytest.skip("symlink unavailable")
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.query_one(OptionList).highlighted = 1
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            assert "child failed evidence" in screen.query_one(TextArea).text
            screen.query_one(OptionList).highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == record.task_id)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            text = screen.query_one(TextArea).text
            assert "must-not-follow" not in text and "child failed evidence" not in text
            assert "Error" in screen._status or "error" in screen._status
        finally:
            work.app.core_context = None


@pytest.mark.parametrize("selected", [False, True])
@pytest.mark.parametrize("change", ["session", "cwd", "owner"])
async def test_stale_full_and_selected_copy_cannot_publish_old_work(work, monkeypatch, selected, change):
    from textual.document._document import Selection
    copied = []
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.action_inspect()
            await screen._action_task
            area = screen.query_one(TextArea)
            area.selection = Selection((0, 0), (0, len(area.document.get_line(0))))
            monkeypatch.setattr(work.app, "copy_to_clipboard", copied.append)
            if change == "session":
                work.manager.set_session(work.manager.create_session(work.manager.current.project_hash), history_agent=work.actor)
            elif change == "cwd":
                other = work.root / "changed"
                other.mkdir()
                monkeypatch.chdir(other)
            else:
                work.registry.unregister("task_get")
            if selected:
                area.action_copy()
            else:
                screen.action_copy()
            assert not copied
            assert "changed" in screen._status.lower()
        finally:
            work.app.core_context = None


async def test_live_partial_output_reprojects_newly_known_credential_boundary(work, monkeypatch):
    from dataclasses import replace
    copied = []
    conversation = work.agents._conversations[work.records[0].conversation_id]
    prefix = "private-live-output-prefix-"
    conversation.record = replace(conversation.record, output=prefix)
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.action_inspect()
            await screen._action_task
            assert prefix in screen.query_one(TextArea).text
            conversation.agent.provider.api_key = prefix + "unreceived-suffix"
            monkeypatch.setattr(work.app, "copy_to_clipboard", copied.append)
            screen.action_copy()
            assert copied and prefix not in copied[-1]
            assert conversation.record.output == prefix
        finally:
            work.app.core_context = None


async def test_catalog_and_combined_details_have_explicit_whole_item_bounds(work, monkeypatch):
    from dataclasses import replace

    import henchman.cli.textual_work as module
    monkeypatch.setattr(module, "_ROWS", 2)
    conversation = work.agents._conversations[work.records[1].conversation_id]
    conversation.record = replace(conversation.record, output="o" * 32760, error="e" * 32760)
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            assert len(screen._rows) == 2 and "omitted" in screen._status
            screen.query_one(OptionList).highlighted = 1
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            text = screen.query_one(TextArea).text
            # Projection can expand a trailing credential prefix and hit the
            # per-item bound before the aggregate bound; both must be explicit.
            assert len(text.encode()) <= 65536 and "omitted" in text.lower()
            assert conversation.record.conversation_id in text
            assert "No run ID is retained" in text
            assert len(conversation.record.output) == len(conversation.record.error) == 32760
        finally:
            work.app.core_context = None


async def test_completed_cancelled_child_is_never_presented_as_success(work):
    cancelled = await work.agents.cancel(work.records[0].conversation_id)
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.action_inspect()
            await screen._action_task
            text = screen.query_one(TextArea).text
            assert cancelled.status == "done" and cancelled.cancelled
            assert "cancelled, not successful completion" in text
            assert "No run ID is retained" in text
        finally:
            work.app.core_context = None


@pytest.mark.parametrize("ending", ["stopped", "failed", "completed", "truncated"])
async def test_task_output_completion_provenance_survives_credential_rotation(work, monkeypatch, ending):
    prefix = "terminal-task-private-prefix-"
    suffix = "import time; time.sleep(30)" if ending == "stopped" else "raise SystemExit(3)" if ending == "failed" else "raise SystemExit(0)"
    record = await work.service.start_task(argv=[sys.executable, "-c", f"import sys; sys.stdout.write({prefix!r}); sys.stdout.flush(); {suffix}"])
    work.tasks.append(record.task_id)
    path = work.service.get_task(record.task_id).output_path
    if ending == "stopped":
        async with asyncio.timeout(5):
            while prefix not in path.read_text():
                await asyncio.sleep(0.01)
        await work.service.stop_task(record.task_id)
    else:
        await work.service.wait_for_task(record.task_id, timeout=5)
    if ending == "truncated":
        work.service.update_task(record.task_id, metadata={"output_truncated": "true"})
        path.write_text(prefix + "[output truncated]")
    before = path.read_bytes()
    async with work.app.run_test() as pilot:
        try:
            screen = await opened(work, pilot)
            screen.query_one(OptionList).highlighted = next(i for i, row in enumerate(screen._rows) if row.identity == record.task_id)
            await pilot.pause()
            screen.action_inspect()
            await screen._action_task
            work.service._runtime.policy.register_secret(prefix + "unreceived-suffix")
            copied = []
            monkeypatch.setattr(work.app, "copy_to_clipboard", copied.append)
            screen.action_copy()
            assert copied
            if ending == "completed":
                assert prefix in copied[-1]  # Successful EOF is not an interrupted secret.
            else:
                assert prefix not in copied[-1]
                assert "REDACTED" in copied[-1] or "omitted" in copied[-1].lower()
            assert path.read_bytes() == before
        finally:
            work.app.core_context = None
