"""Shell tool implementation.

Executes shell commands with timeout support, output capture, and
optional interactive sudo via PTY forwarding.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import termios
import tty
from dataclasses import dataclass

from henchman.tools.base import Tool, ToolKind, ToolResult

# ---------------------------------------------------------------------------
# Constants – replace magic numbers with named values  # noqa: RUF003
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

MAX_OUTPUT_CHARS = 100_000
"""Maximum characters of combined stdout+stderr returned to the model."""


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
    text = "\n".join(parts)
    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n... (output truncated after {MAX_OUTPUT_CHARS} chars)"
    return text or "(no output)"


def _make_result(
    output: str,
    returncode: int | None,
    timed_out: bool,  # noqa: FBT001
    timeout_value: float | None,
) -> ToolResult:
    """Build the final :class:`ToolResult` from process outcome.

    Args:
        output: Combined, possibly truncated output string.
        returncode: Process exit code (``None`` if not reaped).
        timed_out: Whether the command exceeded its timeout.
        timeout_value: The timeout that was in effect (for the error message).

    Returns:
        A populated :class:`ToolResult`.
    """
    if timed_out:
        return ToolResult(
            content=f"Command timed out after {timeout_value} seconds. Partial output:\n{output}",
            success=False,
            error=f"Timeout after {timeout_value} seconds",
        )
    return ToolResult(
        content=output,
        success=returncode == 0,
        error=f"Exit code: {returncode}" if returncode != 0 else None,
    )


# ---------------------------------------------------------------------------
# Async subprocess helpers
# ---------------------------------------------------------------------------
async def _read_stream_into(stream: asyncio.StreamReader, accumulator: list[str]) -> None:
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

        # Linux-specific zombie check – avoids waiting on open pipes.  # noqa: RUF003
        if _is_process_dead(process.pid):
            return False, loop.time() - start

        await asyncio.sleep(_POLL_INTERVAL)


def _is_process_dead(pid: int) -> bool:
    """Return ``True`` if *pid* is a zombie or no longer exists (Linux).

    Args:
        pid: The process ID to check.

    Returns:
        ``True`` when the process can be considered finished.
    """
    try:
        with open(f"/proc/{pid}/stat") as fh:  # noqa: PTH123
            return fh.read().split()[2] == "Z"
    except (FileNotFoundError, ProcessLookupError):
        return True
    except Exception:  # noqa: BLE001
        return False


async def _drain_readers(*tasks: asyncio.Task[None]) -> bool:
    """Give reader tasks a short window to finish consuming buffered data.

    Args:
        *tasks: The asyncio tasks reading stdout/stderr.

    Returns:
        ``True`` if all readers finished within :data:`_DRAIN_TIMEOUT`.
    """
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=_DRAIN_TIMEOUT)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        return False
    return True


def _force_close_pipes(process: asyncio.subprocess.Process) -> None:
    """Close subprocess pipe transports so ``wait()`` can return.

    Args:
        process: The subprocess whose pipes should be closed.
    """
    try:
        trans = process._transport  # type: ignore[attr-defined]  # noqa: SLF001
        if trans is None:
            return
        for fd_num in (1, 2):
            pipe = trans.get_pipe_transport(fd_num)
            if pipe:
                pipe.close()
    except Exception:  # noqa: BLE001
        pass


async def _reap_process(process: asyncio.subprocess.Process) -> None:
    """Wait for *process* to be reaped, killing it as a last resort.

    Args:
        process: The subprocess to reap.
    """
    try:
        await asyncio.wait_for(process.wait(), timeout=_REAP_TIMEOUT)
    except asyncio.TimeoutError:
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

    # -- public helpers exposed for tests ------------------------------------
    def _is_sudo_command(self: ShellTool, command: str) -> bool:
        """Check if a command is a sudo command.

        Args:
            command: The command string to check.

        Returns:
            True if the command starts with 'sudo ', False otherwise.
        """
        return _is_sudo_command(command)

    # -- Tool interface ------------------------------------------------------
    @property
    def name(self: ShellTool) -> str:
        """Tool name."""
        return "shell"

    @property
    def description(self: ShellTool) -> str:
        """Tool description."""
        return (
            "Execute a shell command and return its output. "
            "Long-running commands (builds, tests, data jobs) are fully "
            "supported — the tool will wait until the command completes."
        )

    @property
    def parameters(self: ShellTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
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
            },
            "required": ["command"],
        }

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
        **kwargs: object,
    ) -> ToolResult:
        """Execute shell command.

        Args:
            command: Shell command to execute.
            timeout: Command timeout in seconds. None uses the default.
                0 means no timeout (wait indefinitely).
            cwd: Working directory for the command.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with command output or error.
        """
        effective_timeout = _resolve_timeout(timeout, self._default_timeout)

        try:
            env = _build_env()
            interactive = kwargs.get("interactive", False)
            is_sudo = _is_sudo_command(command)

            # Interactive sudo path (TTY required)
            if (interactive or is_sudo) and sys.stdin.isatty():
                return await self._execute_interactive_sudo(
                    command, env, cwd, effective_timeout,
                )

            # Create subprocess (with sudo fallback when no TTY)
            process = await self._create_process(command, env, cwd, is_sudo)

            # Run subprocess and collect output
            outcome = await self._run_and_collect(process, effective_timeout)

            output = _format_output(outcome.stdout, outcome.stderr)
            return _make_result(output, outcome.returncode, outcome.timed_out, effective_timeout)

        except Exception as e:  # pragma: no cover  # noqa: BLE001
            return ToolResult(
                content=f"Error executing command: {e}",
                success=False,
                error=str(e),
            )

    # -- private orchestration -----------------------------------------------
    async def _create_process(
        self: ShellTool,
        command: str,
        env: dict[str, str],
        cwd: str | None,
        is_sudo: bool,  # noqa: FBT001
    ) -> asyncio.subprocess.Process:
        """Create a subprocess for *command*.

        For sudo commands without a TTY, the command is rewritten to use
        ``sudo -A`` with ``SUDO_ASKPASS=/bin/false`` so that passwordless
        sudo still works while interactive prompts fail fast.

        Args:
            command: The shell command.
            env: Environment variables.
            cwd: Working directory.
            is_sudo: Whether the command is a sudo invocation.

        Returns:
            The created subprocess.
        """
        if is_sudo and not sys.stdin.isatty():
            env = {**env, "SUDO_ASKPASS": "/bin/false"}
            command = f"sudo -A {command[5:]}"

        return await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )

    async def _run_and_collect(
        self: ShellTool,
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

        # Let readers finish consuming any remaining buffered data.
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

    # -- interactive sudo via PTY -------------------------------------------
    async def _execute_interactive_sudo(
        self: ShellTool,
        command: str,
        env: dict[str, str],
        cwd: str | None,
        timeout: float | None,
    ) -> ToolResult:
        """Execute a sudo command with interactive password input.

        This method handles sudo commands that require password input by:
        1. Allocating a pseudo-terminal (PTY) for the subprocess
        2. Forwarding user input from stdin to the subprocess
        3. Capturing output from the subprocess

        Args:
            command: The sudo command to execute.
            env: Environment variables for the subprocess.
            cwd: Working directory for the command.
            timeout: Command timeout in seconds.

        Returns:
            ToolResult with command output or error.
        """
        import errno  # noqa: PLC0415
        import fcntl  # noqa: PLC0415
        import pty  # noqa: PLC0415
        import select  # noqa: PLC0415

        try:
            master_fd, slave_fd = pty.openpty()
            os.setsid()

            process = await asyncio.create_subprocess_shell(
                command,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                cwd=cwd,
                start_new_session=True,
            )
            os.close(slave_fd)

            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            old_settings = termios.tcgetattr(sys.stdin.fileno())

            try:
                tty.setraw(sys.stdin.fileno())
                output_data: list[str] = []
                start_time = asyncio.get_running_loop().time()

                while True:
                    if timeout and (asyncio.get_running_loop().time() - start_time > timeout):
                        process.kill()
                        return ToolResult(
                            content="Command timed out",
                            success=False,
                            error=f"Timeout after {timeout} seconds",
                        )

                    if process.returncode is not None:
                        self._drain_pty(master_fd, output_data)
                        break

                    rlist, _, _ = select.select(
                        [master_fd, sys.stdin], [], [], _POLL_INTERVAL,
                    )
                    self._handle_pty_io(master_fd, rlist, output_data, errno)

                await process.wait()

                output = "".join(output_data)
                if len(output) > MAX_OUTPUT_CHARS:
                    output = (
                        output[:MAX_OUTPUT_CHARS]
                        + f"\n... (output truncated after {MAX_OUTPUT_CHARS} chars)"
                    )

                return ToolResult(
                    content=output or "(no output)",
                    success=process.returncode == 0,
                    error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
                )

            finally:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                os.close(master_fd)

        except Exception as e:  # noqa: BLE001
            return ToolResult(
                content=f"Error executing sudo command: {e}",
                success=False,
                error=str(e),
            )

    # -- PTY I/O helpers (keep interactive loop readable) --------------------
    @staticmethod
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

    @staticmethod
    def _handle_pty_io(
        master_fd: int,
        ready: list[object],
        accumulator: list[str],
        errno_mod: object,
    ) -> None:
        """Handle one iteration of PTY I/O (read output, forward input).

        Args:
            master_fd: File descriptor of the PTY master side.
            ready: List of file descriptors/objects from ``select()``.
            accumulator: List to append decoded output to.
            errno_mod: The ``errno`` module (passed to avoid re-importing).
        """
        if master_fd in ready:
            try:
                chunk = os.read(master_fd, _PTY_READ_SIZE)
                if chunk:
                    decoded = chunk.decode("utf-8", errors="replace")
                    accumulator.append(decoded)
                    sys.stdout.write(decoded)
                    sys.stdout.flush()
            except OSError as e:
                if e.errno != errno_mod.EIO:  # type: ignore[attr-defined]
                    raise

        if sys.stdin in ready:
            try:
                chunk = os.read(sys.stdin.fileno(), _PTY_READ_SIZE)
                if chunk:
                    os.write(master_fd, chunk)
            except OSError:
                pass
