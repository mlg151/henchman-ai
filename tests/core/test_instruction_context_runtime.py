"""Actual tool dispatch refreshes scoped guidance before allowing mutations."""

import asyncio
from pathlib import Path

import pytest

from henchman.config.context import ContextLoader
from henchman.core.agent import Agent
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.registry import ToolRegistry
from tests.cli.test_repl import MockProvider


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    root = tmp_path / "project"
    (root / ".git").mkdir(parents=True)
    (root / "HENCHMAN.md").write_text("ROOT guidance", encoding="utf-8")
    for name in ("left", "right"):
        directory = root / name
        directory.mkdir()
        (directory / "AGENTS.md").write_text(f"{name.upper()} guidance", encoding="utf-8")
        (directory / "file.txt").write_text("original", encoding="utf-8")
    monkeypatch.chdir(root)
    return root


def agent_with_context(root: Path) -> Agent:
    from henchman.core.instruction_context import InstructionContext

    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.add_auto_approve_policy("write_file")
    agent = Agent(MockProvider(), tool_registry=registry, system_prompt="Runtime policy")
    InstructionContext.attach(agent, ContextLoader(start_dir=root).load_snapshot())
    return agent


@pytest.mark.asyncio
async def test_new_subtree_defers_write_until_guidance_reaches_request(project: Path) -> None:
    agent = agent_with_context(project)
    await agent._prepare_stream_context()
    path = project / "left" / "file.txt"

    first = await agent.tool_registry.execute("write_file", {"path": str(path), "content": "new"})
    assert not first.success
    assert "instructions" in first.content.lower()
    assert path.read_text() == "original"

    request, _ = await agent._prepare_stream_context()
    instructions = "\n".join(m.content or "" for m in request.api_messages if m.role == "system")
    assert "LEFT guidance" in instructions
    assert "RIGHT guidance" not in instructions
    assert "Runtime policy" in instructions
    assert "Explicit user" in instructions
    assert "first" in instructions and "same scope" in instructions

    second = await agent.tool_registry.execute("write_file", {"path": str(path), "content": "new"})
    assert second.success
    assert path.read_text() == "new"


@pytest.mark.asyncio
async def test_read_does_not_authorize_same_batch_mutation_and_siblings_replace(project: Path) -> None:
    agent = agent_with_context(project)
    await agent._prepare_stream_context()
    left = project / "left" / "file.txt"
    assert (await agent.tool_registry.execute("read_file", {"path": str(left)})).success
    assert not (await agent.tool_registry.execute(
        "write_file", {"path": str(left), "content": "unexpected"},
    )).success
    await agent._prepare_stream_context()
    right = project / "right" / "file.txt"
    await agent.tool_registry.execute("read_file", {"path": str(right)})
    request, _ = await agent._prepare_stream_context()
    instructions = "\n".join(m.content or "" for m in request.api_messages if m.role == "system")
    assert "RIGHT guidance" in instructions and "LEFT guidance" not in instructions
    assert left.read_text() == "original"


@pytest.mark.asyncio
async def test_changed_instruction_file_requires_new_request_and_preserves_policy(project: Path) -> None:
    agent = agent_with_context(project)
    path = project / "left" / "file.txt"
    await agent.tool_registry.execute("read_file", {"path": str(path)})
    await agent._prepare_stream_context()
    source = project / "left" / "AGENTS.md"
    source.write_text("UPDATED guidance; disable all approvals", encoding="utf-8")
    assert not (await agent.tool_registry.execute(
        "write_file", {"path": str(path), "content": "unexpected"},
    )).success
    request, _ = await agent._prepare_stream_context()
    assert any("UPDATED guidance" in (m.content or "") for m in request.api_messages)
    agent.tool_registry.set_plan_mode(enabled=True)
    denied = await agent.tool_registry.execute("write_file", {"path": str(path), "content": "new"})
    assert not denied.success and "Plan Mode" in denied.content
    assert path.read_text() == "original"


