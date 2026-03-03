"""Metrics reporting for the orchestrator."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.agents.metrics import OrchestratorMetrics

# Display constants
MAX_TOOL_USAGE_TO_DISPLAY = 5
"""Maximum number of tool usage entries to show in metrics."""


class MetricsReporter:
    """Generates formatted metrics reports from ``OrchestratorMetrics``.

    This class encapsulates all report generation logic that was previously
    spread across 18 methods in the Orchestrator class.

    Args:
        metrics: The metrics instance to report on.
    """

    def __init__(self, metrics: OrchestratorMetrics) -> None:
        self.metrics = metrics

    def get_metrics_report(self) -> str:
        """Generate a formatted performance metrics dashboard.

        Returns:
            A formatted markdown string with performance metrics.
        """
        report_lines = ["## Performance Metrics Dashboard", ""]

        report_lines.extend(self._generate_efficiency_metrics())
        report_lines.append("")

        report_lines.extend(self._generate_quality_metrics())
        report_lines.append("")

        report_lines.extend(self._generate_target_metrics())
        report_lines.append("")

        report_lines.extend(self._generate_detailed_statistics())

        return "\n".join(report_lines)

    # -- Section generators ---------------------------------------------------

    def _generate_efficiency_metrics(self) -> list[str]:
        """Generate the efficiency metrics section of the report."""
        lines = ["### Efficiency Metrics"]
        lines.append(self._format_task_completion_time())
        lines.append(self._format_files_accessed())
        lines.append(self._format_tool_usage())
        lines.append(self._format_delegation_rate())
        return lines

    def _generate_quality_metrics(self) -> list[str]:
        """Generate the quality metrics section of the report."""
        lines = ["### Quality Metrics"]
        lines.append(self._format_test_results())
        lines.append(self._format_code_coverage())
        lines.append(self._format_linting_status())
        lines.append(self._format_documentation_coverage())
        return lines

    def _generate_target_metrics(self) -> list[str]:
        """Generate the target performance metrics section of the report."""
        lines = ["### Target Performance Metrics"]
        lines.append(self._format_file_re_reads())
        lines.append(self._format_delegation_target())
        lines.append(self._format_error_rate_target())
        lines.append(self._format_context_window_target())
        return lines

    def _generate_detailed_statistics(self) -> list[str]:
        """Generate the detailed statistics section of the report."""
        lines = ["### Detailed Statistics"]

        lines.extend(self._format_tool_call_statistics())

        lines.append(f"- **Thinking Pattern Usage**: {self.metrics.thinking_pattern_usage}")
        lines.append(f"- **Thinking Quality Score**: {self.metrics.thinking_quality_score}/100")

        delegation_by_type = self.metrics.delegation_by_type
        if any(count > 0 for count in delegation_by_type.values()):
            delegation_summary = ", ".join(
                [f"{k}: {v}" for k, v in delegation_by_type.items() if v > 0],
            )
            lines.append(f"- **Delegation by Type**: {delegation_summary}")

        return lines

    # -- Individual formatters ------------------------------------------------

    def _format_tool_call_statistics(self) -> list[str]:
        """Format tool call statistics for the report.

        Returns:
            List of formatted tool call statistic lines.
        """
        lines: list[str] = []
        tools = self.metrics.tools

        lines.append(f"- **Total Tool Calls**: {tools.total_tool_calls}")
        lines.append(f"- **Successful Tool Calls**: {tools.successful_tool_calls}")
        lines.append(f"- **Failed Tool Calls**: {tools.failed_tool_calls}")

        tool_counts = tools.get_tool_call_counts_by_category()
        for category, count in tool_counts.items():
            if count > 0:
                readable_name = category.value.replace("_", " ").title()
                lines.append(f"- **{readable_name} Calls**: {count}")

        return lines

    def _format_task_completion_time(self) -> str:
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

    def _format_files_accessed(self) -> str:
        """Format files accessed information for the report."""
        files_accessed = self.metrics.performance.files_accessed
        total_files = len(files_accessed)
        total_accesses = sum(files_accessed.values())
        return f"- **Files Accessed**: {total_files} files, {total_accesses} total accesses"

    def _format_tool_usage(self) -> str:
        """Format tool usage information for the report."""
        tool_usage = self.metrics.performance.tool_usage_by_type
        if tool_usage:
            tool_summary = ", ".join(
                [
                    f"{k}: {v}"
                    for k, v in sorted(
                        tool_usage.items(), key=lambda x: x[1], reverse=True,
                    )[:MAX_TOOL_USAGE_TO_DISPLAY]
                ],
            )
            return f"- **Tool Usage**: {tool_summary}"
        return "- **Tool Usage**: No tools used yet"

    def _format_delegation_rate(self) -> str:
        """Format delegation rate for the report."""
        delegation_count = self.metrics.delegation_count
        total_tasks = self.metrics.tools.total_tool_calls + delegation_count
        delegation_rate = self.metrics.performance.delegation_rate
        return f"- **Delegation Rate**: {delegation_count}/{total_tasks} = {delegation_rate:.1f}%"

    def _format_test_results(self) -> str:
        """Format test results for the report."""
        test_results = self.metrics.quality.test_results
        if test_results["total"] > 0:
            return (
                f"- **Test Results**: {test_results['passing']}/{test_results['total']} = "
                f"{test_results['percentage']:.1f}%"
            )
        return "- **Test Results**: No tests run"

    def _format_code_coverage(self) -> str:
        """Format code coverage for the report."""
        code_coverage = self.metrics.quality.code_coverage
        if code_coverage > 0:
            return f"- **Code Coverage**: {code_coverage:.1f}%"
        return "- **Code Coverage**: Not measured"

    def _format_linting_status(self) -> str:
        """Format linting status for the report."""
        linting = self.metrics.quality.linting_status
        return f"- **Linting Status**: {linting['errors']} errors, {linting['warnings']} warnings"

    def _format_documentation_coverage(self) -> str:
        """Format documentation coverage for the report."""
        doc_coverage = self.metrics.quality.documentation_coverage
        if doc_coverage > 0:
            return f"- **Documentation Coverage**: {doc_coverage:.1f}%"
        return "- **Documentation Coverage**: Not measured"

    def _format_file_re_reads(self) -> str:
        """Format file re-reads with target comparison."""
        from henchman.agents.metrics import PerformanceMetrics

        file_re_reads = self.metrics.performance.file_re_reads
        target = PerformanceMetrics.FILE_RE_READS_TARGET
        return (
            f"- **File re-reads per task**: {file_re_reads} "
            f"(Target < {target}, 60% reduction from {PerformanceMetrics.FILE_RE_READS_BASELINE})"
        )

    def _format_delegation_target(self) -> str:
        """Format delegation rate with target comparison."""
        from henchman.agents.metrics import PerformanceMetrics

        delegation_rate = self.metrics.performance.delegation_rate
        target = PerformanceMetrics.DELEGATION_RATE_TARGET
        status = "✅" if delegation_rate >= target else "⚠️"
        return (
            f"- **Delegation rate**: {delegation_rate:.1f}% {status} "
            f"(Target > {target}%, from current 25%)"
        )

    def _format_error_rate_target(self) -> str:
        """Format error rate with target comparison."""
        from henchman.agents.metrics import PerformanceMetrics

        error_rate = self.metrics.performance.error_rate
        target = PerformanceMetrics.ERROR_RATE_TARGET
        status = "✅" if error_rate <= target else "⚠️"
        return f"- **Error rate**: {error_rate:.1f}% {status} (Target reduction of {target}%)"

    def _format_context_window_target(self) -> str:
        """Format context window usage with target comparison."""
        from henchman.agents.metrics import PerformanceMetrics

        context_usage = self.metrics.performance.context_window_usage
        target = PerformanceMetrics.CONTEXT_WINDOW_TARGET
        status = "✅" if context_usage <= target else "⚠️"
        return (
            f"- **Context window usage**: {context_usage:.1f}% {status} "
            f"(Target < {target}%, from 65%)"
        )
