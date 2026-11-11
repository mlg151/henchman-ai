"""Classic and Textual /work share existing owners and bounded literal evidence."""
from __future__ import annotations

import asyncio
import sys
from dataclasses import replace
from io import StringIO
from threading import Event
from types import SimpleNamespace

import pytest
from rich.console import Console

from henchman.cli.command_processor import CommandProcessor
from henchman.cli.commands import CommandContext
from henchman.cli.commands.builtins import get_builtin_commands
from tests.cli.test_textual_work import work as work_fixture

work = work_fixture


def frontend(work, *, textual=False):
    if textual:
        work.app.core_context = work.context
        return work.app
    return SimpleNamespace(
        project_root=work.root, session_manager=work.manager,
        tool_registry=work.registry, orchestrator=work.context.orchestrator,
        agent=work.actor, provider=work.app.provider, settings=work.app.settings,
        config=SimpleNamespace(agent_role=None),
    )


async def render(work, args, *, runtime=None, console=None, session=None):
    commands = [item for item in get_builtin_commands() if item.name == "work"]
    assert len(commands) == 1, "The read-only /work command must be registered exactly once"
    output = StringIO()
    ctx = CommandContext(
        console=console or Console(file=output, width=200, color_system=None),
        args=args, repl=runtime or frontend(work),
        session=work.manager.current if session is None else session,
    )
    await commands[0].execute(ctx)
    return output.getvalue()


@pytest.mark.parametrize("textual", [False, True])
async def test_registered_command_lists_actual_states_and_inspects_exact_agent(work, textual):
    runtime = frontend(work, textual=textual)
    before = tuple(work.actor.messages)
    text = await render(work, ["list"], runtime=runtime)
    assert all(item.conversation_id in text for item in work.records)
    assert "running" in text and "errored" in text and "waiting_for_input" in text
    for record in work.records:
        text = await render(work, ["inspect", "agent", record.conversation_id], runtime=runtime)
        assert "actual-alias" in text and "actual-model" in text and "process-only" in text
        assert record.conversation_id in text and "not task verification" in text
        assert "OPAQUE-SYSTEM" not in text
    assert tuple(work.actor.messages) == before
    assert work.agents.get(work.records[0].conversation_id).status == "running"


async def test_classic_processor_routes_work_without_queue_or_history_mutation(work):
    runtime = frontend(work)
    output = StringIO()
    console = Console(file=output, width=200)
    handler = SimpleNamespace(renderer=SimpleNamespace(console=console),
                              error=lambda text: pytest.fail(text), muted=lambda *_: None)
    processor = CommandProcessor(handler, SimpleNamespace(registry=work.registry), work.manager, work.app.provider)
    before = work.manager.current.to_dict()
    assert await processor.handle_command("/work list", work.actor, runtime)
    assert work.records[0].conversation_id in output.getvalue()
    assert work.manager.current.to_dict() == before
    from henchman.cli.workflow import command_route, command_starts_work
    assert command_route("/work inspect agent exact-id") == "control"
    assert not command_starts_work("/work inspect agent exact-id")


async def test_known_actor_credentials_and_literal_labels_are_projected_before_output(work):
    child = work.agents._conversations[work.records[0].conversation_id]
    child.agent.provider.api_key = "work-copy-private"
    child.record = replace(child.record, role="[bold]work-copy-private[/bold]", output="work-copy-private")
    runtime = frontend(work)
    text = await render(work, [], runtime=runtime)
    assert "work-copy-private" not in text and "[bold][REDACTED][/bold]" in text
    text = await render(work, ["inspect", "agent", child.record.conversation_id], runtime=runtime)
    assert "work-copy-private" not in text and "[REDACTED]" in text
    child.agent.provider.api_key = ""
    text = await render(work, ["inspect", "agent", child.record.conversation_id], runtime=runtime)
    assert "work-copy-private" not in text and "[REDACTED]" in text
    assert child.record.output == "work-copy-private"


