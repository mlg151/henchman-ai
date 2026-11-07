"""Automatic checkpoints belong to authorized deterministic operation effects."""

import asyncio
import base64
import os
from dataclasses import asdict
from threading import Event

import pytest

from henchman.advanced.checkpoints import CheckpointService
from henchman.config.schema import Settings
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.runtime_operations import use_operation_call
from henchman.core.session_data import Session
from henchman.core.session_models import SessionMessage
from henchman.core.session_operations import SessionRunOperations
from henchman.providers.base import ToolCall
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.patch_apply import PatchApplyTool
from henchman.tools.registry import ToolRegistry


def _operation(tool, params):
    call = ToolCall("call", tool.name, params)
    session = Session("session", "project", "today", "today")
    session.messages.append(SessionMessage("assistant", tool_calls=[asdict(call)]))
    runtime = SessionRunOperations(Settings(), lambda: session, lambda _: None, None)
    invocation = runtime.begin().bind_call(call, agent_id="engineer", assistant_index=0)
    return invocation


async def _registry(tool):
    registry = ToolRegistry()
    registry.register(tool)

    async def approve(_request):
        return True

    registry.set_confirmation_handler(approve)
    return registry


async def test_authorized_write_captures_before_and_formatted_after_with_operation_identity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "source.py").write_bytes(b"old = 1\n")
    (tmp_path / "dirty.py").write_bytes(b"dirty=  1\n")
    tool = WriteFileTool()
    params = {"path": "source.py", "content": "answer=  42\n"}
    registry = await _registry(tool)
    operation = _operation(tool, params)
    with use_operation_call(operation):
        result = await registry.execute(tool.name, params)
    assert result.success
    records = CheckpointService(tmp_path).list_checkpoints()
    assert len(records) == 1
    record = records[0]
    assert record.operation.operation_id == operation.binding.operation_id
    assert record.operation.run_id == operation.run.run_id
    assert record.operation.agent_id == "engineer"
    assert record.operation.tool_name == "write_file"
    review = CheckpointService(tmp_path).review(record.checkpoint_id)
    assert [file.path for file in review.files] == ["source.py"]
    assert review.files[0].before.content == b"old = 1\n"
    assert review.files[0].after.content == b"answer = 42\n"
    assert (tmp_path / "dirty.py").read_bytes() == b"dirty=  1\n"
    assert result.metadata["henchman.checkpoint"]["status"] == "captured"
    assert result.metadata["henchman.checkpoint"]["checkpoint_id"] == record.checkpoint_id


async def test_denied_and_unbound_writes_create_no_automatic_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool = WriteFileTool()
    registry = await _registry(tool)
    params = {"path": "source.txt", "content": "text"}
    registry.set_plan_mode(enabled=True)
    with use_operation_call(_operation(tool, params)):
        assert not (await registry.execute(tool.name, params)).success
    assert not (tmp_path / ".henchman/tungsten/checkpoints").exists()
    registry.set_plan_mode(enabled=False)
    assert (await registry.execute(tool.name, params)).success
    assert not (tmp_path / ".henchman/tungsten/checkpoints").exists()


async def test_completed_replay_keeps_one_checkpoint_and_does_not_rewrite_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tool = WriteFileTool()
    registry = await _registry(tool)
    params = {"path": "source.txt", "content": "first"}
    operation = _operation(tool, params)
    with use_operation_call(operation):
        first = await registry.execute(tool.name, params)
    (tmp_path / "source.txt").write_text("user edit")
    with use_operation_call(operation):
        second = await registry.execute(tool.name, params)
    assert second.content == first.content
    assert len(CheckpointService(tmp_path).list_checkpoints()) == 1
    assert (tmp_path / "source.txt").read_text() == "user edit"


