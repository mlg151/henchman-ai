"""Shell tool implementation.

Executes shell commands with timeout support, output capture, and
optional interactive sudo via PTY forwarding.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import os
import select
import sys
from dataclasses import dataclass
from pathlib import Path

from henchman.advanced.tasks import TaskService
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.security import (
    CommandInjectionError,
    sanitize_command,
    sanitize_error_message,
)

# ---------------------------------------------------------------------------
# Constants - replace magic numbers with named values
# ---------------------------------------------------------------------------
_READ_CHUNK_SIZE = 64 * 1024
"""Bytes to read per chunk from subprocess pipes."""

_POLL_INTERVAL = 0.1
"""Seconds between process-alive polling iterations."""

_DRAIN_TIMEOUT = 1.0
"""Seconds to wait for pipe readers to finish after process exits."""

_REAP_TIMEOUT = 1.0
"""Seconds to wait for process.wait() after closing pipes."""

_PTY_READ_SIZE = 1024
"""Bytes to read per chunk from the PTY master fd."""

_DEFAULT_TIMEOUT = 3600
"""Default command timeout in seconds (1 hour)."""

_SUDO_PREFIX_LEN = 5
"""Length of 'sudo ' prefix to strip when rewriting sudo commands."""

MAX_OUTPUT_CHARS = 100_000
"""Maximum characters of combined stdout+stderr returned to the model."""

_SHELL_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": (
                "Shell command to execute on a single line; literal and escaped newlines "
                "are rejected."
            ),
        },
        "timeout": {
            "type": "integer",
            "description": (
                "Command timeout in seconds. Defaults to 3600 (1 hour). "
                "Use 0 for no timeout. Increase for long-running data "
                "transformation or build jobs."
            ),
        },
        "cwd": {
            "type": "string",
            "description": "Working directory for the command",
            "default": None,
        },
        "interactive": {
            "type": "boolean",
            "description": (
                "Enable interactive mode for sudo commands that require password input. "
                "Only works when running in TUI mode with a terminal."
            ),
            "default": False,
        },
        "background": {
            "type": "boolean",
            "default": True,
            "description": "Run as a tracked background task (default). Set false to await output.",
        },
    },
    "required": ["command"],
}


# ---------------------------------------------------------------------------
# Small value objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class _ProcessOutcome:
    """Intermediate result of running and waiting on a subprocess."""

    stdout: str
    stderr: str
    returncode: int | None
    timed_out: bool
    elapsed: float


@dataclass(frozen=True, slots=True)
class ShellParams:
    """Parameter object for shell execution - eliminates primitive obsession."""

    command: str
    env: dict[str, str]
    cwd: str | None
    timeout: float | None


# ---------------------------------------------------------------------------
# Pure helpers (no side effects, easy to test)
# ---------------------------------------------------------------------------
def _resolve_timeout(explicit: int | None, default: int) -> float | None:
    """Translate the user-facing *timeout* parameter into seconds or ``None``.

    Args:
        explicit: The timeout value passed by the caller.  ``None`` means
            "use the default"; ``0`` means "no timeout".
        default: The tool's default timeout in seconds.

    Returns:
        Effective timeout in seconds, or ``None`` for no limit.
    """
    if explicit is None:
        return float(default)
    return None if explicit == 0 else float(explicit)


def _build_env() -> dict[str, str]:
    """Return environment dict with the ``HENCHMAN_CLI`` marker set.

    Returns:
        A copy of the current environment with ``HENCHMAN_CLI=1``.
    """
    return {**os.environ, "HENCHMAN_CLI": "1"}


def _is_sudo_command(command: str) -> bool:
    """Check whether *command* is a ``sudo`` invocation.

    Args:
        command: The command string to check.

    Returns:
        ``True`` if the command starts with ``sudo ``.
    """
    return command.strip().startswith("sudo ")


def _format_output(stdout: str, stderr: str) -> str:
    """Combine and (optionally) truncate stdout + stderr.

    Args:
        stdout: Captured standard output.
        stderr: Captured standard error.

    Returns:
        A single string with both streams joined by a newline,
        truncated if above :data:`MAX_OUTPUT_CHARS`.
    """
    parts = [s for s in (stdout, stderr) if s]
    return _truncate_output("\n".join(parts))


def _truncate_output(text: str) -> str:
    """Truncate shell output to the configured limit."""
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n... (output truncated after {MAX_OUTPUT_CHARS} chars)"
    return text or "(no output)"


def _make_result(outcome: _ProcessOutcome, timeout_value: float | None) -> ToolResult:
    """Build the final :class:`ToolResult` from process outcome.

    Args:
        outcome: The completed process outcome including output and timing.
        timeout_value: The timeout that was in effect (for the error message).

    Returns:
        A populated :class:`ToolResult`.
    """
    output = _format_output(outcome.stdout, outcome.stderr)
    if outcome.timed_out:
        return ToolResult(
            content=f"Command timed out after {timeout_value} seconds. Partial output:\n{output}",
            success=False,
            error=f"Timeout after {timeout_value} seconds",
        )
    return ToolResult(
        content=output,
        success=outcome.returncode == 0,
        error=f"Exit code: {outcome.returncode}" if outcome.returncode != 0 else None,
    )


# ---------------------------------------------------------------------------
# Async subprocess helpers
# ---------------------------------------------------------------------------
async def _read_stream_into(
    stream: asyncio.StreamReader,
    accumulator: list[str],
) -> None:
    """Read *stream* until EOF, appending decoded chunks to *accumulator*.

    Args:
        stream: An :class:`asyncio.StreamReader` (stdout or stderr).
        accumulator: A mutable list that collects decoded text chunks.
    """
    while True:
        chunk = await stream.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        accumulator.append(chunk.decode("utf-8", errors="replace"))


async def _poll_until_exit(
    process: asyncio.subprocess.Process,
    timeout: float | None,
) -> tuple[bool, float]:
    """Poll *process* until it exits, becomes a zombie, or times out.

    We avoid ``process.wait()`` directly because it can hang when
    grandchild processes keep pipes open.

    Args:
        process: The subprocess to monitor.
        timeout: Maximum seconds to wait, or ``None`` for unlimited.

    Returns:
        A ``(timed_out, elapsed)`` tuple.
    """
    loop = asyncio.get_running_loop()
    start = loop.time()

    while True:
        if process.returncode is not None:
            return False, loop.time() - start

        elapsed = loop.time() - start
        if timeout is not None and elapsed > timeout:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            return True, elapsed

        # Linux-specific zombie check - avoids waiting on open pipes.
        if _is_process_dead(process.pid):
            return False, loop.time() - start

        await asyncio.sleep(_POLL_INTERVAL)


def _is_process_dead(pid: int) -> bool:
    """Return ``True`` if *pid* is a zombie or no longer exists (Linux).

    Args:
        pid: The process ID to check.

    Returns:
        ``True`` when Linux procfs proves the process has finished. Other
        platforms rely on the subprocess transport's return code.
    """
    if sys.platform != "linux" or not Path("/proc").is_dir():
        return False
    proc_stat_path = Path(f"/proc/{pid}/stat")
    try:
        with open(proc_stat_path) as fh:
            # The parenthesized process name can contain spaces and brackets.
            fields = fh.read().rpartition(")")[2].split()
            return bool(fields and fields[0] == "Z")
    except (FileNotFoundError, ProcessLookupError):
        return True
    except OSError:
        return False


async def _drain_readers(*tasks: asyncio.Task[None]) -> bool:
    """Give reader tasks a short window to finish consuming buffered data.

    Args:
        *tasks: The asyncio tasks reading stdout/stderr.

    Returns:
        ``True`` if all readers finished within :data:`_DRAIN_TIMEOUT`.
    """
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=_DRAIN_TIMEOUT,
        )
    except TimeoutError:
        return False
    return not any(isinstance(result, BaseException) for result in results)


def _force_close_pipes(process: asyncio.subprocess.Process) -> None:
    """Close subprocess pipe transports so ``wait()`` can return.

    Args:
        process: The subprocess whose pipes should be closed.
    """
    with contextlib.suppress(Exception):
        trans = getattr(process, "_transport", None)
        if trans is None:
            return
        for fd_num in (1, 2):
            pipe = trans.get_pipe_transport(fd_num)
            if pipe:
                pipe.close()


async def _reap_process(process: asyncio.subprocess.Process) -> None:
    """Wait for *process* to be reaped, killing it as a last resort.

    Args:
        process: The subprocess to reap.
    """
    try:
        await asyncio.wait_for(process.wait(), timeout=_REAP_TIMEOUT)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()


async def _cancel_tasks(*tasks: asyncio.Task[None]) -> None:
    """Cancel and await a set of tasks, suppressing :class:`CancelledError`.

    Args:
        *tasks: Tasks to cancel.
    """
    for t in tasks:
        t.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await asyncio.gather(*tasks)


async def _create_process(
    params: ShellParams,
    *,
    is_sudo: bool,
) -> asyncio.subprocess.Process:
    """Create a subprocess for *params.command*.

    For sudo commands without a TTY, the command is rewritten to use
    ``sudo -A`` with ``SUDO_ASKPASS=/bin/false`` so that passwordless
    sudo still works while interactive prompts fail fast.

    Args:
        params: Shell execution parameters.
        is_sudo: Whether the command is a sudo invocation.

    Returns:
        The created subprocess.
    """
    command = params.command
    env = params.env

    if is_sudo and sys.platform != "win32" and not sys.stdin.isatty():
        env = {**env, "SUDO_ASKPASS": "/bin/false"}
        command = f"sudo -A {command[_SUDO_PREFIX_LEN:]}"

    return await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=params.cwd,
    )


async def _run_and_collect(
    process: asyncio.subprocess.Process,
    timeout: float | None,
) -> _ProcessOutcome:
    """Drive *process* to completion and return captured output.

    Handles the full lifecycle: reading stdout/stderr in parallel,
    polling for exit, draining buffers, closing pipes, and reaping.

    Args:
        process: A running subprocess with piped stdout/stderr.
        timeout: Maximum seconds to wait, or ``None`` for unlimited.

    Returns:
        A :class:`_ProcessOutcome` with captured data.
    """
    stdout_data: list[str] = []
    stderr_data: list[str] = []

    stdout_task = asyncio.create_task(
        _read_stream_into(process.stdout, stdout_data),  # type: ignore[arg-type]
    )
    stderr_task = asyncio.create_task(
        _read_stream_into(process.stderr, stderr_data),  # type: ignore[arg-type]
    )

    timed_out, elapsed = await _poll_until_exit(process, timeout)

    readers_done = await _drain_readers(stdout_task, stderr_task)

    _force_close_pipes(process)
    await _reap_process(process)

    if not readers_done:
        await _cancel_tasks(stdout_task, stderr_task)

    return _ProcessOutcome(
        stdout="".join(stdout_data),
        stderr="".join(stderr_data),
        returncode=process.returncode,
        timed_out=timed_out,
        elapsed=elapsed,
    )


# ---------------------------------------------------------------------------
# PTY I/O helpers (keep interactive loop readable)
# ---------------------------------------------------------------------------
def _drain_pty(master_fd: int, accumulator: list[str]) -> None:
    """Read remaining data from the PTY after the process exits.

    Args:
        master_fd: File descriptor of the PTY master side.
        accumulator: List to append decoded output to.
    """
    try:
        while True:
            chunk = os.read(master_fd, _PTY_READ_SIZE)
            if not chunk:
                break
            accumulator.append(chunk.decode("utf-8", errors="replace"))
    except OSError:
        pass


def _handle_pty_read(master_fd: int, accumulator: list[str]) -> None:
    """Read one chunk from the PTY master and write it to stdout.

    Args:
        master_fd: File descriptor of the PTY master side.
        accumulator: List to append decoded output to.
    """
    try:
        chunk = os.read(master_fd, _PTY_READ_SIZE)
    except OSError as e:
        if e.errno != errno.EIO:
            raise
        return

    if not chunk:
        return

    decoded = chunk.decode("utf-8", errors="replace")
    accumulator.append(decoded)
    sys.stdout.write(decoded)
    sys.stdout.flush()


def _handle_pty_stdin_write(master_fd: int) -> None:
    """Forward one chunk from stdin to the PTY master.

    Args:
        master_fd: File descriptor of the PTY master side.
    """
    try:
        chunk = os.read(sys.stdin.fileno(), _PTY_READ_SIZE)
        if chunk:
            os.write(master_fd, chunk)
    except OSError:
        pass


def _handle_pty_io(master_fd: int, ready: list[object], accumulator: list[str]) -> None:
    """Handle one iteration of PTY I/O (read output, forward input).

    Args:
        master_fd: File descriptor of the PTY master side.
        ready: List of file descriptors/objects from ``select()``.
        accumulator: List to append decoded output to.
    """
    if master_fd in ready:
        _handle_pty_read(master_fd, accumulator)
    if sys.stdin in ready:
        _handle_pty_stdin_write(master_fd)


async def _create_pty_process(
    params: ShellParams,
    slave_fd: int,
) -> asyncio.subprocess.Process:
    """Create the subprocess attached to the PTY slave."""
    return await asyncio.create_subprocess_shell(
        params.command,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=params.env,
        cwd=params.cwd,
        start_new_session=True,
    )


def _configure_pty_master(master_fd: int) -> None:
    """Switch the PTY master into non-blocking mode."""
    import fcntl

    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def _build_timeout_result(timeout: float | None) -> ToolResult:
    """Build the timeout result for interactive sudo execution."""
    return ToolResult(
        content="Command timed out",
        success=False,
        error=f"Timeout after {timeout} seconds",
    )


def _is_pty_timed_out(params: ShellParams, start_time: float) -> bool:
    """Return whether the interactive command exceeded its timeout."""
    if not params.timeout:
        return False
    elapsed = asyncio.get_running_loop().time() - start_time
    return elapsed > params.timeout


async def _run_pty_event_loop(
    process: asyncio.subprocess.Process,
    master_fd: int,
    params: ShellParams,
    output_data: list[str],
) -> ToolResult | None:
    """Run the PTY event loop until the process exits or times out."""
    start_time = asyncio.get_running_loop().time()
    while True:
        if _is_pty_timed_out(params, start_time):
            process.kill()
            return _build_timeout_result(params.timeout)
        if process.returncode is not None:
            _drain_pty(master_fd, output_data)
            return None
        ready, _, _ = select.select(
            [master_fd, sys.stdin],
            [],
            [],
            _POLL_INTERVAL,
        )
        _handle_pty_io(master_fd, ready, output_data)


def _build_pty_result(
    process: asyncio.subprocess.Process,
    output_data: list[str],
) -> ToolResult:
    """Build the final PTY execution result."""
    output = _truncate_output("".join(output_data))
    return ToolResult(
        content=output,
        success=process.returncode == 0,
        error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
    )


async def _run_sudo_with_pty(params: ShellParams) -> ToolResult:
    """Execute a sudo command with interactive password input via PTY.

    Args:
        params: Shell execution parameters.

    Returns:
        ToolResult with command output or error.
    """
    try:
        import pty
        import termios
        import tty

        master_fd, slave_fd = pty.openpty()
        os.setsid()
        process = await _create_pty_process(params, slave_fd)
        os.close(slave_fd)
        _configure_pty_master(master_fd)

        stdin_fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(stdin_fd)

        try:
            tty.setraw(stdin_fd)
            output_data: list[str] = []
            timeout_result = await _run_pty_event_loop(process, master_fd, params, output_data)
            if timeout_result is not None:
                return timeout_result
            await process.wait()
            return _build_pty_result(process, output_data)

        finally:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_settings)
            os.close(master_fd)

    except Exception as e:  # noqa: BLE001
        return ToolResult(
            content=f"Error executing sudo command: {e}",
            success=False,
            error=str(e),
        )


# ---------------------------------------------------------------------------
# Main tool class
# ---------------------------------------------------------------------------
class ShellTool(Tool):
    """Execute shell commands.

    This tool executes shell commands and captures their output.
    It sets the ``HENCHMAN_CLI=1`` environment variable for script detection.

    For sudo commands, it supports interactive password input when run in TUI mode.
    """

    # Kept as a class attr for backward-compat (tests reference it).
    MAX_OUTPUT_CHARS = MAX_OUTPUT_CHARS

    def __init__(self: ShellTool, default_timeout: int = _DEFAULT_TIMEOUT) -> None:
        """Initialize the shell tool.

        Args:
            default_timeout: Default command timeout in seconds.
                Commands will be killed after this duration.
                Defaults to 3600 (1 hour).
        """
        self._default_timeout = default_timeout
        self._project_root = Path.cwd()

    def bind_runtime(self, *, project_root: Path | None = None, **_: object) -> None:
        """Bind background jobs to the project's shared task registry."""
        if project_root is not None:
            self._project_root = project_root.resolve()

    # -- public helpers exposed for tests ------------------------------------
    def _is_sudo_command(self: ShellTool, command: str) -> bool:
        """Check if a command is a sudo command.

        Args:
            command: The command string to check.

        Returns:
            True if the command starts with 'sudo ', False otherwise.
        """
        return _is_sudo_command(command)

    async def _execute_interactive_sudo(
        self: ShellTool,
        params: ShellParams,
    ) -> ToolResult:
        """Execute a sudo command interactively via PTY.

        Thin wrapper around the module-level :func:`_run_sudo_with_pty`
        preserved for backward-compatibility with tests that patch this method.

        Args:
            params: Shell execution parameters.

        Returns:
            ToolResult with command output or error.
        """
        return await _run_sudo_with_pty(params)

    async def _execute_params(
        self: ShellTool,
        params: ShellParams,
        *,
        interactive: object,
    ) -> ToolResult:
        """Execute already-sanitized shell parameters."""
        command = params.command
        timeout = params.timeout
        is_sudo = _is_sudo_command(command)
        if _should_use_interactive_mode(interactive, is_sudo=is_sudo):
            return await self._execute_interactive_sudo(params)
        process = await _create_process(params, is_sudo=is_sudo)
        outcome = await _run_and_collect(process, timeout)
        return _make_result(outcome, timeout)

    # -- Tool interface ------------------------------------------------------
    @property
    def name(self: ShellTool) -> str:
        """Tool name."""
        return "shell"

    @property
    def description(self: ShellTool) -> str:
        """Tool description."""
        return (
            "Execute a shell command as a background task by default and return its task ID. "
            "Use task_get, task_list, task_output and task_stop to track multiple long-running jobs. "
            "Set background=false to wait for completion and return output."
        )

    parameters = _SHELL_PARAMETERS

    @property
    def kind(self: ShellTool) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    # -- main entry point ----------------------------------------------------
    async def execute(  # type: ignore[override]
        self: ShellTool,
        command: str = "",
        timeout: int | None = None,
        cwd: str | None = None,
        background: bool = True,
        **kwargs: object,
    ) -> ToolResult:
        """Execute shell command.

        Args:
            command: Shell command to execute.
            timeout: Command timeout in seconds. None uses the default.
                0 means no timeout (wait indefinitely).
            cwd: Working directory for the command.
            background: Return a tracked task immediately instead of awaiting completion.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with command output or error.
        """
        # Validate and sanitize command
        try:
            sanitized_command = sanitize_command(command)
        except (CommandInjectionError, ValueError) as e:
            content = f"Security validation failed: {e}"
            if "control characters" in str(e) or "embedded newline" in str(e):
                content += (
                    " Commands must use a single line; literal and escaped newlines are rejected. "
                    "For multiline Python, use python_exec if allowed."
                )
            return ToolResult(
                content=content,
                success=False,
                error="Command validation failed",
            )

        params = ShellParams(
            command=sanitized_command,
            env=_build_env(),
            cwd=cwd,
            timeout=_resolve_timeout(timeout, self._default_timeout),
        )

        try:
            if background:
                if kwargs.get("interactive", False):
                    return ToolResult(
                        content="Interactive terminal input requires background=false.",
                        success=False,
                        error="Interactive background execution is unsupported",
                    )
                command = params.command
                if sys.platform != "win32" and _is_sudo_command(command):
                    command = f"sudo -A {command[_SUDO_PREFIX_LEN:]}"
                record = await TaskService(self._project_root).start_task(
                    argv=[command], shell=True, cwd=params.cwd, env=params.env,
                    timeout=params.timeout, title="shell", metadata={"tool": "shell"},
                )
                return ToolResult(
                    content=f"Started background task {record.task_id} [{record.status}]. "
                    "Use task_get for status, task_output for output, task_list for all jobs, "
                    "or task_stop to stop this task. Starting a task does not confirm success.",
                )
            return await self._execute_params(
                params,
                interactive=kwargs.get("interactive", False),
            )
        except Exception as e:  # noqa: BLE001  # pragma: no cover
            sanitized_error = sanitize_error_message(e)
            return ToolResult(
                content=f"Error executing command: {sanitized_error}",
                success=False,
                error=sanitized_error,
            )


def _should_use_interactive_mode(interactive: object, *, is_sudo: bool) -> bool:
    """Return whether command execution should use the PTY path."""
    return sys.platform != "win32" and bool(interactive or is_sudo) and sys.stdin.isatty()
