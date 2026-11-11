"""User-owned, bounded POSIX external draft composition; never a model tool."""

from __future__ import annotations

import asyncio
import math
import os
import shlex
import signal
import stat
import sys
import tempfile
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_DRAFT_BYTES = 1024 * 1024
EDITOR_TIMEOUT = 1800.0
_STOP_TIMEOUT = 2.0


class DraftEditorError(RuntimeError):
    """A value-free composition failure; the original draft remains available."""


def resolve_editor_argv() -> tuple[str, ...]:
    """Resolve the explicitly configured command without shell expansion/fallback."""
    value = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not value:
        raise DraftEditorError("Set VISUAL or EDITOR to a foreground editor command first.")
    try:
        command = tuple(shlex.split(value))
        if not command or len(command) > 64 or len(value) > 16384 or "\0" in value:
            raise ValueError
    except ValueError:
        raise DraftEditorError("External editor configuration is invalid.") from None
    return command


def _environment() -> dict[str, str]:
    names = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "TERM", "COLORTERM", "LANG", "TZ", "TMPDIR"}
    return {name: value for name, value in os.environ.items()
            if name in names or name.startswith(("LC_", "XDG_"))}


def _authorize(callback: Callable[[], object]) -> None:
    try:
        if callback() is not None:
            raise ValueError
    except Exception:
        raise DraftEditorError("External editor requires the same idle session, draft and unrestricted policy.") from None


