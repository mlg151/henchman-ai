"""Built-in tools for Henchman-AI."""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass

from henchman.tools.builtins.ask_user import AskUserTool
from henchman.tools.builtins.code_format import CodeFormatTool
from henchman.tools.builtins.coverage_map import CoverageMapTool
from henchman.tools.builtins.dead_code import DeadCodeTool
from henchman.tools.builtins.deep_research import DeepResearchTool
from henchman.tools.builtins.delegate import DelegateTaskTool
from henchman.tools.builtins.diff_view import DiffViewTool
from henchman.tools.builtins.env_inspect import EnvInspectTool
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_overview import FileOverviewTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.git_ops import GitOpsTool
from henchman.tools.builtins.glob_tool import GlobTool
from henchman.tools.builtins.goal_status import GoalStatusTool
from henchman.tools.builtins.grep import GrepTool
from henchman.tools.builtins.import_graph import ImportGraphTool
from henchman.tools.builtins.kg_query import KgQueryTool
from henchman.tools.builtins.kg_update import KgUpdateTool
from henchman.tools.builtins.lint_check import LintCheckTool
from henchman.tools.builtins.ls import LsTool
from henchman.tools.builtins.patch_apply import PatchApplyTool
from henchman.tools.builtins.pattern_search import PatternSearchTool
from henchman.tools.builtins.pip_inspect import PipInspectTool
from henchman.tools.builtins.pytest_run import PytestRunTool
from henchman.tools.builtins.python_ast import PythonAstTool
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.builtins.rag_search import RagSearchTool
from henchman.tools.builtins.research_notes import ResearchNotesTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.builtins.symbol_trace import SymbolTraceTool
from henchman.tools.builtins.test_gen import TestGenTool
from henchman.tools.builtins.tier1_tools import SkillTool, SleepTool, ToolSearchTool
from henchman.tools.builtins.tier2_tools import (
    EnterPlanModeTool,
    EnterWorktreeTool,
    ExitPlanModeTool,
    ExitWorktreeTool,
)
from henchman.tools.builtins.tier5_tools import (
    SendMessageTool,
    SendUserFileTool,
    TeamCreateTool,
    TeamDeleteTool,
    WorkflowTool,
)
from henchman.tools.builtins.tier6_tools import (
    LSPTool,
    McpAuthTool,
    MCPTool,
    REPLTool,
    ScheduleCronTool,
    TaskCreateTool,
    TaskGetTool,
    TaskListTool,
    TaskOutputTool,
    TaskStopTool,
    TaskUpdateTool,
    TungstenTool,
    VerifyPlanExecutionTool,
)
from henchman.tools.builtins.traceback_parse import TracebackParseTool
from henchman.tools.builtins.web_fetch import WebFetchTool
from henchman.tools.builtins.web_search import DuckDuckGoSearchTool as WebSearchTool


@dataclass
class _BuiltinSpec:
    """Specification for a builtin tool that may be unavailable."""

    export_name: str
    tool_name: str
    description: str


class _PlaceholderTool:
    """Placeholder for a builtin tool that is not available in the current environment."""

    def __init__(self, spec: _BuiltinSpec) -> None:
        """Initialize the placeholder.

        Args:
            spec: The builtin tool specification.
        """
        self._spec = spec

    @property
    def name(self) -> str:
        """Return the tool name for this placeholder."""
        return self._spec.tool_name


def _create_placeholder_tool(spec: _BuiltinSpec) -> type[_PlaceholderTool]:
    """Create a placeholder tool class for an unavailable builtin.

    Args:
        spec: Specification for the builtin tool.

    Returns:
        A placeholder tool class.
    """
    return type(
        spec.export_name,
        (_PlaceholderTool,),
        {"__doc__": spec.description, "_spec": spec},
    )


_UNAVAILABLE_BUILTIN_NAMES: set[str] = set()


def unavailable_builtin_exports() -> set[str]:
    """Return the set of export names that are placeholders for unavailable tools.

    Returns:
        Set of export names that are unavailable in the current environment.
    """
    module = sys.modules[__name__]
    unavailable: set[str] = set()
    for name in __all__:
        obj = getattr(module, name, None)
        if obj is not None and isinstance(obj, type) and issubclass(obj, _PlaceholderTool):
            unavailable.add(name)
    return unavailable


def iter_available_builtin_tool_classes() -> tuple[type[object], ...]:
    """Iterate over all available builtin tool classes.

    Excludes placeholder/unavailable tools and tools that require
    runtime wiring (e.g., RagSearchTool).

    Returns:
        Tuple of available builtin tool classes registered in this module.
    """
    module = sys.modules[__name__]
    classes: list[type[object]] = []
    for name in __all__:
        obj = getattr(module, name, None)
        if obj is None or not inspect.isclass(obj):
            continue
        if issubclass(obj, _PlaceholderTool):
            continue
        # Skip tools that require runtime wiring and can't be instantiated directly
        if obj is RagSearchTool:
            continue
        classes.append(obj)
    return tuple(classes)


__all__ = [
    "AskUserTool",
    "CodeFormatTool",
    "CoverageMapTool",
    "DeadCodeTool",
    "DeepResearchTool",
    "DelegateTaskTool",
    "DiffViewTool",
    "EditFileTool",
    "EnterPlanModeTool",
    "EnterWorktreeTool",
    "EnvInspectTool",
    "ExitPlanModeTool",
    "ExitWorktreeTool",
    "FileOverviewTool",
    "GitOpsTool",
    "GlobTool",
    "GoalStatusTool",
    "GrepTool",
    "ImportGraphTool",
    "KgQueryTool",
    "KgUpdateTool",
    "LSPTool",
    "LintCheckTool",
    "LsTool",
    "MCPTool",
    "McpAuthTool",
    "PatchApplyTool",
    "PatternSearchTool",
    "PipInspectTool",
    "PytestRunTool",
    "PythonAstTool",
    "PythonExecTool",
    "RagSearchTool",
    "ReadFileTool",
    "REPLTool",
    "ResearchNotesTool",
    "ScheduleCronTool",
    "SendMessageTool",
    "SendUserFileTool",
    "ShellTool",
    "SkillTool",
    "SleepTool",
    "SymbolTraceTool",
    "TaskCreateTool",
    "TaskGetTool",
    "TaskListTool",
    "TaskOutputTool",
    "TaskStopTool",
    "TaskUpdateTool",
    "TeamCreateTool",
    "TeamDeleteTool",
    "TestGenTool",
    "ToolSearchTool",
    "TracebackParseTool",
    "TungstenTool",
    "VerifyPlanExecutionTool",
    "WebFetchTool",
    "WebSearchTool",
    "WorkflowTool",
    "WriteFileTool",
]
