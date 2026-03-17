"""Write file tool implementation."""

from __future__ import annotations

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.security import (
    PathTraversalError,
    sanitize_error_message,
    validate_path,
)


def _write_content_to_path(path: str, content: str) -> ToolResult:
    """Validate path and write content to file.

    Args:
        path: Destination file path.
        content: Text content to write.

    Returns:
        ToolResult with success status (raises on security/permission error).
    """
    file_path = validate_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return ToolResult(
        content=f"Successfully wrote {len(content)} bytes to {path}",
        success=True,
    )


class WriteFileTool(Tool):
    """Write content to a file, creating it if it does not exist.

    This tool writes the provided content to a file. It will create
    parent directories if they do not exist and overwrite existing files.
    """

    @property
    def name(self: WriteFileTool) -> str:
        """Tool name."""
        return "write_file"

    @property
    def description(self: WriteFileTool) -> str:
        """Tool description."""
        return "Write content to a file. Creates parent directories if needed."

    @property
    def parameters(self: WriteFileTool) -> dict[str, object]:
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
    def kind(self: WriteFileTool) -> ToolKind:
        """Tool kind - WRITE requires confirmation."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]
        self: WriteFileTool,
        path: str = "",
        content: str = "",
        **kwargs: object,
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
            return _write_content_to_path(path, content)
        except (PathTraversalError, ValueError) as e:
            return ToolResult(
                content=f"Security validation failed: {e}",
                success=False,
                error="Path validation failed",
            )
        except PermissionError:
            sanitized_error = sanitize_error_message("Permission denied")
            return ToolResult(
                content=f"Error: {sanitized_error}",
                success=False,
                error=sanitized_error,
            )
        except Exception as e:  # pragma: no cover
            sanitized_error = sanitize_error_message(e)
            return ToolResult(
                content=f"Error writing file: {sanitized_error}",
                success=False,
                error=sanitized_error,
            )
