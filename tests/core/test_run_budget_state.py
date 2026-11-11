"""Durable state preserves observations, uncertainty and exact price snapshots."""

import json
from decimal import Decimal

import pytest

from henchman.core.run_budget import BudgetLimits, ReportedCost, RequestEstimate, RunBudgetLedger
from henchman.core.run_budget_state import decode_state, encode_state
from henchman.providers.usage import TokenPricing, UsageReport


def test_state_roundtrip_preserves_finality_and_decimal_rates() -> None:
    ledger = RunBudgetLedger(run_id="run", limits=BudgetLimits(max_cost=Decimal("1.234567890123456789")), clock=lambda: 10)
    pricing = TokenPricing.uniform(Decimal("0.000000000000000001"))
    ledger.reserve(RequestEstimate(10, 20, pricing), request_id="partial", operation_id="operation")
    ledger.start("partial")
    ledger.reconcile("partial", UsageReport(prompt_tokens=10, completion_tokens=1, source="reported"))
    ledger.reconcile("partial", final=True)  # Finished without final usage remains uncertain.
    ledger.reserve(RequestEstimate(10, 20, pricing), request_id="cancelled")
    ledger.start("cancelled")
    ledger.cancel("cancelled")
    ledger.reconcile("cancelled", reported_cost=ReportedCost(Decimal("0.01234567890123456789"), "USD"), final=True)
    encoded = encode_state(ledger.export_state())
    assert '"0.000000000000000001"' in encoded or '"1E-18"' in encoded
    restored = RunBudgetLedger.from_state(decode_state(encoded), clock=lambda: 900)
    assert restored.snapshot() == ledger.snapshot()
    restored.reconcile("partial", UsageReport(prompt_tokens=10, completion_tokens=2, source="reported"), final=True)
    assert restored.snapshot().settled_tokens == 12
    assert ledger.snapshot().settled_tokens == 0


@pytest.mark.parametrize("damage", ["future", "duplicate", "dispatched", "final", "negative", "float_money"])
def test_invalid_state_cannot_restore_spend_capacity(damage: str) -> None:
    ledger = RunBudgetLedger(run_id="run", limits=BudgetLimits(max_cost=Decimal("1")))
    ledger.reserve(RequestEstimate(1, 2, TokenPricing.uniform(0)), request_id="request")
    payload = json.loads(encode_state(ledger.export_state()))
    if damage == "future":
        payload["version"] = 999
    elif damage == "duplicate":
        payload["attempts"].append(payload["attempts"][0])
    elif damage == "dispatched":
        payload["attempts"][0]["dispatched"] = True
    elif damage == "final":
        payload["attempts"][0]["final_usage"] = True
    elif damage == "negative":
        payload["elapsed_seconds"] = -1
    else:
        payload["limits"]["max_cost"] = 1.0
    with pytest.raises(ValueError):
        decode_state(json.dumps(payload))


def test_snapshot_derives_overrun_without_another_failed_request() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_tokens=10))
    record = ledger.reserve(RequestEstimate(5, 5))
    ledger.start(record.request_id)
    ledger.reconcile(record.request_id, UsageReport(total_tokens=11, source="reported"), final=True)
    assert ledger.snapshot().stop_reason == "token_limit"


def test_zero_money_remaining_can_still_admit_free_requests() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal(0)))
    assert ledger.snapshot().stop_reason is None
    record = ledger.reserve(RequestEstimate(1, 1, TokenPricing.uniform(0)))
    assert ledger.start(record.request_id)
    assert ledger.snapshot().stop_reason is None
