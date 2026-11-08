"""Launch intent, ownership, and observer safety at the public task boundary."""

import asyncio
import json
import multiprocessing
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from henchman.advanced.task_store import TaskStore
from henchman.advanced.tasks import TaskService


def _observe(project, result):
    service = TaskService(Path(project))
    records = service.list_tasks()
    result.put((records[0].status, service.tail_output(records[0].task_id)))


async def test_independent_observer_preserves_live_status_log_and_later_output(tmp_path):
    service = TaskService(tmp_path)
    release = tmp_path / "release"
    code = ("import time,pathlib; print('first',flush=True); "
            f"p=pathlib.Path({str(release)!r}); "
            "exec('while not p.exists(): time.sleep(.01)'); print('second',flush=True)")
    task = await service.start_task(argv=[sys.executable, "-u", "-c", code])
    context = multiprocessing.get_context("spawn")
    result = context.Queue()
    observer = context.Process(target=_observe, args=(str(tmp_path), result))
    try:
        async with asyncio.timeout(15):
            while "first" not in service.tail_output(task.task_id):
                await asyncio.sleep(.01)
        before = task.output_path.stat()
        original_index = service._index_path.read_bytes()
        observer.start()
        await asyncio.to_thread(observer.join, 15)
        assert observer.exitcode == 0
        assert result.get(timeout=2) == ("outcome_unknown", "first")
        assert service._index_path.read_bytes() == original_index
        assert os.path.samestat(before, task.output_path.stat())
        assert service.get_task(task.task_id).status == "running"
        release.touch()
        assert (await service.wait_for_task(task.task_id, timeout=15)).status == "completed"
        assert "second" in task.output_path.read_text()
    finally:
        if observer.pid is not None:
            if observer.is_alive():
                observer.terminate()
            observer.join()
        result.close()
        await service.stop_task(task.task_id)


async def test_intent_is_committed_before_transport_and_failed_spawn_is_recorded(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    observed = []

    async def fail_spawn(*_args, **_kwargs):
        saved = TaskStore(service._index_path).read()
        observed.extend(saved)
        assert len(saved) == 1 and saved[0]["status"] == "started"
        assert saved[0]["pid"] is None
        raise OSError("offline spawn failure")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail_spawn)
    with pytest.raises(OSError, match="offline spawn failure"):
        await service.start_task(argv=["never-executed"])
    assert len(observed) == 1
    assert service.list_tasks()[0].status == "failed"
    assert not service._runtime.processes


