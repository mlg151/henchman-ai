"""Tests for henchman.metrics.models."""

from datetime import datetime

import pytest

from henchman.metrics.models import (
    BaseMetric,
    CostData,
    CostMetric,
    MetricType,
    PerformanceEventData,
    PerformanceMetric,
    TokenMetric,
    TokenUsageData,
    ToolMetric,
    UsageMetric,
)


class TestMetricType:
    """Tests for MetricType enum."""

    def test_values(self) -> None:
        """Test MetricType has expected values."""
        assert MetricType.TOKEN_USAGE == "token_usage"
        assert MetricType.COST == "cost"
        assert MetricType.TOOL_PERFORMANCE == "tool_performance"
        assert MetricType.USAGE_PATTERN == "usage_pattern"
        assert MetricType.PERFORMANCE == "performance"

    def test_is_str_enum(self) -> None:
        """Test MetricType is a string enum."""
        assert isinstance(MetricType.TOKEN_USAGE, str)


class TestBaseMetric:
    """Tests for BaseMetric dataclass."""

    def test_defaults(self) -> None:
        """Test BaseMetric has sensible defaults."""
        m = BaseMetric()
        assert m.id  # UUID is generated
        assert isinstance(m.timestamp, datetime)
        assert m.metric_type == MetricType.PERFORMANCE
        assert m.session_id is None
        assert m.agent_id is None
        assert m.user_id is None
        assert m.metadata == {}

    def test_unique_ids(self) -> None:
        """Test each BaseMetric gets a unique ID."""
        m1 = BaseMetric()
        m2 = BaseMetric()
        assert m1.id != m2.id

    def test_custom_values(self) -> None:
        """Test BaseMetric accepts custom values."""
        m = BaseMetric(
            session_id="sess-1",
            agent_id="agent-1",
            user_id="user-abc",
            metadata={"key": "value"},
        )
        assert m.session_id == "sess-1"
        assert m.agent_id == "agent-1"
        assert m.user_id == "user-abc"
        assert m.metadata == {"key": "value"}


class TestTokenMetric:
    """Tests for TokenMetric dataclass."""

    def test_defaults(self) -> None:
        """Test TokenMetric default values."""
        m = TokenMetric()
        assert m.metric_type == MetricType.TOKEN_USAGE
        assert m.model == ""
        assert m.provider == ""
        assert m.prompt_tokens == 0
        assert m.completion_tokens == 0
        assert m.total_tokens == 0
        assert m.cached_tokens is None
        assert m.token_limit is None
        assert m.token_ratio is None

    def test_custom_values(self) -> None:
        """Test TokenMetric with custom values."""
        m = TokenMetric(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cached_tokens=20,
            token_limit=4096,
            token_ratio=0.037,
        )
        assert m.model == "gpt-4"
        assert m.cached_tokens == 20
        assert m.token_ratio == pytest.approx(0.037)


class TestCostMetric:
    """Tests for CostMetric dataclass."""

    def test_defaults(self) -> None:
        """Test CostMetric default values."""
        m = CostMetric()
        assert m.metric_type == MetricType.COST
        assert m.prompt_cost == 0.0
        assert m.completion_cost == 0.0
        assert m.total_cost == 0.0
        assert m.currency == "USD"
        assert m.cost_per_token is None
        assert m.estimated_cost is None

    def test_custom_values(self) -> None:
        """Test CostMetric with custom values."""
        m = CostMetric(
            model="gpt-4",
            provider="openai",
            prompt_cost=0.01,
            completion_cost=0.02,
            total_cost=0.03,
            currency="EUR",
            cost_per_token=0.00001,
            estimated_cost=0.05,
        )
        assert m.currency == "EUR"
        assert m.cost_per_token == pytest.approx(0.00001)
        assert m.estimated_cost == pytest.approx(0.05)


class TestToolMetric:
    """Tests for ToolMetric dataclass."""

    def test_defaults(self) -> None:
        """Test ToolMetric default values."""
        m = ToolMetric()
        assert m.metric_type == MetricType.TOOL_PERFORMANCE
        assert m.tool_name == ""
        assert m.tool_category == ""
        assert m.execution_time_ms == 0.0
        assert m.success is True
        assert m.error_type is None
        assert m.input_size is None
        assert m.output_size is None
        assert m.cache_hit is False

    def test_failure_metric(self) -> None:
        """Test ToolMetric for a failed execution."""
        m = ToolMetric(
            tool_name="shell",
            success=False,
            error_type="TimeoutError",
            execution_time_ms=5000.0,
        )
        assert m.success is False
        assert m.error_type == "TimeoutError"


