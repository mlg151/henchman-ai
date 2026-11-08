"""Shared descendant capacity is reserved before construction and held through cleanup."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic import ValidationError

from henchman.agents.delegation_admission import DelegationAdmission, DelegationAdmissionError
from henchman.agents.subagents import BackgroundSubagentManager, subagent_actor
from henchman.config.schema import AgentSettings
from henchman.core.events import AgentEvent, EventType


@pytest.mark.parametrize("value", [True, False, -1, 1.5, "2", None])
def test_configuration_requires_nonnegative_strict_integer(value: object) -> None:
    with pytest.raises(ValidationError):
        AgentSettings(max_concurrent_delegations=value)


def test_default_and_zero_have_explicit_meaning() -> None:
    assert AgentSettings().max_concurrent_delegations == 4
    admission = DelegationAdmission(0)
    with pytest.raises(DelegationAdmissionError) as denied:
        admission.reserve()
    assert denied.value.payload == {
        "code": "delegation_capacity", "limit": 0, "active": 0, "retryable": False,
    }


def test_retired_generation_cannot_reserve_and_release_is_idempotent() -> None:
    admission = DelegationAdmission(1)
    generation = admission.generation
    lease = admission.reserve()
    admission.retire()
    with pytest.raises(DelegationAdmissionError):
        admission.reopen()
    lease.release()
    lease.release()
    admission.reopen()
    with pytest.raises(DelegationAdmissionError) as denied:
        admission.reserve(generation=generation)
    assert denied.value.payload["code"] == "delegation_retired"
    assert admission.active == 0


def manager_for(admission: DelegationAdmission, runner: Any,
                created: list[str] | None = None) -> BackgroundSubagentManager:
    def factory(_role: str, _prompt: str, _tools: list[str], identity: str) -> str:
        if created is not None:
            created.append(identity)
        return identity
    return BackgroundSubagentManager(factory, runner, available_tools=lambda _: ["invoke_subagent"],
                                     admission=admission)


def spawn(manager: BackgroundSubagentManager) -> str:
    return manager.spawn("task", role="child", system_prompt="system", tools=["invoke_subagent"]).conversation_id


async def test_racing_spawns_reserve_before_factory_and_nested_refuses_without_wait() -> None:
    admission = DelegationAdmission(2)
    created: list[str] = []
    nested: list[str] = []
    gate = asyncio.Event()
    async def runner(identity: str, _: str) -> AsyncIterator[AgentEvent]:
        with pytest.raises(DelegationAdmissionError) as denied:
            spawn(manager)
        nested.append(str(denied.value.payload["code"]))
        await gate.wait()
        yield AgentEvent(EventType.CONTENT, identity)
    manager = manager_for(admission, runner, created)
    async def attempt() -> str:
        try:
            return spawn(manager)
        except DelegationAdmissionError:
            return "denied"
    try:
        results = await asyncio.gather(*(attempt() for _ in range(20)))
        await asyncio.sleep(0)
        assert results.count("denied") == 18
        assert len(created) == admission.active == 2
        assert nested == ["delegation_capacity"] * 2
    finally:
        await manager.close()
    assert admission.active == 0


async def test_completed_followup_reacquires_without_queuing_denied_input() -> None:
    admission = DelegationAdmission(1)
    seen: list[str] = []
    async def runner(_: str, prompt: str) -> AsyncIterator[AgentEvent]:
        seen.append(prompt)
        yield AgentEvent(EventType.CONTENT, prompt)
    manager = manager_for(admission, runner)
    try:
        identity = spawn(manager)
        await manager.wait_for_notification()
        assert admission.active == 0
        other = admission.reserve()
        with pytest.raises(DelegationAdmissionError):
            await manager.send_message(identity, "denied followup")
        other.release()
        await manager.send_message(identity, "accepted followup")
        await manager.wait_for_notification()
        assert seen == ["task", "accepted followup"]
        assert admission.active == 0
    finally:
        await manager.close()


async def test_cancel_before_worker_entry_releases_reservation() -> None:
    admission = DelegationAdmission(1)
    entered = False
    async def runner(_: str, prompt: str) -> AsyncIterator[AgentEvent]:
        nonlocal entered
        entered = True
        yield AgentEvent(EventType.CONTENT, prompt)
    manager = manager_for(admission, runner)
    identity = spawn(manager)
    await manager.cancel(identity)
    assert not entered
    assert admission.active == 0
    await manager.close()


async def test_cancel_holds_slot_until_joined_cleanup_even_if_caller_cancelled() -> None:
    admission = DelegationAdmission(1)
    started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def runner(_: str, prompt: str) -> AsyncIterator[AgentEvent]:
        started.set()
        try:
            await asyncio.Event().wait()
            yield AgentEvent(EventType.CONTENT, prompt)
        finally:
            cleaning.set()
            await release.wait()
    manager = manager_for(admission, runner)
    identity = spawn(manager)
    await started.wait()
    task = asyncio.create_task(manager.cancel(identity))
    await cleaning.wait()
    task.cancel("first cancellation")
    await asyncio.sleep(0)
    assert not task.done()
    assert admission.active == 1
    with pytest.raises(DelegationAdmissionError):
        spawn(manager)
    release.set()
    with pytest.raises(asyncio.CancelledError, match="first cancellation"):
        await task
    assert admission.active == 0
    await manager.close()


async def test_factory_failure_releases_and_reset_rejects_old_conversation() -> None:
    admission = DelegationAdmission(1)
    async def runner(_: str, prompt: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.CONTENT, prompt)
    manager = manager_for(admission, runner)
    original = manager._factory
    def fail(*_args: object) -> Any:
        raise ValueError("factory failed")
    manager._factory = fail
    with pytest.raises(ValueError, match="factory failed"):
        spawn(manager)
    assert admission.active == 0
    manager._factory = original
    identity = spawn(manager)
    await manager.wait_for_notification()
    await manager.cancel_all()
    with pytest.raises(DelegationAdmissionError):
        await manager.send_message(identity, "stale")
    with subagent_actor(identity), pytest.raises(DelegationAdmissionError):
        spawn(manager)
    fresh = spawn(manager)
    assert fresh != identity
    await manager.close()


def runtime(*, limit: int = 1, retries: int = 0, steps: tuple[Any, ...] = ()) -> Any:
    from henchman.agents.config import AgentConfig
    from henchman.agents.orchestrator import Orchestrator
    from henchman.config.schema import Settings
    from henchman.providers.base import FinishReason, ModelProvider, StreamChunk
    class Provider(ModelProvider):
        name = "admission-fixture"
        calls = 0
        async def chat_completion_stream(self, messages: Any, tools: Any = None, **kwargs: Any) -> AsyncIterator[StreamChunk]:
            index = self.calls
            self.calls += 1
            yield steps[index] if index < len(steps) else StreamChunk(content="Done", finish_reason=FinishReason.STOP)
    settings = Settings()
    settings.agents.max_concurrent_delegations = limit
    settings.agents.max_delegation_retries = retries
    for role in ("tech_lead", "explorer", "engineer"):
        settings.agents.agents[role] = AgentConfig(name=role, role=role, description="Fixture",
            tools=["delegate_task", "invoke_subagent"], system_prompt="Fixture", auto_approve=["delegate_task"])
    return Orchestrator(Provider(), settings=settings)


async def test_named_and_dynamic_routes_share_capacity_before_role_creation() -> None:
    from henchman.agents.orchestrator_types import DelegationParams
    orch = runtime()
    runner = orch.delegation_runner
    assert runner.admission is orch.subagents.admission
    held = spawn(orch.subagents)
    assert "explorer" not in orch.pool._agents
    events = [event async for event in runner.run_delegation(DelegationParams("explorer", "task"))]
    assert events[0].type == EventType.ERROR
    assert events[0].data["admission"]["code"] == "delegation_capacity"
    assert "explorer" not in orch.pool._agents
    await orch.subagents.cancel(held)
    stream = runner.run_delegation(DelegationParams("explorer", "task", {"completion_requirement": "response"}))
    assert (await anext(stream)).type == EventType.AGENT_STARTED
    assert runner.admission.active == 1
    with pytest.raises(DelegationAdmissionError):
        spawn(orch.subagents)
    await stream.aclose()
    assert runner.admission.active == 0
    await orch.aclose()


async def test_capacity_denial_never_auto_retries_and_primary_is_excluded() -> None:
    from henchman.providers.base import FinishReason, StreamChunk, ToolCall
    orch = runtime(limit=0, retries=3, steps=(StreamChunk(tool_calls=[ToolCall("child", "delegate_task", {
        "agent": "explorer", "task": "task", "completion_requirement": "response",
    })], finish_reason=FinishReason.TOOL_CALLS),))
    calls = 0
    original = orch.delegation_runner.run_delegation
    async def observed(*args: Any, **kwargs: Any) -> AsyncIterator[AgentEvent]:
        nonlocal calls
        calls += 1
        async for event in original(*args, **kwargs):
            yield event
    orch.delegation_runner.run_delegation = observed
    events = [event async for event in orch.run("Task")]
    assert calls == 1
    assert orch.default_provider.calls == 2
    assert "explorer" not in orch.pool._agents
    result = next(event.data for event in events if event.type == EventType.TOOL_CALL_RESULT)
    assert result["success"] is False
    assert result["admission"]["retryable"] is False
    await orch.aclose()


async def test_compatibility_manager_reserves_before_allocating_worker() -> None:
    from henchman.agents.delegation_manager import DelegationManager
    from henchman.providers.base import ToolCall
    orch = runtime(limit=0)
    manager = DelegationManager(orch.delegation_runner)
    with pytest.raises(DelegationAdmissionError):
        await manager.start_delegation(orch.tech_lead, ToolCall("child", "delegate_task", {
            "agent": "explorer", "task": "task",
        }), 0)
    assert not manager.ongoing_tasks
    assert "explorer" not in orch.pool._agents
    assert not orch.default_provider.calls
    await orch.aclose()


async def test_shutdown_closes_suspended_named_stream_and_unentered_compat_worker() -> None:
    from henchman.agents.delegation_manager import DelegationManager
    from henchman.agents.orchestrator_types import DelegationParams
    from henchman.providers.base import ToolCall
    orch = runtime(limit=2)
    stream = orch.delegation_runner.run_delegation(DelegationParams("explorer", "task"))
    assert (await anext(stream)).type == EventType.AGENT_STARTED
    manager = DelegationManager(orch.delegation_runner)
    task_id = await manager.start_delegation(orch.tech_lead, ToolCall("child", "delegate_task", {
        "agent": "engineer", "task": "task",
    }), 0)
    await orch.aclose()
    assert orch.delegation_runner.admission.active == 0
    assert not orch.pool._execution_claims
    assert manager.get_delegation(task_id).asyncio_task.done()
    assert [event async for event in stream] == []
    assert not orch.default_provider.calls


async def test_parallel_reserves_before_start_and_streams_more_than_buffer(monkeypatch: pytest.MonkeyPatch) -> None:
    import henchman.agents.delegation as module
    from henchman.agents.orchestrator_types import DelegationParams
    orch = runtime(limit=1)
    monkeypatch.setattr(module, "MAX_PARALLEL_DELEGATION_BUFFER", 1)
    async with asyncio.timeout(3):
        events = [event async for event in orch.delegation_runner.run_parallel_delegations([
            DelegationParams(role, "task", {"completion_requirement": "response"})
            for role in ("explorer", "engineer")
        ])]
    denials = [event for event in events if event.type == EventType.ERROR]
    assert len(denials) == 1
    assert denials[0].data["admission"]["code"] == "delegation_capacity"
    assert "engineer" not in orch.pool._agents
    assert any(event.type == EventType.AGENT_COMPLETED for event in events)
    assert orch.delegation_runner.admission.active == 0
    await orch.aclose()


async def test_failed_worker_creation_leaves_no_active_record(monkeypatch: pytest.MonkeyPatch) -> None:
    admission = DelegationAdmission(1)
    async def runner(_: str, prompt: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.CONTENT, prompt)
    manager = manager_for(admission, runner)
    def fail(*_args: object) -> Any:
        raise RuntimeError("worker creation failed")
    monkeypatch.setattr(manager, "_start_worker", fail)
    with pytest.raises(RuntimeError, match="worker creation failed"):
        spawn(manager)
    assert admission.active == 0
    assert not manager.has_running_work()
    assert manager.list() == []
    await manager.close()


async def test_waiting_for_input_retains_slot_until_execution_finishes() -> None:
    admission = DelegationAdmission(1)
    async def runner(_: str, prompt: str) -> AsyncIterator[AgentEvent]:
        answer = await manager.request_input(prompt)
        yield AgentEvent(EventType.CONTENT, answer)
    manager = manager_for(admission, runner)
    identity = spawn(manager)
    assert (await manager.wait_for_notification()).status == "waiting_for_input"
    assert admission.active == 1
    with pytest.raises(DelegationAdmissionError):
        spawn(manager)
    await manager.send_message(identity, "answer")
    await manager.wait_for_notification()
    assert admission.active == 0
    await manager.close()


async def test_cancelling_tree_joins_every_child_after_caller_cancellation() -> None:
    admission = DelegationAdmission(2)
    running: dict[str, asyncio.Event] = {}
    cleaning: dict[str, asyncio.Event] = {}
    releases: dict[str, asyncio.Event] = {}
    async def runner(identity: str, prompt: str) -> AsyncIterator[AgentEvent]:
        running.setdefault(identity, asyncio.Event()).set()
        try:
            await asyncio.Event().wait()
            yield AgentEvent(EventType.CONTENT, prompt)
        finally:
            cleaning.setdefault(identity, asyncio.Event()).set()
            await releases.setdefault(identity, asyncio.Event()).wait()
    manager = manager_for(admission, runner)
    parent = spawn(manager)
    with subagent_actor(parent):
        child = spawn(manager)
    await asyncio.sleep(0)
    task = asyncio.create_task(manager.cancel(parent))
    await cleaning.setdefault(child, asyncio.Event()).wait()
    task.cancel("first tree cancellation")
    releases[child].set()
    for _ in range(20):
        await asyncio.sleep(0)
        if task.done() or parent in cleaning:
            break
    parent_was_joined = parent in cleaning and not task.done()
    releases.setdefault(parent, asyncio.Event()).set()
    with pytest.raises(asyncio.CancelledError, match="first tree cancellation"):
        await task
    try:
        assert parent_was_joined
        assert admission.active == 0
    finally:
        await manager.close()


async def test_parallel_close_joins_buffer_blocked_producers(monkeypatch: pytest.MonkeyPatch) -> None:
    import henchman.agents.delegation as module
    from henchman.agents.orchestrator_types import DelegationParams
    orch = runtime(limit=2)
    monkeypatch.setattr(module, "MAX_PARALLEL_DELEGATION_BUFFER", 1)
    stream = orch.delegation_runner.run_parallel_delegations([
        DelegationParams(role, "task", {"completion_requirement": "response"})
        for role in ("explorer", "engineer")
    ])
    await anext(stream)
    await asyncio.sleep(0)
    async with asyncio.timeout(3):
        await stream.aclose()
    assert orch.delegation_runner.admission.active == 0
    assert not orch.pool._execution_claims
    await orch.aclose()


async def test_model_tools_return_structured_denials_without_queuing_followup() -> None:
    from henchman.tools.builtins.subagents import InvokeSubagentTool
    from henchman.tools.builtins.tier5_tools import SendMessageTool
    admission = DelegationAdmission(1)
    async def runner(_: str, prompt: str) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(EventType.CONTENT, prompt)
    manager = manager_for(admission, runner)
    identity = spawn(manager)
    await manager.wait_for_notification()
    held = admission.reserve()
    try:
        result = await InvokeSubagentTool(manager).execute(task="task", role="role", system_prompt="sys", tools=[])
        assert result.success is False
        assert result.metadata["admission"]["code"] == "delegation_capacity"
        tool = SendMessageTool()
        tool._subagent_manager = manager
        result = await tool.execute(conversation_id=identity, message="not queued")
        assert result.success is False
        assert result.metadata["admission"]["retryable"] is False
        assert manager._conversations[identity].inbox.empty()
    finally:
        held.release()
        await manager.close()


@pytest.mark.parametrize("parallel", [False, True])
async def test_stale_stream_rejected_before_actor_creation_after_reset(parallel: bool) -> None:
    from henchman.agents.orchestrator_types import DelegationParams
    orch = runtime()
    params = DelegationParams("explorer", "task")
    stream = (orch.delegation_runner.run_parallel_delegations([params]) if parallel
              else orch.delegation_runner.run_delegation(params))
    await orch.cancel_subagents()
    events = [event async for event in stream]
    assert events[0].data["admission"]["code"] == "delegation_retired"
    assert "explorer" not in orch.pool._agents
    assert not orch.default_provider.calls
    await orch.aclose()


async def test_failed_cleanup_releases_capacity_and_retains_caller_cancellation() -> None:
    admission = DelegationAdmission(1)
    started, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def runner(_: str, prompt: str) -> AsyncIterator[AgentEvent]:
        started.set()
        try:
            await asyncio.Event().wait()
            yield AgentEvent(EventType.CONTENT, prompt)
        finally:
            cleaning.set()
            await release.wait()
            raise RuntimeError("owned cleanup failed")
    manager = manager_for(admission, runner)
    identity = spawn(manager)
    await started.wait()
    task = asyncio.create_task(manager.cancel(identity))
    await cleaning.wait()
    task.cancel("original cancellation")
    release.set()
    with pytest.raises(asyncio.CancelledError, match="original cancellation"):
        await task
    assert admission.active == 0
    assert manager._conversations[identity].task.done()
    await manager.close()


async def test_repeated_settlement_joins_one_stream_close_owner() -> None:
    admission = DelegationAdmission(1)
    lease = admission.reserve()
    cleaning, release = asyncio.Event(), asyncio.Event()
    async def stream() -> AsyncIterator[AgentEvent]:
        try:
            yield AgentEvent(EventType.CONTENT, "owned")
        finally:
            cleaning.set()
            try:
                await release.wait()
            finally:
                lease.release()
    owned = stream()
    lease.stream = owned
    await anext(owned)
    admission.retire()
    first = asyncio.create_task(admission.settle())
    await cleaning.wait()
    second = asyncio.create_task(admission.settle())
    await asyncio.sleep(0)
    second.cancel("caller cancellation")
    await asyncio.sleep(0)
    still_joining = not second.done()
    release.set()
    await first
    with pytest.raises(asyncio.CancelledError, match="caller cancellation"):
        await second
    assert still_joining
    assert admission.active == 0
