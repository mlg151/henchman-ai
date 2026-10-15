"""Diff view tool implementation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.utils import coerce_int

MAX_OUTPUT_CHARS = 100_000
_GIT_TIMEOUT_SECONDS = 30


@dataclass
class DiffParams:
    """Parameters for the diff view operation."""

    path: str | None = None
    staged: bool = False
    compare: str | None = None
    stat: bool = False
    name_only: bool = False
    context_lines: int | None = None
    cwd: str | None = None


def _build_diff_params_from_kwargs(kwargs: dict[str, object]) -> DiffParams:
    """Build a :class:`DiffParams` from raw ``**kwargs``."""
    raw_context = kwargs.get("context_lines")
    return DiffParams(
        path=str(kwargs["path"]) if kwargs.get("path") is not None else None,
        staged=bool(kwargs.get("staged", False)),
        compare=str(kwargs["compare"]) if kwargs.get("compare") is not None else None,
        stat=bool(kwargs.get("stat", False)),
        name_only=bool(kwargs.get("name_only", False)),
        context_lines=coerce_int(raw_context) if raw_context is not None else None,
        cwd=str(kwargs["cwd"]) if kwargs.get("cwd") is not None else None,
    )


def _build_diff_command(params: DiffParams) -> list[str]:
    """Build a git diff command from DiffParams."""
    cmd = ["git", "--no-pager", "diff"]
    if params.staged and not params.compare:
        cmd.append("--cached")
    if params.stat:
        cmd.append("--stat")
    if params.name_only:
        cmd.append("--name-only")
    if params.context_lines is not None:
        cmd.append(f"-U{params.context_lines}")
    if params.compare:
        cmd.append(params.compare)
    if params.path:
        cmd.extend(["--", params.path])
    return cmd


def _parse_git_output(
    stdout: bytes,
    stderr: bytes,
    returncode: int | None,
) -> ToolResult:
    """Parse git command output into a ToolResult."""
    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")

    if returncode != 0:
        return ToolResult(
            content=f"Error: {stderr_text.strip() or 'git diff failed'}",
            success=False,
            error=stderr_text.strip(),
        )

    if not stdout_text.strip():
        return ToolResult(content="No changes detected.", success=True)

    output = stdout_text
    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + f"\n... (truncated after {MAX_OUTPUT_CHARS} chars)"

    return ToolResult(content=output, success=True)


async def _run_git_command(
    cmd: list[str],
    cwd: str | None = None,
) -> ToolResult:
    """Execute a git command and return the result."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=_GIT_TIMEOUT_SECONDS,
        )
        return _parse_git_output(stdout, stderr, process.returncode)

    except FileNotFoundError:
        return ToolResult(
            content="Error: git is not installed",
            success=False,
            error="git not found",
        )
    except TimeoutError:
        return ToolResult(
            content=f"git diff timed out after {_GIT_TIMEOUT_SECONDS}s",
            success=False,
            error="Timeout",
        )


class DiffViewTool(Tool):
    """Show git diff of current changes or compare branches/refs."""

    @property
    def name(self: DiffViewTool) -> str:
        """Tool name."""
        return "diff_view"

    @property
    def description(self: DiffViewTool) -> str:
        """Tool description."""
        return (
            "Show git diff of current changes or compare branches/refs. "
            "Shows unstaged changes by default, staged with staged=true, "
            "or branch comparison with compare='main..feature'. "
            "Use stat=true for a summary of changed files."
        )

    @property
    def parameters(self: DiffViewTool) -> dict[str, object]:
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
    def kind(self: DiffViewTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(
        self: DiffViewTool,
        **kwargs: object,
    ) -> ToolResult:
        """Show git diff.

        Args:
            **kwargs: Diff parameters - path, staged, compare, stat,
                name_only, context_lines, cwd.

        Returns:
            ToolResult with diff output.
        """
        params = _build_diff_params_from_kwargs(kwargs)
        cmd = _build_diff_command(params)
        return await _run_git_command(cmd, cwd=params.cwd)

    def _build_command(self: DiffViewTool, params: DiffParams) -> list[str]:
        return _build_diff_command(params)

    async def _run_git(
        self: DiffViewTool,
        cmd: list[str],
        cwd: str | None = None,
    ) -> ToolResult:
        """Execute a git command and return the result."""
        return await _run_git_command(cmd, cwd=cwd)
