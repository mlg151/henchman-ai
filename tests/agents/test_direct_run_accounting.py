"""Direct runs select accounting from their actual role provider after claiming."""

import pytest
from tests.agents.test_agent_budget_scope import AccountingProvider

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import Settings
from henchman.core.run_budget import BudgetAccountingError


async def test_supported_specialist_gets_accounting_with_uninstrumented_default(monkeypatch):
    default = AccountingProvider()
    default.supports_run_budget = False
    specialist = AccountingProvider()
    orchestrator = Orchestrator(default)
    orchestrator.pool.get_agent("explorer").provider = specialist
    original = orchestrator.pool.get_agent

    def get_after_claim(role):
        assert orchestrator._public_run_active
        return original(role)

    monkeypatch.setattr(orchestrator.pool, "get_agent", get_after_claim)
    _ = [event async for event in orchestrator.run_direct("explorer", "go")]
    assert orchestrator.last_budget_scope is not None
    assert orchestrator.last_budget_scope.ledger.snapshot().consumed_requests == 1
    assert default.calls == 0 and specialist.calls == 1


async def test_bounded_unsupported_specialist_cannot_use_supported_default_as_cover():
    default = AccountingProvider()
    specialist = AccountingProvider()
    specialist.supports_run_budget = False
    orchestrator = Orchestrator(default, settings=Settings(usage={"limits": {"max_requests": 1}}))
    orchestrator.pool.get_agent("explorer").provider = specialist
    with pytest.raises(BudgetAccountingError):
        _ = [event async for event in orchestrator.run_direct("explorer", "go")]
    assert default.calls == 0 and specialist.calls == 0
