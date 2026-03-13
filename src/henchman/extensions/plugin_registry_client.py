"""Plugin registry API client."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urljoin

import aiohttp
from pydantic import ValidationError
from typing_extensions import Self

from henchman.extensions.constants import PluginConstants
from henchman.extensions.models import (
    PluginMetadata,
    PluginSearchParams,
    PluginSearchResult,
)

logger = logging.getLogger(__name__)


def _build_search_query_params(
    search_params: PluginSearchParams,
    category: str | None,
) -> dict[str, Any]:
    """Build the query-parameter dict for the plugin search endpoint.

    Args:
        search_params: Search parameters containing page, page_size, query, and category.
        category: Optional category filter (deprecated, use search_params.category instead).

    Returns:
        Dictionary of URL query parameters.
    """
    params: dict[str, Any] = {
        "page": search_params.page,
        "page_size": search_params.page_size,
    }
    if search_params.query:
        params["q"] = search_params.query

    # Use category from search_params if available, otherwise from parameter
    effective_category = search_params.category if search_params.category is not None else category
    if effective_category:
        params["category"] = effective_category

    return params


def _parse_search_result(
    data: dict[str, Any],
    search_params: PluginSearchParams,
) -> PluginSearchResult:
    """Parse the raw JSON response into a PluginSearchResult.

    Falls back to an empty result when the payload fails validation.

    Args:
        data: Raw response dictionary from the registry API.
        search_params: Original search parameters (used for fallback).

    Returns:
        Validated PluginSearchResult.
    """
    try:
        plugins = [PluginMetadata(**p) for p in data.get("plugins", [])]
        return PluginSearchResult(
            plugins=plugins,
            total=data.get("total", 0),
            page=data.get("page", 1),
            page_size=data.get("page_size", PluginConstants.DEFAULT_PAGE_SIZE),
            query=search_params.query,
        )
    except ValidationError as exc:
        logger.exception("Invalid plugin data from registry: %s", exc)  # noqa: TRY401
        return PluginSearchResult(
            plugins=[],
            total=0,
            page=search_params.page,
            page_size=search_params.page_size,
            query=search_params.query,
        )


class PluginRegistryClient:
    """Client for plugin registry API."""

    def __init__(
        self: Self,
        registry_url: str = "https://registry.henchman.ai",
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize registry client.

        Args:
            registry_url: Base URL for plugin registry API.
            session: Optional aiohttp session (will create one if not provided).
        """
        self.registry_url = registry_url
        self._session = session
        self._own_session = session is None

    async def __aenter__(self: Self) -> Self:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(
        self: Self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.close()

    async def initialize(self: Self) -> None:
        """Initialize HTTP session if not already created.

        Returns:
            None
        """
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=PluginConstants.REGISTRY_TIMEOUT),
                headers={"User-Agent": f"Henchman-AI/{__version__}"},
            )

    async def close(self: Self) -> None:
        """Close HTTP session if we own it.

        Returns:
            None
        """
        if self._session and self._own_session:
            await self._session.close()
            self._session = None

    async def search_plugins(
        self: Self,
        search_params: PluginSearchParams,
        category: str | None = None,
    ) -> PluginSearchResult:
        """Search for plugins in the registry.

        Args:
            search_params: Search parameters.
            category: Filter by category.

        Returns:
            PluginSearchResult with matching plugins.

        Raises:
            aiohttp.ClientError: If registry request fails.
            RuntimeError: If client not initialized.
        """
        if self._session is None:
            msg = "Registry client not initialized"
            raise RuntimeError(msg)

        params = _build_search_query_params(search_params, category)
        url = urljoin(self.registry_url, "/api/v1/plugins/search")
        async with self._session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        return _parse_search_result(data, search_params)

    async def get_plugin_info(
        self: Self,
        plugin_name: str,
        version: str | None = None,
    ) -> PluginMetadata | None:
        """Get detailed information about a plugin.

        Args:
            plugin_name: Name of the plugin.
            version: Specific version to fetch (default: latest).

        Returns:
            PluginMetadata or None if not found.

        Raises:
            aiohttp.ClientError: If registry request fails.
            RuntimeError: If client not initialized.
        """
        if self._session is None:
            msg = "Registry client not initialized"
            raise RuntimeError(msg)

        if version:
            url = urljoin(
                self.registry_url,
                f"/api/v1/plugins/{plugin_name}/versions/{version}",
            )
        else:
            url = urljoin(self.registry_url, f"/api/v1/plugins/{plugin_name}")

        async with self._session.get(url) as response:
            if response.status == PluginConstants.HTTP_NOT_FOUND:
                return None
            response.raise_for_status()
            data = await response.json()

        try:
            return PluginMetadata(**data)
        except ValidationError as exc:
            logger.exception("Invalid plugin data from registry: %s", exc)  # noqa: TRY401
            return None


# Import at bottom to avoid circular imports
from henchman.version import VERSION as __version__  # noqa: E402, N811
