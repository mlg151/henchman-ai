"""Foreground repair restrictions layered over ordinary tool authorization.

This is a trusted runtime lease, not a sandbox. Neither persisted reports nor
model arguments can create it, and inherited child tasks cannot use it.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from henchman.advanced.acceptance_checks import CheckSpec
    from henchman.advanced.verification_repair import VerificationRepairSession
    from henchman.tools.base import Tool


class RepairControlError(RuntimeError):
    """Repair authority is unavailable; never convert it into a retryable tool result."""


@dataclass
class _Spawn:
    command: tuple[str, ...]
    cwd: Path
    used: bool = False


_CURRENT: ContextVar[RepairScope | None] = ContextVar("repair_scope", default=None)
_SPAWN: ContextVar[_Spawn | None] = ContextVar("repair_spawn", default=None)


class RepairScope:
    """One owner, fixed implementations and a revocable foreground authority."""

    def __init__(self, repair: VerificationRepairSession, *, root: Path,
                 tools: tuple[Tool, ...], verifier: Tool, checks: tuple[CheckSpec, ...],
                 validate: Callable[[], None]) -> None:
        self.repair = repair
        self.root = root
        self.tools = {tool.name: (tool, getattr(tool.execute, "__func__", None)) for tool in tools}
        self.verifier = verifier
        self.checks = checks
        self.validate = validate
        self.owner = asyncio.current_task()
        self.active = True
        self.phase: Literal["repair", "verify"] | None = None
        self._invocation: Callable[[], None] | None = None
        self._failure: RepairControlError | None = None

    def deny(self, detail: str) -> None:
        self._failure = RepairControlError(detail)
        raise self._failure

    def check(self) -> None:
        if not self.active or asyncio.current_task() is not self.owner:
            self.deny("Repair authority is closed or belongs to another foreground task")
        if self._failure is not None:
            raise self._failure
        self.validate()
        self.repair._current()
        if self._invocation is not None:
            self._invocation()

    def paths(self, tool: Tool, params: dict[str, object]) -> tuple[Path, ...]:
        """Resolve only qualified builtins with their actual path semantics."""
        from henchman.tools.builtins.file_edit import EditFileTool
        from henchman.tools.builtins.file_read import ReadFileTool
        from henchman.tools.builtins.file_write import WriteFileTool
        from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool

        self.check()
        self.check_implementation(tool)
        if self.phase == "verify":
            if (tool is not self.verifier or type(tool) is not VerifyPlanExecutionTool
                or params != {"action": "verify", "plan_id": self.repair.request.plan_id}):
                self.deny("Only the captured verification is available during repair checks")
            return ()
        if self.phase != "repair" or type(tool) not in {ReadFileTool, EditFileTool, WriteFileTool}:
            self.deny("Tool is unsupported in bounded repair; request separate explicit work")
        raw = params.get("path")
        if not isinstance(raw, str) or not raw:
            self.deny("Repair tool requires an explicit file target")
        assert isinstance(raw, str)
        path = Path(os.path.abspath(Path(raw).expanduser()))
        if not path.is_relative_to(self.root):
            self.deny("Repair file target is outside the held project")
        relative = path.relative_to(self.root).as_posix()
        allowed = set(self.repair.request.edit_paths)
        if type(tool) is ReadFileTool:
            allowed.update(self.repair.request.protected_paths)
            for check in self.checks:
                allowed.update(check.inputs)
                if check.kind.startswith("file_") and check.path is not None:
                    allowed.add(check.path)
        if relative not in allowed:
            self.deny("Repair file target is protected or outside the explicit scope")
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            self.deny("Repair file targets cannot traverse symlinks")
        if type(tool) is WriteFileTool and not path.parent.is_dir():
            self.deny("Repair writes require an existing parent directory")
        return () if type(tool) is ReadFileTool or params.get("dry_run") is True else (path,)

    def check_implementation(self, tool: Tool) -> None:
        captured = self.tools.get(tool.name)
        if (captured is None or captured[0] is not tool
            or getattr(tool.execute, "__func__", None) is not captured[1]
            or getattr(tool.execute, "__func__", None) is not type(tool).execute):
            self.deny("Repair tool implementation changed or was not admitted")

    def disclosed_tools(self, tools: Sequence[Tool]) -> list[Tool]:
        """Expose only captured model tools; controller checks stay internal.

        Disclosure never grants execution. Missing/replaced captured file tools
        invalidate this lease instead of silently presenting a changed scope.
        """
        from henchman.tools.builtins.file_edit import EditFileTool
        from henchman.tools.builtins.file_read import ReadFileTool
        from henchman.tools.builtins.file_write import WriteFileTool

        self.check()
        if self.phase == "verify":
            return []
        if self.phase != "repair":
            self.deny("Model tool disclosure requires the foreground repair phase")
        qualified = {ReadFileTool, EditFileTool, WriteFileTool}
        current = {tool.name: tool for tool in tools}
        for name, (captured, _) in self.tools.items():
            if type(captured) in qualified and current.get(name) is not captured:
                self.deny("Repair tool implementation changed or was not admitted")
        visible = [tool for tool in tools if type(tool) in qualified]
        for tool in visible:
            self.check_implementation(tool)
        return visible

    async def admit(self, tool: Tool, params: dict[str, object]) -> None:
        paths = self.paths(tool, params)
        if paths:
            await self.repair.admit_mutation(tuple(path.relative_to(self.root).as_posix() for path in paths))
        self.check()

    @contextmanager
    def activate(self, phase: Literal["repair", "verify"]) -> Iterator[None]:
        previous = self.phase
        self.phase = phase
        token = _CURRENT.set(self)
        try:
            yield
        finally:
            _CURRENT.reset(token)
            self.phase = previous

    @contextmanager
    def invocation(self, validate: Callable[[], None]) -> Iterator[None]:
        previous = self._invocation
        self._invocation = validate
        try:
            yield
        finally:
            self._invocation = previous


def current_repair() -> RepairScope | None:
    return _CURRENT.get()


async def check_verification(root: Path, checks: tuple[CheckSpec, ...]) -> None:
    scope = current_repair()
    if scope is not None:
        scope.check()
        if scope.phase != "verify" or root != scope.root or checks != scope.checks:
            scope.deny("Verification no longer matches the captured repair criteria")
        await scope.repair._inspect()
        scope.check()


@contextmanager
def owned_spawn(command: Sequence[str], cwd: Path) -> Iterator[None]:
    """Bind one exact argv at a trusted check/formatter construction boundary."""
    scope = current_repair()
    if scope is None:
        yield
        return
    scope.check()
    if cwd != scope.root:
        scope.deny("Repair subprocess project changed")
    token = _SPAWN.set(_Spawn(tuple(command), cwd))
    try:
        yield
    finally:
        _SPAWN.reset(token)


async def check_spawn(command: Sequence[str], cwd: Path) -> None:
    scope = current_repair()
    if scope is not None:
        scope.check()
        permit = _SPAWN.get()
        if permit is None or permit.used or permit.command != tuple(command) or permit.cwd != cwd:
            scope.deny("Repair subprocess lacks its exact owned check or formatter admission")
        assert permit is not None
        await scope.repair._inspect()
        scope.check()
        permit.used = True
