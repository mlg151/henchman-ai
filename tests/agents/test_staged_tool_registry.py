"""A delegated staged scope cannot dispatch live workspace mutation tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from henchman.agents.proposal_runtime import ProposalCoordinator
from henchman.agents.staged_tool_registry import StagedToolRegistry
from henchman.agents.workspace_ownership import WorkspaceBinding
from henchman.tools.access_policy import ToolAccessPolicy
from henchman.tools.base import Tool, ToolResult
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.registry import ToolRegistry


class OpaqueTool(Tool):
    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Opaque fixture"

    async def execute(self, **params: object) -> ToolResult:
        raise AssertionError("Opaque tool must never run")


async def test_staged_tools_use_owned_overlay_and_never_format_live_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "code.py"
    path.write_text("value=1\n")
    unrelated = tmp_path / "unrelated.py"
    unrelated.write_text("untouched=1\n")
    session, parent_actor, child = object(), object(), object()
    runtime = ProposalCoordinator(tmp_path, session=session, generation=0, parent=parent_actor, paths=["code.py"],
                                  current_binding=lambda: WorkspaceBinding(tmp_path, session, 0))
    handle = runtime.reserve(child, paths=["code.py"], completed=lambda: True)
    parent = ToolRegistry()
    for tool in (ReadFileTool(), WriteFileTool(), EditFileTool(), OpaqueTool()):
        parent.register(tool)
    parent.add_auto_approve_policy("write_file")
    parent.add_auto_approve_policy("edit_file")

    async def run():
        registry = StagedToolRegistry(parent, runtime.workspace(handle, child), ["read_file", "write_file", "edit_file"])
        assert registry.get("shell") is None
        written = await registry.execute("write_file", {"path": "code.py", "content": "value=2\n"})
        assert written.success
        read = await registry.execute("read_file", {"path": "code.py", "line_numbers": True})
        assert read.success and read.content == "1: value=2\n"
        edited = await registry.execute("edit_file", {"path": "code.py", "old_str": "value=2", "new_str": "value=3"})
        assert edited.success
        assert path.read_text() == "value=1\n"
        assert unrelated.read_text() == "untouched=1\n"
        assert (await registry.execute("read_file", {"path": "unrelated.py"})).success is False

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    review = runtime.review(handle)
    assert review.files[0].after.content == b"value=3\n"
    runtime.publish(handle, review)
    assert path.read_text() == "value=3\n"
    assert unrelated.read_text() == "untouched=1\n"
    await runtime.close()


async def test_staged_scope_retains_live_plan_mode_and_rejects_late_overrides(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "file").write_text("before")
    session, parent_actor, child = object(), object(), object()
    runtime = ProposalCoordinator(tmp_path, session=session, generation=0, parent=parent_actor, paths=["file"],
                                  current_binding=lambda: WorkspaceBinding(tmp_path, session, 0))
    handle = runtime.reserve(child, paths=["file"], completed=lambda: True)
    parent = ToolRegistry()
    parent.register(WriteFileTool())
    parent.add_auto_approve_policy("write_file")

    async def run():
        registry = StagedToolRegistry(parent, runtime.workspace(handle, child), ["write_file"])
        with pytest.raises(PermissionError):
            registry.register(OpaqueTool())
        parent.set_plan_mode(enabled=True)
        denied = await registry.execute("write_file", {"path": "file", "content": "after"})
        assert not denied.success and "Plan Mode" in denied.content
        parent.set_plan_mode(enabled=False)
        parent.unregister("write_file")
        assert registry.get("write_file") is None

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    runtime.discard(handle)
    assert (tmp_path / "file").read_text() == "before"
    await runtime.close()


async def test_staged_scope_obeys_confirmation_and_restricted_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "file").write_text("before")
    session, parent_actor, child = object(), object(), object()
    runtime = ProposalCoordinator(tmp_path, session=session, generation=0, parent=parent_actor, paths=["file"],
                                  current_binding=lambda: WorkspaceBinding(tmp_path, session, 0))
    handle = runtime.reserve(child, paths=["file"], completed=lambda: True)
    parent = ToolRegistry()
    parent.register(WriteFileTool())

    async def run():
        registry = StagedToolRegistry(parent, runtime.workspace(handle, child), ["write_file"])
        denied = await registry.execute("write_file", {"path": "file", "content": "after"})
        assert not denied.success and "confirmation" in str(denied.error).lower()
        parent.add_auto_approve_policy("write_file")
        parent.set_access_policy(ToolAccessPolicy.unbound())
        restricted = await registry.execute("write_file", {"path": "file", "content": "after"})
        assert not restricted.success
        parent.set_access_policy(ToolAccessPolicy())
        parent.unregister("write_file")
        parent.register(WriteFileTool())
        assert registry.get("write_file") is None

    worker = asyncio.create_task(run())
    runtime.bind(handle, worker)
    await worker
    review = runtime.review(handle)
    assert review.files[0].after.content == b"before"
    assert not review.files[0].hunks
    runtime.discard(handle)
    assert (tmp_path / "file").read_text() == "before"
    await runtime.close()
