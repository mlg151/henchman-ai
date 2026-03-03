"""Metrics classes for the orchestrator agent system."""

from __future__ import annotations

from dataclasses import dataclass, field
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

# Mapping from ToolCategory enum to the attribute name on ToolMetrics
_CATEGORY_ATTR_MAP: dict[ToolCategory, str] = {
    ToolCategory.READ_FILE: "read_file_calls",
    ToolCategory.WRITE_FILE: "write_file_calls",
    ToolCategory.EDIT_FILE: "edit_file_calls",
    ToolCategory.SHELL: "shell_calls",
    ToolCategory.GIT_OPS: "git_ops_calls",
}


def _categorize_tool(tool_name: str) -> ToolCategory:
    """Categorize a tool by its name.

    Args:
        tool_name: Name of the tool to categorize.

    Returns:
        The tool's category, or ToolCategory.OTHER if not found.
    """
    return _TOOL_CATEGORY_MAP.get(tool_name, ToolCategory.OTHER)


def _increment_counter(counter: dict[str, int], key: str) -> None:
    """Increment a string-keyed integer counter dict in-place.

    Args:
        counter: The dict to mutate.
        key: The key whose count should be incremented.
    """
    counter[key] = counter.get(key, 0) + 1


@dataclass
class PerformanceMetrics:
    """Encapsulates performance-related metrics."""

    # Target constants
    DELEGATION_RATE_TARGET: float = field(default=40.0, init=False, repr=False)
    ERROR_RATE_TARGET: float = field(default=50.0, init=False, repr=False)
    CONTEXT_WINDOW_TARGET: float = field(default=40.0, init=False, repr=False)
    FILE_RE_READS_TARGET: float = field(default=1.3, init=False, repr=False)
    FILE_RE_READS_BASELINE: float = field(default=3.2, init=False, repr=False)

    task_start_time: float = 0.0
    task_end_time: float = 0.0
    task_duration_minutes: float = 0.0
    files_accessed: dict[str, int] = field(default_factory=dict)
    tool_usage_by_type: dict[str, int] = field(default_factory=dict)
    delegation_rate: float = 0.0
    file_re_reads: int = 0
    error_rate: float = 0.0
    context_window_usage: float = 0.0

    def reset(self: PerformanceMetrics) -> None:
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

    def calculate_file_re_reads(self: PerformanceMetrics) -> None:
        """Calculate file re-reads from access patterns."""
        if self.files_accessed:
            total_accesses = sum(self.files_accessed.values())
            unique_files = len(self.files_accessed)
            if unique_files > 0:
                self.file_re_reads = total_accesses - unique_files

    def track_file_access(self: PerformanceMetrics, file_path: str) -> None:
        """Track a file access for re-read analysis.

        Args:
            file_path: The path of the file that was accessed.
        """
        _increment_counter(self.files_accessed, file_path)

    def track_tool_usage(self: PerformanceMetrics, tool_name: str) -> None:
        """Track tool usage by type.

        Args:
            tool_name: The name of the tool that was used.
        """
        counter = self.tool_usage_by_type
        counter[tool_name] = counter.get(tool_name, 0) + 1


@dataclass
class QualityMetrics:
    """Encapsulates quality-related metrics."""

    test_results: dict[str, Any] = field(
        default_factory=lambda: {"passing": 0, "total": 0, "percentage": 0.0},
    )
    code_coverage: float = 0.0
    linting_status: dict[str, int] = field(
        default_factory=lambda: {"errors": 0, "warnings": 0},
    )
    documentation_coverage: float = 0.0

    def reset(self: QualityMetrics) -> None:
        """Reset quality metrics for a new run."""
        self.test_results = {"passing": 0, "total": 0, "percentage": 0.0}
        self.code_coverage = 0.0
        self.linting_status = {"errors": 0, "warnings": 0}
        self.documentation_coverage = 0.0

    def calculate_test_percentage(self: QualityMetrics) -> None:
        """Calculate test results percentage."""
        if self.test_results["total"] > 0:
            self.test_results["percentage"] = (
                self.test_results["passing"]
                / self.test_results["total"]
                * PERCENTAGE_MULTIPLIER
            )


class ToolMetrics:
    """Encapsulates tool usage metrics."""

    def __init__(self: ToolMetrics) -> None:
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

    def reset(self: ToolMetrics) -> None:
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

    def track_tool_call(self: ToolMetrics, tool_name: str, *, success: bool) -> None:
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

        counter_attr = _CATEGORY_ATTR_MAP.get(
            _categorize_tool(tool_name),
            "other_tool_calls",
        )
        setattr(self, counter_attr, getattr(self, counter_attr) + 1)

    def calculate_error_rate(self: ToolMetrics) -> float:
        """Calculate error rate percentage."""
        if self.total_tool_calls > 0:
            return (
                self.failed_tool_calls / self.total_tool_calls
            ) * PERCENTAGE_MULTIPLIER
        return 0.0

    def get_tool_call_counts_by_category(self: ToolMetrics) -> dict[ToolCategory, int]:
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