async def test_unknown_effects_report_unavailable_without_inferred_file_ownership(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class Opaque(Tool):
        name, description, kind = "opaque", "Unknown effects", ToolKind.EXECUTE

        async def execute(self, **params):
            (tmp_path / "effect.txt").write_text("effect")
            return ToolResult("done")

    tool = Opaque()
    registry = await _registry(tool)
    with use_operation_call(_operation(tool, {})):
        result = await registry.execute(tool.name, {})
    assert result.success
    assert result.metadata["henchman.checkpoint"] == {"status": "unavailable", "reason": "Tool effects have no deterministic file scope"}
    assert not (tmp_path / ".henchman/tungsten/checkpoints").exists()


@pytest.mark.parametrize("tool,params,expected", [
    (WriteFileTool(), {"path": "file"}, ("file",)),
    (EditFileTool(), {"path": "file", "dry_run": True}, ()),
    (EditFileTool(), {"path": "file"}, ("file",)),
    (PatchApplyTool(), {"path": "override", "patch": "--- a/a\n+++ b/b\n@@ -1 +1 @@\n-old\n+new"}, ("override",)),
    (PatchApplyTool(), {"patch": "--- a/a\n+++ b/b\n@@ -1 +1 @@\n-old\n+new"}, ("b",)),
])
def test_builtin_scope_matches_actual_parser_targets(tool, params, expected):
    assert tool.checkpoint_paths(params) == expected


async def test_literal_tilde_patch_scope_matches_actual_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "~").mkdir()
    target = tmp_path / "~/file"
    target.write_bytes(b"old\n")
    tool = PatchApplyTool()
    params = {"path": "~/file", "patch": "@@ -1 +1 @@\n-old\n+new\n"}
    registry = await _registry(tool)
    with use_operation_call(_operation(tool, params)):
        result = await registry.execute(tool.name, params)
    assert result.success, result.content
    record, = CheckpointService(tmp_path).list_checkpoints()
    file, = CheckpointService(tmp_path).review(record.checkpoint_id).files
    assert file.path == "~/file" and file.before.content == b"old\n"
    assert file.after.content == target.read_bytes()
    assert target.read_text() == "new\n"


async def test_write_expands_home_before_declaring_scope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    tool = WriteFileTool()
    params = {"path": "~/file", "content": "new"}
    registry = await _registry(tool)
    with use_operation_call(_operation(tool, params)):
        result = await registry.execute(tool.name, params)
    assert result.success, result.content
    record, = CheckpointService(tmp_path).list_checkpoints()
    file, = CheckpointService(tmp_path).review(record.checkpoint_id).files
    assert file.path == "file" and file.after.content == b"new"


@pytest.mark.parametrize("failure", ["raise", "cancel", "result", "invalid_output"])
async def test_partial_effect_and_failure_remain_reviewable(tmp_path, monkeypatch, failure):
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "partial.txt"
    target.write_text("old")

    class Partial(Tool):
        name, description, kind = "partial", "Partial effect", ToolKind.WRITE
        output_schema = {"type": "object"} if failure == "invalid_output" else None

        def checkpoint_paths(self, params):
            return ("partial.txt",)

        async def execute(self, **params):
            target.write_text("partial")
            if failure == "raise":
                raise RuntimeError("failure after write")
            if failure == "cancel":
                raise asyncio.CancelledError()
            return ToolResult("partial", success=failure == "invalid_output")

    tool = Partial()
    registry = await _registry(tool)
    operation = _operation(tool, {})
    with use_operation_call(operation):
        if failure in {"raise", "cancel"}:
            with pytest.raises(OperationRecoveryError if failure == "raise" else asyncio.CancelledError):
                await registry.execute(tool.name, {})
        else:
            result = await registry.execute(tool.name, {})
            assert not result.success
            assert result.metadata["henchman.checkpoint"]["status"] == "captured"
    record, = CheckpointService(tmp_path).list_checkpoints()
    file, = CheckpointService(tmp_path).review(record.checkpoint_id).files
    assert record.state == "ready" and file.before.content == b"old" and file.after.content == b"partial"
    expected_state = "outcome_unknown" if failure in {"raise", "cancel"} else "completed"
    assert operation.run.journal.report().records[0].state == expected_state


