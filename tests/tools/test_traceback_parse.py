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
