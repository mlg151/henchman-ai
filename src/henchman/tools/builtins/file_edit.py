"""Edit file tool implementation."""

import difflib
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class EditFileTool(Tool):
    """Edit a file by replacing a specific string or line range.

    This tool performs precise text replacements in files.
    Supports two modes:
    - String replacement: old_str must match exactly once.
    - Line range: replace lines start_line..end_line with new_str.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "edit_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Edit a file by replacing old_str with new_str (must match exactly once), "
            "or by replacing a line range (start_line/end_line) with new_str."
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

    @property
    def kind(self) -> ToolKind:
        """Tool kind - WRITE requires confirmation."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]
        self,
        path: str = "",
        old_str: str | None = None,
        new_str: str = "",
        start_line: int | None = None,
        end_line: int | None = None,
        dry_run: bool = False,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Edit file by replacing string or line range.

        Args:
            path: Path to the file to edit.
            old_str: The string to find and replace (string mode).
            new_str: The replacement string.
            start_line: Start line (1-based) for line-range mode.
            end_line: End line (1-based, inclusive) for line-range mode.
            dry_run: Preview changes without applying.
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

            # Determine mode
            has_line_range = start_line is not None and end_line is not None
            has_old_str = old_str is not None

            if has_line_range and has_old_str:
                return ToolResult(
                    content="Error: Provide either old_str or start_line/end_line, not both.",
                    success=False,
                    error="Ambiguous edit: both old_str and line range provided",
                )

            if not has_line_range and not has_old_str:
                return ToolResult(
                    content="Error: Provide old_str or start_line/end_line.",
                    success=False,
                    error="No edit target: provide old_str or start_line/end_line",
                )

            if has_line_range:
                assert start_line is not None and end_line is not None
                return self._edit_line_range(
                    file_path, content, start_line, end_line, new_str, dry_run
                )
            else:
                assert old_str is not None
                return self._edit_string(file_path, content, old_str, new_str, dry_run)

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

    def _edit_string(
        self,
        file_path: Path,
        content: str,
        old_str: str,
        new_str: str,
        dry_run: bool,
    ) -> ToolResult:
        """Replace a unique string in the file.

        Args:
            file_path: Path to the file.
            content: Current file content.
            old_str: String to find and replace.
            new_str: Replacement string.
            dry_run: Preview only.

        Returns:
            ToolResult with success status.
        """
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

        new_content = content.replace(old_str, new_str, 1)

        if dry_run:
            return self._make_diff(file_path, content, new_content)

        file_path.write_text(new_content)
        return ToolResult(content=f"Successfully edited {file_path}", success=True)

    def _edit_line_range(
        self,
        file_path: Path,
        content: str,
        start_line: int,
        end_line: int,
        new_str: str,
        dry_run: bool,
    ) -> ToolResult:
        """Replace a range of lines in the file.

        Args:
            file_path: Path to the file.
            content: Current file content.
            start_line: Start line number (1-based).
            end_line: End line number (1-based, inclusive).
            new_str: Replacement text.
            dry_run: Preview only.

        Returns:
            ToolResult with success status.
        """
        lines = content.splitlines(keepends=True)
        total = len(lines)

        if start_line < 1 or end_line < start_line:
            return ToolResult(
                content=f"Error: Invalid line range {start_line}-{end_line}.",
                success=False,
                error=f"Invalid line range: {start_line}-{end_line}",
            )

        if start_line > total:
            return ToolResult(
                content=f"Error: start_line {start_line} exceeds file length ({total} lines).",
                success=False,
                error=f"start_line {start_line} > file length {total}",
            )

        # Clamp end_line to file length
        clamped_end = min(end_line, total)

        # Build replacement lines (ensure trailing newline if replacing mid-file)
        replacement = new_str
        if replacement and not replacement.endswith("\n") and clamped_end < total:
            replacement += "\n"

        new_lines = lines[: start_line - 1] + [replacement] + lines[clamped_end:]
        new_content = "".join(new_lines)

        if dry_run:
            return self._make_diff(file_path, content, new_content)

        file_path.write_text(new_content)
        return ToolResult(
            content=f"Successfully edited {file_path} (replaced lines {start_line}-{clamped_end})",
            success=True,
        )

    def _make_diff(self, file_path: Path, old: str, new: str) -> ToolResult:
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
