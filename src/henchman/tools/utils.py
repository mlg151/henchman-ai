"""Shared utilities for tool implementations."""

from pathlib import Path

from henchman.tools.base import ToolResult


def validate_file_path(path: str) -> ToolResult | None:
    """Validate a file path exists and is accessible.

    Args:
        path: Path to validate.

    Returns:
        ToolResult with error if validation fails, None if valid.
    """
    if not path:
        return ToolResult(
            content="Error: No path provided",
            success=False,
            error="Empty path",
        )

    file_path = Path(path)
    if not file_path.exists():
        return ToolResult(
            content=f"Error: File not found: {path}",
            success=False,
            error=f"File not found: {path}",
        )

    return None


def validate_directory_path(path: str) -> ToolResult | None:
    """Validate a directory path exists and is accessible.

    Args:
        path: Path to validate.

    Returns:
        ToolResult with error if validation fails, None if valid.
    """
    if not path:
        return ToolResult(
            content="Error: No directory path provided",
            success=False,
            error="Empty directory path",
        )

    dir_path = Path(path)
    if not dir_path.exists():
        return ToolResult(
            content=f"Error: Directory not found: {path}",
            success=False,
            error=f"Directory not found: {path}",
        )

    if not dir_path.is_dir():
        return ToolResult(
            content=f"Error: Path is not a directory: {path}",
            success=False,
            error=f"Not a directory: {path}",
        )

    return None