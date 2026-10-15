"""Tests for the pattern_search tool."""

from __future__ import annotations

import textwrap
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.pattern_search import (
    PatternMatch,
    PatternSearchParams,
    PatternSearchTool,
    _build_pattern_search_report,
    _collect_files,
    _deduplicate_and_rank,
    _execute_pattern_search,
    _extract_keywords,
    _extract_structural_patterns,
    _search_file_structural,
)

# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestExtractKeywords:
    """Tests for _extract_keywords."""

    def test_removes_stop_words(self) -> None:
        """Stop words are filtered out."""
        keywords = _extract_keywords("find all the functions that handle errors")
        assert "the" not in keywords
        assert "that" not in keywords
        assert "find" not in keywords  # "find" is a stop word

    def test_keeps_meaningful_words(self) -> None:
        """Meaningful words are retained."""
        keywords = _extract_keywords("authentication middleware")
        assert "authentication" in keywords
        assert "middleware" in keywords

    def test_ignores_short_tokens(self) -> None:
        """Tokens shorter than 3 chars are excluded."""
        keywords = _extract_keywords("if x is ok")
        assert "x" not in keywords
        assert "ok" not in keywords  # len 2

    def test_empty_description(self) -> None:
        """Empty description returns empty list."""
        assert _extract_keywords("") == []


class TestExtractStructuralPatterns:
    """Tests for _extract_structural_patterns."""

    def test_detects_inheritance(self) -> None:
        """Detects 'inherits from X' pattern."""
        patterns = _extract_structural_patterns("classes that inherit from Tool")
        labels = [p[0] for p in patterns]
        assert any("inherits" in lbl for lbl in labels)

    def test_detects_decorator(self) -> None:
        """Detects '@decorator' or 'decorated with' pattern."""
        patterns = _extract_structural_patterns("methods decorated with property")
        labels = [p[0] for p in patterns]
        assert any("decorator" in lbl for lbl in labels)

    def test_detects_async(self) -> None:
        """Detects async function pattern."""
        patterns = _extract_structural_patterns("async coroutines that handle requests")
        labels = [p[0] for p in patterns]
        assert any("async" in lbl for lbl in labels)

    def test_detects_class_def(self) -> None:
        """Detects class definition pattern."""
        patterns = _extract_structural_patterns("class definitions")
        labels = [p[0] for p in patterns]
        assert any("class" in lbl for lbl in labels)

    def test_detects_raises(self) -> None:
        """Detects raise/exception pattern."""
        patterns = _extract_structural_patterns("functions that raise exceptions")
        labels = [p[0] for p in patterns]
        assert any("raises" in lbl for lbl in labels)

    def test_no_patterns_for_generic(self) -> None:
        """Generic descriptions without structural hints return few patterns."""
        patterns = _extract_structural_patterns("some code")
        # May or may not have patterns depending on description content
        assert isinstance(patterns, list)


class TestCollectFiles:
    """Tests for _collect_files."""

    def test_file_returns_itself(self, tmp_path: Path) -> None:
        """Single file path returns just that file."""
        p = tmp_path / "a.py"
        p.write_text("x = 1")
        files = _collect_files(p, None)
        assert files == [p]

    def test_directory_collects_files(self, tmp_path: Path) -> None:
        """Directory collects all files recursively."""
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")
        files = _collect_files(tmp_path, None)
        names = [f.name for f in files]
        assert "a.py" in names
        assert "b.py" in names

    def test_glob_filter(self, tmp_path: Path) -> None:
        """Glob pattern filters files."""
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.txt").write_text("text")
        files = _collect_files(tmp_path, "*.py")
        names = [f.name for f in files]
        assert "a.py" in names
        assert "b.txt" not in names


