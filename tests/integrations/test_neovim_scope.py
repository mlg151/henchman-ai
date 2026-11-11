"""Editor selection is an additional dispatch denial, never approval authority."""

import asyncio
import json
import os
from types import MethodType

import pytest
from click.testing import CliRunner

from henchman.advanced.checkpoint_models import CheckpointOperation
from henchman.advanced.checkpoints import CheckpointService
from henchman.cli.commands.checkpoint import create_checkpoint_command
from henchman.config.schema import Settings
from henchman.tools.access_policy import ToolAccessPolicy
from henchman.tools.base import ToolResult
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.patch_apply import PatchApplyTool
from henchman.tools.builtins.pytest_run import PytestRunTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry
from henchman.utils.evidence_redaction import EvidenceRedactor

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Initial editor pilot uses the POSIX stdio transport")


@pytest.fixture
def selection(tmp_path, monkeypatch):
    from henchman.integrations.neovim import EditorSelection

    monkeypatch.chdir(tmp_path)
    (tmp_path / "module.py").write_text("value = 1\n")
    (tmp_path / "test_module.py").write_text("def test_value():\n    assert True\n")
    return EditorSelection(tmp_path, ("module.py", "test_module.py"))


@pytest.mark.parametrize("target", ["missing", ".", "../outside", ".git/config", "a/../module.py"])
def test_selection_refuses_non_regular_or_ambiguous_targets(tmp_path, target):
    from henchman.integrations.neovim import EditorSelection

    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/config").write_text("protected")
    with pytest.raises(ValueError, match="Editor selection"):
        EditorSelection(tmp_path, (target,))


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "parent_symlink"])
def test_selection_refuses_link_aliases(tmp_path, kind):
    from henchman.integrations.neovim import EditorSelection

    source = tmp_path / "source"
    source.mkdir()
    (source / "file").write_text("original")
    if kind == "parent_symlink":
        (tmp_path / "alias").symlink_to(source, target_is_directory=True)
        path = "alias/file"
    else:
        path = "alias"
        if kind == "symlink":
            (tmp_path / path).symlink_to(source / "file")
        else:
            os.link(source / "file", tmp_path / path)
    with pytest.raises(ValueError, match="Editor selection"):
        EditorSelection(tmp_path, (path,))


def test_selection_bounds_and_duplicate_paths(tmp_path):
    from henchman.integrations.neovim import EditorSelection

    with pytest.raises(ValueError):
        EditorSelection(tmp_path, ())
    with pytest.raises(ValueError):
        EditorSelection(tmp_path, tuple("file" for _ in range(257)))
    (tmp_path / "file").write_text("original")
    with pytest.raises(ValueError):
        EditorSelection(tmp_path, ("file", str(tmp_path / "file")))


def test_exact_builtin_targets_and_method_identity(selection):
    assert selection.guard(ReadFileTool(), {"path": "module.py"}) is None
    assert selection.guard(WriteFileTool(), {"path": "module.py", "content": "replacement"}) is None
    assert selection.guard(EditFileTool(), {"path": "module.py", "old_str": "1", "new_str": "2"}) is None
    assert selection.guard(ReadFileTool(), {"path": "test_module.py"}) is None
    assert selection.guard(WriteFileTool(), {"path": "unselected", "content": "new"}) is not None
    assert selection.guard(ShellTool(), {"command": "git commit -am changed", "background": False}) is not None
    class Impersonator(WriteFileTool):
        pass
    assert selection.guard(Impersonator(), {"path": "module.py"}) is not None
    tool = WriteFileTool()
    async def replacement(_self, **_kwargs):
        return ToolResult("unexpected")
    tool.execute = MethodType(replacement, tool)
    assert selection.guard(tool, {"path": "module.py"}) is not None


def test_patch_scope_uses_parser_even_for_dry_run(selection):
    patch = "--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n"
    assert selection.guard(PatchApplyTool(), {"patch": patch}) is None
    assert selection.guard(PatchApplyTool(), {"patch": patch, "dry_run": True}) is None
    outside = patch.replace("module.py", "other.py")
    assert selection.guard(PatchApplyTool(), {"patch": outside, "dry_run": True}) is not None
    assert selection.guard(PatchApplyTool(), {"patch": "malformed"}) is not None


@pytest.mark.parametrize("params", [
    {"path": "."}, {"path": "test_module.py", "timeout": 0},
    {"path": "test_module.py", "timeout": 301},
    {"path": "test_module.py", "coverage": True},
    {"path": "test_module.py", "parallel": 2},
])
def test_pytest_remains_bounded_explicit_project_code(selection, params):
    assert selection.guard(PytestRunTool(), params) is not None
    assert selection.guard(PytestRunTool(), {"path": "test_module.py::test_value", "timeout": 20}) is None


