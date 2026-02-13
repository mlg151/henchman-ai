"""Smoke tests for large file handling.

These tests verify the system handles large files gracefully:
1. Large file reads are truncated
2. Large tool outputs don't crash the system
3. Context limits prevent 413 errors
"""

from pathlib import Path

import pytest

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.file_read import DEFAULT_MAX_CHARS, ReadFileTool
from henchman.tools.registry import MAX_TOOL_OUTPUT, ToolRegistry


class TestLargeFileReading:
    """Smoke tests for reading large files."""

    @pytest.fixture
    def temp_large_file(self, tmp_path) -> Path:
        """Create a large test file."""
        large_file = tmp_path / "large_file.txt"
        # Create file with 200KB of content (larger than default limit)
        content = "Line {}: " + "x" * 100 + "\n"
        lines = [content.format(i) for i in range(2000)]
        large_file.write_text("".join(lines))
        return large_file

    @pytest.fixture
    def temp_huge_file(self, tmp_path) -> Path:
        """Create a huge test file (1MB+)."""
        huge_file = tmp_path / "huge_file.txt"
        # Create 1MB file
        chunk = "data " * 1000 + "\n"
        with open(huge_file, "w") as f:
            for _ in range(200):
                f.write(chunk)
        return huge_file

    @pytest.mark.anyio
    async def test_large_file_does_not_crash(self, temp_large_file):
        """Reading a large file completes without error."""
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_large_file))

        assert result.success is True
        assert len(result.content) > 0

    @pytest.mark.anyio
    async def test_large_file_truncated(self, temp_large_file):
        """Large file content is truncated to safe limit."""
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_large_file))

        # File is 200KB+, should be truncated
        assert len(result.content) < DEFAULT_MAX_CHARS + 500

    @pytest.mark.anyio
    async def test_huge_file_handled_gracefully(self, temp_huge_file):
        """1MB+ file is handled without memory issues."""
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_huge_file))

        assert result.success is True
        # Should be heavily truncated
        assert len(result.content) < 100000

    @pytest.mark.anyio
    async def test_custom_max_chars_respected(self, temp_large_file):
        """Custom max_chars parameter is respected."""
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_large_file), max_chars=1000)

        # Should be truncated to custom limit (with some room for message)
        assert len(result.content) < 1500

    @pytest.mark.anyio
    async def test_truncation_message_included(self, temp_large_file):
        """Truncated files include informative message."""
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_large_file), max_chars=1000)

        # Should mention truncation or file size
        content_lower = result.content.lower()
        assert "truncated" in content_lower or "characters" in content_lower


class TestLargeToolOutput:
    """Smoke tests for large tool outputs."""

    @pytest.mark.anyio
    async def test_tool_registry_truncates_output(self):
        """ToolRegistry truncates excessively large outputs."""

        class HugeOutputTool(Tool):
            @property
            def name(self) -> str:
                return "huge_output"

            @property
            def description(self) -> str:
                return "Returns huge output"

            @property
            def parameters(self) -> dict:
                return {"type": "object", "properties": {}}

            @property
            def kind(self) -> ToolKind:
                return ToolKind.READ

            async def execute(self, **params) -> ToolResult:
                # Return 1MB of content
                return ToolResult(content="x" * 1_000_000)

        registry = ToolRegistry()
        registry.register(HugeOutputTool())

        result = await registry.execute("huge_output", {})

        # Should be truncated to MAX_TOOL_OUTPUT
        assert len(result.content) <= MAX_TOOL_OUTPUT + 200

    @pytest.mark.anyio
    async def test_normal_output_not_affected(self):
        """Normal-sized outputs are not modified."""

        class NormalOutputTool(Tool):
            @property
            def name(self) -> str:
                return "normal_output"

            @property
            def description(self) -> str:
                return "Returns normal output"

            @property
            def parameters(self) -> dict:
                return {"type": "object", "properties": {}}

            @property
            def kind(self) -> ToolKind:
                return ToolKind.READ

            async def execute(self, **params) -> ToolResult:
                return ToolResult(content="Normal sized output")

        registry = ToolRegistry()
        registry.register(NormalOutputTool())

        result = await registry.execute("normal_output", {})

        assert result.content == "Normal sized output"


class TestBinaryFileHandling:
    """Smoke tests for handling binary/non-text files."""

    @pytest.fixture
    def temp_binary_file(self, tmp_path) -> Path:
        """Create a binary test file."""
        binary_file = tmp_path / "binary.bin"
        # Write some binary data
        binary_file.write_bytes(bytes(range(256)) * 100)
        return binary_file

    @pytest.mark.anyio
    async def test_binary_file_error_handling(self, temp_binary_file):
        """Binary files are handled gracefully."""
        tool = ReadFileTool()
        result = await tool.execute(path=str(temp_binary_file))

        # Should either fail gracefully or return partial content
        # (depends on whether file can be decoded)
        assert result is not None


class TestLineRangeWithLargeFiles:
    """Tests for reading specific lines from large files."""

    @pytest.fixture
    def temp_numbered_file(self, tmp_path) -> Path:
        """Create a file with numbered lines."""
        file = tmp_path / "numbered.txt"
        lines = [f"Line {i}: content\n" for i in range(10000)]
        file.write_text("".join(lines))
        return file

    @pytest.mark.anyio
    async def test_line_range_efficient(self, temp_numbered_file):
        """Reading specific lines doesn't load entire file into result."""
        tool = ReadFileTool()
        result = await tool.execute(
            path=str(temp_numbered_file),
            start_line=100,
            end_line=110,
        )

        assert result.success is True
        # Should only have ~10 lines of content
        assert "Line 100" in result.content
        assert "Line 109" in result.content

    @pytest.mark.anyio
    async def test_end_of_large_file(self, temp_numbered_file):
        """Can read end of large file efficiently."""
        tool = ReadFileTool()
        result = await tool.execute(
            path=str(temp_numbered_file),
            start_line=9990,
            end_line=10000,
        )

        assert result.success is True
        assert "Line 9990" in result.content


class TestMemoryUsage:
    """Tests to ensure large operations don't cause memory issues."""

    @pytest.mark.anyio
    async def test_repeated_large_reads(self, tmp_path):
        """Multiple large file reads don't accumulate memory."""
        # Create a moderately large file
        large_file = tmp_path / "repeated.txt"
        large_file.write_text("data\n" * 50000)

        tool = ReadFileTool()

        # Read the file multiple times
        for _ in range(10):
            result = await tool.execute(path=str(large_file))
            assert result.success is True

        # If we get here without OOM, the test passes

    @pytest.mark.anyio
    async def test_many_small_file_reads(self, tmp_path):
        """Many small file operations complete efficiently."""
        # Create many small files
        for i in range(100):
            (tmp_path / f"file_{i}.txt").write_text(f"Content of file {i}\n")

        tool = ReadFileTool()

        # Read all files
        results = []
        for i in range(100):
            result = await tool.execute(path=str(tmp_path / f"file_{i}.txt"))
            results.append(result)

        assert all(r.success for r in results)
        assert len(results) == 100
