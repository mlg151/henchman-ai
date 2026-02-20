"""Shell tool implementation."""

import asyncio
import contextlib
import os

from henchman.tools.base import Tool, ToolKind, ToolResult


class ShellTool(Tool):
    """Execute shell commands.

    This tool executes shell commands and captures their output.
    It sets the HENCHMAN_CLI=1 environment variable for script detection.
    """

    # Safety limits
    MAX_OUTPUT_CHARS = 100_000

    def __init__(self, default_timeout: int = 3600) -> None:
        """Initialize the shell tool.

        Args:
            default_timeout: Default command timeout in seconds.
                Commands will be killed after this duration.
                Defaults to 3600 (1 hour).
        """
        self._default_timeout = default_timeout

    @property
    def name(self) -> str:
        """Tool name."""
        return "shell"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Execute a shell command and return its output. "
            "Long-running commands (builds, tests, data jobs) are fully "
            "supported — the tool will wait until the command completes."
        )

    @property
    def parameters(self) -> dict[str, object]:
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
            },
            "required": ["command"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    async def execute(  # type: ignore[override]
        self,
        command: str = "",
        timeout: int | None = None,
        cwd: str | None = None,
        **kwargs: object,  # noqa: ARG002
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
        effective_timeout: float | None = (
            self._default_timeout if timeout is None else (None if timeout == 0 else timeout)
        )
        try:
            # Set up environment with HENCHMAN_CLI marker
            env = {**os.environ, "HENCHMAN_CLI": "1"}

            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )

            # Create tasks to read stdout/stderr

            async def read_stream(stream: asyncio.StreamReader) -> str:
                """Read all data from a stream asynchronously.

                Args:
                    stream: The stream to read from.

                Returns:
                    The concatenated string output.
                """
                output = []
                while True:
                    chunk = await stream.read(64 * 1024)
                    if not chunk:
                        break
                    output.append(chunk.decode("utf-8", errors="replace"))

                return "".join(output)

            # We use a more robust approach than process.communicate()
            # We want to stop reading when the process exits, even if pipes are kept open
            # by grandchildren processes.

            stdout_data = []
            stderr_data = []

            async def read_stdout() -> None:
                """Read stdout from the process."""
                while True:
                    chunk = await process.stdout.read(64 * 1024)  # type: ignore[union-attr]
                    if not chunk:
                        break
                    stdout_data.append(chunk.decode("utf-8", errors="replace"))

            async def read_stderr() -> None:
                """Read stderr from the process."""
                while True:
                    chunk = await process.stderr.read(64 * 1024)  # type: ignore[union-attr]
                    if not chunk:
                        break
                    stderr_data.append(chunk.decode("utf-8", errors="replace"))

            stdout_task = asyncio.create_task(read_stdout())
            stderr_task = asyncio.create_task(read_stderr())

            # Polling loop to wait for process exit or timeout
            # We cannot use process.wait() directly because it hangs on open pipes from children.
            start_time = asyncio.get_running_loop().time()

            while True:
                # Check directly if process has exited (unlikely if pipes open)
                if process.returncode is not None:
                    break

                # Check timeout
                if effective_timeout and (
                    asyncio.get_running_loop().time() - start_time > effective_timeout
                ):
                    with contextlib.suppress(ProcessLookupError):
                        process.kill()
                    # If we kill it, we still need to wait() to reap it.
                    # Fall through to force close pipes if needed.
                    break

                # Check for zombie state (Linux specific optimization)
                is_dead = False
                try:
                    with open(f"/proc/{process.pid}/stat") as f:
                        if f.read().split()[2] == "Z":
                            is_dead = True
                except (FileNotFoundError, ProcessLookupError):
                    # Process gone completely
                    is_dead = True
                except Exception:
                    pass

                if is_dead:
                    # Process finished but wait() might hang on pipes.
                    # Break to force cleanup.
                    break

                await asyncio.sleep(0.1)

            # If we are here, process is either done, zombie, or timed out.

            # Try to let readers finish reading remaining output.
            # We do this BEFORE force closing pipes, because force closing pipes might
            # cause us to lose buffered data that hasn't been read yet.
            readers_finished = False
            try:
                await asyncio.wait_for(asyncio.gather(stdout_task, stderr_task), timeout=1.0)
                readers_finished = True
            except asyncio.TimeoutError:
                # Readers likely stuck on open pipes (grandchildren), we will close pipes below.
                pass
            except Exception:
                pass
            # Force close pipes to ensure wait() returns
            try:
                trans = process._transport  # type: ignore[attr-defined]
                if trans:
                    pipe_out = trans.get_pipe_transport(1)
                    if pipe_out:
                        pipe_out.close()
                    pipe_err = trans.get_pipe_transport(2)
                    if pipe_err:
                        pipe_err.close()
            except Exception:
                pass

            # Now wait() should return immediately
            try:
                # Use a small timeout just in case
                await asyncio.wait_for(process.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                # Should not happen if confirmed dead/zombie and pipes closed
                # But if it does, ensure process is dead
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                # We can't do much more than abandon it if wait() still hangs,
                # but with closed pipes it theoretically must return.

            # Cancel readers if they didn't finish
            if not readers_finished:
                stdout_task.cancel()
                stderr_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.gather(stdout_task, stderr_task)

            # Combine output
            stdout_text = "".join(stdout_data)
            stderr_text = "".join(stderr_data)

            output_parts = []
            if stdout_text:
                output_parts.append(stdout_text)
            if stderr_text:
                output_parts.append(stderr_text)

            output = "\n".join(output_parts)

            # Check if this was a timeout failure
            if effective_timeout and (
                asyncio.get_running_loop().time() - start_time > effective_timeout
            ):
                return ToolResult(
                    content=f"Command timed out after {effective_timeout} seconds. Partial output:\n{output}",
                    success=False,
                    error=f"Timeout after {effective_timeout} seconds",
                )

            # Truncate if too long
            if len(output) > self.MAX_OUTPUT_CHARS:
                output = (
                    output[: self.MAX_OUTPUT_CHARS]
                    + f"\n... (output truncated after {self.MAX_OUTPUT_CHARS} chars)"
                )

            return ToolResult(
                content=output if output else "(no output)",
                success=process.returncode == 0,
                error=f"Exit code: {process.returncode}" if process.returncode != 0 else None,
            )

        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error executing command: {e}",
                success=False,
                error=str(e),
            )
