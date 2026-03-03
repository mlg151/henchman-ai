"""Metrics classes for the orchestrator agent system."""

from __future__ import annotations

from enum import Enum
from typing import Any

# Shared arithmetic constants
PERCENTAGE_MULTIPLIER = 100.0
"""Multiplier to convert a ratio to a percentage."""

SECONDS_PER_MINUTE = 60.0
"""Number of seconds in a minute."""


class ToolCategory(Enum):
    """Categories for tool classification in metrics tracking."""

    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    EDIT_FILE = "edit_file"
    SHELL = "shell"
    GIT_OPS = "git_ops"
    OTHER = "other"


# Mapping from tool names to their categories
_TOOL_CATEGORY_MAP: dict[str, ToolCategory] = {
    "read_file": ToolCategory.READ_FILE,
    "write_file": ToolCategory.WRITE_FILE,
    "edit_file": ToolCategory.EDIT_FILE,
    "shell": ToolCategory.SHELL,
    "git_ops": ToolCategory.GIT_OPS,
}


def _categorize_tool(tool_name: str) -> ToolCategory:
    """Categorize a tool by its name.

    Args:
        tool_name: Name of the tool to categorize.

    Returns:
        The tool's category, or ToolCategory.OTHER if not found.
    """
    return _TOOL_CATEGORY_MAP.get(tool_name, ToolCategory.OTHER)


class PerformanceMetrics:
    """Encapsulates performance-related metrics."""

    # Target constants
    DELEGATION_RATE_TARGET = 40.0  # Target > 40% (from current 25%)
    ERROR_RATE_TARGET = 50.0  # Target reduction of 50%
    CONTEXT_WINDOW_TARGET = 40.0  # Target < 40% (from 65%)
    FILE_RE_READS_TARGET = 1.3  # Target < 1.3 (60% reduction from 3.2)
    FILE_RE_READS_BASELINE = 3.2  # Baseline from which we're reducing by 60%

    def __init__(self) -> None:
        """Initialize performance metrics with default values."""
        self.task_start_time: float = 0.0
        self.task_end_time: float = 0.0
        self.task_duration_minutes: float = 0.0
        self.files_accessed: dict[str, int] = {}
        self.tool_usage_by_type: dict[str, int] = {}
        self.delegation_rate: float = 0.0
        self.file_re_reads: int = 0
        self.error_rate: float = 0.0
        self.context_window_usage: float = 0.0

    def reset(self) -> None:
        """Reset performance metrics for a new run."""
        self.task_start_time = 0.0
        self.task_end_time = 0.0
        self.task_duration_minutes = 0.0
        self.files_accessed.clear()
        self.tool_usage_by_type.clear()
        self.delegation_rate = 0.0
        self.file_re_reads = 0
        self.error_rate = 0.0
        self.context_window_usage = 0.0

    def calculate_file_re_reads(self) -> None:
        """Calculate file re-reads from access patterns."""
        if self.files_accessed:
            total_accesses = sum(self.files_accessed.values())
            unique_files = len(self.files_accessed)
            if unique_files > 0:
                self.file_re_reads = total_accesses - unique_files

    def track_file_access(self, file_path: str) -> None:
        """Track a file access for re-read analysis.

        Args:
            file_path: The path of the file that was accessed.
        """
        self.files_accessed[file_path] = self.files_accessed.get(file_path, 0) + 1

    def track_tool_usage(self, tool_name: str) -> None:
        """Track tool usage by type.

        Args:
            tool_name: The name of the tool that was used.
        """
        self.tool_usage_by_type[tool_name] = self.tool_usage_by_type.get(tool_name, 0) + 1


class QualityMetrics:
    """Encapsulates quality-related metrics."""

    def __init__(self) -> None:
        """Initialize quality metrics with default values."""
        self.test_results: dict[str, Any] = {"passing": 0, "total": 0, "percentage": 0.0}
        self.code_coverage: float = 0.0
        self.linting_status: dict[str, int] = {"errors": 0, "warnings": 0}
        self.documentation_coverage: float = 0.0

    def reset(self) -> None:
        """Reset quality metrics for a new run."""
        self.test_results = {"passing": 0, "total": 0, "percentage": 0.0}
        self.code_coverage = 0.0
        self.linting_status = {"errors": 0, "warnings": 0}
        self.documentation_coverage = 0.0

    def calculate_test_percentage(self) -> None:
        """Calculate test results percentage."""
        if self.test_results["total"] > 0:
            self.test_results["percentage"] = (
                self.test_results["passing"] / self.test_results["total"] * PERCENTAGE_MULTIPLIER
            )


