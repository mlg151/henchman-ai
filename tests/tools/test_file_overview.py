"""Tests for the file_overview tool."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from henchman.tools.base import ToolKind
from henchman.tools.builtins.file_overview import (
    FileOverviewTool,
    _collect_imports,
    _execute_file_overview,
    _format_annotation,
    _format_class,
    _format_function_sig,
    _summarize_generic,
    _summarize_json,
    _summarize_markdown,
    _summarize_python,
    _summarize_yaml,
)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestFormatAnnotation:
    """Tests for _format_annotation."""

    def test_none_returns_empty(self) -> None:
        """None annotation returns empty string."""
        assert _format_annotation(None) == ""

    def test_simple_annotation(self) -> None:
        """Name annotation returns ': TypeName'."""
        import ast
        tree = ast.parse("def f(x: int): pass")
        func = tree.body[0]
        ann = func.args.args[0].annotation  # type: ignore[attr-defined]
        assert _format_annotation(ann) == ": int"


class TestSummarizeMarkdown:
    """Tests for _summarize_markdown."""

    def test_headings_extracted(self) -> None:
        """Extracts # headings from lines."""
        lines = ["# Title", "some text", "## Section", "more text", "### Sub"]
        result = _summarize_markdown(lines)
        assert "# Title" in result
        assert "## Section" in result
        assert "### Sub" in result
        assert "some text" not in result

    def test_line_count_shown(self) -> None:
        """Shows total line count."""
        lines = ["line"] * 5
        result = _summarize_markdown(lines)
        assert "5 lines" in result

    def test_truncates_many_headings(self) -> None:
        """Truncates list after 30 headings."""
        lines = [f"# Heading {i}" for i in range(40)]
        result = _summarize_markdown(lines)
        assert "more" in result


class TestSummarizeJson:
    """Tests for _summarize_json."""

    def test_object_shows_keys(self) -> None:
        """Dict shows top-level key count and names."""
        result = _summarize_json('{"a": 1, "b": 2}')
        assert "2 top-level keys" in result
        assert "a" in result

    def test_array_shows_length(self) -> None:
        """Array shows item count."""
        result = _summarize_json("[1, 2, 3]")
        assert "3 items" in result

    def test_invalid_json(self) -> None:
        """Invalid JSON returns error message."""
        result = _summarize_json("not json {")
        assert "could not parse" in result.lower() or "json" in result.lower()


class TestSummarizeYaml:
    """Tests for _summarize_yaml."""

    def test_top_level_keys(self) -> None:
        """Shows top-level key names."""
        lines = ["name: test", "  nested: val", "version: 1.0"]
        result = _summarize_yaml(lines)
        assert "name" in result
        assert "version" in result


class TestSummarizePython:
    """Tests for _summarize_python."""

    def test_imports_section(self) -> None:
        """Extracts import statements."""
        source = "import os\nfrom pathlib import Path\n"
        result = _summarize_python(source, depth=2, include_docs=True)
        assert "import os" in result
        assert "from pathlib import Path" in result

    def test_function_signature(self) -> None:
        """Extracts function signatures."""
        source = 'def hello(name: str) -> str:\n    """Say hello."""\n    return name\n'
        result = _summarize_python(source, depth=2, include_docs=True)
        assert "hello" in result
        assert "str" in result

    def test_class_with_methods(self) -> None:
        """Extracts class and method signatures at depth 2."""
        source = textwrap.dedent("""\
            class Foo:
                def bar(self) -> None:
                    pass
        """)
        result = _summarize_python(source, depth=2, include_docs=True)
        assert "class Foo" in result
        assert "bar" in result

    def test_depth_1_excludes_methods(self) -> None:
        """Depth 1 shows class but not methods."""
        source = textwrap.dedent("""\
            class Foo:
                def bar(self) -> None:
                    pass
        """)
        result = _summarize_python(source, depth=1, include_docs=True)
        assert "class Foo" in result
        assert "bar" not in result

    def test_syntax_error(self) -> None:
        """Returns SyntaxError message for invalid Python."""
        result = _summarize_python("def bad(", depth=2, include_docs=True)
        assert "SyntaxError" in result

    def test_empty_file(self) -> None:
        """Empty source returns empty marker."""
        result = _summarize_python("", depth=2, include_docs=True)
        assert "Empty" in result

    def test_module_docstring_included(self) -> None:
        """Module docstring is shown when include_docs=True."""
        source = '"""Module doc."""\nimport os\n'
        result = _summarize_python(source, depth=2, include_docs=True)
        assert "Module doc" in result

    def test_module_docstring_excluded(self) -> None:
        """Module docstring is skipped when include_docs=False."""
        source = '"""Module doc."""\nimport os\n'
        result = _summarize_python(source, depth=2, include_docs=False)
        assert "Module doc" not in result


