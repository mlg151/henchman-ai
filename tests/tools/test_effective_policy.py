"""Centralized effective tool policy (#18).

The plan-mode gate, per-invocation operation effects, and confirmation
requirements must resolve from one shared verdict so that every dispatch
path — direct execution, batches, orchestrated delegation, and scoped
subagent registries — enforces the same effective policy.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.policy import PolicyDecision, evaluate_effective_policy
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry
from henchman.utils.retry import RetryConfig


class _KindTool(Tool):
    """Parameterless mock tool with a static kind and optional override."""

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


class TestEvaluateEffectivePolicy:
    """The shared verdict function is the single source of policy truth."""

    def test_read_allowed_in_plan_mode(self) -> None:
        tool = _KindTool("read_x", ToolKind.READ)
        decision = evaluate_effective_policy(
            tool, {}, plan_mode_active=True, auto_approved=False
        )
        assert decision.allowed
        assert decision.effective_kind is ToolKind.READ
        assert decision.confirmation is None
        assert decision.denial_reason is None

    @pytest.mark.parametrize(
        ("kind"), [ToolKind.WRITE, ToolKind.EXECUTE, ToolKind.NETWORK]
    )
    def test_effectful_kinds_blocked_in_plan_mode(self, kind: ToolKind) -> None:
        tool = _KindTool("write_x", kind)
        # Auto-approval must never override the plan-mode boundary.
        decision = evaluate_effective_policy(
            tool, {}, plan_mode_active=True, auto_approved=True
        )
        assert not decision.allowed
        assert decision.denial_reason == "Tool disabled in Plan Mode"
        assert decision.effective_kind is kind
        assert decision.confirmation is None

    def test_effectful_kind_allowed_without_plan_mode(self) -> None:
        tool = _KindTool("write_x", ToolKind.WRITE)
        decision = evaluate_effective_policy(
            tool, {}, plan_mode_active=False, auto_approved=False
        )
        assert decision.allowed
        assert decision.effective_kind is ToolKind.WRITE
        assert decision.confirmation is not None
        assert decision.denial_reason is None

    def test_auto_approval_suppresses_confirmation(self) -> None:
        tool = _KindTool("write_x", ToolKind.WRITE)
        decision = evaluate_effective_policy(
            tool, {}, plan_mode_active=False, auto_approved=True
        )
        assert decision.allowed
        assert decision.confirmation is None

    def test_read_only_override_allowed_in_plan_mode(self) -> None:
        tool = _KindTool("write_x", ToolKind.WRITE, effective_kind=ToolKind.READ)
        decision = evaluate_effective_policy(
            tool, {}, plan_mode_active=True, auto_approved=False
        )
        assert decision.allowed
        assert decision.effective_kind is ToolKind.READ
        assert decision.confirmation is None

    def test_effectful_override_blocked_in_plan_mode(self) -> None:
        tool = _KindTool("read_x", ToolKind.READ, effective_kind=ToolKind.EXECUTE)
        decision = evaluate_effective_policy(
            tool, {}, plan_mode_active=True, auto_approved=False
        )
        assert not decision.allowed
        assert decision.effective_kind is ToolKind.EXECUTE

    def test_effectful_override_requires_confirmation_without_plan_mode(self) -> None:
        tool = _KindTool("read_x", ToolKind.READ, effective_kind=ToolKind.EXECUTE)
        decision = evaluate_effective_policy(
            tool, {}, plan_mode_active=False, auto_approved=False
        )
        assert decision.allowed
        assert decision.confirmation is not None
        assert decision.confirmation.risk_level == "high"


class TestRegistryPolicyQuery:
    """ToolRegistry.evaluate_policy exposes the shared verdict publicly."""

    def test_unregistered_tool_returns_none(self) -> None:
        registry = ToolRegistry()
        assert registry.evaluate_policy("missing", {}) is None

    def test_read_verdict_outside_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("read_x", ToolKind.READ))
        decision = registry.evaluate_policy("read_x", {})
        assert isinstance(decision, PolicyDecision)
        assert decision.allowed
        assert decision.confirmation is None

    def test_write_verdict_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        registry.set_plan_mode(enabled=True)
        decision = registry.evaluate_policy("write_x", {})
        assert decision is not None
        assert not decision.allowed
        assert decision.denial_reason == "Tool disabled in Plan Mode"

    @pytest.mark.parametrize("kind", [ToolKind.READ, ToolKind.WRITE, ToolKind.EXECUTE])
    @pytest.mark.parametrize("plan_mode", [False, True])
    @pytest.mark.parametrize("auto_approved", [False, True])
    async def test_query_matches_authorize_outcome(
        self, kind: ToolKind, plan_mode: bool, auto_approved: bool
    ) -> None:
        registry = ToolRegistry()
        tool = _KindTool("op", kind)
        registry.register(tool)
        if plan_mode:
            registry.set_plan_mode(enabled=True)
        if auto_approved:
            registry.add_auto_approve_policy("op")
        decision = registry.evaluate_policy("op", {})
        assert decision is not None
        authorized = await registry.authorize("op", {})
        if not decision.allowed:
            assert isinstance(authorized, ToolResult)
            assert authorized.error == "Tool disabled in Plan Mode"
        elif decision.confirmation is not None:
            # No handler in this registry: an explicit needs-input denial
            # (headless input is never fabricated), distinct from the plan-mode denial.
            assert isinstance(authorized, ToolResult)
            assert "Confirmation required" in (authorized.error or "")
        else:
            assert not isinstance(authorized, ToolResult)

    def test_auto_approval_cannot_override_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        registry.add_auto_approve_policy("write_x")
        registry.set_plan_mode(enabled=True)
        decision = registry.evaluate_policy("write_x", {})
        assert decision is not None
        assert not decision.allowed


class TestLateRegistrationBoundary:
    """Registration order must never bypass the plan-mode boundary."""

    async def test_tool_registered_after_plan_mode_is_blocked(self) -> None:
        registry = ToolRegistry()
        registry.set_plan_mode(enabled=True)
        registry.register(_KindTool("late_mcp", ToolKind.NETWORK))
        result = await registry.authorize("late_mcp", {})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"

    async def test_plan_mode_enabled_after_registration_is_blocked(self) -> None:
        registry = ToolRegistry()
        tool = _KindTool("early_mcp", ToolKind.NETWORK)
        registry.register(tool)
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize("early_mcp", {})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"

    async def test_read_tool_registered_after_plan_mode_is_allowed(self) -> None:
        registry = ToolRegistry()
        registry.set_plan_mode(enabled=True)
        tool = _KindTool("late_read", ToolKind.READ)
        registry.register(tool)
        result = await registry.authorize("late_read", {})
        assert isinstance(result, Tool)
        assert tool.executed == []


class TestScopedRegistryPolicyInheritance:
    """Scoped subagent registries evaluate the inherited policy, not their own."""

    async def test_child_inherits_parent_plan_mode(self) -> None:
        parent = ToolRegistry()
        parent.register(_KindTool("write_x", ToolKind.WRITE))
        parent.set_plan_mode(enabled=True)
        child = ScopedToolRegistry(parent, None)
        decision = child.evaluate_policy("write_x", {})
        assert decision is not None
        assert not decision.allowed
        result = await child.authorize("write_x", {})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"

    async def test_child_local_plan_mode_blocks_without_parent(self) -> None:
        parent = ToolRegistry()
        parent.register(_KindTool("write_x", ToolKind.WRITE))
        child = ScopedToolRegistry(parent, None)
        child.set_plan_mode(enabled=True)
        decision = child.evaluate_policy("write_x", {})
        assert decision is not None
        assert not decision.allowed

    async def test_child_inherits_parent_auto_approval(self) -> None:
        parent = ToolRegistry()
        tool = _KindTool("write_x", ToolKind.WRITE)
        parent.register(tool)
        parent.add_auto_approve_policy("write_x")
        child = ScopedToolRegistry(parent, None, inherit_auto_approve=True)
        decision = child.evaluate_policy("write_x", {})
        assert decision is not None
        assert decision.allowed
        assert decision.confirmation is None

    def test_child_without_inheritance_keeps_confirmation(self) -> None:
        parent = ToolRegistry()
        parent.register(_KindTool("write_x", ToolKind.WRITE))
        parent.add_auto_approve_policy("write_x")
        child = ScopedToolRegistry(parent, None, inherit_auto_approve=False)
        decision = child.evaluate_policy("write_x", {})
        assert decision is not None
        assert decision.allowed
        assert decision.confirmation is not None

    def test_excluded_parent_tool_is_not_found(self) -> None:
        parent = ToolRegistry()
        parent.register(_KindTool("write_x", ToolKind.WRITE))
        child = ScopedToolRegistry(parent, None)
        child.unregister("write_x")
        assert child.evaluate_policy("write_x", {}) is None


class TestExecutionGateParity:
    """Execution entry points consume the same verdict as the query."""

    async def test_execute_blocked_without_running_tool(self) -> None:
        registry = ToolRegistry()
        tool = _KindTool("write_x", ToolKind.WRITE)
        registry.register(tool)
        registry.set_plan_mode(enabled=True)
        result = await registry.execute("write_x", {"value": "data"})
        assert result.success is False
        assert result.error == "Tool disabled in Plan Mode"
        assert tool.executed == []

    async def test_execute_batch_reports_blocked_invocation(self) -> None:
        registry = ToolRegistry()
        registry.register(_KindTool("read_x", ToolKind.READ))
        registry.register(_KindTool("write_x", ToolKind.WRITE))
        registry.set_plan_mode(enabled=True)
        batch = await registry.execute_batch(
            [("read_x", {}), ("write_x", {"value": "data"})]
        )
        assert batch.successful == 1
        assert batch.failed == 1
        assert batch.results["1:write_x"].error == "Tool disabled in Plan Mode"

    async def test_allowed_execution_still_runs(self) -> None:
        registry = ToolRegistry()
        tool = _KindTool("read_x", ToolKind.READ)
        registry.register(tool)
        registry.set_plan_mode(enabled=True)
        result = await registry.execute("read_x", {"value": "data"})
        assert result.success
        assert tool.executed == [{"value": "data"}]


@pytest.mark.parametrize(
    "change", ["plan", "plan_roundtrip", "handler", "remove", "replace", "session", "effect", "params"],
)
async def test_approval_cannot_authorize_a_changed_invocation(
    change: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent changes while approval is pending invalidate that approval."""
    monkeypatch.chdir(tmp_path)
    parent = ToolRegistry()
    tool = _KindTool("write_x", ToolKind.WRITE)
    replacement = _KindTool("write_x", ToolKind.WRITE)
    parent.register(tool)
    registry = ScopedToolRegistry(parent, None)
    entered, release = asyncio.Event(), asyncio.Event()
    params: dict[str, object] = {"value": "original"}

    async def approve(_request: ConfirmationRequest) -> bool:
        entered.set()
        await release.wait()
        return True

    parent.set_confirmation_handler(approve)
    running = asyncio.create_task(registry.execute("write_x", params))
    await asyncio.wait_for(entered.wait(), timeout=5)
    if change == "plan":
        parent.set_plan_mode(enabled=True)
    elif change == "plan_roundtrip":
        parent.set_plan_mode(enabled=True)
        parent.set_plan_mode(enabled=False)
    elif change == "handler":
        async def deny(_request: ConfirmationRequest) -> bool:
            return False
        parent.set_confirmation_handler(deny)
    elif change in {"remove", "replace"}:
        parent.unregister("write_x")
        if change == "replace":
            parent.register(replacement)
    elif change == "session":
        parent.clear_grants()
    elif change == "effect":
        tool._effective_kind = ToolKind.EXECUTE
    else:
        params["value"] = "changed"
    release.set()
    result = await asyncio.wait_for(running, timeout=5)
    assert not result.success
    assert tool.executed == replacement.executed == []
    assert parent.list_approval_grants() == []


