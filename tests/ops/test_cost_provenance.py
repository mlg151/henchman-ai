"""Cost observations never fabricate prices or conflate estimates with billing."""

from pathlib import Path

import pytest

from henchman.ops.observability import CostTrackingService
from henchman.ops.store import OpsStore
from henchman.providers.usage import TokenPricing


@pytest.fixture
def store(tmp_path: Path) -> OpsStore:
    return OpsStore(tmp_path / "ops.db")


def test_unpriced_usage_has_unknown_cost(store: OpsStore) -> None:
    service = CostTrackingService(store=store)
    assert service.record_usage(provider="test", model="test", prompt_tokens=100, completion_tokens=20) is None
    payload = store.list_ops_events("cost")[0]["payload"]
    assert payload["cost_source"] == "unknown"
    assert payload["total_cost"] is None
    assert payload["usage_source"] == "reported"
    assert service.summary()["total_cost"] is None
    assert service.summary()["unknown_cost_events"] == 1


def test_explicit_zero_overrides_configured_default(store: OpsStore) -> None:
    service = CostTrackingService(store=store, default_cost_per_1k_tokens=10)
    assert service.record_usage(
        provider="local", model="test", prompt_tokens=100, completion_tokens=20,
        cost_per_1k_tokens=0,
    ) == 0
    payload = store.list_ops_events("cost")[0]["payload"]
    assert payload["cost_source"] == "estimated"
    assert payload["estimated_cost"] == 0
    assert payload["reported_cost"] is None


def test_input_output_cache_rates_are_separate_and_snapshotted(store: OpsStore) -> None:
    service = CostTrackingService(store=store)
    pricing = TokenPricing(
        input_per_1k=2, output_per_1k=10, cache_read_per_1k=0.5, cache_write_per_1k=3,
        source="configured:test", as_of="2026-11-07",
    )
    amount = service.record_usage(
        provider="test", model="one", prompt_tokens=1000, completion_tokens=100,
        cached_tokens=600, cache_creation_tokens=100, pricing=pricing,
    )
    assert amount == pytest.approx(2.2)
    payload = store.list_ops_events("cost")[0]["payload"]
    assert payload["pricing"]["source"] == "configured:test"
    assert payload["pricing"]["as_of"] == "2026-11-07"
    assert payload["cost_source"] == "estimated"
    assert payload["reported_cost"] is None


def test_missing_cache_rate_or_counts_keeps_cost_unknown(store: OpsStore) -> None:
    service = CostTrackingService(store=store)
    assert service.record_usage(
        provider="test", model="test", prompt_tokens=100, completion_tokens=20,
        cached_tokens=60, pricing=TokenPricing(input_per_1k=2, output_per_1k=10),
    ) is None
    assert service.record_usage(
        provider="test", model="test", prompt_tokens=None, completion_tokens=20,
        cost_per_1k_tokens=0,
    ) is None


def test_billing_and_estimates_are_separate_across_currency_changes(store: OpsStore) -> None:
    service = CostTrackingService(store=store)
    service.record_usage(
        provider="test", model="test", prompt_tokens=1000, completion_tokens=0,
        pricing=TokenPricing(input_per_1k=2, output_per_1k=10, currency="USD"),
        reported_cost=1.5,
    )
    service.record_usage(
        provider="test", model="test", prompt_tokens=1000, completion_tokens=0,
        pricing=TokenPricing(input_per_1k=3, output_per_1k=10, currency="EUR"),
    )
    first = store.list_ops_events("cost")[0]["payload"]
    assert first["reported_cost"] == 1.5
    assert first["estimated_cost"] == 2
    assert first["cost_source"] == "reported"
    summary = service.summary()
    assert summary["total_cost"] is None
    assert summary["by_currency"]["USD"]["reported_cost"] == 1.5
    assert summary["by_currency"]["EUR"]["estimated_cost"] == 3


def test_partial_estimates_do_not_hide_unknown_costs(store: OpsStore) -> None:
    service = CostTrackingService(store=store)
    service.record_usage(
        provider="test", model="test", prompt_tokens=1000, completion_tokens=0,
        cost_per_1k_tokens=2, usage_source="estimated",
    )
    service.record_usage(provider="test", model="test", prompt_tokens=1000, completion_tokens=0)
    summary = service.summary()
    assert summary["total_cost"] is None
    assert summary["by_currency"]["USD"]["estimated_cost"] == 2
    assert summary["unknown_cost_events"] == 1
    assert store.list_ops_events("cost")[0]["payload"]["usage_source"] == "estimated"


def test_zero_reported_billing_is_distinct_from_a_zero_estimate(store: OpsStore) -> None:
    service = CostTrackingService(store=store)
    assert service.record_usage(
        provider="test", model="test", prompt_tokens=None, completion_tokens=None,
        usage_source="unknown", reported_cost=0,
    ) == 0
    payload = store.list_ops_events("cost")[0]["payload"]
    assert payload["reported_cost"] == 0
    assert payload["estimated_cost"] is None
    assert payload["cost_source"] == "reported"
    assert service.summary()["total_cost"] == 0


@pytest.mark.parametrize("rate", [-1, float("nan"), float("inf"), True])
def test_invalid_prices_are_rejected(rate: float) -> None:
    with pytest.raises(ValueError, match="finite nonnegative"):
        TokenPricing(input_per_1k=rate, output_per_1k=1)
