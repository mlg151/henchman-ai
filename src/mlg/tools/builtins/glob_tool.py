"""Glob tool implementation."""

from pathlib import Path

from mlg.tools.base import Tool, ToolKind, ToolResult


class GlobTool(Tool):
    """Find files matching a glob pattern.

    This tool searches for files matching a glob pattern
    in a directory and its subdirectories.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "glob"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Find files matching a glob pattern (e.g., '*.py', '**/*.txt')."

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
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
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]

        self,
        pattern: str = "",
        path: str = ".",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Find files matching glob pattern.

        Args:
            pattern: Glob pattern to match.
            path: Base path to search in.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with matching files or error.
        """
        try:
            base_path = Path(path)

            if not base_path.exists():
                return ToolResult(
                    content=f"Error: Path not found: {path}",
                    success=False,
                    error=f"Path not found: {path}",
                )

            # Find matching files
            matches = list(base_path.glob(pattern))

            if not matches:
                return ToolResult(
                    content="No matches found",
                    success=True,
                )

            # Format output
            results = []
            for match in sorted(matches):
                try:
                    rel_path = match.relative_to(base_path)
                    results.append(str(rel_path))
                except ValueError:  # pragma: no cover
                    results.append(str(match))

            return ToolResult(
                content="\n".join(results),
                success=True,
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error searching files: {e}",
                success=False,
                error=str(e),
            )
