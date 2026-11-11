"""Real filesystem and fail-closed dispatch tests for restricted tool policies."""

import os
from unittest.mock import AsyncMock

import pytest

from henchman.cli.tool_manager import ToolManager
from henchman.config.schema import Settings
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.builtins.web_fetch import WebFetchTool
from henchman.tools.scoped_registry import ScopedToolRegistry


def restricted_registry(tmp_path, **settings):
    manager = ToolManager(Settings(tools=settings))
    manager.bind_runtime(project_root=tmp_path)
    for tool in (ReadFileTool(), WriteFileTool(), ShellTool(), PythonExecTool(), WebFetchTool()):
        manager.registry.register(tool)
        manager.registry.add_auto_approve_policy(tool.name)
    return manager.registry


@pytest.mark.parametrize("setting", [
    {"filesystem_read_roots": []}, {"filesystem_write_roots": []}, {"network_access": "disabled"},
    {"network_allowed_hosts": ["example.com"]},
])
@pytest.mark.parametrize("name,params", [
    ("shell", {"command": "echo harmless", "background": False}),
    ("python_exec", {"code": "print(1+2)", "background": False}),
    ("web_fetch", {"url": "https://example.com"}),
])
async def test_any_restriction_denies_unmediated_tools(tmp_path, monkeypatch, setting, name, params):
    registry = restricted_registry(tmp_path, **setting)
    dispatch = AsyncMock(return_value=ToolResult(content="bypassed"))
    monkeypatch.setattr(registry.get(name), "execute", dispatch)
    result = await registry.execute(name, params)
    assert not result.success
    assert "restricted" in result.content.lower()
    dispatch.assert_not_awaited()


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory handles required")
async def test_allowed_read_and_write_use_separate_roots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    readable = tmp_path / "readable"
    writable = tmp_path / "writable"
    readable.mkdir()
    writable.mkdir()
    (readable / "data").write_text("first\nsecond\n")
    registry = restricted_registry(tmp_path, filesystem_read_roots=["readable"],
                                   filesystem_write_roots=["writable"], network_access="disabled")
    result = await registry.execute("read_file", {
        "path": "readable/data", "start_line": 2, "end_line": 2, "line_numbers": True,
    })
    assert result.success, result.content
    assert result.content == "2: second\n"
    result = await registry.execute("write_file", {"path": "writable/new/data", "content": "saved"})
    assert result.success, result.content
    assert (writable / "new/data").read_text() == "saved"
    assert not (await registry.execute("read_file", {"path": "writable/new/data"})).success
    assert not (await registry.execute("write_file", {"path": "readable/data", "content": "changed"})).success
    assert (readable / "data").read_text() == "first\nsecond\n"


@pytest.mark.parametrize("operation", ["read_file", "write_file"])
@pytest.mark.skipif(os.name == "nt", reason="symlink creation is platform-dependent")
async def test_symlink_escape_denied_before_content_or_mutation(tmp_path, operation):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("private outside")
    (workspace / "link").symlink_to(outside)
    registry = restricted_registry(workspace, filesystem_read_roots=["."], filesystem_write_roots=["."])
    result = await registry.execute(operation, {"path": str(workspace / "link"), "content": "overwrite"})
    assert not result.success
    assert "private outside" not in result.content
    assert outside.read_text() == "private outside"


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory handles required")
async def test_policy_inheritance_cannot_be_widened_and_late_tools_deny(tmp_path):
    from henchman.tools.access_policy import ToolAccessPolicy

    registry = restricted_registry(tmp_path, filesystem_read_roots=["."], filesystem_write_roots=[])
    child = ScopedToolRegistry(registry, None, inherit_auto_approve=True)
    child.set_access_policy(ToolAccessPolicy.from_settings(Settings().tools, project_root=tmp_path))
    late = ShellTool()
    registry.unregister("shell")
    registry.register(late)
    assert not (await child.execute("shell", {"command": "echo no"})).success
    assert not (await child.execute("write_file", {"path": str(tmp_path / "new"), "content": "no"})).success
    (tmp_path / "data").write_text("allowed")
    assert (await child.execute("read_file", {"path": str(tmp_path / "data")})).success


class Impostor(Tool):
    name = "read_file"
    description = "Claims a trusted name"
    kind = ToolKind.READ

    async def execute(self, **params):
        raise AssertionError("Unqualified implementation dispatched")


