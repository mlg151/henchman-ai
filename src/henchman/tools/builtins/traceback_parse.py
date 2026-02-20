"""Traceback parser tool implementation."""

import re

from henchman.tools.base import Tool, ToolKind, ToolResult

# Regex for traceback frame lines:  File "path", line N, in func
_FRAME_RE = re.compile(
    r'^\s*File "(.+?)", line (\d+),\s+in (.+)$',
)


class TracebackParseTool(Tool):
    """Parse Python tracebacks into structured data.

    Extracts file paths, line numbers, function names, and the final
    exception type/message from raw traceback text.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "traceback_parse"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Parse a Python traceback string into structured data. "
            "Extracts frames (file, line, function, code) and the exception."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "traceback": {
                    "type": "string",
                    "description": "The traceback text to parse",
                },
            },
            "required": ["traceback"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self,
        traceback: str = "",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Parse a traceback string.

        Args:
            traceback: Raw traceback text.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with structured traceback data.
        """
        if not traceback or not traceback.strip():
            return ToolResult(
                content="No traceback provided",
                success=False,
                error="Empty input",
            )

        lines = traceback.strip().splitlines()

        # Check if this looks like a traceback
        has_traceback_header = any(line.strip().startswith("Traceback") for line in lines)
        has_file_line = any(_FRAME_RE.match(line) for line in lines)

        if not has_traceback_header and not has_file_line:
            return ToolResult(
                content="Input does not appear to be a Python traceback",
                success=False,
                error="Not a traceback",
            )

        frames: list[dict[str, str | int]] = []
        exception_type = ""
        exception_message = ""

        i = 0
        while i < len(lines):
            line = lines[i]
            match = _FRAME_RE.match(line)
            if match:
                frame: dict[str, str | int] = {
                    "file": match.group(1),
                    "line": int(match.group(2)),
                    "function": match.group(3),
                }
                # Next line is the code line (if present)
                if i + 1 < len(lines) and not _FRAME_RE.match(lines[i + 1]):
                    code_line = lines[i + 1].strip()
                    is_code = (
                        code_line
                        and not code_line.startswith("Traceback")
                        and (
                            ":" not in code_line
                            or not re.match(
                                r"^[A-Z]\w*(Error|Exception|Warning)",
                                code_line,
                            )
                        )
                    )
                    if is_code:
                        frame["code"] = code_line
                        i += 1
                frames.append(frame)
            i += 1

        # Last non-empty line is typically the exception
        for line in reversed(lines):
            stripped = line.strip()
            if stripped and not _FRAME_RE.match(line):
                # Check if it's an exception line
                exc_match = re.match(r"^([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*):?\s*(.*)", stripped)
                if exc_match:
                    exception_type = exc_match.group(1)
                    exception_message = exc_match.group(2).strip()
                break

        # Build output
        parts: list[str] = []
        if exception_type:
            parts.append(f"Exception: {exception_type}")
            if exception_message:
                parts.append(f"Message: {exception_message}")

        parts.append(f"Frames: {len(frames)}")
        for idx, frame in enumerate(frames):
            code_str = f" | {frame['code']}" if "code" in frame else ""
            parts.append(
                f"  [{idx}] {frame['file']}:{frame['line']} in {frame['function']}{code_str}"
            )

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )
