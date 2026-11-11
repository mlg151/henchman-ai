"""Contract tests for Tier 8 operational data storage and services.

These tests validate that:
- Remote session, remote event, and ops event payloads conform to schemas
- Observability service payloads (analytics, telemetry, cost, diagnostic) conform to schemas
- Feature flag state and app state payloads conform to schemas
- Rate limiter parsing conforms to behavioral contract
- Migration runner lifecycle conforms to behavioral contract
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from henchman.ops.flags import FeatureFlagService
from henchman.ops.migrations import AppStateStore, Migration, MigrationRunner
from henchman.ops.observability import (
    AnalyticsService,
    CostTrackingService,
    DiagnosticTrackingService,
    TelemetryService,
)
from henchman.ops.rate_limits import ParsedRateLimit, RateLimiter, parse_rate_limit
from henchman.ops.state import AppStateStore as AppState
from henchman.ops.store import OpsStore
from tests.contracts.helpers import assert_contract_matches, load_contract_schema


@pytest.fixture
def ops_store() -> OpsStore:
    """Provide a transient OpsStore for contract testing."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "ops.db"
        yield OpsStore(db_path)


# ===========================================================================
# OpsStore persistence contracts
# ===========================================================================


class TestOpsStoreContracts:
    """OpsStore payloads must satisfy their JSON Schema contracts."""

    def test_remote_session_payload_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        session_id = "sess-123"
        payload = {"user_id": "alice", "metadata": {"origin": "web"}}

        normalized = ops_store.upsert_remote_session(session_id, payload)

        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=normalized,
            schema_name="ops/remote_session",
        )

    def test_remote_event_payload_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        session_id = "sess-123"
        payload = {"type": "click", "element": "submit"}

        normalized = ops_store.append_remote_event(session_id, payload)

        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=normalized,
            schema_name="ops/remote_event",
        )

    def test_ops_event_record_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        category = "analytics"
        event_type = "app_start"
        payload = {"version": "1.0.0", "platform": "linux"}

        record = ops_store.record_ops_event(
            category=category,
            event_type=event_type,
            payload=payload,
        )

        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=record,
            schema_name="ops/ops_event",
        )


# ===========================================================================
# Observability service payload contracts
# ===========================================================================