async def test_failed_task_inspection_preserves_index_and_interrupted_output(work):
    prefix = "work-terminal-private-prefix-"
    record = await work.service.start_task(argv=[sys.executable, "-c", f"print({prefix!r}, end=''); raise SystemExit(3)"])
    await work.service.wait_for_task(record.task_id, timeout=5)
    before = work.service._index_path.read_bytes()
    path = work.service.get_task(record.task_id).output_path
    log = path.read_bytes()
    work.service._runtime.policy.register_secret(prefix + "unreceived-suffix")
    text = await render(work, ["inspect", "task", record.task_id])
    assert "failed" in text and "Return code: 3" in text
    assert prefix not in text and "[REDACTED]" in text
    assert "not execution authority or task verification" in text
    assert "Interactive attachment: unavailable" in text
    assert path.read_bytes() == log and work.service._index_path.read_bytes() == before


async def test_missing_owners_do_not_construct_task_storage(work, monkeypatch):
    from henchman.advanced.tasks import TaskService
    runtime = frontend(work)
    work.registry.unregister("task_get")
    runtime.orchestrator = SimpleNamespace(subagents=None)
    monkeypatch.setattr(TaskService, "__init__", lambda *_a, **_k: pytest.fail("Inspection created storage"))
    text = await render(work, [], runtime=runtime)
    assert "owner unavailable" in text and "task service unavailable" in text
    text = await render(work, ["inspect", "task", "unavailable"], runtime=runtime)
    assert "unavailable" in text


@pytest.mark.parametrize("args", [["stop", "task"], ["inspect", "task"], ["inspect", "other", "id"], ["list", "extra"]])
async def test_invalid_work_arguments_never_read_or_change_owners(work, monkeypatch, args):
    with monkeypatch.context() as patch:
        patch.setattr(work.service, "list_tasks", lambda: pytest.fail("Invalid command inspected tasks"))
        patch.setattr(work.agents, "list", lambda: pytest.fail("Invalid command inspected agents"))
        assert "Usage:" in await render(work, args)


@pytest.mark.parametrize("change", ["session", "cwd", "owner", "project"])
async def test_late_task_read_refuses_replaced_runtime_before_publication(work, monkeypatch, change):
    record = await work.service.start_task(argv=[sys.executable, "-c", "print('old-project-evidence')"])
    await work.service.wait_for_task(record.task_id, timeout=5)
    runtime = frontend(work)
    entered, release, finished = Event(), Event(), Event()
    original = work.service.get_task
    def blocked(identity):
        entered.set()
        assert release.wait(10)
        try:
            return original(identity)
        finally:
            finished.set()
    monkeypatch.setattr(work.service, "get_task", blocked)
    task = asyncio.create_task(render(work, ["inspect", "task", record.task_id], runtime=runtime))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if change == "session":
            work.manager.set_session(work.manager.create_session(work.manager.current.project_hash), history_agent=work.actor)
        elif change == "owner":
            work.registry.unregister("task_get")
        else:
            other = work.root / "other"
            other.mkdir()
            if change == "cwd":
                monkeypatch.chdir(other)
            else:
                runtime.project_root = other
        release.set()
        text = await asyncio.wait_for(task, 10)
        assert finished.is_set() and "old-project-evidence" not in text
        assert "changed" in text.lower()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_command_cancellation_joins_owned_read_and_never_publishes(work, monkeypatch):
    entered, release, finished = Event(), Event(), Event()
    original = work.service.list_tasks
    def blocked():
        entered.set()
        assert release.wait(10)
        try:
            return original()
        finally:
            finished.set()
    monkeypatch.setattr(work.service, "list_tasks", blocked)
    output = StringIO()
    task = asyncio.create_task(render(work, ["list"], console=Console(file=output)))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel("first interruption")
        await asyncio.sleep(0)
        task.cancel("second interruption")
        await asyncio.sleep(0)
        assert not task.done() and not finished.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError) as error:
            await task
        assert error.value.args == ("first interruption",)
        assert finished.is_set() and output.getvalue() == ""
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_selected_classic_session_must_match_before_any_owner_read(work, monkeypatch):
    stale = work.manager.current
    work.manager.set_session(work.manager.create_session(stale.project_hash), history_agent=work.actor)
    with monkeypatch.context() as patch:
        patch.setattr(work.service, "list_tasks", lambda: pytest.fail("Stale session read tasks"))
        patch.setattr(work.agents, "list", lambda: pytest.fail("Stale session read agents"))
        text = await render(work, [], session=stale)
    assert "Selected session changed" in text


