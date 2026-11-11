"""Direct runs select accounting from their actual role provider after claiming."""

import pytest
from tests.agents.test_agent_budget_scope import AccountingProvider

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import Settings
from henchman.core.run_budget import BudgetAccountingError, BudgetExceeded


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


@pytest.mark.parametrize("leader_supported", [False, True])
@pytest.mark.parametrize("request_limit", [None, 0])
async def test_primary_accounting_uses_actual_leader_provider(leader_supported, request_limit):
    default = AccountingProvider()
    default.supports_run_budget = not leader_supported
    leader = AccountingProvider()
    leader.supports_run_budget = leader_supported
    settings = Settings(usage={"limits": {"max_requests": request_limit}})
    orchestrator = Orchestrator(default, settings=settings)
    orchestrator.tech_lead.set_provider(leader)

    if request_limit == 0:
        expected = BudgetExceeded if leader_supported else BudgetAccountingError
        with pytest.raises(expected):
            _ = [event async for event in orchestrator.run("go")]
        assert leader.calls == 0
        assert orchestrator.last_budget_scope.ledger.snapshot().remaining_requests == 0
    else:
        _ = [event async for event in orchestrator.run("go")]
        assert leader.calls == 1
        if leader_supported:
            assert orchestrator.last_budget_scope is not None
            assert orchestrator.last_budget_scope.ledger.snapshot().consumed_requests == 1
        else:
            assert orchestrator.last_budget_scope is None
    assert default.calls == 0
