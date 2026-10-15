"""Web search tool implementation using DuckDuckGo."""

from __future__ import annotations

import aiohttp
from bs4 import BeautifulSoup

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.utils import coerce_int

_HTTP_ERROR_THRESHOLD = 400
_DEFAULT_TIMEOUT = 10
_DEFAULT_MAX_RESULTS = 5
_DDG_SEARCH_BASE_URL = "https://html.duckduckgo.com/html/"
_DDG_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
_DEPS_AVAILABLE = True

def _build_ddg_request_headers() -> dict[str, str]:
    """Return HTTP request headers for DuckDuckGo searches."""
    return {"User-Agent": _DDG_USER_AGENT}


def _parse_ddg_results(soup: BeautifulSoup, max_results: int) -> list[str]:
    """Extract formatted search results from a parsed DuckDuckGo page.

    Args:
        soup: Parsed BeautifulSoup document.
        max_results: Maximum number of results to return.

    Returns:
        List of formatted result strings (title, URL, snippet).
    """
    results: list[str] = []
    for i, result in enumerate(soup.find_all("div", class_="result")):
        if i >= max_results:
            break
        title_elem = result.find("a", class_="result__a")
        snippet_elem = result.find("a", class_="result__snippet")
        if title_elem:
            title = title_elem.get_text(strip=True)
            link = title_elem.get("href", "")
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
            results.append(f"### {title}\nURL: {link}\n{snippet}\n")
    return results


def _build_search_url(query: str) -> str:
    """Build the DuckDuckGo HTML search URL."""
    return f"{_DDG_SEARCH_BASE_URL}?q={query}"


async def _search_duckduckgo_results(query: str, max_results: int) -> ToolResult:
    """Run a DuckDuckGo search and return formatted results."""
    async with (
        aiohttp.ClientSession(headers=_build_ddg_request_headers()) as session,
        session.get(
            _build_search_url(query),
            timeout=aiohttp.ClientTimeout(total=_DEFAULT_TIMEOUT),
        ) as response,
    ):
        if response.status >= _HTTP_ERROR_THRESHOLD:
            return ToolResult(
                content=f"Search failed with HTTP {response.status}",
                success=False,
                error=f"HTTP {response.status}",
            )

        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        results = _parse_ddg_results(soup, max_results)
        if not results:
            return ToolResult(content="No results found.", success=True)
        return ToolResult(content="\n".join(results), success=True)


class DuckDuckGoSearchTool(Tool):
    """Search the web using DuckDuckGo.

    This tool searches DuckDuckGo and returns a summary of the results.
    """

    @property
    def name(self: DuckDuckGoSearchTool) -> str:
        """Tool name."""
        return "web_search"

    @property
    def description(self: DuckDuckGoSearchTool) -> str:
        """Tool description."""
        return "Search the web for information."

    @property
    def parameters(self: DuckDuckGoSearchTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": _DEFAULT_MAX_RESULTS,
                },
            },
            "required": ["query"],
        }

    @property
    def kind(self: DuckDuckGoSearchTool) -> ToolKind:
        """Tool kind - NETWORK requires confirmation."""
        return ToolKind.NETWORK

    async def execute(
        self: DuckDuckGoSearchTool,
        **kwargs: object,
    ) -> ToolResult:
        """Execute web search.

        Args:
            **kwargs: Search query and maximum result count.

        Returns:
            ToolResult with search results.
        """
        query = str(kwargs.get("query", ""))
        max_results = coerce_int(kwargs.get("max_results", _DEFAULT_MAX_RESULTS))
        if not _DEPS_AVAILABLE:  # pragma: no cover
            return ToolResult(
                content="Error: aiohttp and beautifulsoup4 are required for web_search",
                success=False,
                error="Dependencies not installed. Please run: pip install aiohttp beautifulsoup4",
            )
        try:  # pragma: no cover
            return await _search_duckduckgo_results(query, max_results)
        except (aiohttp.ClientError, OSError, RuntimeError, TimeoutError, ValueError) as e:  # pragma: no cover
            return ToolResult(
                content=f"Error performing search: {e}",
                success=False,
                error=str(e),
            )
