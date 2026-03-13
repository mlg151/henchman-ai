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


class TestImportGraphInternals:
    """Tests for import_graph module-level helpers."""

    def test_extract_top_level_module_from_import(self) -> None:
        """_extract_top_level_module handles from X.Y import Z."""
        from henchman.tools.builtins.import_graph import _extract_top_level_module

        result = _extract_top_level_module("from os.path import join")
        assert result == "os"

    def test_extract_top_level_module_import(self) -> None:
        """_extract_top_level_module handles import X.Y."""
        from henchman.tools.builtins.import_graph import _extract_top_level_module

        result = _extract_top_level_module("import os.path")
        assert result == "os"

    def test_extract_top_level_module_other(self) -> None:
        """_extract_top_level_module returns empty for unknown format."""
        from henchman.tools.builtins.import_graph import _extract_top_level_module

        result = _extract_top_level_module("not an import")
        assert result == ""

    def test_classify_import_unknown(self) -> None:
        """_classify_import returns third-party for unknown module."""
        from henchman.tools.builtins.import_graph import _classify_import

        result = _classify_import("import numpy", set())
        assert result == "third-party"

    def test_extract_imports_with_alias(self) -> None:
        """_extract_imports_from_import_node handles aliased imports."""
        import ast

        from henchman.tools.builtins.import_graph import _extract_imports_from_import_node

        node = ast.parse("import numpy as np").body[0]
        imports = _extract_imports_from_import_node(node)  # type: ignore[arg-type]
        assert any("numpy as np" in imp for imp in imports)

    def test_extract_dependencies_syntax_error(self) -> None:
        """ImportGraphBuilder skips files with syntax errors."""
        from henchman.tools.builtins.import_graph import ImportGraphBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.py"
            bad.write_text("def foo(")  # syntax error
            builder = ImportGraphBuilder(Path(tmpdir))
            deps = builder._extract_dependencies_from_file(bad, "bad", set())
            assert deps is None

    def test_cycle_finder_no_duplicate_cycles(self) -> None:
        """_CycleFinder deduplicates cycles."""
        from henchman.tools.builtins.import_graph import _CycleFinder

        # a -> b -> a
        graph = {"a": {"b"}, "b": {"a"}}
        finder = _CycleFinder(graph)
        cycles = finder.find_cycles()
        # Should only report cycle once
        assert len(cycles) == 1

    def test_import_analysis_request_validate_bad_scan_dir(self) -> None:
        """ImportAnalysisRequest.validate returns error for bad scan_dir."""
        from henchman.tools.builtins.import_graph import ImportAnalysisRequest

        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text("import os\n")
            req = ImportAnalysisRequest(path=str(f), scan_dir="/nonexistent/dir")
            result = req.validate()
            assert result is not None
            assert result.success is False

    async def test_parse_file_read_error(self) -> None:
        """_parse_file returns ToolResult on read error."""
        import unittest.mock as mock

        from henchman.tools.base import ToolResult
        from henchman.tools.builtins.import_graph import ImportGraphTool

        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test.py"
            f.write_text("import os\n")
            with mock.patch("pathlib.Path.read_text", side_effect=OSError("read error")):
                result = tool._parse_file(f, str(f))
                assert isinstance(result, ToolResult)
                assert result.success is False

    def test_file_imports_module_parse_error(self) -> None:
        """_file_imports_module returns False on parse error."""
        from henchman.tools.builtins.import_graph import ImportGraphTool

        tool = ImportGraphTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            bad = Path(tmpdir) / "bad.py"
            bad.write_text("def foo(")
            result = tool._file_imports_module(bad, "os")
            assert result is False

    def test_check_import_from_node_module_name(self) -> None:
        """_import_from_node_contains_module finds module name in module string."""
        import ast

        from henchman.tools.builtins.import_graph import ImportGraphTool

        tool = ImportGraphTool()
        node = ast.parse("from os.path import join").body[0]
        result = tool._import_from_node_contains_module(node, "path")  # type: ignore[arg-type]
        assert result is True

    def test_collect_local_modules_nonexistent_dir(self) -> None:
        """_collect_local_modules returns empty set for nonexistent dir."""
        from henchman.tools.builtins.import_graph import ImportGraphTool

        tool = ImportGraphTool()
        result = tool._collect_local_modules(Path("/nonexistent/dir"))
        assert result == set()


class TestImportGraphCoverageGaps:
    """Additional tests for import_graph coverage gaps."""

    def test_classify_import_empty_module(self) -> None:
        """_classify_import returns third-party for empty module name (line 55)."""
        from henchman.tools.builtins.import_graph import _classify_import

        # "from " with nothing after → _extract_top_level_module returns ""
        result = _classify_import("from ", set())
        assert result == "third-party"

    def test_build_graph_skips_syntax_error_files(self) -> None:
        """ImportGraphBuilder.build_graph skips files with syntax errors (175->172)."""
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.import_graph import ImportGraphBuilder

        with tempfile.TemporaryDirectory() as tmpdir:
            good = Path(tmpdir) / "good.py"
            good.write_text("import os\n")
            bad = Path(tmpdir) / "bad.py"
            bad.write_text("def foo(")  # syntax error
            builder = ImportGraphBuilder(Path(tmpdir))
            graph = builder.build_graph()
            assert "good" in graph
            assert "bad" not in graph

    def test_dfs_already_visited_not_in_rec_stack(self) -> None:
        """DFS neighbor in visited but not in rec_stack skips it (362->359)."""
        from henchman.tools.builtins.import_graph import _CycleFinder

        # a -> {b, c}, b -> {c}: when DFS visits c via b, then a tries c again
        # c is visited but not in rec_stack
        graph = {"a": {"b", "c"}, "b": {"c"}, "c": set()}
        finder = _CycleFinder(graph)
        cycles = finder.find_cycles()
        # No cycles in this DAG
        assert cycles == []

    def test_record_cycle_deduplication(self) -> None:
        """_record_cycle deduplicates cycles (378->exit)."""
        from henchman.tools.builtins.import_graph import _CycleFinder

        finder = _CycleFinder({"a": {"b"}, "b": {"a"}})
        finder.path = ["a", "b"]
        finder.seen_cycles = set()
        finder.cycles = []
        # Record same cycle twice
        finder._record_cycle("a")
        assert len(finder.cycles) == 1
        finder._record_cycle("a")  # Should be deduped
        assert len(finder.cycles) == 1  # Still 1
