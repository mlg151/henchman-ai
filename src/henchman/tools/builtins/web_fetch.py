"""Web fetch tool implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from aiohttp import ClientResponse

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.security import (
    SSRFError,
    sanitize_error_message,
    validate_url,
)
from henchman.tools.utils import coerce_int

_HTTP_ERROR_THRESHOLD = 400
_DEFAULT_MAX_LENGTH = 10_000
_DEFAULT_TIMEOUT_SECONDS = 30



@dataclass
class FetchParams:
    """Parameter object for web fetch operations."""

    url: str
    max_length: int = _DEFAULT_MAX_LENGTH
    timeout: int = _DEFAULT_TIMEOUT_SECONDS


async def _process_fetch_response(response: ClientResponse, max_length: int) -> ToolResult:
    """Process an aiohttp response and return a ToolResult.

    Args:
        response: aiohttp ClientResponse object.
        max_length: Maximum content length to return.

    Returns:
        ToolResult with response content or HTTP error.
    """
    if response.status >= _HTTP_ERROR_THRESHOLD:
        return ToolResult(
            content=f"HTTP Error: {response.status}",
            success=False,
            error=f"HTTP {response.status}",
        )
    content = await response.text()
    if len(content) > max_length:
        content = content[:max_length] + "\n... (truncated)"
    return ToolResult(content=content, success=True)


async def _fetch_content_with_aiohttp(params: FetchParams) -> ToolResult:
    """Fetch URL content via aiohttp and return a ToolResult.

    Args:
        params: Fetch operation parameters.

    Returns:
        ToolResult with page content or error.
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
            session.get(
                params.url,
                timeout=aiohttp.ClientTimeout(total=params.timeout),
            ) as response,
        ):
            return await _process_fetch_response(response, params.max_length)

    except TimeoutError:
        error_msg = f"Request timeout after {params.timeout} seconds"
        return ToolResult(content=error_msg, success=False, error=error_msg)
    except Exception as e:  # pragma: no cover
        sanitized_error = sanitize_error_message(e)
        return ToolResult(
            content=f"Error fetching URL: {sanitized_error}",
            success=False,
            error=sanitized_error,
        )


class WebFetchTool(Tool):
    """Fetch content from a URL.

    This tool fetches the content of a URL and returns it as text.
    """

    _web_fetch_parameters: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum content length to return",
                "default": _DEFAULT_MAX_LENGTH,
            },
            "timeout": {
                "type": "integer",
                "description": "Request timeout in seconds",
                "default": _DEFAULT_TIMEOUT_SECONDS,
            },
        },
        "required": ["url"],
    }

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
        return self._web_fetch_parameters

    @property
    def kind(self: WebFetchTool) -> ToolKind:
        """Tool kind - NETWORK requires confirmation."""
        return ToolKind.NETWORK

    async def execute(
        self: WebFetchTool,
        **kwargs: object,
    ) -> ToolResult:
        """Fetch URL content.

        Args:
            **kwargs: URL, maximum content length, and request timeout.

        Returns:
            ToolResult with URL content or error.
        """
        url = str(kwargs.get("url", ""))
        max_length = coerce_int(kwargs.get("max_length", _DEFAULT_MAX_LENGTH))
        timeout = coerce_int(kwargs.get("timeout", _DEFAULT_TIMEOUT_SECONDS))
        try:
            validated_url = validate_url(url)
        except (SSRFError, ValueError) as e:
            return ToolResult(
                content=f"Security validation failed: {e}",
                success=False,
                error="URL validation failed",
            )

        fetch_params = FetchParams(url=validated_url, max_length=max_length, timeout=timeout)
        return await _fetch_content_with_aiohttp(fetch_params)
