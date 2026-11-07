"""Run evidence preserves observation provenance without changing admission."""

from decimal import Decimal

from henchman.core.run_accounting import budget_snapshot_payload
from henchman.core.run_budget import RequestEstimate, RunBudgetLedger
from henchman.providers.usage import TokenPricing, UsageReport
from henchman.utils.evidence_redaction import EvidenceRedactor


def dispatch(ledger, usage=None, *, pricing=None, final=True, provider="compatible", model="model"):
    record = ledger.reserve(RequestEstimate(20, 10, pricing), provider=provider, model=model)
    ledger.start(record.request_id)
    if usage is not None:
        ledger.reconcile(record.request_id, usage, final=final)
    else:
        ledger.cancel(record.request_id)
    return record


def test_usage_summary_separates_sources_and_partial_counts_without_recounting_snapshots():
    ledger = RunBudgetLedger()
    record = dispatch(ledger, UsageReport(prompt_tokens=10, completion_tokens=2, cached_tokens=4, source="reported"))
    ledger.reconcile(record.request_id, UsageReport(prompt_tokens=10, completion_tokens=2, cached_tokens=4, source="reported"), final=True)
    dispatch(ledger, UsageReport(prompt_tokens=3, source="reported"), final=False)
    dispatch(ledger, UsageReport(total_tokens=8, source="estimated"))
    dispatch(ledger)
    cancelled = ledger.reserve(RequestEstimate(100, 100), provider="never-sent", model="unused")
    ledger.cancel(cancelled.request_id)
    ledger.reserve(RequestEstimate(100, 100), provider="not-yet-sent", model="unused")
    before = ledger.export_state()

    payload = budget_snapshot_payload(ledger.snapshot())
    rows = {row["usage_source"]: row for row in payload["usage_breakdown"]}
    assert set(rows) == {"reported", "estimated", "unknown"}
    reported = rows["reported"]
    assert reported["dispatched_requests"] == 2
    assert reported["settled_requests"] == 1
    assert reported["counts"]["total_tokens"] == 12
    assert reported["counted_requests"]["total_tokens"] == 1
    assert reported["counts"]["prompt_tokens"] == 13
    assert reported["counted_requests"]["prompt_tokens"] == 2
    assert reported["counts"]["cached_tokens"] == 4
    assert reported["counted_requests"]["cached_tokens"] == 1
    assert rows["estimated"]["counts"]["total_tokens"] == 8
    assert rows["estimated"]["settled_requests"] == 0
    assert all(value is None for value in rows["unknown"]["counts"].values())
    assert all(value == 0 for value in rows["unknown"]["counted_requests"].values())
    assert payload["settled_tokens"] == 12
    assert payload["held_tokens"] == 290
    assert all(row["provider"] == "compatible" and row["pricing"] is None for row in rows.values())
    after = ledger.export_state()
    assert after.attempts == before.attempts


def test_usage_summary_retains_distinct_exact_price_snapshots_and_explicit_zero():
    ledger = RunBudgetLedger()
    prices = [
        TokenPricing(Decimal("0"), Decimal("0"), source="local configured", as_of="2026-11-07"),
        TokenPricing(Decimal("0.000000000000000000000000000001"), Decimal("2"), currency="EUR", source="later catalog", as_of="2026-11-08"),
    ]
    for price in prices:
        dispatch(ledger, UsageReport(prompt_tokens=1, completion_tokens=1, source="reported"), pricing=price)
    dispatch(ledger, UsageReport(total_tokens=0, source="reported"), model="unknown-priced")
    rows = budget_snapshot_payload(ledger.snapshot())["usage_breakdown"]
    assert len(rows) == 3
    assert rows[0]["pricing"]["input_per_1k"] == "0"
    assert rows[0]["pricing"]["cache_read_per_1k"] is None
    assert rows[1]["pricing"]["input_per_1k"] == "1E-30"
    assert rows[1]["pricing"]["currency"] == "EUR"
    assert [(row["pricing"]["source"], row["pricing"]["as_of"]) for row in rows[:2]] == [
        ("local configured", "2026-11-07"), ("later catalog", "2026-11-08"),
    ]
    assert rows[2]["model"] == "unknown-priced" and rows[2]["pricing"] is None
    assert rows[2]["counts"]["total_tokens"] == 0
    assert rows[2]["counted_requests"]["total_tokens"] == 1


def test_usage_summary_projects_labels_with_current_policy_without_changing_authority():
    ledger = RunBudgetLedger()
    dispatch(ledger, provider="old-secret-provider", model="new-secret-model",
             pricing=TokenPricing.uniform(0))
    policy = EvidenceRedactor(["old-secret"])
    policy.register_secret("new-secret")
    payload = budget_snapshot_payload(ledger.snapshot(), redactor=policy)
    row = payload["usage_breakdown"][0]
    assert row["provider"] == "[REDACTED]-provider"
    assert row["model"] == "[REDACTED]-model"
    assert ledger.snapshot().records[0].provider == "old-secret-provider"
    assert ledger.snapshot().records[0].model == "new-secret-model"


def test_usage_summary_survives_durable_reopen_without_double_counting(tmp_path):
    from henchman.ops.run_budget_store import RunBudgetStore

    store = RunBudgetStore(tmp_path / "ops.db")
    ledger = store.create_run(run_id="retained", project_hash="project", session_id="session")
    record = dispatch(ledger, UsageReport(prompt_tokens=10, completion_tokens=2, source="reported"),
                      pricing=TokenPricing.uniform(Decimal("0.000000000000000000001")))
    expected = budget_snapshot_payload(ledger.snapshot())["usage_breakdown"]
    reopened = RunBudgetStore(tmp_path / "ops.db").resume_run(
        "retained", store_id=store.store_id, project_hash="project", session_id="session",
    )
    reopened.reconcile(record.request_id, UsageReport(total_tokens=12, source="reported"), final=True)
    before = (tmp_path / "ops.db").read_bytes()
    inspection = RunBudgetStore.inspect_session(tmp_path / "ops.db", "project", "session")
    assert inspection is not None and inspection.snapshot is not None
    assert budget_snapshot_payload(inspection.snapshot)["usage_breakdown"] == expected
    assert inspection.snapshot.consumed_requests == 1
    # Read-only inspection does not persist a new projection or alter accounting.
    assert (tmp_path / "ops.db").read_bytes() == before
