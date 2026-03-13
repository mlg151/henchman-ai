"""Tests for henchman.metrics.collector."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from henchman.core.events import AgentEvent, EventType
from henchman.metrics.collector import (
    CollectorConfig,
    MetricsCollector,
    ToolExecutionParams,
    _build_cost_metric,
    _build_performance_metric,
    _build_token_metric,
    _increment_sampled_counter,
    _store_provider_metric,
)
from henchman.metrics.models import (
    CostData,
    CostMetric,
    PerformanceEventData,
    TokenMetric,
    TokenUsageData,
)
from henchman.metrics.storage import MetricsStorage
from henchman.providers.base import ToolCall


@pytest.fixture()
def tmp_storage(tmp_path: Path) -> MetricsStorage:
    """Create a temporary MetricsStorage for tests."""
    return MetricsStorage(
        db_path=tmp_path / "collector_test.db",
        retention_days=None,
        max_metrics=None,
    )


@pytest.fixture()
def collector(tmp_storage: MetricsStorage) -> MetricsCollector:
    """Create a MetricsCollector with a temporary storage."""
    cfg = CollectorConfig(
        enabled=True,
        anonymize=False,
        sampling_rate=1.0,
        session_id="test-session",
    )
    return MetricsCollector(config=cfg, storage=tmp_storage)


@pytest.fixture()
def disabled_collector(tmp_storage: MetricsStorage) -> MetricsCollector:
    """Create a disabled MetricsCollector."""
    cfg = CollectorConfig(enabled=False, session_id="disabled-session")
    return MetricsCollector(config=cfg, storage=tmp_storage)


class TestCollectorConfig:
    """Tests for CollectorConfig dataclass."""

    def test_defaults(self) -> None:
        """Test CollectorConfig default values."""
        cfg = CollectorConfig()
        assert cfg.enabled is True
        assert cfg.anonymize is True
        assert cfg.sampling_rate == 1.0
        assert cfg.session_id is None
        assert cfg.user_id is None

    def test_custom_values(self) -> None:
        """Test CollectorConfig with custom values."""
        cfg = CollectorConfig(
            enabled=False,
            anonymize=False,
            sampling_rate=0.5,
            session_id="sess-1",
            user_id="user-1",
        )
        assert cfg.enabled is False
        assert cfg.sampling_rate == 0.5


class TestToolExecutionParams:
    """Tests for ToolExecutionParams dataclass."""

    def test_defaults(self) -> None:
        """Test ToolExecutionParams defaults."""
        p = ToolExecutionParams(tool_name="read_file")
        assert p.tool_name == "read_file"
        assert p.tool_category == ""
        assert p.input_size is None
        assert p.agent_id is None

    def test_custom_values(self) -> None:
        """Test ToolExecutionParams with all fields."""
        p = ToolExecutionParams(
            tool_name="write_file",
            tool_category="write",
            input_size=1024,
            agent_id="agent-1",
        )
        assert p.tool_category == "write"
        assert p.input_size == 1024


class TestMetricsCollectorInit:
    """Tests for MetricsCollector initialization."""

    def test_default_config(self, tmp_storage: MetricsStorage) -> None:
        """Test MetricsCollector with default config."""
        collector = MetricsCollector(storage=tmp_storage)
        assert collector.enabled is True
        assert collector.anonymize is True
        assert collector.sampling_rate == 1.0
        assert collector.session_id  # UUID generated

    def test_custom_config(self, tmp_storage: MetricsStorage) -> None:
        """Test MetricsCollector with custom config."""
        cfg = CollectorConfig(
            enabled=True,
            anonymize=True,
            sampling_rate=0.5,
            user_id="user123",
            session_id="test-session",
        )
        c = MetricsCollector(config=cfg, storage=tmp_storage)
        assert c.session_id == "test-session"
        assert c.user_id_hash is not None  # Anonymized

    def test_anonymize_false_no_hash(self, tmp_storage: MetricsStorage) -> None:
        """Test that user_id_hash is None when anonymize=False."""
        cfg = CollectorConfig(anonymize=False, user_id="user123")
        c = MetricsCollector(config=cfg, storage=tmp_storage)
        assert c.user_id_hash is None

    def test_no_user_id_no_hash(self, tmp_storage: MetricsStorage) -> None:
        """Test that user_id_hash is None when no user_id given."""
        cfg = CollectorConfig(anonymize=True, user_id=None)
        c = MetricsCollector(config=cfg, storage=tmp_storage)
        assert c.user_id_hash is None

    def test_default_storage_created(self) -> None:
        """Test that default storage is created when none provided."""
        import appdirs

        with patch.object(appdirs, "user_data_dir", return_value="/tmp/test_henchman"):
            c = MetricsCollector()
            assert c.storage is not None


class TestShouldSample:
    """Tests for MetricsCollector.should_sample."""

    def test_enabled_full_rate(self, collector: MetricsCollector) -> None:
        """Test sampling at 100% rate always returns True."""
        assert collector.should_sample() is True

    def test_disabled(self, disabled_collector: MetricsCollector) -> None:
        """Test disabled collector never samples."""
        assert disabled_collector.should_sample() is False

    def test_partial_rate(self, tmp_storage: MetricsStorage) -> None:
        """Test sampling at partial rate sometimes returns True/False."""
        cfg = CollectorConfig(enabled=True, sampling_rate=0.0, session_id="s")
        c = MetricsCollector(config=cfg, storage=tmp_storage)
        # At 0.0 rate, random() is always >= 0.0, so should be False
        with patch("random.random", return_value=0.5):
            assert c.should_sample() is False

    def test_partial_rate_passes(self, tmp_storage: MetricsStorage) -> None:
        """Test sampling passes when random is below rate."""
        cfg = CollectorConfig(enabled=True, sampling_rate=0.9, session_id="s")
        c = MetricsCollector(config=cfg, storage=tmp_storage)
        with patch("random.random", return_value=0.1):
            assert c.should_sample() is True


class TestStartEndCommand:
    """Tests for start_command and end_command."""

    def test_start_command(self, collector: MetricsCollector) -> None:
        """Test starting a command sets state."""
        collector.start_command("chat", subcommand="save")
        assert collector._current_command == "chat"
        assert collector._command_start_time is not None

    def test_end_command_returns_metric(self, collector: MetricsCollector) -> None:
        """Test ending a command returns a UsageMetric."""
        collector.start_command("chat")
        metric = collector.end_command()
        assert metric is not None
        assert metric.command == "chat"
        assert metric.duration_ms >= 0

    def test_end_command_clears_state(self, collector: MetricsCollector) -> None:
        """Test that end_command clears the command state."""
        collector.start_command("chat")
        collector.end_command()
        assert collector._current_command is None
        assert collector._command_start_time is None

    def test_end_command_no_start_returns_none(self, collector: MetricsCollector) -> None:
        """Test end_command without start returns None."""
        result = collector.end_command()
        assert result is None

    def test_start_command_disabled(self, disabled_collector: MetricsCollector) -> None:
        """Test start_command does nothing when disabled."""
        disabled_collector.start_command("chat")
        assert disabled_collector._current_command is None

    def test_end_command_disabled(self, disabled_collector: MetricsCollector) -> None:
        """Test end_command returns None when disabled."""
        # Manually set state to ensure it's the sampling that blocks
        disabled_collector._command_start_time = time.time()
        result = disabled_collector.end_command()
        assert result is None

    def test_end_command_no_storage(self, tmp_path: Path) -> None:
        """Test end_command works when storage is None."""
        cfg = CollectorConfig(enabled=True, anonymize=False, session_id="s", sampling_rate=1.0)
        c = MetricsCollector(config=cfg, storage=MagicMock())
        c.storage = None  # type: ignore[assignment]
        c._current_command = "chat"
        c._command_start_time = time.time()
        metric = c.end_command()
        assert metric is not None
        assert metric.command == "chat"


class TestRecordTokenUsage:
    """Tests for record_token_usage."""

    def test_returns_token_metric(self, collector: MetricsCollector) -> None:
        """Test that record_token_usage returns a TokenMetric."""
        usage = TokenUsageData(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
        )
        result = collector.record_token_usage(usage)
        assert result is not None
        assert result.total_tokens == 150

    def test_calculates_token_ratio(self, collector: MetricsCollector) -> None:
        """Test token ratio is calculated from token_limit."""
        usage = TokenUsageData(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=100,
            token_limit=1000,
        )
        result = collector.record_token_usage(usage)
        assert result is not None
        assert result.token_ratio == pytest.approx(0.2)

    def test_no_token_ratio_without_limit(self, collector: MetricsCollector) -> None:
        """Test token_ratio is None when no token_limit."""
        usage = TokenUsageData(
            model="gpt-4", provider="openai", prompt_tokens=100, completion_tokens=50
        )
        result = collector.record_token_usage(usage)
        assert result is not None
        assert result.token_ratio is None

    def test_updates_accumulator(self, collector: MetricsCollector) -> None:
        """Test that token counts accumulator is updated."""
        usage = TokenUsageData(
            model="gpt-4", provider="openai", prompt_tokens=100, completion_tokens=50
        )
        collector.record_token_usage(usage)
        assert collector._token_counts["openai:gpt-4"] == 150

    def test_disabled_returns_none(self, disabled_collector: MetricsCollector) -> None:
        """Test disabled collector returns None."""
        usage = TokenUsageData(
            model="gpt-4", provider="openai", prompt_tokens=100, completion_tokens=50
        )
        assert disabled_collector.record_token_usage(usage) is None


class TestRecordCost:
    """Tests for record_cost."""

    def test_returns_cost_metric(self, collector: MetricsCollector) -> None:
        """Test that record_cost returns a CostMetric."""
        cost = CostData(
            model="gpt-4",
            provider="openai",
            prompt_cost=0.01,
            completion_cost=0.02,
        )
        result = collector.record_cost(cost)
        assert result is not None
        assert result.total_cost == pytest.approx(0.03)

    def test_updates_cost_accumulator(self, collector: MetricsCollector) -> None:
        """Test cost accumulator is updated."""
        cost = CostData(
            model="gpt-4",
            provider="openai",
            prompt_cost=0.01,
            completion_cost=0.02,
        )
        collector.record_cost(cost)
        assert collector._cost_accumulator["openai:gpt-4"] == pytest.approx(0.03)

    def test_disabled_returns_none(self, disabled_collector: MetricsCollector) -> None:
        """Test disabled collector returns None."""
        cost = CostData(
            model="gpt-4", provider="openai", prompt_cost=0.01, completion_cost=0.02
        )
        assert disabled_collector.record_cost(cost) is None

    def test_no_storage_still_works(self, tmp_path: Path) -> None:
        """Test record_cost works when storage is None (no-op)."""
        cfg = CollectorConfig(enabled=True, anonymize=False, session_id="s")
        c = MetricsCollector(config=cfg, storage=MagicMock())
        c.storage = None  # type: ignore[assignment]
        cost = CostData(
            model="gpt-4", provider="openai", prompt_cost=0.01, completion_cost=0.02
        )
        result = c.record_cost(cost)
        assert result is not None


class TestTrackToolExecution:
    """Tests for track_tool_execution context manager."""

    @pytest.mark.anyio()
    async def test_successful_execution(self, collector: MetricsCollector) -> None:
        """Test tracking a successful tool execution."""
        params = ToolExecutionParams(tool_name="read_file", tool_category="read")
        async with collector.track_tool_execution(params):
            pass
        # Tool count should be updated
        assert collector._tool_counts.get("read_file", 0) == 1

    @pytest.mark.anyio()
    async def test_failed_execution(self, collector: MetricsCollector) -> None:
        """Test tracking a failed tool execution records error."""
        params = ToolExecutionParams(tool_name="shell", tool_category="execute")
        with pytest.raises(RuntimeError):
            async with collector.track_tool_execution(params):
                raise RuntimeError("Tool failed")

        # Should still have been tracked
        assert collector._tool_counts.get("shell", 0) == 1

    @pytest.mark.anyio()
    async def test_execution_no_storage(self, collector: MetricsCollector) -> None:
        """Test track_tool_execution works when storage is None."""
        collector.storage = None  # type: ignore[assignment]
        params = ToolExecutionParams(tool_name="glob", tool_category="read")
        async with collector.track_tool_execution(params):
            pass
        assert collector._tool_counts.get("glob", 0) == 1

    @pytest.mark.anyio()
    async def test_disabled_skips_tracking(
        self, disabled_collector: MetricsCollector
    ) -> None:
        """Test disabled collector doesn't track tool execution."""
        params = ToolExecutionParams(tool_name="read_file")
        async with disabled_collector.track_tool_execution(params):
            pass
        assert disabled_collector._tool_counts.get("read_file", 0) == 0