@pytest.mark.parametrize("change", ["symlink", "hardlink", "remove", "parent", "cwd", "revoke", "method", "policy", "worktree"])
async def test_changed_selection_after_approval_never_mutates(selection, tmp_path, change):
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    selection.bind(registry)
    entered, release = asyncio.Event(), asyncio.Event()
    async def approve(_request):
        entered.set()
        await release.wait()
        return True
    registry.set_confirmation_handler(approve)
    child = ScopedToolRegistry(registry, None)
    task = asyncio.create_task(child.execute("write_file", {"path": "module.py", "content": "bad"}))
    await asyncio.wait_for(entered.wait(), 5)
    source = tmp_path / "module.py"
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.write_text("protected")
    if change == "symlink":
        source.unlink()
        source.symlink_to(outside)
    elif change == "hardlink":
        source.unlink()
        os.link(outside, source)
    elif change == "remove":
        source.unlink()
    elif change == "parent":
        moved = tmp_path.with_name(tmp_path.name + "-moved")
        tmp_path.rename(moved)
        tmp_path.mkdir()
        (tmp_path / "module.py").write_text("new project")
    elif change == "cwd":
        os.chdir(tmp_path.parent)
    elif change == "method":
        async def replaced(_self, **_kwargs):
            outside.write_text("bad")
            return ToolResult("unexpected")
        tool = registry.get("write_file")
        tool.execute = MethodType(replaced, tool)
    elif change == "policy":
        settings = Settings()
        settings.tools.filesystem_write_roots = []
        registry.restrict_access_policy(ToolAccessPolicy.from_settings(settings.tools, project_root=tmp_path))
    elif change == "worktree":
        (tmp_path / ".git").mkdir()
    else:
        selection.close()
    release.set()
    assert not (await task).success
    assert outside.read_text() == "protected"
    if source.exists() and not source.is_symlink():
        assert source.read_text() != "bad"


async def test_selection_preserves_approvals_ancestor_guard_and_access_policy(selection, tmp_path):
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    registry.bind_execution_guard(lambda *_: ToolResult("prior denial", success=False))
    selection.bind(registry)
    registry.add_auto_approve_policy("write_file")
    assert not (await registry.execute("write_file", {"path": "module.py", "content": "bad"})).success
    assert (tmp_path / "module.py").read_text() == "value = 1\n"
    settings = Settings()
    settings.tools.filesystem_write_roots = []
    registry.restrict_access_policy(ToolAccessPolicy.from_settings(settings.tools, project_root=tmp_path))
    assert not (await registry.execute("write_file", {"path": "module.py", "content": "bad"})).success


