"""Tests for MetricsReporter."""

from henchman.agents.metrics_reporter import MAX_TOOL_USAGE_TO_DISPLAY, MetricsReporter
from henchman.agents.orchestrator import OrchestratorMetrics, PerformanceMetrics


def test_metrics_reporter_init():
    """Test MetricsReporter initializes with metrics reference."""
    metrics = OrchestratorMetrics()
    reporter = MetricsReporter(metrics)
    assert reporter.metrics is metrics


def test_get_metrics_report_default():
    """Test report generation with default/empty metrics."""
    metrics = OrchestratorMetrics()
    reporter = MetricsReporter(metrics)
    report = reporter.get_metrics_report()

    assert "## Performance Metrics Dashboard" in report
    assert "### Efficiency Metrics" in report
    assert "### Quality Metrics" in report
    assert "### Target Performance Metrics" in report
    assert "### Detailed Statistics" in report


def test_get_metrics_report_with_data():
    """Test report generation with populated metrics."""
    metrics = OrchestratorMetrics()
    metrics.performance.task_start_time = 1700000000.0
    metrics.performance.task_end_time = 1700000060.0
    metrics.delegation_count = 2
    metrics.tools.total_tool_calls = 10
    metrics.tools.successful_tool_calls = 9
    metrics.tools.failed_tool_calls = 1
    metrics.tools.read_file_calls = 3
    metrics.tools.write_file_calls = 2
    metrics.performance.tool_usage_by_type = {"read_file": 3, "write_file": 2}
    metrics.performance.files_accessed = {"file1.py": 2, "file2.py": 1}
    metrics.quality.test_results = {"passing": 45, "total": 50, "percentage": 90.0}
    metrics.quality.linting_status = {"errors": 2, "warnings": 5}
    metrics.thinking_pattern_usage = 1
    metrics.thinking_quality_score = 5
    metrics.calculate_final_metrics()

    reporter = MetricsReporter(metrics)
    report = reporter.get_metrics_report()

    assert "Task Completion Time" in report
    assert "60.00s" in report
    assert "Files Accessed" in report
    assert "2 files" in report
    assert "3 total accesses" in report
    assert "Tool Usage" in report
    assert "read_file: 3" in report
    assert "Delegation Rate" in report
    assert "2/12" in report
    assert "Test Results" in report
    assert "45/50" in report
    assert "90.0%" in report
    assert "Linting Status" in report
    assert "2 errors" in report
    assert "5 warnings" in report
    assert "Total Tool Calls" in report
    assert "Thinking Pattern Usage" in report


def test_format_task_completion_time_not_completed():
    """Test task completion time when task hasn't finished."""
    metrics = OrchestratorMetrics()
    reporter = MetricsReporter(metrics)
    result = reporter._format_task_completion_time()
    assert "Not completed yet" in result


def test_format_task_completion_time_completed():
    """Test task completion time when task has finished."""
    metrics = OrchestratorMetrics()
    metrics.performance.task_start_time = 1700000000.0
    metrics.performance.task_end_time = 1700000120.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_task_completion_time()
    assert "120.00s" in result
    assert "2.00min" in result


def test_format_files_accessed():
    """Test files accessed formatting."""
    metrics = OrchestratorMetrics()
    metrics.performance.files_accessed = {"a.py": 3, "b.py": 1}
    reporter = MetricsReporter(metrics)
    result = reporter._format_files_accessed()
    assert "2 files" in result
    assert "4 total accesses" in result


def test_format_tool_usage_empty():
    """Test tool usage when no tools have been used."""
    metrics = OrchestratorMetrics()
    reporter = MetricsReporter(metrics)
    result = reporter._format_tool_usage()
    assert "No tools used yet" in result


def test_format_tool_usage_with_data():
    """Test tool usage with data, respecting max display limit."""
    metrics = OrchestratorMetrics()
    metrics.performance.tool_usage_by_type = {f"tool_{i}": 10 - i for i in range(8)}
    reporter = MetricsReporter(metrics)
    result = reporter._format_tool_usage()
    assert "Tool Usage" in result
    # Should only show top MAX_TOOL_USAGE_TO_DISPLAY entries
    assert "tool_0: 10" in result


def test_format_delegation_rate():
    """Test delegation rate formatting."""
    metrics = OrchestratorMetrics()
    metrics.delegation_count = 5
    metrics.tools.total_tool_calls = 15
    metrics.performance.delegation_rate = 25.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_delegation_rate()
    assert "5/20" in result
    assert "25.0%" in result


def test_format_test_results_no_tests():
    """Test test results when no tests have been run."""
    metrics = OrchestratorMetrics()
    reporter = MetricsReporter(metrics)
    result = reporter._format_test_results()
    assert "No tests run" in result


def test_format_test_results_with_data():
    """Test test results with actual data."""
    metrics = OrchestratorMetrics()
    metrics.quality.test_results = {"passing": 90, "total": 100, "percentage": 90.0}
    reporter = MetricsReporter(metrics)
    result = reporter._format_test_results()
    assert "90/100" in result
    assert "90.0%" in result


