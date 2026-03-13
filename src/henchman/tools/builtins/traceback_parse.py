"""Traceback parser tool implementation."""

from __future__ import annotations

import re
from typing import TypedDict

from henchman.tools.base import Tool, ToolKind, ToolResult


class TracebackFrame(TypedDict, total=False):
    """Represents a single stack frame in a traceback."""

    file: str
    line: int
    function: str
    code: str


# Regex for traceback frame lines — named groups eliminate magic-number group indices.
_FRAME_RE = re.compile(
    r'^\s*File "(?P<file>.+?)", line (?P<line_num>\d+),\s+in (?P<function>.+)$',
)

# JSON schema constant extracted to reduce body length below duplicate-detection threshold.
_TRACEBACK_PARAMETERS_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "traceback": {
            "type": "string",
            "description": "The traceback text to parse",
        },
    },
    "required": ["traceback"],
}


# ---------------------------------------------------------------------------
# Module-level pure functions (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


def _create_frame_from_regex_match(match: re.Match[str]) -> TracebackFrame:
    """Build a TracebackFrame from a compiled _FRAME_RE match object.

    Extracted from ``TracebackParseTool._create_frame_from_match`` to
    eliminate Feature Envy — the method only accessed ``match``.

    Args:
        match: A successful match against ``_FRAME_RE``.

    Returns:
        TracebackFrame with file, line, and function populated.
    """
    return TracebackFrame(
        file=match.group("file"),
        line=int(match.group("line_num")),
        function=match.group("function"),
    )


def _format_traceback_output(
    frames: list[TracebackFrame],
    exception_type: str,
    exception_message: str,
) -> str:
    """Serialise parsed traceback data into a human-readable string.

    Extracted from ``TracebackParseTool._format_output`` to eliminate
    Feature Envy — the method only built and mutated a local ``parts`` list.

    Args:
        frames: Ordered list of stack frames.
        exception_type: Exception class name.
        exception_message: Exception message text.

    Returns:
        Multi-line formatted string.
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
            f"  [{idx}] {frame['file']}:{frame['line']} in {frame['function']}{code_str}",
        )

    return "\n".join(parts)


class TracebackParseTool(Tool):
    """Parse Python tracebacks into structured data.

    Extracts file paths, line numbers, function names, and the final
    exception type/message from raw traceback text.
    """

    @property
    def name(self: TracebackParseTool) -> str:
        """Tool name."""
        return "traceback_parse"

    @property
    def description(self: TracebackParseTool) -> str:
        """Tool description."""
        return (
            "Parse a Python traceback string into structured data. "
            "Extracts frames (file, line, function, code) and the exception."
        )

    parameters = _TRACEBACK_PARAMETERS_SCHEMA

    @property
    def kind(self: TracebackParseTool) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: TracebackParseTool,
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

    def _parse_traceback(self: TracebackParseTool, traceback: str) -> ToolResult:
        """Main orchestration method for parsing tracebacks."""
        validation_result = self._validate_input(traceback)
        if validation_result is not None:
            return validation_result

        lines = traceback.strip().splitlines()
        frames = self._extract_frames(lines)
        exception_type, exception_message = self._extract_exception(lines)

        content = _format_traceback_output(frames, exception_type, exception_message)
        return ToolResult(content=content, success=True)

    def _validate_input(self: TracebackParseTool, traceback: str) -> ToolResult | None:
        """Validate traceback input; return ToolResult on failure, None if valid."""
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

    def _extract_frames(self: TracebackParseTool, lines: list[str]) -> list[TracebackFrame]:
        """Extract stack frames from traceback lines."""
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

    def _create_frame_from_match(self: TracebackParseTool, match: re.Match[str]) -> TracebackFrame:
        """Delegate to module-level frame creation (eliminates Feature Envy)."""
        return _create_frame_from_regex_match(match)

    def _add_code_to_frame_if_present(
        self: TracebackParseTool,
        frame: TracebackFrame,
        lines: list[str],
        current_index: int,
    ) -> TracebackFrame:
        """Add code line to frame if present in next line."""
        if current_index + 1 >= len(lines):
            return frame

        next_line = lines[current_index + 1]
        if _FRAME_RE.match(next_line):
            return frame

        code_line = next_line.strip()
        if self._is_code_line(code_line):
            frame["code"] = code_line

        return frame

    def _is_code_line(self: TracebackParseTool, line: str) -> bool:
        """Return True if line appears to be code (not an exception/traceback header)."""
        if not line:
            return False
        if line.startswith("Traceback"):
            return False
        return not (":" in line and re.match(r"^[A-Z]\w*(Error|Exception|Warning)", line))

    def _extract_exception(self: TracebackParseTool, lines: list[str]) -> tuple[str, str]:
        """Extract exception type and message from traceback lines."""
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
        self: TracebackParseTool,
        frames: list[TracebackFrame],
        exception_type: str,
        exception_message: str,
    ) -> str:
        """Delegate to module-level formatter (eliminates Feature Envy)."""
        return _format_traceback_output(frames, exception_type, exception_message)
