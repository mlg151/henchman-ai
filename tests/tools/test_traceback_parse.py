"""Tests for traceback_parse tool."""

from henchman.tools.base import ToolKind
from henchman.tools.builtins.traceback_parse import TracebackParseTool

SAMPLE_TRACEBACK = """Traceback (most recent call last):
  File "/app/main.py", line 10, in main
    result = process(data)
  File "/app/processor.py", line 25, in process
    return transform(data)
  File "/app/transform.py", line 42, in transform
    raise ValueError("Invalid data format")
ValueError: Invalid data format"""

SAMPLE_MULTILINE = """Traceback (most recent call last):
  File "test.py", line 5, in <module>
    foo()
  File "test.py", line 3, in foo
    return 1 / 0
ZeroDivisionError: division by zero"""


class TestTracebackParseTool:
    """Tests for TracebackParseTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = TracebackParseTool()
        assert tool.name == "traceback_parse"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = TracebackParseTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind."""
        tool = TracebackParseTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = TracebackParseTool()
        params = tool.parameters
        assert "traceback" in params["properties"]
        assert "traceback" in params["required"]

    async def test_parse_simple_traceback(self) -> None:
        """Parse a simple traceback."""
        tool = TracebackParseTool()
        result = await tool.execute(traceback=SAMPLE_TRACEBACK)
        assert result.success is True
        assert "ValueError" in result.content
        assert "Invalid data format" in result.content
        assert "/app/main.py" in result.content
        assert "line 10" in result.content or "10" in result.content

    async def test_parse_extracts_frames(self) -> None:
        """Parse extracts all stack frames."""
        tool = TracebackParseTool()
        result = await tool.execute(traceback=SAMPLE_TRACEBACK)
        assert result.success is True
        assert "main.py" in result.content
        assert "processor.py" in result.content
        assert "transform.py" in result.content

    async def test_parse_division_error(self) -> None:
        """Parse a ZeroDivisionError traceback."""
        tool = TracebackParseTool()
        result = await tool.execute(traceback=SAMPLE_MULTILINE)
        assert result.success is True
        assert "ZeroDivisionError" in result.content
        assert "division by zero" in result.content

    async def test_empty_input(self) -> None:
        """Handle empty input."""
        tool = TracebackParseTool()
        result = await tool.execute(traceback="")
        assert result.success is False

    async def test_non_traceback_input(self) -> None:
        """Handle input that isn't a traceback."""
        tool = TracebackParseTool()
        result = await tool.execute(traceback="just some random text")
        assert result.success is False

    async def test_parse_includes_function_names(self) -> None:
        """Parsed output includes function names."""
        tool = TracebackParseTool()
        result = await tool.execute(traceback=SAMPLE_TRACEBACK)
        assert result.success is True
        assert "main" in result.content
        assert "process" in result.content
        assert "transform" in result.content

    def test_is_code_line_empty(self) -> None:
        """_is_code_line returns False for empty line."""
        tool = TracebackParseTool()
        assert tool._is_code_line("") is False

    def test_is_code_line_traceback_header(self) -> None:
        """_is_code_line returns False for Traceback header."""
        tool = TracebackParseTool()
        assert tool._is_code_line("Traceback (most recent call last):") is False

    def test_is_code_line_exception(self) -> None:
        """_is_code_line returns False for exception lines."""
        tool = TracebackParseTool()
        assert tool._is_code_line("ValueError: bad input") is False

    def test_is_code_line_real_code(self) -> None:
        """_is_code_line returns True for actual code."""
        tool = TracebackParseTool()
        assert tool._is_code_line("result = process(data)") is True

    def test_extract_exception_with_empty_lines(self) -> None:
        """_extract_exception handles empty lines in reversed iteration."""
        tool = TracebackParseTool()
        lines = ["", "  ", "ValueError: bad data"]
        exc_type, exc_msg = tool._extract_exception(lines)
        assert exc_type == "ValueError"
        assert exc_msg == "bad data"

    def test_format_output_with_message(self) -> None:
        """_format_output includes exception and message."""
        tool = TracebackParseTool()
        from henchman.tools.builtins.traceback_parse import TracebackFrame

        frames: list[TracebackFrame] = [{"file": "test.py", "line": 1, "function": "main"}]
        output = tool._format_output(frames, "ValueError", "bad input")
        assert "ValueError" in output
        assert "bad input" in output

    def test_format_output_no_message(self) -> None:
        """_format_output works with exception type but no message."""
        tool = TracebackParseTool()
        from henchman.tools.builtins.traceback_parse import TracebackFrame

        frames: list[TracebackFrame] = []
        output = tool._format_output(frames, "RuntimeError", "")
        assert "RuntimeError" in output

    async def test_frame_with_another_frame_next(self) -> None:
        """Handles frame when next line is also a frame (no code added)."""
        tool = TracebackParseTool()
        tb = (
            "Traceback (most recent call last):\n"
            '  File "a.py", line 1, in func_a\n'
            '  File "b.py", line 2, in func_b\n'
            "ValueError: oops"
        )
        result = await tool.execute(traceback=tb)
        assert result.success is True
        assert "ValueError" in result.content

    async def test_frame_as_last_line(self) -> None:
        """_add_code_to_frame handles frame with no following line (EOF)."""
        tool = TracebackParseTool()
        # Frame is the LAST line - no next line to check
        tb = 'Traceback (most recent call last):\n  File "a.py", line 1, in func'
        result = await tool.execute(traceback=tb)
        assert result.success is True
        assert "a.py" in result.content

    def test_extract_exception_all_empty_or_frame(self) -> None:
        """_extract_exception returns empty when all lines are empty/frames."""
        tool = TracebackParseTool()
        lines = ["", "  ", '  File "x.py", line 1, in foo']
        exc_type, exc_msg = tool._extract_exception(lines)
        assert exc_type == ""
        assert exc_msg == ""

    def test_extract_exception_exc_match_false(self) -> None:
        """_extract_exception handles line where exc_match is None."""
        tool = TracebackParseTool()
        # Line starting with a digit - regex won't match
        lines = ["42: something unexpected"]
        exc_type, exc_msg = tool._extract_exception(lines)
        assert exc_type == ""

    def test_format_output_no_exception_type(self) -> None:
        """_format_output works with empty exception_type."""
        tool = TracebackParseTool()
        from henchman.tools.builtins.traceback_parse import TracebackFrame
        frames: list[TracebackFrame] = [{"file": "test.py", "line": 5, "function": "fn"}]
        output = tool._format_output(frames, "", "")
        assert "Frames: 1" in output
        assert "Exception" not in output
