"""Shell tool implementation."""

import asyncio
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

            # Wait for completion with timeout
            try:
                if effective_timeout is not None:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=effective_timeout,
                    )
                else:
                    stdout, stderr = await process.communicate()
            except (TimeoutError, asyncio.TimeoutError):
                process.kill()
                await process.wait()
                return ToolResult(
                    content=f"Command timed out after {effective_timeout} seconds",
                    success=False,
                    error=f"Timeout after {effective_timeout} seconds",
                )
            except asyncio.CancelledError:
                process.kill()
                await process.wait()
                raise

            # Decode output
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            # Combine output
            output_parts = []
            if stdout_text:
                output_parts.append(stdout_text)
            if stderr_text:
                output_parts.append(stderr_text)

            output = "\n".join(output_parts)

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