@pytest.mark.parametrize("change", ["plan_mode", "remove", "replace", "guard"])
async def test_authorization_change_while_capture_awaits_discards_before_only_capture(tmp_path, monkeypatch, change):
    from henchman.tools.checkpoint_capture import MutationCheckpoint

    monkeypatch.chdir(tmp_path)
    tool = WriteFileTool()
    registry = await _registry(tool)
    original = MutationCheckpoint.begin

    async def changed(capture):
        await original(capture)
        if change == "plan_mode":
            registry.set_plan_mode(enabled=True)
        elif change == "remove":
            registry.unregister(tool.name)
        elif change == "replace":
            registry.register(WriteFileTool())
        else:
            registry.set_execution_guard(lambda *_args: ToolResult("blocked", success=False))

    monkeypatch.setattr(MutationCheckpoint, "begin", changed)
    params = {"path": "file", "content": "must not run"}
    operation = _operation(tool, params)
    with use_operation_call(operation):
        result = await registry.execute(tool.name, params)
    assert not result.success and not (tmp_path / "file").exists()
    assert CheckpointService(tmp_path).list_checkpoints() == ()
    assert operation.run.journal.report().records[0].state == "cancelled"


@pytest.mark.skipif(os.name == "nt", reason="Restricted file backend requires POSIX descriptors")
async def test_restricted_operation_reports_unavailable_without_unmediated_storage(tmp_path, monkeypatch):
    from henchman.tools.access_policy import ToolAccessPolicy

    monkeypatch.chdir(tmp_path)
    tool = WriteFileTool()
    registry = await _registry(tool)
    registry.set_access_policy(ToolAccessPolicy.from_settings(Settings(tools={"filesystem_write_roots": ["."]}).tools,
                                                             project_root=tmp_path))
    params = {"path": "file", "content": "allowed body"}
    with use_operation_call(_operation(tool, params)):
        result = await registry.execute(tool.name, params)
    assert result.success and (tmp_path / "file").read_text() == "allowed body"
    assert result.metadata["henchman.checkpoint"]["status"] == "unavailable"
    assert not (tmp_path / ".henchman/tungsten/checkpoints").exists()