class TestUsageMetric:
    """Tests for UsageMetric dataclass."""

    def test_defaults(self) -> None:
        """Test UsageMetric default values."""
        m = UsageMetric()
        assert m.metric_type == MetricType.USAGE_PATTERN
        assert m.command == ""
        assert m.subcommand is None
        assert m.workflow_type == ""
        assert m.duration_ms == 0.0
        assert m.tool_calls_count == 0
        assert m.agent_switches == 0
        assert m.context_compactions == 0
        assert m.user_feedback is None

    def test_custom_values(self) -> None:
        """Test UsageMetric with custom values."""
        m = UsageMetric(
            command="chat",
            subcommand="save",
            tool_calls_count=5,
            agent_switches=2,
            context_compactions=1,
            user_feedback="great",
        )
        assert m.command == "chat"
        assert m.subcommand == "save"
        assert m.tool_calls_count == 5


class TestPerformanceMetric:
    """Tests for PerformanceMetric dataclass."""

    def test_defaults(self) -> None:
        """Test PerformanceMetric default values."""
        m = PerformanceMetric()
        assert m.metric_type == MetricType.PERFORMANCE
        assert m.event_type == ""
        assert m.latency_ms == 0.0
        assert m.memory_usage_mb is None
        assert m.cpu_usage_percent is None
        assert m.concurrent_operations == 1
        assert m.queue_depth is None

    def test_custom_values(self) -> None:
        """Test PerformanceMetric with custom values."""
        m = PerformanceMetric(
            event_type="tool_execution",
            latency_ms=123.4,
            memory_usage_mb=256.0,
            cpu_usage_percent=45.0,
            concurrent_operations=3,
            queue_depth=5,
        )
        assert m.event_type == "tool_execution"
        assert m.memory_usage_mb == 256.0
        assert m.queue_depth == 5


class TestTokenUsageData:
    """Tests for TokenUsageData dataclass."""

    def test_required_fields(self) -> None:
        """Test TokenUsageData requires model, provider, and token counts."""
        d = TokenUsageData(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
        )
        assert d.model == "gpt-4"
        assert d.provider == "openai"
        assert d.prompt_tokens == 100
        assert d.completion_tokens == 50
        assert d.cached_tokens is None
        assert d.token_limit is None
        assert d.agent_id is None

    def test_optional_fields(self) -> None:
        """Test TokenUsageData with optional fields."""
        d = TokenUsageData(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            cached_tokens=10,
            token_limit=4096,
            agent_id="agent-1",
        )
        assert d.cached_tokens == 10
        assert d.token_limit == 4096
        assert d.agent_id == "agent-1"


class TestCostData:
    """Tests for CostData dataclass."""

    def test_required_fields(self) -> None:
        """Test CostData with required fields."""
        d = CostData(
            model="gpt-4",
            provider="openai",
            prompt_cost=0.01,
            completion_cost=0.02,
        )
        assert d.currency == "USD"
        assert d.cost_per_token is None
        assert d.estimated_cost is None
        assert d.agent_id is None

    def test_optional_fields(self) -> None:
        """Test CostData with optional fields."""
        d = CostData(
            model="gpt-4",
            provider="openai",
            prompt_cost=0.01,
            completion_cost=0.02,
            currency="EUR",
            cost_per_token=0.00001,
            estimated_cost=0.05,
            agent_id="agent-1",
        )
        assert d.currency == "EUR"
        assert d.agent_id == "agent-1"


class TestPerformanceEventData:
    """Tests for PerformanceEventData dataclass."""

    def test_required_fields(self) -> None:
        """Test PerformanceEventData with required fields."""
        d = PerformanceEventData(event_type="tool_execution", latency_ms=50.0)
        assert d.event_type == "tool_execution"
        assert d.latency_ms == 50.0
        assert d.memory_usage_mb is None
        assert d.cpu_usage_percent is None
        assert d.concurrent_operations == 1
        assert d.queue_depth is None

    def test_optional_fields(self) -> None:
        """Test PerformanceEventData with optional fields."""
        d = PerformanceEventData(
            event_type="llm_call",
            latency_ms=200.0,
            memory_usage_mb=512.0,
            cpu_usage_percent=80.0,
            concurrent_operations=4,
            queue_depth=2,
        )
        assert d.memory_usage_mb == 512.0
        assert d.concurrent_operations == 4
        assert d.queue_depth == 2
