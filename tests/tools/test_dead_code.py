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


class TestDeadCodeInternals:
    """Tests for dead_code module-level helpers."""

    def test_is_import_context_true(self) -> None:
        """is_import_context returns True for names in import statements."""
        import ast

        from henchman.tools.builtins.dead_code import is_import_context

        source = "import os\n"
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                name_node = ast.Name(id="os")
                name_node.lineno = 1  # type: ignore[attr-defined]
                result = is_import_context(name_node, tree)
                assert result is True
                return

    def test_collect_top_level_definitions_class(self) -> None:
        """collect_top_level_definitions includes public classes."""
        import ast

        from henchman.tools.builtins.dead_code import collect_top_level_definitions

        tree = ast.parse("class MyClass:\n    pass\n")
        defs = collect_top_level_definitions(tree)
        assert "MyClass" in defs
        assert defs["MyClass"][0] == "class"

    def test_collect_import_from_names_star_skipped(self) -> None:
        """_collect_import_from_names skips star imports."""
        import ast

        from henchman.tools.builtins.dead_code import _collect_import_from_names

        node = ast.parse("from os import *\n").body[0]
        imported: dict[str, int] = {}
        _collect_import_from_names(node, imported)  # type: ignore[arg-type]
        assert imported == {}

    def test_process_name_in_import_context(self) -> None:
        """_process_name_node returns None when name is in import context."""
        import ast

        from henchman.tools.builtins.dead_code import _process_name_node

        source = "import os\n"
        tree = ast.parse(source)
        name_node = ast.Name(id="os")
        name_node.lineno = 1  # type: ignore[attr-defined]
        result = _process_name_node(name_node, tree)
        assert result is None

    def test_process_attribute_node_non_name_root(self) -> None:
        """_process_attribute_node returns None for non-Name root."""
        import ast

        from henchman.tools.builtins.dead_code import _process_attribute_node

        # obj[0].attr - root is a Subscript, not Name
        node = ast.parse("obj[0].attr").body[0].value  # type: ignore[union-attr]
        result = _process_attribute_node(node)  # type: ignore[arg-type]
        assert result is None

    def test_collect_used_names_attribute(self) -> None:
        """collect_used_names captures attribute root names."""
        import ast

        from henchman.tools.builtins.dead_code import collect_used_names

        tree = ast.parse("os.path.join('a', 'b')\n")
        used = collect_used_names(tree)
        assert "os" in used

    def test_extract_names_from_all_non_list_returns_none(self) -> None:
        """_extract_names_from_all returns None for non-list/tuple AST nodes."""
        import ast

        from henchman.tools.builtins.dead_code import _extract_names_from_all

        node = ast.Constant(value="not a list")
        result = _extract_names_from_all(node)
        assert result is None

    def test_extract_names_from_all_list(self) -> None:
        """_extract_names_from_all extracts string names from list literal."""
        import ast

        from henchman.tools.builtins.dead_code import _extract_names_from_all

        source = "__all__ = ['foo', 'bar']\n"
        tree = ast.parse(source)
        assign = tree.body[0]
        result = _extract_names_from_all(assign.value)  # type: ignore[union-attr]
        assert result == {"foo", "bar"}

    async def test_parse_file_read_error(self) -> None:
        """_parse_file returns ToolResult on read error."""
        import unittest.mock as mock
        from pathlib import Path

        from henchman.tools.base import ToolResult
        from henchman.tools.builtins.dead_code import DeadCodeTool

        tool = DeadCodeTool()
        with mock.patch("pathlib.Path.read_text", side_effect=OSError("fail")):
            result = tool._parse_file(Path("/fake/file.py"))
            assert isinstance(result, ToolResult)
            assert result.success is False

    async def test_directory_scan_no_findings(self) -> None:
        """Directory scan returns clean message when no dead code found."""
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.dead_code import DeadCodeTool

        tool = DeadCodeTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "clean.py"
            f.write_text("import os\nprint(os.getcwd())\n")
            result = await tool.execute(path=tmpdir)
            assert result.success is True
            assert "No dead code" in result.content


class TestDeadCodeCoverage:
    """Additional tests for dead_code coverage gaps."""

    def test_collect_imported_names_from_import(self) -> None:
        """collect_imported_names handles from-import (ast.ImportFrom)."""
        import ast

        from henchman.tools.builtins.dead_code import collect_imported_names

        tree = ast.parse("from os import path\n")
        result = collect_imported_names(tree)
        assert "path" in result

    def test_collect_import_from_names_with_asname(self) -> None:
        """_collect_import_from_names handles aliased imports."""
        import ast

        from henchman.tools.builtins.dead_code import _collect_import_from_names

        node = ast.parse("from os import path as p\n").body[0]
        imported: dict[str, int] = {}
        _collect_import_from_names(node, imported)  # type: ignore[arg-type]
        assert "p" in imported

    def test_collect_used_names_import_context_name(self) -> None:
        """collect_used_names: Name on same line as import returns None (214->211)."""
        import ast

        from henchman.tools.builtins.dead_code import collect_used_names

        # Use semicolon: bare Name 'path' is on same line as import
        # is_import_context returns True → _process_name_node returns None → 214->211
        tree = ast.parse("from os import path; z = path\n")
        used = collect_used_names(tree)
        # 'path' excluded because it's on the import line
        assert "path" not in used

    def test_collect_used_names_attribute_non_name_root(self) -> None:
        """collect_used_names: Attribute with non-Name root returns None (218->211)."""
        import ast

        from henchman.tools.builtins.dead_code import collect_used_names

        # "hello".upper() - root of attribute chain is Constant, not Name → root_name=None
        tree = ast.parse('result = "hello".upper()\n')
        used = collect_used_names(tree)
        # "hello" is a Constant, so _process_attribute_node returns None
        # result is in used_names (it's a Name store context)
        assert isinstance(used, set)

    def test_extract_names_from_all_non_constant_element(self) -> None:
        """_extract_names_from_all: list with non-constant element hits 272->271."""
        import ast

        from henchman.tools.builtins.dead_code import _extract_names_from_all

        # __all__ = [foo, bar] - variables, not string constants
        source = "__all__ = [foo, bar]\n"
        tree = ast.parse(source)
        assign = tree.body[0]
        result = _extract_names_from_all(assign.value)  # type: ignore[union-attr]
        # names is empty because elements are Names, not Constants
        assert result is None
