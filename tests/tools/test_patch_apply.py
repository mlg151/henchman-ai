"""Tests for patch_apply tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.patch_apply import PatchApplyParameters, PatchApplyTool, PatchParser


class TestPatchApplyTool:
    """Tests for PatchApplyTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = PatchApplyTool()
        assert tool.name == "patch_apply"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = PatchApplyTool()
        assert len(tool.description) > 10

    def test_kind_is_write(self) -> None:
        """Tool is WRITE kind."""
        tool = PatchApplyTool()
        assert tool.kind == ToolKind.WRITE

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = PatchApplyTool()
        params = tool.parameters
        assert "patch" in params["properties"]
        assert "patch" in params["required"]

    async def test_simple_patch(self) -> None:
        """Apply a simple one-hunk patch."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "hello.py"
            f.write_text("x = 1\ny = 2\nz = 3\n")
            patch = (
                "--- a/hello.py\n+++ b/hello.py\n@@ -1,3 +1,3 @@\n x = 1\n-y = 2\n+y = 99\n z = 3\n"
            )
            result = await tool.execute(patch=patch, path=str(f))
            assert result.success is True
            assert "OK" in result.content
            assert f.read_text() == "x = 1\ny = 99\nz = 3\n"

    async def test_multi_hunk_patch(self) -> None:
        """Apply patch with multiple hunks."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "multi.py"
            f.write_text("a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n")
            patch = (
                "@@ -1,2 +1,2 @@\n"
                "-a = 1\n"
                "+a = 10\n"
                " b = 2\n"
                "@@ -4,2 +4,2 @@\n"
                "-d = 4\n"
                "+d = 40\n"
                " e = 5\n"
            )
            result = await tool.execute(patch=patch, path=str(f))
            assert result.success is True
            content = f.read_text()
            assert "a = 10" in content
            assert "d = 40" in content

    async def test_dry_run(self) -> None:
        """Dry run does not modify file."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "dry.py"
            original = "x = 1\n"
            f.write_text(original)
            patch = "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"
            result = await tool.execute(patch=patch, path=str(f), dry_run=True)
            assert result.success is True
            assert "dry run" in result.content
            assert f.read_text() == original

    async def test_empty_patch(self) -> None:
        """Handle empty patch."""
        tool = PatchApplyTool()
        result = await tool.execute(patch="")
        assert result.success is False

    async def test_malformed_patch(self) -> None:
        """Handle malformed patch without file path."""
        tool = PatchApplyTool()
        result = await tool.execute(patch="@@ -1,1 +1,1 @@\n-old\n+new\n")
        assert result.success is False

    async def test_file_not_found(self) -> None:
        """Handle nonexistent target file."""
        tool = PatchApplyTool()
        patch = "--- a/missing.py\n+++ b/missing.py\n@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"
        result = await tool.execute(patch=patch)
        assert "SKIP" in result.content

    async def test_hunk_mismatch(self) -> None:
        """Handle hunk that doesn't match file content."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mismatch.py"
            f.write_text("totally different content\n")
            patch = "@@ -1,1 +1,1 @@\n-expected line\n+new line\n"
            result = await tool.execute(patch=patch, path=str(f))
            assert "FAIL" in result.content

    async def test_fuzz_matching(self) -> None:
        """Fuzz allows offset in context matching."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "fuzz.py"
            # Extra line at the top shifts everything by 1
            f.write_text("extra\nx = 1\ny = 2\n")
            patch = "@@ -1,2 +1,2 @@\n-x = 1\n+x = 99\n y = 2\n"
            result = await tool.execute(patch=patch, path=str(f), fuzz=2)
            assert result.success is True
            assert "x = 99" in f.read_text()

    async def test_file_header_parsing(self) -> None:
        """Parse --- / +++ file headers with b/ prefix."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "header.py"
            f.write_text("a = 1\n")
            patch = f"--- a/header.py\n+++ b/{f}\n@@ -1,1 +1,1 @@\n-a = 1\n+a = 2\n"
            # Use explicit path since b/ stripping won't find the file
            result = await tool.execute(patch=patch, path=str(f))
            assert result.success is True

    async def test_addition_only_hunk(self) -> None:
        """Apply hunk that only adds lines."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "add.py"
            f.write_text("line1\nline2\n")
            patch = "@@ -1,2 +1,3 @@\n line1\n+inserted\n line2\n"
            result = await tool.execute(patch=patch, path=str(f))
            assert result.success is True
            content = f.read_text()
            assert "inserted" in content
            assert content.index("inserted") < content.index("line2")

    async def test_deletion_only_hunk(self) -> None:
        """Apply hunk that only deletes lines."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "del.py"
            f.write_text("keep\nremove\nkeep2\n")
            patch = "@@ -1,3 +1,2 @@\n keep\n-remove\n keep2\n"
            result = await tool.execute(patch=patch, path=str(f))
            assert result.success is True
            content = f.read_text()
            assert "remove" not in content
            assert "keep" in content
            assert "keep2" in content

    def test_parse_patch_no_path(self) -> None:
        """Parse raises ValueError without default path."""
        tool = PatchApplyTool()
        try:
            tool._parse_patch("@@ -1,1 +1,1 @@\n-old\n+new\n")
            raise AssertionError("Should have raised ValueError")
        except ValueError:
            pass

    def test_lines_match(self) -> None:
        """Test _lines_match helper."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        lines = ["a", "b", "c", "d"]
        assert applier._lines_match(lines, ["b", "c"], 1) is True
        assert applier._lines_match(lines, ["b", "c"], 0) is False
        assert applier._lines_match(lines, ["c", "d"], 2) is True
        assert applier._lines_match(lines, ["x"], 0) is False


class TestPatchApplyInternals:
    """Tests for patch_apply internal helpers."""

    def test_split_content_trailing_newline(self) -> None:
        """_split_original_content removes trailing empty from newline-ending content."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        lines = applier._split_original_content("line1\nline2\n")
        assert lines == ["line1", "line2"]

    def test_split_content_no_trailing_newline(self) -> None:
        """_split_original_content works for content without trailing newline."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        lines = applier._split_original_content("line1\nline2")
        assert lines == ["line1", "line2"]

    def test_reconstruct_content_adds_newline(self) -> None:
        """_reconstruct_content adds trailing newline when original had one."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        result = applier._reconstruct_content(["line1", "line2"], "original\n")
        assert result.endswith("\n")

    def test_extract_hunk_lines_non_list(self) -> None:
        """_extract_hunk_lines returns empty list for non-list value."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        result = applier._extract_hunk_lines({"lines": "not a list"})
        assert result == []

    def test_extract_old_and_new_lines_context(self) -> None:
        """_extract_old_and_new_lines includes context lines in both old and new."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        old, new = applier._extract_old_and_new_lines([" context", "-removed", "+added"])
        assert "context" in old
        assert "context" in new
        assert "removed" in old
        assert "added" in new

    def test_find_match_empty_old_lines(self) -> None:
        """_find_match returns expected_start when old_lines is empty."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        result = applier._find_match(["a", "b", "c"], [], 1, 0)
        assert result == 1

    def test_find_match_wide_search(self) -> None:
        """_find_match uses wide search when fuzz is exhausted.

        Places target at index 20 with expected_start=0 and fuzz=0 so the
        exact and fuzz-delta checks both miss, forcing the wide-scan branch.
        """
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        lines = ["a"] * 20 + ["target"] + ["a"] * 30
        result = applier._find_match(lines, ["target"], 0, 0)
        assert result == 20

    def test_lines_match_negative_start(self) -> None:
        """_lines_match returns False for negative start."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        result = applier._lines_match(["a", "b"], ["a"], -1)
        assert result is False

    def test_parse_no_path_raises(self) -> None:
        """PatchParser.parse raises ValueError when no file path found."""
        import pytest

        from henchman.tools.builtins.patch_apply import PatchParser

        parser = PatchParser("@@ -1,1 +1,1 @@\n-old\n+new\n")
        with pytest.raises(ValueError, match="[Nn]o.*path|[Pp]ath.*not.*found"):
            parser.parse()

    def test_parse_hunk_header_invalid(self) -> None:
        """_parse_hunk_header returns None for invalid header."""
        from henchman.tools.builtins.patch_apply import PatchParser

        parser = PatchParser("", default_path="test.py")
        result = parser._parse_hunk_header("not a hunk header")
        assert result is None

    def test_parse_hunk_header_no_counts(self) -> None:
        """_parse_hunk_header handles header without count groups (defaults to 1)."""
        from henchman.tools.builtins.patch_apply import PatchParser

        parser = PatchParser("", default_path="test.py")
        result = parser._parse_hunk_header("@@ -1 +1 @@")
        assert result is not None
        old_start, old_count, new_start, new_count = result
        assert old_start == 1
        assert old_count == 1

    def test_handle_hunk_content_backslash(self) -> None:
        """_handle_hunk_content ignores backslash no-newline lines."""
        from henchman.tools.builtins.patch_apply import PatchParser

        patch = (
            "--- a/test.py\n+++ b/test.py\n"
            "@@ -1,1 +1,1 @@\n-old\n+new\n\\ No newline at end of file\n"
        )
        parser = PatchParser(patch)
        result = parser.parse()
        assert "test.py" in result

    def test_handle_hunk_content_trailing_blank(self) -> None:
        """_handle_hunk_content ignores trailing blank line at EOF."""
        from henchman.tools.builtins.patch_apply import PatchParser

        patch = "--- a/test.py\n+++ b/test.py\n@@ -1,1 +1,1 @@\n-old\n+new\n"
        parser = PatchParser(patch)
        result = parser.parse()
        assert "test.py" in result

    async def test_execute_with_params_empty_patch(self) -> None:
        """_execute_with_params returns error for empty patch."""
        from henchman.tools.builtins.patch_apply import PatchApplyParameters, PatchApplyTool

        tool = PatchApplyTool()
        result = await tool._execute_with_params(
            PatchApplyParameters(patch="   ", path=None, dry_run=False, fuzz=2)
        )
        assert result.success is False
        assert "Empty" in result.content

    async def test_apply_patch_file_read_error(self) -> None:
        """_apply_patch_to_single_file handles read errors gracefully."""
        import tempfile
        import unittest.mock as mock
        from pathlib import Path

        from henchman.tools.builtins.patch_apply import PatchApplyTool

        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "target.py"
            f.write_text("old\n")
            with mock.patch("pathlib.Path.read_text", side_effect=OSError("read error")):
                result = tool._apply_patch_to_single_file(
                    str(f),
                    [
                        {
                            "old_start": 1,
                            "old_count": 1,
                            "new_start": 1,
                            "new_count": 1,
                            "lines": ["-old", "+new"],
                        }
                    ],
                    dry_run=False,
                    fuzz=2,
                )
                assert "SKIP" in result


