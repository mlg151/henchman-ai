"""Tests for import_graph tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.import_graph import ImportGraphTool


class TestImportGraphTool:
    """Tests for ImportGraphTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = ImportGraphTool()
        assert tool.name == "import_graph"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = ImportGraphTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind."""
        tool = ImportGraphTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = ImportGraphTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_simple_imports(self) -> None:
        """Detect imports in a simple file."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "simple.py"
            f.write_text("import os\nfrom pathlib import Path\nimport json\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "os" in result.content
            assert "pathlib" in result.content
            assert "json" in result.content

    async def test_from_imports(self) -> None:
        """Detect 'from X import Y' style imports."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "froms.py"
            f.write_text("from collections import defaultdict\nfrom typing import Any, Optional\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "collections" in result.content
            assert "typing" in result.content

    async def test_relative_imports(self) -> None:
        """Detect relative imports."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "rel.py"
            f.write_text("from . import sibling\nfrom ..parent import thing\n")
            result = await tool.execute(path=str(f))
            assert result.success is True
            assert "sibling" in result.content
            assert "parent" in result.content or "thing" in result.content

    async def test_package_reverse_imports(self) -> None:
        """Find reverse imports within a package."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "a.py").write_text("from mypkg import b\n")
            (pkg / "b.py").write_text("import os\n")
            result = await tool.execute(path=str(pkg / "b.py"), scan_dir=str(pkg))
            assert result.success is True
            # a.py imports b, so b should show a.py as a reverse import
            assert "a.py" in result.content

    async def test_nonexistent_file(self) -> None:
        """Handle nonexistent file."""
        tool = ImportGraphTool()
        result = await tool.execute(path="/nonexistent/foo.py")
        assert result.success is False

    async def test_no_imports(self) -> None:
        """Handle file with no imports."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "noimports.py"
            f.write_text("x = 1\n")
            result = await tool.execute(path=str(f))
            assert result.success is True

    async def test_syntax_error(self) -> None:
        """Handle file with syntax errors."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "broken.py"
            f.write_text("def foo(\n")
            result = await tool.execute(path=str(f))
            assert result.success is False