class TestRecordAgentSwitch:
    """Tests for record_agent_switch."""

    def test_increments_counter(self, collector: MetricsCollector) -> None:
        """Test agent switch counter is incremented."""
        collector.record_agent_switch()
        assert collector._agent_switches == 1

    def test_multiple_switches(self, collector: MetricsCollector) -> None:
        """Test multiple agent switches."""
        collector.record_agent_switch()
        collector.record_agent_switch()
        assert collector._agent_switches == 2

    def test_disabled_no_increment(self, disabled_collector: MetricsCollector) -> None:
        """Test disabled collector doesn't increment."""
        disabled_collector.record_agent_switch()
        assert disabled_collector._agent_switches == 0


class TestRecordContextCompaction:
    """Tests for record_context_compaction."""

    def test_increments_counter(self, collector: MetricsCollector) -> None:
        """Test context compaction counter is incremented."""
        collector.record_context_compaction()
        assert collector._context_compactions == 1

    def test_disabled_no_increment(self, disabled_collector: MetricsCollector) -> None:
        """Test disabled collector doesn't increment."""
        disabled_collector.record_context_compaction()
        assert disabled_collector._context_compactions == 0


class TestRecordPerformanceEvent:
    """Tests for record_performance_event."""

    def test_returns_performance_metric(self, collector: MetricsCollector) -> None:
        """Test that record_performance_event returns a PerformanceMetric."""
        event = PerformanceEventData(event_type="llm_call", latency_ms=200.0)
        result = collector.record_performance_event(event)
        assert result is not None
        assert result.event_type == "llm_call"
        assert result.latency_ms == 200.0

    def test_disabled_returns_none(self, disabled_collector: MetricsCollector) -> None:
        """Test disabled collector returns None."""
        event = PerformanceEventData(event_type="llm_call", latency_ms=200.0)
        assert disabled_collector.record_performance_event(event) is None

    def test_no_storage(self, collector: MetricsCollector) -> None:
        """Test performance event recorded without storage."""
        collector.storage = None  # type: ignore[assignment]
        event = PerformanceEventData(event_type="test", latency_ms=10.0)
        result = collector.record_performance_event(event)
        assert result is not None


