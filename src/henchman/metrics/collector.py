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

        total_tokens = usage.prompt_tokens + usage.completion_tokens
        token_ratio = total_tokens / usage.token_limit if usage.token_limit else None

        metric = TokenMetric(
            session_id=self.session_id,
            user_id=self.user_id_hash,
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

        if self.storage:
            self.storage.store_metric(metric)

        # Update accumulators for cost calculation
        key = f"{usage.provider}:{usage.model}"
        self._token_counts[key] += total_tokens

        return metric

    def record_cost(
        self,
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

        total_cost = cost.prompt_cost + cost.completion_cost

        metric = CostMetric(
            session_id=self.session_id,
            user_id=self.user_id_hash,
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

        if self.storage:
            self.storage.store_metric(metric)

        # Update cost accumulator
        key = f"{cost.provider}:{cost.model}"
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

        metric = PerformanceMetric(
            session_id=self.session_id,
            user_id=self.user_id_hash,
            event_type=event.event_type,
            latency_ms=event.latency_ms,
            memory_usage_mb=event.memory_usage_mb,
            cpu_usage_percent=event.cpu_usage_percent,
            concurrent_operations=event.concurrent_operations,
            queue_depth=event.queue_depth,
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

    def _handle_tool_call_request(self, event: AgentEvent) -> None:
        """Start timing for each tool call in the request.

        Args:
            event: TOOL_CALL_REQUEST agent event.
        """
        if not (event.data and isinstance(event.data, list)):
            return
        for tool_call in event.data:
            if isinstance(tool_call, ToolCall):
                self._tool_timers[tool_call.id] = time.time()

    def _handle_tool_call_result(self, event: AgentEvent) -> None:
        """Record tool execution latency when a result arrives.

        Args:
            event: TOOL_CALL_RESULT agent event.
        """
        if not (event.data and "tool_call_id" in event.data):
            return
        tool_call_id = event.data["tool_call_id"]
        if tool_call_id not in self._tool_timers:
            return
        latency_ms = (time.time() - self._tool_timers[tool_call_id]) * 1000
        self.record_performance_event(
                PerformanceEventData(
                    event_type="tool_execution",
                    latency_ms=latency_ms,
                ),
            )
        del self._tool_timers[tool_call_id]

    def _handle_content_thought_event(self, event: AgentEvent) -> None:
        """Record a content or thought event as a performance observation.

        Args:
            event: CONTENT or THOUGHT agent event.
        """
        self.record_performance_event(
            event_type=event.type.name.lower(),
            latency_ms=0.0,  # Would need actual timing
        )

    async def process_agent_event(self, event: AgentEvent) -> None:  # noqa: C901
        """Process an agent event for metrics collection.

        Args:
            event: Agent event to process.
        """
        if not self.enabled:
            return

        _handlers = {
            EventType.TOOL_CALL_REQUEST: self._handle_tool_call_request,
            EventType.TOOL_CALL_RESULT: self._handle_tool_call_result,
            EventType.CONTEXT_COMPACTED: lambda _e: self.record_context_compaction(),
            EventType.AGENT_DELEGATED: lambda _e: self.record_agent_switch(),
        }
        if event.type in (EventType.CONTENT, EventType.THOUGHT):
            self._handle_content_thought_event(event)
        elif event.type in _handlers:
            _handlers[event.type](event)
