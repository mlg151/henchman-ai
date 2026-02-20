"""Diff view tool implementation."""

import asyncio

from henchman.tools.base import Tool, ToolKind, ToolResult

MAX_OUTPUT_CHARS = 100_000


class DiffViewTool(Tool):
    """Show git diff of current changes.

    Displays working-tree or staged changes in a git repository,
    optionally filtered to a specific file.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "diff_view"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Show git diff of current changes. Shows unstaged changes by "
            "default, or staged changes with staged=true. Optionally filter "
            "to a specific file with 'path'."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Optional file path to limit diff to",
                },
                "staged": {
                    "type": "boolean",
                    "description": "Show staged changes (--cached)",
                    "default": False,
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (git repo root)",
                },
            },
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self,
        path: str | None = None,
        staged: bool = False,
        cwd: str | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Show git diff.

        Args:
            path: Optional file path to filter diff.
            staged: Show staged changes instead of unstaged.
            cwd: Working directory (must be a git repo).
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with diff output.
        """
        cmd = ["git", "--no-pager", "diff"]
        if staged:
            cmd.append("--cached")
        if path:
            cmd.extend(["--", path])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30,
            )
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            if process.returncode != 0:
                return ToolResult(
                    content=f"Error: {stderr_text.strip() or 'git diff failed'}",
                    success=False,
                    error=stderr_text.strip(),
                )

            if not stdout_text.strip():
                return ToolResult(
                    content="No changes detected.",
                    success=True,
                )

            output = stdout_text
            if len(output) > MAX_OUTPUT_CHARS:
                output = (
                    output[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
                )

            return ToolResult(content=output, success=True)

        except FileNotFoundError:
            return ToolResult(
                content="Error: git is not installed",
                success=False,
                error="git not found",
            )
        except (TimeoutError, asyncio.TimeoutError):
            return ToolResult(
                content="git diff timed out after 30s",
                success=False,
                error="Timeout",
            )
