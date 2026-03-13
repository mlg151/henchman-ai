"""Read file tool implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from henchman.tools.base import Tool, ToolKind, ToolResult

# Default maximum characters to return
DEFAULT_MAX_CHARS = 50000


@dataclass
class ReadFileConfig:
    """Configuration for reading a file with optional range/limit."""

    path: str
    start_line: int = 1
    end_line: int = -1
    max_chars: int = DEFAULT_MAX_CHARS


def _config_from_read_kwargs(path: str, kwargs: dict[str, Any]) -> ReadFileConfig:
    """Build a ReadFileConfig from an execute **kwargs dict.

    Args:
        path: The required file path.
        kwargs: Additional keyword arguments from execute.

    Returns:
        Populated ReadFileConfig.
    """
    return ReadFileConfig(
        path=path,
        start_line=int(kwargs.get("start_line", 1)),
        end_line=int(kwargs.get("end_line", -1)),
        max_chars=int(kwargs.get("max_chars", DEFAULT_MAX_CHARS)),
    )


def _would_exceed_char_limit(max_chars: int, chars_read: int, line: str) -> bool:
    """Return True if adding *line* would exceed the character limit."""
    return max_chars > 0 and chars_read + len(line) > max_chars


async def _read_lines_from_file(
    file_handle: AsyncIterator[str],
    config: ReadFileConfig,
) -> list[str]:
    """Read and filter lines from an async-iterable file handle.

    Args:
        file_handle: Async-iterable yielding text lines.
        config: Range and character-limit configuration.

    Returns:
        List of lines (possibly truncated) matching the requested range.
    """
    lines: list[str] = []
    current_line = 0
    chars_read = 0

    async for line in file_handle:  # type: ignore[union-attr]
        current_line += 1
        if current_line < config.start_line:
            continue
        if config.end_line != -1 and current_line > config.end_line:
            break
        if _would_exceed_char_limit(config.max_chars, chars_read, line):
            lines.append(line[: config.max_chars - chars_read])
            lines.append(f"\n... (truncated after {config.max_chars} chars)")
            break
        lines.append(line)
        chars_read += len(line)

    return lines


async def _execute_read_file(config: ReadFileConfig) -> ToolResult:
    """Execute file read operation according to *config*.

    Args:
        config: File path, line range, and character limit.

    Returns:
        ToolResult with file contents or an error message.
    """
    import anyio  # noqa: PLC0415

    try:
        file_path = Path(config.path)
        if not file_path.exists():  # noqa: ASYNC240
            return ToolResult(
                content=f"Error: File not found: {config.path}",
                success=False,
                error=f"File not found: {config.path}",
            )

        async with await anyio.open_file(file_path, "r") as f:
            lines = await _read_lines_from_file(f, config)

        return ToolResult(content="".join(lines), success=True)
    except PermissionError:
        return ToolResult(
            content=f"Error: Permission denied: {config.path}",
            success=False,
            error=f"Permission denied: {config.path}",
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            content=f"Error reading file: {e}",
            success=False,
            error=str(e),
        )


class ReadFileTool(Tool):
    """Read contents of a file with optional line range.

    This tool reads the contents of a file and returns them as text.
    It supports reading specific line ranges for large files.
    """

    @property
    def name(self: ReadFileTool) -> str:
        """Tool name."""
        return "read_file"

    @property
    def description(self: ReadFileTool) -> str:
        """Tool description."""
        return (
            "Read the contents of a file. Supports optional line range for large files. "
            "Always use start_line/end_line to read specific ranges when dealing with "
            "large files to avoid exceeding context limits."
        )

    @property
    def parameters(self: ReadFileTool) -> dict[str, object]:
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
    def kind(self: ReadFileTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: ReadFileTool,
        path: str = "",
        **kwargs: object,
    ) -> ToolResult:
        """Read file contents.

        Args:
            path: Path to the file to read.
            **kwargs: Optional ``start_line``, ``end_line``, and ``max_chars``.

        Returns:
            ToolResult with file contents or error.
        """
        if not path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )
        config = _config_from_read_kwargs(path, kwargs)
        return await _execute_read_file(config)
