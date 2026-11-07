"""Observability services for analytics, telemetry, costs, and diagnostics."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from henchman.ops.store import OpsStore
from henchman.providers.usage import TokenPricing, UsageReport, UsageSource, validate_money


class AnalyticsService:
    """Record and query product analytics events."""

    def __init__(self, *, store: OpsStore) -> None:
        """Initialize the analytics service.

        Args:
            store: Shared operations store.
        """
        self._store = store

    def record(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Record an analytics event.

        Args:
            event_type: Event name.
            payload: Structured event details.

        Returns:
            Persisted event record.
        """
        return self._store.record_ops_event(
            category="analytics",
            event_type=event_type,
            payload=payload,
        )

    def count(self, event_type: str | None = None) -> int:
        """Count matching analytics events.

        Args:
            event_type: Optional event name filter.

        Returns:
            Number of matching events.
        """
        events = self._store.list_ops_events("analytics")
        if event_type is None:
            return len(events)
        return sum(1 for event in events if event["event_type"] == event_type)


class TelemetryService:
    """Record operational telemetry for API and tool usage."""

    def __init__(self, *, store: OpsStore) -> None:
        """Initialize the telemetry service.

        Args:
            store: Shared operations store.
        """
        self._store = store

    def record(
        self,
        event_type: str,
        *,
        tokens: int,
        tool_calls: int,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a telemetry event.

        Args:
            event_type: Event name.
            tokens: Token count associated with the event.
            tool_calls: Tool-call count associated with the event.
            payload: Optional additional payload fields.

        Returns:
            Persisted event record.
        """
        telemetry_payload = dict(payload or {})
        telemetry_payload["tokens"] = tokens
        telemetry_payload["tool_calls"] = tool_calls
        return self._store.record_ops_event(
            category="telemetry",
            event_type=event_type,
            payload=telemetry_payload,
        )

    def list_events(self) -> list[dict[str, Any]]:
        """List telemetry events in chronological order."""
        return self._store.list_ops_events("telemetry")


class CostTrackingService:
    """Track model usage costs without depending on a remote billing backend."""

    def __init__(self, *, store: OpsStore, default_cost_per_1k_tokens: float | None = None) -> None:
        """Initialize the cost tracking service.

        Args:
            store: Shared operations store.
            default_cost_per_1k_tokens: Explicit uniform estimate, or unknown pricing.
        """
        self._store = store
        self._default_pricing = (
            TokenPricing.uniform(default_cost_per_1k_tokens)
            if default_cost_per_1k_tokens is not None else None
        )

    def record_usage(
        self,
        *,
        provider: str,
        model: str,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        cost_per_1k_tokens: float | None = None,
        cached_tokens: int | None = None,
        cache_creation_tokens: int | None = None,
        usage_source: UsageSource = "reported",
        pricing: TokenPricing | None = None,
        reported_cost: float | None = None,
        currency: str | None = None,
    ) -> float | None:
        """Record usage with separate price estimates and provider-reported billing.

        Cache counts are subsets of prompt tokens. Missing prices/counts remain
        unknown; configured prices never become reported billing. The returned
        amount prefers explicitly reported billing, then an available estimate.
        """
        if pricing is not None and cost_per_1k_tokens is not None:
            raise ValueError("Provide pricing or a uniform cost rate, not both")
        if cost_per_1k_tokens is not None:
            pricing = TokenPricing.uniform(cost_per_1k_tokens)
        elif pricing is None:
            pricing = self._default_pricing
        effective_currency = currency or (pricing.currency if pricing else "USD")
        if pricing is not None and pricing.currency != effective_currency:
            raise ValueError("Reported currency must match the price estimate currency")
        TokenPricing(currency=effective_currency)
        if reported_cost is not None:
            validate_money(reported_cost, "reported_cost")
        usage = UsageReport(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            cached_tokens=cached_tokens, cache_creation_tokens=cache_creation_tokens,
            source=usage_source,
        )
        estimated_cost = pricing.estimate(usage) if pricing is not None else None
        total_cost = reported_cost if reported_cost is not None else estimated_cost
        cost_source = (
            "reported" if reported_cost is not None
            else "estimated" if estimated_cost is not None else "unknown"
        )
        self._store.record_ops_event(
            category="cost",
            event_type="model_usage",
            payload={
                "provider": provider,
                "model": model,
                **asdict(usage),
                "usage_source": usage.source,
                "total_cost": total_cost,
                "estimated_cost": estimated_cost,
                "reported_cost": reported_cost,
                "cost_source": cost_source,
                "currency": effective_currency,
                "pricing": asdict(pricing) if pricing is not None else None,
            },
        )
        return total_cost

    def summary(self) -> dict[str, Any]:
        """Summarize estimates and billing separately without converting currencies."""
        events = self._store.list_ops_events("cost")
        by_currency: dict[str, dict[str, Any]] = {}
        unknown = 0
        for event in events:
            payload = event["payload"]
            totals = by_currency.setdefault(payload.get("currency", "USD"), {
                "estimated_cost": None, "reported_cost": None, "total_cost": None,
                "unknown_cost_events": 0,
            })
            for key in ("estimated_cost", "reported_cost"):
                if payload.get(key) is not None:
                    totals[key] = (totals[key] or 0) + payload[key]
            if payload.get("cost_source", "unknown") == "unknown" or payload.get("total_cost") is None:
                unknown += 1
                totals["unknown_cost_events"] += 1
            else:
                totals["total_cost"] = (totals["total_cost"] or 0) + payload["total_cost"]
        for totals in by_currency.values():
            if totals["unknown_cost_events"]:
                totals["total_cost"] = None
        currency = next(iter(by_currency)) if len(by_currency) == 1 else None
        return {
            "events": len(events),
            "total_cost": by_currency[currency]["total_cost"] if currency else None,
            "currency": currency,
            "unknown_cost_events": unknown,
            "by_currency": by_currency,
        }


class DiagnosticTrackingService:
    """Record diagnostic checks and health probes."""

    def __init__(self, *, store: OpsStore) -> None:
        """Initialize the diagnostics service.

        Args:
            store: Shared operations store.
        """
        self._store = store

    def record(self, event_type: str, *, status: str, details: dict[str, Any]) -> dict[str, Any]:
        """Record one diagnostic event.

        Args:
            event_type: Diagnostic event name.
            status: Status label such as ``pass`` or ``fail``.
            details: Event details.

        Returns:
            Persisted event record.
        """
        payload = dict(details)
        payload["status"] = status
        return self._store.record_ops_event(
            category="diagnostic",
            event_type=event_type,
            payload=payload,
        )

    def list_events(self, *, status: str | None = None) -> list[dict[str, Any]]:
        """List diagnostic events, optionally filtered by status.

        Args:
            status: Optional status filter.

        Returns:
            Matching diagnostic events.
        """
        events = self._store.list_ops_events("diagnostic")
        if status is None:
            return events
        return [event for event in events if event["payload"].get("status") == status]