@pytest.mark.parametrize("failure", [False, True])
async def test_awaited_read_refreshes_rotated_service_policy_before_publication(work, monkeypatch, failure):
    secret = "work-newly-known-private-value"
    record = await work.service.start_task(argv=[sys.executable, "-c", f"print({secret!r})"])
    await work.service.wait_for_task(record.task_id, timeout=5)
    original = work.service.get_task
    def rotated(identity):
        work.service._runtime.policy.register_secret(secret)
        if failure:
            raise OSError(secret)
        return original(identity)
    monkeypatch.setattr(work.service, "get_task", rotated)
    text = await render(work, ["inspect", "task", record.task_id])
    assert secret not in text and "[REDACTED]" in text
    assert ("Work inspection unavailable:" in text) is failure


async def test_unowned_task_remains_unknown_without_index_write_or_pid_adoption(work):
    from tests.advanced.test_task_store import record
    store = work.service._store
    raw = store.create(record())
    raw = store.replace(dict(raw, status="started", started_at=raw["created_at"]),
                        expected_revision=raw["revision"], owner_id="owner-a")
    raw = store.replace(dict(raw, status="running", pid=987654),
                        expected_revision=raw["revision"], owner_id="owner-a")
    before = store.path.read_bytes()
    text = await render(work, ["inspect", "task", raw["task_id"]])
    assert "outcome_unknown" in text and "no PID is adopted" in text
    assert store.path.read_bytes() == before
    assert raw["task_id"] not in work.service._runtime.processes


async def test_large_retained_log_and_combined_agent_details_have_whole_item_bounds(work):
    record = await work.service.start_task(argv=[sys.executable, "-c", "print('x' * 32769)"])
    await work.service.wait_for_task(record.task_id, timeout=5)
    before = work.service.get_task(record.task_id).output_path.read_bytes()
    text = await render(work, ["inspect", "task", record.task_id])
    assert "retained log exceeds 32 KiB" in text and "x" * 100 not in text
    assert work.service.get_task(record.task_id).output_path.read_bytes() == before
    child = work.agents._conversations[work.records[1].conversation_id]
    child.record = replace(child.record, output="o" * 32760, error="e" * 32760)
    text = await render(work, ["inspect", "agent", child.record.conversation_id])
    assert "omitted" in text.lower() and child.record.conversation_id in text
    # Console wrapping adds line breaks; the projected content itself is capped.
    from henchman.cli.work_inspection import WorkInspection
    inspection = WorkInspection(frontend(work))
    fields, interrupted = await inspection.inspect("agent", child.record.conversation_id)
    assert len(inspection.details(fields, interrupted=interrupted).encode()) <= 65536
    assert len(child.record.output) == len(child.record.error) == 32760


async def test_catalog_cannot_expand_beyond_200_rows(work, monkeypatch):
    from henchman.cli.work_inspection import WorkInspection
    original = work.agents.list()
    with monkeypatch.context() as patch:
        patch.setattr(work.agents, "list", lambda: [original[0]] * 205)
        inspection = WorkInspection(frontend(work))
        rows, notice = await inspection.catalog(limit=500)
        assert len(rows) == 200 and "200-row display limit" in notice
        text = await render(work, [])
    assert text.count(original[0].conversation_id) == 200
    assert len(inspection.catalog_text(rows, notice).encode()) <= 65536


async def test_inspection_error_is_bounded_without_publishing_a_prefix(work, monkeypatch):
    error = ValueError("private-observation-" * 10000)
    def failed(_identity):
        raise error
    monkeypatch.setattr(work.service, "get_task", failed)
    text = await render(work, ["inspect", "task", "task-012345abcdef"])
    assert "unavailable" in text and "omitted" in text.lower()
    assert "private-observation-" not in text and len(text.encode()) <= 65536
    assert error.args == ("private-observation-" * 10000,)