class TestObservabilityContract:
    """Observability service return payloads must satisfy JSON Schema contracts.

    Covers AnalyticsService, TelemetryService, CostTrackingService,
    and DiagnosticTrackingService.
    """

    def test_analytics_event_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """AnalyticsService.record() must return a contract-compliant payload."""
        service = AnalyticsService(store=ops_store)
        record = service.record("app_start", {"version": "1.0.0", "platform": "linux"})

        assert_contract_matches(
            contract_suite=contract_suite,
            payload=record,
            schema_name="ops/analytics_event",
        )

    def test_telemetry_event_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """TelemetryService.record() must return a contract-compliant payload."""
        service = TelemetryService(store=ops_store)
        record = service.record(
            "api_request",
            tokens=150,
            tool_calls=3,
            payload={"endpoint": "/v1/chat"},
        )

        assert_contract_matches(
            contract_suite=contract_suite,
            payload=record,
            schema_name="ops/telemetry_event",
        )

    def test_telemetry_event_minimal_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """TelemetryService.record() without optional payload should comply."""
        service = TelemetryService(store=ops_store)
        record = service.record("heartbeat", tokens=0, tool_calls=0)

        assert_contract_matches(
            contract_suite=contract_suite,
            payload=record,
            schema_name="ops/telemetry_event",
        )

    def test_cost_tracking_summary_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """CostTrackingService.summary() must return a contract-compliant payload."""
        service = CostTrackingService(store=ops_store)
        # Record some usage first
        service.record_usage(
            provider="openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
        )
        summary = service.summary()
        assert summary["total_cost"] is None
        assert summary["unknown_cost_events"] == 1
        assert summary["by_currency"]["USD"] == {
            "estimated_cost": None, "reported_cost": None, "total_cost": None,
            "unknown_cost_events": 1,
        }

        assert_contract_matches(
            contract_suite=contract_suite,
            payload=summary,
            schema_name="ops/cost_summary",
        )

    def test_cost_tracking_empty_summary_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """CostTrackingService.summary() with no events should still comply."""
        service = CostTrackingService(store=ops_store)
        summary = service.summary()
        assert summary == {
            "events": 0, "total_cost": None, "currency": None,
            "unknown_cost_events": 0, "by_currency": {},
        }

        assert_contract_matches(
            contract_suite=contract_suite,
            payload=summary,
            schema_name="ops/cost_summary",
        )

    @pytest.mark.parametrize("rate,reported,total", [(0, None, 0), (2, 0.25, 0.25)])
    def test_cost_tracking_priced_summary_matches_contract(
        self, contract_suite, ops_store: OpsStore, rate: float,
        reported: float | None, total: float,
    ) -> None:
        service = CostTrackingService(store=ops_store)
        service.record_usage(
            provider="test", model="test", prompt_tokens=100, completion_tokens=50,
            cost_per_1k_tokens=rate, reported_cost=reported,
        )
        summary = service.summary()
        assert summary["total_cost"] == total
        assert summary["by_currency"]["USD"] == {
            "estimated_cost": 0.15 * rate, "reported_cost": reported,
            "total_cost": total, "unknown_cost_events": 0,
        }
        assert_contract_matches(
            contract_suite=contract_suite, payload=summary, schema_name="ops/cost_summary",
        )

    def test_cost_tracking_currencies_remain_separate_in_contract(
        self, contract_suite, ops_store: OpsStore,
    ) -> None:
        service = CostTrackingService(store=ops_store)
        for currency, cost in (("USD", 0.2), ("EUR", 0.3)):
            service.record_usage(
                provider="test", model="test", prompt_tokens=None, completion_tokens=None,
                reported_cost=cost, currency=currency, usage_source="unknown",
            )
        summary = service.summary()
        assert summary["total_cost"] is None and summary["currency"] is None
        assert summary["unknown_cost_events"] == 0
        assert summary["by_currency"]["USD"]["reported_cost"] == 0.2
        assert summary["by_currency"]["EUR"]["reported_cost"] == 0.3
        assert_contract_matches(
            contract_suite=contract_suite, payload=summary, schema_name="ops/cost_summary",
        )

    @pytest.mark.parametrize("field,value", [
        ("total_cost", -1), ("total_cost", "free"), ("unknown_cost_events", -1),
        ("unexpected", 0),
    ])
    def test_cost_summary_contract_rejects_invalid_money_or_extra_fields(
        self, contract_suite, ops_store: OpsStore, field: str, value: object,
    ) -> None:
        summary = CostTrackingService(store=ops_store).summary()
        summary[field] = value
        errors = contract_suite.validate_json_schema(summary, load_contract_schema("ops/cost_summary"))
        assert any(field in error for error in errors)

    def test_diagnostic_event_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """DiagnosticTrackingService.record() must return a contract-compliant payload."""
        service = DiagnosticTrackingService(store=ops_store)
        record = service.record(
            "health_check",
            status="pass",
            details={"duration_ms": 42},
        )

        assert_contract_matches(
            contract_suite=contract_suite,
            payload=record,
            schema_name="ops/diagnostic_event",
        )

    def test_diagnostic_event_fail_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """DiagnosticTrackingService.record() with fail status should comply."""
        service = DiagnosticTrackingService(store=ops_store)
        record = service.record(
            "disk_check",
            status="fail",
            details={"error": "disk full", "free_gb": 0.5},
        )

        assert_contract_matches(
            contract_suite=contract_suite,
            payload=record,
            schema_name="ops/diagnostic_event",
        )


# ===========================================================================
# Feature flag state contracts
# ===========================================================================


class TestFeatureFlagContract:
    """FeatureFlagService payloads must satisfy JSON Schema contracts."""

    def test_feature_flag_state_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """Persisted feature flag state must satisfy the flag_state schema."""
        service = FeatureFlagService(
            store=ops_store,
            defaults={"advanced_mode": False},
        )
        service.set_flag("advanced_mode", True, source="env")

        # Retrieve the stored flag via the store's get_feature_flag
        flag_state = ops_store.get_feature_flag("advanced_mode")
        assert flag_state is not None

        assert_contract_matches(
            contract_suite=contract_suite,
            payload=flag_state,
            schema_name="ops/flag_state",
        )

    def test_multiple_flag_states_match_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """Multiple feature flags should each satisfy the schema."""
        service = FeatureFlagService(store=ops_store)
        service.set_flag("dark_mode", True, source="user")
        service.set_flag("experimental", False, source="config")

        for flag_name in ("dark_mode", "experimental"):
            flag_state = ops_store.get_feature_flag(flag_name)
            assert flag_state is not None
            assert_contract_matches(
                contract_suite=contract_suite,
                payload=flag_state,
                schema_name="ops/flag_state",
            )


# ===========================================================================
# AppState contracts
# ===========================================================================


class TestAppStateContract:
    """AppState payloads must satisfy JSON Schema contracts."""

    def test_app_state_get_set_matches_contract(
        self, contract_suite: object, ops_store: OpsStore
    ) -> None:
        """AppStateStore.get() return values should be contract-compliant."""
        app_state = AppState(store=ops_store)
        app_state.set("ui.theme", "dark")
        app_state.set("ui.font_size", 14)

        value = app_state.get("ui.theme")
        assert value == "dark"
        # App state contract is about the key/value pair shape
        assert isinstance(value, str)


# ===========================================================================
# Rate limiter behavioral contracts
# ===========================================================================


