"""Web fetch tool implementation."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import ClassVar

from aiohttp import ClientResponse

from henchman.tools.access_policy import check_network_access
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.http_security import checked_http_url, public_http_session, request_origin
from henchman.tools.security import (
    SSRFError,
    sanitize_error_message,
    validate_url,
)
from henchman.tools.utils import coerce_int

_HTTP_ERROR_THRESHOLD = 400
_DEFAULT_MAX_LENGTH = 10_000
_DEFAULT_TIMEOUT_SECONDS = 30
_MAX_REDIRECTS = 10
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})



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
        url = checked_http_url(params.url)
        headers = {}
        if url.user is not None:
            if ":" in url.user:
                raise SSRFError("URL authentication username must not contain a colon")
            credentials = f"{url.user}:{url.password or ''}".encode("latin1")
            headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")
        url = url.with_user(None)
        async with asyncio.timeout(params.timeout if params.timeout > 0 else None):
            for redirect_count in range(_MAX_REDIRECTS + 1):
                assert url.raw_host is not None
                check_network_access(url.raw_host)
                async with public_http_session(authority=url) as session, session.get(
                    url, headers=headers, allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=params.timeout),
                ) as response:
                    check_network_access(url.raw_host)
                    if response.status not in _REDIRECT_STATUSES or not response.headers.get("Location"):
                        result = await _process_fetch_response(response, params.max_length)
                        check_network_access(url.raw_host)
                        return result
                    if redirect_count == _MAX_REDIRECTS:
                        raise SSRFError("HTTP redirect limit exceeded")
                    from yarl import URL

                    destination = checked_http_url(str(url.join(URL(response.headers["Location"]))))
                    if destination.user is not None:
                        raise SSRFError("Redirect URLs must not introduce credentials")
                    if request_origin(destination) != request_origin(url):
                        # Once removed, auth stays absent even if a later hop
                        # returns to the initial origin. Cookies are disabled.
                        headers = {}
                    url = destination
        raise SSRFError("HTTP redirect limit exceeded")

    except SSRFError as exc:
        return ToolResult(content=f"Security validation failed: {exc}",
                          success=False, error="URL security validation failed")
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
