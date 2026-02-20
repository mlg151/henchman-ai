"""Tests for python_exec tool."""

import tempfile

from henchman.tools.base import ToolKind
from henchman.tools.builtins.python_exec import PythonExecTool


class TestPythonExecTool:
    """Tests for PythonExecTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = PythonExecTool()
        assert tool.name == "python_exec"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = PythonExecTool()
        assert len(tool.description) > 10

    def test_kind_is_execute(self) -> None:
        """Tool is EXECUTE kind (requires confirmation)."""
        tool = PythonExecTool()
        assert tool.kind == ToolKind.EXECUTE

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = PythonExecTool()
        params = tool.parameters
        assert "code" in params["properties"]
        assert "code" in params["required"]

    async def test_simple_print(self) -> None:
        """Execute simple print statement."""
        tool = PythonExecTool()
        result = await tool.execute(code='print("hello world")')
        assert result.success is True
        assert "hello world" in result.content

    async def test_captures_stdout(self) -> None:
        """Captures stdout from executed code."""
        tool = PythonExecTool()
        result = await tool.execute(code="for i in range(3): print(i)")
        assert result.success is True
        assert "0" in result.content
        assert "1" in result.content
        assert "2" in result.content

    async def test_captures_stderr(self) -> None:
        """Captures stderr from executed code."""
        tool = PythonExecTool()
        result = await tool.execute(code='import sys; sys.stderr.write("warning\\n")')
        assert "warning" in result.content

    async def test_syntax_error(self) -> None:
        """Reports syntax errors."""
        tool = PythonExecTool()
        result = await tool.execute(code="def foo(")
        assert result.success is False
        assert "SyntaxError" in result.content or "syntax" in result.content.lower()

    async def test_runtime_error(self) -> None:
        """Reports runtime errors."""
        tool = PythonExecTool()
        result = await tool.execute(code="1/0")
        assert result.success is False
        assert "ZeroDivisionError" in result.content

    async def test_timeout(self) -> None:
        """Kills long-running code after timeout."""
        tool = PythonExecTool()
        result = await tool.execute(
            code="import time; time.sleep(60)",
            timeout=1,
        )
        assert result.success is False
        assert "timeout" in result.content.lower() or "timed out" in result.content.lower()

    async def test_cwd_parameter(self) -> None:
        """Respects working directory parameter."""
        tool = PythonExecTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await tool.execute(
                code="import os; print(os.getcwd())",
                cwd=tmpdir,
            )
            assert result.success is True
            assert tmpdir in result.content

    async def test_multiline_code(self) -> None:
        """Handles multi-line code blocks."""
        tool = PythonExecTool()
        code = """
def greet(name):
    return f"Hello, {name}!"

print(greet("World"))
"""
        result = await tool.execute(code=code)
        assert result.success is True
        assert "Hello, World!" in result.content

    async def test_uses_same_python(self) -> None:
        """Uses the current Python interpreter."""
        tool = PythonExecTool()
        result = await tool.execute(code="import sys; print(sys.executable)")
        assert result.success is True
        assert "python" in result.content.lower()

    async def test_return_value_in_output(self) -> None:
        """Expression results are not auto-printed (like script mode)."""
        tool = PythonExecTool()
        result = await tool.execute(code="x = 42")
        assert result.success is True
        # No output expected — assignment doesn't print
        assert "42" not in result.content or result.content.strip() == ""