def test_run_review_filters_canonical_operation_before_projection(tmp_path):
    path = tmp_path / "file"
    path.write_text("before\n")
    service = CheckpointService(tmp_path)
    for run in ("owned-run", "foreign-run"):
        record = service.begin(["file"], actor="worker", operation=CheckpointOperation("operation", run, "worker", "edit_file"))
        path.write_text(run + "\n")
        service.complete(record.checkpoint_id)
    policy = EvidenceRedactor()
    policy.register_secret("owned-run")
    command = create_checkpoint_command(project_root=tmp_path, redactor=policy)
    result = CliRunner().invoke(command, ["review-run", "owned-run"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["checkpoints"]) == 1
    assert payload["checkpoints"][0]["operation"]["run_id"] != "owned-run"
    assert "foreign-run" not in result.output and "owned-run" not in result.output
    assert payload["task_verified"] is False
    assert path.read_text() == "foreign-run\n"


async def test_guard_rechecks_after_formatter_wait_and_preserves_denial(selection, tmp_path, monkeypatch):
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    registry.add_auto_approve_policy("write_file")
    selection.bind(registry)
    entered, release = asyncio.Event(), asyncio.Event()
    async def format_call(_tool, _params, invoke, **_kwargs):
        entered.set()
        await release.wait()
        return await invoke()
    monkeypatch.setattr(registry._effective_formatter, "run", format_call)
    task = asyncio.create_task(registry.execute("write_file", {"path": "module.py", "content": "bad"}))
    await asyncio.wait_for(entered.wait(), 5)
    alias = tmp_path / "alias"
    os.link(tmp_path / "module.py", alias)
    release.set()
    assert not (await task).success
    assert alias.read_text() == "value = 1\n"


async def test_unchanged_selection_never_autoapproves_and_allows_existing_approval(selection, tmp_path):
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    selection.bind(registry)
    params = {"path": "module.py", "content": "value = 2\n"}
    assert not (await registry.execute("write_file", params)).success
    calls = []
    async def approve(request):
        calls.append(request.tool_name)
        return True
    registry.set_confirmation_handler(approve)
    assert (await registry.execute("write_file", params)).success
    assert calls == ["write_file"]
    assert (tmp_path / "module.py").read_text() == "value = 2\n"


def test_selection_close_preserves_newer_binding(selection):
    registry = ToolRegistry()
    selection.bind(registry)
    retained = registry._execution_guard
    def newer(*_):
        return ToolResult("new owner", success=False)
    registry.bind_execution_guard(newer)
    selection.close()
    assert registry._execution_guard is newer
    assert retained(WriteFileTool(), {"path": "module.py"}) is not None


def test_run_review_refuses_restricted_storage_before_creation(tmp_path):
    directory = tmp_path / ".henchman"
    directory.mkdir()
    (directory / "settings.yaml").write_text("tools:\n  filesystem_read_roots: []\n")
    command = create_checkpoint_command(project_root=tmp_path)
    result = CliRunner().invoke(command, ["review-run", "owned-run"])
    assert result.exit_code != 0 and "restricted tool policy" in result.output
    assert list(directory.iterdir()) == [directory / "settings.yaml"]


def test_run_review_reports_bounded_omissions_and_incomplete_capture(tmp_path):
    (tmp_path / "file").write_text("before\n")
    service = CheckpointService(tmp_path)
    operation = CheckpointOperation("operation", "owned-run", "worker", "edit_file")
    for index in range(18):
        record = service.begin(["file"], actor="worker", operation=operation)
        (tmp_path / "file").write_text(f"after {index}\n")
        if index != 0:
            service.complete(record.checkpoint_id)
    result = CliRunner().invoke(create_checkpoint_command(project_root=tmp_path), ["review-run", "owned-run"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["checkpoints"]) == 16 and payload["checkpoints_omitted"] == 2
    assert payload["checkpoints"][0]["state"] == "capturing"
    assert len(result.output.encode()) < 300000


def test_review_structural_fields_survive_credentials_and_evidence_never_becomes_identity(tmp_path):
    (tmp_path / "source").write_text("before\n")
    service = CheckpointService(tmp_path)
    record = service.begin(["source"], actor="worker", operation=CheckpointOperation("operation", "run", "files", "after"))
    (tmp_path / "source").write_text("after\n")
    service.complete(record.checkpoint_id)
    policy = EvidenceRedactor(["files", "after"])
    result = CliRunner().invoke(create_checkpoint_command(project_root=tmp_path, redactor=policy), ["review-run", "run"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    review = payload["checkpoints"][0]
    assert review["files"][0]["after"]["status"] == "secret"
    assert review["operation"]["agent_id"] == "[REDACTED]"
    assert review["operation"]["tool_name"] == "[REDACTED]"


async def test_selection_rechecks_after_owned_before_capture(selection, tmp_path, monkeypatch):
    from tests.tools.test_checkpoint_capture import _operation

    from henchman.core.runtime_operations import use_operation_call
    from henchman.tools.checkpoint_capture import MutationCheckpoint

    registry = ToolRegistry()
    tool = WriteFileTool()
    registry.register(tool)
    registry.add_auto_approve_policy(tool.name)
    selection.bind(registry)
    original = MutationCheckpoint.begin
    async def begin(capture):
        await original(capture)
        (tmp_path / "module.py").unlink()
        (tmp_path / "module.py").symlink_to(tmp_path / "test_module.py")
    monkeypatch.setattr(MutationCheckpoint, "begin", begin)
    params = {"path": "module.py", "content": "bad"}
    with use_operation_call(_operation(tool, params)):
        result = await registry.execute(tool.name, params)
    assert not result.success
    assert (tmp_path / "test_module.py").read_text() == "def test_value():\n    assert True\n"


def test_selection_rejects_replaced_nested_parent_without_changing_cwd(tmp_path, monkeypatch):
    from henchman.integrations.neovim import EditorSelection

    monkeypatch.chdir(tmp_path)
    directory = tmp_path / "nested"
    directory.mkdir()
    (directory / "source").write_text("old")
    selection = EditorSelection(tmp_path, ("nested/source",))
    directory.rename(tmp_path / "retained")
    directory.mkdir()
    (directory / "source").write_text("new")
    assert selection.guard(WriteFileTool(), {"path": "nested/source", "content": "bad"}) is not None


def test_run_review_bounds_escaped_multibyte_payload_with_visible_omissions(tmp_path):
    path = tmp_path / "source"
    path.write_text("before\n")
    service = CheckpointService(tmp_path)
    for index in range(18):
        record = service.begin(["source"], actor="worker", operation=CheckpointOperation("operation", "run", "worker", "edit_file"))
        path.write_text("🙂" * 15000 + str(index))
        service.complete(record.checkpoint_id)
    result = CliRunner().invoke(create_checkpoint_command(project_root=tmp_path), ["review-run", "run"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(result.output.encode()) <= 524289
    assert payload["checkpoints_omitted"] > 0
    assert len(payload["checkpoints"]) + payload["checkpoints_omitted"] == 18
