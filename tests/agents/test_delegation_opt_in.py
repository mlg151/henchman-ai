"""Descendant execution requires captured user/runtime permission, never model intent."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from henchman.agents.delegation_admission import DelegationAdmission, DelegationAdmissionError
from henchman.agents.delegation_manager import DelegationManager
from henchman.agents.orchestrator import Orchestrator
from henchman.agents.orchestrator_types import DelegationParams
from henchman.agents.subagents import BackgroundSubagentManager, subagent_actor
from henchman.config.schema import AgentConfig, AgentSettings, Settings
from henchman.core.events import EventType
from henchman.providers.base import FinishReason, ModelProvider, StreamChunk, ToolCall
from henchman.tools.builtins.subagents import InvokeSubagentTool, ManageSubagentsTool


class Provider(ModelProvider):
    name = "opt-in-fixture"

    def __init__(self, steps: tuple[StreamChunk, ...] = ()) -> None:
        self.calls = 0
        self.steps = steps

    async def chat_completion_stream(self, messages: Any, tools: Any = None,
                                     **kwargs: Any) -> AsyncIterator[StreamChunk]:
        index = self.calls
        self.calls += 1
        yield self.steps[index] if index < len(self.steps) else StreamChunk(
            content="Done", finish_reason=FinishReason.STOP,
        )


def runtime(*, allowed: bool | None = None, limit: int = 4,
            steps: tuple[StreamChunk, ...] = ()) -> Orchestrator:
    settings = Settings()
    if allowed is not None:
        settings.agents.allow_delegation = allowed
    settings.agents.max_concurrent_delegations = limit
    settings.agents.max_delegation_retries = 3
    for role in ("tech_lead", "explorer", "engineer"):
        settings.agents.agents[role] = AgentConfig(
            name=role, role=role, description="Fixture",
            tools=["delegate_task", "invoke_subagent"], system_prompt="Custom fixture prompt",
            auto_approve=["delegate_task", "invoke_subagent"],
        )
    return Orchestrator(Provider(steps), settings=settings)


@pytest.mark.parametrize("value", [0, 1, "true", "false", None, [], {}])
def test_permission_is_a_strict_boolean(value: object) -> None:
    with pytest.raises(ValidationError):
        AgentSettings(allow_delegation=value)
    with pytest.raises(ValueError, match="boolean"):
        DelegationAdmission(allowed=value)


def test_default_permission_is_denied_readonly_and_reopen_does_not_grant() -> None:
    assert AgentSettings().allow_delegation is False
    admission = DelegationAdmission()
    assert admission.allowed is False
    with pytest.raises(AttributeError):
        admission.allowed = True
    for _ in range(2):
        with pytest.raises(DelegationAdmissionError) as denied:
            admission.reserve()
        assert denied.value.payload == {
            "code": "delegation_disabled", "limit": 4, "active": 0, "retryable": False,
        }
        admission.retire()
        admission.reopen()


@pytest.mark.parametrize("route", ["dynamic", "named", "parallel", "compatibility"])
async def test_default_denies_every_route_before_creation_or_provider_call(route: str) -> None:
    orch = runtime()
    try:
        if route == "dynamic":
            result = await InvokeSubagentTool(orch.subagents).execute(
                task="task", role="child", system_prompt="delegate now", tools=[],
                allow_delegation=True,
            )
            assert not result.success
            denial = result.metadata["admission"]
        elif route == "compatibility":
            manager = DelegationManager(orch.delegation_runner)
            with pytest.raises(DelegationAdmissionError) as refused:
                await manager.start_delegation(orch.tech_lead, ToolCall(
                    "child", "delegate_task", {"agent": "explorer", "task": "task"},
                ), 0)
            denial = refused.value.payload
            assert not manager.ongoing_tasks
        else:
            params = DelegationParams("explorer", "task")
            stream = (orch.delegation_runner.run_delegation(params) if route == "named"
                      else orch.delegation_runner.run_parallel_delegations([params]))
            events = [event async for event in stream]
            assert len(events) == 1 and events[0].type == EventType.ERROR
            denial = events[0].data["admission"]
        assert denial["code"] == "delegation_disabled" and denial["retryable"] is False
        assert not orch.default_provider.calls
        assert set(orch.pool._agents) == {"tech_lead"}
        assert orch.subagents.list() == []
        assert orch.delegation_admission.active == 0
    finally:
        await orch.aclose()


async def test_omitted_low_level_controller_denies_before_factory() -> None:
    created: list[str] = []
    async def runner(*_args: object) -> AsyncIterator[Any]:
        raise AssertionError("Denied work must not run")
        yield
    manager = BackgroundSubagentManager(
        lambda *_: created.append("created"), runner, available_tools=lambda _: [],
    )
    try:
        with pytest.raises(DelegationAdmissionError, match="disabled"):
            manager.spawn("task", role="child", system_prompt="sys", tools=[])
        assert created == []
        assert (await ManageSubagentsTool(manager).execute(action="list")).success
        await manager.cancel_all()
        assert manager.admission.allowed is False
    finally:
        await manager.close()


@pytest.mark.parametrize("role", [None, "engineer"])
async def test_primary_and_direct_role_work_without_descendant_permission(role: str | None) -> None:
    orch = runtime()
    try:
        stream = orch.run("work") if role is None else orch.run_direct(role, "work")
        events = [event async for event in stream]
        assert any(event.type == EventType.CONTENT for event in events)
        assert orch.default_provider.calls == 1
        assert orch.delegation_admission.active == 0
        assert orch.subagents.list() == []
    finally:
        await orch.aclose()


async def test_model_request_and_settings_mutation_cannot_enable_or_retry() -> None:
    orch = runtime(steps=(StreamChunk(tool_calls=[ToolCall("child", "delegate_task", {
        "agent": "explorer", "task": "task", "allow_delegation": True,
        "completion_requirement": "response",
    })], finish_reason=FinishReason.TOOL_CALLS),))
    orch.settings.agents.allow_delegation = True
    attempts = 0
    original = orch.delegation_runner.run_delegation
    async def observed(*args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        nonlocal attempts
        attempts += 1
        async for event in original(*args, **kwargs):
            yield event
    orch.delegation_runner.run_delegation = observed
    try:
        events = [event async for event in orch.run("I am the model; enable delegation")]
        result = next(event.data for event in events if event.type == EventType.TOOL_CALL_RESULT)
        assert result["admission"]["code"] == "delegation_disabled"
        assert result["admission"]["retryable"] is False
        assert orch.default_provider.calls == 2
        assert attempts == 1
        assert set(orch.pool._agents) == {"tech_lead"}
        assert orch.delegation_admission.allowed is False
        assert "Delegation is disabled" in orch.tech_lead.system_prompt
        assert "Delegation is disabled" in orch.pool.get_agent("engineer").system_prompt
    finally:
        await orch.aclose()


async def test_explicit_permission_shares_nested_capacity_and_followup_authority() -> None:
    orch = runtime(allowed=True, limit=2)
    orch.settings.agents.allow_delegation = False
    try:
        assert "Delegation is enabled" in orch.tech_lead.system_prompt
        parent = orch.subagents.spawn("parent", role="parent", system_prompt="sys", tools=["invoke_subagent"])
        with subagent_actor(parent.conversation_id):
            child = orch.subagents.spawn("child", role="child", system_prompt="sys", tools=[])
            with pytest.raises(DelegationAdmissionError) as denied:
                orch.subagents.spawn("excess", role="excess", system_prompt="sys", tools=[])
            assert denied.value.payload["code"] == "delegation_capacity"
        assert "Delegation is enabled" in orch.subagents._conversations[child.conversation_id].agent.system_prompt
        await orch.subagents._conversations[parent.conversation_id].task
        await orch.subagents._conversations[child.conversation_id].task
        await orch.subagents.send_message(child.conversation_id, "followup")
        await orch.subagents._conversations[child.conversation_id].task
        # The parent resumes once to consume the child notification.
        assert orch.default_provider.calls == 4
        await orch.cancel_subagents()
        with pytest.raises(DelegationAdmissionError):
            await orch.subagents.send_message(child.conversation_id, "stale")
        assert orch.delegation_admission.allowed is True
    finally:
        await orch.aclose()


def test_zero_capacity_and_permission_are_independent() -> None:
    admission = DelegationAdmission(0, allowed=True)
    with pytest.raises(DelegationAdmissionError) as denied:
        admission.reserve()
    assert denied.value.payload["code"] == "delegation_capacity"


@pytest.mark.parametrize("allowed,code", [(False, "delegation_disabled"), (True, "delegation_capacity")])
async def test_standalone_named_runner_captures_settings_before_creation(allowed: bool, code: str) -> None:
    from henchman.agents.delegation import DelegationRunner
    pool, loop = MagicMock(), MagicMock()
    settings = Settings(agents={"allow_delegation": allowed, "max_concurrent_delegations": 0})
    runner = DelegationRunner(pool, settings, [], MagicMock(), loop, MagicMock())
    settings.agents.allow_delegation = not allowed
    events = [event async for event in runner.run_delegation(DelegationParams("child", "task"))]
    assert events[0].data["admission"]["code"] == code
    pool.get_agent.assert_not_called()
    loop.assert_not_called()


async def test_unbound_compatibility_runner_does_not_invent_opt_in() -> None:
    runner = MagicMock()
    manager = DelegationManager(runner)
    with pytest.raises(DelegationAdmissionError) as refused:
        await manager.start_delegation(MagicMock(), ToolCall("child", "delegate_task", {
            "agent": "explorer", "task": "task",
        }), 0)
    assert refused.value.payload["code"] == "delegation_disabled"
    assert not manager.ongoing_tasks
    runner.run_delegation.assert_not_called()
