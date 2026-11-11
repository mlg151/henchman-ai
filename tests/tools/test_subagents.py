"""Dynamic subagent tool contracts and runtime binding."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from henchman.advanced.checkpoint_models import ReviewResult
from henchman.agents.delegation_admission import DelegationAdmission
from henchman.agents.subagents import BackgroundSubagentManager
from henchman.core.events import AgentEvent, EventType
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.run_budget import BudgetControlError
from henchman.providers.continuation import ProviderContinuationError
from henchman.tools.base import ToolKind
from henchman.tools.builtins.subagents import (
    InvokeSubagentTool,
    ManageSubagentsTool,
    PublishSubagentProposalTool,
)
from henchman.tools.registry import ToolRegistry
from henchman.tools.repair_scope import RepairControlError


def create_manager() -> BackgroundSubagentManager:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        await asyncio.Event().wait()
        yield AgentEvent(EventType.CONTENT, _prompt)

    return BackgroundSubagentManager(
        admission=DelegationAdmission(allowed=True),
        factory=lambda *args: args,
        runner=runner,
        available_tools=lambda _actor: ["read_file"],
    )


async def test_unbound_tools_fail_with_actionable_error() -> None:
    for tool in (InvokeSubagentTool(), ManageSubagentsTool()):
        result = await tool.execute()
        assert not result.success
        assert "runtime" in result.content.lower()


async def test_invoke_requires_explicit_task_role_prompt_and_tool_subset() -> None:
    manager = create_manager()
    tool = InvokeSubagentTool()
    tool.bind_runtime(subagent_manager=manager)
    try:
        assert tool.kind == ToolKind.EXECUTE
        missing = await tool.execute(task="task", role="reviewer", system_prompt="review")
        assert not missing.success
        bad = await tool.execute(
            task="task", role="reviewer", system_prompt="review", tools=["shell"]
        )
        assert not bad.success
        result = await tool.execute(
            task="Review files",
            role="custom reviewer",
            system_prompt="Only review",
            tools=["read_file"],
        )
        assert result.success
        record = json.loads(result.content)
        assert record["role"] == "custom reviewer"
        assert record["status"] == "running"
        assert record["tools"] == ["read_file"]
    finally:
        await manager.close()


async def test_manage_lists_inspects_and_cancels_without_polling() -> None:
    manager = create_manager()
    tool = ManageSubagentsTool(manager)
    try:
        record = manager.spawn("task", role="review", system_prompt="review", tools=[])
        listed = await tool.execute(action="list")
        assert listed.success
        assert record.conversation_id in listed.content
        inspected = await tool.execute(action="get", conversation_id=record.conversation_id)
        assert json.loads(inspected.content)["status"] == "running"
        assert tool.execution_kind({"action": "get"}) == ToolKind.READ
        assert tool.execution_kind({"action": "cancel"}) == ToolKind.WRITE
        cancelled = await tool.execute(action="cancel", conversation_id=record.conversation_id)
        assert json.loads(cancelled.content)["cancelled"]
        missing = await tool.execute(action="get", conversation_id="missing")
        assert not missing.success
        invalid = await tool.execute(action="invalid")
        assert not invalid.success
    finally:
        await manager.close()


@pytest.mark.parametrize("error_type", [OperationRecoveryError, BudgetControlError,
                                       ProviderContinuationError, RepairControlError])
@pytest.mark.parametrize("action", ["spawn", "review", "publish"])
async def test_runtime_control_failures_propagate(error_type, action, monkeypatch) -> None:
    manager = create_manager()
    error = error_type("control")

    def fail(*_args, **_kwargs):
        raise error

    async def fail_async(*_args, **_kwargs):
        raise error

    try:
        if action == "spawn":
            monkeypatch.setattr(manager, "spawn", fail)
            call = InvokeSubagentTool(manager).execute(task="task", role="role", system_prompt="prompt", tools=[])
        elif action == "review":
            monkeypatch.setattr(manager, "review_staged", fail_async)
            call = ManageSubagentsTool(manager).execute(action="review", conversation_id="child")
        else:
            monkeypatch.setattr(manager, "publish_staged", fail)
            call = PublishSubagentProposalTool(manager).execute(conversation_id="child", review_token="token")
        with pytest.raises(error_type) as caught:
            await call
        assert caught.value is error
    finally:
        await manager.close()


async def test_auto_approving_management_does_not_approve_publication(monkeypatch) -> None:
    manager = create_manager()

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Publication must not be dispatched without its own approval")

    monkeypatch.setattr(manager, "publish_staged", unexpected)
    registry = ToolRegistry()
    registry.register(PublishSubagentProposalTool(manager))
    registry.add_auto_approve_policy("manage_subagents")
    try:
        result = await registry.execute("publish_subagent_proposal", {"conversation_id": "child", "review_token": "token"})
        assert not result.success and "confirmation" in str(result.error).lower()
    finally:
        await manager.close()


async def test_publication_preserves_exact_reviewed_python_bytes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "file.py"
    path.write_text("value=1\n")

    class Manager:
        def publish_staged(self, _identity: str, _token: str) -> ReviewResult:
            path.write_text("value=2\n")
            return ReviewResult(("file.py",), True)

    registry = ToolRegistry()
    registry.register(PublishSubagentProposalTool(Manager()))
    registry.add_auto_approve_policy("publish_subagent_proposal")
    result = await registry.execute("publish_subagent_proposal", {"conversation_id": "child", "review_token": "token"})
    assert result.success
    assert path.read_text() == "value=2\n"
