"""Git operations tool implementation.

Provides structured access to common git queries without requiring
the generic shell tool, enabling auto-approval for safe read operations.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from henchman.tools.base import Tool, ToolKind, ToolResult

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

MAX_OUTPUT_CHARS = 100_000


class GitOpsTool(Tool):
    """Run common git operations and return structured output.

    Consolidates frequent git queries (status, log, blame, show, etc.)
    into a single tool with action-based dispatch. Read-only actions are
    auto-approved; mutation actions require confirmation.
    """

    READ_ACTIONS = frozenset(
        {"status", "log", "blame", "show", "branch_list", "stash_list", "diff_branches"},
    )

    @property
    def name(self: GitOpsTool) -> str:
        """Tool name."""
        return "git_ops"

    @property
    def description(self: GitOpsTool) -> str:
        """Tool description."""
        return (
            "Run git operations: status, log, blame, show, branch_list, "
            "stash_list, diff_branches. Safer and faster than using shell "
            "for common git queries."
        )

    @property
    def parameters(self: GitOpsTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Git action to perform",
                    "enum": [
                        "status",
                        "log",
                        "blame",
                        "show",
                        "branch_list",
                        "stash_list",
                        "diff_branches",
                    ],
                },
                "path": {
                    "type": "string",
                    "description": "File path (for blame, log with path filter)",
                },
                "ref": {
                    "type": "string",
                    "description": "Git ref/commit (for show, log --since)",
                },
                "ref2": {
                    "type": "string",
                    "description": "Second ref (for diff_branches: ref..ref2)",
                },
                "max_count": {
                    "type": "integer",
                    "description": "Max entries for log (default: 20)",
                    "default": 20,
                },
                "start_line": {
                    "type": "integer",
                    "description": "Start line for blame range",
                },
                "end_line": {
                    "type": "integer",
                    "description": "End line for blame range",
                },
                "stat": {
                    "type": "boolean",
                    "description": "Show diffstat summary (for log, diff_branches)",
                    "default": False,
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory (defaults to current)",
                },
            },
            "required": ["action"],
        }

    @property
    def kind(self: GitOpsTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def _run_git(
        self: GitOpsTool, args: list[str], cwd: str | None = None,
    ) -> tuple[bool, str]:
        """Execute a git command and return (success, output).

        Args:
            args: Git subcommand and arguments.
            cwd: Working directory.

        Returns:
            Tuple of (success, output text).
        """
        cmd = ["git", "--no-pager", *args]
        create_subprocess_exec = asyncio.create_subprocess_exec
        PIPE = asyncio.subprocess.PIPE  # noqa: N806
        try:
            process = await create_subprocess_exec(
                *cmd,
                stdout=PIPE,
                stderr=PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30,
            )
            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")
            combined = (out + "\n" + err).strip()
        except FileNotFoundError:
            return False, "Error: git is not installed"
        except (TimeoutError, asyncio.TimeoutError):
            return False, "Error: git command timed out after 30s"
        else:
            return process.returncode == 0, combined

    async def execute(  # type: ignore[override]  # noqa: PLR0913
        self: GitOpsTool,
        action: str = "",
        path: str | None = None,
        ref: str | None = None,
        ref2: str | None = None,
        max_count: int = 20,
        start_line: int | None = None,
        end_line: int | None = None,
        stat: bool = False,  # noqa: FBT001, FBT002
        cwd: str | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Execute a git operation.

        Args:
            action: Git action to perform.
            path: File path for path-scoped actions.
            ref: Git ref or commit hash.
            ref2: Second ref for comparisons.
            max_count: Max entries for log.
            start_line: Start line for blame.
            end_line: End line for blame.
            stat: Show diffstat summary.
            cwd: Working directory.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with git output.
        """
        if not action:
            return ToolResult(
                content="Error: No action specified",
                success=False,
                error="Empty action",
            )

        if action not in self.READ_ACTIONS:
            return ToolResult(
                content=f"Error: Unknown action '{action}'",
                success=False,
                error=f"Unknown action: {action}",
            )

        from typing import Any  # noqa: PLC0415

        handler_map: dict[str, Callable[..., Coroutine[Any, Any, tuple[bool, str]]]] = {
            "status": self._status,
            "log": self._log,
            "blame": self._blame,
            "show": self._show,
            "branch_list": self._branch_list,
            "stash_list": self._stash_list,
            "diff_branches": self._diff_branches,
        }
        handler = handler_map[action]

        ok, output = await handler(
            path=path,
            ref=ref,
            ref2=ref2,
            max_count=max_count,
            start_line=start_line,
            end_line=end_line,
            stat=stat,
            cwd=cwd,
        )

        if len(output) > MAX_OUTPUT_CHARS:
            output = (
                output[:MAX_OUTPUT_CHARS]
                + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"
            )

        return ToolResult(content=output, success=ok, error=None if ok else output)

    async def _status(self: GitOpsTool, cwd: str | None = None, **_: object) -> tuple[bool, str]:
        """Get working tree status."""
        return await self._run_git(["status", "--short", "--branch"], cwd=cwd)

    async def _log(
        self: GitOpsTool,
        path: str | None = None,
        ref: str | None = None,
        max_count: int = 20,
        stat: bool = False,  # noqa: FBT001, FBT002
        cwd: str | None = None,
        **_: object,
    ) -> tuple[bool, str]:
        """Show commit log."""
        args = ["log", f"--max-count={max_count}", "--oneline"]
        if stat:
            args.append("--stat")
        if ref:
            args.append(ref)
        if path:
            args.extend(["--", path])
        return await self._run_git(args, cwd=cwd)

    async def _blame(
        self: GitOpsTool,
        path: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        cwd: str | None = None,
        **_: object,
    ) -> tuple[bool, str]:
        """Annotate file lines with commit info."""
        if not path:
            return False, "Error: 'path' is required for blame"
        args = ["blame"]
        if start_line is not None and end_line is not None:
            args.extend(["-L", f"{start_line},{end_line}"])
        args.append(path)
        return await self._run_git(args, cwd=cwd)

    async def _show(
        self: GitOpsTool,
        ref: str | None = None,
        path: str | None = None,
        stat: bool = False,  # noqa: FBT001, FBT002
        cwd: str | None = None,
        **_: object,
    ) -> tuple[bool, str]:
        """Show commit contents."""
        args = ["show"]
        if stat:
            args.append("--stat")
        target = ref or "HEAD"
        if path:
            args.append(f"{target} -- {path}")
        else:
            args.append(target)
        return await self._run_git(args, cwd=cwd)

    async def _branch_list(
        self: GitOpsTool, cwd: str | None = None, **_: object,
    ) -> tuple[bool, str]:
        """List branches."""
        return await self._run_git(["branch", "-a", "-v"], cwd=cwd)

    async def _stash_list(
        self: GitOpsTool, cwd: str | None = None, **_: object,
    ) -> tuple[bool, str]:
        """List stashes."""
        ok, output = await self._run_git(["stash", "list"], cwd=cwd)
        if ok and not output.strip():
            return True, "No stashes"
        return ok, output

    async def _diff_branches(
        self: GitOpsTool,
        ref: str | None = None,
        ref2: str | None = None,
        stat: bool = False,  # noqa: FBT001, FBT002
        path: str | None = None,
        cwd: str | None = None,
        **_: object,
    ) -> tuple[bool, str]:
        """Diff between two refs."""
        if not ref or not ref2:
            return False, "Error: 'ref' and 'ref2' are required for diff_branches"
        args = ["diff"]
        if stat:
            args.append("--stat")
        args.append(f"{ref}..{ref2}")
        if path:
            args.extend(["--", path])
        return await self._run_git(args, cwd=cwd)
