"""Python code execution tool implementation."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from henchman.advanced.tasks import TaskService
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.utils import create_parameter_schema

# Safety limits
MAX_OUTPUT_CHARS = 100_000
DEFAULT_TIMEOUT_SECONDS = 30


@dataclass
class ExecRequest:
    """Parameters for a Python code execution request."""

    code: str
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    cwd: str | None = None


async def _run_python_subprocess(request: ExecRequest) -> ToolResult:
    """Launch a subprocess and return its captured output.

    Args:
        request: Execution parameters (code, timeout, working directory).

    Returns:
        ToolResult with stdout/stderr or error message.
    """
    effective_timeout: float | None = None if request.timeout == 0 else float(request.timeout)
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            request.code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=request.cwd,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return await _collect_process_output(process, effective_timeout, request.timeout)
    except Exception as exc:  # pragma: no cover
        return ToolResult(
            content=f"Error executing Python code: {exc}",
            success=False,
            error=str(exc),
        )


async def _collect_process_output(
    process: asyncio.subprocess.Process,
    effective_timeout: float | None,
    timeout_seconds: int,
) -> ToolResult:
    """Await process completion and collect stdout/stderr.

    Args:
        process: Running subprocess.
        effective_timeout: Timeout value in seconds, or None for no limit.
        timeout_seconds: Original timeout for error messages.

    Returns:
        ToolResult with formatted output or timeout error.
    """
    try:
        if effective_timeout is not None:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=effective_timeout,
            )
        else:
            stdout, stderr = await process.communicate()
    except TimeoutError:
        process.terminate()
        await process.wait()
        return ToolResult(
            content=f"Code timed out after {timeout_seconds} seconds",
            success=False,
            error=f"Timeout after {timeout_seconds}s",
        )
    except asyncio.CancelledError:
        process.terminate()
        await process.wait()
        raise

    return _format_process_output(process, stdout, stderr)


def _format_process_output(
    process: asyncio.subprocess.Process,
    stdout: bytes,
    stderr: bytes,
) -> ToolResult:
    """Format raw process output bytes into a ToolResult.

    Args:
        process: Completed subprocess (used for return code).
        stdout: Raw stdout bytes from the process.
        stderr: Raw stderr bytes from the process.

    Returns:
        ToolResult with decoded, possibly truncated output.
    """
    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")

    parts: list[str] = []
    if stdout_text:
        parts.append(stdout_text)
    if stderr_text:
        parts.append(stderr_text)

    output = "\n".join(parts) if parts else "(no output)"

    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"

    return ToolResult(
        content=output,
        success=process.returncode == 0,
        error=(f"Exit code: {process.returncode}" if process.returncode != 0 else None),
    )


class PythonExecTool(Tool):
    """Execute a Python code snippet in a sandboxed subprocess.

    Runs Python code using the current interpreter in a subprocess,
    capturing stdout and stderr.  Faster and safer than constructing
    ``shell`` + ``python -c "..."`` commands manually.
    """

    def __init__(self) -> None:
        """Initialize project binding without creating persistent task files."""
        self._project_root = Path.cwd()

    def bind_runtime(self, *, project_root: Path | None = None, **_: object) -> None:
        """Bind background jobs to the project's shared task registry."""
        if project_root is not None:
            self._project_root = project_root.resolve()

    @property
    def name(self: PythonExecTool) -> str:
        """Tool name."""
        return "python_exec"

    @property
    def description(self: PythonExecTool) -> str:
        """Tool description."""
        return (
            "Execute a Python code snippet in a subprocess using the current "
            "interpreter as a background task by default. Returns a task ID; use "
            "task_get, task_list, task_output and task_stop to track multiple jobs. "
            "Set background=false to wait for completion and return stdout/stderr."
        )

    @property
    def parameters(self: PythonExecTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return create_parameter_schema(
            required_params=["code"],
            optional_params={
                "code": {
                    "type": "string",
                    "description": "Python source to execute, not a shell command",
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        f"Execution timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})"
                    ),
                    "default": DEFAULT_TIMEOUT_SECONDS,
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory for execution",
                },
                "background": {
                    "type": "boolean",
                    "default": True,
                    "description": "Return a tracked background task; false waits for output.",
                },
            },
        )

    @property
    def kind(self: PythonExecTool) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    async def execute(  # type: ignore[override]
        self: PythonExecTool,
        code: str = "",
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        cwd: str | None = None,
        background: bool = True,
        **kwargs: object,
    ) -> ToolResult:
        """Execute Python code in a subprocess.

        Args:
            code: Python code to execute.
            timeout: Execution timeout in seconds.
            cwd: Working directory for execution.
            background: Return a tracked task immediately instead of awaiting completion.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with stdout/stderr or error.
        """
        if not code.strip():
            return ToolResult(
                content=(
                    "Error: No code provided. Supply Python source in the required code "
                    "argument, not shell syntax or a command argument. Set cwd separately "
                    "for the working directory. Use shell for shell commands only if allowed."
                ),
                success=False,
                error="Empty code",
            )
        if background:
            try:
                record = await TaskService(self._project_root).start_task(
                    argv=[sys.executable, "-u", "-c", code], cwd=cwd,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                    timeout=float(timeout) if timeout else None,
                    title="python_exec", metadata={"tool": "python_exec"},
                )
            except (OSError, ValueError) as exc:
                return ToolResult(content=f"Error executing Python code: {exc}",
                                  success=False, error=str(exc))
            return ToolResult(
                content=f"Started background task {record.task_id} [{record.status}]. "
                "Use task_get for status, task_output for output, task_list for all jobs, "
                "or task_stop to stop this task. Starting a task does not confirm success.",
            )
        request = ExecRequest(code=code, timeout=timeout, cwd=cwd)
        return await _run_python_subprocess(request)
