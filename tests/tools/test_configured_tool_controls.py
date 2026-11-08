"""Configured approval/backend controls govern real tools and inherited scopes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.tool_manager import ToolManager
from henchman.config.schema import Settings
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall
from henchman.tools.access_policy import ToolAccessError, ToolAccessPolicy
from henchman.tools.base import ConfirmationRequest, ToolKind
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.policy import evaluate_effective_policy
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry


def manager(tmp_path: Path, *, auto_approve_read: bool = False) -> ToolManager:
    result = ToolManager(Settings(tools={"auto_approve_read": auto_approve_read}))
    result.bind_runtime(project_root=tmp_path)
    result.registry.register(ReadFileTool())
    return result


def test_synchronous_policy_requires_read_approval_even_for_preset_auto_approval() -> None:
    decision = evaluate_effective_policy(
        ReadFileTool(), {"path": "data"}, plan_mode_active=True,
        auto_approved=True, require_read_confirmation=True,
    )
    assert decision.allowed and decision.effective_kind is ToolKind.READ
    assert decision.confirmation is not None
    assert decision.confirmation.risk_level == "low"


def test_read_requirement_preserves_custom_confirmation_without_duplicate_policy_calls() -> None:
    class CustomRead(ReadFileTool):
        policy_calls = 0

        def needs_confirmation(self, params: dict[str, object]) -> ConfirmationRequest:
            self.policy_calls += 1
            return ConfirmationRequest(self.name, "Protected read", params, risk_level="high")

    tool = CustomRead()
    decision = evaluate_effective_policy(
        tool, {"path": "data"}, plan_mode_active=False,
        auto_approved=False, require_read_confirmation=True,
    )
    assert decision.confirmation is not None and decision.confirmation.risk_level == "high"
    assert tool.policy_calls == 1


async def test_false_requires_confirmation_before_native_read(tmp_path: Path) -> None:
    target = tmp_path / "data"
    target.write_text("private test content")
    registry = manager(tmp_path).registry
    registry.add_auto_approve_policy("read_file")
    decision = registry.evaluate_policy("read_file", {"path": str(target)})
    assert decision is not None and decision.confirmation is not None
    result = await registry.execute("read_file", {"path": str(target)})
    assert not result.success and "confirmation" in result.content.lower()
    assert "private test content" not in result.content


async def test_true_preserves_default_read_behavior(tmp_path: Path) -> None:
    target = tmp_path / "data"
    target.write_text("public test content")
    result = await manager(tmp_path, auto_approve_read=True).registry.execute("read_file", {"path": str(target)})
    assert result.success and result.content == "public test content"


async def test_read_approval_grant_reused_only_for_same_target(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_text("first value")
    second.write_text("second value")
    registry = manager(tmp_path).registry
    approve = AsyncMock(return_value=True)
    registry.set_confirmation_handler(approve)
    for target in (first, first, second):
        assert (await registry.execute("read_file", {"path": str(target)})).success
    assert approve.await_count == 2
    registry.clear_grants()
    approve.return_value = False
    assert not (await registry.execute("read_file", {"path": str(first)})).success
    assert approve.await_count == 3


async def test_scoped_and_late_tools_cannot_widen_parent_requirement(tmp_path: Path) -> None:
    parent = manager(tmp_path).registry
    child = ScopedToolRegistry(parent, None, inherit_auto_approve=True)
    parent.restrict_tool_settings(Settings().tools, project_root=tmp_path)
    child.set_read_confirmation_required(False)
    child.add_auto_approve_policy("read_file")
    target = tmp_path / "late"
    target.write_text("late value")
    parent.unregister("read_file")
    parent.register(ReadFileTool())
    assert not (await child.execute("read_file", {"path": str(target)})).success
    parent.set_confirmation_handler(AsyncMock(return_value=True))
    assert (await child.execute("read_file", {"path": str(target)})).success


async def test_read_policy_change_during_approval_invalidates_dispatch(tmp_path: Path) -> None:
    target = tmp_path / "data"
    target.write_text("protected")
    registry = manager(tmp_path).registry
    entered, release = asyncio.Event(), asyncio.Event()

    async def approve(_request: ConfirmationRequest) -> bool:
        entered.set()
        await release.wait()
        return True

    registry.set_confirmation_handler(approve)
    pending = asyncio.create_task(registry.execute("read_file", {"path": str(target)}))
    await asyncio.wait_for(entered.wait(), 1)
    registry.set_read_confirmation_required(False)
    registry.set_read_confirmation_required(True)
    release.set()
    result = await pending
    assert not result.success and "scope changed" in result.content
    assert not registry.list_approval_grants()


async def test_explicit_yes_approves_read_requirement(tmp_path: Path) -> None:
    target = tmp_path / "data"
    target.write_text("approved")
    tools = manager(tmp_path)
    tools.set_auto_approve(auto_approve=True)
    tools.set_confirmation_handler()
    assert (await tools.registry.execute("read_file", {"path": str(target)})).success


class LocalProvider(ModelProvider):
    name = "offline-fixture"
    default_model = "test-model"

    def __init__(self, target: Path) -> None:
        self.target = target
        self.tool_results: list[str] = []

    async def chat_completion_stream(self, messages: list[Message], **_kwargs: Any) -> AsyncIterator[StreamChunk]:
        results = [message.content or "" for message in messages if message.role == "tool"]
        if results:
            self.tool_results.extend(results)
            yield StreamChunk(content="Done", finish_reason=FinishReason.STOP)
        else:
            yield StreamChunk(tool_calls=[ToolCall("read-1", "read_file", {"path": str(self.target)})],
                              finish_reason=FinishReason.TOOL_CALLS)


async def test_orchestrator_cached_future_and_dynamic_read_controls(tmp_path: Path) -> None:
    target = tmp_path / "data"
    target.write_text("must not be read")
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    provider = LocalProvider(target)
    orchestrator = Orchestrator(provider, settings=Settings(agents={"allow_delegation": True}, tools={"auto_approve_read": False}), tool_registry=registry)
    try:
        cached = orchestrator.pool.get_agent("explorer")
        for agent in (orchestrator.tech_lead, cached, orchestrator.pool.get_agent("engineer")):
            verdict = agent.tool_registry.evaluate_policy("read_file", {"path": str(target)})
            assert verdict is not None and verdict.confirmation is not None
            assert not (await agent.tool_registry.execute("read_file", {"path": str(target)})).success
        orchestrator.subagents.spawn("read", role="reader", system_prompt="Read task", tools=["read_file"])
        await asyncio.wait_for(orchestrator.subagents.wait_for_notification(), 3)
        assert provider.tool_results
        assert all("must not be read" not in result for result in provider.tool_results)
        assert "confirmation" in provider.tool_results[0].lower()
    finally:
        await orchestrator.aclose()


@pytest.mark.parametrize("boundary", ["manager", "policy", "registry", "orchestrator"])
def test_docker_request_fails_before_any_dispatch(tmp_path: Path, boundary: str) -> None:
    settings = Settings(tools={"sandbox": "docker"})
    target = tmp_path / "untouched"
    registry = ToolRegistry()
    registry.register(ShellTool())
    registry.add_auto_approve_policy("shell")
    with pytest.raises(ToolAccessError, match=r"tools\.sandbox.*docker.*unsupported"):
        if boundary == "manager":
            ToolManager(settings)
        elif boundary == "policy":
            ToolAccessPolicy.from_settings(settings.tools, project_root=tmp_path)
        elif boundary == "registry":
            registry.restrict_tool_settings(settings.tools, project_root=tmp_path)
        else:
            Orchestrator(LocalProvider(target), settings=settings, tool_registry=registry)
    assert not target.exists()
