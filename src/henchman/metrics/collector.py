"""Metrics collector for Henchman-AI.

Collects metrics from agent events, tool execution, and system performance.
"""

import hashlib
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from henchman.core.events import AgentEvent, EventType
from henchman.metrics.models import (
    CostMetric,
    PerformanceMetric,
    TokenMetric,
    ToolMetric,
    UsageMetric,
)
from henchman.metrics.storage import MetricsStorage
from henchman.providers.base import ToolCall


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
        self,
        enabled: bool = True,
        anonymize: bool = True,
        sampling_rate: float = 1.0,
        storage: MetricsStorage | None = None,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        """Initialize the metrics collector.

        Args:
            enabled: Whether metrics collection is enabled.
            anonymize: Whether to anonymize user data.
            sampling_rate: Sampling rate for metrics (0.0 to 1.0).
            storage: Storage backend for metrics.
            session_id: Current session identifier.
            user_id: Optional user identifier for anonymization.
        """
        self.enabled = enabled
        self.anonymize = anonymize
        self.sampling_rate = sampling_rate
        self.storage = storage or MetricsStorage()
        self.session_id = session_id or self._generate_session_id()
        self.user_id_hash = self._hash_user_id(user_id) if anonymize and user_id else None

        # Runtime state
        self._current_command: str | None = None
        self._command_start_time: float | None = None
        self._tool_timers: dict[str, float] = {}
        self._token_counts: dict[str, int] = defaultdict(int)
        self._cost_accumulator: dict[str, float] = defaultdict(float)
        self._tool_counts: dict[str, int] = defaultdict(int)
        self._agent_switches: int = 0
        self._context_compactions: int = 0

    def _generate_session_id(self) -> str:
        """Generate a unique session identifier."""
        import uuid
        return str(uuid.uuid4())

    def _hash_user_id(self, user_id: str) -> str:
        """Create an anonymized hash of user ID."""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    def should_sample(self) -> bool:
        """Determine if current operation should be sampled."""
        if not self.enabled:
            return False
        if self.sampling_rate >= 1.0:
            return True
        import random
        return random.random() < self.sampling_rate

    def start_command(self, command: str, subcommand: str | None = None) -> None:
        """Start tracking a command execution.

        Args:
            command: The main command being executed.
            subcommand: Optional subcommand.
        """
        if not self.should_sample():
            return

        self._current_command = command
        self._command_start_time = time.time()
        self._tool_counts.clear()
        self._agent_switches = 0
        self._context_compactions = 0

    def end_command(self, success: bool = True) -> UsageMetric | None:
        """End tracking of current command and return usage metric.

        Args:
            success: Whether the command completed successfully.

        Returns:
            UsageMetric if sampled, None otherwise.
        """
        if not self.should_sample() or not self._command_start_time:
            return None

        duration_ms = (time.time() - self._command_start_time) * 1000
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

        # Reset state
        self._current_command = None
        self._command_start_time = None
        self._tool_counts.clear()

        return metric

    def record_token_usage(
        self,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int | None = None,
        token_limit: int | None = None,
        agent_id: str | None = None,
    ) -> TokenMetric | None:
        """Record token usage for a model call.

        Args:
            model: Model name.
            provider: Provider name.
            prompt_tokens: Number of prompt tokens.
            completion_tokens: Number of completion tokens.
            cached_tokens: Optional number of cached tokens.
            token_limit: Optional model token limit.
            agent_id: Optional agent identifier.

        Returns:
            TokenMetric if sampled, None otherwise.
        """
        if not self.should_sample():
            return None

        total_tokens = prompt_tokens + completion_tokens
        token_ratio = total_tokens / token_limit if token_limit else None

        metric = TokenMetric(
            session_id=self.session_id,
            user_id=self.user_id_hash,
            agent_id=agent_id,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cached_tokens=cached_tokens,
            token_limit=token_limit,
            token_ratio=token_ratio,
        )

        if self.storage:
            self.storage.store_metric(metric)

        # Update accumulators for cost calculation
        key = f"{provider}:{model}"
        self._token_counts[key] += total_tokens

        return metric

    def record_cost(
        self,
        model: str,
        provider: str,
        prompt_cost: float,
        completion_cost: float,
        currency: str = "USD",
        cost_per_token: float | None = None,
        estimated_cost: float | None = None,
        agent_id: str | None = None,
    ) -> CostMetric | None:
        """Record cost for a model call.

        Args:
            model: Model name.
            provider: Provider name.
            prompt_cost: Cost for prompt tokens.
            completion_cost: Cost for completion tokens.
            currency: Currency code.
            cost_per_token: Optional cost per token.
            estimated_cost: Optional estimated cost.
            agent_id: Optional agent identifier.

        Returns:
            CostMetric if sampled, None otherwise.
        """
        if not self.should_sample():
            return None

        total_cost = prompt_cost + completion_cost

        metric = CostMetric(
            session_id=self.session_id,
            user_id=self.user_id_hash,
            agent_id=agent_id,
            model=model,
            provider=provider,
            prompt_cost=prompt_cost,
            completion_cost=completion_cost,
            total_cost=total_cost,
            currency=currency,
            cost_per_token=cost_per_token,
            estimated_cost=estimated_cost,
        )

        if self.storage:
            self.storage.store_metric(metric)

        # Update cost accumulator
        key = f"{provider}:{model}"
        self._cost_accumulator[key] += total_cost

        return metric

    @asynccontextmanager
    async def track_tool_execution(
        self,
        tool_name: str,
        tool_category: str = "",
        input_size: int | None = None,
        agent_id: str | None = None,
    ) -> AsyncIterator[None]:
        """Context manager for tracking tool execution.

        Args:
            tool_name: Name of the tool being executed.
            tool_category: Category of the tool.
            input_size: Approximate input size in characters.
            agent_id: Optional agent identifier.

        Yields:
            None
        """
        start_time = time.time()
        success = True
        error_type = None
        cache_hit = False
        output_size = None

        try:
            yield
        except Exception as e:
            success = False
            error_type = type(e).__name__
            raise
        finally:
            if self.should_sample():
                execution_time_ms = (time.time() - start_time) * 1000

                metric = ToolMetric(
                    session_id=self.session_id,
                    user_id=self.user_id_hash,
                    agent_id=agent_id,
                    tool_name=tool_name,
                    tool_category=tool_category,
                    execution_time_ms=execution_time_ms,
                    success=success,
                    error_type=error_type,
                    input_size=input_size,
                    output_size=output_size,
                    cache_hit=cache_hit,
                )

                if self.storage:
                    self.storage.store_metric(metric)

                # Update tool counts
                self._tool_counts[tool_name] = self._tool_counts.get(tool_name, 0) + 1

    def record_agent_switch(self) -> None:
        """Record an agent switch event."""
        if self.should_sample():
            self._agent_switches += 1

    def record_context_compaction(self) -> None:
        """Record a context compaction event."""
        if self.should_sample():
            self._context_compactions += 1

    def record_performance_event(
        self,
        event_type: str,
        latency_ms: float,
        memory_usage_mb: float | None = None,
        cpu_usage_percent: float | None = None,
        concurrent_operations: int = 1,
        queue_depth: int | None = None,
    ) -> PerformanceMetric | None:
        """Record a system performance event.

        Args:
            event_type: Type of performance event.
            latency_ms: Latency in milliseconds.
            memory_usage_mb: Optional memory usage in MB.
            cpu_usage_percent: Optional CPU usage percentage.
            concurrent_operations: Number of concurrent operations.
            queue_depth: Optional queue depth.

        Returns:
            PerformanceMetric if sampled, None otherwise.
        """
        if not self.should_sample():
            return None

        metric = PerformanceMetric(
            session_id=self.session_id,
            user_id=self.user_id_hash,
            event_type=event_type,
            latency_ms=latency_ms,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            concurrent_operations=concurrent_operations,
            queue_depth=queue_depth,
        )

        if self.storage:
            self.storage.store_metric(metric)

        return metric

    def get_session_summary(self) -> dict[str, Any]:
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

    async def process_agent_event(self, event: AgentEvent) -> None:
        """Process an agent event for metrics collection.

        Args:
            event: Agent event to process.
        """
        if not self.enabled:
            return

        # Record performance for various event types
        if event.type in [EventType.CONTENT, EventType.THOUGHT]:
            self.record_performance_event(
                event_type=event.type.name.lower(),
                latency_ms=0.0,  # Would need actual timing
            )
        elif event.type == EventType.TOOL_CALL_REQUEST:
            if event.data and isinstance(event.data, list):
                for tool_call in event.data:
                    if isinstance(tool_call, ToolCall):
                        self._tool_timers[tool_call.id] = time.time()
        elif event.type == EventType.TOOL_CALL_RESULT:
            if event.data and "tool_call_id" in event.data:
                tool_call_id = event.data["tool_call_id"]
                if tool_call_id in self._tool_timers:
                    latency_ms = (time.time() - self._tool_timers[tool_call_id]) * 1000
                    self.record_performance_event(
                        event_type="tool_execution",
                        latency_ms=latency_ms,
                    )
                    del self._tool_timers[tool_call_id]
        elif event.type == EventType.CONTEXT_COMPACTED:
            self.record_context_compaction()
        elif event.type == EventType.AGENT_DELEGATED:
            self.record_agent_switch()
