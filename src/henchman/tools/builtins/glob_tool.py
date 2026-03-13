"""Glob tool implementation."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from henchman.tools.base import Tool, ToolKind, ToolResult

# Safety limit: maximum number of matches to return.
_MAX_MATCHES = 1000


def _collect_glob_matches(
    base_path: Path,
    pattern: str,
    max_count: int,
) -> tuple[list[Path], bool]:
    """Collect up to *max_count* paths matching *pattern* under *base_path*.

    Returns:
        Tuple of (matches, truncated).
    """
    matches_iter = base_path.glob(pattern)  # noqa: ASYNC240
    matches: list[Path] = []
    try:
        for _ in range(max_count + 1):
            matches.append(next(matches_iter))  # noqa: PERF401
    except StopIteration:
        pass

    if len(matches) > max_count:
        return matches[:max_count], True
    return matches, False


def _format_glob_results(
    matches: list[Path],
    base_path: Path,
    truncated: bool,
    max_count: int,
) -> str:
    """Format matched paths as a newline-separated string."""
    results: list[str] = []
    for match in sorted(matches):
        try:
            rel_path = match.relative_to(base_path)
            results.append(str(rel_path))
        except ValueError:  # pragma: no cover
            results.append(str(match))

    if truncated:
        results.append(
            f"... Output truncated (limit reached: {max_count} matches) ...",
        )
    return "\n".join(results)


class GlobTool(Tool):
    """Find files matching a glob pattern."""

    _glob_tool_parameters: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match (e.g., '*.py', '**/*.txt')",
            },
            "path": {
                "type": "string",
                "description": "Base path to search in. Defaults to current directory.",
                "default": ".",
            },
        },
        "required": ["pattern"],
    }

    @property
    def name(self: GlobTool) -> str:
        """Tool name."""
        return "glob"

    @property
    def description(self: GlobTool) -> str:
        """Tool description."""
        return "Find files matching a glob pattern (e.g., '*.py', '**/*.txt')."

    @property
    def parameters(self: GlobTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return self._glob_tool_parameters

    @property
    def kind(self: GlobTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: GlobTool,
        pattern: str = "",
        path: str = ".",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Find files matching glob pattern.

        Args:
            pattern: Glob pattern to match (e.g., '*.py', '**/*.txt').
            path: Base path to search in. Defaults to current directory.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with matched files or error message.
        """
        try:
            base_path = Path(path)

            if not base_path.exists():  # noqa: ASYNC240
                return ToolResult(
                    content=f"Error: Path not found: {path}",
                    success=False,
                    error=f"Path not found: {path}",
                )

            matches, truncated = _collect_glob_matches(base_path, pattern, _MAX_MATCHES)

            if not matches:
                return ToolResult(
                    content="No matches found",
                    success=True,
                )

            content = _format_glob_results(matches, base_path, truncated, _MAX_MATCHES)
            return ToolResult(content=content, success=True)

        except Exception as e:  # pragma: no cover  # noqa: BLE001
            return ToolResult(
                content=f"Error searching files: {e}",
                success=False,
                error=str(e),
            )
