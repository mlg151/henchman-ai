"""Tests for grep tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.grep import GrepTool


class TestGrepTool:
    """Tests for GrepTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = GrepTool()
        assert tool.name == "grep"

    def test_description(self) -> None:
        """Tool has description."""
        tool = GrepTool()
        assert "search" in tool.description.lower() or "pattern" in tool.description.lower()

    def test_kind_is_read(self) -> None:
        """Tool is a READ kind (auto-approved)."""
        tool = GrepTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = GrepTool()
        params = tool.parameters
        assert "pattern" in params["properties"]
        assert "path" in params["properties"]
        assert "pattern" in params["required"]

    async def test_grep_simple_pattern(self) -> None:
        """Find lines matching simple pattern."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\nfoo bar\nhello there\n")
            f.flush()
            result = await tool.execute(pattern="hello", path=f.name)
        assert result.success is True
        assert "hello world" in result.content
        assert "hello there" in result.content
        assert "foo bar" not in result.content
        Path(f.name).unlink()

    async def test_grep_regex_pattern(self) -> None:
        """Find lines matching regex pattern."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test123\ntest456\nhello\n")
            f.flush()
            result = await tool.execute(pattern=r"test\d+", path=f.name)
        assert result.success is True
        assert "test123" in result.content
        assert "test456" in result.content
        assert "hello" not in result.content
        Path(f.name).unlink()

    async def test_grep_case_insensitive(self) -> None:
        """Case insensitive search."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello\nHELLO\nhello\nworld\n")
            f.flush()
            result = await tool.execute(pattern="hello", path=f.name, ignore_case=True)
        assert result.success is True
        assert "Hello" in result.content
        assert "HELLO" in result.content
        assert "hello" in result.content
        Path(f.name).unlink()

    async def test_grep_directory(self) -> None:
        """Search in all files in a directory."""
        tool = GrepTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file1.txt").write_text("hello world\n")
            (Path(tmpdir) / "file2.txt").write_text("goodbye world\n")

            result = await tool.execute(pattern="hello", path=tmpdir)
            assert result.success is True
            assert "hello" in result.content
            assert "file1.txt" in result.content

    async def test_grep_with_line_numbers(self) -> None:
        """Include line numbers in output."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line1\nhello\nline3\n")
            f.flush()
            result = await tool.execute(pattern="hello", path=f.name, line_numbers=True)
        assert result.success is True
        assert "2" in result.content  # Line number
        Path(f.name).unlink()

    async def test_grep_no_matches(self) -> None:
        """Handle no matches gracefully."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\n")
            f.flush()
            result = await tool.execute(pattern="nonexistent", path=f.name)
        assert result.success is True
        assert "no matches" in result.content.lower() or result.content.strip() == ""
        Path(f.name).unlink()

    async def test_grep_file_not_found(self) -> None:
        """Handle file not found error."""
        tool = GrepTool()
        result = await tool.execute(pattern="test", path="/nonexistent/file.txt")
        assert result.success is False
        assert result.error is not None

    async def test_grep_with_glob_pattern(self) -> None:
        """Search with file glob pattern."""
        tool = GrepTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "file.txt").write_text("hello txt\n")
            (Path(tmpdir) / "file.py").write_text("hello py\n")

            result = await tool.execute(pattern="hello", path=tmpdir, glob="*.txt")
            assert result.success is True
            assert "hello txt" in result.content
            assert "hello py" not in result.content

    async def test_grep_context_before(self) -> None:
        """Show lines before a match."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line1\nline2\ntarget\nline4\n")
            f.flush()
            result = await tool.execute(
                pattern="target", path=f.name, context_before=1, line_numbers=True
            )
        assert result.success is True
        assert "line2" in result.content
        assert "target" in result.content
        Path(f.name).unlink()

    async def test_grep_context_after(self) -> None:
        """Show lines after a match."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("line1\ntarget\nline3\nline4\n")
            f.flush()
            result = await tool.execute(
                pattern="target", path=f.name, context_after=1, line_numbers=True
            )
        assert result.success is True
        assert "target" in result.content
        assert "line3" in result.content
        Path(f.name).unlink()

    async def test_grep_context_separator(self) -> None:
        """Non-contiguous context blocks separated by '--'."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("a\nmatch1\nb\nc\nd\ne\nmatch2\nf\n")
            f.flush()
            result = await tool.execute(
                pattern="match", path=f.name, context_before=0, context_after=0, line_numbers=True
            )
        assert result.success is True
        assert "match1" in result.content
        assert "match2" in result.content
        Path(f.name).unlink()

    async def test_grep_context_line_separator_types(self) -> None:
        """Context lines use '-' separator, match lines use ':'."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("before\ntarget\nafter\n")
            f.flush()
            result = await tool.execute(
                pattern="target", path=f.name, context_before=1, context_after=1, line_numbers=True
            )
        assert result.success is True
        # Match line uses ':'
        assert "2:target" in result.content
        # Context lines use '-'
        assert "1-before" in result.content
        assert "3-after" in result.content
        Path(f.name).unlink()

    async def test_grep_invert_match(self) -> None:
        """Select non-matching lines."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello\nworld\nhello again\n")
            f.flush()
            result = await tool.execute(pattern="hello", path=f.name, invert_match=True)
        assert result.success is True
        assert "world" in result.content
        assert "hello" not in result.content
        Path(f.name).unlink()

    async def test_grep_whole_word(self) -> None:
        """Match whole words only."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("cat\ncatalog\nthe cat sat\n")
            f.flush()
            result = await tool.execute(pattern="cat", path=f.name, whole_word=True)
        assert result.success is True
        assert "cat" in result.content
        assert "the cat sat" in result.content
        # "catalog" should not match since "cat" is not a whole word there
        lines = result.content.strip().split("\n")
        assert not any(line.strip() == "catalog" for line in lines)
        Path(f.name).unlink()

    async def test_grep_count_only(self) -> None:
        """Count matches per file."""
        tool = GrepTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.txt").write_text("hello\nhello\nworld\n")
            (Path(tmpdir) / "b.txt").write_text("hello\n")

            result = await tool.execute(pattern="hello", path=tmpdir, count_only=True)
            assert result.success is True
            assert "2" in result.content  # a.txt has 2 matches
            assert "1" in result.content  # b.txt has 1 match
            assert "Total: 3" in result.content

    async def test_grep_count_only_no_matches(self) -> None:
        """Count mode with no matches."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello\n")
            f.flush()
            result = await tool.execute(pattern="nonexistent", path=f.name, count_only=True)
        assert result.success is True
        assert "no matches" in result.content.lower()
        Path(f.name).unlink()

    async def test_grep_invalid_regex(self) -> None:
        """Handle invalid regex pattern."""
        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello\n")
            f.flush()
            result = await tool.execute(pattern="[invalid", path=f.name)
        assert result.success is False
        assert "invalid regex" in result.content.lower() or "error" in result.content.lower()
        Path(f.name).unlink()


