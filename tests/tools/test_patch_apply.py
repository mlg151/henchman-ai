"""Tests for patch_apply tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.patch_apply import PatchApplyTool


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
                "--- a/hello.py\n"
                "+++ b/hello.py\n"
                "@@ -1,3 +1,3 @@\n"
                " x = 1\n"
                "-y = 2\n"
                "+y = 99\n"
                " z = 3\n"
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
            patch = "@@ -1,1 +1,1 @@\n" "-x = 1\n" "+x = 2\n"
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
        patch = (
            "--- a/missing.py\n"
            "+++ b/missing.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-x = 1\n"
            "+x = 2\n"
        )
        result = await tool.execute(patch=patch)
        assert "SKIP" in result.content

    async def test_hunk_mismatch(self) -> None:
        """Handle hunk that doesn't match file content."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "mismatch.py"
            f.write_text("totally different content\n")
            patch = "@@ -1,1 +1,1 @@\n" "-expected line\n" "+new line\n"
            result = await tool.execute(patch=patch, path=str(f))
            assert "FAIL" in result.content

    async def test_fuzz_matching(self) -> None:
        """Fuzz allows offset in context matching."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "fuzz.py"
            # Extra line at the top shifts everything by 1
            f.write_text("extra\nx = 1\ny = 2\n")
            patch = "@@ -1,2 +1,2 @@\n" "-x = 1\n" "+x = 99\n" " y = 2\n"
            result = await tool.execute(patch=patch, path=str(f), fuzz=2)
            assert result.success is True
            assert "x = 99" in f.read_text()

    async def test_file_header_parsing(self) -> None:
        """Parse --- / +++ file headers with b/ prefix."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "header.py"
            f.write_text("a = 1\n")
            patch = (
                f"--- a/header.py\n"
                f"+++ b/{f}\n"
                "@@ -1,1 +1,1 @@\n"
                "-a = 1\n"
                "+a = 2\n"
            )
            # Use explicit path since b/ stripping won't find the file
            result = await tool.execute(patch=patch, path=str(f))
            assert result.success is True

    async def test_addition_only_hunk(self) -> None:
        """Apply hunk that only adds lines."""
        tool = PatchApplyTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "add.py"
            f.write_text("line1\nline2\n")
            patch = "@@ -1,2 +1,3 @@\n" " line1\n" "+inserted\n" " line2\n"
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
            patch = "@@ -1,3 +1,2 @@\n" " keep\n" "-remove\n" " keep2\n"
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
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_lines_match(self) -> None:
        """Test _lines_match helper."""
        tool = PatchApplyTool()
        lines = ["a", "b", "c", "d"]
        assert tool._lines_match(lines, ["b", "c"], 1) is True
        assert tool._lines_match(lines, ["b", "c"], 0) is False
        assert tool._lines_match(lines, ["c", "d"], 2) is True
        assert tool._lines_match(lines, ["x"], 0) is False
