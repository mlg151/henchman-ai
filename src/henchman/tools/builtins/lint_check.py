"""Lint check tool implementation."""

import asyncio
import sys
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult

MAX_OUTPUT_CHARS = 100_000


class LintCheckTool(Tool):
    """Run linters (ruff, mypy) on Python files and return structured diagnostics.

    Provides structured lint/type-check output for specific files,
    more targeted and readable than raw ``shell`` commands.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "lint_check"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Run ruff and/or mypy on a Python file or directory. "
            "Returns structured lint diagnostics. Use 'linter' parameter "
            "to run only 'ruff', only 'mypy', or 'both' (default)."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to a Python file or directory to lint",
                },
                "linter": {
                    "type": "string",
                    "description": ("Which linter to run: 'ruff', 'mypy', or 'both' (default)"),
                    "default": "both",
                    "enum": ["ruff", "mypy", "both"],
                },
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - READ, just reports diagnostics."""
        return ToolKind.READ

    async def _run_tool(self, cmd: list[str], label: str) -> tuple[bool, str]:
        """Run a linter command and return (success, output).

        Args:
            cmd: Command to execute.
            label: Label for the output section.

        Returns:
            Tuple of (success, formatted output).
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120,
            )
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")
            combined = (stdout_text + "\n" + stderr_text).strip()
            ok = process.returncode == 0
            if ok and not combined:
                return True, f"=== {label} ===\nNo issues found ✓"
            return ok, f"=== {label} ===\n{combined}"
        except FileNotFoundError:
            return False, f"=== {label} ===\n{label} is not installed"
        except (TimeoutError, asyncio.TimeoutError):
            return False, f"=== {label} ===\nTimed out after 120s"

    async def execute(  # type: ignore[override]
        self,
        path: str = "",
        linter: str = "both",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Run lint checks on the given path.

        Args:
            path: Path to Python file or directory.
            linter: Which linter: 'ruff', 'mypy', or 'both'.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with diagnostic output.
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

        sections: list[str] = []
        all_ok = True

        if linter in ("ruff", "both"):
            ok, output = await self._run_tool([sys.executable, "-m", "ruff", "check", path], "ruff")
            sections.append(output)
            if not ok:
                all_ok = False

        if linter in ("mypy", "both"):
            ok, output = await self._run_tool([sys.executable, "-m", "mypy", path], "mypy")
            sections.append(output)
            if not ok:
                all_ok = False

        content = "\n\n".join(sections)
        if len(content) > MAX_OUTPUT_CHARS:
            content = (
                content[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
            )

        return ToolResult(content=content, success=all_ok)
