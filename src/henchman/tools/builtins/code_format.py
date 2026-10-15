"""Code format tool implementation."""

from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.formatting import format_python_files
from henchman.tools.security import sanitize_error_message

_CODE_FORMAT_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to Python file or directory to format",
        },
    },
    "required": ["path"],
}


class CodeFormatTool(Tool):
    """Format Python files in place with the shared Black backend."""

    @property
    def name(self: "CodeFormatTool") -> str:
        """Tool name."""
        return "code_format"

    @property
    def description(self: "CodeFormatTool") -> str:
        """Tool description."""
        return (
            "Format Python files or directories in place with Black, "
            "honoring project configuration."
        )

    @property
    def parameters(self: "CodeFormatTool") -> dict[str, object]:
        """JSON Schema for parameters."""
        return _CODE_FORMAT_PARAMETERS

    @property
    def kind(self: "CodeFormatTool") -> ToolKind:
        """Tool kind - WRITE modifies files."""
        return ToolKind.WRITE

    def _validate_path(self: "CodeFormatTool", path: str) -> "ToolResult | None":
        """Validate that path is non-empty and exists on disk.

        Args:
            path: Path string to validate.

        Returns:
            A ToolResult error if invalid, None if the path is usable.
        """
        if not path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )
        if not Path(path).exists():
            return ToolResult(
                content=f"Error: Path not found: {path}",
                success=False,
                error=f"Path not found: {path}",
            )
        return None

    async def execute(  # type: ignore[override]
        self: "CodeFormatTool",
        path: str = "",
        **kwargs: object,
    ) -> ToolResult:
        """Format Python files with Black.

        Args:
            path: Path to file or directory.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult indicating what was formatted.
        """
        validation_error = self._validate_path(path)
        if validation_error:
            return validation_error
        try:
            await format_python_files([Path(path)], cwd=Path.cwd())
        except TimeoutError:
            return ToolResult(
                content="Black formatting timed out",
                success=False,
                error="Timeout",
            )
        except Exception as exc:
            diagnostic = sanitize_error_message(exc)
            return ToolResult(
                content=f"Black formatting failed: {diagnostic}",
                success=False,
                error=diagnostic,
            )
        return ToolResult(content=f"Black formatting completed: {path}", success=True)
