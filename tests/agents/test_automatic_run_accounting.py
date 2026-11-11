"""Public orchestrator runs activate configured accounting for the whole team."""

import pytest
from tests.agents.test_agent_budget_scope import AccountingProvider

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import Settings
from henchman.core.events import EventType
from henchman.core.run_budget import BudgetExceeded, BudgetLimits, RunBudgetLedger
from henchman.providers.runtime_budget import RunBudgetScope, current_run_budget, use_run_budget


@pytest.mark.parametrize("direct", [False, True])
async def test_configured_zero_prevents_public_run_dispatch(direct):
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider, settings=Settings(usage={"limits": {"max_requests": 0}}))
    stream = orchestrator.run_direct("explorer", "go") if direct else orchestrator.run("go")
    with pytest.raises(BudgetExceeded, match="request_limit"):
        _ = [event async for event in stream]
    assert provider.calls == 0
    assert orchestrator.last_budget_scope.ledger.snapshot().remaining_requests == 0
    assert current_run_budget() is None
    assert orchestrator._public_run_active is False


async def test_completed_runs_have_distinct_totals_and_authoritative_completion():
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider)
    first = [event async for event in orchestrator.run("first")]
    initial = orchestrator.last_budget_scope
    second = [event async for event in orchestrator.run("second")]
    assert initial.ledger is not orchestrator.last_budget_scope.ledger
    for events in (first, second):
        completion = next(event for event in events if event.type == EventType.AGENT_COMPLETED)
        budget = completion.data["budget"]
        assert budget["consumed_requests"] == 1
        assert budget["settled_tokens"] == 3
        assert budget["accounting_lifetime"] == "process"
        assert budget["unknown_cost_requests"] == 1
    assert provider.calls == 2


async def test_supplied_scope_spans_public_turns_without_reset():
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider)
    scope = RunBudgetScope(RunBudgetLedger(limits=BudgetLimits(max_requests=1)))
    _ = [event async for event in orchestrator.run("first", budget_scope=scope)]
    with pytest.raises(BudgetExceeded):
        _ = [event async for event in orchestrator.run("continue", budget_scope=scope)]
    assert provider.calls == 1
    assert orchestrator.last_budget_scope is scope


async def test_ambient_budget_cannot_be_replaced_by_explicit_fresh_scope():
    provider = AccountingProvider()
    orchestrator = Orchestrator(provider)
    outer = RunBudgetScope(RunBudgetLedger(limits=BudgetLimits(max_requests=0)))
    with use_run_budget(outer), pytest.raises(RuntimeError, match="different run"):
        _ = [event async for event in orchestrator.run("go", budget_scope=RunBudgetScope(RunBudgetLedger()))]
    assert provider.calls == 0


async def test_uninstrumented_provider_with_configured_limits_cannot_bypass_them():
    provider = AccountingProvider()
    provider.supports_run_budget = False
    orchestrator = Orchestrator(provider, settings=Settings(usage={"limits": {"max_requests": 4}}))
    with pytest.raises(RuntimeError, match="accounting"):
        _ = [event async for event in orchestrator.run("go")]
    assert provider.calls == 0


async def test_headless_budget_denial_keeps_authoritative_aggregate_evidence():
    from henchman.cli.headless import run_orchestrator_json

    provider = AccountingProvider()
    orchestrator = Orchestrator(provider, settings=Settings(usage={"limits": {"max_requests": 0}}))
    events = []
    assert not await run_orchestrator_json(orchestrator, "go", events.append)
    assert events[-1].type == EventType.FINISHED
    assert events[-1].data["status"] == "failed"
    assert events[-1].data["budget"]["consumed_requests"] == 0
    assert events[-1].data["budget"]["stop_reason"] == "request_limit"
    assert provider.calls == 0


async def test_public_event_yields_do_not_leak_actor_and_allow_cross_task_close():
    import asyncio

    from henchman.agents.subagents import _ACTOR

    provider = AccountingProvider()
    orchestrator = Orchestrator(provider)
    stream = orchestrator.run("go")
    assert _ACTOR.get() is None
    await anext(stream)  # agent_started
    await anext(stream)  # partial content
    try:
        assert _ACTOR.get() is None
    finally:
        await asyncio.create_task(stream.aclose())
    assert orchestrator._public_run_active is False
    assert orchestrator.last_budget_scope.ledger.snapshot().unknown_dispatched_requests == 1


async def test_failed_accounting_setup_does_not_publish_previous_run_totals():
    from types import SimpleNamespace

    from henchman.cli.headless import run_orchestrator_json
    from henchman.core.run_budget import BudgetAccountingError

    orchestrator = Orchestrator(AccountingProvider())
    _ = [event async for event in orchestrator.run("previous")]

    def unavailable(_provider):
        raise BudgetAccountingError("store_unavailable")

    orchestrator.accounting_runtime = SimpleNamespace(begin=unavailable)
    events = []
    assert not await run_orchestrator_json(orchestrator, "new task", events.append)
    assert "budget" not in events[-1].data
    assert orchestrator.last_completion_status.value == "failed"