def test_format_code_coverage_not_measured():
    """Test code coverage when not measured."""
    metrics = OrchestratorMetrics()
    reporter = MetricsReporter(metrics)
    result = reporter._format_code_coverage()
    assert "Not measured" in result


def test_format_code_coverage_with_data():
    """Test code coverage with actual data."""
    metrics = OrchestratorMetrics()
    metrics.quality.code_coverage = 85.5
    reporter = MetricsReporter(metrics)
    result = reporter._format_code_coverage()
    assert "85.5%" in result


def test_format_linting_status():
    """Test linting status formatting."""
    metrics = OrchestratorMetrics()
    metrics.quality.linting_status = {"errors": 3, "warnings": 7}
    reporter = MetricsReporter(metrics)
    result = reporter._format_linting_status()
    assert "3 errors" in result
    assert "7 warnings" in result


def test_format_documentation_coverage_not_measured():
    """Test documentation coverage when not measured."""
    metrics = OrchestratorMetrics()
    reporter = MetricsReporter(metrics)
    result = reporter._format_documentation_coverage()
    assert "Not measured" in result


def test_format_documentation_coverage_with_data():
    """Test documentation coverage with actual data."""
    metrics = OrchestratorMetrics()
    metrics.quality.documentation_coverage = 95.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_documentation_coverage()
    assert "95.0%" in result


def test_format_file_re_reads():
    """Test file re-reads target formatting."""
    metrics = OrchestratorMetrics()
    metrics.performance.file_re_reads = 2.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_file_re_reads()
    assert "2.0" in result
    assert str(PerformanceMetrics.FILE_RE_READS_TARGET) in result
    assert str(PerformanceMetrics.FILE_RE_READS_BASELINE) in result


def test_format_delegation_target_met():
    """Test delegation target when target is met."""
    metrics = OrchestratorMetrics()
    metrics.performance.delegation_rate = 50.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_delegation_target()
    assert "50.0%" in result
    assert "✅" in result


def test_format_delegation_target_not_met():
    """Test delegation target when target is not met."""
    metrics = OrchestratorMetrics()
    metrics.performance.delegation_rate = 10.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_delegation_target()
    assert "10.0%" in result
    assert "⚠️" in result


def test_format_error_rate_target_met():
    """Test error rate target when target is met."""
    metrics = OrchestratorMetrics()
    metrics.performance.error_rate = 10.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_error_rate_target()
    assert "10.0%" in result
    assert "✅" in result


def test_format_error_rate_target_not_met():
    """Test error rate target when target is not met."""
    metrics = OrchestratorMetrics()
    metrics.performance.error_rate = 99.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_error_rate_target()
    assert "99.0%" in result
    assert "⚠️" in result


def test_format_context_window_target_met():
    """Test context window target when target is met."""
    metrics = OrchestratorMetrics()
    metrics.performance.context_window_usage = 30.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_context_window_target()
    assert "30.0%" in result
    assert "✅" in result


def test_format_context_window_target_not_met():
    """Test context window target when target is not met."""
    metrics = OrchestratorMetrics()
    metrics.performance.context_window_usage = 80.0
    reporter = MetricsReporter(metrics)
    result = reporter._format_context_window_target()
    assert "80.0%" in result
    assert "⚠️" in result


def test_format_tool_call_statistics():
    """Test tool call statistics formatting."""
    metrics = OrchestratorMetrics()
    metrics.tools.total_tool_calls = 20
    metrics.tools.successful_tool_calls = 18
    metrics.tools.failed_tool_calls = 2
    metrics.tools.read_file_calls = 5
    metrics.tools.write_file_calls = 3
    reporter = MetricsReporter(metrics)
    lines = reporter._format_tool_call_statistics()

    text = "\n".join(lines)
    assert "Total Tool Calls" in text
    assert "20" in text
    assert "Successful Tool Calls" in text
    assert "18" in text
    assert "Failed Tool Calls" in text
    assert "2" in text
    assert "Read File Calls" in text
    assert "Write File Calls" in text


def test_generate_detailed_statistics_with_delegation_breakdown():
    """Test detailed statistics includes delegation breakdown when present."""
    metrics = OrchestratorMetrics()
    metrics.delegation_by_type = {"planner": 3, "explorer": 0, "engineer": 2}
    reporter = MetricsReporter(metrics)
    lines = reporter._generate_detailed_statistics()

    text = "\n".join(lines)
    assert "Delegation by Type" in text
    assert "planner: 3" in text
    assert "engineer: 2" in text
    assert "explorer" not in text  # 0 count filtered out


def test_generate_detailed_statistics_without_delegation():
    """Test detailed statistics omits delegation breakdown when all zero."""
    metrics = OrchestratorMetrics()
    reporter = MetricsReporter(metrics)
    lines = reporter._generate_detailed_statistics()

    text = "\n".join(lines)
    assert "Delegation by Type" not in text


def test_max_tool_usage_constant():
    """Test the MAX_TOOL_USAGE_TO_DISPLAY constant value."""
    assert MAX_TOOL_USAGE_TO_DISPLAY == 5
