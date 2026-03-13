"""Code format tool implementation."""

import asyncio
import sys
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult

_RUFF_TIMEOUT = 60
_TIMEOUT_ERRORS = (TimeoutError, asyncio.TimeoutError)

_CODE_FORMAT_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to Python file or directory to format",
        },
    },
    "required": ["path"],
}


async def _run_ruff_subprocess(
    ruff_args: list[str],
    timeout: int = _RUFF_TIMEOUT,
) -> tuple[int, bytes, bytes]:
    """Run a ruff subprocess and return (returncode, stdout, stderr).

    Args:
        ruff_args: Arguments to pass to ruff (e.g. ["format", path]).
        timeout: Timeout in seconds before the process is abandoned.

    Returns:
        Tuple of (returncode, stdout_bytes, stderr_bytes).
    """
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "ruff",
        *ruff_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    return proc.returncode or 0, stdout, stderr


async def _check_formatting_needed(path: str) -> tuple[bool, bytes]:
    """Check whether a path needs ruff formatting without modifying it.

    Args:
        path: File or directory path to check.

    Returns:
        Tuple of (needs_formatting, check_stderr_bytes).
    """
    rc, _stdout, stderr = await _run_ruff_subprocess(["format", "--check", path])
    return rc != 0, stderr


async def _format_and_report(path: str) -> ToolResult:
    """Apply ruff formatting and return a descriptive ToolResult.

    Args:
        path: File or directory path to format.

    Returns:
        ToolResult describing what changed.
    """
    needs_formatting, check_stderr = await _check_formatting_needed(path)
    if not needs_formatting:
        return ToolResult(
            content=f"Already formatted: {path}",
            success=True,
        )

    fmt_rc, fmt_stdout, fmt_stderr = await _run_ruff_subprocess(["format", path])
    if fmt_rc != 0:
        combined = (
            fmt_stdout.decode("utf-8", errors="replace")
            + "\n"
            + fmt_stderr.decode("utf-8", errors="replace")
        ).strip()
        return ToolResult(
            content=f"Formatting error:\n{combined}",
            success=False,
            error=combined,
        )

    changed_text = check_stderr.decode("utf-8", errors="replace").strip()
    if changed_text:
        return ToolResult(
            content=f"Formatted:\n{changed_text}",
            success=True,
        )
    return ToolResult(
        content=f"Formatted: {path}",
        success=True,
    )


class CodeFormatTool(Tool):
    """Run ruff format on Python files.

    Formats files in-place and reports what changed, eliminating
    the edit-lint-fix cycle for formatting issues.
    """

    @property
    def name(self: "CodeFormatTool") -> str:
        """Tool name."""
        return "code_format"

    @property
    def description(self: "CodeFormatTool") -> str:
        """Tool description."""
        return (
            "Run ruff format on a Python file or directory. Formats code "
            "in-place and reports whether changes were made."
        )

    @property
    def parameters(self: "CodeFormatTool") -> dict[str, object]:
        """JSON Schema for parameters."""
        return _CODE_FORMAT_PARAMETERS

    @property
    def kind(self: "CodeFormatTool") -> ToolKind:
        """Tool kind - WRITE modifies files."""
        return ToolKind.WRITE

    def _validate_path(self: "CodeFormatTool", path: str) -> "ToolResult | None":
        """Validate that path is non-empty and exists on disk.

        Args:
            path: Path string to validate.

        Returns:
            A ToolResult error if invalid, None if the path is usable.
        """
        if not path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )
        if not Path(path).exists():
            return ToolResult(
                content=f"Error: Path not found: {path}",
                success=False,
                error=f"Path not found: {path}",
            )
        return None

    async def execute(  # type: ignore[override]
        self: "CodeFormatTool",
        path: str = "",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Format Python files with ruff.

        Args:
            path: Path to file or directory.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult indicating what was formatted.
        """
        validation_error = self._validate_path(path)
        if validation_error:
            return validation_error
        try:
            return await _format_and_report(path)
        except FileNotFoundError:
            return ToolResult(
                content="Error: ruff is not installed",
                success=False,
                error="ruff not found",
            )
        except _TIMEOUT_ERRORS:
            return ToolResult(
                content=f"ruff format timed out after {_RUFF_TIMEOUT}s",
                success=False,
                error="Timeout",
            )
