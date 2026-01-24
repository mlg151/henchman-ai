"""Web fetch tool implementation."""


from henchman.tools.base import Tool, ToolKind, ToolResult


class WebFetchTool(Tool):
    """Fetch content from a URL.

    This tool fetches the content of a URL and returns it as text.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "web_fetch"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Fetch content from a URL."

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum content length to return",
                    "default": 10000,
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds",
                    "default": 30,
                },
            },
            "required": ["url"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - NETWORK requires confirmation."""
        return ToolKind.NETWORK

    async def execute(  # type: ignore[override]

        self,
        url: str = "",
        max_length: int = 10000,
        timeout: int = 30,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Fetch URL content.

        Args:
            url: URL to fetch.
            max_length: Maximum content length to return.
            timeout: Request timeout in seconds.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with URL content or error.
        """
        try:
            import aiohttp
        except ImportError:
            return ToolResult(
                content="Error: aiohttp is required for web_fetch",
                success=False,
                error="aiohttp not installed",
            )

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response,
            ):
                if response.status >= 400:
                    return ToolResult(
                        content=f"HTTP Error: {response.status}",
                        success=False,
                        error=f"HTTP {response.status}",
                    )

                content = await response.text()

                # Truncate if needed
                if len(content) > max_length:
                    content = content[:max_length] + "\n... (truncated)"

                return ToolResult(
                    content=content,
                    success=True,
                )

        except TimeoutError:
            return ToolResult(
                content=f"Request timed out after {timeout} seconds",
                success=False,
                error=f"Timeout after {timeout} seconds",
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error fetching URL: {e}",
                success=False,
                error=str(e),
            )