@pytest.mark.parametrize("change", ["plan", "remove", "replace", "revoke", "params"])
async def test_dispatch_rechecks_authorization_after_formatter_lock(
    change: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A queued write must not use stale authorization when the lock opens."""
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry()
    tool = _KindTool("write_x", ToolKind.WRITE)
    replacement = _KindTool("write_x", ToolKind.WRITE)
    registry.register(tool)
    approved = asyncio.Event()
    params: dict[str, object] = {"value": "original"}

    async def approve(_request: ConfirmationRequest) -> bool:
        approved.set()
        return True

    registry.set_confirmation_handler(approve)
    lock = registry._effective_formatter._lock
    await lock.acquire()
    running = asyncio.create_task(registry.execute("write_x", params))
    try:
        await asyncio.wait_for(approved.wait(), timeout=5)
        if change == "plan":
            registry.set_plan_mode(enabled=True)
        elif change in {"remove", "replace"}:
            registry.unregister("write_x")
            if change == "replace":
                registry.register(replacement)
        elif change == "revoke":
            registry.clear_grants()
        else:
            params["value"] = "changed"
    finally:
        lock.release()
    result = await asyncio.wait_for(running, timeout=5)
    assert not result.success
    assert tool.executed == replacement.executed == []


@pytest.mark.parametrize("change", ["plan", "remove", "replace", "revoke_auto"])
async def test_network_retry_rechecks_current_authority(
    change: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A network retry cannot run after the original authority was withdrawn."""
    monkeypatch.chdir(tmp_path)
    registry = ToolRegistry(RetryConfig(max_retries=1, base_delay=0, jitter=False))
    replacement = _KindTool("network_x", ToolKind.NETWORK)

    class InterruptedNetwork(_KindTool):
        async def execute(self, **params: object) -> ToolResult:
            self.executed.append(params)
            if len(self.executed) == 1:
                if change == "plan":
                    registry.set_plan_mode(enabled=True)
                elif change in {"remove", "replace"}:
                    registry.unregister(self.name)
                    if change == "replace":
                        registry.register(replacement)
                else:
                    registry.remove_auto_approve_policy(self.name)
                raise ConnectionError("retryable failure")
            return ToolResult("stale retry executed")

    tool = InterruptedNetwork("network_x", ToolKind.NETWORK)
    registry.register(tool)
    registry.add_auto_approve_policy(tool.name)
    result = await registry.execute(tool.name, {})
    assert not result.success
    assert len(tool.executed) == 1
    assert replacement.executed == []
