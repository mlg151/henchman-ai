"""Web search tool implementation using DuckDuckGo."""

from __future__ import annotations

from henchman.tools.base import Tool, ToolKind, ToolResult

_HTTP_ERROR_THRESHOLD = 400


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
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    @property
    def kind(self: DuckDuckGoSearchTool) -> ToolKind:
        """Tool kind - NETWORK requires confirmation."""
        return ToolKind.NETWORK

    async def execute(  # type: ignore[override]
        self: DuckDuckGoSearchTool,
        query: str = "",
        max_results: int = 5,
        **kwargs: object,
    ) -> ToolResult:
        """Execute web search.

        Args:
            query: Search query.
            max_results: Maximum results to return.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with search results.
        """
        try:  # pragma: no cover
            import aiohttp
            from bs4 import BeautifulSoup
        except ImportError:  # pragma: no cover
            return ToolResult(
                content="Error: aiohttp and beautifulsoup4 are required for web_search",
                success=False,
                error="Dependencies not installed. Please run: pip install aiohttp beautifulsoup4",
            )

        try:  # pragma: no cover
            # DuckDuckGo HTML search URL
            url = f"https://html.duckduckgo.com/html/?q={query}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            }

            async with (
                aiohttp.ClientSession(headers=headers) as session,
                session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response,
            ):
                if response.status >= _HTTP_ERROR_THRESHOLD:
                    return ToolResult(
                        content=f"Search failed with HTTP {response.status}",
                        success=False,
                        error=f"HTTP {response.status}",
                    )

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                results = []
                # DuckDuckGo HTML results are usually in 'result' class divs
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

                if not results:
                    return ToolResult(
                        content="No results found.",
                        success=True,
                    )

                return ToolResult(
                    content="\n".join(results),
                    success=True,
                )

        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error performing search: {e}",
                success=False,
                error=str(e),
            )