async def test_cancellation_joins_completion_and_holds_shared_mutation_lock(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entered, release = Event(), Event()
    original = CheckpointService.complete

    def blocked(service, identity):
        entered.set()
        assert release.wait(10), "test failed to release completion"
        return original(service, identity)

    monkeypatch.setattr(CheckpointService, "complete", blocked)
    tool = WriteFileTool()
    parent = await _registry(tool)
    child = await _registry(WriteFileTool())
    child.inherit_policies_from(parent)
    params = {"path": "file", "content": "first"}
    operation = _operation(tool, params)

    async def dispatch():
        with use_operation_call(operation):
            return await parent.execute(tool.name, params)

    first = asyncio.create_task(dispatch())
    second = None
    try:
        assert await asyncio.to_thread(entered.wait, 10)
        first.cancel()
        await asyncio.sleep(0)
        first.cancel()
        second = asyncio.create_task(child.execute(tool.name, {"path": "file", "content": "second"}))
        await asyncio.sleep(0)
        assert not first.done() and not second.done()
        assert (tmp_path / "file").read_text() == "first"
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(first, 10)
        if second is not None:
            assert (await asyncio.wait_for(second, 10)).success
    record, = CheckpointService(tmp_path).list_checkpoints()
    file, = CheckpointService(tmp_path).review(record.checkpoint_id).files
    assert file.after.content == b"first"
    assert (tmp_path / "file").read_text() == "second"
    assert operation.run.journal.report().records[0].state == "outcome_unknown"


async def test_denied_after_capture_does_not_format_concurrent_external_edit(tmp_path, monkeypatch):
    from henchman.tools.checkpoint_capture import MutationCheckpoint

    monkeypatch.chdir(tmp_path)
    target = tmp_path / "file.py"
    target.write_text("old = 1\n")
    tool = WriteFileTool()
    registry = await _registry(tool)
    original = MutationCheckpoint.begin

    async def changed(capture):
        await original(capture)
        target.write_text("external=  1\n")
        registry.set_plan_mode(enabled=True)

    monkeypatch.setattr(MutationCheckpoint, "begin", changed)
    params = {"path": "file.py", "content": "must not run"}
    with use_operation_call(_operation(tool, params)):
        result = await registry.execute(tool.name, params)
    assert not result.success
    assert target.read_text() == "external=  1\n"
    assert CheckpointService(tmp_path).list_checkpoints() == ()


async def test_policy_tightened_during_body_prevents_formatter_and_after_reads(tmp_path, monkeypatch):
    from henchman.tools.access_policy import ToolAccessPolicy

    monkeypatch.chdir(tmp_path)
    target = tmp_path / "file.py"
    target.write_text("old = 1\n")

    class ChangesPolicy(Tool):
        name, description, kind = "changes_policy", "Changes policy during body", ToolKind.WRITE

        def checkpoint_paths(self, params):
            return ("file.py",)

        async def execute(self, **params):
            target.write_text("changed=  1\n")
            registry.set_access_policy(ToolAccessPolicy.from_settings(Settings(tools={"network_access": "disabled"}).tools,
                                                                     project_root=tmp_path))
            return ToolResult("done")

    tool = ChangesPolicy()
    registry = await _registry(tool)
    with use_operation_call(_operation(tool, {})), pytest.raises(OperationRecoveryError, match="outcome_unknown"):
        await registry.execute(tool.name, {})
    assert target.read_text() == "changed=  1\n"
    record, = CheckpointService(tmp_path).list_checkpoints()
    assert record.state == "capturing"


async def test_policy_tightened_while_waiting_for_formatter_lock_prevents_snapshot(tmp_path, monkeypatch):
    from henchman.tools import formatting
    from henchman.tools.access_policy import ToolAccessPolicy

    monkeypatch.chdir(tmp_path)
    tool = WriteFileTool()
    registry = await _registry(tool)
    params = {"path": "file.py", "content": "value=1\n"}
    operation = _operation(tool, params)
    approved = asyncio.Event()

    async def approve(_request):
        approved.set()
        return True

    registry.set_confirmation_handler(approve)

    async def snapshot(_scope):
        raise AssertionError("unmediated snapshot after policy restriction")

    monkeypatch.setattr(formatting, "_take_snapshot", snapshot)

    async def dispatch():
        with use_operation_call(operation):
            return await registry.execute(tool.name, params)

    async with registry._formatter._lock:
        task = asyncio.create_task(dispatch())
        await asyncio.wait_for(approved.wait(), 5)
        registry.set_access_policy(ToolAccessPolicy.unbound())
    result = await asyncio.wait_for(task, 5)
    assert not result.success and "snapshot" not in result.content
    assert not (tmp_path / ".henchman/tungsten/checkpoints").exists()


async def test_policy_tightened_inside_before_worker_denies_storage_and_dispatch(tmp_path, monkeypatch):
    from henchman.tools import checkpoint_capture
    from henchman.tools.access_policy import ToolAccessPolicy

    monkeypatch.chdir(tmp_path)
    tool = WriteFileTool()
    registry = await _registry(tool)
    params = {"path": "file", "content": "must not run"}

    def changed(*args, **kwargs):
        registry.set_access_policy(ToolAccessPolicy.unbound())
        return CheckpointService(*args, **kwargs)

    monkeypatch.setattr(checkpoint_capture, "CheckpointService", changed)
    operation = _operation(tool, params)
    with use_operation_call(operation):
        result = await registry.execute(tool.name, params)
    assert not result.success and not (tmp_path / "file").exists()
    assert not (tmp_path / ".henchman/tungsten/checkpoints").exists()
    assert operation.run.journal.report().records[0].state == "cancelled"


@pytest.mark.parametrize("control", ["budget", "continuation"])
async def test_control_failure_remains_primary_when_after_capture_fails(tmp_path, monkeypatch, control):
    from henchman.core.run_budget import BudgetExceeded
    from henchman.providers.continuation import ProviderContinuationError

    monkeypatch.chdir(tmp_path)
    error = BudgetExceeded("request_limit") if control == "budget" else ProviderContinuationError("missing")
    calls = []

    class Failing(Tool):
        name, description, kind = "failing", "Partial write with control failure", ToolKind.WRITE

        def checkpoint_paths(self, params):
            return ("file",)

        async def execute(self, **params):
            calls.append("effect")
            (tmp_path / "file").write_text("partial")
            raise error

    def failed(*_args):
        raise OSError("after capture storage failed")

    monkeypatch.setattr(CheckpointService, "complete", failed)
    tool = Failing()
    registry = await _registry(tool)
    operation = _operation(tool, {})
    with use_operation_call(operation), pytest.raises(type(error)) as observed:
        await registry.execute(tool.name, {})
    assert observed.value is error
    assert error.__notes__ and "Checkpoint finalization" in error.__notes__[0]
    assert operation.run.journal.report().records[0].state == "outcome_unknown"
    record, = CheckpointService(tmp_path).list_checkpoints()
    assert record.state == "capturing"
    with use_operation_call(operation), pytest.raises(OperationRecoveryError):
        await registry.execute(tool.name, {})
    assert calls == ["effect"]


async def test_checkpoint_metadata_collision_preserves_original_and_emits_bounded_notice(tmp_path, monkeypatch):
    from henchman.tools.checkpoint_capture import MutationCheckpoint

    monkeypatch.chdir(tmp_path)
    tool = WriteFileTool()
    capture = MutationCheckpoint(_operation(tool, {}), tool, {"path": "file"}, lambda: False)
    capture.report = {"status": "captured", "checkpoint_id": "a" * 32, "restorable": True}
    metadata = {"checkpoint": "original", "henchman.checkpoint": {"caller": "do not overwrite"}}
    raw = ToolResult("raw content", content_blocks=({"type": "text", "text": "raw block"},), metadata=metadata)
    projected = capture.project(raw)
    assert projected.metadata == metadata
    assert projected.content.startswith("raw content\n")
    assert "captured" in projected.content and "a" * 32 in projected.content
    assert "do not overwrite" not in projected.content and len(projected.content) < 200
    assert raw.content == "raw content" and raw.metadata is metadata
    assert projected.content_blocks == raw.content_blocks


async def test_policy_tightened_between_before_files_stops_next_read_and_persistence(tmp_path, monkeypatch):
    from henchman.advanced.checkpoint_files import WorkspaceFiles
    from henchman.tools.access_policy import ToolAccessPolicy

    monkeypatch.chdir(tmp_path)
    for name in ("a", "b"):
        (tmp_path / name).write_text("original")
    reads, calls = [], []
    original = WorkspaceFiles.state

    class Multiple(Tool):
        name, description, kind = "multiple", "Two deterministic targets", ToolKind.WRITE

        def checkpoint_paths(self, params):
            return ("a", "b")

        async def execute(self, **params):
            calls.append("not allowed")
            return ToolResult("unreachable")

    tool = Multiple()
    registry = await _registry(tool)

    def changed(files, path):
        reads.append(path)
        value = original(files, path)
        registry.set_access_policy(ToolAccessPolicy.unbound())
        return value

    monkeypatch.setattr(WorkspaceFiles, "state", changed)
    operation = _operation(tool, {})
    with use_operation_call(operation):
        result = await registry.execute(tool.name, {})
    assert not result.success and reads == ["a"] and calls == []
    assert not list((tmp_path / ".henchman/tungsten/checkpoints").glob("*.json"))
    assert operation.run.journal.report().records[0].state == "cancelled"


async def test_known_scope_is_not_erased_when_policy_tightens(tmp_path, monkeypatch):
    from henchman.tools.checkpoint_capture import MutationCheckpoint

    monkeypatch.chdir(tmp_path)
    tool = WriteFileTool()
    restricted = False
    capture = MutationCheckpoint(_operation(tool, {}), tool, {"path": "file.py"}, lambda: restricted)
    restricted = True
    await capture.begin()
    assert capture.paths == (tmp_path / "file.py",)
    assert capture.report["status"] == "unavailable"
    assert not (tmp_path / ".henchman/tungsten/checkpoints").exists()


async def test_cancellation_during_before_capture_joins_and_discards_without_dispatch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entered, release = Event(), Event()
    original = CheckpointService.begin

    def blocked(service, *args, **kwargs):
        record = original(service, *args, **kwargs)
        entered.set()
        assert release.wait(10), "test failed to release capture"
        return record

    monkeypatch.setattr(CheckpointService, "begin", blocked)
    tool = WriteFileTool()
    registry = await _registry(tool)
    params = {"path": "file", "content": "must not run"}
    operation = _operation(tool, params)

    async def dispatch():
        with use_operation_call(operation):
            return await registry.execute(tool.name, params)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(entered.wait, 10)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 10)
    assert not (tmp_path / "file").exists()
    assert CheckpointService(tmp_path).list_checkpoints() == ()
    assert operation.run.journal.report().records[0].state == "cancelled"


