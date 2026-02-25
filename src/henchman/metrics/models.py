"""Metrics data models for Henchman-AI."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
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
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    user_id: Optional[str] = None  # Anonymized hash
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
    cached_tokens: Optional[int] = None
    token_limit: Optional[int] = None
    token_ratio: Optional[float] = None  # total_tokens / token_limit


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
    cost_per_token: Optional[float] = None
    estimated_cost: Optional[float] = None  # For streaming where exact tokens unknown


@dataclass
class ToolMetric(BaseMetric):
    """Tool performance metrics."""

    metric_type: MetricType = MetricType.TOOL_PERFORMANCE
    tool_name: str = ""
    tool_category: str = ""
    execution_time_ms: float = 0.0
    success: bool = True
    error_type: Optional[str] = None
    input_size: Optional[int] = None  # Approximate input size in characters
    output_size: Optional[int] = None  # Approximate output size in characters
    cache_hit: bool = False


@dataclass
class UsageMetric(BaseMetric):
    """Usage pattern metrics."""

    metric_type: MetricType = MetricType.USAGE_PATTERN
    command: str = ""
    subcommand: Optional[str] = None
    workflow_type: str = ""
    duration_ms: float = 0.0
    tool_calls_count: int = 0
    agent_switches: int = 0
    context_compactions: int = 0
    user_feedback: Optional[str] = None  # Optional explicit feedback


@dataclass
class PerformanceMetric(BaseMetric):
    """System performance metrics."""

    metric_type: MetricType = MetricType.PERFORMANCE
    event_type: str = ""
    latency_ms: float = 0.0
    memory_usage_mb: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    concurrent_operations: int = 1
    queue_depth: Optional[int] = None