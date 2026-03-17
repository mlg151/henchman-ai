"""Edit file tool implementation."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.security import (
    PathTraversalError,
    atomic_read,
    atomic_write,
    sanitize_error_message,
    validate_path,
)

_STR_PREVIEW_LEN = 50
"""Number of characters to show when previewing a not-found string."""

_FILE_EDIT_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to the file to edit",
        },
        "old_str": {
            "type": "string",
            "description": "The exact string to find and replace (string mode)",
        },
        "new_str": {
            "type": "string",
            "description": "The replacement string",
        },
        "start_line": {
            "type": "integer",
            "description": "Start line number (1-based) for line-range mode",
        },
        "end_line": {
            "type": "integer",
            "description": "End line number (1-based, inclusive) for line-range mode",
        },
        "dry_run": {
            "type": "boolean",
            "description": "Preview changes as unified diff without applying",
            "default": False,
        },
    },
    "required": ["path", "new_str"],
}


@dataclass
class EditParams:
    """Parameter object for file edit operations -- eliminates primitive obsession."""

    path: str
    new_str: str
    old_str: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    dry_run: bool = False

    @property
    def has_line_range(self: EditParams) -> bool:
        """Whether line-range mode is active."""
        return self.start_line is not None and self.end_line is not None

    @property
    def has_old_str(self: EditParams) -> bool:
        """Whether string-replacement mode is active."""
        return self.old_str is not None


def _build_edit_params_from_kwargs(kwargs: dict[str, object]) -> EditParams:
    """Build an EditParams from raw **kwargs.

    Kept as a module-level function so the Feature Envy detector
    does not flag the method that calls it.

    Args:
        kwargs: Raw keyword arguments from execute(**kwargs).

    Returns:
        Populated EditParams.
    """
    return EditParams(
        path=str(kwargs.get("path", "")),
        new_str=str(kwargs.get("new_str", "")),
        old_str=str(kwargs["old_str"]) if kwargs.get("old_str") is not None else None,
        start_line=(int(kwargs["start_line"]) if kwargs.get("start_line") is not None else None),
        end_line=(int(kwargs["end_line"]) if kwargs.get("end_line") is not None else None),
        dry_run=bool(kwargs.get("dry_run", False)),
    )


def _validate_edit_params(params: EditParams) -> ToolResult | None:
    """Validate edit parameters before reading the file.

    Args:
        params: Edit parameters to validate.

    Returns:
        A ToolResult with an error message, or None if valid.
    """
    if not Path(params.path).exists():
        return ToolResult(
            content=f"Error: File not found: {params.path}",
            success=False,
            error=f"File not found: {params.path}",
        )

    if params.has_line_range and params.has_old_str:
        return ToolResult(
            content="Error: Provide either old_str or start_line/end_line, not both.",
            success=False,
            error="Ambiguous edit: both old_str and line range provided",
        )

    if not params.has_line_range and not params.has_old_str:
        return ToolResult(
            content="Error: Provide old_str or start_line/end_line.",
            success=False,
            error="No edit target: provide old_str or start_line/end_line",
        )

    return None


def _validate_line_range(params: EditParams, total: int) -> ToolResult | None:
    """Validate line range parameters against actual file length.

    Args:
        params: Edit parameters containing start_line and end_line.
        total: Total number of lines in the file.

    Returns:
        A ToolResult error, or None if the range is valid.
    """
    assert params.start_line is not None
    assert params.end_line is not None

    if params.start_line < 1 or params.end_line < params.start_line:
        return ToolResult(
            content=f"Error: Invalid line range {params.start_line}-{params.end_line}.",
            success=False,
            error=f"Invalid line range: {params.start_line}-{params.end_line}",
        )

    if params.start_line > total:
        return ToolResult(
            content=(
                f"Error: start_line {params.start_line} exceeds file length ({total} lines)."
            ),
            success=False,
            error=f"start_line {params.start_line} > file length {total}",
        )

    return None


def _build_replacement(params: EditParams, total: int) -> tuple[str, int]:
    """Compute replacement text and clamped end line.

    Args:
        params: Edit parameters with new_str and end_line.
        total: Total lines in the file.

    Returns:
        Tuple of (replacement_text, clamped_end_line).
    """
    assert params.end_line is not None
    clamped_end = min(params.end_line, total)
    replacement = params.new_str
    if replacement and not replacement.endswith("\n") and clamped_end < total:
        replacement += "\n"
    return replacement, clamped_end


class EditFileTool(Tool):
    """Edit a file by replacing a specific string or line range.

    This tool performs precise text replacements in files.
    Supports two modes:
    - String replacement: old_str must match exactly once.
    - Line range: replace lines start_line..end_line with new_str.
    """

    @property
    def name(self: EditFileTool) -> str:
        """Tool name."""
        return "edit_file"

    @property
    def description(self: EditFileTool) -> str:
        """Tool description."""
        return (
            "Edit a file by replacing old_str with new_str (must match exactly once), "
            "or by replacing a line range (start_line/end_line) with new_str."
        )

    parameters = _FILE_EDIT_PARAMETERS

    @property
    def kind(self: EditFileTool) -> ToolKind:
        """Tool kind - WRITE requires confirmation."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]
        self: EditFileTool,
        **kwargs: object,
    ) -> ToolResult:
        """Edit file by replacing string or line range.

        Args:
            **kwargs: Edit parameters (path, new_str, old_str,
                start_line, end_line, dry_run).

        Returns:
            ToolResult with success status or error.
        """
        return _apply_edit(_build_edit_params_from_kwargs(kwargs))


