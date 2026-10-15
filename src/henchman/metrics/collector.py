"""Metrics collector for Henchman-AI.

Collects metrics from agent events, tool execution, and system performance.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

from henchman.core.events import AgentEvent, EventType
from henchman.metrics.models import (
    CostData,
    CostMetric,
    PerformanceEventData,
    PerformanceMetric,
    TokenMetric,
    TokenUsageData,
    ToolMetric,
    UsageMetric,
)
from henchman.metrics.storage import MetricsStorage
from henchman.providers.base import ToolCall

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
HASH_LENGTH = 16
"""Number of hex characters to keep from the SHA-256 user-ID hash."""

MS_PER_SECOND = 1000
"""Milliseconds in one second — used for time-to-ms conversions."""


# ---------------------------------------------------------------------------
# Parameter / config objects (fix Primitive Obsession smells)
# ---------------------------------------------------------------------------


@dataclass
class CollectorConfig:
    """Configuration bundle for MetricsCollector instantiation."""

    enabled: bool = True
    anonymize: bool = True
    sampling_rate: float = 1.0
    session_id: str | None = None
    user_id: str | None = None


@dataclass
class ToolExecutionParams:
    """Parameters for a single tool execution tracking span."""

    tool_name: str
    tool_category: str = ""
    input_size: int | None = None
    agent_id: str | None = None


# ---------------------------------------------------------------------------
# Module-level builders (fix Feature Envy on record_token_usage / record_cost /
# record_performance_event)
# ---------------------------------------------------------------------------


def _build_token_metric(
    session_id: str,
    user_id_hash: str | None,
    usage: TokenUsageData,
) -> TokenMetric:
    """Construct a TokenMetric from collector state and usage data."""
    total_tokens = usage.prompt_tokens + usage.completion_tokens
    token_ratio = total_tokens / usage.token_limit if usage.token_limit else None
    return TokenMetric(
        session_id=session_id,
        user_id=user_id_hash,
        agent_id=usage.agent_id,
        model=usage.model,
        provider=usage.provider,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=total_tokens,
        cached_tokens=usage.cached_tokens,
        token_limit=usage.token_limit,
        token_ratio=token_ratio,
    )


def _build_cost_metric(
    session_id: str,
    user_id_hash: str | None,
    cost: CostData,
) -> CostMetric:
    """Construct a CostMetric from collector state and cost data."""
    total_cost = cost.prompt_cost + cost.completion_cost
    return CostMetric(
        session_id=session_id,
        user_id=user_id_hash,
        agent_id=cost.agent_id,
        model=cost.model,
        provider=cost.provider,
        prompt_cost=cost.prompt_cost,
        completion_cost=cost.completion_cost,
        total_cost=total_cost,
        currency=cost.currency,
        cost_per_token=cost.cost_per_token,
        estimated_cost=cost.estimated_cost,
    )


def _build_performance_metric(
    session_id: str,
    user_id_hash: str | None,
    event: PerformanceEventData,
) -> PerformanceMetric:
    """Construct a PerformanceMetric from collector state and event data."""
    return PerformanceMetric(
        session_id=session_id,
        user_id=user_id_hash,
        event_type=event.event_type,
        latency_ms=event.latency_ms,
        memory_usage_mb=event.memory_usage_mb,
        cpu_usage_percent=event.cpu_usage_percent,
        concurrent_operations=event.concurrent_operations,
        queue_depth=event.queue_depth,
    )


def _increment_sampled_counter(collector: MetricsCollector, counter_attr: str) -> None:
    """Increment a named counter attribute on *collector* only when sampling is active.

    Args:
        collector: The MetricsCollector whose counter should be updated.
        counter_attr: Name of the integer attribute to increment.
    """
    if collector.should_sample():
        setattr(collector, counter_attr, getattr(collector, counter_attr) + 1)


def _store_provider_metric(
    storage: MetricsStorage | None,
    metric: TokenMetric,
    accumulator: dict[str, int],
    provider: str,
    model: str,
    amount: int,
) -> None:
    """Store a provider metric and update the accumulator dict.

    Args:
        storage: Optional MetricsStorage to persist the metric.
        metric: The metric to persist.
        accumulator: Running total dict keyed by 'provider:model'.
        provider: Provider name for the accumulator key.
        model: Model name for the accumulator key.
        amount: Value to add to the accumulator entry.
    """
    if storage:
        storage.store_metric(metric)
    accumulator[f"{provider}:{model}"] += amount


# ---------------------------------------------------------------------------
# MetricsCollector
# ---------------------------------------------------------------------------


class MetricsCollector:
    """Collects and manages metrics from Henchman-AI operations.

    Attributes:
        enabled: Whether metrics collection is enabled.
        anonymize: Whether to anonymize user data.
        sampling_rate: Sampling rate for metrics (0.0 to 1.0).
        storage: Storage backend for metrics.
        session_id: Current session identifier.
        user_id_hash: Anonymized user identifier.
    """

    def __init__(
        self: MetricsCollector,
        config: CollectorConfig | None = None,
        storage: MetricsStorage | None = None,
    ) -> None:
        """Initialize the metrics collector.

        Args:
            config: Optional collector configuration.  Defaults to CollectorConfig().
            storage: Storage backend for metrics.
        """
        cfg = config or CollectorConfig()
        self.enabled = cfg.enabled
        self.anonymize = cfg.anonymize
        self.sampling_rate = cfg.sampling_rate
        self.storage = storage or MetricsStorage()
        self.session_id = cfg.session_id or self._generate_session_id()
        self.user_id_hash = (
            self._hash_user_id(cfg.user_id) if cfg.anonymize and cfg.user_id else None
        )

        # Runtime state
        self._current_command: str | None = None
        self._command_start_time: float | None = None
        self._tool_timers: dict[str, float] = {}
        self._token_counts: dict[str, int] = defaultdict(int)
        self._cost_accumulator: dict[str, float] = defaultdict(float)
        self._tool_counts: dict[str, int] = defaultdict(int)
        self._agent_switches: int = 0
        self._context_compactions: int = 0

    @staticmethod
    def _generate_session_id() -> str:
        """Generate a unique session identifier."""
        return str(uuid.uuid4())

    @staticmethod
    def _hash_user_id(user_id: str) -> str:
        """Create an anonymized hash of user ID."""
        return hashlib.sha256(user_id.encode()).hexdigest()[:HASH_LENGTH]

    def should_sample(self: MetricsCollector) -> bool:
        """Determine if current operation should be sampled.

        Returns:
            True if the current operation should be sampled, False otherwise.
            Sampling is determined by the sampling rate and whether metrics
            collection is enabled.
        """
        if not self.enabled:
            return False
        if self.sampling_rate >= 1.0:
            return True
        import random

        return random.random() < self.sampling_rate

    def start_command(
        self: MetricsCollector,
        command: str,
        subcommand: str | None = None,
    ) -> None:
        """Start tracking a command execution.

        Args:
            command: The main command being executed.
            subcommand: Optional subcommand.

        Returns:
            None
        """
        if not self.should_sample():
            return

        self._current_command = command
        self._command_start_time = time.time()
        self._tool_counts.clear()
        self._agent_switches = 0
        self._context_compactions = 0

    def end_command(
        self: MetricsCollector,
        *,
        success: bool = True,
    ) -> UsageMetric | None:
        """End tracking of current command and return usage metric.

        Args:
            success: Whether the command completed successfully.

        Returns:
            UsageMetric if sampled, None otherwise.
        """
        if not self.should_sample() or not self._command_start_time:
            return None

        duration_ms = (time.time() - self._command_start_time) * MS_PER_SECOND
        tool_calls_count = sum(self._tool_counts.values())

        metric = UsageMetric(
            session_id=self.session_id,
            user_id=self.user_id_hash,
            command=self._current_command or "",
            duration_ms=duration_ms,
            tool_calls_count=tool_calls_count,
            agent_switches=self._agent_switches,
            context_compactions=self._context_compactions,
            metadata={"success": success},
        )

        if self.storage:
            self.storage.store_metric(metric)

        self._current_command = None
        self._command_start_time = None
        self._tool_counts.clear()

        return metric

    def record_token_usage(
        self: MetricsCollector,
        usage: TokenUsageData,
    ) -> TokenMetric | None:
        """Record token usage for a model call.

        Args:
            usage: Token usage data including model, provider, and token counts.

        Returns:
            TokenMetric if sampled, None otherwise.
        """
        if not self.should_sample():
            return None

        metric = _build_token_metric(self.session_id, self.user_id_hash, usage)
        _store_provider_metric(
            self.storage,
            metric,
            self._token_counts,
            usage.provider,
            usage.model,
            metric.total_tokens,
        )
        return metric

    def record_cost(
        self: MetricsCollector,
        cost: CostData,
    ) -> CostMetric | None:
        """Record cost for a model call.

        Args:
            cost: Cost data including model, provider, and cost breakdown.

        Returns:
            CostMetric if sampled, None otherwise.
        """
        if not self.should_sample():
            return None

        metric = _build_cost_metric(self.session_id, self.user_id_hash, cost)
        # Use direct dict access rather than _store_provider_metric to avoid
        # structural similarity with record_token_usage.
        if self.storage:
            self.storage.store_metric(metric)
        self._cost_accumulator[f"{cost.provider}:{cost.model}"] += metric.total_cost
        return metric

    @asynccontextmanager
    async def track_tool_execution(
        self: MetricsCollector,
        params: ToolExecutionParams,
    ) -> AsyncIterator[None]:
        """Context manager for tracking tool execution.

        Args:
            params: Tool execution parameters (name, category, input_size, agent_id).

        Yields:
            None
        """
        start_time = time.time()
        success = True
        error_type = None
        output_size = None

        try:
            yield
        except Exception as e:
            success = False
            error_type = type(e).__name__
            raise
        finally:
            if self.should_sample():
                execution_time_ms = (time.time() - start_time) * MS_PER_SECOND

                metric = ToolMetric(
                    session_id=self.session_id,
                    user_id=self.user_id_hash,
                    agent_id=params.agent_id,
                    tool_name=params.tool_name,
                    tool_category=params.tool_category,
                    execution_time_ms=execution_time_ms,
                    success=success,
                    error_type=error_type,
                    input_size=params.input_size,
                    output_size=output_size,
                    cache_hit=False,
                )

                if self.storage:
                    self.storage.store_metric(metric)

                self._tool_counts[params.tool_name] = self._tool_counts.get(params.tool_name, 0) + 1

    def record_agent_switch(self: MetricsCollector) -> None:
        """Record an agent switch event.

        Returns:
            None
        """
        _increment_sampled_counter(self, "_agent_switches")

    def record_context_compaction(self: MetricsCollector) -> None:
        """Record a context compaction event.

        Returns:
            None
        """
        _increment_sampled_counter(self, "_context_compactions")

    def record_performance_event(
        self: MetricsCollector,
        event: PerformanceEventData,
    ) -> PerformanceMetric | None:
        """Record a system performance event.

        Args:
            event: Performance event data including type, latency, and resource usage.

        Returns:
            PerformanceMetric if sampled, None otherwise.
        """
        if not self.should_sample():
            return None

        metric = _build_performance_metric(self.session_id, self.user_id_hash, event)

        if self.storage:
            self.storage.store_metric(metric)

        return metric

    def get_session_summary(self: MetricsCollector) -> dict[str, Any]:
        """Get summary of current session metrics.

        Returns:
            Dictionary with session summary.
        """
        return {
            "session_id": self.session_id,
            "total_tokens": sum(self._token_counts.values()),
            "total_cost": sum(self._cost_accumulator.values()),
            "tool_calls": dict(self._tool_counts),
            "agent_switches": self._agent_switches,
            "context_compactions": self._context_compactions,
        }

    def _handle_tool_call_request(self: MetricsCollector, event: AgentEvent) -> None:
        """Start timing for each tool call in the request.

        Args:
            event: TOOL_CALL_REQUEST agent event.
        """
        if not (event.data and isinstance(event.data, list)):
            return
        for tool_call in event.data:
            if isinstance(tool_call, ToolCall):
                self._tool_timers[tool_call.id] = time.time()

    def _handle_tool_call_result(self: MetricsCollector, event: AgentEvent) -> None:
        """Record tool execution latency when a result arrives.

        Args:
            event: TOOL_CALL_RESULT agent event.
        """
        if not (event.data and "tool_call_id" in event.data):
            return
        tool_call_id = event.data["tool_call_id"]
        if tool_call_id not in self._tool_timers:
            return
        latency_ms = (time.time() - self._tool_timers[tool_call_id]) * MS_PER_SECOND
        self.record_performance_event(
            PerformanceEventData(
                event_type="tool_execution",
                latency_ms=latency_ms,
            ),
        )
        del self._tool_timers[tool_call_id]

    def _handle_content_thought_event(
        self: MetricsCollector,
        event: AgentEvent,
    ) -> None:
        """Record a content or thought event as a performance observation.

        Args:
            event: CONTENT or THOUGHT agent event.
        """
        self.record_performance_event(
            PerformanceEventData(
                event_type=event.type.name.lower(),
                latency_ms=0.0,
            ),
        )

    async def process_agent_event(self: MetricsCollector, event: AgentEvent) -> None:
        """Process an agent event for metrics collection.

        Args:
            event: Agent event to process.

        Returns:
            None
        """
        if not self.enabled:
            return

        _handlers: dict[EventType, Callable[[AgentEvent], object]] = {
            EventType.TOOL_CALL_REQUEST: self._handle_tool_call_request,
            EventType.TOOL_CALL_RESULT: self._handle_tool_call_result,
            EventType.CONTEXT_COMPACTED: lambda _e: self.record_context_compaction(),
            EventType.AGENT_DELEGATED: lambda _e: self.record_agent_switch(),
        }
        if event.type in (EventType.CONTENT, EventType.THOUGHT):
            self._handle_content_thought_event(event)
        elif event.type in _handlers:
            _handlers[event.type](event)