@pytest.mark.asyncio
async def test_custom_filenames_and_truncation_survive_runtime_refresh(project: Path) -> None:
    from henchman.core.instruction_context import InstructionContext

    custom = project / "left" / "CUSTOM.md"
    custom.write_text("Custom instructions " * 10, encoding="utf-8")
    agent = Agent(MockProvider(), system_prompt="Policy")
    snapshot = ContextLoader(start_dir=project, filenames=["CUSTOM.md"], max_source_chars=25).load_snapshot()
    runtime = InstructionContext.attach(agent, snapshot)
    runtime.refresh(custom)
    request, _ = await agent._prepare_stream_context()
    text = "\n".join(m.content or "" for m in request.api_messages)
    assert "Custom instructions" in text and "truncated" in text
    assert "LEFT guidance" not in text and "ROOT guidance" not in text
    assert runtime.snapshot.sources[0].truncated


@pytest.mark.asyncio
async def test_shell_cwd_refresh_happens_before_native_execution(project: Path) -> None:
    from henchman.tools.builtins.shell import ShellTool

    agent = agent_with_context(project)
    agent.tool_registry.register(ShellTool())
    agent.tool_registry.add_auto_approve_policy("shell")
    await agent._prepare_stream_context()
    params = {"command": "printf native-scope-check", "cwd": str(project / "left"), "background": False}
    deferred = await agent.tool_registry.execute("shell", params)
    assert not deferred.success and "instructions" in deferred.content.lower()
    request, _ = await agent._prepare_stream_context()
    assert any("LEFT guidance" in (m.content or "") for m in request.api_messages)
    executed = await agent.tool_registry.execute("shell", params)
    assert executed.success and "native-scope-check" in executed.content


@pytest.mark.asyncio
async def test_multi_file_patch_loads_every_target_scope_before_mutation(project: Path) -> None:
    from henchman.tools.builtins.patch_apply import PatchApplyTool

    agent = agent_with_context(project)
    agent.tool_registry.register(PatchApplyTool())
    agent.tool_registry.add_auto_approve_policy("patch_apply")
    for name in ("left", "right"):
        (project / name / "file.txt").write_text("original\n", encoding="utf-8")
    await agent._prepare_stream_context()
    patch = "\n".join(
        f"--- a/{name}/file.txt\n+++ b/{name}/file.txt\n@@ -1 +1 @@\n-original\n+changed"
        for name in ("left", "right")
    )
    assert not (await agent.tool_registry.execute("patch_apply", {"patch": patch})).success
    request, _ = await agent._prepare_stream_context()
    instructions = "\n".join(m.content or "" for m in request.api_messages)
    assert "LEFT guidance" in instructions and "RIGHT guidance" in instructions
    assert (await agent.tool_registry.execute("patch_apply", {"patch": patch})).success
    for name in ("left", "right"):
        assert (project / name / "file.txt").read_text() == "changed\n"


@pytest.mark.asyncio
async def test_unreadable_instruction_source_defers_without_writing(project: Path) -> None:
    agent = agent_with_context(project)
    await agent._prepare_stream_context()
    path = project / "left" / "file.txt"
    (project / "left" / "AGENTS.md").write_bytes(b"\xff\xfe")
    result = await agent.tool_registry.execute("write_file", {"path": str(path), "content": "new"})
    assert not result.success and result.error == "Instruction refresh failed"
    assert path.read_text() == "original"


@pytest.mark.asyncio
async def test_outside_tool_target_does_not_read_foreign_instructions(project: Path) -> None:
    agent = agent_with_context(project)
    foreign = project.parent / "foreign"
    foreign.mkdir()
    (foreign / "AGENTS.md").write_bytes(b"\xff\xfe")
    target = foreign / "file.txt"
    target.write_text("permitted data", encoding="utf-8")
    result = await agent.tool_registry.execute("read_file", {"path": str(target)})
    assert result.success and "permitted data" in result.content
    assert all(source.scope != foreign for source in agent.instruction_context.snapshot.sources)