class TestPatchApplyCoverageGaps:
    """Additional tests for patch_apply coverage gaps."""

    def test_reconstruct_content_no_trailing_newline(self) -> None:
        """_reconstruct_content does not add newline when original lacks it (95->97)."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        result = applier._reconstruct_content(["line1", "line2"], "no newline at end")
        assert not result.endswith("\n")
        assert result == "line1\nline2"

    def test_extract_old_and_new_lines_unknown_prefix(self) -> None:
        """_extract_old_and_new_lines skips lines with unknown prefix (180->175)."""
        from henchman.tools.builtins.patch_apply import HunkApplier

        applier = HunkApplier()
        old, new = applier._extract_old_and_new_lines(["-remove", "+add", "X_unknown"])
        assert old == ["remove"]
        assert new == ["add"]

    def test_handle_hunk_header_returns_none(self) -> None:
        """_handle_hunk_header returns early when _parse_hunk_header returns None (line 350)."""
        parser = PatchParser("", default_path="test.py")
        # Call directly with invalid header - _parse_hunk_header returns None
        parser._handle_hunk_header("not a real hunk header")
        assert parser.current_hunk is None

    def test_handle_hunk_content_unknown_prefix_not_last(self) -> None:
        """_handle_hunk_content ignores lines with no matching prefix mid-file (397->400)."""
        parser = PatchParser("", default_path="test.py")
        parser.current_hunk = {"old_start": 1, "old_count": 1, "new_start": 1, "new_count": 1}
        parser.hunk_lines = []
        parser.lines = ["+add", "X_unknown_middle", "-remove"]
        parser.index = 1  # not the last line
        parser._handle_hunk_content("X_unknown_middle")
        # Should increment index without adding to hunk_lines
        assert parser.index == 2
        assert "X_unknown_middle" not in parser.hunk_lines

    async def test_execute_with_params_no_hunks(self) -> None:
        """_execute_with_params returns error when patch parses but has no hunks (line 508)."""
        tool = PatchApplyTool()
        # A patch that has a file header but no hunks
        params = PatchApplyParameters(
            patch="--- a/test.py\n+++ b/test.py\n",
            path="test.py",
            dry_run=False,
            fuzz=2,
        )
        result = await tool._execute_with_params(params)
        assert result.success is False
        assert "hunks" in result.content.lower() or "No" in result.content
