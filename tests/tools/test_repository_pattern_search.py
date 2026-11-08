"""Fresh repository evidence through the existing pattern-search tool."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from henchman.tools.builtins.pattern_search import PatternSearchTool


def git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.name", "Offline Fixture")
    git(root, "config", "user.email", "offline@example.invalid")
    files = {
        "AGENTS.md": "Root convention: reuse existing functions.\n",
        "src/pkg/AGENTS.md": "Package convention: preserve label ordering.\n",
        "src/other/AGENTS.md": "unrelated-sibling-instruction-canary\n",
        "src/pkg/__init__.py": "",
        "src/pkg/normalization.py": (
            "def normalize_label(value: str) -> str:\n"
            '    """Canonical labels use casefold and normalized whitespace."""\n'
            '    return "-".join(value.casefold().split())\n'
        ),
        "src/pkg/index.py": (
            "from .normalization import normalize_label as canonical\n\n"
            "def unique_labels(values):\n"
            "    return list(dict.fromkeys(canonical(value) for value in values))\n"
        ),
        "tests/test_labels.py": (
            "from pkg.normalization import normalize_label\n\n"
            "def test_normalization():\n"
            '    assert normalize_label("Straße") == "strasse"\n'
        ),
        "src/other/distractor.py": "def unrelated():\n    return 'no relation'\n",
        ".gitignore": "ignored/\n",
    }
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "repository fixture")
    (root / "ignored").mkdir()
    (root / "ignored/private.py").write_text(
        'def normalize_label(value):\n    return "ignored-private-source-canary"\n',
    )
    return root


def tool(root: Path) -> PatternSearchTool:
    return PatternSearchTool(project_root=root)


async def search(root: Path, **kwargs):
    return await tool(root).execute(
        description="canonical labels",
        strategy="repository",
        **kwargs,
    )


async def test_pack_finds_existing_implementation_tests_references_and_scoped_rules(repository):
    result = await search(repository)
    assert result.success, result.content
    assert result.structured_content_present
    report = result.structured_content
    assert json.loads(result.content) == report
    assert report["kind"] == "repository_evidence"
    assert report["task_verified"] is False
    implementation = next(
        item for item in report["implementations"] if item["symbol"] == "normalize_label"
    )
    source = repository / "src/pkg/normalization.py"
    assert implementation["path"] == "src/pkg/normalization.py"
    assert implementation["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert implementation["content"] == source.read_text()
    assert implementation["start_line"] == 1 and implementation["end_line"] == 3
    assert implementation["current_revision"] == git(repository, "rev-parse", "HEAD")
    assert implementation["retrieval_reasons"]
    assert any(item["path"] == "tests/test_labels.py" for item in report["tests"])
    assert any(item["path"] == "src/pkg/index.py" for item in report["references"])
    instructions = report["instructions"]
    assert [item["path"] for item in instructions] == ["AGENTS.md", "src/pkg/AGENTS.md"]
    assert instructions[1]["scope"] == "src/pkg"
    assert all("tracked" not in item for item in instructions)
    assert implementation["id"] in instructions[1]["applies_to"]
    assert "unrelated-sibling-instruction-canary" not in result.content
    assert "ignored-private-source-canary" not in result.content


async def test_repository_mode_requires_trusted_binding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = await PatternSearchTool().execute(description="helper", strategy="repository")
    assert not result.success and "bound" in result.error


async def test_tool_manager_existing_binding_hook_activates_repository_mode(repository):
    from henchman.cli.tool_manager import ToolManager

    manager = ToolManager()
    manager.bind_runtime(project_root=repository)
    manager.register_builtin_tools()
    result = await manager.registry.execute(
        "pattern_search",
        {"description": "canonical labels", "strategy": "repository"},
    )
    assert result.success, result.content
    assert "normalize_label" in result.content


async def test_current_writes_and_untracked_sources_need_no_index(repository):
    source = repository / "src/pkg/normalization.py"
    source.write_text('def changed_label():\n    """Canonical labels changed."""\n    return 99\n')
    fresh = repository / "new_labels.py"
    fresh.write_text('def new_label():\n    """Canonical labels newly created."""\n    return 1\n')
    result = await search(repository)
    assert result.success, result.content
    items = result.structured_content["implementations"]
    assert any(item["symbol"] == "changed_label" for item in items)
    item = next(item for item in items if item["symbol"] == "new_label")
    assert item["tracked"] is False
    assert item["source_sha256"] == hashlib.sha256(fresh.read_bytes()).hexdigest()
    assert "def normalize_label" not in result.content


async def test_parse_error_is_visible_partial_not_a_successful_empty_search(repository):
    (repository / "broken.py").write_text("def broken(\n")
    result = await search(repository)
    assert not result.success
    report = result.structured_content
    assert report["complete"] is False
    assert report["implementations"]
    assert any(item["code"] == "python_parse_error" for item in report["diagnostics"])


@pytest.mark.parametrize("top_k", [0, -1, 21, True, 1.5, "2"])
async def test_repository_bounds_reject_before_source_access(repository, top_k, monkeypatch):
    from henchman.analysis import repository_search

    def forbidden(*_args, **_kwargs):
        pytest.fail("invalid request read source")

    monkeypatch.setattr(repository_search, "search_repository", forbidden)
    result = await tool(repository).execute(
        description="labels",
        strategy="repository",
        top_k=top_k,
    )
    assert not result.success


async def test_cross_workspace_path_is_rejected_without_reading(repository, tmp_path):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "secret.py").write_text("cross-workspace-private-canary")
    result = await search(repository, path=str(foreign))
    assert not result.success
    assert "cross-workspace-private-canary" not in result.content


async def test_existing_restricted_policy_refuses_before_repository_work(repository, monkeypatch):
    from henchman.analysis import repository_search
    from henchman.config.schema import ToolSettings
    from henchman.tools.access_policy import ToolAccessPolicy
    from henchman.tools.registry import ToolRegistry

    def forbidden(*_args, **_kwargs):
        pytest.fail("restricted search performed repository work")

    monkeypatch.setattr(repository_search, "search_repository", forbidden)
    registry = ToolRegistry()
    registry.register(tool(repository))
    registry.set_access_policy(
        ToolAccessPolicy.from_settings(
            ToolSettings(filesystem_read_roots=[]),
            project_root=repository,
        )
    )
    result = await registry.execute(
        "pattern_search",
        {
            "description": "canonical labels",
            "strategy": "repository",
        },
    )
    assert not result.success


@pytest.mark.parametrize("change", ["source", "revision", "membership", "instruction"])
async def test_publication_rejects_changed_observation(repository, monkeypatch, change):
    from henchman.analysis import repository_search

    original = repository_search.bounded_result

    def mutate(pack):
        result = original(pack)
        if change == "source":
            (repository / "src/pkg/normalization.py").write_text(
                "def replacement():\n    return 0\n"
            )
        elif change == "revision":
            git(repository, "commit", "--allow-empty", "-m", "new revision")
        elif change == "membership":
            (repository / "new.py").write_text("def canonical_labels():\n    return 0\n")
        else:
            (repository / "HENCHMAN.md").write_text("new guidance")
        return result

    monkeypatch.setattr(repository_search, "bounded_result", mutate)
    result = await search(repository)
    assert not result.success
    assert result.structured_content["status"] == "unavailable"
    assert not result.structured_content["implementations"]
    assert "casefold" not in result.content


@pytest.mark.parametrize("change", ["policy", "registration", "guard", "binding"])
async def test_late_registry_authority_change_discards_evidence(repository, monkeypatch, change):
    from henchman.analysis import repository_sources
    from henchman.tools.access_policy import ToolAccessPolicy
    from henchman.tools.base import ToolResult
    from henchman.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registered = tool(repository)
    registry.register(registered)
    original = repository_sources.run_bounded_subprocess
    changed = False

    async def wait_then_change(*args, **kwargs):
        nonlocal changed
        result = await original(*args, **kwargs)
        if not changed:
            changed = True
            if change == "policy":
                registry.restrict_access_policy(ToolAccessPolicy(read_roots=()))
            elif change == "registration":
                registry.unregister("pattern_search")
                registry.register(tool(repository))
            elif change == "guard":
                registry.bind_execution_guard(lambda *_: ToolResult(content="held", success=False))
            else:
                registered.bind_runtime(project_root=repository)
        return result

    monkeypatch.setattr(repository_sources, "run_bounded_subprocess", wait_then_change)
    result = await registry.execute(
        "pattern_search", {"description": "canonical labels", "strategy": "repository"}
    )
    assert not result.success
    assert "casefold" not in result.content
    assert result.error == "repository_authorization_changed"


async def test_ignored_tracked_sources_are_not_retrieved(repository):
    ignored = repository / "ignored" / "tracked.py"
    ignored.write_text('def canonical_labels():\n    """ignored tracked canary"""\n    return 0\n')
    git(repository, "add", "--force", "ignored/tracked.py")
    result = await search(repository)
    assert result.success, result.content
    assert "ignored tracked canary" not in result.content


async def test_nested_repository_is_not_traversed(repository):
    nested = repository / "nested"
    nested.mkdir()
    git(nested, "init", "-q")
    (nested / "private.py").write_text(
        'def canonical_labels():\n    """nested canary"""\n    return 0\n'
    )
    result = await search(repository)
    assert result.success, result.content
    assert "nested canary" not in result.content


async def test_symlink_and_hardlink_sources_are_explicitly_unavailable(repository, tmp_path):
    import os

    outside = tmp_path / "outside.py"
    outside.write_text('def canonical_labels():\n    """foreign canary"""\n    return 0\n')
    try:
        (repository / "linked.py").symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation unavailable")
    os.link(outside, repository / "hard.py")
    result = await search(repository)
    assert not result.success
    assert result.structured_content["status"] == "partial"
    assert "foreign canary" not in result.content
    codes = {item["code"] for item in result.structured_content["diagnostics"]}
    assert "source_symlink_unavailable" in codes
    assert "source_type_unavailable" in codes


async def test_file_budget_retains_partial_evidence(repository, monkeypatch):
    from henchman.analysis import repository_search

    monkeypatch.setattr(repository_search, "MAX_FILES", 1)
    result = await search(repository)
    assert not result.success
    assert result.structured_content["coverage"]["observed_files"] <= 1
    assert any(
        item["code"] == "repository_file_budget_exceeded"
        for item in result.structured_content["diagnostics"]
    )


async def test_oversized_source_is_not_prefix_evidence(repository):
    (repository / "huge.py").write_text(
        'def canonical_labels():\n    return "' + "x" * 300_000 + '"\n'
    )
    result = await search(repository)
    assert not result.success
    assert not any(
        item["path"] == "huge.py" for item in result.structured_content["implementations"]
    )
    assert any(
        item["code"] == "source_byte_budget_exceeded"
        for item in result.structured_content["diagnostics"]
    )


async def test_deadline_is_explicit_failure(repository, monkeypatch):
    from henchman.analysis import repository_search

    monkeypatch.setattr(repository_search, "TOTAL_SECONDS", 0.0)
    result = await search(repository)
    assert not result.success
    assert result.error == "repository_deadline_exceeded"


async def test_output_is_bounded_whole_json_with_explicit_omission(repository, monkeypatch):
    from henchman.analysis import repository_evidence

    monkeypatch.setattr(repository_evidence, "MAX_OUTPUT_BYTES", 1600)
    result = await search(repository)
    assert not result.success
    assert len(result.content.encode()) <= 1600
    assert json.loads(result.content) == result.structured_content
    assert result.structured_content.get("output_omitted_items", 0) > 0


async def test_git_environment_cannot_redirect_bound_workspace(repository, tmp_path, monkeypatch):
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    git(foreign, "init", "-q")
    monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(foreign))
    result = await search(repository)
    assert result.success, result.content
    assert any(
        item["symbol"] == "normalize_label" for item in result.structured_content["implementations"]
    )


async def test_custom_instruction_discovery_and_capture_limit_are_respected(repository):
    from types import SimpleNamespace

    from henchman.config.context import ContextLoader

    (repository / "CUSTOM.md").write_text("custom-rule-" * 50)
    snapshot = ContextLoader(
        filenames=("CUSTOM.md",), start_dir=repository, max_source_chars=35
    ).load_snapshot()
    search_tool = tool(repository)
    search_tool.bind_runtime(
        project_root=repository, session_manager=SimpleNamespace(instruction_snapshot=snapshot)
    )
    result = await search_tool.execute(description="canonical labels", strategy="repository")
    assert result.success, result.content
    records = result.structured_content["instructions"]
    assert [item["path"] for item in records] == ["CUSTOM.md"]
    assert records[0]["content"] == ("custom-rule-" * 50)[:35]
    assert records[0]["excerpt_truncated"]


async def test_native_git_wait_cancellation_joins_owned_process(repository, monkeypatch):
    import asyncio
    import sys

    from henchman.analysis import repository_sources
    from henchman.tools import subprocess_utils

    entered = asyncio.Event()
    processes = []
    original_create = asyncio.create_subprocess_exec
    original_run = subprocess_utils.run_bounded_subprocess

    async def create(*args, **kwargs):
        process = await original_create(*args, **kwargs)
        processes.append(process)
        entered.set()
        return process

    async def delayed_git(_command, **kwargs):
        return await original_run([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(repository_sources, "run_bounded_subprocess", delayed_git)
    task = asyncio.create_task(search(repository))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel("cancel repository observation")
        with pytest.raises(asyncio.CancelledError, match="cancel repository observation"):
            await asyncio.wait_for(task, 5)
        assert processes and all(process.returncode is not None for process in processes)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_repository_pack_survives_real_handoff_and_retained_compaction(repository, tmp_path):
    from unittest.mock import MagicMock

    from henchman.agents.delegation import _assemble_delegation_input
    from henchman.core.agent import Agent
    from henchman.core.session import SessionManager
    from henchman.core.session_context import SessionContextService
    from henchman.core.session_models import SessionMessage
    from henchman.providers.base import ModelProvider
    from henchman.utils.compaction import _truncate_tool_message_content

    result = await search(repository)
    assert result.success, result.content
    agent = Agent(provider=MagicMock(spec=ModelProvider))
    agent.submit_tool_result("repository-read", result)
    message = agent.messages[-1]
    handoff = _assemble_delegation_input("Reuse the existing helper", {"context": result.content})
    assert "src/pkg/normalization.py" in handoff
    assert '"task_verified":false' in handoff
    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = manager.create_session(project_hash="repository-evidence")
    session.messages = [
        SessionMessage("user", "Inspect existing implementation"),
        SessionMessage(
            "assistant",
            tool_calls=[{"id": "repository-read", "name": "pattern_search", "arguments": {}}],
        ),
        SessionMessage(
            "tool", message.content, tool_call_id="repository-read", tool_result=message.tool_result
        ),
        SessionMessage("assistant", handoff),
        SessionMessage("user", "Next turn"),
        SessionMessage("assistant", "Next response"),
    ]
    service = SessionContextService(manager)
    service.compact_session(session, preserve_turns=1)
    manager.save(session)
    retained = service.restore_compacted_messages(manager.load(session.id))
    assert retained[2].tool_result == message.tool_result
    assert retained[2].tool_result["structured_content"]["instructions"]
    compacted = _truncate_tool_message_content(message, 1000)
    assert compacted.tool_result["projection_truncated"] is True
    assert message.tool_result["structured_content"] == result.structured_content


async def test_independent_reuse_oracle_requires_existing_helper_calls(repository):
    import sys

    from henchman.tools.subprocess_utils import run_bounded_subprocess

    result = await search(repository)
    assert result.success, result.content
    helper = repository / "src/pkg/normalization.py"
    original = helper.read_bytes()
    caller = repository / "src/pkg/index.py"
    caller.write_text(
        "from . import normalization\n"
        "def unique_labels(values):\n"
        "    result = []\n"
        "    for value in values:\n"
        "        label = normalization.normalize_label(value)\n"
        "        if label and label not in result:\n"
        "            result.append(label)\n"
        "    return result\n"
    )
    # A separate Python process checks both behavior and actual reuse by replacing
    # the shared helper. Retrieval itself still makes no task-verification claim.
    oracle = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from pkg import index, normalization; "
        "assert index.unique_labels(['Straße','STRASSE',' Red Fox ', '']) == ['strasse','red-fox']; "
        "calls=[]; normalization.normalize_label=lambda value: (calls.append(value) or 'shared'); "
        "assert index.unique_labels(['one','two']) == ['shared']; "
        "assert calls == ['one','two']; print('reuse oracle passed')"
    )
    checked = await run_bounded_subprocess(
        [sys.executable, "-I", "-c", oracle, str(repository / "src")], cwd=repository, timeout=5
    )
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout.strip() == b"reuse oracle passed"
    assert helper.read_bytes() == original
    assert result.structured_content["task_verified"] is False


async def test_invalid_source_bytes_count_against_read_budget(repository, monkeypatch):
    from henchman.analysis import repository_sources

    # Both failed decodes still consumed real bytes; they cannot grant a fresh
    # budget to the next candidate.
    (repository / "00_bad.py").write_bytes(b"\xff" * 80)
    (repository / "01_bad.py").write_bytes(b"\xff" * 80)
    (repository / "02_helper.py").write_text(
        'def canonical_labels():\n    return "must-not-read-canary"\n'
    )
    monkeypatch.setattr(repository_sources, "MAX_SOURCE_BYTES", 160)
    result = await search(repository)
    assert not result.success
    assert "must-not-read-canary" not in result.content
    assert result.structured_content["coverage"]["source_bytes"] == 160


async def test_definition_budget_is_visible_without_unbounded_match_materialization(
    repository, monkeypatch
):
    from henchman.analysis import repository_search

    (repository / "many.py").write_text(
        "".join(f"def canonical_labels_{index}():\n    return {index}\n" for index in range(8))
    )
    monkeypatch.setattr(repository_search, "MAX_DEFINITIONS", 2, raising=False)
    result = await search(repository)
    assert not result.success
    assert len(result.structured_content["implementations"]) <= 2
    assert any(
        item["code"] == "definition_budget_exceeded"
        for item in result.structured_content["diagnostics"]
    )


async def test_parent_restriction_after_wait_revokes_child_repository_lease(
    repository, monkeypatch
):
    from henchman.analysis import repository_sources
    from henchman.tools.access_policy import ToolAccessPolicy
    from henchman.tools.registry import ToolRegistry
    from henchman.tools.scoped_registry import ScopedToolRegistry

    parent = ToolRegistry()
    parent.register(tool(repository))
    child = ScopedToolRegistry(parent, None, inherit_auto_approve=True)
    original = repository_sources.run_bounded_subprocess

    async def wait_then_restrict(*args, **kwargs):
        result = await original(*args, **kwargs)
        parent.restrict_access_policy(ToolAccessPolicy(network_access="disabled"))
        return result

    monkeypatch.setattr(repository_sources, "run_bounded_subprocess", wait_then_restrict)
    result = await child.execute(
        "pattern_search", {"description": "canonical labels", "strategy": "repository"}
    )
    assert not result.success and result.error == "repository_authorization_changed"
    assert "casefold" not in result.content


async def test_approval_policy_change_prevents_repository_git_dispatch(repository, monkeypatch):
    from henchman.analysis import repository_sources
    from henchman.tools.access_policy import ToolAccessPolicy
    from henchman.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register(tool(repository))
    registry.set_read_confirmation_required(True)

    async def approve(_request):
        registry.restrict_access_policy(ToolAccessPolicy(read_roots=()))
        return True

    async def forbidden(*_args, **_kwargs):
        pytest.fail("stale approval dispatched Git")

    registry.set_confirmation_handler(approve)
    monkeypatch.setattr(repository_sources, "run_bounded_subprocess", forbidden)
    result = await registry.execute(
        "pattern_search", {"description": "canonical labels", "strategy": "repository"}
    )
    assert not result.success


async def test_repository_lease_is_closed_in_retained_child_context(repository, monkeypatch):
    import contextvars

    from henchman.analysis import repository_sources
    from henchman.tools.access_policy import ToolAccessError, check_repository_read_authorization
    from henchman.tools.registry import ToolRegistry

    captured = []
    original = repository_sources.run_bounded_subprocess

    async def capture_context(*args, **kwargs):
        captured.append(contextvars.copy_context())
        return await original(*args, **kwargs)

    registry = ToolRegistry()
    registry.register(tool(repository))
    monkeypatch.setattr(repository_sources, "run_bounded_subprocess", capture_context)
    result = await registry.execute(
        "pattern_search", {"description": "canonical labels", "strategy": "repository"}
    )
    assert result.success, result.content
    with pytest.raises(ToolAccessError, match="closed"):
        captured[0].run(check_repository_read_authorization)


async def test_recovery_control_error_propagates_without_partial_result(repository, monkeypatch):
    from henchman.analysis import repository_sources
    from henchman.core.operation_recovery import OperationRecoveryError

    error = OperationRecoveryError("review_required")

    async def stop(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(repository_sources, "run_bounded_subprocess", stop)
    with pytest.raises(OperationRecoveryError) as raised:
        await search(repository)
    assert raised.value is error


async def test_candidate_entry_budget_refuses_before_source_read(repository, monkeypatch):
    from henchman.analysis import repository_sources

    monkeypatch.setattr(repository_sources, "MAX_ENTRIES", 1)

    def forbidden(*_args, **_kwargs):
        pytest.fail("excess listing reached source read")

    monkeypatch.setattr(repository_sources, "read_source", forbidden)
    result = await search(repository)
    assert not result.success and result.error == "repository_entry_budget_exceeded"


async def test_empty_unborn_repository_is_fresh_empty_evidence(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    git(root, "init", "-q")
    result = await search(root)
    assert result.success, result.content
    assert result.structured_content["current_revision"] is None
    assert result.structured_content["implementations"] == []
    assert result.structured_content["task_verified"] is False


async def test_pending_cancel_at_final_guard_cannot_publish_success(repository, monkeypatch):
    import asyncio

    from henchman.analysis.repository_sources import RepositoryObservation

    armed = False
    published = []
    original_verify = RepositoryObservation.verify
    original_check = RepositoryObservation.check

    async def verify(self, *args, **kwargs):
        nonlocal armed
        await original_verify(self, *args, **kwargs)
        armed = True

    def cancel_at_guard(self):
        nonlocal armed
        original_check(self)
        if armed:
            armed = False
            asyncio.current_task().cancel("cancel publication")

    async def invoke():
        result = await search(repository)
        published.append(result)
        await asyncio.sleep(0)

    monkeypatch.setattr(RepositoryObservation, "verify", verify)
    monkeypatch.setattr(RepositoryObservation, "check", cancel_at_guard)
    with pytest.raises(asyncio.CancelledError, match="cancel publication"):
        await asyncio.create_task(invoke())
    assert published == []