async def test_joined_worker_failure_preserves_first_cancellation_and_joins():
    from henchman.tools.checkpoint_capture import _joined

    entered, release, finished = Event(), Event(), Event()

    def failed():
        entered.set()
        assert release.wait(10)
        finished.set()
        raise OSError("private failure details")

    task = asyncio.create_task(_joined(failed))
    try:
        assert await asyncio.to_thread(entered.wait, 10)
        task.cancel("original cancellation")
        await asyncio.sleep(0)
        task.cancel("later cancellation")
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError) as observed:
        await task
    assert observed.value.args == ("original cancellation",) and finished.is_set()
    assert "private failure details" not in str(observed.value.__notes__)


@pytest.mark.parametrize("initially_restricted", [False, True])
async def test_storage_unavailability_retains_exact_declared_formatting_scope(tmp_path, monkeypatch, initially_restricted):
    from henchman.tools.checkpoint_capture import MutationCheckpoint

    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.chdir(root)
    tool = WriteFileTool()
    target = root / "file.py" if initially_restricted else tmp_path / "outside.py"
    restricted = initially_restricted
    capture = MutationCheckpoint(_operation(tool, {}), tool, {"path": str(target)}, lambda: restricted)
    restricted = False
    await capture.begin()
    assert capture.paths == (target,)
    assert capture.report["status"] == "unavailable"
    assert not (root / ".henchman/tungsten/checkpoints").exists()


