"""Shared utilities for tool implementations."""

from pathlib import Path
from typing import Any

from henchman.tools.base import ToolResult


def coerce_int(value: object) -> int:
    """Convert a JSON-compatible scalar to an integer.

    Raises:
        TypeError: If *value* is not a scalar accepted by ``int``.
    """
    if not isinstance(value, (str, int, float, bytes, bytearray)):
        message = f"Expected an integer-compatible value, got {type(value).__name__}"
        raise TypeError(message)
    return int(value)


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


def create_parameter_schema(
    required_params: list[str],
    optional_params: dict[str, dict[str, Any]] | None = None,
) -> dict[str, object]:
    """Create a standardized parameter schema for tools.

    Args:
        required_params: List of required parameter names.
        optional_params: Dict mapping optional parameter names to their schemas.

    Returns:
        JSON Schema parameter definition.
    """
    properties: dict[str, Any] = {}

    # Add required parameters (simple string type by default)
    for param in required_params:
        properties[param] = {
            "type": "string",
            "description": f"{param.replace('_', ' ').title()}",
        }

    # Add optional parameters if provided
    if optional_params:
        properties.update(optional_params)

    return {
        "type": "object",
        "properties": properties,
        "required": required_params,
    }


def create_path_parameter_schema(
    additional_params: dict[str, dict[str, Any]] | None = None,
    required: list[str] | None = None,
) -> dict[str, object]:
    """Create a parameter schema for tools that take a file path.

    Args:
        additional_params: Additional parameters to include.
        required: Custom required parameter list (defaults to ["path"]).

    Returns:
        JSON Schema parameter definition.
    """
    base_properties = {
        "path": {
            "type": "string",
            "description": "Path to the file or directory",
        },
    }

    if additional_params:
        base_properties.update(additional_params)

    return create_parameter_schema(
        required_params=required or ["path"],
        optional_params=additional_params,
    )
