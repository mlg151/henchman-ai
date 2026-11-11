"""Approval-reuse scoping (#18).

A user-approved tool invocation is remembered for the session scope so that a
repeated, still-valid authorization does not re-prompt. Any change to the
action, parameters, or risk invalidates the grant and re-prompts. Grants are
scoped to the exact approved invocation and never extend to other tools,
arguments, or risk levels.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.policy import ApprovalGrantStore, GrantKey, grant_key_for
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry


class _KindTool(Tool):
    """Mock tool with a static kind and optional per-invocation override."""

    def __init__(
        self,
        name: str,
        kind: ToolKind,
        effective_kind: ToolKind | None = None,
    ) -> None:
        self._name = name
        self._kind = kind
        self._effective_kind = effective_kind
        self.executed: list[dict[str, object]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock {self._name} tool"

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {"value": {"type": "string"}}}

    @property
    def kind(self) -> ToolKind:
        return self._kind

    def execution_kind(self, params: dict[str, object]) -> ToolKind:
        if self._effective_kind is None:
            return self._kind
        return self._effective_kind

    async def execute(self, **params: object) -> ToolResult:
        self.executed.append(params)
        return ToolResult(content=f"Executed {self._name}")


class _RiskShiftingTool(Tool):
    """A WRITE tool that escalates to EXECUTE (high risk) when forced."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.executed: list[dict[str, object]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock {self._name} tool"

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {"value": {"type": "string"}}}

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    def execution_kind(self, params: dict[str, object]) -> ToolKind:
        return ToolKind.EXECUTE if params.get("forced") else ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        self.executed.append(params)
        return ToolResult(content=f"Executed {self._name}")


def _approve_all(record: list[ConfirmationRequest]):
    async def handler(request: ConfirmationRequest) -> bool:
        record.append(request)
        return True

    return handler


def _deny_all(record: list[ConfirmationRequest]):
    async def handler(request: ConfirmationRequest) -> bool:
        record.append(request)
        return False

    return handler


class TestGrantKeyDerivation:
    """The grant key captures exactly the approved invocation's scope."""

    def test_identical_requests_share_a_key(self) -> None:
        a = grant_key_for(
            ConfirmationRequest(
                tool_name="write_file", description="one", params={"path": "/a"}, risk_level="medium"
            ),
            ToolKind.WRITE,
        )
        b = grant_key_for(
            ConfirmationRequest(
                tool_name="write_file", description="two", params={"path": "/a"}, risk_level="medium"
            ),
            ToolKind.WRITE,
        )
        # The description is display text, not scope.
        assert a == b

    def test_changed_params_change_the_key(self) -> None:
        a = grant_key_for(
            ConfirmationRequest(tool_name="write_file", description="d", params={"path": "/a"}),
            ToolKind.WRITE,
        )
        b = grant_key_for(
            ConfirmationRequest(tool_name="write_file", description="d", params={"path": "/b"}),
            ToolKind.WRITE,
        )
        assert a != b

    def test_changed_risk_changes_the_key(self) -> None:
        a = grant_key_for(
            ConfirmationRequest(tool_name="op", description="d", params={"v": 1}, risk_level="medium"),
            ToolKind.WRITE,
        )
        b = grant_key_for(
            ConfirmationRequest(tool_name="op", description="d", params={"v": 1}, risk_level="high"),
            ToolKind.WRITE,
        )
        assert a != b

    def test_changed_effective_kind_changes_the_key(self) -> None:
        a = grant_key_for(
            ConfirmationRequest(tool_name="op", description="d", params={"v": 1}), ToolKind.WRITE
        )
        b = grant_key_for(
            ConfirmationRequest(tool_name="op", description="d", params={"v": 1}), ToolKind.EXECUTE
        )
        assert a != b

    def test_changed_tool_name_changes_the_key(self) -> None:
        a = grant_key_for(
            ConfirmationRequest(tool_name="op_a", description="d", params={"v": 1}), ToolKind.WRITE
        )
        b = grant_key_for(
            ConfirmationRequest(tool_name="op_b", description="d", params={"v": 1}), ToolKind.WRITE
        )
        assert a != b

    def test_none_params_digest_like_empty(self) -> None:
        a = grant_key_for(
            ConfirmationRequest(tool_name="op", description="d", params=None), ToolKind.WRITE
        )
        b = grant_key_for(
            ConfirmationRequest(tool_name="op", description="d", params={}), ToolKind.WRITE
        )
        assert a == b