class TestCollectImports:
    """Tests for _collect_imports."""

    def test_regular_import(self) -> None:
        """Finds regular import statements."""
        import ast
        tree = ast.parse("import os\nimport sys\n")
        imports = _collect_imports(tree)
        assert "import os" in imports
        assert "import sys" in imports

    def test_from_import(self) -> None:
        """Finds from-import statements."""
        import ast
        tree = ast.parse("from pathlib import Path\n")
        imports = _collect_imports(tree)
        assert any("Path" in i for i in imports)


class TestSummarizeGeneric:
    """Tests for _summarize_generic."""

    def test_markdown_file(self, tmp_path: Path) -> None:
        """Delegates to markdown summarizer for .md files."""
        p = tmp_path / "f.md"
        p.write_text("# Title\ntext\n")
        result = _summarize_generic(p, p.read_text())
        assert "Title" in result

    def test_json_file(self, tmp_path: Path) -> None:
        """Delegates to JSON summarizer for .json files."""
        p = tmp_path / "f.json"
        p.write_text('{"key": 1}')
        result = _summarize_generic(p, p.read_text())
        assert "key" in result

    def test_yaml_file(self, tmp_path: Path) -> None:
        """Delegates to YAML summarizer for .yaml files."""
        p = tmp_path / "f.yaml"
        p.write_text("name: test\nversion: 1\n")
        result = _summarize_generic(p, p.read_text())
        assert "name" in result

    def test_short_generic_file(self, tmp_path: Path) -> None:
        """Short generic files returned as-is."""
        p = tmp_path / "f.txt"
        p.write_text("hello world\n")
        result = _summarize_generic(p, p.read_text())
        assert "hello world" in result

    def test_long_generic_file(self, tmp_path: Path) -> None:
        """Long generic files get truncated preview."""
        p = tmp_path / "f.txt"
        lines = [f"line {i}" for i in range(50)]
        p.write_text("\n".join(lines))
        result = _summarize_generic(p, p.read_text())
        assert "omitted" in result


class TestExecuteFileOverview:
    """Tests for _execute_file_overview."""

    def test_missing_file(self) -> None:
        """Returns error for missing file."""
        result = _execute_file_overview("/no/such/file.py", 2)
        assert result.success is False
        assert "not found" in result.content.lower()

    def test_directory_path(self, tmp_path: Path) -> None:
        """Returns error for directory path."""
        result = _execute_file_overview(str(tmp_path), 2)
        assert result.success is False

    def test_python_file(self, tmp_path: Path) -> None:
        """Returns structural summary for Python file."""
        p = tmp_path / "mod.py"
        p.write_text("import os\ndef foo(): pass\n")
        result = _execute_file_overview(str(p), 2)
        assert result.success is True
        assert "mod.py" in result.content
        assert "foo" in result.content

    def test_markdown_file(self, tmp_path: Path) -> None:
        """Returns heading summary for Markdown file."""
        p = tmp_path / "README.md"
        p.write_text("# Title\ntext\n## Section\n")
        result = _execute_file_overview(str(p), 2)
        assert result.success is True
        assert "Title" in result.content

    def test_json_file(self, tmp_path: Path) -> None:
        """Returns structural summary for JSON file."""
        p = tmp_path / "config.json"
        p.write_text('{"name": "test", "version": "1.0"}')
        result = _execute_file_overview(str(p), 2)
        assert result.success is True
        assert "name" in result.content


# ---------------------------------------------------------------------------
# Tool class tests
# ---------------------------------------------------------------------------


class TestFileOverviewTool:
    """Tests for the FileOverviewTool class."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = FileOverviewTool()
        assert tool.name == "file_overview"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = FileOverviewTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind (auto-approved)."""
        tool = FileOverviewTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Parameters schema has required 'path' field."""
        tool = FileOverviewTool()
        params = tool.parameters
        assert "path" in params["properties"]
        assert "path" in params["required"]

    async def test_execute_missing_path(self) -> None:
        """Returns error when path is empty."""
        tool = FileOverviewTool()
        result = await tool.execute(path="")
        assert result.success is False

    async def test_execute_python_file(self, tmp_path: Path) -> None:
        """Executes successfully for a Python file."""
        p = tmp_path / "test.py"
        p.write_text("import os\ndef hello(): pass\n")
        tool = FileOverviewTool()
        result = await tool.execute(path=str(p))
        assert result.success is True
        assert "hello" in result.content

    async def test_execute_default_depth(self, tmp_path: Path) -> None:
        """Default depth of 2 includes class methods."""
        p = tmp_path / "mod.py"
        p.write_text("class Foo:\n    def bar(self): pass\n")
        tool = FileOverviewTool()
        result = await tool.execute(path=str(p))
        assert result.success is True
        assert "bar" in result.content

    async def test_execute_ignores_extra_kwargs(self, tmp_path: Path) -> None:
        """Extra kwargs are silently ignored."""
        p = tmp_path / "test.py"
        p.write_text("x = 1\n")
        tool = FileOverviewTool()
        result = await tool.execute(path=str(p), unknown_param="ignored")
        assert result.success is True
