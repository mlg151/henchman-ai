"""Tests for the deep_research tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from henchman.tools.base import ToolKind
from henchman.tools.builtins.deep_research import (
    DeepResearchTool,
    ResearchParams,
    ResearchResult,
    ResearchSource,
    _build_report,
    _execute_deep_research,
    _generate_subqueries,
)

# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestGenerateSubqueries:
    """Tests for _generate_subqueries."""

    def test_always_includes_original(self) -> None:
        """Original question is always the first sub-query."""
        params = ResearchParams(question="How does Python GIL work?", max_sources=5)
        queries = _generate_subqueries(params)
        assert queries[0] == "How does Python GIL work?"

    def test_focus_appended(self) -> None:
        """Focus keyword is appended to sub-queries."""
        params = ResearchParams(question="concurrency", max_sources=5, focus="Python")
        queries = _generate_subqueries(params)
        assert any("Python" in q for q in queries)

    def test_max_queries_respected(self) -> None:
        """Number of sub-queries does not exceed max_queries."""
        params = ResearchParams(question="a very long question", max_sources=2)
        queries = _generate_subqueries(params)
        assert len(queries) <= 2

    def test_no_duplicates(self) -> None:
        """No duplicate sub-queries are returned."""
        params = ResearchParams(question="What is X", max_sources=10)
        queries = _generate_subqueries(params)
        assert len(queries) == len(set(queries))

    def test_extra_variants_added(self) -> None:
        """Best practices and example variants are added."""
        params = ResearchParams(question="SQLAlchemy session management", max_sources=10)
        queries = _generate_subqueries(params)
        assert any("best practices" in q for q in queries)
        assert any("example" in q for q in queries)


class TestBuildReport:
    """Tests for _build_report."""

    def test_report_has_title(self) -> None:
        """Report includes the original question as title."""
        result = ResearchResult(question="What is X")
        result.sources.append(
            ResearchSource(title="Test Page", url="https://example.com", snippet="Some content")
        )
        report = _build_report(result)
        assert "What is X" in report

    def test_report_has_sources(self) -> None:
        """Report includes source titles and URLs."""
        result = ResearchResult(question="Q")
        result.sources.append(
            ResearchSource(title="Page A", url="https://a.com", snippet="content A")
        )
        report = _build_report(result)
        assert "Page A" in report
        assert "https://a.com" in report

    def test_report_truncates_long_snippets(self) -> None:
        """Report truncates snippets longer than 800 chars."""
        result = ResearchResult(question="Q")
        long_snippet = "x" * 900
        result.sources.append(
            ResearchSource(title="T", url="http://t.com", snippet=long_snippet)
        )
        report = _build_report(result)
        assert "..." in report

    def test_report_with_errors(self) -> None:
        """Report includes errors section when errors present."""
        result = ResearchResult(question="Q")
        result.errors.append("Connection timeout")
        report = _build_report(result)
        assert "Connection timeout" in report

    def test_report_shows_source_count(self) -> None:
        """Report shows number of sources gathered."""
        result = ResearchResult(question="Q")
        report = _build_report(result)
        assert "0" in report


class TestExecuteDeepResearch:
    """Tests for _execute_deep_research."""

    async def test_missing_aiohttp(self) -> None:
        """Returns error if aiohttp is not installed."""
        import builtins
        real_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "aiohttp":
                raise ImportError("no aiohttp")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            params = ResearchParams(question="test question", max_sources=3)
            result = await _execute_deep_research(params)
        assert result.success is False
        assert "aiohttp" in result.content

    async def test_no_results_returns_message(self) -> None:
        """Returns friendly message when no sources found."""
        with patch(
            "henchman.tools.builtins.deep_research._research_single_query",
            new_callable=AsyncMock,
            return_value=[],
        ), patch(
            "henchman.tools.builtins.deep_research._generate_subqueries",
            return_value=["sub1"],
        ):
            import sys
            import types
            # Inject mock aiohttp so the import inside function succeeds
            mock_aiohttp = types.ModuleType("aiohttp")
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_aiohttp.ClientSession = MagicMock(  # type: ignore[attr-defined]
                return_value=mock_session
            )
            old_mod = sys.modules.get("aiohttp")
            sys.modules["aiohttp"] = mock_aiohttp
            try:
                params = ResearchParams(question="obscure topic xyz", max_sources=1)
                result = await _execute_deep_research(params)
            finally:
                if old_mod is None:
                    del sys.modules["aiohttp"]
                else:
                    sys.modules["aiohttp"] = old_mod

        assert "No results" in result.content or result.success is True


# ---------------------------------------------------------------------------
# Tool class tests
# ---------------------------------------------------------------------------


class TestDeepResearchTool:
    """Tests for the DeepResearchTool class."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = DeepResearchTool()
        assert tool.name == "deep_research"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = DeepResearchTool()
        assert "research" in tool.description.lower()

    def test_kind_is_network(self) -> None:
        """Tool is NETWORK kind (requires confirmation)."""
        tool = DeepResearchTool()
        assert tool.kind == ToolKind.NETWORK

    def test_parameters_schema(self) -> None:
        """Parameters schema has required 'question' field."""
        tool = DeepResearchTool()
        params = tool.parameters
        assert "question" in params["properties"]
        assert "question" in params["required"]
        assert "max_sources" in params["properties"]
        assert "focus" in params["properties"]

    async def test_execute_empty_question(self) -> None:
        """Returns error when question is empty."""
        tool = DeepResearchTool()
        result = await tool.execute(question="")
        assert result.success is False
        assert "required" in result.content.lower()

    async def test_execute_passes_focus(self) -> None:
        """Focus parameter is passed through."""
        tool = DeepResearchTool()
        with patch(
            "henchman.tools.builtins.deep_research._execute_deep_research",
            new_callable=AsyncMock,
        ) as mock_exec:
            from henchman.tools.base import ToolResult
            from henchman.tools.builtins.deep_research import ResearchParams
            mock_exec.return_value = ToolResult(content="report", success=True)
            await tool.execute(question="test", focus="Python")
            expected_params = ResearchParams(question="test", max_sources=5, focus="Python")
            mock_exec.assert_called_once_with(expected_params)

    async def test_execute_ignores_extra_kwargs(self) -> None:
        """Extra kwargs are silently ignored."""
        tool = DeepResearchTool()
        with patch(
            "henchman.tools.builtins.deep_research._execute_deep_research",
            new_callable=AsyncMock,
        ) as mock_exec:
            from henchman.tools.base import ToolResult
            mock_exec.return_value = ToolResult(content="ok", success=True)
            result = await tool.execute(question="q", unknown="ignored")
            assert result.success is True

    def test_needs_confirmation(self) -> None:
        """NETWORK tool always needs confirmation."""
        tool = DeepResearchTool()
        req = tool.needs_confirmation({"question": "test"})
        assert req is not None
