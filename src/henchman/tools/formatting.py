"""Bounded automatic Python formatting after authorized tool mutations."""

from __future__ import annotations

import asyncio
import hashlib
import stat
import sys
from collections.abc import Awaitable, Callable, Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from threading import Event

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.subprocess_utils import run_bounded_subprocess
from henchman.utils.source_files import iter_python_files

MAX_FILES = 5000
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_BATCH_PATHS = 64
MAX_ARGV_CHARS = 20_000
FORMAT_TIMEOUT = 30.0
_SUFFIXES = frozenset({".py", ".pyi"})
_BLACK_COMMAND = [sys.executable, "-I", "-m", "black", "--quiet", "--workers", "1", "--safe", "--"]
_FileIdentity = tuple[int, int, int, int, int]


class FormattingError(Exception):
    """Tracking or Black could not complete within the formatter's bounds."""


@dataclass
class _TrackingReport:
    entries_seen: int = 0
    skipped_symlinks: int = 0
    truncated: bool = False
    errors: list[str] = field(default_factory=list)

    def error(self, path: Path, message: str) -> None:
        if not self.errors:
            self.errors.append(f"{path}: {message}")
        self.truncated = True


@dataclass(frozen=True)
class _Scope:
    root: Path
    direct: bool


@dataclass
class _Invocation:
    """Admission and serialization for nested calls in one tool transaction."""

    active: bool = True
    child_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    child_task: asyncio.Task[object] | None = None


async def _close_invocation(frame: _Invocation, *, cancel: bool = False) -> None:
    """Close admission and join the admitted child before releasing its parent."""
    frame.active = False
    if not frame.child_lock.locked():
        return
    if cancel and frame.child_task is not None:
        frame.child_task.cancel()

    async def wait_for_child() -> None:
        async with frame.child_lock:
            pass

    cleanup = asyncio.create_task(wait_for_child())
    interrupted: asyncio.CancelledError | None = None
    while not cleanup.done():
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError as exc:
            interrupted = exc
            if frame.child_task is not None:
                frame.child_task.cancel()
    cleanup.result()
    if interrupted is not None:
        raise interrupted


def _scope(tool: Tool, params: dict[str, object]) -> _Scope | None:
    if tool.name == "lint_check":
        path = params.get("path")
        if isinstance(path, str) and path:
            target = Path(path).expanduser().resolve()
            if target.is_dir():
                return _Scope(target, False)
            return _Scope(target, True) if target.suffix in _SUFFIXES else None
    if tool.name in {"write_file", "edit_file"}:
        path = params.get("path")
        if isinstance(path, str) and path:
            target = Path(path).expanduser().resolve()
            return _Scope(target, True) if target.suffix in _SUFFIXES else None
    cwd = params.get("cwd")
    root = (
        Path(cwd).expanduser().resolve() if isinstance(cwd, str) and cwd else Path.cwd().resolve()
    )
    return _Scope(root, False)


def _reject_symlinks(path: Path) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise FormattingError(f"Cannot track symlink path: {component}")


