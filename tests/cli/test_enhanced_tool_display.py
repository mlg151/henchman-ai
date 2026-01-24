"""Test enhanced tool display in markdown format."""

from unittest.mock import Mock

from rich.console import Console
from rich.markdown import Markdown

from henchman.cli.console import OutputRenderer


class TestEnhancedToolDisplay:
    """Tests for enhanced tool display methods."""

    def test_tool_call_display(self) -> None:
        """Test tool call display in markdown format."""
        console = Mock(spec=Console)
        renderer = OutputRenderer(console=console)

        arguments = {"path": "/test/file.txt", "content": "Hello World"}
        renderer.tool_call("write_file", arguments)

        # Verify markdown was called with expected content
        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert isinstance(call_args, Markdown)
        markup = call_args.markup
        assert "Tool Call" in markup
        assert "write_file" in markup
        assert "path" in markup
        assert "content" in markup

    def test_tool_result_success(self) -> None:
        """Test successful tool result display."""
        console = Mock(spec=Console)
        renderer = OutputRenderer(console=console)

        content = "File written successfully"
        renderer.tool_result(content, success=True)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert isinstance(call_args, Markdown)
        markup = call_args.markup
        assert "Tool Result" in markup
        assert "File written" in markup

    def test_tool_result_failure(self) -> None:
        """Test failed tool result display."""
        console = Mock(spec=Console)
        renderer = OutputRenderer(console=console)

        content = "Permission denied"
        error = "Cannot write to file"
        renderer.tool_result(content, success=False, error=error)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert isinstance(call_args, Markdown)
        markup = call_args.markup
        assert "Tool Failed" in markup
        assert "Permission denied" in markup
        assert "Cannot write to file" in markup

    def test_tool_result_truncation(self) -> None:
        """Test that long tool results are truncated."""
        console = Mock(spec=Console)
        renderer = OutputRenderer(console=console)

        # Create very long content
        content = "A" * 1500
        renderer.tool_result(content, success=True)

        console.print.assert_called_once()
        call_args = console.print.call_args[0][0]
        assert isinstance(call_args, Markdown)
        markup = call_args.markup
        assert "(truncated)" in markup
        assert len(markup) < 2000  # Should be truncated

    def test_tool_summary_with_duration(self) -> None:
        """Test tool summary with duration."""
        console = Mock(spec=Console)
        renderer = OutputRenderer(console=console)

        renderer.tool_summary("read_file", duration=1.234)

        console.print.assert_called_once()
        call_args = str(console.print.call_args[0][0])
        assert "read_file" in call_args
        assert "1.23" in call_args  # Formatted duration

    def test_tool_summary_without_duration(self) -> None:
        """Test tool summary without duration."""
        console = Mock(spec=Console)
        renderer = OutputRenderer(console=console)

        renderer.tool_summary("shell")

        console.print.assert_called_once()
        call_args = str(console.print.call_args[0][0])
        assert "shell" in call_args
        assert "Executed" in call_args


class TestConsoleIntegration:
    """Integration tests for console output."""

    def test_markdown_method_exists(self) -> None:
        """Verify markdown method exists and works."""
        console = Mock(spec=Console)
        renderer = OutputRenderer(console=console)

        # This should not raise an error
        renderer.markdown("# Test Heading\nSome content")

        console.print.assert_called_once()

    def test_all_output_methods(self) -> None:
        """Test all output methods work together."""
        console = Mock(spec=Console)
        renderer = OutputRenderer(console=console)

        # Test a sequence of operations
        renderer.success("Operation completed")
        renderer.warning("Be careful")
        renderer.error("Something went wrong")
        renderer.muted("Debug info")
        renderer.heading("Section Title")
        renderer.code("print('hello')", "python")

        # Should have been called 6 times
        assert console.print.call_count == 6
