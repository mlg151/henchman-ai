"""Tool metrics controller for the orchestrator module.

Tracks tool call success/failure, errors, and delegation counts.
"""

from __future__ import annotations

from typing import Any

from .orchestrator_components import OrchestratorComponent
from .orchestrator_types import TOOL_ERROR_MAX_LENGTH


class ToolMetricsController(OrchestratorComponent):
    """Manages tool metrics and error tracking."""

    def update_tool_metrics(
        self: ToolMetricsController,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        success: bool,
    ) -> None:
        """Update metrics for a tool call."""
        self.metrics.update_tool_metrics(tool_name, arguments, success)

    def track_tool_error(
        self: ToolMetricsController,
        tool_errors: list[str],
        tool_name: str,
        result_content: str | None,
    ) -> None:
        """Track tool errors for delegation summaries."""
        error_message = result_content or "unknown error"
        tool_errors.append(
            f"{tool_name}: {error_message[:TOOL_ERROR_MAX_LENGTH]}",
        )

    def update_delegation_metrics(
        self: ToolMetricsController,
        target: str,
    ) -> None:
        """Update metrics for a delegation."""
        self.metrics.delegation_count += 1
        if target in self.metrics.delegation_by_type:
            self.metrics.delegation_by_type[target] += 1
