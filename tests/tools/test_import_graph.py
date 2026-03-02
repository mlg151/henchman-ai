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
            f.write_text(
                "from collections import defaultdict\nfrom typing import Any, Optional\n"
            )
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

    async def test_detect_cycles(self) -> None:
        """Detect circular imports between modules."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "a.py").write_text("from pkg import b\n")
            (pkg / "b.py").write_text("from pkg import a\n")
            result = await tool.execute(
                path=str(pkg / "a.py"),
                scan_dir=str(pkg),
                detect_cycles=True,
            )
            assert result.success is True
            assert "Circular imports:" in result.content
            assert "a" in result.content and "b" in result.content

    async def test_no_cycles(self) -> None:
        """No circular imports found when none exist."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "pkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "a.py").write_text("import os\n")
            (pkg / "b.py").write_text("import sys\n")
            result = await tool.execute(
                path=str(pkg / "a.py"),
                scan_dir=str(pkg),
                detect_cycles=True,
            )
            assert result.success is True
            assert "none detected" in result.content

    async def test_classify_imports(self) -> None:
        """Classify imports as stdlib, local, or third-party."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir) / "mypkg"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "mymod.py").write_text("x = 1\n")
            target = pkg / "main.py"
            target.write_text("import os\nfrom . import mymod\nimport requests\n")
            result = await tool.execute(
                path=str(target),
                scan_dir=str(pkg),
                classify=True,
            )
            assert result.success is True
            assert "[stdlib]" in result.content
            assert "[local]" in result.content
            assert "[third-party]" in result.content

    async def test_classify_without_scan_dir(self) -> None:
        """Classify falls back gracefully without scan_dir."""
        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text("import os\nimport requests\n")
            result = await tool.execute(path=str(f), classify=True)
            assert result.success is True
            assert "[stdlib]" in result.content

    def test_classify_import_method(self) -> None:
        """Test _classify_import helper directly."""
        from henchman.tools.builtins.import_graph import ImportAnalyzer
        
        analyzer = ImportAnalyzer(set())
        assert analyzer.classify_import("import os") == "stdlib"
        assert analyzer.classify_import("import requests") == "third-party"
        assert analyzer.classify_import("from . import foo") == "local"
        assert analyzer.classify_import("from ..bar import baz") == "local"
        
        analyzer_with_local = ImportAnalyzer({"mymod"})
        assert analyzer_with_local.classify_import("import mymod") == "local"

    def test_build_import_graph(self) -> None:
        """Test _build_import_graph constructs correct graph."""
        from henchman.tools.builtins.import_graph import ImportGraphBuilder
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = Path(tmpdir)
            (pkg / "a.py").write_text("from pkg import b\n")
            (pkg / "b.py").write_text("import os\n")
            builder = ImportGraphBuilder(pkg)
            graph = builder.build_graph()
            assert "a" in graph
            assert "b" in graph.get("a", set())
