"""Fallback CLI dispatch must use the acting agent's authorization scope."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.agents.pool import create_scoped_registry
from henchman.cli.app import _process_tool_calls
from henchman.cli.tool_executor import ToolExecutor
from henchman.core.agent import Agent
from henchman.core.events import AgentEvent
from henchman.providers.base import Message, ToolCall
from henchman.providers.ollama import OllamaProvider
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry
from henchman.utils.validation import validate_message_sequence


class SpyTool(Tool):
    description = "Record scoped execution"

    def __init__(self, name: str, kind: ToolKind = ToolKind.READ) -> None:
        self._name = name
        self._kind = kind
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def kind(self) -> ToolKind:
        return self._kind

    async def execute(self, **params: object) -> ToolResult:
        self.calls += 1
        return ToolResult("Executed within scope")


def _executor(root: ToolRegistry) -> ToolExecutor:
    return ToolExecutor(
        output_handler=MagicMock(),
        tool_manager=cast(Any, SimpleNamespace(registry=root)),
        provider=OllamaProvider(),
    )


@pytest.mark.parametrize("dispatch", ["executor", "headless"])
@pytest.mark.parametrize("allowed", [False, True])
async def test_dispatch_uses_actor_registry_and_never_executes_root_only_tools(
    dispatch: str,
    allowed: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = ToolRegistry()
    permitted, excluded = SpyTool("allowed"), SpyTool("root_only")
    root.register(permitted)
    root.register(excluded)
    scoped = create_scoped_registry(root, ["allowed"])
    root_execute = AsyncMock(wraps=root.execute)
    scoped_execute = AsyncMock(wraps=scoped.execute)
    monkeypatch.setattr(root, "execute", root_execute)
    monkeypatch.setattr(scoped, "execute", scoped_execute)
    agent = Agent(OllamaProvider(), tool_registry=scoped)
    call = ToolCall("request", "allowed" if allowed else "root_only", {})
    agent.messages.append(Message(role="assistant", tool_calls=[call]))

    if dispatch == "executor":
        responded: set[str] = set()
        await _executor(root)._execute_and_record_tool_call(call, agent, responded)
        assert responded == {"request"}
    else:
        events: list[AgentEvent] = []
        pending = [call]
        await _process_tool_calls(
            SimpleNamespace(agent=agent, tool_registry=root),
            pending,
            events.append,
        )
        assert pending == []
        assert events[-1].data["success"] is allowed

    root_execute.assert_not_awaited()
    scoped_execute.assert_awaited_once_with(call.name, {})
    assert excluded.calls == 0
    assert permitted.calls == int(allowed)
    assert agent.turn.tool_count == 1
    validate_message_sequence(agent.messages)
    assert agent.messages[-1].tool_call_id == "request"


@pytest.mark.parametrize("actor_approved", [False, True])
def test_confirmation_classification_uses_actor_local_approval(actor_approved: bool) -> None:
    root, actor = ToolRegistry(), ToolRegistry()
    root.register(SpyTool("write", ToolKind.WRITE))
    actor.register(SpyTool("write", ToolKind.WRITE))
    (actor if actor_approved else root).add_auto_approve_policy("write")
    call = ToolCall("request", "write", {})
    parallel, sequential = _executor(root)._split_tools_by_confirmation_requirement([call], actor)
    assert parallel == ([call] if actor_approved else [])
    assert sequential == ([] if actor_approved else [call])
