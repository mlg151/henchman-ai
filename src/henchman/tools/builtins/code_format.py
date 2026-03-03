"""Code format tool implementation."""

import asyncio
import sys
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class CodeFormatTool(Tool):
    """Run ruff format on Python files.

    Formats files in-place and reports what changed, eliminating
    the edit-lint-fix cycle for formatting issues.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "code_format"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Run ruff format on a Python file or directory. Formats code "
            "in-place and reports whether changes were made."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to Python file or directory to format",
                },
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - WRITE modifies files."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]  # noqa: PLR0911
        self,
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
        if not path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )

        target = Path(path)
        if not target.exists():
            return ToolResult(
                content=f"Error: Path not found: {path}",
                success=False,
                error=f"Path not found: {path}",
            )

        create_subprocess_exec = asyncio.create_subprocess_exec
        PIPE = asyncio.subprocess.PIPE
        wait_for = asyncio.wait_for

        # First do a check to see what would change
        try:
            check_proc = await create_subprocess_exec(
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                path,
                stdout=PIPE,
                stderr=PIPE,
            )
            _check_stdout, check_stderr = await wait_for(
                check_proc.communicate(),
                timeout=60,
            )

            needs_formatting = check_proc.returncode != 0

            if not needs_formatting:
                return ToolResult(
                    content=f"Already formatted: {path}",
                    success=True,
                )

            # Apply formatting
            fmt_proc = await create_subprocess_exec(
                sys.executable,
                "-m",
                "ruff",
                "format",
                path,
                stdout=PIPE,
                stderr=PIPE,
            )
            fmt_stdout, fmt_stderr = await wait_for(
                fmt_proc.communicate(),
                timeout=60,
            )

            stdout_text = fmt_stdout.decode("utf-8", errors="replace")
            stderr_text = fmt_stderr.decode("utf-8", errors="replace")
            combined = (stdout_text + "\n" + stderr_text).strip()

            if fmt_proc.returncode != 0:
                return ToolResult(
                    content=f"Formatting error:\n{combined}",
                    success=False,
                    error=combined,
                )

            # Report what changed
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

        except FileNotFoundError:
            return ToolResult(
                content="Error: ruff is not installed",
                success=False,
                error="ruff not found",
            )
        except (TimeoutError, asyncio.TimeoutError):
            return ToolResult(
                content="ruff format timed out after 60s",
                success=False,
                error="Timeout",
            )
