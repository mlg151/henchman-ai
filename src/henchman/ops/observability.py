"""Observability services for analytics, telemetry, costs, and diagnostics."""

from __future__ import annotations

from typing import Any

from henchman.ops.store import OpsStore


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

    def __init__(self, *, store: OpsStore, default_cost_per_1k_tokens: float = 0.002) -> None:
        """Initialize the cost tracking service.

        Args:
            store: Shared operations store.
            default_cost_per_1k_tokens: Default cost rate for synthetic cost tracking.
        """
        self._store = store
        self._default_cost_per_1k_tokens = default_cost_per_1k_tokens

    def record_usage(
        self,
        *,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_per_1k_tokens: float | None = None,
    ) -> float:
        """Record model usage and return the computed cost.

        Args:
            provider: Provider name.
            model: Model name.
            prompt_tokens: Prompt token count.
            completion_tokens: Completion token count.
            cost_per_1k_tokens: Optional rate override.

        Returns:
            Computed total cost.
        """
        total_tokens = prompt_tokens + completion_tokens
        rate = cost_per_1k_tokens or self._default_cost_per_1k_tokens
        total_cost = round((total_tokens / 1000) * rate, 6)
        self._store.record_ops_event(
            category="cost",
            event_type="model_usage",
            payload={
                "provider": provider,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "total_cost": total_cost,
            },
        )
        return total_cost

    def summary(self) -> dict[str, float | int]:
        """Return a compact cost summary."""
        events = self._store.list_ops_events("cost")
        total_cost = round(
            sum(float(event["payload"].get("total_cost", 0.0)) for event in events),
            6,
        )
        return {"events": len(events), "total_cost": total_cost}


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
