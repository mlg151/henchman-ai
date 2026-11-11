"""Shared run budgets admit actual attempts once and retain uncertain consumption."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, Inexact, localcontext
from threading import Barrier

import pytest

from henchman.core.run_budget import (
    BudgetExceeded,
    BudgetLimits,
    ReportedCost,
    RequestEstimate,
    RunBudgetLedger,
)
from henchman.providers.usage import TokenPricing, UsageReport


def reported(prompt: int, completion: int) -> UsageReport:
    return UsageReport(prompt_tokens=prompt, completion_tokens=completion, source="reported")


def test_reservation_dispatch_and_cumulative_reconciliation_are_distinct() -> None:
    ledger = RunBudgetLedger(run_id="run-1", limits=BudgetLimits(max_tokens=30, max_requests=1))
    estimate = RequestEstimate(prompt_tokens=20, max_output_tokens=10)
    entry = ledger.reserve(estimate, request_id="attempt-1", operation_id="operation", agent_id="worker")
    assert entry.run_id == "run-1"
    assert ledger.reserve(estimate, request_id="attempt-1", operation_id="operation", agent_id="worker") == entry
    snapshot = ledger.snapshot()
    assert (snapshot.reserved_requests, snapshot.consumed_requests, snapshot.held_tokens) == (1, 0, 30)
    assert snapshot.accounting_lifetime == "process"
    assert ledger.start(entry.request_id)
    assert not ledger.start(entry.request_id)
    ledger.reconcile(entry.request_id, reported(20, 2))
    ledger.reconcile(entry.request_id, reported(20, 2))
    snapshot = ledger.snapshot()
    assert (snapshot.settled_tokens, snapshot.held_tokens, snapshot.unknown_dispatched_requests) == (0, 30, 1)
    ledger.reconcile(entry.request_id, reported(20, 3), final=True)
    ledger.reconcile(entry.request_id, reported(20, 3), final=True)
    ledger.reconcile(entry.request_id, reported(20, 1))  # Delayed earlier snapshot.
    snapshot = ledger.snapshot()
    assert (snapshot.settled_tokens, snapshot.held_tokens, snapshot.remaining_tokens) == (23, 0, 7)
    assert snapshot.unknown_dispatched_requests == 0
    assert snapshot.records[0].usage.completion_tokens == 3


def test_duplicate_ids_cannot_change_model_agent_or_estimates() -> None:
    ledger = RunBudgetLedger(run_id="stable")
    ledger.reserve(RequestEstimate(10, 5), request_id="same", agent_id="one")
    with pytest.raises(ValueError, match="different"):
        ledger.reserve(RequestEstimate(20, 5), request_id="same", agent_id="one")
    with pytest.raises(ValueError, match="different"):
        ledger.reserve(RequestEstimate(10, 5), request_id="same", agent_id="two")
    assert len(ledger.snapshot().records) == 1


@pytest.mark.parametrize("limit,reason", [
    (BudgetLimits(max_requests=0), "request_limit"),
    (BudgetLimits(max_tokens=0), "token_limit"),
    (BudgetLimits(max_seconds=0), "time_limit"),
])
def test_explicit_zero_limits_prevent_admission(limit: BudgetLimits, reason: str) -> None:
    ledger = RunBudgetLedger(limits=limit)
    with pytest.raises(BudgetExceeded) as failure:
        ledger.reserve(RequestEstimate(1, 1))
    assert failure.value.reason == reason
    assert ledger.snapshot().records == ()


def test_concurrent_reservations_allow_exactly_one_dispatch() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=1, max_tokens=15))
    barrier = Barrier(2)

    def dispatch(attempt: str) -> bool:
        barrier.wait(timeout=5)
        try:
            entry = ledger.reserve(RequestEstimate(10, 5), request_id=attempt, agent_id=attempt)
            return ledger.start(entry.request_id)
        except BudgetExceeded:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(dispatch, ("specialist-a", "specialist-b")))
    assert results.count(True) == 1
    snapshot = ledger.snapshot()
    assert snapshot.consumed_requests == 1 and snapshot.held_tokens == 15


def test_cancel_before_dispatch_releases_but_cancel_after_dispatch_retains() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_tokens=20, max_requests=1))
    first = ledger.reserve(RequestEstimate(10, 10), request_id="not-sent")
    ledger.cancel(first.request_id)
    ledger.cancel(first.request_id)
    assert not ledger.start(first.request_id)
    assert ledger.snapshot().remaining_tokens == 20
    second = ledger.reserve(RequestEstimate(10, 10), request_id="sent")
    assert ledger.start(second.request_id)
    ledger.reconcile(second.request_id, reported(10, 2))
    ledger.cancel(second.request_id)
    ledger.cancel(second.request_id)
    snapshot = ledger.snapshot()
    assert snapshot.remaining_requests == 0
    assert snapshot.remaining_tokens == 0
    assert snapshot.unknown_dispatched_requests == 1
    ledger.reconcile(second.request_id, reported(10, 4), final=True)
    assert ledger.snapshot().remaining_tokens == 6
    assert ledger.snapshot().consumed_requests == 1


def test_missing_or_estimated_final_usage_cannot_release_consumption() -> None:
    for final_usage in (None, UsageReport(prompt_tokens=1, completion_tokens=1, source="estimated")):
        ledger = RunBudgetLedger(limits=BudgetLimits(max_tokens=20))
        entry = ledger.reserve(RequestEstimate(10, 10))
        ledger.start(entry.request_id)
        ledger.reconcile(entry.request_id, reported(10, 1))
        ledger.reconcile(entry.request_id, final_usage, final=True)
        snapshot = ledger.snapshot()
        assert snapshot.settled_tokens == 0 and snapshot.held_tokens == 20
        assert snapshot.unknown_dispatched_requests == 1


def test_elapsed_deadline_is_checked_again_at_dispatch() -> None:
    now = [10.0]
    ledger = RunBudgetLedger(limits=BudgetLimits(max_seconds=5, max_tokens=20), clock=lambda: now[0])
    entry = ledger.reserve(RequestEstimate(10, 10))
    now[0] = 15.0
    with pytest.raises(BudgetExceeded) as failure:
        ledger.start(entry.request_id)
    assert failure.value.reason == "time_limit"
    snapshot = ledger.snapshot()
    assert snapshot.remaining_seconds == 0
    assert snapshot.consumed_requests == 0 and snapshot.held_tokens == 0
    assert snapshot.remaining_tokens == 20


def test_overrun_is_recorded_and_blocks_an_already_reserved_followup() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_tokens=30))
    first = ledger.reserve(RequestEstimate(10, 5))
    second = ledger.reserve(RequestEstimate(10, 5))
    ledger.start(first.request_id)
    ledger.reconcile(first.request_id, reported(40, 5), final=True)
    with pytest.raises(BudgetExceeded) as failure:
        ledger.start(second.request_id)
    assert failure.value.reason == "token_limit"
    assert ledger.snapshot().settled_tokens == 45
    assert ledger.snapshot().held_tokens == 0
    assert ledger.snapshot().remaining_tokens == 0


def test_retries_share_operation_identity_but_each_attempt_consumes_a_request() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=2))
    for number in (1, 2):
        entry = ledger.reserve(RequestEstimate(10, 5), request_id=f"retry-{number}", operation_id="one-operation")
        ledger.start(entry.request_id)
        ledger.reconcile(entry.request_id, reported(10, number), final=True)
    snapshot = ledger.snapshot()
    assert snapshot.consumed_requests == 2 and snapshot.settled_tokens == 23
    assert {entry.operation_id for entry in snapshot.records} == {"one-operation"}
    with pytest.raises(BudgetExceeded, match="request"):
        ledger.reserve(RequestEstimate(10, 5), request_id="retry-3", operation_id="one-operation")


def test_money_reservation_uses_highest_applicable_input_rate_and_exact_decimal() -> None:
    pricing = TokenPricing(input_per_1k=2, output_per_1k=10, cache_read_per_1k=0.5, cache_write_per_1k=3)
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal("4")))
    entry = ledger.reserve(RequestEstimate(1000, 100, pricing=pricing))
    assert entry.held_cost == Decimal("4")
    assert ledger.snapshot().remaining_cost == 0
    ledger.start(entry.request_id)
    usage = UsageReport(prompt_tokens=1000, completion_tokens=100, cached_tokens=600, cache_creation_tokens=100, source="reported")
    ledger.reconcile(entry.request_id, usage, final=True)
    snapshot = ledger.snapshot()
    assert snapshot.remaining_cost == Decimal("1.8")
    assert snapshot.money[0].settled_estimated_cost == Decimal("2.2")
    assert snapshot.money[0].reported_cost is None
    ledger.reconcile(entry.request_id, usage, final=True, reported_cost=ReportedCost(Decimal("2.4"), "USD"))
    ledger.reconcile(entry.request_id, usage, final=True, reported_cost=ReportedCost(Decimal("2.4"), "USD"))
    snapshot = ledger.snapshot()
    assert snapshot.remaining_cost == Decimal("1.6")
    assert snapshot.money[0].reported_cost == Decimal("2.4")


def test_money_cap_requires_known_prices_and_currency_but_accepts_explicit_zero() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal(0)))
    with pytest.raises(BudgetExceeded) as failure:
        ledger.reserve(RequestEstimate(10, 5))
    assert failure.value.reason == "unknown_price"
    assert ledger.snapshot().remaining_cost is None
    with pytest.raises(BudgetExceeded) as failure:
        ledger.reserve(RequestEstimate(10, 5, pricing=TokenPricing(0, 0, 0, 0, currency="EUR")))
    assert failure.value.reason == "currency_mismatch"
    assert ledger.snapshot().remaining_cost is None
    entry = ledger.reserve(RequestEstimate(10, 5, pricing=TokenPricing.uniform(0)))
    assert ledger.start(entry.request_id)
    ledger.cancel(entry.request_id)
    assert ledger.snapshot().remaining_cost == 0
    assert ledger.snapshot().money[0].held_cost == 0
    assert ledger.snapshot().unknown_dispatched_requests == 1


def test_unknown_applicable_cache_rate_fails_strict_money_admission() -> None:
    pricing = TokenPricing(input_per_1k=1, output_per_1k=2)
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal("1")))
    with pytest.raises(BudgetExceeded) as failure:
        ledger.reserve(RequestEstimate(10, 5, pricing=pricing))
    assert failure.value.reason == "unknown_price"
    assert ledger.start(ledger.reserve(RequestEstimate(10, 5, pricing=pricing, cache_mode="none")).request_id)


def test_cancelled_paid_call_keeps_money_reservation_until_final_usage() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal("0.02")))
    entry = ledger.reserve(RequestEstimate(10, 10, pricing=TokenPricing.uniform(1)))
    ledger.start(entry.request_id)
    ledger.cancel(entry.request_id)
    assert ledger.snapshot().remaining_cost == 0
    with pytest.raises(BudgetExceeded) as failure:
        ledger.reserve(RequestEstimate(1, 1, pricing=TokenPricing.uniform(1)))
    assert failure.value.reason == "money_limit"
    ledger.reconcile(entry.request_id, reported(10, 1), final=True)
    assert ledger.snapshot().remaining_cost == Decimal("0.009")


def test_unexpected_reported_currency_keeps_billing_and_blocks_money_claims() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal("1")))
    entry = ledger.reserve(RequestEstimate(10, 10, pricing=TokenPricing.uniform(1)))
    ledger.start(entry.request_id)
    ledger.reconcile(entry.request_id, reported(10, 1), final=True, reported_cost=ReportedCost(Decimal("0.01"), "EUR"))
    assert ledger.snapshot().remaining_cost is None
    assert any(m.currency == "EUR" and m.reported_cost == Decimal("0.01") for m in ledger.snapshot().money)
    with pytest.raises(BudgetExceeded) as failure:
        ledger.reserve(RequestEstimate(1, 1, pricing=TokenPricing.uniform(0)))
    assert failure.value.reason == "currency_mismatch"


def test_partial_reported_billing_does_not_release_an_inflight_money_hold() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal("0.02")))
    entry = ledger.reserve(RequestEstimate(10, 10, pricing=TokenPricing.uniform(1)))
    ledger.start(entry.request_id)
    ledger.reconcile(entry.request_id, reported_cost=ReportedCost(Decimal("0.001"), "USD"))
    assert ledger.snapshot().remaining_cost == 0
    assert ledger.snapshot().money[0].held_cost == Decimal("0.02")
    with pytest.raises(BudgetExceeded):
        ledger.reserve(RequestEstimate(1, 1, pricing=TokenPricing.uniform(1)))
    ledger.reconcile(entry.request_id, reported_cost=ReportedCost(Decimal("0.012"), "USD"), final=True)
    assert ledger.snapshot().remaining_cost == Decimal("0.008")
    assert ledger.snapshot().unknown_dispatched_requests == 1  # Billing does not invent tokens.


def test_reported_billing_does_not_require_a_configured_price() -> None:
    ledger = RunBudgetLedger()
    entry = ledger.reserve(RequestEstimate(10, 10))
    ledger.start(entry.request_id)
    ledger.reconcile(entry.request_id, final=True, reported_cost=ReportedCost(Decimal("1.25"), "EUR"))
    snapshot = ledger.snapshot()
    assert snapshot.unknown_cost_requests == 0
    assert snapshot.money[0].reported_cost == Decimal("1.25")
    assert snapshot.remaining_cost is None
    assert snapshot.unknown_dispatched_requests == 1


def test_unknown_pricing_is_not_summarized_as_a_zero_currency_hold() -> None:
    ledger = RunBudgetLedger()
    entry = ledger.reserve(RequestEstimate(10, 10, pricing=TokenPricing(input_per_1k=1)))
    ledger.start(entry.request_id)
    snapshot = ledger.snapshot()
    assert snapshot.money[0].held_cost is None
    assert snapshot.money[0].unknown_cost_requests == 1
    assert snapshot.remaining_cost is None


def test_final_total_cannot_price_stale_partial_components() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal("0.020")))
    entry = ledger.reserve(RequestEstimate(10, 10, pricing=TokenPricing.uniform(1)))
    ledger.start(entry.request_id)
    ledger.reconcile(entry.request_id, reported(10, 1))
    record = ledger.reconcile(entry.request_id, UsageReport(total_tokens=20, source="reported"), final=True)
    assert record.settled_tokens == 20
    assert record.settled_estimated_cost is None
    assert record.held_cost == Decimal("0.020") and record.cost_uncertain
    assert ledger.snapshot().remaining_cost is None
    with pytest.raises(BudgetExceeded, match="unknown_price"):
        ledger.reserve(RequestEstimate(1, 1, pricing=TokenPricing.uniform(1)))
    ledger.reconcile(entry.request_id, reported(10, 10), final=True)
    assert ledger.snapshot().remaining_cost == 0


@pytest.mark.parametrize("usage", [
    UsageReport(total_tokens=100, source="reported"),
    UsageReport(prompt_tokens=100, source="reported"),
])
def test_partial_overrun_without_cost_breakdown_stops_money_admission(usage: UsageReport) -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal("0.1")))
    entry = ledger.reserve(RequestEstimate(10, 10, pricing=TokenPricing.uniform(1)))
    ledger.start(entry.request_id)
    record = ledger.reconcile(entry.request_id, usage)
    assert record.cost_uncertain
    assert ledger.snapshot().remaining_cost is None
    with pytest.raises(BudgetExceeded, match="unknown_price"):
        ledger.reserve(RequestEstimate(10, 10, pricing=TokenPricing.uniform(1)))


def test_partial_usage_can_reveal_an_unpriced_cache_mode() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal("0.1")))
    pricing = TokenPricing(input_per_1k=1, output_per_1k=1)
    estimate = RequestEstimate(10, 10, pricing=pricing, cache_mode="none")
    entry = ledger.reserve(estimate)
    ledger.start(entry.request_id)
    record = ledger.reconcile(entry.request_id, UsageReport(
        prompt_tokens=10, completion_tokens=1, cache_creation_tokens=10, source="reported",
    ))
    assert record.cost_uncertain and ledger.snapshot().remaining_cost is None
    with pytest.raises(BudgetExceeded, match="unknown_price"):
        ledger.reserve(estimate)


@pytest.mark.parametrize("precision,estimate,cap", [
    (4, RequestEstimate(1000, 3, pricing=TokenPricing.uniform(0.12345)), "0.12381"),
    (28, RequestEstimate(1, 1, pricing=TokenPricing(input_per_1k=1, output_per_1k=1e-30), cache_mode="none"), "0.001"),
])
def test_money_admission_never_rounds_down_to_the_cap(precision: int, estimate: RequestEstimate, cap: str) -> None:
    with localcontext() as context:
        context.prec = precision
        ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal(cap)))
        with pytest.raises(BudgetExceeded, match="money_limit"):
            ledger.reserve(estimate)
        assert ledger.snapshot().records == ()


def test_money_snapshots_and_reconciliation_ignore_decimal_context() -> None:
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=Decimal(1)))
    estimate = RequestEstimate(1000, 3, pricing=TokenPricing.uniform(0.12345))
    entries = [ledger.reserve(estimate) for _ in range(2)]
    for entry in entries:
        ledger.start(entry.request_id)
    with localcontext() as context:
        context.prec = 4
        context.traps[Inexact] = True
        snapshot = ledger.snapshot()
        assert snapshot.money[0].held_cost == Decimal("0.24764070")
        assert snapshot.remaining_cost == Decimal("0.75235930")
        ledger.reconcile(entries[0].request_id, reported(1000, 1), final=True,
                         reported_cost=ReportedCost(Decimal("0.123456789"), "USD"))
        assert ledger.snapshot().remaining_cost == Decimal("0.752722861")
        ledger.reconcile(entries[1].request_id, reported(1000, 2), final=True,
                         reported_cost=ReportedCost(Decimal("0.123456781"), "USD"))
        snapshot = ledger.snapshot()
        assert snapshot.money[0].settled_estimated_cost == Decimal("0.24727035")
        assert snapshot.money[0].reported_cost == Decimal("0.246913570")
        assert snapshot.money[0].settled_reported_cost == Decimal("0.246913570")
        assert snapshot.remaining_cost == Decimal("0.753086430")


def test_finite_money_limits_beyond_integer_string_conversion_limits_remain_usable() -> None:
    cap = Decimal("1e5000")
    ledger = RunBudgetLedger(limits=BudgetLimits(max_cost=cap))
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = True
        assert ledger.snapshot().remaining_cost == cap
        entry = ledger.reserve(RequestEstimate(1, 1, pricing=TokenPricing.uniform(0)))
        ledger.start(entry.request_id)
        ledger.reconcile(entry.request_id, final=True, reported_cost=ReportedCost(cap, "USD"))
        assert ledger.snapshot().remaining_cost == 0
        assert ledger.snapshot().money[0].settled_reported_cost == cap


@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_invalid_count_limits_are_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        BudgetLimits(max_requests=value)