def _identity(path: Path) -> _FileIdentity:
    _reject_symlinks(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise FormattingError(f"Expected a regular Python source file: {path}")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _check_size(path: Path, identity: _FileIdentity) -> None:
    if identity[2] > MAX_SOURCE_BYTES:
        raise FormattingError(f"Python source exceeds {MAX_SOURCE_BYTES}-byte limit: {path}")


def _snapshot(
    scope: _Scope, stop: Event, report: _TrackingReport | None = None
) -> dict[Path, _FileIdentity]:
    _reject_symlinks(scope.root)
    if scope.direct:
        try:
            return {scope.root: _identity(scope.root)}
        except FileNotFoundError:
            return {}
    if not scope.root.is_dir():
        raise FormattingError(f"Expected a working directory: {scope.root}")
    report = report if report is not None else _TrackingReport()
    snapshot: dict[Path, _FileIdentity] = {}
    for path in iter_python_files(
        scope.root, report, stop, suffixes=_SUFFIXES, skip_virtualenvs=True
    ):
        if len(snapshot) >= MAX_FILES:
            raise FormattingError(f"Python source tracking exceeds {MAX_FILES}-file limit")
        snapshot[path] = _identity(path)
    if report.truncated or stop.is_set():
        raise FormattingError(
            report.errors[0] if report.errors else "Python source tracking stopped"
        )
    return snapshot


async def _take_snapshot(scope: _Scope) -> dict[Path, _FileIdentity]:
    stop = Event()
    try:
        return await asyncio.to_thread(_snapshot, scope, stop)
    finally:
        stop.set()


def _batches(paths: list[Path]) -> Iterator[list[Path]]:
    batch: list[Path] = []
    base_chars = sum(len(arg) + 1 for arg in _BLACK_COMMAND)
    chars = base_chars
    for path in paths:
        size = len(str(path)) + 1
        if base_chars + size > MAX_ARGV_CHARS:
            raise FormattingError(f"Source path exceeds Black argv limit: {path}")
        if batch and (len(batch) >= MAX_BATCH_PATHS or chars + size > MAX_ARGV_CHARS):
            yield batch
            batch, chars = [], base_chars
        batch.append(path)
        chars += size
    if batch:
        yield batch


def _fingerprints(paths: list[Path], stop: Event) -> dict[Path, bytes]:
    result = {}
    for path in paths:
        identity = _identity(path)
        _check_size(path, identity)
        digest = hashlib.sha256()
        total = 0
        with path.open("rb") as source:
            while data := source.read(65536):
                if stop.is_set():
                    raise FormattingError("Python source fingerprinting stopped")
                total += len(data)
                if total > MAX_SOURCE_BYTES:
                    raise FormattingError(f"Python source exceeds byte limit: {path}")
                digest.update(data)
        if _identity(path) != identity:
            raise FormattingError(f"Python source changed while fingerprinting: {path}")
        result[path] = digest.digest()
    return result


async def _format_changed(scope: _Scope, before: dict[Path, _FileIdentity]) -> int:
    after = await _take_snapshot(scope)
    changed = sorted(path for path, identity in after.items() if before.get(path) != identity)
    if not changed:
        return 0
    cwd = scope.root.parent if scope.direct else scope.root
    stop = Event()
    try:
        async with asyncio.timeout(FORMAT_TIMEOUT):
            old = await asyncio.to_thread(_fingerprints, changed, stop)
            await format_python_files(changed, cwd=cwd)
            new = await asyncio.to_thread(_fingerprints, changed, stop)
            return sum(old[path] != new[path] for path in changed)
    except TimeoutError as exc:
        raise FormattingError(f"Black exceeded {FORMAT_TIMEOUT:g}-second timeout") from exc
    finally:
        stop.set()


def _expand_paths(paths: list[Path], cwd: Path, stop: Event) -> list[Path]:
    if len(paths) > MAX_FILES:
        raise FormattingError(f"Python source tracking exceeds {MAX_FILES}-file limit")
    sources: set[Path] = set()
    report = _TrackingReport()
    for path in paths:
        target = (cwd / path).resolve()
        _reject_symlinks(target)
        if target.is_dir():
            sources.update(_snapshot(_Scope(target, False), stop, report))
        else:
            if target.suffix not in _SUFFIXES:
                raise FormattingError(f"Expected a .py or .pyi source file: {target}")
            sources.add(target)
        if len(sources) > MAX_FILES:
            raise FormattingError(f"Python source tracking exceeds {MAX_FILES}-file limit")
    for source in sources:
        _check_size(source, _identity(source))
    return sorted(sources)


async def format_python_files(paths: list[Path], *, cwd: Path) -> None:
    """Run trusted Black on bounded files/directories, preserving timeout/cancellation.

    Standard project configuration is honored. This is formatting, not an OS
    sandbox or a guarantee that project-configured exclusions were formatted.
    """
    stop = Event()
    try:
        async with asyncio.timeout(FORMAT_TIMEOUT):
            sources = await asyncio.to_thread(_expand_paths, paths, cwd, stop)
            for batch in _batches(sources):
                result = await run_bounded_subprocess(
                    [*_BLACK_COMMAND, *(str(path) for path in batch)],
                    cwd=cwd,
                    timeout=FORMAT_TIMEOUT,
                    max_output_bytes=8192,
                )
                if result.returncode != 0:
                    output = (result.stderr or result.stdout).decode("utf-8", errors="replace")
                    raise FormattingError(f"Black exited {result.returncode}: {output.strip()}")
    finally:
        stop.set()


def _failure(result: ToolResult | None, error: Exception) -> ToolResult:
    message = f"Automatic Black formatting failed: {error}"
    if result is None:
        return ToolResult(message, success=False, error=message)
    return replace(
        result,
        content=f"{message}\n{result.content}",
        success=False,
        error=f"{result.error}; {message}" if result.error else message,
    )


class PythonAutoFormatter:
    """Serialize source mutation and automatic Black formatting."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._invocation: ContextVar[_Invocation | None] = ContextVar(
            "python_formatting_invocation", default=None
        )

    async def run(
        self,
        tool: Tool,
        params: dict[str, object],
        execute: Callable[[], Awaitable[ToolResult]],
    ) -> ToolResult:
        """Execute once, format observed source mutations, and preserve tool failures."""
        # Runtime coordination must remain available while a child holds the
        # mutation lock, especially when the parent needs to cancel that child.
        if tool.name in {"invoke_subagent", "manage_subagents"} or (
            tool.name == "send_message" and "conversation_id" in params
        ):
            return await execute()
        background = tool.name == "task_create" or (
            tool.name in {"shell", "shell_secure", "python_exec"}
            and bool(params.get("background", True))
        )
        if background:
            result = await execute()
            if result.success:
                return replace(
                    result,
                    content=f"{result.content}\nAutomatic Black formatting skipped for a "
                    "background task. Format changed Python files after the task completes.",
                )
            return result
        if tool.execution_kind(params) not in {ToolKind.WRITE, ToolKind.EXECUTE}:
            return await execute()
        parent = self._invocation.get()
        if parent is not None and parent.active:
            async with parent.child_lock:
                # The parent may close admission while this sibling waits.
                if parent.active:
                    parent.child_task = asyncio.current_task()
                    try:
                        return await self._run_invocation(tool, params, execute)
                    finally:
                        parent.child_task = None
        async with self._lock:
            return await self._run_invocation(tool, params, execute)

    async def _run_invocation(
        self,
        tool: Tool,
        params: dict[str, object],
        execute: Callable[[], Awaitable[ToolResult]],
    ) -> ToolResult:
        frame = _Invocation()
        token = self._invocation.set(frame)
        try:
            return await self._execute_and_format(tool, params, execute, frame)
        finally:
            try:
                await _close_invocation(frame, cancel=True)
            finally:
                self._invocation.reset(token)

    async def _execute_and_format(
        self,
        tool: Tool,
        params: dict[str, object],
        execute: Callable[[], Awaitable[ToolResult]],
        frame: _Invocation,
    ) -> ToolResult:
        try:
            scope = _scope(tool, params)
            before = await _take_snapshot(scope) if scope else {}
        except Exception as exc:
            return _failure(None, exc)
        try:
            result = await execute()
        except Exception as original:
            await _close_invocation(frame)
            if scope:
                try:
                    await _format_changed(scope, before)
                except Exception as formatting_error:
                    raise FormattingError(
                        f"Automatic Black formatting failed: {formatting_error}; "
                        f"original tool failure: {original}"
                    ) from original
            raise
        await _close_invocation(frame)
        if scope:
            try:
                formatted = await _format_changed(scope, before)
            except Exception as exc:
                return _failure(result, exc)
            if formatted:
                return replace(
                    result,
                    content=f"{result.content}\nBlack formatted {formatted} Python source file(s).",
                )
        return result