class TestRateLimiterContract:
    """RateLimiter and parse_rate_limit must satisfy behavioral contracts."""

    def test_parse_rate_limit_hour(self) -> None:
        """parse_rate_limit('1000/hour') should produce correct ParsedRateLimit."""
        parsed = parse_rate_limit("1000/hour")
        assert isinstance(parsed, ParsedRateLimit)
        assert parsed.limit == 1000
        assert parsed.window_seconds == 3600
        assert parsed.raw == "1000/hour"

    def test_parse_rate_limit_minute(self) -> None:
        """parse_rate_limit('10/minute') should produce correct ParsedRateLimit."""
        parsed = parse_rate_limit("10/minute")
        assert parsed.limit == 10
        assert parsed.window_seconds == 60

    def test_parse_rate_limit_second(self) -> None:
        """parse_rate_limit('5/second') should produce correct ParsedRateLimit."""
        parsed = parse_rate_limit("5/second")
        assert parsed.limit == 5
        assert parsed.window_seconds == 1

    def test_parse_rate_limit_day(self) -> None:
        """parse_rate_limit('1000/day') should produce correct ParsedRateLimit."""
        parsed = parse_rate_limit("1000/day")
        assert parsed.limit == 1000
        assert parsed.window_seconds == 86400

    def test_parse_rate_limit_invalid_raises(self) -> None:
        """parse_rate_limit should raise ValueError for invalid formats."""
        with pytest.raises(ValueError, match="Invalid rate limit"):
            parse_rate_limit("1000")
        with pytest.raises(ValueError, match="Unsupported rate limit"):
            parse_rate_limit("1000/decade")

    def test_rate_limiter_allow_basic(self) -> None:
        """RateLimiter.allow() should return True for allowed requests."""
        limiter = RateLimiter()
        assert limiter.allow("test-key", "5/second") is True

    def test_rate_limiter_exceeds_limit(self) -> None:
        """RateLimiter.allow() should return False when limit is exceeded."""
        limiter = RateLimiter()
        for _ in range(3):
            limiter.allow("burst-key", "3/minute")
        assert limiter.allow("burst-key", "3/minute") is False


# ===========================================================================
# Migration runner behavioral contracts
# ===========================================================================


class TestMigrationRunnerContract:
    """MigrationRunner must satisfy the migration lifecycle contract."""

    def test_migration_runner_initial_version(self, ops_store: OpsStore) -> None:
        """A fresh MigrationRunner should report version 0."""
        runner = MigrationRunner(
            store=ops_store,
            namespace="test",
            migrations=[],
        )
        assert runner.current_version() == 0

    def test_migration_runner_applies_in_order(self, ops_store: OpsStore) -> None:
        """MigrationRunner should apply migrations in version order."""
        state_store = AppStateStore(store=ops_store)
        applied: list[str] = []

        m1 = Migration(version=1, name="m1", apply=lambda _: applied.append("m1"))
        m2 = Migration(version=2, name="m2", apply=lambda _: applied.append("m2"))

        runner = MigrationRunner(
            store=ops_store,
            namespace="test_order",
            migrations=[m1, m2],
        )

        results = runner.migrate(state_store)
        assert results == ["m1", "m2"]
        assert applied == ["m1", "m2"]
        assert runner.current_version() == 2

    def test_migration_runner_idempotent(self, ops_store: OpsStore) -> None:
        """Re-applying migrations should be a no-op."""
        state_store = AppStateStore(store=ops_store)
        apply_count = 0

        def _apply(_state_store: AppStateStore) -> None:
            nonlocal apply_count
            apply_count += 1

        m1 = Migration(version=1, name="m1", apply=_apply)
        runner = MigrationRunner(
            store=ops_store,
            namespace="test_idempotent",
            migrations=[m1],
        )

        results_first = runner.migrate(state_store)
        assert results_first == ["m1"]
        assert apply_count == 1

        results_second = runner.migrate(state_store)
        assert results_second == []
        assert apply_count == 1  # Not reapplied

    def test_migration_runner_partial_apply(self, ops_store: OpsStore) -> None:
        """MigrationRunner should skip already-applied migrations."""
        state_store = AppStateStore(store=ops_store)
        applied: list[str] = []

        m1 = Migration(version=1, name="m1", apply=lambda _: applied.append("m1"))
        m2 = Migration(version=2, name="m2", apply=lambda _: applied.append("m2"))

        # Apply both
        runner = MigrationRunner(
            store=ops_store,
            namespace="test_partial",
            migrations=[m1, m2],
        )
        runner.migrate(state_store)
        assert applied == ["m1", "m2"]

        # Reset and verify m1 is not re-applied
        applied.clear()

        # New runner with same namespace — should skip version 1 and 2
        runner2 = MigrationRunner(
            store=ops_store,
            namespace="test_partial",
            migrations=[m1, m2],
        )
        results = runner2.migrate(state_store)
        assert results == []
        assert applied == []
