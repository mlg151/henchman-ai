"""Diff view tool implementation."""

import asyncio

from henchman.tools.base import Tool, ToolKind, ToolResult

MAX_OUTPUT_CHARS = 100_000


class DiffViewTool(Tool):
    """Show git diff of current changes or compare branches/refs.

    Displays working-tree, staged, or branch-comparison diffs in a git
    repository, optionally filtered to a specific file.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "diff_view"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Show git diff of current changes or compare branches/refs. "
            "Shows unstaged changes by default, staged with staged=true, "
            "or branch comparison with compare='main..feature'. "
            "Use stat=true for a summary of changed files."
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
                "compare": {
                    "type": "string",
                    "description": (
                        "Compare two refs, e.g. 'main..feature' or 'HEAD~3..HEAD'"
                    ),
                },
                "stat": {
                    "type": "boolean",
                    "description": "Show --stat summary (files changed, insertions, deletions)",
                    "default": False,
                },
                "name_only": {
                    "type": "boolean",
                    "description": "Show only names of changed files",
                    "default": False,
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines around changes (default 3)",
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
        compare: str | None = None,
        stat: bool = False,
        name_only: bool = False,
        context_lines: int | None = None,
        cwd: str | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Show git diff.

        Args:
            path: Optional file path to filter diff.
            staged: Show staged changes instead of unstaged.
            compare: Compare two refs (e.g. 'main..feature').
            stat: Show --stat summary instead of full diff.
            name_only: Show only changed file names.
            context_lines: Number of context lines (git -U flag).
            cwd: Working directory (must be a git repo).
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with diff output.
        """
        cmd = self._build_command(
            path=path,
            staged=staged,
            compare=compare,
            stat=stat,
            name_only=name_only,
            context_lines=context_lines,
        )
        return await self._run_git(cmd, cwd=cwd)

    def _build_command(
        self,
        *,
        path: str | None,
        staged: bool,
        compare: str | None,
        stat: bool,
        name_only: bool,
        context_lines: int | None,
    ) -> list[str]:
        """Build the git diff command.

        Args:
            path: Optional file path filter.
            staged: Use --cached for staged changes.
            compare: Ref comparison spec (e.g. 'main..feature').
            stat: Use --stat for summary.
            name_only: Use --name-only for file list.
            context_lines: Number of context lines.

        Returns:
            Command as list of strings.
        """
        cmd = ["git", "--no-pager", "diff"]
        if staged and not compare:
            cmd.append("--cached")
        if stat:
            cmd.append("--stat")
        if name_only:
            cmd.append("--name-only")
        if context_lines is not None:
            cmd.append(f"-U{context_lines}")
        if compare:
            cmd.append(compare)
        if path:
            cmd.extend(["--", path])
        return cmd

    async def _run_git(
        self,
        cmd: list[str],
        cwd: str | None = None,
    ) -> ToolResult:
        """Execute a git command and return the result.

        Args:
            cmd: Command to execute.
            cwd: Working directory.

        Returns:
            ToolResult with command output.
        """
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
                    output[:MAX_OUTPUT_CHARS]
                    + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
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
