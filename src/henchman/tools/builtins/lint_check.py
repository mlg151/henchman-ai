"""Lint check tool implementation."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.subprocess_utils import run_python_subprocess

MAX_OUTPUT_CHARS = 100_000

_LINT_TIMEOUT_SECONDS = 120
"""Timeout in seconds for individual linter commands."""


@dataclass
class LintParams:
    """Parameter object for lint check operations."""

    path: str
    linter: str = "both"
    fix: bool = False


async def _run_linter_command(cmd: list[str], label: str) -> tuple[bool, str]:
    """Run a linter command and return (success, formatted output).

    Args:
        cmd: Command to execute.
        label: Label for the output section header.

    Returns:
        Tuple of (success, formatted output).
    """
    try:
        stdout, stderr, returncode = await run_python_subprocess(
            cmd,
            timeout=_LINT_TIMEOUT_SECONDS,
        )
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        combined = (stdout_text + "\n" + stderr_text).strip()
        ok = returncode == 0
    except FileNotFoundError:
        return False, f"=== {label} ===\n{label} is not installed"
    except TimeoutError:
        return False, f"=== {label} ===\nTimed out after {_LINT_TIMEOUT_SECONDS}s"
    else:
        if ok and not combined:
            return True, f"=== {label} ===\nNo issues found \u2713"
        return ok, f"=== {label} ===\n{combined}"


async def _collect_lint_sections(params: LintParams) -> tuple[list[str], bool]:
    """Run the selected linters and collect their output sections.

    Args:
        params: Lint check parameters.

    Returns:
        Tuple of (sections, all_ok).
    """
    sections: list[str] = []
    all_ok = True

    if params.linter in ("ruff", "both"):
        ruff_cmd = [sys.executable, "-m", "ruff", "check"]
        if params.fix:
            ruff_cmd.append("--fix")
        ruff_cmd.extend(["--", params.path])
        label = "ruff --fix" if params.fix else "ruff"
        ok, output = await _run_linter_command(ruff_cmd, label)
        sections.append(output)
        if not ok:
            all_ok = False

    if params.linter in ("mypy", "both"):
        ok, output = await _run_linter_command(
            [sys.executable, "-m", "mypy", "--", params.path],
            "mypy",
        )
        sections.append(output)
        if not ok:
            all_ok = False

    return sections, all_ok


class LintCheckTool(Tool):
    """Run linters (ruff, mypy) on Python files and return structured diagnostics.

    Provides structured lint/type-check output for specific files,
    more targeted and readable than raw ``shell`` commands.
    Supports auto-fix mode via ``fix=True`` (runs ``ruff check --fix``).
    """

    @property
    def name(self: LintCheckTool) -> str:
        """Tool name."""
        return "lint_check"

    @property
    def description(self: LintCheckTool) -> str:
        """Tool description."""
        return (
            "Run ruff and/or mypy on a Python file or directory. "
            "Returns structured lint diagnostics. Use 'linter' to choose "
            "'ruff', 'mypy', or 'both' (default). Set 'fix' to auto-fix ruff issues."
        )

    @property
    def parameters(self: LintCheckTool) -> dict[str, object]:
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
                "fix": {
                    "type": "boolean",
                    "description": "Auto-fix safe ruff issues (runs ruff check --fix)",
                    "default": False,
                },
            },
            "required": ["path"],
        }

    @property
    def kind(self: LintCheckTool) -> ToolKind:
        """Tool kind - READ by default, but fix mode modifies files."""
        return ToolKind.READ

    def execution_kind(self, params: dict[str, object]) -> ToolKind:
        """Treat an explicit fix request as a source mutation."""
        return ToolKind.WRITE if params.get("fix") is True else self.kind

    def needs_confirmation(
        self: LintCheckTool,
        params: dict[str, object],
    ) -> ConfirmationRequest | None:
        """Require confirmation when fix mode is enabled.

        Args:
            params: The parameters being passed to the tool.

        Returns:
            ConfirmationRequest when fix=True, None otherwise.
        """
        if params.get("fix"):
            return ConfirmationRequest(
                tool_name=self.name,
                description=f"Auto-fix lint issues in {params.get('path', 'unknown')}",
                params=params,
                risk_level="medium",
            )
        return None

    async def _run_tool(
        self: LintCheckTool,
        cmd: list[str],
        label: str,
    ) -> tuple[bool, str]:
        """Run a linter command and return (success, output).

        Args:
            cmd: Command to execute.
            label: Label for the output section.

        Returns:
            Tuple of (success, formatted output).
        """
        return await _run_linter_command(cmd, label)

    async def execute(  # type: ignore[override]
        self: LintCheckTool,
        path: str = "",
        linter: str = "both",
        *,
        fix: bool = False,
        **kwargs: object,
    ) -> ToolResult:
        """Run lint checks on the given path.

        Args:
            path: Path to Python file or directory.
            linter: Which linter: 'ruff', 'mypy', or 'both'.
            fix: Auto-fix safe ruff issues.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with diagnostic output.
        """
        if linter not in ("ruff", "mypy", "both"):
            message = "Unsupported linter; choose 'ruff', 'mypy', or 'both'"
            return ToolResult(content=message, success=False, error=message)
        if not isinstance(fix, bool):
            message = "fix must be a boolean"
            return ToolResult(content=message, success=False, error=message)
        if not isinstance(path, str) or not path.strip():
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

        lint_params = LintParams(path=path, linter=linter, fix=fix)
        sections, all_ok = await _collect_lint_sections(lint_params)

        content = "\n\n".join(sections)
        if len(content) > MAX_OUTPUT_CHARS:
            content = (
                content[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
            )

        return ToolResult(
            content=content,
            success=all_ok,
            error=None if all_ok else "One or more requested lint checks failed",
        )