class TestGrantStore:
    """The store tracks granted keys for the session scope."""

    def _key(self) -> GrantKey:
        return grant_key_for(
            ConfirmationRequest(tool_name="op", description="d", params={"v": 1}), ToolKind.WRITE
        )

    def test_empty_store_grants_nothing(self) -> None:
        store = ApprovalGrantStore()
        assert not store.is_granted(self._key())
        assert len(store) == 0

    def test_grant_then_lookup(self) -> None:
        store = ApprovalGrantStore()
        key = self._key()
        store.grant(key)
        assert store.is_granted(key)
        assert len(store) == 1

    def test_revoke_forgets(self) -> None:
        store = ApprovalGrantStore()
        key = self._key()
        store.grant(key)
        store.revoke(key)
        assert not store.is_granted(key)

    def test_clear_forgets_all(self) -> None:
        store = ApprovalGrantStore()
        store.grant(self._key())
        store.clear()
        assert len(store) == 0
        assert not store.is_granted(self._key())


class TestApprovalReuse:
    """Repeated still-valid authorizations skip the prompt; changed scope re-prompts."""

    async def test_identical_approved_call_is_not_reprompted(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_approve_all(prompts))
        first = await registry.authorize("write_x", {"path": "/a"})
        assert isinstance(first, Tool)
        assert len(prompts) == 1
        second = await registry.authorize("write_x", {"path": "/a"})
        assert isinstance(second, Tool)
        assert len(prompts) == 1  # Reused; not re-prompted.

    async def test_changed_params_require_new_prompt(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_approve_all(prompts))
        await registry.authorize("write_x", {"path": "/a"})
        await registry.authorize("write_x", {"path": "/b"})
        assert len(prompts) == 2

    async def test_denied_call_records_no_grant(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_deny_all(prompts))
        result = await registry.authorize("write_x", {"path": "/a"})
        assert isinstance(result, ToolResult)
        assert registry.list_approval_grants() == []
        # A later attempt still prompts (nothing was granted).
        result2 = await registry.authorize("write_x", {"path": "/a"})
        assert isinstance(result2, ToolResult)
        assert len(prompts) == 2

    async def test_grant_does_not_extend_to_other_tool(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_a", ToolKind.WRITE))
        registry.register(_KindTool("write_b", ToolKind.WRITE))
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_approve_all(prompts))
        await registry.authorize("write_a", {"path": "/a"})
        await registry.authorize("write_b", {"path": "/a"})
        assert len(prompts) == 2

    async def test_risk_escalation_requires_new_prompt(self) -> None:
        registry = ToolRegistry()
        tool = _RiskShiftingTool("op")
        registry.register(tool)
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_approve_all(prompts))
        # WRITE (medium) first.
        await registry.authorize("op", {"value": "v"})
        # Same value but escalated to EXECUTE (high) — new scope.
        await registry.authorize("op", {"value": "v", "forced": True})
        assert len(prompts) == 2
        assert [p.risk_level for p in prompts] == ["medium", "high"]

    async def test_auto_approved_tool_records_no_grant(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        registry.add_auto_approve_policy("write_x")
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_approve_all(prompts))
        result = await registry.authorize("write_x", {"path": "/a"})
        assert isinstance(result, Tool)
        assert len(prompts) == 0
        assert registry.list_approval_grants() == []

    async def test_execute_path_reuses_grant(self) -> None:
        registry = ToolRegistry()
        tool = _KindTool("write_x", ToolKind.WRITE)
        registry.register(tool)
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_approve_all(prompts))
        r1 = await registry.execute("write_x", {"path": "/a"})
        r2 = await registry.execute("write_x", {"path": "/a"})
        assert r1.success and r2.success
        assert len(prompts) == 1
        assert len(tool.executed) == 2

    async def test_plan_mode_denial_records_no_grant(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        registry.set_plan_mode(enabled=True)
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_approve_all(prompts))
        result = await registry.authorize("write_x", {"path": "/a"})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"
        assert len(prompts) == 0
        assert registry.list_approval_grants() == []