class ToolMetrics:
    """Encapsulates tool usage metrics."""

    def __init__(self) -> None:
        """Initialize tool metrics with default values."""
        self.total_tool_calls: int = 0
        self.successful_tool_calls: int = 0
        self.failed_tool_calls: int = 0
        self.read_file_calls: int = 0
        self.write_file_calls: int = 0
        self.edit_file_calls: int = 0
        self.shell_calls: int = 0
        self.git_ops_calls: int = 0
        self.other_tool_calls: int = 0

    def reset(self) -> None:
        """Reset tool metrics for a new run."""
        self.total_tool_calls = 0
        self.successful_tool_calls = 0
        self.failed_tool_calls = 0
        self.read_file_calls = 0
        self.write_file_calls = 0
        self.edit_file_calls = 0
        self.shell_calls = 0
        self.git_ops_calls = 0
        self.other_tool_calls = 0

    def track_tool_call(self, tool_name: str, *, success: bool) -> None:
        """Track a tool call with its category.

        Args:
            tool_name: The name of the tool that was called.
            success: Whether the tool call was successful.
        """
        self.total_tool_calls += 1

        if success:
            self.successful_tool_calls += 1
        else:
            self.failed_tool_calls += 1

        # Increment the appropriate per-category counter
        category = _categorize_tool(tool_name)
        _category_counter: dict[ToolCategory, str] = {
            ToolCategory.READ_FILE: "read_file_calls",
            ToolCategory.WRITE_FILE: "write_file_calls",
            ToolCategory.EDIT_FILE: "edit_file_calls",
            ToolCategory.SHELL: "shell_calls",
            ToolCategory.GIT_OPS: "git_ops_calls",
        }
        counter_attr = _category_counter.get(category, "other_tool_calls")
        setattr(self, counter_attr, getattr(self, counter_attr) + 1)

    def calculate_error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self.total_tool_calls > 0:
            return (self.failed_tool_calls / self.total_tool_calls) * PERCENTAGE_MULTIPLIER
        return 0.0

    def get_tool_call_counts_by_category(self) -> dict[ToolCategory, int]:
        """Get tool call counts organized by category.

        Returns:
            A dictionary mapping tool categories to their call counts.
        """
        return {
            ToolCategory.READ_FILE: self.read_file_calls,
            ToolCategory.WRITE_FILE: self.write_file_calls,
            ToolCategory.EDIT_FILE: self.edit_file_calls,
            ToolCategory.SHELL: self.shell_calls,
            ToolCategory.GIT_OPS: self.git_ops_calls,
            ToolCategory.OTHER: self.other_tool_calls,
        }