# Mapping from public key name → (component_attr, field_name) for OrchestratorMetrics.
# Used by __getitem__, __setitem__, and __contains__ to avoid large inline dicts.
_COMPONENT_KEY_MAP: dict[str, tuple[str, str]] = {
    # PerformanceMetrics fields
    "task_start_time": ("performance", "task_start_time"),
    "task_end_time": ("performance", "task_end_time"),
    "task_duration_minutes": ("performance", "task_duration_minutes"),
    "files_accessed": ("performance", "files_accessed"),
    "tool_usage_by_type": ("performance", "tool_usage_by_type"),
    "delegation_rate": ("performance", "delegation_rate"),
    "file_re_reads": ("performance", "file_re_reads"),
    "error_rate": ("performance", "error_rate"),
    "context_window_usage": ("performance", "context_window_usage"),
    # QualityMetrics fields
    "test_results": ("quality", "test_results"),
    "code_coverage": ("quality", "code_coverage"),
    "linting_status": ("quality", "linting_status"),
    "documentation_coverage": ("quality", "documentation_coverage"),
    # ToolMetrics fields
    "total_tool_calls": ("tools", "total_tool_calls"),
    "successful_tool_calls": ("tools", "successful_tool_calls"),
    "failed_tool_calls": ("tools", "failed_tool_calls"),
    "read_file_calls": ("tools", "read_file_calls"),
    "write_file_calls": ("tools", "write_file_calls"),
    "edit_file_calls": ("tools", "edit_file_calls"),
    "shell_calls": ("tools", "shell_calls"),
    "git_ops_calls": ("tools", "git_ops_calls"),
    "other_tool_calls": ("tools", "other_tool_calls"),
}


class OrchestratorMetrics:
    """Encapsulates metrics collection and calculation for the orchestrator.

    This class addresses the Primitive Obsession code smell by providing
    a proper object-oriented interface for metrics management instead of
    using a complex nested dictionary directly.
    """

    def __init__(self: OrchestratorMetrics) -> None:
        """Initialize all metrics with default values."""
        # Core metrics
        self.thinking_pattern_usage: int = 0
        self.delegation_count: int = 0
        self.delegation_by_type: dict[str, int] = {
            "planner": 0,
            "explorer": 0,
            "engineer": 0,
        }
        self.thinking_quality_score: int = 0

        # Component metrics
        self.performance = PerformanceMetrics()
        self.quality = QualityMetrics()
        self.tools = ToolMetrics()

    def reset_for_run(self: OrchestratorMetrics) -> None:
        """Reset all metrics for a new run while preserving structure."""
        self.thinking_pattern_usage = 0
        self.delegation_count = 0
        self.delegation_by_type = {"planner": 0, "explorer": 0, "engineer": 0}
        self.thinking_quality_score = 0

        self.performance.reset()
        self.quality.reset()
        self.tools.reset()

    def calculate_final_metrics(self: OrchestratorMetrics) -> None:
        """Calculate derived metrics after task completion."""
        if self.performance.task_start_time and self.performance.task_end_time:
            duration = self.performance.task_end_time - self.performance.task_start_time
            self.performance.task_duration_minutes = duration / SECONDS_PER_MINUTE

        total_tasks = self.tools.total_tool_calls + self.delegation_count
        if total_tasks > 0:
            self.performance.delegation_rate = (
                self.delegation_count / total_tasks * PERCENTAGE_MULTIPLIER
            )

        self.performance.error_rate = self.tools.calculate_error_rate()
        self.quality.calculate_test_percentage()
        self.performance.calculate_file_re_reads()

    def update_tool_metrics(
        self: OrchestratorMetrics,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        success: bool,
    ) -> None:
        """Update metrics for a tool call.

        Args:
            tool_name: Name of the tool called.
            arguments: Arguments passed to the tool.
            success: Whether the tool call succeeded.
        """
        self.tools.track_tool_call(tool_name, success=success)
        self.performance.track_tool_usage(tool_name)

        if tool_name == "read_file" and "path" in arguments:
            file_path = str(arguments["path"])
            self.performance.track_file_access(file_path)

    def __getitem__(self: OrchestratorMetrics, key: str) -> Any:
        """Support dictionary-like access for backward compatibility.

        Args:
            key: The metric name to retrieve.

        Returns:
            The metric value.

        Raises:
            KeyError: If the key is not a valid metric.
        """
        if hasattr(self, key):
            return getattr(self, key)
        if key in _COMPONENT_KEY_MAP:
            component_name, attr = _COMPONENT_KEY_MAP[key]
            return getattr(getattr(self, component_name), attr)
        msg = f"'{key}' is not a valid metric"
        raise KeyError(msg)

    def __contains__(self: OrchestratorMetrics, key: str) -> bool:
        """Support 'in' operator for backward compatibility.

        Args:
            key: The metric name to check.

        Returns:
            True if the metric exists, False otherwise.
        """
        return hasattr(self, key) or key in _COMPONENT_KEY_MAP

    def get(self: OrchestratorMetrics, key: str, default: Any = None) -> Any:
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

    def __setitem__(self: OrchestratorMetrics, key: str, value: Any) -> None:
        """Support dictionary-like assignment for backward compatibility.

        Args:
            key: The metric name to set.
            value: The value to assign.

        Raises:
            KeyError: If the key is not a valid metric.
        """
        if hasattr(self, key):
            setattr(self, key, value)
            return
        if key in _COMPONENT_KEY_MAP:
            component_name, attr = _COMPONENT_KEY_MAP[key]
            setattr(getattr(self, component_name), attr, value)
        else:
            msg = f"'{key}' is not a valid metric"
            raise KeyError(msg)