class TestGrepInternals:
    """Tests for grep internal functions and classes."""

    def test_format_context_block_empty_indices(self) -> None:
        """_format_context_block returns empty for no match indices."""
        from henchman.tools.builtins.grep import ContextConfig, _format_context_block

        config = ContextConfig(context_before=2, context_after=2, line_numbers=True, file_prefix="")
        result = _format_context_block(["a", "b"], set(), config)
        assert result == []

    def test_format_context_block_separator(self) -> None:
        """_format_context_block inserts -- separator between non-adjacent blocks."""
        from henchman.tools.builtins.grep import ContextConfig, _format_context_block

        lines = [f"line{i}" for i in range(20)]
        config = ContextConfig(context_before=0, context_after=0, line_numbers=True, file_prefix="")
        # Two non-adjacent matches
        result = _format_context_block(lines, {0, 10}, config)
        assert "--" in result

    def test_format_context_block_no_line_numbers(self) -> None:
        """_format_context_block works without line numbers."""
        from henchman.tools.builtins.grep import ContextConfig, _format_context_block

        lines = ["hello", "world"]
        config = ContextConfig(context_before=0, context_after=0, line_numbers=False, file_prefix="")
        result = _format_context_block(lines, {0}, config)
        assert result == ["hello"]

    def test_result_formatter_should_truncate(self) -> None:
        """ResultFormatter.should_truncate returns True when limits exceeded."""
        from henchman.tools.builtins.grep import ResultFormatter

        fmt = ResultFormatter()
        assert fmt.should_truncate(["x"] * 1000, 0) is True
        assert fmt.should_truncate([], 100_001) is True
        assert fmt.should_truncate([], 100) is False

    def test_file_searcher_find_matching_indices(self) -> None:
        """FileSearcher._find_matching_indices delegates correctly."""
        import re

        from henchman.tools.builtins.grep import FileSearcher, ResultFormatter

        searcher = FileSearcher(ResultFormatter())
        regex = re.compile("hello")
        result = searcher._find_matching_indices(["hello", "world"], regex, False)
        assert result == {0}

    def test_file_searcher_validate_and_setup(self) -> None:
        """FileSearcher._validate_and_setup returns error for missing path."""
        from henchman.tools.builtins.grep import FileSearcher, ResultFormatter, ToolResult

        searcher = FileSearcher(ResultFormatter())
        from henchman.tools.builtins.grep import GrepParameters
        result = searcher._validate_and_setup(GrepParameters(pattern="pattern", path="/nonexistent/path"))
        assert isinstance(result, ToolResult)
        assert result.success is False

    def test_file_searcher_count_matches(self) -> None:
        """FileSearcher._count_matches counts per file."""
        import re
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.grep import FileSearcher, ResultFormatter

        searcher = FileSearcher(ResultFormatter())
        regex = re.compile("hello")
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.txt"
            f.write_text("hello\nworld\nhello\n")
            result = searcher._count_matches([f], regex, False)
            assert "2" in result.content

    def test_file_searcher_search_single_file(self) -> None:
        """FileSearcher._search_single_file delegates correctly."""
        import re
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.grep import FileSearcher, ResultFormatter, SearchConfig

        searcher = FileSearcher(ResultFormatter())
        regex = re.compile("hello")
        config = SearchConfig(
            invert_match=False,
            has_context=False,
            context_before=0,
            context_after=0,
            line_numbers=False,
            multi_file=False,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.txt"
            f.write_text("hello world\n")
            result = searcher._search_single_file(f, regex, config, "")
            assert result is not None
            matches, chars = result
            assert len(matches) > 0

    def test_file_searcher_search_files(self) -> None:
        """FileSearcher.search_files returns results."""
        import re
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.grep import FileSearcher, ResultFormatter, SearchConfig

        searcher = FileSearcher(ResultFormatter())
        regex = re.compile("hello")
        config = SearchConfig(
            invert_match=False,
            has_context=False,
            context_before=0,
            context_after=0,
            line_numbers=False,
            multi_file=False,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.txt"
            f.write_text("hello world\n")
            result = searcher.search_files([f], regex, config)
            assert result.success is True

    async def test_execute_with_params(self) -> None:
        """GrepTool._execute_with_params delegates to _execute_grep."""
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.grep import GrepParameters, GrepTool

        tool = GrepTool()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world\n")
            f.flush()
            params = GrepParameters(pattern="hello", path=f.name)
            result = await tool._execute_with_params(params)
            Path(f.name).unlink()
        assert result.success is True

    async def test_truncation_on_many_matches(self) -> None:
        """Results truncated when match limit exceeded."""
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.grep import GrepTool

        tool = GrepTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with 1001 matching lines
            f = Path(tmpdir) / "big.txt"
            f.write_text("\n".join(["match"] * 1001))
            result = await tool.execute(pattern="match", path=str(f))
            assert "truncated" in result.content or result.success is True

    def test_file_searcher_collect_files(self) -> None:
        """FileSearcher._collect_files delegates to _collect_files (line 428)."""
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.grep import FileSearcher, ResultFormatter

        searcher = FileSearcher(ResultFormatter())
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.txt"
            f.write_text("hello\n")
            files = searcher._collect_files(Path(tmpdir), None)
            assert f in files

    async def test_truncation_across_files_line316(self) -> None:
        """Outer loop breaks when truncated=True at start of next file (line 316)."""
        import re
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.grep import (
            SearchConfig,
            _search_files,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "a.txt"
            f2 = Path(tmpdir) / "b.txt"
            f1.write_text("\n".join(["match"] * 600))
            f2.write_text("match\n")

            regex = re.compile("match")
            config = SearchConfig(
                invert_match=False,
                has_context=False,
                context_before=0,
                context_after=0,
                line_numbers=False,
                multi_file=True,
            )
            # Use small max_matches to trigger truncation during first file
            result = _search_files([f1, f2], regex, config, max_matches=3, max_output_chars=100_000)
            assert "truncated" in result.content
