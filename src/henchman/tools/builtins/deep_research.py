"""Deep research tool - multi-query web research with synthesis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

from henchman.tools.base import Tool, ToolKind, ToolResult

_DEFAULT_MAX_SOURCES = 5
_DEFAULT_TIMEOUT = 15
_MAX_FETCH_LENGTH = 5000
_HTTP_ERROR_THRESHOLD = 400
_MAX_SUBQUERIES = 5
_MIN_SENTENCE_LENGTH = 10
_REPORT_EXCERPT_LENGTH = 800


@dataclass
class ResearchSource:
    """A single research source with title, URL, and content snippet.

    Attributes:
        title: Page title or query label.
        url: Source URL.
        snippet: Extracted content snippet.
    """

    title: str
    url: str
    snippet: str


@dataclass
class ResearchResult:
    """Aggregated result from a deep research run.

    Attributes:
        question: The original research question.
        sources: List of sources gathered.
        errors: Any errors encountered during research.
    """

    question: str
    sources: list[ResearchSource] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class ResearchParams:
    """Parameters for deep research operations.

    Groups related parameters to address primitive obsession code smell.

    Attributes:
        question: Research question or topic to investigate.
        max_sources: Maximum number of sources to gather.
        focus: Optional focus keyword to narrow sub-queries.
    """

    question: str
    max_sources: int = _DEFAULT_MAX_SOURCES
    focus: str | None = None


def _generate_subqueries(params: ResearchParams) -> list[str]:
    """Generate sub-queries from a research question.

    Splits a broad question into focused sub-queries by extracting
    key phrases and appending optional focus context.

    Args:
        params: Research parameters containing question, focus, and max_sources.

    Returns:
        List of sub-query strings (at least 1, at most max_sources).
    """
    base = params.question.strip()
    focus_suffix = f" {params.focus}" if params.focus else ""

    # Always include the original question as the first query
    queries: list[str] = [base + focus_suffix]

    # Try to extract "what", "how", "why" sub-questions
    sentences = re.split(r"[.?!]", base)
    for sentence in sentences[1:]:
        sentence = sentence.strip()
        if len(sentence) > _MIN_SENTENCE_LENGTH:
            queries.append(sentence + focus_suffix)

    # Add a "best practices" and "examples" variant for richer results
    short = base[:60]
    queries.append(f"{short} best practices{focus_suffix}")
    queries.append(f"{short} example{focus_suffix}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique.append(q)

    return unique[:params.max_sources]


async def _search_duckduckgo(query: str, session: object) -> list[tuple[str, str]]:
    """Search DuckDuckGo and return (title, url) pairs.

    Args:
        query: Search query string.
        session: Active aiohttp ClientSession.

    Returns:
        List of (title, url) tuples from search results.
    """
    import aiohttp  # noqa: PLC0415
    from bs4 import BeautifulSoup  # noqa: PLC0415

    url = f"https://html.duckduckgo.com/html/?q={query}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
    }
    try:
        async with session.get(  # type: ignore[attr-defined]
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=_DEFAULT_TIMEOUT),
        ) as resp:
            if resp.status >= _HTTP_ERROR_THRESHOLD:
                return []
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            results: list[tuple[str, str]] = []
            for div in soup.find_all("div", class_="result")[:3]:
                a = div.find("a", class_="result__a")
                if a:
                    href: str = str(a.get("href") or "")
                    results.append((a.get_text(strip=True), href))
            return results
    except Exception:  # noqa: BLE001  # pragma: no cover
        return []


async def _fetch_snippet(url: str, session: object) -> str:
    """Fetch and extract a text snippet from a URL.

    Args:
        url: URL to fetch content from.
        session: Active aiohttp ClientSession.

    Returns:
        Extracted text snippet (up to _MAX_FETCH_LENGTH chars).
    """
    import aiohttp  # noqa: PLC0415

    try:
        async with session.get(  # type: ignore[attr-defined]
            url,
            timeout=aiohttp.ClientTimeout(total=_DEFAULT_TIMEOUT),
        ) as resp:
            if resp.status >= _HTTP_ERROR_THRESHOLD:
                return ""
            text = await resp.text()
            # Strip HTML tags roughly
            clean = re.sub(r"<[^>]+>", " ", text)
            clean = re.sub(r"\s+", " ", clean).strip()
            return clean[:_MAX_FETCH_LENGTH]
    except Exception:  # noqa: BLE001  # pragma: no cover
        return ""


async def _research_single_query(
    query: str,
    session: object,
) -> list[ResearchSource]:
    """Run a single query and return gathered sources.

    Args:
        query: Search query to run.
        session: Active aiohttp ClientSession.

    Returns:
        List of ResearchSource objects found for the query.
    """
    hits = await _search_duckduckgo(query, session)
    sources: list[ResearchSource] = []
    for title, url in hits[:1]:  # Fetch top result per sub-query
        if url:
            snippet = await _fetch_snippet(url, session)
            if snippet:
                sources.append(ResearchSource(title=title, url=url, snippet=snippet))
    return sources


def _build_report(result: ResearchResult) -> str:
    """Build a Markdown research report from gathered sources.

    Args:
        result: Aggregated research result with sources and errors.

    Returns:
        Formatted Markdown report string.
    """
    lines: list[str] = [
        f"# Research Report: {result.question}\n",
        f"**Sources gathered:** {len(result.sources)}\n",
    ]

    for i, src in enumerate(result.sources, 1):
        lines.append(f"## Source {i}: {src.title}")
        lines.append(f"**URL:** {src.url}\n")
        # Show excerpt of snippet
        excerpt = src.snippet[:_REPORT_EXCERPT_LENGTH].rstrip()
        if len(src.snippet) > _REPORT_EXCERPT_LENGTH:
            excerpt += "..."
        lines.append(excerpt)
        lines.append("")

    if result.errors:
        lines.append("## Errors encountered")
        for err in result.errors:
            lines.append(f"- {err}")

    return "\n".join(lines)


async def _execute_deep_research(
    params: ResearchParams,
) -> ToolResult:
    """Execute the full deep research pipeline.

    Args:
        params: Research parameters containing question, max_sources, and focus.

    Returns:
        ToolResult with a synthesized Markdown research report.
    """
    try:
        import aiohttp  # noqa: PLC0415
    except ImportError:
        return ToolResult(
            content="Error: aiohttp and beautifulsoup4 are required for deep_research",
            success=False,
            error="aiohttp not installed",
        )

    subqueries = _generate_subqueries(params)
    result = ResearchResult(question=params.question)

    try:
        async with aiohttp.ClientSession() as session:
            for query in subqueries:
                if len(result.sources) >= params.max_sources:
                    break
                sources = await _research_single_query(query, session)
                result.sources.extend(sources)
    except Exception as e:  # noqa: BLE001  # pragma: no cover
        result.errors.append(str(e))

    if not result.sources and not result.errors:
        return ToolResult(
            content=f"No results found for: {params.question}",
            success=True,
        )

    return ToolResult(content=_build_report(result), success=True)


class DeepResearchTool(Tool):
    """End-to-end web research tool that synthesizes multiple sources.

    Decomposes a research question into sub-queries, searches the web
    for each, fetches the top result, and synthesizes findings into a
    structured Markdown report with citations. Replaces the manual cycle
    of web_search + web_fetch + manual synthesis.
    """

    _parameters: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Research question or topic to investigate",
            },
            "max_sources": {
                "type": "integer",
                "description": "Maximum number of sources to gather",
                "default": _DEFAULT_MAX_SOURCES,
            },
            "focus": {
                "type": "string",
                "description": (
                    "Optional focus keyword to narrow sub-queries "
                    "(e.g. 'Python', 'security', 'performance')"
                ),
            },
        },
        "required": ["question"],
    }

    @property
    def name(self: DeepResearchTool) -> str:
        """Tool name."""
        return "deep_research"

    @property
    def description(self: DeepResearchTool) -> str:
        """Tool description."""
        return (
            "Perform end-to-end web research on a question: generates sub-queries, "
            "searches the web for each, fetches top results, and synthesizes findings "
            "into a structured Markdown report with citations. Use instead of multiple "
            "web_search + web_fetch calls."
        )
    @property
    def kind(self: DeepResearchTool) -> ToolKind:
        """Tool kind - NETWORK requires confirmation."""
        return ToolKind.NETWORK

    async def execute(  # type: ignore[override]
        self: DeepResearchTool,
        question: str = "",
        max_sources: int = _DEFAULT_MAX_SOURCES,
        focus: str | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Execute deep research on a question.

        Args:
            question: Research question or topic to investigate.
            max_sources: Maximum number of sources to gather.
            focus: Optional focus keyword to narrow sub-queries.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with a synthesized Markdown research report.
        """
        if not question:
            return ToolResult(
                content="Error: question is required",
                success=False,
                error="question is required",
            )
        params = ResearchParams(
            question=question,
            max_sources=max_sources,
            focus=focus,
        )
        return await _execute_deep_research(params)
