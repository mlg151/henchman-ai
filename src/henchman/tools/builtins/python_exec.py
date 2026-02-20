"""Python code execution tool implementation."""

import asyncio
import sys

from henchman.tools.base import Tool, ToolKind, ToolResult

# Safety limits
MAX_OUTPUT_CHARS = 100_000


class PythonExecTool(Tool):
    """Execute a Python code snippet in a sandboxed subprocess.

    Runs Python code using the current interpreter in a subprocess,
    capturing stdout and stderr.  Faster and safer than constructing
    ``shell`` + ``python -c "..."`` commands manually.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "python_exec"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Execute a Python code snippet in a subprocess using the current "
            "interpreter. Returns stdout/stderr. Useful for testing "
            "transformations, validating schemas, and quick REPL-style checks."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Execution timeout in seconds (default: 30)",
                    "default": 30,
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for execution",
                },
            },
            "required": ["code"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    async def execute(  # type: ignore[override]
        self,
        code: str = "",
        timeout: int = 30,
        cwd: str | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Execute Python code in a subprocess.

        Args:
            code: Python code to execute.
            timeout: Execution timeout in seconds.
            cwd: Working directory for execution.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with stdout/stderr or error.
        """
        if not code.strip():
            return ToolResult(
                content="Error: No code provided",
                success=False,
                error="Empty code",
            )

        effective_timeout: float | None = None if timeout == 0 else timeout

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

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
                    content=f"Code timed out after {timeout} seconds",
                    success=False,
                    error=f"Timeout after {timeout}s",
                )
            except asyncio.CancelledError:
                process.kill()
                await process.wait()
                raise

            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            parts = []
            if stdout_text:
                parts.append(stdout_text)
            if stderr_text:
                parts.append(stderr_text)

            output = "\n".join(parts) if parts else "(no output)"

            if len(output) > MAX_OUTPUT_CHARS:
                output = (
                    output[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
                )

            return ToolResult(
                content=output,
                success=process.returncode == 0,
                error=(f"Exit code: {process.returncode}" if process.returncode != 0 else None),
            )

        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error executing Python code: {e}",
                success=False,
                error=str(e),
            )
