"""Additional selected-file admission for the opt-in Neovim pilot.

This is a repeatable dispatch check, not filesystem confinement against another
process. Builtin policy, approvals, checkpoint capture and formatter ownership
remain authoritative. Pytest executes explicitly trusted project code.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from henchman.advanced.checkpoint_files import WorkspaceFiles
from henchman.advanced.checkpoint_models import CheckpointConflict
from henchman.tools.base import Tool, ToolResult
from henchman.tools.builtins.ask_user import AskUserTool
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.patch_apply import PatchApplyTool, PatchParser
from henchman.tools.builtins.pytest_run import PytestRunTool
from henchman.tools.registry import ExecutionGuard, ToolRegistry
from henchman.utils.evidence_redaction import EvidenceRedactor

_IMPLEMENTATIONS: dict[type[Tool], object] = {kind: kind.execute for kind in (
    ReadFileTool, WriteFileTool, EditFileTool, PatchApplyTool, PytestRunTool, AskUserTool,
)}
_PRIVATE = frozenset({".git", ".henchman", ".Henchman", ".venv", "node_modules", "__pycache__"})
_DENIAL = "Editor selection does not permit this tool, target, or changed workspace; no action was dispatched."


class EditorSelection:
    """Hold explicit existing files and parent identity for one subprocess run."""

    def __init__(self, project_root: Path, paths: tuple[str, ...]) -> None:
        self.root = project_root.absolute()
        self._closed = False
        self._registry: ToolRegistry | None = None
        self._previous: ExecutionGuard | None = None
        self._callback: ExecutionGuard = self._guard_with_previous
        self._parents: dict[str, tuple[tuple[int, int], ...]] = {}
        try:
            if (os.name != "posix" or not 1 <= len(paths) <= 256
                    or self.root.resolve(strict=True) != self.root):
                raise ValueError
            self._files = WorkspaceFiles(self.root, EvidenceRedactor(), 1_048_576, ())
            names = tuple(self._name(path) for path in paths)
            if len(set(names)) != len(names):
                raise ValueError
            for name in names:
                self._parents[name] = self._observe(name)
            self.paths = names
        except (OSError, ValueError, CheckpointConflict):
            raise ValueError("Editor selection requires 1–256 distinct saved regular project files without links or private state.") from None

    def _name(self, value: object) -> str:
        if not isinstance(value, str) or not value or len(value) > 4096 or "\\" in value or "\x00" in value:
            raise ValueError
        path = Path(value)
        if not path.parts or ".." in path.parts or path.parts[0].startswith("~"):
            raise ValueError
        if path.is_absolute():
            path = path.relative_to(self.root)
        if any(part in _PRIVATE for part in path.parts):
            raise ValueError
        return self._files.path(path.as_posix())

    def _observe(self, name: str) -> tuple[tuple[int, int], ...]:
        with self._files.parent(name) as (directory, leaf, parents):
            metadata = os.stat(leaf, dir_fd=directory, follow_symlinks=False)
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                    or metadata.st_mode & 0o7000):
                raise ValueError
            return parents

    def _targets(self, tool: Tool, params: dict[str, object]) -> tuple[str, ...]:
        if type(tool) is AskUserTool:
            return ()
        if type(tool) is PatchApplyTool:
            patch = params.get("patch")
            default = params.get("path")
            if not isinstance(patch, str) or (default is not None and not isinstance(default, str)):
                raise ValueError
            targets = tuple(PatchParser(patch, default).parse())
            if not targets or len(targets) > 256:
                raise ValueError
            return tuple(self._name(path) for path in targets)
        path = params.get("path")
        if type(tool) is PytestRunTool:
            # Ordinary pytest/conftest/plugins execute trusted project code;
            # this allowlist neither confines nor certifies those effects.
            timeout = params.get("timeout", 300)
            if (type(timeout) is not int or not 1 <= timeout <= 300
                    or params.get("coverage", False) is not False or params.get("parallel") is not None):
                raise ValueError
            if isinstance(path, str):
                path = path.split("::", 1)[0]
        return (self._name(path),)

    def guard(self, tool: Tool, params: dict[str, object]) -> ToolResult | None:
        """Recheck live paths at every inherited registry dispatch boundary."""
        try:
            if self._closed or Path.cwd() != self.root:
                raise ValueError
            expected = _IMPLEMENTATIONS.get(type(tool))
            if expected is None or getattr(tool.execute, "__func__", None) is not expected:
                raise ValueError
            self._files.check_root()
            for name in self._targets(tool, params):
                if name not in self._parents or self._observe(name) != self._parents[name]:
                    raise ValueError
        except (OSError, ValueError, CheckpointConflict):
            return ToolResult(_DENIAL, success=False, error=_DENIAL)
        return None

    def _guard_with_previous(self, tool: Tool, params: dict[str, object]) -> ToolResult | None:
        denied = self.guard(tool, params)
        return denied if denied is not None or self._previous is None else self._previous(tool, params)

    def bind(self, registry: ToolRegistry) -> None:
        """Intersect the existing guard; never change approval/access policy."""
        if self._closed or self._registry is not None:
            raise ValueError("Editor selection has already been bound or retired")
        self._registry, self._previous = registry, registry._execution_guard
        registry.bind_execution_guard(self._callback)

    def close(self) -> None:
        """Revoke retained callbacks and restore only this owned binding."""
        self._closed = True
        if self._registry is not None and self._registry._execution_guard is self._callback:
            self._registry.bind_execution_guard(self._previous)