class TestGetSessionSummary:
    """Tests for get_session_summary."""

    def test_returns_summary_dict(self, collector: MetricsCollector) -> None:
        """Test that get_session_summary returns expected keys."""
        summary = collector.get_session_summary()
        assert "session_id" in summary
        assert "total_tokens" in summary
        assert "total_cost" in summary
        assert "tool_calls" in summary
        assert "agent_switches" in summary
        assert "context_compactions" in summary

    def test_summary_reflects_activity(self, collector: MetricsCollector) -> None:
        """Test summary reflects recorded activity."""
        collector.record_token_usage(
            TokenUsageData(
                model="gpt-4", provider="openai", prompt_tokens=100, completion_tokens=50
            )
        )
        collector.record_agent_switch()
        summary = collector.get_session_summary()
        assert summary["total_tokens"] == 150
        assert summary["agent_switches"] == 1


class TestProcessAgentEvent:
    """Tests for process_agent_event."""

    @pytest.mark.anyio()
    async def test_tool_call_request(self, collector: MetricsCollector) -> None:
        """Test TOOL_CALL_REQUEST event starts timing."""
        tool_call = ToolCall(id="tc-1", name="read_file", arguments={})
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=[tool_call])
        await collector.process_agent_event(event)
        assert "tc-1" in collector._tool_timers

    @pytest.mark.anyio()
    async def test_tool_call_result(self, collector: MetricsCollector) -> None:
        """Test TOOL_CALL_RESULT event records latency."""
        # Set up a timer first
        collector._tool_timers["tc-2"] = time.time()
        event = AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={"tool_call_id": "tc-2", "result": "ok"},
        )
        await collector.process_agent_event(event)
        assert "tc-2" not in collector._tool_timers

    @pytest.mark.anyio()
    async def test_tool_call_result_unknown_id(self, collector: MetricsCollector) -> None:
        """Test TOOL_CALL_RESULT with unknown tool_call_id is ignored."""
        event = AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={"tool_call_id": "unknown-id", "result": "ok"},
        )
        await collector.process_agent_event(event)  # Should not raise

    @pytest.mark.anyio()
    async def test_context_compacted_event(self, collector: MetricsCollector) -> None:
        """Test CONTEXT_COMPACTED event increments counter."""
        event = AgentEvent(type=EventType.CONTEXT_COMPACTED, data=None)
        await collector.process_agent_event(event)
        assert collector._context_compactions == 1

    @pytest.mark.anyio()
    async def test_agent_delegated_event(self, collector: MetricsCollector) -> None:
        """Test AGENT_DELEGATED event increments agent switch counter."""
        event = AgentEvent(type=EventType.AGENT_DELEGATED, data=None)
        await collector.process_agent_event(event)
        assert collector._agent_switches == 1

    @pytest.mark.anyio()
    async def test_content_event(self, collector: MetricsCollector) -> None:
        """Test CONTENT event records performance event."""
        event = AgentEvent(type=EventType.CONTENT, data="hello")
        await collector.process_agent_event(event)  # Should not raise

    @pytest.mark.anyio()
    async def test_thought_event(self, collector: MetricsCollector) -> None:
        """Test THOUGHT event records performance event."""
        event = AgentEvent(type=EventType.THOUGHT, data="thinking...")
        await collector.process_agent_event(event)  # Should not raise

    @pytest.mark.anyio()
    async def test_disabled_skips_all(self, disabled_collector: MetricsCollector) -> None:
        """Test disabled collector skips all events."""
        event = AgentEvent(type=EventType.CONTEXT_COMPACTED, data=None)
        await disabled_collector.process_agent_event(event)
        assert disabled_collector._context_compactions == 0

    @pytest.mark.anyio()
    async def test_tool_call_request_non_list_data(
        self, collector: MetricsCollector
    ) -> None:
        """Test TOOL_CALL_REQUEST with non-list data is handled gracefully."""
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=None)
        await collector.process_agent_event(event)  # Should not raise

    @pytest.mark.anyio()
    async def test_tool_call_request_non_toolcall_items(
        self, collector: MetricsCollector
    ) -> None:
        """Test TOOL_CALL_REQUEST with non-ToolCall list items is handled."""
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=["not-a-toolcall"])
        await collector.process_agent_event(event)  # Should not raise

    @pytest.mark.anyio()
    async def test_tool_call_result_no_tool_call_id(
        self, collector: MetricsCollector
    ) -> None:
        """Test TOOL_CALL_RESULT with no tool_call_id key is handled."""
        event = AgentEvent(
            type=EventType.TOOL_CALL_RESULT,
            data={"result": "ok"},
        )
        await collector.process_agent_event(event)  # Should not raise

    @pytest.mark.anyio()
    async def test_unhandled_event_type(self, collector: MetricsCollector) -> None:
        """Test that an event type not in handlers is silently ignored."""
        event = AgentEvent(type=EventType.FINISHED, data=None)
        await collector.process_agent_event(event)  # Should not raise


