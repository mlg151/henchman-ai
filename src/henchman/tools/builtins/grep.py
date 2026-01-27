"""Grep tool implementation."""

import re
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class GrepTool(Tool):
    """Search for text patterns in files.

    This tool searches for text or regex patterns in files,
    similar to the grep command.
    """

    # Safety limits
    MAX_MATCHES = 1000
    MAX_OUTPUT_CHARS = 100_000

    @property
    def name(self) -> str:
        """Tool name."""
        return "grep"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Search for text patterns in files using regex."

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in",
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case insensitive search",
                    "default": False,
                },
                "line_numbers": {
                    "type": "boolean",
                    "description": "Include line numbers in output",
                    "default": False,
                },
                "glob": {
                    "type": "string",
                    "description": "File glob pattern to filter files (e.g., '*.py')",
                    "default": None,
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
        ignore_case: bool = False,
        line_numbers: bool = False,
        glob: str | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Search for pattern in files.

        Args:
            pattern: Text or regex pattern to search for.
            path: File or directory to search in.
            ignore_case: Case insensitive search.
            line_numbers: Include line numbers in output.
            glob: File glob pattern to filter files.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with matching lines or error.
        """
        try:
            target = Path(path)

            if not target.exists():
                return ToolResult(
                    content=f"Error: Path not found: {path}",
                    success=False,
                    error=f"Path not found: {path}",
                )

            # Compile regex
            flags = re.IGNORECASE if ignore_case else 0
            try:
                regex = re.compile(pattern, flags)
            except re.error as e:
                return ToolResult(
                    content=f"Error: Invalid regex pattern: {e}",
                    success=False,
                    error=f"Invalid regex: {e}",
                )

            # Collect files to search
            if target.is_file():
                files = [target]
            else:
                if glob:
                    files = list(target.glob(glob))
                else:
                    files = [f for f in target.rglob("*") if f.is_file()]

            # Search files
            results = []
            total_chars = 0
            truncated = False

            for file_path in files:
                if truncated:
                    break
                try:
                    content = file_path.read_text()
                    lines = content.splitlines()
                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            prefix = f"{file_path}:" if len(files) > 1 else ""
                            match_str = f"{prefix}{i}:{line}" if line_numbers else f"{prefix}{line}"

                            results.append(match_str)
                            total_chars += len(match_str) + 1  # +1 for newline

                            if len(results) >= self.MAX_MATCHES or total_chars >= self.MAX_OUTPUT_CHARS:
                                truncated = True
                                results.append(f"... Output truncated (limit reached: {len(results)} matches or {total_chars} chars) ...")
                                break

                except (PermissionError, UnicodeDecodeError):  # pragma: no cover
                    # Skip files we can't read
                    continue

            if not results:
                return ToolResult(
                    content="No matches found",
                    success=True,
                )

            return ToolResult(
                content="\n".join(results),
                success=True,
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error searching: {e}",
                success=False,
                error=str(e),
            )