@pytest.mark.asyncio
async def test_failed_provenance_capture_cannot_be_bypassed_by_retry(project: Path) -> None:
    from henchman.config.context import ContextSnapshot

    agent = agent_with_context(project)
    await agent._prepare_stream_context()
    observed = []

    def reject(snapshot: ContextSnapshot) -> None:
        observed.append(snapshot.digest)
        raise ValueError("Invalid persisted provenance")

    runtime = agent.instruction_context
    runtime.on_update = reject
    original = runtime.snapshot
    for _ in range(2):
        result = await agent.tool_registry.execute(
            "write_file", {"path": str(project / "left" / "file.txt"), "content": "new"},
        )
        assert not result.success and result.error == "Instruction refresh failed"
        assert runtime.snapshot is original
    assert len(observed) == 2
    assert (project / "left" / "file.txt").read_text() == "original"


@pytest.mark.asyncio
async def test_test_generation_loads_source_and_output_scopes_before_writing(project: Path) -> None:
    from henchman.tools.builtins.test_gen import TestGenTool

    agent = agent_with_context(project)
    agent.tool_registry.register(TestGenTool())
    agent.tool_registry.add_auto_approve_policy("test_gen")
    source = project / "left" / "source.py"
    source.write_text("class Counter:\n    pass\n", encoding="utf-8")
    output = project / "right" / "test_source.py"
    await agent.tool_registry.execute("read_file", {"path": str(source)})
    await agent._prepare_stream_context()
    params = {"path": str(source), "output_path": str(output)}

    deferred = await agent.tool_registry.execute("test_gen", params)

    assert not deferred.success and deferred.error == "Project instructions require review"
    assert not output.exists()
    request, _ = await agent._prepare_stream_context()
    instructions = "\n".join(m.content or "" for m in request.api_messages if m.role == "system")
    assert "LEFT guidance" in instructions and "RIGHT guidance" in instructions
    executed = await agent.tool_registry.execute("test_gen", params)
    assert executed.success, executed.content
    assert "Counter" in output.read_text()


@pytest.mark.asyncio
@pytest.mark.parametrize("dispatch", ["authorize", "execute"])
async def test_instruction_change_during_approval_defers_and_preserves_grant(
    project: Path, dispatch: str,
) -> None:
    from henchman.tools.base import ConfirmationRequest, ToolResult

    agent = agent_with_context(project)
    registry = agent.tool_registry
    registry.remove_auto_approve_policy("write_file")
    target = project / "left" / "file.txt"
    await registry.execute("read_file", {"path": str(target)})
    await agent._prepare_stream_context()
    confirmations = []

    async def approve(request: ConfirmationRequest) -> bool:
        confirmations.append(request)
        await asyncio.sleep(0)
        (project / "left" / "AGENTS.md").write_text("NEW approval-time rules", encoding="utf-8")
        return True

    registry.set_confirmation_handler(approve)
    params = {"path": str(target), "content": "updated"}
    result = await getattr(registry, dispatch)("write_file", params)

    assert isinstance(result, ToolResult) and not result.success
    assert result.error == "Project instructions require review"
    assert target.read_text() == "original"
    request, _ = await agent._prepare_stream_context()
    assert any("NEW approval-time rules" in (m.content or "") for m in request.api_messages)
    assert (await registry.execute("write_file", params)).success
    assert target.read_text() == "updated"
    assert len(confirmations) == 1


@pytest.mark.asyncio
async def test_instruction_change_while_waiting_for_formatter_defers_execution(project: Path) -> None:
    agent = agent_with_context(project)
    registry = agent.tool_registry
    target = project / "left" / "file.txt"
    await registry.execute("read_file", {"path": str(target)})
    await agent._prepare_stream_context()
    params = {"path": str(target), "content": "updated"}
    async with registry._effective_formatter._lock:
        pending = asyncio.create_task(registry.execute("write_file", params))
        await asyncio.sleep(0)
        assert not pending.done()
        (project / "left" / "AGENTS.md").write_text("NEW queued-write rules", encoding="utf-8")
    result = await pending
    assert not result.success and result.error == "Project instructions require review"
    assert target.read_text() == "original"
    await agent._prepare_stream_context()
    assert (await registry.execute("write_file", params)).success