class TestGrantSessionScope:
    """Grants are session-scoped: shared across a registry ancestry, not across sessions."""

    async def test_scoped_child_reuses_parent_grant(self) -> None:
        parent = ToolRegistry()
        parent.register(_KindTool("write_x", ToolKind.WRITE))
        prompts: list[ConfirmationRequest] = []
        parent.set_confirmation_handler(_approve_all(prompts))
        child = ScopedToolRegistry(parent, None)
        await parent.authorize("write_x", {"path": "/a"})
        assert len(prompts) == 1
        result = await child.authorize("write_x", {"path": "/a"})
        assert isinstance(result, Tool)
        assert len(prompts) == 1  # Child sees the parent's grant.

    async def test_child_approval_is_visible_to_parent(self) -> None:
        parent = ToolRegistry()
        parent.register(_KindTool("write_x", ToolKind.WRITE))
        prompts: list[ConfirmationRequest] = []
        parent.set_confirmation_handler(_approve_all(prompts))
        child = ScopedToolRegistry(parent, None)
        # The child resolves the parent's confirmation handler.
        await child.authorize("write_x", {"path": "/a"})
        assert len(prompts) == 1
        result = await parent.authorize("write_x", {"path": "/a"})
        assert isinstance(result, Tool)
        assert len(prompts) == 1  # Parent sees the grant recorded via the child.

    async def test_separate_registries_do_not_share_grants(self) -> None:
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        r1.register(_KindTool("write_x", ToolKind.WRITE))
        r2.register(_KindTool("write_x", ToolKind.WRITE))
        prompts2: list[ConfirmationRequest] = []
        r2.set_confirmation_handler(_approve_all(prompts2))
        # r1 approves (no handler -> no prompt recorded on r2).
        r1.set_confirmation_handler(_approve_all([]))
        await r1.authorize("write_x", {"path": "/a"})
        # r2 has no grant and must prompt.
        result = await r2.authorize("write_x", {"path": "/a"})
        assert isinstance(result, Tool)
        assert len(prompts2) == 1

    async def test_clear_grants_invalidates(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        prompts: list[ConfirmationRequest] = []
        registry.set_confirmation_handler(_approve_all(prompts))
        await registry.authorize("write_x", {"path": "/a"})
        assert len(registry.list_approval_grants()) == 1
        registry.clear_grants()
        assert registry.list_approval_grants() == []
        result = await registry.authorize("write_x", {"path": "/a"})
        assert isinstance(result, Tool)
        assert len(prompts) == 2  # Re-prompted after the session reset.


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as exc:
        pytest.skip(f"Symlinks unavailable on this platform: {exc}")


async def test_retargeted_symlink_requires_new_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first, second, link = (tmp_path / name for name in ("first.txt", "second.txt", "link.txt"))
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    _symlink(link, first)
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    prompts: list[ConfirmationRequest] = []

    async def approve_once(request: ConfirmationRequest) -> bool:
        prompts.append(request)
        return len(prompts) == 1

    registry.set_confirmation_handler(approve_once)
    params = {"path": str(link), "content": "approved"}
    assert (await registry.execute("write_file", params)).success
    link.unlink()
    _symlink(link, second)
    result = await registry.execute("write_file", params)
    assert not result.success
    assert len(prompts) == 2
    assert second.read_text(encoding="utf-8") == "second"


@pytest.mark.parametrize("during", ["approval", "formatter"])
async def test_inflight_symlink_change_cannot_retarget_approved_write(
    during: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    first, second, link = (tmp_path / name for name in ("first.txt", "second.txt", "link.txt"))
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    _symlink(link, first)
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    entered, release = asyncio.Event(), asyncio.Event()

    async def approve(_request: ConfirmationRequest) -> bool:
        entered.set()
        if during == "approval":
            await release.wait()
        return True

    registry.set_confirmation_handler(approve)
    lock = registry._effective_formatter._lock
    if during == "formatter":
        await lock.acquire()
    running = asyncio.create_task(registry.execute("write_file", {"path": str(link), "content": "bad"}))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        link.unlink()
        _symlink(link, second)
    finally:
        release.set()
        if during == "formatter":
            lock.release()
    result = await asyncio.wait_for(running, timeout=5)
    assert not result.success
    assert first.read_text(encoding="utf-8") == "first"
    assert second.read_text(encoding="utf-8") == "second"


async def test_replacement_tool_does_not_reuse_old_grant() -> None:
    parent = ToolRegistry()
    parent.register(_KindTool("write_x", ToolKind.WRITE))
    prompts: list[ConfirmationRequest] = []
    parent.set_confirmation_handler(_approve_all(prompts))
    child = ScopedToolRegistry(parent, None)
    await child.authorize("write_x", {})
    parent.unregister("write_x")
    replacement = _KindTool("write_x", ToolKind.WRITE)
    parent.register(replacement)
    assert await child.authorize("write_x", {}) is replacement
    assert len(prompts) == 2


async def test_relative_path_grant_does_not_cross_git_worktrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    if shutil.which("git") is None:
        pytest.skip("Git is unavailable")
    main, worktree = tmp_path / "main", tmp_path / "worktree"

    def git(*args: str) -> None:
        subprocess.run(["git", *args], capture_output=True, check=True)

    git("init", "-q", str(main))
    (main / "sample.txt").write_text("baseline", encoding="utf-8")
    git("-C", str(main), "add", "sample.txt")
    git("-C", str(main), "-c", "user.name=Policy Test", "-c", "user.email=test@example.invalid",
        "commit", "-qm", "fixture")
    git("-C", str(main), "worktree", "add", "-q", "--detach", str(worktree))
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    prompts: list[ConfirmationRequest] = []

    async def approve_once(request: ConfirmationRequest) -> bool:
        prompts.append(request)
        return len(prompts) == 1

    registry.set_confirmation_handler(approve_once)
    params = {"path": "sample.txt", "content": "approved-for-main"}
    monkeypatch.chdir(main)
    assert (await registry.execute("write_file", params)).success
    monkeypatch.chdir(worktree)
    result = await registry.execute("write_file", params)
    assert not result.success
    assert len(prompts) == 2
    assert (worktree / "sample.txt").read_text(encoding="utf-8") == "baseline"
