"""Refactored shell tool with extracted classes for better maintainability.

This demonstrates the refactoring approach before applying it to the actual file.
"""

import asyncio
import contextlib
import errno
import fcntl
import os
import pty
import select
import sys
import termios
import tty
from dataclasses import dataclass
from typing import TYPE_CHECKING

from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_READ_CHUNK_SIZE = 64 * 1024
_POLL_INTERVAL = 0.1
_DRAIN_TIMEOUT = 1.0
_REAP_TIMEOUT = 1.0
_PTY_READ_SIZE = 1024
_DEFAULT_TIMEOUT = 3600
_MAX_OUTPUT_CHARS = 100_000


# ---------------------------------------------------------------------------
# Value Objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    """Result of running and waiting on a subprocess."""
    stdout: str
    stderr: str
    returncode: int | None
    timed_out: bool
    elapsed: float


@dataclass
class PtyDescriptor:
    """Encapsulates PTY file descriptor and its settings."""
    master_fd: int
    slave_fd: int
    old_termios_settings: list[int] | None = None

    def __enter__(self):
        """Set up PTY with non-blocking mode."""
        flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
        fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self.old_termios_settings = termios.tcgetattr(sys.stdin.fileno())
        tty.setraw(sys.stdin.fileno())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore terminal settings and close file descriptors."""
        if self.old_termios_settings:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self.old_termios_settings)
        os.close(self.master_fd)


# ---------------------------------------------------------------------------
# Helper Functions (Pure)
# ---------------------------------------------------------------------------
def resolve_timeout(explicit: int | None, default: int) -> float | None:
    """Translate timeout parameter into seconds or None."""
    if explicit is None:
        return float(default)
    return None if explicit == 0 else float(explicit)


def build_env() -> dict[str, str]:
    """Return environment dict with HENCHMAN_CLI marker set."""
    return {**os.environ, "HENCHMAN_CLI": "1"}


def is_sudo_command(command: str) -> bool:
    """Check whether command is a sudo invocation."""
    return command.strip().startswith("sudo ")


def format_output(stdout: str, stderr: str, max_chars: int = _MAX_OUTPUT_CHARS) -> str:
    """Combine and truncate stdout + stderr."""
    parts = [s for s in (stdout, stderr) if s]
    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n... (output truncated after {max_chars} chars)"
    return text or "(no output)"


def make_result(
    output: str,
    returncode: int | None,
    timed_out: bool,
    timeout_value: float | None,
) -> ToolResult:
    """Build final ToolResult from process outcome."""
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
# Async Subprocess Helpers
# ---------------------------------------------------------------------------
async def read_stream_into(stream: asyncio.StreamReader, accumulator: list[str]) -> None:
    """Read stream until EOF, appending decoded chunks to accumulator."""
    while True:
        chunk = await stream.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        accumulator.append(chunk.decode("utf-8", errors="replace"))


def is_process_dead(pid: int) -> bool:
    """Return True if pid is a zombie or no longer exists (Linux)."""
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().split()[2] == "Z"
    except (FileNotFoundError, ProcessLookupError):
        return True
    except Exception:  # noqa: BLE001
        return False


async def poll_until_exit(
    process: asyncio.subprocess.Process,
    timeout: float | None,
) -> tuple[bool, float]:
    """Poll process until it exits, becomes a zombie, or times out."""
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

        if is_process_dead(process.pid):
            return False, loop.time() - start

        await asyncio.sleep(_POLL_INTERVAL)


async def drain_readers(*tasks: asyncio.Task[None]) -> bool:
    """Give reader tasks a short window to finish consuming buffered data."""
    try:
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=_DRAIN_TIMEOUT)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        return False
    return True


def force_close_pipes(process: asyncio.subprocess.Process) -> None:
    """Close subprocess pipe transports so wait() can return."""
    try:
        trans = process._transport  # type: ignore[attr-defined]
        if trans is None:
            return
        for fd_num in (1, 2):
            pipe = trans.get_pipe_transport(fd_num)
            if pipe:
                pipe.close()
    except Exception:  # noqa: BLE001
        pass


async def reap_process(process: asyncio.subprocess.Process) -> None:
    """Wait for process to terminate after closing pipes."""
    try:
        await asyncio.wait_for(process.wait(), timeout=_REAP_TIMEOUT)
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        pass


async def cancel_tasks(*tasks: asyncio.Task[None]) -> None:
    """Cancel tasks and wait for cancellation."""
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


# ---------------------------------------------------------------------------
# PTY Manager Class
# ---------------------------------------------------------------------------
class PtyManager:
    """Manages PTY (pseudo-terminal) operations for interactive commands."""

    @staticmethod
    def create_pty() -> PtyDescriptor:
        """Create a new PTY pair."""
        master_fd, slave_fd = pty.openpty()
        os.setsid()
        return PtyDescriptor(master_fd=master_fd, slave_fd=slave_fd)

    @staticmethod
    def drain_pty(master_fd: int, accumulator: list[str]) -> None:
        """Read remaining data from PTY after process exits."""
        try:
            while True:
                chunk = os.read(master_fd, _PTY_READ_SIZE)
                if not chunk:
                    break
                accumulator.append(chunk.decode("utf-8", errors="replace"))
        except OSError:
            pass

    @staticmethod
    def handle_pty_io(
        master_fd: int,
        ready: list[object],
        accumulator: list[str],
    ) -> None:
        """Handle one iteration of PTY I/O (read output, forward input)."""
        if master_fd in ready:
            try:
                chunk = os.read(master_fd, _PTY_READ_SIZE)
                if chunk:
                    decoded = chunk.decode("utf-8", errors="replace")
                    accumulator.append(decoded)
                    sys.stdout.write(decoded)
                    sys.stdout.flush()
            except OSError as e:
                if e.errno != errno.EIO:
                    raise

        if sys.stdin in ready:
            try:
                chunk = os.read(sys.stdin.fileno(), _PTY_READ_SIZE)
                if chunk:
                    os.write(master_fd, chunk)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Interactive Loop Class
# ---------------------------------------------------------------------------
class InteractiveLoop:
    """Manages the interactive loop for PTY-based commands."""

    def __init__(self, pty_manager: PtyManager, timeout: float | None):
        self.pty_manager = pty_manager
        self.timeout = timeout
        self.output_data: list[str] = []
        self.start_time: float = 0.0

    async def run(
        self,
        process: asyncio.subprocess.Process,
        master_fd: int,
    ) -> str:
        """Run the interactive loop until process completes or times out."""
        self.start_time = asyncio.get_running_loop().time()

        with PtyDescriptor(master_fd, -1):  # Use PtyDescriptor as context manager
            while True:
                if self._check_timeout(process):
                    return self._format_result(timed_out=True)

                if process.returncode is not None:
                    self.pty_manager.drain_pty(master_fd, self.output_data)
                    break

                await self._process_pty_io(master_fd)

        await process.wait()
        return self._format_result(timed_out=False)

    def _check_timeout(self, process: asyncio.subprocess.Process) -> bool:
        """Check if command has timed out."""
        if self.timeout and (asyncio.get_running_loop().time() - self.start_time > self.timeout):
            process.kill()
            return True
        return False

    async def _process_pty_io(self, master_fd: int) -> None:
        """Process one iteration of PTY I/O."""
        rlist, _, _ = select.select(
            [master_fd, sys.stdin], [], [], _POLL_INTERVAL,
        )
        self.pty_manager.handle_pty_io(master_fd, rlist, self.output_data)

    def _format_result(self, timed_out: bool) -> str:
        """Format the final output result."""
        output = "".join(self.output_data)
        if len(output) > _MAX_OUTPUT_CHARS:
            output = (
                output[:_MAX_OUTPUT_CHARS]
                + f"\n... (output truncated after {_MAX_OUTPUT_CHARS} chars)"
            )
        return output if output else "(no output)"


# ---------------------------------------------------------------------------
# Shell Tool Class (Refactored)
# ---------------------------------------------------------------------------
class ShellTool(Tool):
    """Execute shell commands with improved structure."""

    MAX_OUTPUT_CHARS = _MAX_OUTPUT_CHARS

    def __init__(self, default_timeout: int = _DEFAULT_TIMEOUT) -> None:
        self._default_timeout = default_timeout
        self._pty_manager = PtyManager()

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return (
            "Execute a shell command and return its output. "
            "Long-running commands (builds, tests, data jobs) are fully "
            "supported — the tool will wait until the command completes."
        )

    @property
    def parameters(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
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
    def kind(self) -> ToolKind:
        return ToolKind.EXECUTE

    async def execute(
        self,
        command: str = "",
        timeout: int | None = None,
        cwd: str | None = None,
        **kwargs: object,
    ) -> ToolResult:
        """Execute shell command with refactored structure."""
        effective_timeout = resolve_timeout(timeout, self._default_timeout)

        try:
            env = build_env()
            interactive = kwargs.get("interactive", False)
            is_sudo = is_sudo_command(command)

            # Interactive sudo path (TTY required)
            if (interactive or is_sudo) and sys.stdin.isatty():
                return await self._execute_interactive_sudo(
                    command, env, cwd, effective_timeout,
                )

            # Create subprocess (with sudo fallback when no TTY)
            process = await self._create_process(command, env, cwd, is_sudo)

            # Run subprocess and collect output
            outcome = await self._run_and_collect(process, effective_timeout)

            output = format_output(outcome.stdout, outcome.stderr)
            return make_result(output, outcome.returncode, outcome.timed_out, effective_timeout)

        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error executing command: {e}",
                success=False,
                error=str(e),
            )

    async def _create_process(
        self,
        command: str,
        env: dict[str, str],
        cwd: str | None,
        is_sudo: bool,
    ) -> asyncio.subprocess.Process:
        """Create a subprocess for command."""
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
        self,
        process: asyncio.subprocess.Process,
        timeout: float | None,
    ) -> ProcessOutcome:
        """Drive process to completion and return captured output."""
        stdout_data: list[str] = []
        stderr_data: list[str] = []

        stdout_task = asyncio.create_task(
            read_stream_into(process.stdout, stdout_data),  # type: ignore[arg-type]
        )
        stderr_task = asyncio.create_task(
            read_stream_into(process.stderr, stderr_data),  # type: ignore[arg-type]
        )

        timed_out, elapsed = await poll_until_exit(process, timeout)

        # Let readers finish consuming any remaining buffered data
        readers_done = await drain_readers(stdout_task, stderr_task)

        force_close_pipes(process)
        await reap_process(process)

        if not readers_done:
            await cancel_tasks(stdout_task, stderr_task)

        return ProcessOutcome(
            stdout="".join(stdout_data),
            stderr="".join(stderr_data),
            returncode=process.returncode,
            timed_out=timed_out,
            elapsed=elapsed,
        )

    async def _execute_interactive_sudo(
        self,
        command: str,
        env: dict[str, str],
        cwd: str | None,
        timeout: float | None,
    ) -> ToolResult:
        """Execute a sudo command with interactive password input."""
        try:
            # Create PTY and process
            pty_desc = self._pty_manager.create_pty()

            process = await asyncio.create_subprocess_shell(
                command,
                stdin=pty_desc.slave_fd,
                stdout=pty_desc.slave_fd,
                stderr=pty_desc.slave_fd,
                env=env,
                cwd=cwd,
                start_new_session=True,
            )
            os.close(pty_desc.slave_fd)

            # Run interactive loop
            loop = InteractiveLoop(self._pty_manager, timeout)
            output = await loop.run(process, pty_desc.master_fd)

            return ToolResult(
                content=output,
                success=process.returncode == 0,
                error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
            )

        except Exception as e:
            return ToolResult(
                content=f"Error executing sudo command: {e}",
                success=False,
                error=str(e),
            )
