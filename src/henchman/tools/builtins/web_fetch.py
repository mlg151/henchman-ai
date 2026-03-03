"""Web fetch tool implementation."""

from __future__ import annotations

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.security import (
    SSRFError,
    sanitize_error_message,
    validate_url,
)

_HTTP_ERROR_THRESHOLD = 400


class WebFetchTool(Tool):
    """Fetch content from a URL.

    This tool fetches the content of a URL and returns it as text.
    """

    @property
    def name(self: WebFetchTool) -> str:
        """Tool name."""
        return "web_fetch"

    @property
    def description(self: WebFetchTool) -> str:
        """Tool description."""
        return "Fetch content from a URL."

    @property
    def parameters(self: WebFetchTool) -> dict[str, object]:
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
    def kind(self: WebFetchTool) -> ToolKind:
        """Tool kind - NETWORK requires confirmation."""
        return ToolKind.NETWORK

    async def execute(  # type: ignore[override]
        self: WebFetchTool,
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
        # Validate URL to prevent SSRF attacks
        try:
            validated_url = validate_url(url)
        except (SSRFError, ValueError) as e:
            return ToolResult(
                content=f"Security validation failed: {e}",
                success=False,
                error="URL validation failed",
            )

        try:
            import aiohttp  # noqa: PLC0415
        except ImportError:
            return ToolResult(
                content="Error: aiohttp is required for web_fetch",
                success=False,
                error="aiohttp not installed",
            )

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.get(validated_url, timeout=aiohttp.ClientTimeout(total=timeout)) as response,
            ):
                if response.status >= _HTTP_ERROR_THRESHOLD:
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
            sanitized_error = sanitize_error_message(f"Request timed out after {timeout} seconds")
            return ToolResult(
                content=sanitized_error,
                success=False,
                error=sanitized_error,
            )
        except Exception as e:  # pragma: no cover  # noqa: BLE001
            sanitized_error = sanitize_error_message(e)
            return ToolResult(
                content=f"Error fetching URL: {sanitized_error}",
                success=False,
                error=sanitized_error,
            )
