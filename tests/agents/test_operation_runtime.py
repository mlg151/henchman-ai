"""Public orchestrator dispatch activates session recovery before any effect."""

from copy import deepcopy

import pytest
from tests.core.test_session_operations import EffectTool, approve

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import Settings
from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.runtime_operations import current_operation_run
from henchman.core.session_data import Session
from henchman.core.session_operations import SessionRunOperations
from henchman.providers.base import FinishReason, Message, ModelProvider, StreamChunk, ToolCall
from henchman.tools.registry import ToolRegistry


class ToolProvider(ModelProvider):
    name = "offline"
    default_model = "offline"

    def __init__(self):
        self.calls = 0

    async def chat_completion_stream(self, messages, tools=None, **kwargs):
        self.calls += 1
        if self.calls == 1:
            yield StreamChunk(tool_calls=[ToolCall("call", "effect", {"value": "one"})], finish_reason=FinishReason.TOOL_CALLS)
        else:
            yield StreamChunk(content="Done.", finish_reason=FinishReason.STOP)


def build(tmp_path, *, session=None, allow_delegation=False):
    session = session or Session("session", "project", "today", "today")
    registry = ToolRegistry()
    tool = EffectTool()
    registry.register(tool)
    registry.set_confirmation_handler(lambda _request: approve())
    provider = ToolProvider()
    settings = Settings.model_validate({"agents": {"allow_delegation": allow_delegation}, "operations": {"persistence": "durable"}})
    orchestrator = Orchestrator(provider, tool_registry=registry, settings=settings)
    orchestrator.operation_runtime = SessionRunOperations(settings, lambda: session, lambda _: None, tmp_path / "ops.db")
    return orchestrator, provider, tool, session


async def test_public_primary_dispatch_persists_request_result_and_restores_context(tmp_path):
    orchestrator, provider, tool, session = build(tmp_path)
    async for _event in orchestrator.run("do the effect"):
        assert current_operation_run() is None
    assert provider.calls == 2 and tool.calls == ["one"]
    report = orchestrator.operation_runtime.report()
    assert len(report.records) == 1 and report.records[0].state == "completed"
    binding = session.operations.bindings[0]
    assert session.messages[binding.assistant_index].tool_calls[0]["id"] == "call"
    assert any(message.role == "tool" and message.tool_call_id == "call" for message in session.messages)
    assert session.operations.observed_ids == (report.records[0].operation_id,)


async def test_old_public_session_backup_stops_before_model_or_tool_dispatch(tmp_path):
    orchestrator, _, tool, session = build(tmp_path)
    backup = deepcopy(session)
    _ = [event async for event in orchestrator.run("do the effect")]
    restored, provider, other_tool, _ = build(tmp_path, session=backup)
    with pytest.raises(OperationRecoveryError, match="transcript_behind_journal"):
        _ = [event async for event in restored.run("continue")]
    assert provider.calls == 0 and not other_tool.calls and tool.calls == ["one"]


async def test_unknown_primary_effect_propagates_and_prevents_provider_continuation(tmp_path):
    orchestrator, provider, tool, _ = build(tmp_path)
    tool.failure = ConnectionError("response lost after effect")
    with pytest.raises(OperationRecoveryError):
        _ = [event async for event in orchestrator.run("do the effect")]
    assert provider.calls == 1 and tool.calls == ["one"]
    assert orchestrator.operation_runtime.report().records[0].state == "outcome_unknown"


async def test_unbound_public_run_has_process_recovery_without_creating_storage():
    registry = ToolRegistry()
    tool = EffectTool()
    registry.register(tool)
    registry.set_confirmation_handler(lambda _request: approve())
    orchestrator = Orchestrator(ToolProvider(), tool_registry=registry)
    _ = [event async for event in orchestrator.run("do the effect")]
    assert tool.calls == ["one"]
    assert orchestrator.operation_runtime.report().records[0].state == "completed"
    assert orchestrator.operation_runtime.path is None


async def test_unbound_durable_policy_fails_before_provider_dispatch():
    provider = ToolProvider()
    orchestrator = Orchestrator(provider, settings=Settings.model_validate({"operations": {"persistence": "durable"}}))
    with pytest.raises(OperationRecoveryError, match="durable_operation_session_required"):
        _ = [event async for event in orchestrator.run("go")]
    assert provider.calls == 0


async def test_operation_cleanup_failure_preserves_primary_control_and_finishes_budget(tmp_path):
    from types import SimpleNamespace

    from henchman.core.run_budget import BudgetExceeded
    orchestrator, _, tool, _ = build(tmp_path)
    primary = BudgetExceeded("request_limit")
    tool.failure = primary
    finished = []
    orchestrator.accounting_runtime = SimpleNamespace(begin=lambda _provider: None,
        finish=lambda scope, **kwargs: finished.append((scope, kwargs)))
    def fail_cleanup(*_args, **_kwargs):
        raise OperationRecoveryError("session_save_failed")
    orchestrator.operation_runtime.finish = fail_cleanup
    with pytest.raises(BudgetExceeded) as raised:
        _ = [event async for event in orchestrator.run("perform effect")]
    assert raised.value is primary
    assert len(finished) == 1 and not finished[0][1]["completed"]


async def test_operation_cleanup_failure_prevents_successful_budget_close(tmp_path):
    from types import SimpleNamespace
    orchestrator, _, _, _ = build(tmp_path)
    finished = []
    orchestrator.accounting_runtime = SimpleNamespace(begin=lambda _provider: None,
        finish=lambda scope, **kwargs: finished.append((scope, kwargs)))
    def fail_cleanup(*_args, **_kwargs):
        raise OperationRecoveryError("session_save_failed")
    orchestrator.operation_runtime.finish = fail_cleanup
    with pytest.raises(OperationRecoveryError, match="session_save_failed"):
        _ = [event async for event in orchestrator.run("perform effect")]
    assert len(finished) == 1 and not finished[0][1]["completed"]


def test_earlier_primary_turn_growth_cannot_retarget_later_saved_requests(tmp_path):
    orchestrator, _, tool, session = build(tmp_path)
    agent = orchestrator.tech_lead
    run = orchestrator.operation_runtime.begin(agent=agent)
    first = [Message("user", "first"), Message("assistant", "answer")]
    agent.current_turn_messages = first
    run.capture_agent(agent)
    agent.current_turn_messages = [Message("user", "notification")]
    _, offset, _ = run.capture_agent(agent)
    assert offset == 2
    saved = deepcopy(session.messages)
    first.append(Message("assistant", "late insertion"))
    with pytest.raises(OperationRecoveryError, match="primary_turn_history_changed"):
        run.capture_agent(agent)
    assert session.messages == saved and not tool.calls
