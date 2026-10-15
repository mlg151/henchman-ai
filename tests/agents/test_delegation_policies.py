"""Delegation and cached specialist scopes must enforce current tool policies."""

from collections.abc import AsyncIterator
from functools import partial
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.agents.pool import create_scoped_registry
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.registry import ToolRegistry


def scripted_provider(*responses: StreamChunk) -> MagicMock:
    provider = MagicMock(spec=ModelProvider)
    provider.estimate_input_tokens.side_effect = partial(ModelProvider.estimate_input_tokens, provider)
    provider.prepare_output_budget.side_effect = partial(ModelProvider.prepare_output_budget, provider)
    queue = iter(responses)

    async def stream(*_args: object, **_kwargs: object) -> AsyncIterator[StreamChunk]:
        yield next(queue, StreamChunk(content="Stopped.", finish_reason=FinishReason.STOP))

    provider.chat_completion_stream.side_effect = stream
    return provider


def command_arguments(path: Path) -> dict[str, object]:
    return {
        "code": f"from pathlib import Path; Path({str(path)!r}).write_text('ran')",
        "background": False,
    }


def delegation_fixture(path: Path) -> tuple[Orchestrator, MagicMock]:
    lead = scripted_provider(StreamChunk(
        tool_calls=[ToolCall("delegate-1", "delegate_task", {
            "agent": "engineer", "task": "Create the marker",
        })],
        finish_reason=FinishReason.TOOL_CALLS,
    ))
    child = scripted_provider(StreamChunk(
        tool_calls=[ToolCall("command-1", "python_exec", command_arguments(path))],
        finish_reason=FinishReason.TOOL_CALLS,
    ))
    orchestrator = Orchestrator(default_provider=lead)
    orchestrator.settings.agents.max_delegation_retries = 0
    orchestrator.tool_registry.register(PythonExecTool())
    specialist = orchestrator.pool.get_agent("engineer")
    specialist.provider = child
    specialist._stall.enabled = False
    return orchestrator, child


@pytest.mark.asyncio
@pytest.mark.parametrize("policy", ["plan", "deny", "unregistered"])
async def test_delegation_policy_blocks_before_child_model(
    tmp_path: Path, policy: str,
) -> None:
    marker = tmp_path / "ran.txt"
    orchestrator, child = delegation_fixture(marker)
    handler = AsyncMock(return_value=False)
    if policy == "plan":
        orchestrator.tool_registry.set_plan_mode(enabled=True)
    elif policy == "deny":
        orchestrator.tool_registry.set_confirmation_handler(handler)
    else:
        orchestrator.tool_registry.unregister("delegate_task")

    events = [event async for event in orchestrator.run("Create the marker")]

    assert not marker.exists()
    child.chat_completion_stream.assert_not_called()
    result = next(event for event in events if event.type == EventType.TOOL_CALL_RESULT)
    assert result.data["tool_call_id"] == "delegate-1"
    assert result.data["success"] is False
    assert not any(event.type == EventType.AGENT_DELEGATED for event in events)
    if policy == "deny":
        handler.assert_awaited_once()
        assert handler.call_args.args[0].tool_name == "delegate_task"


@pytest.mark.asyncio
async def test_explicit_auto_approval_allows_real_delegated_command(tmp_path: Path) -> None:
    marker = tmp_path / "ran.txt"
    orchestrator, child = delegation_fixture(marker)
    handler = AsyncMock(return_value=False)
    orchestrator.tool_registry.set_confirmation_handler(handler)
    orchestrator.tool_registry.add_auto_approve_policy("delegate_task")
    specialist = orchestrator.pool.get_agent("engineer")
    specialist.tool_registry.add_auto_approve_policy("python_exec")

    events = [event async for event in orchestrator.run("Create the marker")]

    assert marker.read_text() == "ran"
    assert child.chat_completion_stream.call_count >= 2
    handler.assert_not_awaited()
    assert any(event.type == EventType.AGENT_DELEGATED for event in events)


@pytest.mark.asyncio
async def test_unallowed_role_cannot_hallucinate_delegation(tmp_path: Path) -> None:
    orchestrator, child = delegation_fixture(tmp_path / "ran.txt")
    explorer = orchestrator.pool.get_agent("explorer")
    assert explorer.tool_registry.get("delegate_task") is None
    events = [event async for event in orchestrator.run_direct("explorer", "Inspect")]
    child.chat_completion_stream.assert_not_called()
    assert not any(event.type == EventType.AGENT_DELEGATED for event in events)
    result = next(event for event in events if event.type == EventType.TOOL_CALL_RESULT)
    assert result.data["success"] is False
    assert "not found" in result.data["result"]


@pytest.mark.asyncio
async def test_cached_scope_observes_parent_plan_mode_changes(tmp_path: Path) -> None:
    parent = ToolRegistry()
    parent.register(PythonExecTool())
    scoped = create_scoped_registry(parent, ["python_exec"], auto_approve=["python_exec"])
    nested = create_scoped_registry(scoped, ["python_exec"], auto_approve=["python_exec"])
    marker = tmp_path / "ran.txt"

    parent.set_plan_mode(enabled=True)
    result = await nested.execute("python_exec", command_arguments(marker))
    assert not result.success
    assert "Plan Mode" in result.content
    assert not marker.exists()

    parent.set_plan_mode(enabled=False)
    assert (await nested.execute("python_exec", command_arguments(marker))).success
    assert marker.read_text() == "ran"


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_handler", [False, True])
async def test_cached_scope_observes_new_parent_confirmation(
    tmp_path: Path, initial_handler: bool,
) -> None:
    parent = ToolRegistry()
    parent.register(PythonExecTool())
    approve = AsyncMock(return_value=True)
    if initial_handler:
        parent.set_confirmation_handler(approve)
    scoped = create_scoped_registry(parent, ["python_exec"])
    deny = AsyncMock(return_value=False)
    parent.set_confirmation_handler(deny)
    marker = tmp_path / "ran.txt"

    result = await scoped.execute("python_exec", command_arguments(marker))

    assert not result.success
    assert not marker.exists()
    approve.assert_not_awaited()
    deny.assert_awaited_once()

    parent.set_confirmation_handler(approve)
    assert (await scoped.execute("python_exec", command_arguments(marker))).success
    assert marker.read_text() == "ran"