async def test_corrupt_authority_blocks_spawn_before_any_process(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    service._index_path.write_text("broken")

    async def forbidden(*_args, **_kwargs):
        pytest.fail("Corrupt authority must deny before process creation")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(OSError, match="index"):
        await service.start_task(argv=["never-executed"])


async def test_metadata_update_during_run_survives_owned_finalization(tmp_path):
    service = TaskService(tmp_path)
    task = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(.1)"])
    service.update_task(task.task_id, title="updated", metadata={"note": "keep"})
    final = await service.wait_for_task(task.task_id, timeout=15)
    assert final.status == "completed" and final.title == "updated" and final.metadata["note"] == "keep"
    assert TaskStore(service._index_path).read()[0]["title"] == "updated"


async def test_active_work_query_uses_only_live_local_handles(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    task = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(.1)"])
    try:
        assert TaskService.has_active_work(tmp_path)
        await service.wait_for_task(task.task_id, timeout=15)
    finally:
        await service.stop_task(task.task_id)
    before = service._index_path.read_bytes()

    def forbidden(*_args, **_kwargs):
        pytest.fail("Ownership query must not read, resolve, or persist files")

    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(TaskService, "__init__", forbidden)
    assert not TaskService.has_active_work(tmp_path)
    monkeypatch.undo()
    assert service._index_path.read_bytes() == before


def _crash_launch(project, target):
    service = TaskService(Path(project))
    count = 0

    def checkpoint(stage):
        nonlocal count
        if stage == "create:after_commit" and target == "queued":
            os._exit(37)
        if stage == "replace:after_commit":
            count += 1
            if {1: "started", 2: "running", 3: "completed"}.get(count) == target:
                os._exit(37)

    service._store._checkpoint = checkpoint

    async def run():
        marker = Path(project) / "effect"
        code = f"from pathlib import Path; p=Path({str(marker)!r}); p.open('a').write('effect\\n')"
        task = await service.start_task(argv=[sys.executable, "-c", code])
        await service.wait_for_task(task.task_id)

    asyncio.run(run())


@pytest.mark.parametrize("stage", ["queued", "started", "running", "completed"])
def test_process_death_preserves_dispatch_boundary_without_replay(tmp_path, stage):
    child = multiprocessing.get_context("spawn").Process(target=_crash_launch, args=(str(tmp_path), stage))
    child.start()
    try:
        child.join(20)
        assert child.exitcode == 37
    finally:
        if child.is_alive():
            child.terminate()
        child.join()
    service = TaskService(tmp_path)
    record = service.list_tasks()[0]
    assert record.status == ({"queued": "queued", "completed": "completed"}.get(stage, "outcome_unknown"))
    assert not service._runtime.processes and not TaskService.has_active_work(tmp_path)
    before = service._index_path.read_bytes()
    TaskService(tmp_path).list_tasks()
    assert service._index_path.read_bytes() == before
    if stage in {"queued", "started"}:
        assert not (tmp_path / "effect").exists()
    elif stage == "completed":
        assert (tmp_path / "effect").read_text() == "effect\n"


async def test_final_save_failure_retains_started_evidence_and_local_failure(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    task = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(.1)"])
    owned = service._runtime.processes[task.task_id]
    native = service._store.update_owned

    def fail_final(identity, **kwargs):
        if kwargs["changes"].get("status") in {"completed", "failed", "stopped"}:
            raise OSError("final save unavailable")
        return native(identity, **kwargs)

    monkeypatch.setattr(service._store, "update_owned", fail_final)
    final = await service.wait_for_task(task.task_id, timeout=15)
    assert final.status == "failed" and "persist" in final.metadata["error"]
    assert final.metadata["status_persisted"] == "false"
    assert owned.returncode == 0 and not TaskService.has_active_work(tmp_path)
    assert TaskStore(service._index_path).read()[0]["status"] == "running"
    from henchman.core.goals import GoalService
    from henchman.core.session_data import Session
    from henchman.tools.builtins.goal_status import GoalStatusTool

    session = Session("session", "project", "now", "now")
    goal = GoalService().start(session, "Finish work")
    tool = GoalStatusTool()
    tool.bind_runtime(session_manager=SimpleNamespace(current=session), project_root=tmp_path)
    result = await tool.execute(action="complete", goal_id=goal.id, summary="Done")
    assert not result.success and "unresolved" in result.content
    TaskService._runtimes.pop(service._storage_dir)
    assert TaskService(tmp_path).get_task(task.task_id).status == "outcome_unknown"


async def test_operation_ids_are_linked_without_reusing_task_identity(tmp_path):
    from henchman.core.operation_bindings import OperationBinding
    from henchman.core.operation_recovery import OperationContext
    from henchman.core.runtime_operations import use_operation_call

    context = OperationContext("project", "session", "run", "turn", "agent", "call")
    binding = OperationBinding("operation", context, 0)
    service = TaskService(tmp_path)
    with use_operation_call(SimpleNamespace(binding=binding)):
        task = await service.start_task(argv=[sys.executable, "-c", "pass"])
    await service.wait_for_task(task.task_id, timeout=15)
    assert task.task_id != "operation"
    assert task.operation_context == {"operation_id": "operation", "project_hash": "project",
                                      "session_id": "session", "run_id": "run", "turn_id": "turn",
                                      "agent_id": "agent", "tool_call_id": "call"}


@pytest.mark.parametrize("status", ["queued", "started", "running", "outcome_unknown"])
async def test_goal_cannot_complete_with_unresolved_process_evidence(tmp_path, status):
    from tests.advanced.test_task_store import record

    from henchman.core.goals import GoalService
    from henchman.core.session_data import Session
    from henchman.tools.builtins.goal_status import GoalStatusTool

    service = TaskService(tmp_path)
    payload = record()
    payload.update(status=status, owner_id=None)
    service._index_path.write_text(json.dumps([payload]))
    service._index_path.with_suffix(".lock").unlink()  # Construct a genuine legacy fixture.
    TaskService._runtimes.pop(service._storage_dir)
    session = Session("session", "project", "now", "now")
    goal = GoalService().start(session, "Finish work")
    tool = GoalStatusTool()
    tool.bind_runtime(session_manager=SimpleNamespace(current=session), project_root=tmp_path)
    result = await tool.execute(action="complete", goal_id=goal.id, summary="Done")
    assert not result.success and "unresolved" in result.content
    assert GoalService().get(session).status == "active"


async def test_queued_tool_display_is_explicitly_not_dispatched(tmp_path):
    from tests.advanced.test_task_store import record

    from henchman.tools.builtins.tier6_tools import TaskGetTool

    service = TaskService(tmp_path)
    queued = service._store.create(record())
    tool = TaskGetTool()
    tool.bind_runtime(project_root=tmp_path, tool_registry=None)
    result = await tool.execute(task_id=queued["task_id"])
    assert result.success and "not dispatched" in result.content.lower()
    assert "disposition" in result.content.lower()


async def test_cancellation_before_start_commit_keeps_not_dispatched_observation(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    cancelled = False

    def checkpoint(stage):
        nonlocal cancelled
        if stage == "replace:before_commit" and not cancelled:
            cancelled = True
            raise asyncio.CancelledError

    async def forbidden(*_args, **_kwargs):
        pytest.fail("Cancellation before start must not spawn")

    service._store._checkpoint = checkpoint
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(asyncio.CancelledError):
        await service.start_task(argv=["never-executed"])
    saved = TaskStore(service._index_path).read()[0]
    assert saved["status"] == "cancelled" and saved["started_at"] is None and saved["pid"] is None
    assert not TaskService.has_active_work(tmp_path)


async def test_cancellation_during_spawn_retains_intent_and_reaps_only_owned_child(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    native = asyncio.create_subprocess_exec
    created = asyncio.Event()
    release = asyncio.Event()
    children = []

    async def gated(*args, **kwargs):
        process = await native(*args, **kwargs)
        children.append(process)
        created.set()
        await release.wait()
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", gated)
    launch = asyncio.create_task(service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"]))
    await asyncio.wait_for(created.wait(), 15)
    launch.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(launch, 10)
    assert children[0].returncode is not None
    saved = TaskStore(service._index_path).read()[0]
    assert saved["status"] == "stopped" and saved["started_at"] is not None
    assert not TaskService.has_active_work(tmp_path)


async def test_cancelled_spawn_without_returned_handle_is_unknown_and_closes_capture(tmp_path, monkeypatch):
    service = TaskService(tmp_path)

    async def cancelled(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "create_subprocess_exec", cancelled)
    with pytest.raises(asyncio.CancelledError):
        await service.start_task(argv=["never-executed"])
    assert service.list_tasks()[0].status == "outcome_unknown"
    assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("henchman-task-output")]


async def test_failed_cleanup_preserves_owned_handle_for_explicit_stop(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    native_update = service._store.update_owned
    native_terminate = service._terminate_process
    failed = False
    children = []

    def fail_running(identity, **kwargs):
        if kwargs["changes"].get("status") == "running":
            raise OSError("running save failed")
        return native_update(identity, **kwargs)

    async def fail_once(process):
        nonlocal failed
        children.append(process)
        if not failed:
            failed = True
            raise OSError("cleanup temporarily failed")
        await native_terminate(process)

    monkeypatch.setattr(service._store, "update_owned", fail_running)
    monkeypatch.setattr(service, "_terminate_process", fail_once)
    try:
        with pytest.raises(OSError, match="running save failed"):
            await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"])
        assert TaskService.has_active_work(tmp_path)
        record = service.list_tasks()[0]
        assert record.status == "outcome_unknown"
        final = await service.stop_task(record.task_id)
        assert final.status == "stopped"
        assert not TaskService.has_active_work(tmp_path)
    finally:
        for process in children:
            await native_terminate(process)


async def test_pending_owned_launch_blocks_restore_until_cancellation_cleanup_settles(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    entered = asyncio.Event()
    release = asyncio.Event()
    native = asyncio.create_subprocess_exec

    async def gated(*args, **kwargs):
        entered.set()
        await release.wait()
        return await native(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", gated)
    launch = asyncio.create_task(service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"]))
    try:
        await asyncio.wait_for(entered.wait(), 15)
        assert not service._runtime.processes and not service._runtime.monitors
        assert TaskService.has_active_work(tmp_path)
        launch.cancel()
        await asyncio.sleep(0)
        assert TaskService.has_active_work(tmp_path)
    finally:
        launch.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(launch, 15)
    assert not TaskService.has_active_work(tmp_path)


async def test_owned_final_observation_projects_newly_known_credentials(tmp_path):
    service = TaskService(tmp_path)
    secret = "newly-known-task-credential"
    release = tmp_path / "release"
    code = ("import time,pathlib; " + f"p=pathlib.Path({str(release)!r}); "
            "exec('while not p.exists(): time.sleep(.01)')")
    task = await service.start_task(argv=[sys.executable, "-c", code, secret], metadata={"echo": secret})
    try:
        settings = tmp_path / ".henchman/settings.yaml"
        settings.write_text(json.dumps({"providers": {"options": {"test": {"api_key": secret}}}}))
        TaskService(tmp_path)  # Register the new policy without rewriting active evidence.
        release.touch()
        await service.wait_for_task(task.task_id, timeout=15)
        assert secret not in service._index_path.read_text()
    finally:
        await service.stop_task(task.task_id)


async def test_finalization_does_not_overwrite_metadata_from_another_store_handle(tmp_path):
    service = TaskService(tmp_path)
    release = tmp_path / "release"
    code = ("import time,pathlib; " + f"p=pathlib.Path({str(release)!r}); "
            "exec('while not p.exists(): time.sleep(.01)')")
    task = await service.start_task(argv=[sys.executable, "-c", code], metadata={"note": "original"})
    try:
        other = TaskStore(service._index_path)
        current = other.read()[0]
        other.replace(dict(current, metadata={"note": "external edit"}), expected_revision=current["revision"])
        release.touch()
        final = await service.wait_for_task(task.task_id, timeout=15)
        assert final.metadata["note"] == "external edit"
        assert other.read()[0]["metadata"]["note"] == "external edit"
    finally:
        await service.stop_task(task.task_id)


async def test_monitor_cleanup_error_settles_waiter_but_retains_live_ownership(tmp_path, monkeypatch):
    service = TaskService(tmp_path)
    native = service._terminate_process
    failed = False

    async def fail_once(process):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("monitor cleanup refused")
        await native(process)

    monkeypatch.setattr(service, "_terminate_process", fail_once)
    task = await service.start_task(argv=[sys.executable, "-c", "import time; time.sleep(30)"], timeout=.05)
    process = service._runtime.processes[task.task_id]
    monitor = service._runtime.monitors[task.task_id]
    try:
        observed = await service.wait_for_task(task.task_id, timeout=2)
        assert observed.status == "outcome_unknown" and "cleanup" in observed.metadata["error"]
        assert TaskService.has_active_work(tmp_path)
        assert (await service.stop_task(task.task_id)).status == "stopped"
    finally:
        await native(process)
        await asyncio.gather(monitor, return_exceptions=True)


@pytest.mark.parametrize('cleanup_fails', [False, True])
async def test_stop_retains_monitor_outcome_when_waiter_is_removed_during_termination(tmp_path, monkeypatch, cleanup_fails):
    from henchman.tools.builtins.tier6_tools import TaskStopTool

    monkeypatch.chdir(tmp_path)
    tool = TaskStopTool()
    tool.bind_runtime(tool_registry=None, project_root=tmp_path)
    service = tool._task_service
    original_terminate = service._terminate_process
    original_finish = service._finish_capture
    record = await service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    process = service._runtime.processes[record.task_id]
    monitor = service._runtime.monitors[record.task_id]
    direct = None

    async def fail_after_cleanup(child, output):
        await original_finish(child, output)
        if cleanup_fails:
            raise OSError('monitor cleanup observation unavailable')

    async def hold_direct_until_monitor_settles(child):
        await original_terminate(child)
        if asyncio.current_task() is direct:
            async with asyncio.timeout(15):
                while record.task_id in service._runtime.waiters:
                    await asyncio.sleep(.01)

    monkeypatch.setattr(service, '_finish_capture', fail_after_cleanup)
    monkeypatch.setattr(service, '_terminate_process', hold_direct_until_monitor_settles)
    try:
        direct = asyncio.create_task(tool.execute(task_id=record.task_id))
        result = await asyncio.wait_for(direct, 20)
        if cleanup_fails:
            assert not result.success and '[outcome_unknown]' in result.content
            assert 'cleanup observation unavailable' in result.content
        else:
            assert result.success and '[stopped]' in result.content
        assert process.returncode is not None and monitor.done()
    finally:
        if process.returncode is None:
            await original_terminate(process)
        await asyncio.gather(monitor, return_exceptions=True)


@pytest.mark.parametrize('mismatch', ['process', 'loop'])
async def test_stop_refuses_foreign_runtime_before_signalling(tmp_path, mismatch):
    from henchman.advanced.tasks import TaskOwnershipError

    service = TaskService(tmp_path)
    record = await service.start_task(argv=[sys.executable, '-c', 'import time; time.sleep(30)'])
    runtime = service._runtime
    process = runtime.processes[record.task_id]
    original_process_id = runtime.process_id
    original_waiter = runtime.waiters[record.task_id]
    other_loop = asyncio.new_event_loop()
    try:
        if mismatch == 'process':
            runtime.process_id = -1
        else:
            runtime.waiters[record.task_id] = other_loop.create_future()
        with pytest.raises(TaskOwnershipError, match='runtime|loop'):
            await service.stop_task(record.task_id)
        assert process.returncode is None
    finally:
        runtime.process_id = original_process_id
        runtime.waiters[record.task_id] = original_waiter
        other_loop.close()
        await service.stop_task(record.task_id)