@pytest.mark.parametrize("outside_project", [False, True])
async def test_only_declared_files_are_formatted_despite_concurrent_dirty_edit(tmp_path, monkeypatch, outside_project):
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.chdir(root)
    target = (tmp_path if outside_project else root) / "target.py"
    target.write_text("old = 1\n")
    unrelated = root / "unrelated.py"
    unrelated.write_text("old = 1\n")
    entered, release = asyncio.Event(), asyncio.Event()

    class Declared(Tool):
        name, description, kind = "declared", "One exact target", ToolKind.WRITE

        def checkpoint_paths(self, params):
            return (str(target),)

        async def execute(self, **params):
            target.write_text("owned=  1\n")
            entered.set()
            await release.wait()
            return ToolResult("done")

    tool = Declared()
    registry = await _registry(tool)

    async def dispatch():
        with use_operation_call(_operation(tool, {})):
            return await registry.execute(tool.name, {})

    task = asyncio.create_task(dispatch())
    try:
        await asyncio.wait_for(entered.wait(), 10)
        unrelated.write_text("external=  1\n")
    finally:
        release.set()
        result = await asyncio.wait_for(task, 10)
    assert result.success
    assert target.read_text() == "owned = 1\n"
    assert unrelated.read_text() == "external=  1\n"
    assert result.metadata["henchman.checkpoint"]["status"] == ("unavailable" if outside_project else "captured")
    if not outside_project:
        record, = CheckpointService(root).list_checkpoints()
        assert [file.path for file in CheckpointService(root).review(record.checkpoint_id).files] == ["target.py"]


