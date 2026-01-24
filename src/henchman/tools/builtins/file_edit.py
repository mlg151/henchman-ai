"""Edit file tool implementation."""

from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class EditFileTool(Tool):
    """Edit a file by replacing a specific string.

    This tool performs precise text replacements in files.
    The old_str must match exactly one occurrence in the file.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "edit_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Edit a file by replacing old_str with new_str. "
            "The old_str must match exactly one occurrence."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_str": {
                    "type": "string",
                    "description": "The exact string to find and replace",
                },
                "new_str": {
                    "type": "string",
                    "description": "The string to replace old_str with",
                },
            },
            "required": ["path", "old_str", "new_str"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - WRITE requires confirmation."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]

        self,
        path: str = "",
        old_str: str = "",
        new_str: str = "",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Edit file by replacing string.

        Args:
            path: Path to the file to edit.
            old_str: The string to find and replace.
            new_str: The replacement string.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with success status or error.
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

            # Count occurrences
            count = content.count(old_str)

            if count == 0:
                return ToolResult(
                    content=f"Error: String not found in file: {old_str[:50]}...",
                    success=False,
                    error="String not found in file",
                )

            if count > 1:
                return ToolResult(
                    content=f"Error: String matches {count} times. Must be unique.",
                    success=False,
                    error=f"Multiple matches ({count}). String must be unique.",
                )

            # Perform replacement
            new_content = content.replace(old_str, new_str, 1)
            file_path.write_text(new_content)

            return ToolResult(
                content=f"Successfully edited {path}",
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
                content=f"Error editing file: {e}",
                success=False,
                error=str(e),
            )