class TestModuleLevelHelpers:
    """Tests for module-level helper functions."""

    def test_build_token_metric(self) -> None:
        """Test _build_token_metric constructs correctly."""
        usage = TokenUsageData(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            token_limit=1000,
            agent_id="a1",
        )
        metric = _build_token_metric("sess-1", "hash123", usage)
        assert metric.total_tokens == 150
        assert metric.token_ratio == pytest.approx(0.15)
        assert metric.session_id == "sess-1"
        assert metric.user_id == "hash123"

    def test_build_cost_metric(self) -> None:
        """Test _build_cost_metric constructs correctly."""
        cost = CostData(
            model="gpt-4",
            provider="openai",
            prompt_cost=0.01,
            completion_cost=0.02,
            agent_id="a1",
        )
        metric = _build_cost_metric("sess-1", "hash123", cost)
        assert metric.total_cost == pytest.approx(0.03)
        assert metric.agent_id == "a1"

    def test_build_performance_metric(self) -> None:
        """Test _build_performance_metric constructs correctly."""
        event = PerformanceEventData(
            event_type="llm_call",
            latency_ms=100.0,
            memory_usage_mb=256.0,
            cpu_usage_percent=50.0,
            concurrent_operations=2,
            queue_depth=3,
        )
        metric = _build_performance_metric("sess-1", None, event)
        assert metric.event_type == "llm_call"
        assert metric.latency_ms == 100.0
        assert metric.queue_depth == 3

    def test_increment_sampled_counter(self, collector: MetricsCollector) -> None:
        """Test _increment_sampled_counter increments when sampling active."""
        _increment_sampled_counter(collector, "_agent_switches")
        assert collector._agent_switches == 1

    def test_increment_sampled_counter_disabled(
        self, disabled_collector: MetricsCollector
    ) -> None:
        """Test _increment_sampled_counter does not increment when disabled."""
        _increment_sampled_counter(disabled_collector, "_agent_switches")
        assert disabled_collector._agent_switches == 0

    def test_store_provider_metric_with_storage(self, tmp_storage: MetricsStorage) -> None:
        """Test _store_provider_metric stores metric and updates accumulator."""
        from collections import defaultdict

        metric = TokenMetric(model="gpt-4", provider="openai", total_tokens=100)
        accumulator: dict = defaultdict(float)
        _store_provider_metric(tmp_storage, metric, accumulator, "openai", "gpt-4", 100)
        assert accumulator["openai:gpt-4"] == 100

    def test_store_provider_metric_no_storage(self) -> None:
        """Test _store_provider_metric without storage doesn't raise."""
        from collections import defaultdict

        metric = CostMetric(model="gpt-4", provider="openai", total_cost=0.01)
        accumulator: dict = defaultdict(float)
        _store_provider_metric(None, metric, accumulator, "openai", "gpt-4", 0.01)
        assert accumulator["openai:gpt-4"] == pytest.approx(0.01)
