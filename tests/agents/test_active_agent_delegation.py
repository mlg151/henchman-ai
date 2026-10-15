"""Delegations cannot reset an active cached agent's conversation."""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from copy import deepcopy
from typing import Any

import pytest

from henchman.agents.config import AgentConfig
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_types import AgentLoopParams, DelegationParams
from henchman.config.schema import Settings
from henchman.core.events import EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from henchman.utils.validation import validate_message_sequence


class ScriptedProvider(ModelProvider):
    name = "active-agent-test"

    def __init__(self, *steps: StreamChunk | Exception | None) -> None:
        self.steps = list(steps)
        self.requests: list[list[Message]] = []
        self.waiting = asyncio.Event()

    async def chat_completion_stream(
        self, messages: list[Message], tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        validate_message_sequence(messages)
        self.requests.append(deepcopy(messages))
        step = self.steps.pop(0) if self.steps else response()
        if isinstance(step, Exception):
            raise step
        if step is None:
            self.waiting.set()
            await asyncio.Event().wait()
        else:
            yield step


def response() -> StreamChunk:
    return StreamChunk(content="Finished response.", finish_reason=FinishReason.STOP)


def delegate(target: str, call_id: str) -> StreamChunk:
    return StreamChunk(
        tool_calls=[ToolCall(call_id, "delegate_task", {
            "agent": target, "task": "Delegated task",
            "completion_requirement": "response",
        })],
        finish_reason=FinishReason.TOOL_CALLS,
    )


def orchestrator(provider: ModelProvider, *, retries: int = 0) -> Orchestrator:
    settings = Settings()
    settings.agents.max_delegation_retries = retries
    for role in ("tech_lead", "explorer"):
        settings.agents.agents[role] = AgentConfig(
            name=role, role=role, description="Test agent", tools=["delegate_task"],
            auto_approve=["delegate_task"], system_prompt=f"You are {role}.",
        )
    return Orchestrator(provider, settings=settings)


def metrics_state(orch: Orchestrator) -> dict[str, Any]:
    """Snapshot values, including counters whose classes use identity equality."""
    return deepcopy({
        name: vars(value) if hasattr(value, "__dict__") else value
        for name, value in vars(orch.metrics).items()
    })


@pytest.mark.parametrize("role", ["tech_lead", "explorer"])
async def test_self_delegation_is_balanced_without_reset_and_parent_continues(role: str) -> None:
    provider = ScriptedProvider(delegate(role, "self"), response())
    orch = orchestrator(provider, retries=1)
    agent = orch.pool.get_agent(role)
    agent._stall.enabled = False
    stream = (
        orch.run("ORIGINAL USER TASK") if role == "tech_lead"
        else orch.run_direct(role, "ORIGINAL USER TASK")
    )
    events = [event async for event in stream]

    failures = [event for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert len(failures) == 1
    assert failures[0].data["tool_call_id"] == "self"
    assert failures[0].data["success"] is False
    assert "already active" in failures[0].data["result"]
    assert len(provider.requests) == 2
    assert any(message.content == "ORIGINAL USER TASK" for message in agent.messages)
    assert agent.messages[-1].content == "Finished response."
    validate_message_sequence(agent.messages)
    assert len([m for m in agent.messages if m.tool_call_id == "self"]) == 1


async def test_child_cannot_delegate_to_active_ancestor_even_under_alias() -> None:
    parent = ScriptedProvider(delegate("explorer", "parent"), response())
    child = ScriptedProvider(delegate("leader_alias", "ancestor"), response())
    orch = orchestrator(parent)
    orch.pool.configs["leader_alias"] = orch.pool.configs["tech_lead"]
    orch.pool._agents["leader_alias"] = orch.tech_lead
    explorer = orch.pool.get_agent("explorer")
    explorer.provider = child
    explorer._stall.enabled = False
    events = [event async for event in orch.run("ORIGINAL ROOT TASK")]

    failure = next(event for event in events if (
        event.type == EventType.TOOL_CALL_RESULT
        and event.data["tool_call_id"] == "ancestor"
    ))
    assert failure.data["success"] is False
    assert "already active" in failure.data["result"]
    assert len(parent.requests) == len(child.requests) == 2
    assert any(m.content == "ORIGINAL ROOT TASK" for m in orch.tech_lead.messages)
    assert orch.tech_lead.messages[-1].content == "Finished response."
    validate_message_sequence(orch.tech_lead.messages)
    validate_message_sequence(explorer.messages)


async def test_reservation_covers_started_yield_and_releases_on_close() -> None:
    provider = ScriptedProvider(response())
    orch = orchestrator(provider)
    runner = orch.delegation_runner
    params = DelegationParams("explorer", "First task", {"completion_requirement": "response"})
    stream = runner.run_delegation(params)
    assert isinstance(stream, AsyncGenerator)
    started = await anext(stream)
    assert started.type == EventType.AGENT_STARTED
    target = orch.pool.get_agent("explorer")
    target.messages.append(Message(role="user", content="PRESERVE RESERVED HISTORY"))
    before = deepcopy(target.messages)
    second = [event async for event in runner.run_delegation(
        DelegationParams("explorer", "Second task")
    )]
    assert second[0].type == EventType.ERROR
    assert "already active" in str(second[0].data)
    assert target.messages == before
    assert not provider.requests
    await stream.aclose()
    third = [event async for event in runner.run_delegation(
        DelegationParams("explorer", "Third task", {"completion_requirement": "response"})
    )]
    assert any(event.type == EventType.AGENT_COMPLETED for event in third)
    assert len(provider.requests) == 1


async def test_cancelled_nested_run_releases_parent_and_child_for_reuse() -> None:
    parent = ScriptedProvider(delegate("explorer", "cancelled"), response())
    child = ScriptedProvider(None, response())
    orch = orchestrator(parent)
    explorer = orch.pool.get_agent("explorer")
    explorer.provider = child

    async def consume() -> None:
        async for _event in orch.run("Original task"):
            pass

    task = asyncio.create_task(consume())
    await asyncio.wait_for(child.waiting.wait(), timeout=3)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    validate_message_sequence(orch.tech_lead.messages)
    validate_message_sequence(explorer.messages)
    parent.steps = [delegate("explorer", "reused"), response()]
    events = [event async for event in orch.run("Retry after cancellation")]
    result = next(event for event in events if (
        event.type == EventType.TOOL_CALL_RESULT
        and event.data["tool_call_id"] == "reused"
    ))
    assert result.data["success"] is True
    validate_message_sequence(orch.tech_lead.messages)
    validate_message_sequence(explorer.messages)


async def test_failed_child_retry_and_subsequent_successful_run_release_claims() -> None:
    parent = ScriptedProvider(delegate("explorer", "first"), response())
    child = ScriptedProvider(RuntimeError("First attempt failed"), response(), response())
    orch = orchestrator(parent, retries=1)
    explorer = orch.pool.get_agent("explorer")
    explorer.provider = child
    explorer._stall.enabled = False
    first = [event async for event in orch.run("First root task")]
    assert any(event.type == EventType.TOOL_CALL_RESULT and event.data["success"] for event in first)
    parent.steps = [delegate("explorer", "second"), response()]
    second = [event async for event in orch.run("Second root task")]
    assert any(event.type == EventType.TOOL_CALL_RESULT and event.data["success"] for event in second)
    assert len(child.requests) == 3
    validate_message_sequence(orch.tech_lead.messages)
    validate_message_sequence(explorer.messages)


async def test_concurrent_loop_owner_rejected_without_touching_active_history() -> None:
    provider = ScriptedProvider(None, response())
    orch = orchestrator(provider)
    params = AgentLoopParams(agent=orch.tech_lead, input_text="First task")

    async def consume() -> None:
        async for _event in orch.execution_controller.run_agent_loop(params):
            pass

    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.waiting.wait(), timeout=3)
    before = deepcopy(orch.tech_lead.messages)
    try:
        with pytest.raises(ValueError, match="already active"):
            async for _event in orch.execution_controller.run_agent_loop(
                AgentLoopParams(agent=orch.tech_lead, input_text="Concurrent task")
            ):
                pass
        assert orch.tech_lead.messages == before
        assert len(provider.requests) == 1
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


def test_claims_use_instance_identity_and_reject_running_owner_reentry() -> None:
    orch = orchestrator(ScriptedProvider())
    first = orch.tech_lead
    second = orch.pool.get_agent("explorer")
    second.identity = first.identity
    owner = object()
    with (
        orch.pool.claim_agent(first, owner=owner, running=True),
        orch.pool.claim_agent(second, owner=object(), running=True),
        pytest.raises(ValueError, match="already active"),
        orch.pool.claim_agent(first, owner=owner, running=True),
    ):
        pytest.fail("The same running owner must not reenter")
    with orch.pool.claim_agent(first, owner=object(), running=True):
        pass


async def test_closing_root_loop_at_first_yield_releases_claim() -> None:
    orch = orchestrator(ScriptedProvider(response()))
    params = AgentLoopParams(agent=orch.tech_lead, input_text="Interrupted task")
    stream = orch.execution_controller.run_agent_loop(params)
    await anext(stream)
    await stream.aclose()
    events = [event async for event in orch.run("Fresh task")]
    assert any(event.type == EventType.FINISHED for event in events)
    assert orch.tech_lead.messages[-1].content == "Finished response."
    validate_message_sequence(orch.tech_lead.messages)


@pytest.mark.parametrize("first_direct", [False, True])
@pytest.mark.parametrize("second_direct", [False, True])
async def test_public_run_admission_preserves_shared_state_before_first_yield(
    first_direct: bool, second_direct: bool,
) -> None:
    orch = orchestrator(ScriptedProvider())
    first = (
        orch.run_direct("explorer", "ORIGINAL") if first_direct
        else orch.run("ORIGINAL")
    )
    assert isinstance(first, AsyncGenerator)
    assert (await anext(first)).type == EventType.AGENT_STARTED
    ledger = orch.ledger
    orch.metrics.performance.files_accessed["preserved.py"] = 3
    metrics = metrics_state(orch)
    status = orch.last_completion_status
    agents = dict(orch.pool._agents)
    second = (
        orch.run_direct("engineer", "REJECTED") if second_direct
        else orch.run("REJECTED")
    )
    assert isinstance(second, AsyncGenerator)
    try:
        with pytest.raises(ValueError, match="already active"):
            await anext(second)
        assert orch.ledger is ledger
        assert orch.delegation_runner.ledger is ledger
        assert metrics_state(orch) == metrics
        assert orch.last_completion_status is status
        assert orch.pool._agents == agents
    finally:
        await second.aclose()
        await first.aclose()
    events = [event async for event in orch.run("Fresh run after close")]
    assert any(event.type == EventType.FINISHED for event in events)


async def test_public_first_yield_reserves_target_against_direct_delegation() -> None:
    orch = orchestrator(ScriptedProvider())
    orch.tech_lead.messages.append(Message(role="user", content="PRESERVE HISTORY"))
    before = deepcopy(orch.tech_lead.messages)
    stream = orch.run("New task")
    assert isinstance(stream, AsyncGenerator)
    await anext(stream)
    try:
        rejected = [event async for event in orch.delegation_runner.run_delegation(
            DelegationParams("tech_lead", "Concurrent delegation")
        )]
        assert rejected[0].type == EventType.ERROR
        assert "already active" in str(rejected[0].data)
        assert orch.tech_lead.messages == before
    finally:
        await stream.aclose()


async def test_public_run_rejects_active_lower_level_loop_before_preparation() -> None:
    provider = ScriptedProvider(None)
    orch = orchestrator(provider)

    async def consume() -> None:
        async for _event in orch.execution_controller.run_agent_loop(
            AgentLoopParams(agent=orch.tech_lead, input_text="Active task")
        ):
            pass

    task = asyncio.create_task(consume())
    await asyncio.wait_for(provider.waiting.wait(), timeout=3)
    ledger = orch.ledger
    metrics = metrics_state(orch)
    status = orch.last_completion_status
    try:
        with pytest.raises(ValueError, match="already active"):
            async for _event in orch.run("REJECTED"):
                pass
        assert orch.ledger is ledger
        assert orch.delegation_runner.ledger is ledger
        assert metrics_state(orch) == metrics
        assert orch.last_completion_status is status
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


async def test_public_admission_released_when_direct_resolution_raises() -> None:
    orch = orchestrator(ScriptedProvider(response()))
    with pytest.raises(ValueError, match="not configured"):
        async for _event in orch.run_direct("missing", "Invalid role"):
            pass
    events = [event async for event in orch.run("Valid run")]
    assert any(event.type == EventType.FINISHED for event in events)
