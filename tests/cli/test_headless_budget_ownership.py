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