class OrchestratorMetrics:
    """Encapsulates metrics collection and calculation for the orchestrator.

    This class addresses the Primitive Obsession code smell by providing
    a proper object-oriented interface for metrics management instead of
    using a complex nested dictionary directly.
    """

    def __init__(self) -> None:
        """Initialize all metrics with default values."""
        # Core metrics
        self.thinking_pattern_usage: int = 0
        self.delegation_count: int = 0
        self.delegation_by_type: dict[str, int] = {"planner": 0, "explorer": 0, "engineer": 0}
        self.thinking_quality_score: int = 0

        # Component metrics
        self.performance = PerformanceMetrics()
        self.quality = QualityMetrics()
        self.tools = ToolMetrics()

    def reset_for_run(self) -> None:
        """Reset all metrics for a new run while preserving structure."""
        self.thinking_pattern_usage = 0
        self.delegation_count = 0
        self.delegation_by_type = {"planner": 0, "explorer": 0, "engineer": 0}
        self.thinking_quality_score = 0

        self.performance.reset()
        self.quality.reset()
        self.tools.reset()

    def calculate_final_metrics(self) -> None:
        """Calculate derived metrics after task completion."""
        # Calculate task duration
        if self.performance.task_start_time and self.performance.task_end_time:
            duration = self.performance.task_end_time - self.performance.task_start_time
            # Store duration in minutes for readability
            self.performance.task_duration_minutes = duration / SECONDS_PER_MINUTE

        # Calculate delegation rate
        total_tasks = self.tools.total_tool_calls + self.delegation_count
        if total_tasks > 0:
            self.performance.delegation_rate = self.delegation_count / total_tasks * PERCENTAGE_MULTIPLIER  # noqa: E501

        # Calculate error rate
        self.performance.error_rate = self.tools.calculate_error_rate()

        # Calculate test results percentage
        self.quality.calculate_test_percentage()

        # Calculate file re-reads
        self.performance.calculate_file_re_reads()

    def update_tool_metrics(self, tool_name: str, arguments: dict[str, Any], *, success: bool) -> None:  # noqa: E501
        """Update metrics for a tool call.

        Args:
            tool_name: Name of the tool called.
            arguments: Arguments passed to the tool.
            success: Whether the tool call succeeded.
        """
        # Update tool metrics
        self.tools.track_tool_call(tool_name, success=success)

        # Update performance metrics
        self.performance.track_tool_usage(tool_name)

        # Track file access for re-read analysis
        if tool_name == "read_file" and "path" in arguments:
            file_path = str(arguments["path"])
            self.performance.track_file_access(file_path)

    def __getitem__(self, key: str) -> Any:
        """Support dictionary-like access for backward compatibility.

        Args:
            key: The metric name to retrieve.

        Returns:
            The metric value.

        Raises:
            KeyError: If the key is not a valid metric.
        """
        # Check main class attributes
        if hasattr(self, key):
            return getattr(self, key)

        # Check component classes
        component_mapping = {
            # Performance metrics
            "task_start_time": self.performance.task_start_time,
            "task_end_time": self.performance.task_end_time,
            "task_duration_minutes": self.performance.task_duration_minutes,
            "files_accessed": self.performance.files_accessed,
            "tool_usage_by_type": self.performance.tool_usage_by_type,
            "delegation_rate": self.performance.delegation_rate,
            "file_re_reads": self.performance.file_re_reads,
            "error_rate": self.performance.error_rate,
            "context_window_usage": self.performance.context_window_usage,

            # Quality metrics
            "test_results": self.quality.test_results,
            "code_coverage": self.quality.code_coverage,
            "linting_status": self.quality.linting_status,
            "documentation_coverage": self.quality.documentation_coverage,

            # Tool metrics
            "total_tool_calls": self.tools.total_tool_calls,
            "successful_tool_calls": self.tools.successful_tool_calls,
            "failed_tool_calls": self.tools.failed_tool_calls,
            "read_file_calls": self.tools.read_file_calls,
            "write_file_calls": self.tools.write_file_calls,
            "edit_file_calls": self.tools.edit_file_calls,
            "shell_calls": self.tools.shell_calls,
            "git_ops_calls": self.tools.git_ops_calls,
            "other_tool_calls": self.tools.other_tool_calls,
        }

        if key in component_mapping:
            return component_mapping[key]

        msg = f"'{key}' is not a valid metric"
        raise KeyError(msg)

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for backward compatibility.

        Args:
            key: The metric name to check.

        Returns:
            True if the metric exists, False otherwise.
        """
        # Check main class attributes
        if hasattr(self, key):
            return True

        # Check component class mappings
        component_keys = {
            "task_start_time", "task_end_time", "task_duration_minutes",
            "files_accessed", "tool_usage_by_type", "delegation_rate",
            "file_re_reads", "error_rate", "context_window_usage",
            "test_results", "code_coverage", "linting_status", "documentation_coverage",
            "total_tool_calls", "successful_tool_calls", "failed_tool_calls",
            "read_file_calls", "write_file_calls", "edit_file_calls",
            "shell_calls", "git_ops_calls", "other_tool_calls",
        }

        return key in component_keys

    def get(self, key: str, default: Any = None) -> Any:
        """Support dictionary-like get method for backward compatibility.

        Args:
            key: The metric name to retrieve.
            default: Default value if key doesn't exist.

        Returns:
            The metric value or default.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key: str, value: Any) -> None:
        """Support dictionary-like assignment for backward compatibility.

        Args:
            key: The metric name to set.
            value: The value to assign.

        Raises:
            KeyError: If the key is not a valid metric.
        """
        # Check main class attributes
        if hasattr(self, key):
            setattr(self, key, value)
            return

        # Check component class attributes that can be set
        component_setters = {
            "task_start_time": lambda v: setattr(self.performance, "task_start_time", v),
            "task_end_time": lambda v: setattr(self.performance, "task_end_time", v),
            "task_duration_minutes": lambda v: setattr(self.performance, "task_duration_minutes", v),  # noqa: E501
            "files_accessed": lambda v: setattr(self.performance, "files_accessed", v),
            "tool_usage_by_type": lambda v: setattr(self.performance, "tool_usage_by_type", v),
            "delegation_rate": lambda v: setattr(self.performance, "delegation_rate", v),
            "file_re_reads": lambda v: setattr(self.performance, "file_re_reads", v),
            "error_rate": lambda v: setattr(self.performance, "error_rate", v),
            "context_window_usage": lambda v: setattr(self.performance, "context_window_usage", v),
            "test_results": lambda v: setattr(self.quality, "test_results", v),
            "code_coverage": lambda v: setattr(self.quality, "code_coverage", v),
            "linting_status": lambda v: setattr(self.quality, "linting_status", v),
            "documentation_coverage": lambda v: setattr(self.quality, "documentation_coverage", v),
            "total_tool_calls": lambda v: setattr(self.tools, "total_tool_calls", v),
            "successful_tool_calls": lambda v: setattr(self.tools, "successful_tool_calls", v),
            "failed_tool_calls": lambda v: setattr(self.tools, "failed_tool_calls", v),
            "read_file_calls": lambda v: setattr(self.tools, "read_file_calls", v),
            "write_file_calls": lambda v: setattr(self.tools, "write_file_calls", v),
            "edit_file_calls": lambda v: setattr(self.tools, "edit_file_calls", v),
            "shell_calls": lambda v: setattr(self.tools, "shell_calls", v),
            "git_ops_calls": lambda v: setattr(self.tools, "git_ops_calls", v),
            "other_tool_calls": lambda v: setattr(self.tools, "other_tool_calls", v),
        }

        if key in component_setters:
            component_setters[key](value)  # type: ignore[no-untyped-call]
        else:
            msg = f"'{key}' is not a valid metric"
            raise KeyError(msg)