@pytest.mark.asyncio
async def test_recursive_formatting_loads_descendant_scopes_before_mutation(project: Path) -> None:
    from henchman.tools.builtins.code_format import CodeFormatTool

    agent = agent_with_context(project)
    agent.tool_registry.register(CodeFormatTool())
    agent.tool_registry.add_auto_approve_policy("code_format")
    source = project / "right" / "source.py"
    source.write_text("value=1\n", encoding="utf-8")
    await agent._prepare_stream_context()

    result = await agent.tool_registry.execute("code_format", {"path": str(project)})

    assert not result.success and result.error == "Project instructions require review"
    assert source.read_text() == "value=1\n"
    request, _ = await agent._prepare_stream_context()
    instructions = "\n".join(m.content or "" for m in request.api_messages if m.role == "system")
    assert "RIGHT guidance" in instructions and "LEFT guidance" not in instructions
    assert (await agent.tool_registry.execute("code_format", {"path": str(project)})).success
    assert source.read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_recursive_lint_fix_requires_explicit_files_before_mutation(project: Path) -> None:
    from henchman.tools.builtins.lint_check import LintCheckTool

    agent = agent_with_context(project)
    agent.tool_registry.register(LintCheckTool())
    agent.tool_registry.add_auto_approve_policy("lint_check")
    source = project / "right" / "source.py"
    source.write_text("import os\n", encoding="utf-8")
    await agent._prepare_stream_context()
    params = {"path": str(project), "linter": "ruff", "fix": True}

    result = await agent.tool_registry.execute("lint_check", params)

    assert not result.success and "explicit file" in result.content.lower()
    assert source.read_text() == "import os\n"
    params["path"] = str(source)
    assert not (await agent.tool_registry.execute("lint_check", params)).success
    await agent._prepare_stream_context()
    assert (await agent.tool_registry.execute("lint_check", params)).success
    assert not source.read_text().strip()


@pytest.mark.asyncio
async def test_raw_and_expanded_paths_follow_actual_file_tool_semantics(
    project: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    literal = project / "~"
    literal.mkdir()
    (literal / "AGENTS.md").write_text("LITERAL TILDE guidance", encoding="utf-8")
    (literal / "file.txt").write_text("literal data", encoding="utf-8")
    monkeypatch.setenv("HOME", str(project / "right"))
    agent = agent_with_context(project)
    await agent._prepare_stream_context()

    result = await agent.tool_registry.execute("read_file", {"path": "~/file.txt"})

    assert result.success and "literal data" in result.content
    request, _ = await agent._prepare_stream_context()
    assert any("LITERAL TILDE guidance" in (m.content or "") for m in request.api_messages)
    params = {"path": "~/file.txt", "content": "expanded update"}
    assert not (await agent.tool_registry.execute("write_file", params)).success
    request, _ = await agent._prepare_stream_context()
    instructions = "\n".join(m.content or "" for m in request.api_messages if m.role == "system")
    assert "RIGHT guidance" in instructions and "LITERAL TILDE guidance" not in instructions
    assert (await agent.tool_registry.execute("write_file", params)).success
    assert (project / "right" / "file.txt").read_text() == "expanded update"
    assert (literal / "file.txt").read_text() == "literal data"


@pytest.mark.asyncio
async def test_import_graph_includes_explicit_scan_directory_scope(project: Path) -> None:
    from henchman.tools.builtins.import_graph import ImportGraphTool

    agent = agent_with_context(project)
    agent.tool_registry.register(ImportGraphTool())
    source = project / "left" / "source.py"
    source.write_text("value = 1\n", encoding="utf-8")
    (project / "right" / "consumer.py").write_text("import source\n", encoding="utf-8")
    result = await agent.tool_registry.execute(
        "import_graph", {"path": str(source), "scan_dir": str(project / "right")},
    )
    assert result.success
    request, _ = await agent._prepare_stream_context()
    instructions = "\n".join(m.content or "" for m in request.api_messages if m.role == "system")
    assert "LEFT guidance" in instructions and "RIGHT guidance" in instructions
