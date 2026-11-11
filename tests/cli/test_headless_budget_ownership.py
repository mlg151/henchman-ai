"""Headless accounting and cleanup belong to one successfully claimed invocation."""

import pytest

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.headless import run_orchestrator_json
from henchman.core.events import EventType
from henchman.core.run_budget import RunBudgetLedger
from henchman.providers.runtime_budget import RunBudgetScope
from tests.agents.test_agent_budget_scope import AccountingProvider


@pytest.mark.parametrize("direct", [False, True])
async def test_rejected_overlap_cannot_report_or_close_another_owned_run(direct):
    orchestrator = Orchestrator(AccountingProvider())
    first = orchestrator.run("owned active request")
    try:
        async for event in first:
            if event.type == EventType.CONTENT:
                break
        active = orchestrator.last_budget_scope
        events = []
        assert not await run_orchestrator_json(orchestrator, "rejected overlap", events.append, agent_role="explorer" if direct else None)
        terminal = next(event for event in events if event.type == EventType.FINISHED)
        assert "budget" not in terminal.data
        assert orchestrator.last_budget_scope is active
        assert not orchestrator.subagents._closed
    finally:
        await first.aclose()
        await orchestrator.aclose()


async def test_headless_evidence_captures_its_scope_before_cleanup_changes_global_state(monkeypatch):
    orchestrator = Orchestrator(AccountingProvider())
    unrelated = RunBudgetScope(RunBudgetLedger(run_id="unrelated"))

    async def cleanup():
        orchestrator.last_budget_scope = unrelated

    monkeypatch.setattr(orchestrator, "aclose", cleanup)
    events = []
    assert await run_orchestrator_json(orchestrator, "owned completed run", events.append)
    completed = next(event for event in events if event.type == EventType.AGENT_COMPLETED)
    terminal = next(event for event in events if event.type == EventType.FINISHED)
    assert terminal.data["budget"]["run_id"] == completed.data["budget"]["run_id"]
    assert terminal.data["budget"]["consumed_requests"] == 1


async def test_headless_provenance_uses_held_policy_and_preserves_unknown_price():
    from henchman.config.schema import Settings

    provider = AccountingProvider()
    provider.default_model = "old-credential-late-credential"
    settings = Settings(providers={"deepseek": {"api_key": "old-credential"}})
    orchestrator = Orchestrator(provider, settings=settings)
    events = []

    def render(event):
        if event.type == EventType.CONTENT:
            orchestrator.operation_runtime.current_session.evidence_redactor.register_secret("late-credential")
        events.append(event)

    assert await run_orchestrator_json(orchestrator, "finish locally", render)
    for event in events:
        if event.type in (EventType.AGENT_COMPLETED, EventType.FINISHED):
            row = event.data["budget"]["usage_breakdown"][0]
            assert row["model"] == "[REDACTED]-[REDACTED]"
            assert row["pricing"] is None
            assert row["usage_source"] == "reported"
            assert row["counts"]["total_tokens"] == 3
            assert row["dispatched_requests"] == 1
    assert orchestrator.last_budget_scope.ledger.snapshot().records[0].model == "old-credential-late-credential"


async def test_failed_headless_provenance_refreshes_policy_without_finalization():
    from henchman.core.run_budget import BudgetAccountingError
    from henchman.providers.base import StreamChunk
    from henchman.providers.runtime_budget import budget_attempt, prepare_budget_operation

    class FailingProvider(AccountingProvider):
        default_model = "late-credential"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            operation = prepare_budget_operation(self, {"model": self.default_model, "messages": []})
            with budget_attempt(operation) as attempt:
                attempt.start()
                yield StreamChunk(content="partial")
                raise BudgetAccountingError("deliberate_offline_accounting_failure")

    orchestrator = Orchestrator(FailingProvider())
    events = []

    def render(event):
        if event.type == EventType.CONTENT:
            orchestrator.operation_runtime.current_session.evidence_redactor.register_secret("late-credential")
        events.append(event)

    assert not await run_orchestrator_json(orchestrator, "fail locally", render)
    terminal = next(event for event in events if event.type == EventType.FINISHED)
    row = terminal.data["budget"]["usage_breakdown"][0]
    assert row["model"] == "[REDACTED]"
    assert row["usage_source"] == "unknown"
    assert row["counts"]["total_tokens"] is None
    assert terminal.data["budget"]["unknown_dispatched_requests"] == 1


