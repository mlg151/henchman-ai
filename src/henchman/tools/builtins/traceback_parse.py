"""Traceback parser tool implementation."""

import re
from typing import TypedDict

from henchman.tools.base import Tool, ToolKind, ToolResult


class TracebackFrame(TypedDict, total=False):
    """Represents a single stack frame in a traceback."""
    file: str
    line: int
    function: str
    code: str


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
        return self._parse_traceback(traceback)

    def _parse_traceback(self, traceback: str) -> ToolResult:
        """Main orchestration method for parsing tracebacks.

        Args:
            traceback: Raw traceback text.

        Returns:
            ToolResult with structured traceback data.
        """
        # Validate input
        validation_result = self._validate_input(traceback)
        if validation_result is not None:
            return validation_result

        # Parse the traceback
        lines = traceback.strip().splitlines()
        frames = self._extract_frames(lines)
        exception_type, exception_message = self._extract_exception(lines)

        # Format output
        content = self._format_output(frames, exception_type, exception_message)
        return ToolResult(content=content, success=True)

    def _validate_input(self, traceback: str) -> ToolResult | None:
        """Validate traceback input.

        Args:
            traceback: Raw traceback text.

        Returns:
            ToolResult if validation fails, None if valid.
        """
        if not traceback or not traceback.strip():
            return ToolResult(
                content="No traceback provided",
                success=False,
                error="Empty input",
            )

        lines = traceback.strip().splitlines()
        has_traceback_header = any(line.strip().startswith("Traceback") for line in lines)
        has_file_line = any(_FRAME_RE.match(line) for line in lines)

        if not has_traceback_header and not has_file_line:
            return ToolResult(
                content="Input does not appear to be a Python traceback",
                success=False,
                error="Not a traceback",
            )

        return None

    def _extract_frames(self, lines: list[str]) -> list[TracebackFrame]:
        """Extract stack frames from traceback lines.

        Args:
            lines: List of traceback lines.

        Returns:
            List of extracted frames.
        """
        frames: list[TracebackFrame] = []
        i = 0

        while i < len(lines):
            line = lines[i]
            match = _FRAME_RE.match(line)
            if match:
                frame = self._create_frame_from_match(match)
                frame = self._add_code_to_frame_if_present(frame, lines, i)
                frames.append(frame)
                i += 1 if "code" not in frame else 2
            else:
                i += 1

        return frames

    def _create_frame_from_match(self, match: re.Match[str]) -> TracebackFrame:
        """Create a frame dictionary from regex match.

        Args:
            match: Regex match object.

        Returns:
            Frame dictionary.
        """
        return TracebackFrame(
            file=match.group(1),
            line=int(match.group(2)),
            function=match.group(3),
        )

    def _add_code_to_frame_if_present(
        self,
        frame: TracebackFrame,
        lines: list[str],
        current_index: int,
    ) -> TracebackFrame:
        """Add code line to frame if present in next line.

        Args:
            frame: Current frame.
            lines: All traceback lines.
            current_index: Current line index.

        Returns:
            Updated frame with code if present.
        """
        if current_index + 1 >= len(lines):
            return frame

        next_line = lines[current_index + 1]
        if _FRAME_RE.match(next_line):
            return frame

        code_line = next_line.strip()
        if self._is_code_line(code_line):
            frame["code"] = code_line

        return frame

    def _is_code_line(self, line: str) -> bool:
        """Check if a line appears to be code (not exception or traceback header).

        Args:
            line: Line to check.

        Returns:
            True if line appears to be code.
        """
        if not line:
            return False

        if line.startswith("Traceback"):
            return False

        # Check if line looks like an exception
        # Return False if line contains ":" and matches exception pattern
        return not (":" in line and re.match(r"^[A-Z]\w*(Error|Exception|Warning)", line))

    def _extract_exception(self, lines: list[str]) -> tuple[str, str]:
        """Extract exception type and message from traceback lines.

        Args:
            lines: List of traceback lines.

        Returns:
            Tuple of (exception_type, exception_message).
        """
        exception_type = ""
        exception_message = ""

        for line in reversed(lines):
            stripped = line.strip()
            if not stripped or _FRAME_RE.match(line):
                continue

            exc_match = re.match(r"^([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*):?\s*(.*)", stripped)
            if exc_match:
                exception_type = exc_match.group(1)
                exception_message = exc_match.group(2).strip()
            break

        return exception_type, exception_message

    def _format_output(
        self,
        frames: list[TracebackFrame],
        exception_type: str,
        exception_message: str,
    ) -> str:
        """Format parsed traceback data into readable output.

        Args:
            frames: List of stack frames.
            exception_type: Exception type.
            exception_message: Exception message.

        Returns:
            Formatted output string.
        """
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

        return "\n".join(parts)
