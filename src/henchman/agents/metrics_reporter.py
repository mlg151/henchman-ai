"""Metrics reporting for the orchestrator."""

from __future__ import annotations

import time
from dataclasses import dataclass as _dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.agents.metrics import OrchestratorMetrics, ToolMetrics

# Display constants
MAX_TOOL_USAGE_TO_DISPLAY = 5
"""Maximum number of tool usage entries to show in metrics."""

# ---------------------------------------------------------------------------
# Module-level helpers (fix Feature Envy and Duplicate Code smells)
# ---------------------------------------------------------------------------


@_dataclass
class _RateTarget:
    """Configuration for a rate metric with a target threshold."""

    label: str
    value: float
    target: float
    above: bool
    note: str


def _build_metrics_section(title: str, items: list[str]) -> list[str]:
    """Build a markdown section with a heading followed by item lines.

    Args:
        title: Section heading (e.g. '### Efficiency Metrics').
        items: Pre-formatted bullet-point lines.

    Returns:
        List of lines: [title, item1, item2, ...].
    """
    return [title, *items]


def _format_coverage(label: str, value: float) -> str:
    """Format a coverage percentage metric line.

    Args:
        label: Human-readable label (e.g. 'Code Coverage').
        value: Coverage percentage value.

    Returns:
        Formatted markdown bullet line.
    """
    if value > 0:
        return f"- **{label}**: {value:.1f}%"
    return f"- **{label}**: Not measured"


def _format_rate_target(cfg: _RateTarget) -> str:
    """Format a rate metric with a target threshold and status indicator.

    Args:
        cfg: Rate target configuration.

    Returns:
        Formatted markdown bullet line with ✅/⚠️ status icon.
    """
    passing = cfg.value >= cfg.target if cfg.above else cfg.value <= cfg.target
    status = "✅" if passing else "⚠️"
    return f"- **{cfg.label}**: {cfg.value:.1f}% {status} ({cfg.note})"


def _format_tool_call_statistics(tools: ToolMetrics) -> list[str]:
    """Format tool call statistics lines from a ToolMetrics instance.

    Args:
        tools: ToolMetrics containing counts and category breakdown.

    Returns:
        List of formatted markdown bullet lines.
    """
    lines: list[str] = [
        f"- **Total Tool Calls**: {tools.total_tool_calls}",
        f"- **Successful Tool Calls**: {tools.successful_tool_calls}",
        f"- **Failed Tool Calls**: {tools.failed_tool_calls}",
    ]
    for category, count in tools.get_tool_call_counts_by_category().items():
        if count > 0:
            readable_name = category.value.replace("_", " ").title()
            lines.append(f"- **{readable_name} Calls**: {count}")
    return lines


# ---------------------------------------------------------------------------
# MetricsReporter
# ---------------------------------------------------------------------------


class MetricsReporter:
    """Generates formatted metrics reports from ``OrchestratorMetrics``.

    This class encapsulates all report generation logic that was previously
    spread across 18 methods in the Orchestrator class.

    Args:
        metrics: The metrics instance to report on.
    """

    def __init__(self: MetricsReporter, metrics: OrchestratorMetrics) -> None:
        self.metrics = metrics

    def get_metrics_report(self: MetricsReporter) -> str:
        """Generate a formatted performance metrics dashboard.

        Returns:
            A formatted markdown string with performance metrics.
        """
        sections = [
            self._build_efficiency_section(),
            self._build_quality_section(),
            self._build_target_section(),
        ]
        report_lines = ["## Performance Metrics Dashboard", ""]
        for section in sections:
            report_lines.extend(section)
            report_lines.append("")
        report_lines.extend(self._generate_detailed_statistics())
        return "\n".join(report_lines)

    def _build_efficiency_section(self: MetricsReporter) -> list[str]:
        """Build the efficiency metrics section."""
        efficiency_items = [
            self._format_task_completion_time(),
            self._format_files_accessed(),
            self._format_tool_usage(),
            self._format_delegation_rate(),
        ]
        return _build_metrics_section("### Efficiency Metrics", efficiency_items)

    def _build_quality_section(self: MetricsReporter) -> list[str]:
        """Build the quality metrics section."""
        quality = self.metrics.quality
        quality_items = [
            self._format_test_results(),
            _format_coverage("Code Coverage", quality.code_coverage),
            self._format_linting_status(),
            _format_coverage("Documentation Coverage", quality.documentation_coverage),
        ]
        return _build_metrics_section("### Quality Metrics", quality_items)

    def _build_target_section(self: MetricsReporter) -> list[str]:
        """Build the target performance metrics section."""
        re_reads_line = self._format_file_re_reads()
        rate_lines = [
            self._format_delegation_target(),
            self._format_error_rate_target(),
            self._format_context_window_target(),
        ]
        return _build_metrics_section(
            "### Target Performance Metrics",
            [re_reads_line, *rate_lines],
        )

    # -- Section generators (kept for composability) --------------------------

    def _generate_detailed_statistics(self: MetricsReporter) -> list[str]:
        """Generate the detailed statistics section of the report."""
        lines = ["### Detailed Statistics"]

        lines.extend(self._format_tool_call_statistics())

        lines.append(
            f"- **Thinking Pattern Usage**: {self.metrics.thinking_pattern_usage}",
        )
        lines.append(
            f"- **Thinking Quality Score**: {self.metrics.thinking_quality_score}/100",
        )

        delegation_by_type = self.metrics.delegation_by_type
        if any(count > 0 for count in delegation_by_type.values()):
            delegation_summary = ", ".join(
                [f"{k}: {v}" for k, v in delegation_by_type.items() if v > 0],
            )
            lines.append(f"- **Delegation by Type**: {delegation_summary}")

        return lines

    # -- Individual formatters ------------------------------------------------

    def _format_task_completion_time(self: MetricsReporter) -> str:
        """Format task completion time for the report."""
        start_time = self.metrics.performance.task_start_time
        end_time = self.metrics.performance.task_end_time

        if start_time and end_time:
            duration = end_time - start_time
            start_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time))
            end_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_time))
            return (
                f"- **Task Completion Time**: {start_str} to {end_str} = "
                f"{duration:.2f}s ({duration / 60:.2f}min)"
            )
        return "- **Task Completion Time**: Not completed yet"

    def _format_files_accessed(self: MetricsReporter) -> str:
        """Format files accessed information for the report."""
        files_accessed = self.metrics.performance.files_accessed
        total_files = len(files_accessed)
        total_accesses = sum(files_accessed.values())
        return f"- **Files Accessed**: {total_files} files, {total_accesses} total accesses"

    def _format_tool_usage(self: MetricsReporter) -> str:
        """Format tool usage information for the report."""
        tool_usage = self.metrics.performance.tool_usage_by_type
        if tool_usage:
            tool_summary = ", ".join(
                [
                    f"{k}: {v}"
                    for k, v in sorted(
                        tool_usage.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:MAX_TOOL_USAGE_TO_DISPLAY]
                ],
            )
            return f"- **Tool Usage**: {tool_summary}"
        return "- **Tool Usage**: No tools used yet"

    def _format_delegation_rate(self: MetricsReporter) -> str:
        """Format delegation rate for the report."""
        delegation_count = self.metrics.delegation_count
        total_tasks = self.metrics.tools.total_tool_calls + delegation_count
        delegation_rate = self.metrics.performance.delegation_rate
        return f"- **Delegation Rate**: {delegation_count}/{total_tasks} = {delegation_rate:.1f}%"

    def _format_test_results(self: MetricsReporter) -> str:
        """Format test results for the report."""
        test_results = self.metrics.quality.test_results
        if test_results["total"] > 0:
            return (
                f"- **Test Results**: {test_results['passing']}/{test_results['total']} = "
                f"{test_results['percentage']:.1f}%"
            )
        return "- **Test Results**: No tests run"

    def _format_linting_status(self: MetricsReporter) -> str:
        """Format linting status for the report."""
        linting = self.metrics.quality.linting_status
        return f"- **Linting Status**: {linting['errors']} errors, {linting['warnings']} warnings"

    def _format_code_coverage(self: MetricsReporter) -> str:
        """Format code coverage for the report."""
        coverage = self.metrics.quality.code_coverage
        return _format_coverage("Code Coverage", coverage)

    def _format_documentation_coverage(self: MetricsReporter) -> str:
        """Format documentation coverage for the report."""
        return _format_coverage(
            "Documentation Coverage",
            self.metrics.quality.documentation_coverage,
        )

    def _format_tool_call_statistics(self: MetricsReporter) -> list[str]:
        """Format tool call statistics for the report."""
        return _format_tool_call_statistics(self.metrics.tools)

    def _format_file_re_reads(self: MetricsReporter) -> str:
        """Format file re-reads with target comparison."""
        from henchman.agents.metrics import PerformanceMetrics  # noqa: PLC0415

        file_re_reads = self.metrics.performance.file_re_reads
        target = PerformanceMetrics.FILE_RE_READS_TARGET
        baseline = PerformanceMetrics.FILE_RE_READS_BASELINE
        return (
            f"- **File re-reads per task**: {file_re_reads} "
            f"(Target < {target}, 60% reduction from {baseline})"
        )

    def _format_delegation_target(self: MetricsReporter) -> str:
        """Format delegation rate with target comparison."""
        from henchman.agents.metrics import PerformanceMetrics  # noqa: PLC0415

        target = PerformanceMetrics.DELEGATION_RATE_TARGET
        rate = self.metrics.performance.delegation_rate
        return _format_rate_target(
            _RateTarget(
                label="Delegation rate",
                value=rate,
                target=target,
                above=True,
                note=f"Target > {target}%, from current 25%",
            ),
        )

    def _format_error_rate_target(self: MetricsReporter) -> str:
        """Format error rate with target comparison."""
        from henchman.agents.metrics import PerformanceMetrics  # noqa: PLC0415

        target = PerformanceMetrics.ERROR_RATE_TARGET
        return _format_rate_target(
            _RateTarget(
                label="Error rate",
                value=self.metrics.performance.error_rate,
                target=target,
                above=False,
                note=f"Target reduction of {target}%",
            ),
        )

    def _format_context_window_target(self: MetricsReporter) -> str:
        """Format context window usage with target comparison."""
        from henchman.agents.metrics import PerformanceMetrics  # noqa: PLC0415

        context_pct = self.metrics.performance.context_window_usage
        target = PerformanceMetrics.CONTEXT_WINDOW_TARGET
        status = "✅" if context_pct <= target else "⚠️"
        return (
            f"- **Context window usage**: {context_pct:.1f}% {status}"
            f" (Target < {target}%, from 65%)"
        )
