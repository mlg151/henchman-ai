"""Write file tool implementation."""

from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class WriteFileTool(Tool):
    """Write content to a file, creating it if it doesn't exist.

    This tool writes the provided content to a file. It will create
    parent directories if they don't exist and overwrite existing files.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "write_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Write content to a file. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["path", "content"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - WRITE requires confirmation."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]

        self,
        path: str = "",
        content: str = "",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Write content to file.

        Args:
            path: Path to the file to write.
            content: Content to write to the file.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with success status or error.
        """
        try:
            file_path = Path(path)

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            file_path.write_text(content)

            return ToolResult(
                content=f"Successfully wrote {len(content)} bytes to {path}",
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
                content=f"Error writing file: {e}",
                success=False,
                error=str(e),
            )