@pytest.mark.parametrize("control", ["budget", "continuation"])
async def test_invalid_partial_python_does_not_replace_primary_control_failure(tmp_path, monkeypatch, control):
    from henchman.core.run_budget import BudgetExceeded
    from henchman.providers.continuation import ProviderContinuationError

    monkeypatch.chdir(tmp_path)
    error = BudgetExceeded("request_limit") if control == "budget" else ProviderContinuationError("missing")

    class PartialPython(Tool):
        name, description, kind = "partial_python", "Partial Python mutation", ToolKind.WRITE

        def checkpoint_paths(self, params):
            return ("partial.py",)

        async def execute(self, **params):
            (tmp_path / "partial.py").write_bytes(b"def broken(\n")
            raise error

    tool = PartialPython()
    registry = await _registry(tool)
    with use_operation_call(_operation(tool, {})), pytest.raises(type(error)) as observed:
        await registry.execute(tool.name, {})
    assert observed.value is error
    record, = CheckpointService(tmp_path).list_checkpoints()
    file, = CheckpointService(tmp_path).review(record.checkpoint_id).files
    assert file.after.content == b"def broken(\n" and record.state == "ready"


@pytest.mark.parametrize("secret_phase", ["before", "after"])
async def test_effective_session_credentials_make_raw_content_nonrestorable(tmp_path, monkeypatch, secret_phase):
    monkeypatch.chdir(tmp_path)
    secret = "checkpoint-credential-canary"
    before = secret if secret_phase == "before" else "ordinary before"
    after = secret if secret_phase == "after" else "ordinary after"
    (tmp_path / "file").write_text(before)
    tool = WriteFileTool()
    registry = await _registry(tool)
    params = {"path": "file", "content": after}
    operation = _operation(tool, params)
    operation.run.session.evidence_redactor.register_secret(secret)
    with use_operation_call(operation):
        result = await registry.execute(tool.name, params)
    assert result.success and (tmp_path / "file").read_text() == after
    assert result.metadata["henchman.checkpoint"]["restorable"] is False
    service = CheckpointService(tmp_path, redactor=operation.run.session.evidence_redactor)
    record, = service.list_checkpoints()
    file, = service.review(record.checkpoint_id).files
    assert not file.restorable
    payload = (service._store.path / f"{record.checkpoint_id}.json").read_text()
    assert secret not in payload and base64.b64encode(secret.encode()).decode() not in payload


async def test_declared_create_delete_and_rename_can_be_reviewed_and_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "old").write_text("original")
    (tmp_path / "removed").write_text("keep me")

    class RenameDelete(Tool):
        name, description, kind = "rename_delete", "Three exact paths", ToolKind.WRITE

        def checkpoint_paths(self, params):
            return ("old", "new", "removed")

        async def execute(self, **params):
            (tmp_path / "old").rename(tmp_path / "new")
            (tmp_path / "removed").unlink()
            return ToolResult("done")

    tool = RenameDelete()
    registry = await _registry(tool)
    with use_operation_call(_operation(tool, {})):
        result = await registry.execute(tool.name, {})
    assert result.success
    service = CheckpointService(tmp_path)
    record, = service.list_checkpoints()
    statuses = {file.path: (file.before.status, file.after.status) for file in service.review(record.checkpoint_id).files}
    assert statuses == {"old": ("text", "missing"), "new": ("missing", "text"), "removed": ("text", "missing")}
    plan = service.preview(record.checkpoint_id, decision="reject")
    service.apply(plan.plan_id)
    assert (tmp_path / "old").read_text() == "original" and (tmp_path / "removed").read_text() == "keep me"
    assert not (tmp_path / "new").exists()
