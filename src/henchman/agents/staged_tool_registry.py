"""A closed, policy-inheriting tool scope over one child's staged files.

Opt-in dynamic subagents use this adapter to expose only exact builtin file
tools through a worker-bound overlay. Shell, MCP and other opaque effects are
deliberately unavailable. Restricted policies still fail closed.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from io import StringIO
from pathlib import Path

from henchman.agents.proposal_runtime import StagedWorkspace
from henchman.agents.workspace_ownership import WorkspaceOwnershipError
from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.builtins.file_edit import (
    EditFileTool,
    EditParams,
    _build_replacement,
    _make_diff,
    _validate_line_range,
)
from henchman.tools.builtins.file_read import ReadFileTool, _config_from_read_kwargs
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.formatting import PythonAutoFormatter
from henchman.tools.registry import ToolRegistry
from henchman.tools.scoped_registry import ScopedToolRegistry

_SOURCES: dict[str, type[Tool]] = {"read_file": ReadFileTool, "write_file": WriteFileTool, "edit_file": EditFileTool}


class _StageFormatter(PythonAutoFormatter):
    async def run(self, tool: Tool, params: dict[str, object], execute: Callable[[], Awaitable[ToolResult]]) -> ToolResult:
        # Staging never mutates source files; scanning/formatting the live tree
        # here could otherwise claim another actor's unrelated changes.
        return await execute()


class _StagedFileTool(Tool):
    def __init__(self, source: Tool, workspace: StagedWorkspace) -> None:
        self._source = source
        self._workspace = workspace

    @property
    def name(self) -> str:
        return self._source.name

    @property
    def description(self) -> str:
        return f"{self._source.description} Operates only on the child's staged file scope; parent review is required."

    @property
    def parameters(self) -> dict[str, object]:
        return deepcopy(self._source.parameters)

    @property
    def kind(self) -> ToolKind:
        return self._source.kind

    def needs_confirmation(self, params: dict[str, object]) -> ConfirmationRequest | None:
        if self.kind is ToolKind.READ:
            return None
        return ConfirmationRequest(self.name, "Stage a scoped file change for parent review", params, risk_level="medium")

    def checkpoint_paths(self, params: dict[str, object]) -> tuple[str, ...] | None:
        return ()  # Staging does not mutate a live workspace file.

    async def execute(self, **params: object) -> ToolResult:
        try:
            return self._execute(params)
        except (WorkspaceOwnershipError, ValueError) as error:
            return ToolResult(content=f"Staged file operation refused: {error}", success=False, error=str(error))

    def _execute(self, params: dict[str, object]) -> ToolResult:
        path = params.get("path")
        if not isinstance(path, str) or not path:
            return ToolResult(content="A scoped file path is required.", success=False, error="Invalid path")
        if self.name == "write_file":
            content = params.get("content")
            if not isinstance(content, str):
                return ToolResult(content="Content must be text.", success=False, error="Invalid content")
            self._workspace.stage(path, content)
            return ToolResult(content="Staged file content for parent review.")
        content = self._workspace.read(path)
        if content is None:
            return ToolResult(content="Staged file does not exist.", success=False, error="File not found")
        normalized = StringIO(content, newline=None).read()
        if self.name == "read_file":
            return ToolResult(content=_render_read(normalized, params))
        return self._edit(path, normalized, params)

    def _edit(self, path: str, content: str, params: dict[str, object]) -> ToolResult:
        replacement = params.get("new_str")
        old = params.get("old_str")
        start, end = params.get("start_line"), params.get("end_line")
        if not isinstance(replacement, str):
            return ToolResult(content="Replacement must be text.", success=False, error="Invalid replacement")
        if (start is None) != (end is None) or (old is not None and (start is not None or end is not None)):
            return ToolResult(content="Use either old_str or both line bounds, not both modes.", success=False, error="Invalid edit mode")
        if old is not None:
            if not isinstance(old, str) or not old or content.count(old) != 1:
                return ToolResult(content="Staged text must match exactly once; reread it before retrying.",
                                  success=False, error="Text does not match uniquely")
            updated = content.replace(old, replacement, 1)
        else:
            if type(start) is not int or type(end) is not int:
                return ToolResult(content="Provide old_str or both line bounds.", success=False, error="Invalid edit mode")
            edit = EditParams(path=path, new_str=replacement, start_line=start, end_line=end)
            lines = StringIO(content).readlines()
            error = _validate_line_range(edit, len(lines))
            if error is not None:
                return error
            value, last = _build_replacement(edit, len(lines))
            updated = "".join([*lines[:start - 1], value, *lines[last:]])
        if params.get("dry_run", False):
            return _make_diff(Path(path), content, updated)
        self._workspace.stage(path, updated)
        return ToolResult(content="Staged file edit for parent review.")


def _render_read(content: str, params: dict[str, object]) -> str:
    config = _config_from_read_kwargs("", params)
    result: list[str] = []
    count = 0
    for number, line in enumerate(StringIO(content), start=1):
        if number < config.start_line:
            continue
        if config.end_line != -1 and number > config.end_line:
            break
        if config.line_numbers:
            line = f"{number}: {line}"
        if config.max_chars > 0 and count + len(line) > config.max_chars:
            result.extend((line[:config.max_chars - count], f"\n... (truncated after {config.max_chars} chars)"))
            break
        result.append(line)
        count += len(line)
    return "".join(result)


class StagedToolRegistry(ScopedToolRegistry):
    """Allow only existing exact file tools, replaced with staged implementations."""

    def __init__(self, parent: ToolRegistry, workspace: StagedWorkspace, allowed_tools: list[str]) -> None:
        if Path.cwd().resolve() != workspace._runtime._root_path:
            raise ValueError("Staged tool scope requires the bound project as current directory")
        if (not isinstance(allowed_tools, list) or not all(isinstance(name, str) for name in allowed_tools)
                or not set(allowed_tools) <= _SOURCES.keys()):
            raise ValueError("Staged scope supports only read_file, write_file and edit_file")
        sources: dict[str, Tool] = {}
        for name in dict.fromkeys(allowed_tools):
            source = parent.get(name)
            if type(source) is not _SOURCES[name] or getattr(source.execute, "__func__", None) is not _SOURCES[name].execute:
                raise PermissionError("Staged tool requires the current exact builtin implementation")
            sources[name] = source
        self._sources = sources
        self._closed_registration = False
        self._stage_formatter = _StageFormatter()
        super().__init__(parent, [], inherit_auto_approve=True)
        for source in sources.values():
            super().register(_StagedFileTool(source, workspace))
        self._closed_registration = True

    @property
    def _effective_formatter(self) -> PythonAutoFormatter:
        return self._stage_formatter

    def register(self, tool: Tool) -> None:
        if self._closed_registration:
            raise PermissionError("Staged tool registration is closed")
        super().register(tool)

    def get(self, name: str) -> Tool | None:
        source = self._sources.get(name)
        if source is None or self._parent.get(name) is not source:
            return None
        if getattr(source.execute, "__func__", None) is not _SOURCES[name].execute:
            return None
        return super().get(name)