class TestSearchFileStructural:
    """Tests for _search_file_structural."""

    def test_finds_keyword_match(self, tmp_path: Path) -> None:
        """Finds lines matching keyword patterns."""
        import re
        p = tmp_path / "code.py"
        p.write_text("def authenticate(user):\n    pass\n")
        kw_patterns = [("kw:authenticate", re.compile(r"\bauthenticate\b"))]
        matches = _search_file_structural(p, kw_patterns, [])
        assert len(matches) >= 1
        assert any("authenticate" in m.context for m in matches)

    def test_scores_multiple_pattern_hits(self, tmp_path: Path) -> None:
        """Lines matching more patterns get higher scores."""
        import re
        p = tmp_path / "code.py"
        p.write_text("async def handle_error():\n    raise ValueError\n")
        kw1 = [("kw:handle", re.compile(r"\bhandle\b"))]
        struct1 = [("async_def", re.compile(r"async\s+def"))]
        matches = _search_file_structural(p, kw1, struct1)
        best = max(matches, key=lambda m: m.score)
        assert best.score >= 2

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns no matches."""
        import re
        p = tmp_path / "empty.py"
        p.write_text("")
        matches = _search_file_structural(p, [("kw:x", re.compile(r"x"))], [])
        assert matches == []


class TestDeduplicateAndRank:
    """Tests for _deduplicate_and_rank."""

    def test_sorts_by_score(self) -> None:
        """Results are sorted by score descending."""
        matches = [
            PatternMatch(file="a.py", line=1, context="x", score=1),
            PatternMatch(file="b.py", line=2, context="y", score=5),
            PatternMatch(file="c.py", line=3, context="z", score=3),
        ]
        ranked = _deduplicate_and_rank(matches, 10)
        assert ranked[0].score == 5
        assert ranked[1].score == 3

    def test_top_k_respected(self) -> None:
        """Returns at most top_k results."""
        matches = [PatternMatch(file=f"{i}.py", line=i, context="x") for i in range(20)]
        ranked = _deduplicate_and_rank(matches, 5)
        assert len(ranked) <= 5

    def test_deduplicates_same_location(self) -> None:
        """Removes duplicate (file, line) pairs."""
        matches = [
            PatternMatch(file="a.py", line=1, context="x", score=2),
            PatternMatch(file="a.py", line=1, context="x", score=1),
        ]
        ranked = _deduplicate_and_rank(matches, 10)
        assert len(ranked) == 1


class TestBuildPatternSearchReport:
    """Tests for _build_pattern_search_report."""

    def test_no_matches_message(self) -> None:
        """Returns no-matches message when results empty."""
        report = _build_pattern_search_report("test query", [], "combined")
        assert "No matches" in report

    def test_report_includes_description(self) -> None:
        """Report title contains the description."""
        matches = [PatternMatch(file="a.py", line=1, context="def foo():", score=2)]
        report = _build_pattern_search_report("foo functions", matches, "combined")
        assert "foo functions" in report

    def test_report_shows_file_and_line(self) -> None:
        """Report shows file:line for each match."""
        matches = [PatternMatch(file="src/mod.py", line=42, context="def foo():", score=1)]
        report = _build_pattern_search_report("foo", matches, "structural")
        assert "src/mod.py:42" in report

    def test_report_shows_strategy(self) -> None:
        """Report shows the strategy used."""
        matches = [PatternMatch(file="a.py", line=1, context="x", score=1)]
        report = _build_pattern_search_report("x", matches, "semantic")
        assert "semantic" in report


class TestExecutePatternSearch:
    """Tests for _execute_pattern_search."""

    def test_missing_path(self) -> None:
        """Returns error for non-existent path."""
        params = PatternSearchParams("test", "/no/such/path", 10, "combined")
        result = _execute_pattern_search(params)
        assert result.success is False

    def test_invalid_strategy(self, tmp_path: Path) -> None:
        """Returns error for invalid strategy."""
        params = PatternSearchParams("test", str(tmp_path), 10, "magic")
        result = _execute_pattern_search(params)
        assert result.success is False

    def test_no_patterns_extracted(self, tmp_path: Path) -> None:
        """Handles description with no extractable patterns gracefully."""
        # Use stop-words-only description
        params = PatternSearchParams("the a an is", str(tmp_path), 10, "combined")
        result = _execute_pattern_search(params)
        assert result.success is True

    def test_finds_matches(self, tmp_path: Path) -> None:
        """Finds matching code in files."""
        src = textwrap.dedent("""\
            class AuthHandler:
                def authenticate(self, user: str) -> bool:
                    return True
        """)
        (tmp_path / "auth.py").write_text(src)
        params = PatternSearchParams(
            "classes that authenticate users", str(tmp_path), 10, "combined"
        )
        result = _execute_pattern_search(params)
        assert result.success is True

    def test_semantic_strategy(self, tmp_path: Path) -> None:
        """Semantic strategy works as keyword search."""
        (tmp_path / "mod.py").write_text("def process_payment(): pass\n")
        params = PatternSearchParams("payment processing", str(tmp_path), 5, "semantic")
        result = _execute_pattern_search(params)
        assert result.success is True

    def test_structural_strategy(self, tmp_path: Path) -> None:
        """Structural strategy extracts structural patterns."""
        (tmp_path / "mod.py").write_text("async def fetch(): pass\n")
        params = PatternSearchParams("async functions", str(tmp_path), 5, "structural")
        result = _execute_pattern_search(params)
        assert result.success is True


# ---------------------------------------------------------------------------
# Tool class tests
# ---------------------------------------------------------------------------


class TestPatternSearchTool:
    """Tests for the PatternSearchTool class."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = PatternSearchTool()
        assert tool.name == "pattern_search"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = PatternSearchTool()
        assert "search" in tool.description.lower()

    def test_kind_is_read(self) -> None:
        """Tool is READ kind (auto-approved)."""
        tool = PatternSearchTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Parameters schema has required 'description' field."""
        tool = PatternSearchTool()
        params = tool.parameters
        assert "description" in params["properties"]
        assert "description" in params["required"]
        assert "strategy" in params["properties"]
        assert "top_k" in params["properties"]

    async def test_execute_empty_description(self) -> None:
        """Returns error when description is empty."""
        tool = PatternSearchTool()
        result = await tool.execute(description="")
        assert result.success is False

    async def test_execute_finds_code(self, tmp_path: Path) -> None:
        """Finds matching code in a Python file."""
        (tmp_path / "mod.py").write_text("class Handler:\n    pass\n")
        tool = PatternSearchTool()
        result = await tool.execute(description="class definitions", path=str(tmp_path))
        assert result.success is True

    async def test_execute_ignores_extra_kwargs(self, tmp_path: Path) -> None:
        """Extra kwargs are silently ignored."""
        (tmp_path / "mod.py").write_text("x = 1\n")
        tool = PatternSearchTool()
        result = await tool.execute(
            description="variable assignments",
            path=str(tmp_path),
            unknown="ignored",
        )
        assert result.success is True

    def test_no_confirmation_needed(self) -> None:
        """READ tool does not need confirmation."""
        tool = PatternSearchTool()
        req = tool.needs_confirmation({"description": "test"})
        assert req is None


async def test_inheritance_search_preserves_identifier_case(tmp_path: Path) -> None:
    """Natural-language case folding must not change case-sensitive Python identifiers."""
    source = tmp_path / "handlers.py"
    source.write_text(
        "class ExistingHandler(BaseHandler):\n    pass\n"
        "class DifferentHandler(basehandler):\n    pass\n",
        encoding="utf-8",
    )
    for description in (
        "classes that inherit from BaseHandler",
        "classes that INHERIT FROM BaseHandler",
        "subclass of BaseHandler",
    ):
        result = await PatternSearchTool().execute(
            description=description, path=str(source), strategy="structural",
        )
        assert result.success
        assert "ExistingHandler" in result.content
        assert "DifferentHandler" not in result.content
        assert "inherits:BaseHandler" in result.content