def _foreground(descriptor: int, group: int) -> None:
    # The parent becomes a background process while the editor owns this tty.
    # Block SIGTTOU only around this synchronous handoff, then restore the mask.
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTTOU})
    try:
        os.tcsetpgrp(descriptor, group)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def _read_draft(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_DRAFT_BYTES:
            raise DraftEditorError("Edited draft must be a regular private UTF-8 file within 1 MiB.")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            value = stream.read(MAX_DRAFT_BYTES + 1)
        if len(value) > MAX_DRAFT_BYTES:
            raise DraftEditorError("Edited draft exceeds 1 MiB; original draft preserved.")
        return value.decode("utf-8")
    finally:
        os.close(descriptor)


async def join_owned(task: asyncio.Task[Any], primary: BaseException | None = None) -> BaseException | None:
    """Join once-owned cleanup while retaining the first caller cancellation."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as error:
            if primary is None or not isinstance(primary, asyncio.CancelledError):
                primary = error
        except Exception:
            break
    try:
        task.result()
    except BaseException:
        if primary is None:
            primary = DraftEditorError("External editor cleanup could not confirm completion.")
        else:
            primary.add_note("External editor cleanup also failed.")
    return primary


async def check_editor_control(deadline: float | None = None) -> None:
    """Observe synchronous stop requests before effects or draft publication.

    Usually this has no suspension point. A pending Task.cancel is delivered
    by asyncio itself, preserving its first reason instead of inventing one.
    """
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        await asyncio.sleep(0)
        raise asyncio.CancelledError("External editor interruption requested.")
    if deadline is not None and asyncio.get_running_loop().time() >= deadline:
        raise DraftEditorError("External editor exceeded its deadline; original draft preserved.")


async def edit_draft(
    text: str, *, cwd: Path, authorize: Callable[[], None],
    argv: Sequence[str] | None = None, timeout: float = EDITOR_TIMEOUT,
) -> str:
    """Edit one private UTF-8 draft while owning its foreground process group.

    The configured editor must wait for editing to finish. A successful result
    is draft text only; callers must recheck their composer before applying it.
    Escaped/detached descendants and arbitrary editor behavior are not sandboxed.
    """
    if os.name != "posix" or not hasattr(os, "tcsetpgrp"):
        raise DraftEditorError("External editor composition currently requires a POSIX terminal.")
    import termios

    try:
        if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_DRAFT_BYTES:
            raise ValueError
    except (ValueError, UnicodeError):
        raise DraftEditorError("Draft must be UTF-8 within the 1 MiB external editor limit.") from None
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= EDITOR_TIMEOUT:
        raise DraftEditorError("External editor deadline is invalid.")
    command = tuple(argv) if argv is not None else resolve_editor_argv()
    if (not command or len(command) > 64 or any(not isinstance(part, str) or not part or "\0" in part for part in command)
            or sum(len(part) for part in command) > 16384):
        raise DraftEditorError("External editor configuration is invalid.")
    _authorize(authorize)
    await check_editor_control()
    try:
        terminal = os.open("/dev/tty", os.O_RDWR | os.O_CLOEXEC)
        attributes = termios.tcgetattr(terminal)
        foreground = os.tcgetpgrp(terminal)
        if foreground != os.getpgrp():
            raise OSError("not foreground")
    except OSError:
        if "terminal" in locals():
            os.close(terminal)
        raise DraftEditorError("External editor requires an attached foreground terminal.") from None
    temporary: tempfile.TemporaryDirectory[str] | None = None
    spawn: asyncio.Task[asyncio.subprocess.Process] | None = None
    process: asyncio.subprocess.Process | None = None
    gate_read = gate_write = -1
    result = text
    primary: BaseException | None = None
    deadline = asyncio.get_running_loop().time() + timeout
    try:
        temporary = tempfile.TemporaryDirectory(prefix="henchman-draft-")
        path = Path(temporary.name) / "draft.txt"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(text.encode("utf-8"))
        gate_read, gate_write = os.pipe()
        # Gate exec until the parent has rechecked admission and transferred the
        # terminal. Otherwise an editor can read before its group is foreground.
        async with asyncio.timeout_at(deadline):
            spawn = asyncio.create_task(asyncio.create_subprocess_exec(
                sys.executable, "-I", str(Path(__file__).resolve()), "--exec", str(gate_read), *command, str(path),
                stdin=terminal, stdout=terminal, stderr=terminal, cwd=cwd,
                env=_environment(), pass_fds=(gate_read,), process_group=0,
            ))
            process = await asyncio.shield(spawn)
            os.close(gate_read)
            gate_read = -1
            _authorize(authorize)
            await check_editor_control(deadline)
            _foreground(terminal, process.pid)
            await check_editor_control(deadline)
            os.write(gate_write, b"g")
            os.close(gate_write)
            gate_write = -1
            if await process.wait() != 0:
                raise DraftEditorError("External editor exited unsuccessfully; original draft preserved.")
            _authorize(authorize)
            await check_editor_control(deadline)
            result = _read_draft(path)
            await check_editor_control(deadline)
    except BaseException as error:
        primary = error

    async def cleanup() -> None:
        nonlocal process
        try:
            for descriptor in (gate_read, gate_write):
                if descriptor >= 0:
                    os.close(descriptor)
            if spawn is not None and process is None:
                try:
                    process = await asyncio.wait_for(asyncio.shield(spawn), _STOP_TIMEOUT)
                except TimeoutError:
                    spawn.cancel()
                    with suppress(asyncio.CancelledError):
                        process = await spawn
            if process is not None:
                from henchman.tools.subprocess_utils import _stop_subprocess

                await _stop_subprocess(process, owned_process_group=True)
        finally:
            try:
                try:
                    _foreground(terminal, foreground)
                finally:
                    termios.tcsetattr(terminal, termios.TCSANOW, attributes)
            finally:
                os.close(terminal)
                if temporary is not None:
                    temporary.cleanup()

    primary = await join_owned(asyncio.create_task(cleanup()), primary)
    if primary is not None:
        if not isinstance(primary, Exception):
            raise primary
        if isinstance(primary, DraftEditorError):
            raise primary from None
        raise DraftEditorError("External editor failed or exceeded its deadline; original draft preserved.") from None
    await check_editor_control(deadline)
    return result


def editor_session(frontend: Any) -> object:
    """Capture only the already selected session; never create runtime state."""
    context = getattr(frontend, "core_context", None)
    manager = getattr(context, "session_manager", None) or getattr(frontend, "session_manager", None)
    return getattr(manager, "current", None)


def editor_root(frontend: Any) -> Path:
    context = getattr(frontend, "core_context", None)
    return Path(getattr(context, "project_root", None) or getattr(frontend, "project_root", None) or Path.cwd())


@dataclass(frozen=True)
class DraftBinding:
    """An edit belongs to one selected runtime/session and physical project."""

    context: object
    manager: object
    session: object
    session_key: tuple[object, object]
    root: Path
    directories: tuple[tuple[Path, int, int], ...]

    @staticmethod
    def _directories(root: Path) -> tuple[tuple[Path, int, int], ...]:
        result = []
        for path in (root, *root.parents):
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
                raise DraftEditorError("External editor requires an unchanged physical project directory.")
            result.append((path, info.st_dev, info.st_ino))
        return tuple(result)

    @classmethod
    def capture(cls, frontend: Any) -> DraftBinding:
        require_editor_idle(frontend)
        context = getattr(frontend, "core_context", None)
        manager = getattr(context, "session_manager", None) or getattr(frontend, "session_manager", None)
        root = editor_root(frontend).absolute()
        try:
            directories = cls._directories(root)
        except OSError:
            raise DraftEditorError("External editor project directory is unavailable.") from None
        session = editor_session(frontend)
        return cls(context, manager, session, (getattr(session, "id", None), getattr(session, "project_hash", None)), root, directories)

    def check(self, frontend: Any) -> None:
        require_editor_idle(frontend)
        context = getattr(frontend, "core_context", None)
        manager = getattr(context, "session_manager", None) or getattr(frontend, "session_manager", None)
        try:
            valid = (context is self.context and manager is self.manager and editor_session(frontend) is self.session
                     and (getattr(self.session, "id", None), getattr(self.session, "project_hash", None)) == self.session_key
                     and editor_root(frontend).absolute() == self.root and self._directories(self.root) == self.directories)
        except OSError:
            valid = False
        if not valid:
            raise DraftEditorError("External editor project or selected session changed; original draft preserved.")


def require_editor_idle(frontend: Any) -> None:
    """Check existing local ownership and current policy without resolving agents."""
    from henchman.advanced.tasks import TaskService
    from henchman.cli.workflow import frontend_has_active_work
    from henchman.tools.registry import ToolRegistry

    context = getattr(frontend, "core_context", None)
    settings = getattr(context, "settings", None) or getattr(frontend, "settings", None)
    tools = getattr(settings, "tools", None)
    registry = getattr(context, "tool_registry", None) or getattr(frontend, "tool_registry", None)
    restricted = tools is not None and (tools.filesystem_read_roots is not None or tools.filesystem_write_roots is not None
        or tools.network_access != "unrestricted" or tools.network_allowed_hosts is not None or tools.sandbox != "none")
    if isinstance(registry, ToolRegistry):
        restricted = restricted or any(policy.restricted for policy in registry._effective_access_policies)
        restricted = restricted or registry._effective_plan_mode
    ready = getattr(frontend, "_chat_input_ready", None)
    if (restricted or frontend_has_active_work(frontend)
            or (isinstance(ready, asyncio.Event) and not ready.is_set())
            or TaskService.has_active_work(editor_root(frontend))
            or getattr(getattr(frontend, "_activity_state", None), "_closing", False)
            or getattr(getattr(frontend, "_tool_prompts", None), "_waiting", 0)):
        raise DraftEditorError("External editor requires idle work, no pending decision and unrestricted tool policy.")


if __name__ == "__main__":  # Isolated child: only stdlib, no application initialization.
    if len(sys.argv) < 5 or sys.argv[1] != "--exec":
        raise SystemExit(125)
    gate = int(sys.argv[2])
    permit = os.read(gate, 1)
    os.close(gate)
    if permit != b"g":
        raise SystemExit(125)
    try:
        os.execvpe(sys.argv[3], sys.argv[3:], dict(os.environ))
    except OSError:
        # Never print the command, draft path or executable's exception text.
        raise SystemExit(126) from None