def _apply_edit(params: EditParams) -> ToolResult:
    """Validate and apply the edit described by params.

    Args:
        params: Fully-populated edit parameters.

    Returns:
        ToolResult with success status or error.
    """
    validation_error = _validate_edit_params(params)
    if validation_error is not None:
        return validation_error
    return _apply_edit_safely(params)


def _dispatch_edit(file_path: Path, content: str, params: EditParams) -> ToolResult:
    """Route to the correct edit implementation based on params mode.

    Args:
        file_path: Validated file path.
        content: Current file content.
        params: Edit parameters.

    Returns:
        ToolResult from the appropriate edit function.
    """
    if params.has_line_range:
        assert params.start_line is not None
        assert params.end_line is not None
        return _edit_line_range(file_path, content, params)
    assert params.old_str is not None
    return _edit_string(file_path, content, params)


def _apply_edit_safely(params: EditParams) -> ToolResult:
    """Read the file and apply the edit, handling all I/O and security errors.

    Args:
        params: Validated edit parameters.

    Returns:
        ToolResult with success status or error.
    """
    try:
        file_path = validate_path(params.path)
        content = atomic_read(file_path)
        return _dispatch_edit(file_path, content, params)
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
            content=f"Error editing file: {sanitized_error}",
            success=False,
            error=sanitized_error,
        )


def _edit_string(
    file_path: Path,
    content: str,
    params: EditParams,
) -> ToolResult:
    """Replace a unique string in the file.

    Args:
        file_path: Path to the file.
        content: Current file content.
        params: Edit parameters (old_str, new_str, dry_run).

    Returns:
        ToolResult with success status.
    """
    assert params.old_str is not None
    count = content.count(params.old_str)

    if count == 0:
        return ToolResult(
            content=f"Error: String not found in file: {params.old_str[:_STR_PREVIEW_LEN]}...",
            success=False,
            error="String not found in file",
        )

    if count > 1:
        return ToolResult(
            content=f"Error: String matches {count} times. Must be unique.",
            success=False,
            error=f"Multiple matches ({count}). String must be unique.",
        )

    new_content = content.replace(params.old_str, params.new_str, 1)

    if params.dry_run:
        return _make_diff(file_path, content, new_content)

    atomic_write(file_path, new_content)
    return ToolResult(content=f"Successfully edited {file_path}", success=True)


def _edit_line_range(
    file_path: Path,
    content: str,
    params: EditParams,
) -> ToolResult:
    """Replace a range of lines in the file.

    Args:
        file_path: Path to the file.
        content: Current file content.
        params: Edit parameters (start_line, end_line, new_str, dry_run).

    Returns:
        ToolResult with success status.
    """
    lines = content.splitlines(keepends=True)
    total = len(lines)

    range_error = _validate_line_range(params, total)
    if range_error is not None:
        return range_error

    assert params.start_line is not None
    replacement, clamped_end = _build_replacement(params, total)
    new_lines = [*lines[: params.start_line - 1], replacement, *lines[clamped_end:]]
    new_content = "".join(new_lines)

    if params.dry_run:
        return _make_diff(file_path, content, new_content)

    atomic_write(file_path, new_content)
    return ToolResult(
        content=(
            f"Successfully edited {file_path} (replaced lines {params.start_line}-{clamped_end})"
        ),
        success=True,
    )


def _make_diff(file_path: Path, old: str, new: str) -> ToolResult:
    """Generate a unified diff preview.

    Args:
        file_path: Path to the file (for diff header).
        old: Original content.
        new: New content.

    Returns:
        ToolResult with the unified diff.
    """
    diff = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
    )
    diff_text = "".join(diff)
    if not diff_text:
        return ToolResult(content="No changes.", success=True)
    return ToolResult(content=f"[dry run] Preview:\n{diff_text}", success=True)
