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


class PluginRegistryClient:
    """Client for plugin registry API."""

    def __init__(
        self,
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

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def initialize(self) -> None:
        """Initialize HTTP session if not already created."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=PluginConstants.REGISTRY_TIMEOUT),
                headers={"User-Agent": f"Henchman-AI/{__version__}"},
            )

    async def close(self) -> None:
        """Close HTTP session if we own it."""
        if self._session and self._own_session:
            await self._session.close()
            self._session = None

    async def search_plugins(
        self,
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

        sp_page = search_params.page
        sp_page_size = search_params.page_size
        sp_query = search_params.query
        params: dict[str, Any] = {
            "page": sp_page,
            "page_size": sp_page_size,
        }
        if sp_query:
            params["q"] = sp_query
        if category:
            params["category"] = category

        url = urljoin(self.registry_url, "/api/v1/plugins/search")
        async with self._session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

        try:
            # Convert list of dicts to PluginMetadata objects
            plugins = [PluginMetadata(**plugin_data) for plugin_data in data.get("plugins", [])]
            return PluginSearchResult(
                plugins=plugins,
                total=data.get("total", 0),
                page=data.get("page", 1),
                page_size=data.get("page_size", PluginConstants.DEFAULT_PAGE_SIZE),
                query=search_params.query,
            )
        except ValidationError as e:
            logger.exception("Invalid plugin data from registry: %s", e)
            # Return empty result on validation error
            return PluginSearchResult(
                plugins=[],
                total=0,
                page=search_params.page,
                page_size=search_params.page_size,
                query=search_params.query,
            )

    async def get_plugin_info(
        self,
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

        # Build URL for plugin metadata
        if version:
            url = urljoin(self.registry_url, f"/api/v1/plugins/{plugin_name}/versions/{version}")
        else:
            url = urljoin(self.registry_url, f"/api/v1/plugins/{plugin_name}")

        async with self._session.get(url) as response:
            if response.status == PluginConstants.HTTP_NOT_FOUND:
                return None
            response.raise_for_status()
            data = await response.json()

        try:
            return PluginMetadata(**data)
        except ValidationError as e:
            logger.exception("Invalid plugin data from registry: %s", e)
            return None


# Import at bottom to avoid circular imports
from henchman.version import VERSION as __version__
