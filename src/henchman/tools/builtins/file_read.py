"""Read file tool implementation."""

from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult

# Default maximum characters to return
DEFAULT_MAX_CHARS = 50000


class ReadFileTool(Tool):
    """Read contents of a file with optional line range.

    This tool reads the contents of a file and returns them as text.
    It supports reading specific line ranges for large files.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "read_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Read the contents of a file. Supports optional line range for large files. "
            "Always use start_line/end_line to read specific ranges when dealing with "
            "large files to avoid exceeding context limits."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed). Default: 1",
                    "default": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (inclusive). Use -1 for end of file.",
                    "default": -1,
                },
                "max_chars": {
                    "type": "integer",
                    "description": f"Maximum characters to return. Default: {DEFAULT_MAX_CHARS}",
                    "default": DEFAULT_MAX_CHARS,
                },
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self,
        path: str = "",
        start_line: int = 1,
        end_line: int = -1,
        max_chars: int = DEFAULT_MAX_CHARS,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Read file contents.

        Args:
            path: Path to the file to read.
            start_line: Starting line number (1-indexed).
            end_line: Ending line number (inclusive), -1 for end of file.
            max_chars: Maximum characters to return.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with file contents or error.
        """
        try:
            file_path = Path(path)
            if not file_path.exists():
                return ToolResult(
                    content=f"Error: File not found: {path}",
                    success=False,
                    error=f"File not found: {path}",
                )

            content = file_path.read_text()
            lines = content.splitlines()

            # Apply line range
            start_idx = max(0, start_line - 1)
            selected_lines = lines[start_idx:] if end_line == -1 else lines[start_idx:end_line]

            result_content = "\n".join(selected_lines)

            # Apply max_chars truncation
            if max_chars > 0 and len(result_content) > max_chars:
                result_content = result_content[:max_chars]
                result_content += f"\n\n[... truncated after {max_chars} chars. Use start_line/end_line to read specific ranges.]"

            return ToolResult(
                content=result_content,
                success=True,
            )
        except PermissionError:
            return ToolResult(
                content=f"Error: Permission denied: {path}",
                success=False,
                error=f"Permission denied: {path}",
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error reading file: {e}",
                success=False,
                error=str(e),
            )
