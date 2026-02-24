"""Tests for dead_code tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.dead_code import DeadCodeTool


class TestDeadCodeTool:
    """Tests for DeadCodeTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = DeadCodeTool()
        assert tool.name == "dead_code"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = DeadCodeTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind."""
        tool = DeadCodeTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = DeadCodeTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_unused_import(self) -> None:
        """Detect unused import."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "unused.py"
            f.write_text("import os\nimport sys\nx = sys.argv\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "os" in result.content
            assert "Unused imports" in result.content

    async def test_all_imports_used(self) -> None:
        """No false positives when all imports are used."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "allused.py"
            f.write_text("import os\nimport sys\nprint(os.getcwd(), sys.argv)\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "Unused imports" not in result.content

    async def test_unused_function(self) -> None:
        """Detect unused function."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "dead_func.py"
            f.write_text("def used():\n    pass\n\ndef unused():\n    pass\n\nused()\n")
            result = await tool.execute(path=str(f), check_imports=False)
            assert result.success is True
            # 'unused' is defined but never called
            assert "unused" in result.content

    async def test_whitelisted_names(self) -> None:
        """Whitelisted names are excluded."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "wl.py"
            f.write_text("import os\n")
            result = await tool.execute(path=str(f), whitelist=["os"])
            assert result.success is True
            assert "os" not in result.content or "No dead code" in result.content

    async def test_directory_scan(self) -> None:
        """Scan directory for dead code."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "pkg"
            pkg.mkdir()
            (pkg / "a.py").write_text("import os\nx = 1\n")
            (pkg / "b.py").write_text("import sys\nprint(sys.argv)\n")
            result = await tool.execute(path=str(pkg))
            assert result.success is True
            assert "a.py" in result.content  # a.py has unused os

    async def test_nonexistent_path(self) -> None:
        """Handle nonexistent path."""
        tool = DeadCodeTool()
        result = await tool.execute(path="/nonexistent")
        assert result.success is False

    async def test_empty_path(self) -> None:
        """Handle empty path."""
        tool = DeadCodeTool()
        result = await tool.execute(path="")
        assert result.success is False

    async def test_syntax_error(self) -> None:
        """Handle file with syntax errors."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "broken.py"
            f.write_text("def foo(\n")
            result = await tool.execute(path=str(f))
            assert result.success is False

    async def test_private_functions_excluded(self) -> None:
        """Private functions (starting with _) are not flagged."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "private.py"
            f.write_text("def _private():\n    pass\n")
            result = await tool.execute(path=str(f), check_imports=False)
            assert result.success is True
            assert "_private" not in result.content

    async def test_all_export_respected(self) -> None:
        """Names in __all__ are not flagged."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "exports.py"
            f.write_text('__all__ = ["exported"]\n\ndef exported():\n    pass\n')
            result = await tool.execute(path=str(f), check_imports=False)
            assert result.success is True
            assert "exported" not in result.content or "No dead code" in result.content

    async def test_no_dead_code(self) -> None:
        """Report clean file."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "clean.py"
            f.write_text("x = 1\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "No dead code" in result.content

    async def test_attribute_usage(self) -> None:
        """Import used via attribute access is not flagged."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "attr.py"
            f.write_text("import os\nprint(os.path.join('a', 'b'))\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "os" not in result.content or "No dead code" in result.content

    async def test_imports_only_flag(self) -> None:
        """check_functions=False only checks imports."""
        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text("import os\n\ndef unused():\n    pass\n\nprint(os.getcwd())\n")
            result = await tool.execute(path=str(f), check_functions=False)
            assert result.success is True
            assert "Possibly unused" not in result.content
