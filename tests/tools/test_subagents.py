"""Dynamic subagent tool contracts and runtime binding."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from henchman.agents.subagents import BackgroundSubagentManager
from henchman.core.events import AgentEvent, EventType
from henchman.tools.base import ToolKind
from henchman.tools.builtins.subagents import InvokeSubagentTool, ManageSubagentsTool


def create_manager() -> BackgroundSubagentManager:
    async def runner(_agent: Any, _prompt: str) -> AsyncIterator[AgentEvent]:
        await asyncio.Event().wait()
        yield AgentEvent(EventType.CONTENT, _prompt)

    return BackgroundSubagentManager(
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