async def test_names_and_declared_read_effect_do_not_grant_mediation(tmp_path):
    registry = restricted_registry(tmp_path, network_access="disabled")
    registry.unregister("read_file")
    registry.register(Impostor())
    result = await registry.execute("read_file", {})
    assert not result.success
    assert "unsupported" in result.content.lower()


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory handles required")
async def test_restricted_python_write_never_runs_automatic_formatter(tmp_path, monkeypatch):
    registry = restricted_registry(tmp_path, filesystem_write_roots=["."])
    formatter = AsyncMock(side_effect=AssertionError("Unmediated formatter launched"))
    monkeypatch.setattr(registry._formatter, "run", formatter)
    result = await registry.execute("write_file", {"path": str(tmp_path / "source.py"), "content": "x=1\n"})
    assert result.success, result.content
    assert (tmp_path / "source.py").read_text() == "x=1\n"
    formatter.assert_not_awaited()


async def test_replaced_project_root_requires_explicit_policy_rebinding(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    registry = restricted_registry(workspace, filesystem_read_roots=["."])
    workspace.rename(tmp_path / "old")
    workspace.mkdir()
    (workspace / "data").write_text("different project")
    result = await registry.execute("read_file", {"path": str(workspace / "data")})
    assert not result.success
    assert "different project" not in result.content


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory handles required")
async def test_hardlinked_file_cannot_mutate_an_outside_alias(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("keep")
    os.link(outside, workspace / "alias")
    registry = restricted_registry(workspace, filesystem_write_roots=["."])
    result = await registry.execute("write_file", {"path": str(workspace / "alias"), "content": "changed"})
    assert not result.success
    assert outside.read_text() == "keep"


@pytest.mark.parametrize("operation", ["read_file", "write_file"])
@pytest.mark.parametrize("component", ["directory", "file"])
@pytest.mark.skipif(os.name == "nt", reason="POSIX directory handles required")
async def test_symlink_inserted_at_actual_open_cannot_escape(tmp_path, monkeypatch, operation, component):
    from henchman.tools import access_policy

    workspace = tmp_path / "workspace"
    directory = workspace / "inside"
    directory.mkdir(parents=True)
    (directory / "data").write_text("inside data")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "data").write_text("outside canary")
    registry = restricted_registry(workspace, filesystem_read_roots=["."], filesystem_write_roots=["."])
    original_open = os.open
    changed = False

    def raced_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal changed
        trigger = "inside" if component == "directory" else "data"
        if path == trigger and dir_fd is not None and not changed:
            changed = True
            if component == "directory":
                directory.rename(workspace / "previous")
                directory.symlink_to(outside, target_is_directory=True)
            else:
                (directory / "data").unlink()
                (directory / "data").symlink_to(outside / "data")
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(access_policy.os, "open", raced_open)
    result = await registry.execute(operation, {"path": str(directory / "data"), "content": "overwrite"})
    assert changed
    assert not result.success
    assert "outside canary" not in result.content
    assert (outside / "data").read_text() == "outside canary"


async def test_platform_without_directory_primitives_explicitly_denies(tmp_path, monkeypatch):
    from henchman.tools import access_policy

    registry = restricted_registry(tmp_path, filesystem_read_roots=["."])
    (tmp_path / "data").write_text("private")
    monkeypatch.setattr(access_policy, "_SAFE_DIRECTORY_OPS", False)
    result = await registry.execute("read_file", {"path": str(tmp_path / "data")})
    assert not result.success
    assert "unsupported on this platform" in result.content
    assert "private" not in result.content


async def test_worktree_pointer_change_invalidates_bound_project(tmp_path):
    (tmp_path / ".git").write_text("gitdir: /repo/first\n")
    (tmp_path / "data").write_text("private")
    registry = restricted_registry(tmp_path, filesystem_read_roots=["."])
    (tmp_path / ".git").write_text("gitdir: /repo/second\n")
    result = await registry.execute("read_file", {"path": str(tmp_path / "data")})
    assert not result.success
    assert "private" not in result.content


@pytest.mark.parametrize("trusted", [False, True])
async def test_late_mcp_registration_cannot_bypass_parent_policy(tmp_path, trusted):
    from tests.tools.test_plan_mode_operation_effects import _make_mcp_tool

    registry = restricted_registry(tmp_path, network_access="disabled")
    child = ScopedToolRegistry(registry, None, inherit_auto_approve=True)
    tool = _make_mcp_tool(trusted=trusted)
    dispatch = AsyncMock(return_value=ToolResult(content="bypass"))
    tool.execute = dispatch
    registry.register(tool)
    registry.add_auto_approve_policy(tool.name)
    result = await child.execute(tool.name, {})
    assert not result.success
    dispatch.assert_not_awaited()


async def test_policy_tightened_during_approval_prevents_dispatch(tmp_path):
    from henchman.tools.access_policy import ToolAccessPolicy

    registry = restricted_registry(tmp_path, filesystem_write_roots=["."])
    registry.remove_auto_approve_policy("write_file")

    async def approve(_request):
        registry.set_access_policy(ToolAccessPolicy.from_settings(
            Settings(tools={"filesystem_write_roots": []}).tools, project_root=tmp_path,
        ))
        return True

    registry.set_confirmation_handler(approve)
    result = await registry.execute("write_file", {"path": str(tmp_path / "new"), "content": "denied"})
    assert not result.success
    assert not (tmp_path / "new").exists()


async def test_unbound_manager_does_not_temporarily_allow_restricted_execution():
    manager = ToolManager(Settings(tools={"network_access": "disabled"}))
    manager.registry.register(ShellTool())
    result = await manager.registry.execute("shell", {"command": "echo no", "network_access": "unrestricted"})
    assert not result.success


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory handles required")
async def test_instance_override_cannot_reuse_mediated_class_identity(tmp_path, monkeypatch):
    registry = restricted_registry(tmp_path, filesystem_read_roots=["."])
    dispatch = AsyncMock(return_value=ToolResult(content="unmediated"))
    monkeypatch.setattr(registry.get("read_file"), "execute", dispatch)
    result = await registry.execute("read_file", {"path": str(tmp_path / "data")})
    assert not result.success
    dispatch.assert_not_awaited()


async def test_local_network_policy_cannot_widen_restricted_parent(tmp_path):
    from henchman.tools.access_policy import ToolAccessPolicy

    registry = restricted_registry(tmp_path, network_access="disabled")
    child = ScopedToolRegistry(registry, None, inherit_auto_approve=True)
    child.set_access_policy(ToolAccessPolicy.from_settings(Settings().tools, project_root=tmp_path))
    result = await child.execute("web_fetch", {
        "url": "https://example.com", "network_access": "unrestricted", "trusted": True,
    })
    assert not result.success


@pytest.mark.skipif(os.name == "nt", reason="POSIX directory handles required")
async def test_mutated_settings_do_not_rebind_an_active_restricted_policy(tmp_path):
    settings = Settings(tools={"filesystem_read_roots": ["."], "filesystem_write_roots": []})
    manager = ToolManager(settings)
    manager.bind_runtime(project_root=tmp_path)
    manager.registry.register(WriteFileTool())
    manager.registry.add_auto_approve_policy("write_file")
    settings.tools.filesystem_write_roots = None
    result = await manager.registry.execute("write_file", {"path": str(tmp_path / "new"), "content": "no"})
    assert not result.success
    assert not (tmp_path / "new").exists()


async def test_direct_orchestrator_binds_settings_to_existing_and_future_scopes(tmp_path, monkeypatch):
    from henchman.agents.orchestrator import Orchestrator
    from tests.agents.test_agent_budget_scope import AccountingProvider

    monkeypatch.chdir(tmp_path)
    orchestrator = Orchestrator(AccountingProvider(), settings=Settings(tools={"network_access": "disabled"}))
    orchestrator.tool_registry.register(ShellTool())
    orchestrator.tool_registry.add_auto_approve_policy("shell")
    result = await orchestrator.tech_lead.tool_registry.execute("shell", {"command": "echo no"})
    assert not result.success


async def test_orchestrator_settings_cannot_widen_supplied_registry_policy(tmp_path, monkeypatch):
    from henchman.agents.orchestrator import Orchestrator
    from tests.agents.test_agent_budget_scope import AccountingProvider

    monkeypatch.chdir(tmp_path)
    supplied = restricted_registry(tmp_path, filesystem_write_roots=[])
    orchestrator = Orchestrator(AccountingProvider(), tool_registry=supplied,
                                settings=Settings(tools={"network_access": "disabled"}))
    assert orchestrator.tool_registry is supplied
    result = await orchestrator.tech_lead.tool_registry.execute("write_file", {
        "path": str(tmp_path / "new"), "content": "no",
    })
    assert not result.success
    assert not (tmp_path / "new").exists()
