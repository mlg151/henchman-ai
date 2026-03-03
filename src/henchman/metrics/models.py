"""Metrics data models for Henchman-AI."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class MetricType(str, Enum):
    """Types of metrics that can be collected."""

    TOKEN_USAGE = "token_usage"
    COST = "cost"
    TOOL_PERFORMANCE = "tool_performance"
    USAGE_PATTERN = "usage_pattern"
    PERFORMANCE = "performance"


@dataclass
class BaseMetric:
    """Base class for all metrics."""

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    metric_type: MetricType = MetricType.PERFORMANCE
    session_id: str | None = None
    agent_id: str | None = None
    user_id: str | None = None  # Anonymized hash
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenMetric(BaseMetric):
    """Token usage metrics."""

    metric_type: MetricType = MetricType.TOKEN_USAGE
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int | None = None
    token_limit: int | None = None
    token_ratio: float | None = None  # total_tokens / token_limit


@dataclass
class CostMetric(BaseMetric):
    """Cost calculation metrics."""

    metric_type: MetricType = MetricType.COST
    model: str = ""
    provider: str = ""
    prompt_cost: float = 0.0
    completion_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"
    cost_per_token: float | None = None
    estimated_cost: float | None = None  # For streaming where exact tokens unknown


@dataclass
class ToolMetric(BaseMetric):
    """Tool performance metrics."""

    metric_type: MetricType = MetricType.TOOL_PERFORMANCE
    tool_name: str = ""
    tool_category: str = ""
    execution_time_ms: float = 0.0
    success: bool = True
    error_type: str | None = None
    input_size: int | None = None  # Approximate input size in characters
    output_size: int | None = None  # Approximate output size in characters
    cache_hit: bool = False


@dataclass
class UsageMetric(BaseMetric):
    """Usage pattern metrics."""

    metric_type: MetricType = MetricType.USAGE_PATTERN
    command: str = ""
    subcommand: str | None = None
    workflow_type: str = ""
    duration_ms: float = 0.0
    tool_calls_count: int = 0
    agent_switches: int = 0
    context_compactions: int = 0
    user_feedback: str | None = None  # Optional explicit feedback


@dataclass
class PerformanceMetric(BaseMetric):
    """System performance metrics."""

    metric_type: MetricType = MetricType.PERFORMANCE
    event_type: str = ""
    latency_ms: float = 0.0
    memory_usage_mb: float | None = None
    cpu_usage_percent: float | None = None
    concurrent_operations: int = 1
    queue_depth: int | None = None


@dataclass
class TokenUsageData:
    """Input parameters for recording token usage.

    Groups related token usage primitives to avoid Primitive Obsession.
    """

    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int | None = None
    token_limit: int | None = None
    agent_id: str | None = None


@dataclass
class CostData:
    """Input parameters for recording cost.

    Groups related cost primitives to avoid Primitive Obsession.
    """

    model: str
    provider: str
    prompt_cost: float
    completion_cost: float
    currency: str = "USD"
    cost_per_token: float | None = None
    estimated_cost: float | None = None
    agent_id: str | None = None


@dataclass
class PerformanceEventData:
    """Input parameters for recording a performance event.

    Groups related performance primitives to avoid Primitive Obsession.
    """

    event_type: str
    latency_ms: float
    memory_usage_mb: float | None = None
    cpu_usage_percent: float | None = None
    concurrent_operations: int = 1
    queue_depth: int | None = None
