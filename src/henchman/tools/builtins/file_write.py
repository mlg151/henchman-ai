"""Write file tool implementation."""

from __future__ import annotations

from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.security import (
    PathTraversalError,
    sanitize_error_message,
    validate_path,
)


class WriteFileTool(Tool):
    """Write content to a file, creating it if it doesn't exist.

    This tool writes the provided content to a file. It will create
    parent directories if they don't exist and overwrite existing files.
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
            # Validate and sanitize path
            file_path = validate_path(path)
            
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write content
            file_path.write_text(content)  # noqa: ASYNC240

            return ToolResult(
                content=f"Successfully wrote {len(content)} bytes to {path}",
                success=True,
            )
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
        except Exception as e:  # pragma: no cover  # noqa: BLE001
            sanitized_error = sanitize_error_message(e)
            return ToolResult(
                content=f"Error writing file: {sanitized_error}",
                success=False,
                error=sanitized_error,
            )