async def test_successful_headless_refreshes_policy_without_budget_finalization(monkeypatch):
    from henchman.core.events import AgentEvent

    provider = AccountingProvider()
    provider.default_model = "late-success-credential"
    orchestrator = Orchestrator(provider)
    # An embedded runtime may emit its own successful completion without calling
    # the standard accounting finalizer. The public renderer still owns evidence.
    monkeypatch.setattr("henchman.agents.orchestrator.finalize_run", lambda *_args: [
        AgentEvent(EventType.AGENT_COMPLETED, {"agent": "tech_lead", "scope": "run", "status": "responded"},
                   source_agent="orchestrator"),
    ])
    events = []

    def render(event):
        if event.type == EventType.CONTENT:
            orchestrator.operation_runtime.current_session.evidence_redactor.register_secret("late-success-credential")
        events.append(event)

    assert await run_orchestrator_json(orchestrator, "finish locally", render)
    terminal = next(event for event in events if event.type == EventType.FINISHED)
    assert terminal.data["budget"]["usage_breakdown"][0]["model"] == "[REDACTED]"


async def test_direct_specialist_provider_credential_is_shared_evidence_authority():
    specialist = AccountingProvider()
    specialist.api_key = "specialist-only-credential"
    specialist.default_model = "specialist-only-credential-model"
    orchestrator = Orchestrator(AccountingProvider())
    orchestrator.pool.get_agent("explorer").provider = specialist
    events = []
    assert await run_orchestrator_json(orchestrator, "finish directly", events.append, agent_role="explorer")
    for event in events:
        if event.type in (EventType.AGENT_COMPLETED, EventType.FINISHED):
            assert event.data["budget"]["usage_breakdown"][0]["model"] == "[REDACTED]-model"
    session = orchestrator.operation_runtime.current_session
    assert session.evidence_redactor.text(specialist.api_key) == "[REDACTED]"
    assert specialist.api_key == "specialist-only-credential"


async def test_delegated_provider_credentials_are_registered_before_dispatch_and_after_rotation():
    from henchman.core.runtime_operations import current_operation_run
    from henchman.providers.runtime_budget import budget_attempt, prepare_budget_operation
    from tests.agents.test_active_agent_delegation import delegate, orchestrator, response

    class ScriptedAccountingProvider(AccountingProvider):
        def __init__(self, *steps, credential=None):
            super().__init__()
            self.steps = list(steps)
            self.api_key = credential

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            if self.api_key:
                assert current_operation_run().session.evidence_redactor.text(self.api_key) == "[REDACTED]"
            operation = prepare_budget_operation(self, {"model": self.default_model, "messages": []})
            with budget_attempt(operation) as attempt:
                attempt.start()
                self.calls += 1
                chunk = self.steps.pop(0)
                chunk.usage = {"total_tokens": 3}
                attempt.observe(chunk)
                if self.api_key:
                    self.api_key = "rotated-child-credential"
                yield chunk

    parent = ScriptedAccountingProvider(delegate("explorer", "delegate"), response())
    child = ScriptedAccountingProvider(response(), credential="child-credential")
    child.default_model = "child-credential/rotated-child-credential"
    runtime = orchestrator(parent)
    runtime.pool.get_agent("explorer").provider = child
    events = []
    assert await run_orchestrator_json(runtime, "delegate locally", events.append)
    assert parent.calls == 2 and child.calls == 1
    terminal = next(event for event in events if event.type == EventType.FINISHED)
    rows = terminal.data["budget"]["usage_breakdown"]
    assert {row["model"] for row in rows} == {"test-model", "[REDACTED]/[REDACTED]"}
    assert terminal.data["budget"]["consumed_requests"] == 3
    assert any(event.type == EventType.TOOL_CALL_RESULT and event.data["success"] for event in events)


async def test_cancelled_actor_retains_credentials_registered_during_provider_cleanup():
    import asyncio

    from henchman.providers.base import StreamChunk
    from henchman.providers.runtime_budget import budget_attempt, prepare_budget_operation

    entered = asyncio.Event()

    class WaitingProvider(AccountingProvider):
        api_key = "before-cancel-credential"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            operation = prepare_budget_operation(self, {"model": self.default_model, "messages": []})
            with budget_attempt(operation) as attempt:
                attempt.start()
                try:
                    yield StreamChunk(content="partial")
                    entered.set()
                    await asyncio.Event().wait()
                finally:
                    self.api_key = "cleanup-credential"

    runtime = Orchestrator(AccountingProvider())
    runtime.pool.get_agent("explorer").provider = WaitingProvider()

    async def consume():
        async for _event in runtime.run_direct("explorer", "cancel locally"):
            pass

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        policy = runtime.operation_runtime.current_session.evidence_redactor
        assert policy.text("before-cancel-credential cleanup-credential") == "[REDACTED] [REDACTED]"
        assert runtime.last_budget_scope.ledger.snapshot().unknown_dispatched_requests == 1
    finally:
        task.cancel()
        await runtime.aclose()
