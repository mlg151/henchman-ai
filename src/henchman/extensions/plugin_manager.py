"""Plugin manager for Henchman-AI plugin marketplace."""

from __future__ import annotations

import logging
import shutil
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from henchman.extensions.constants import PluginConstants
from henchman.extensions.manager import ExtensionManager
from henchman.extensions.models import (
    PluginInstallation,
    PluginMetadata,
    PluginSearchParams,
    PluginSearchResult,
    PluginUpdateInfo,
    SecurityReport,
)
from henchman.extensions.plugin_compatibility import PluginCompatibilityChecker
from henchman.extensions.plugin_database import PluginDatabase
from henchman.extensions.plugin_installer import PluginInstaller
from henchman.extensions.plugin_registry_client import PluginRegistryClient
from henchman.extensions.plugin_security_scanner import PluginSecurityScanner

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

PLUGIN_MANAGER_NOT_INITIALIZED = "Plugin manager not initialized"
SEARCH_DEPRECATION_STACKLEVEL = 3


@dataclass(frozen=True)
class _LegacySearchRequest:
    """Legacy search arguments kept for backward compatibility."""

    query: str | None
    page: int
    page_size: int
    category: str | None

    def uses_legacy_arguments(self: _LegacySearchRequest) -> bool:
        """Return whether any legacy argument was used explicitly."""
        return any(
            (
                self.query is not None,
                self.page != 1,
                self.page_size != PluginConstants.DEFAULT_PAGE_SIZE,
                self.category is not None,
            ),
        )

    def to_search_params(self: _LegacySearchRequest) -> PluginSearchParams:
        """Build structured search params from legacy arguments."""
        return PluginSearchParams(
            query=self.query,
            page=self.page,
            page_size=self.page_size,
            category=self.category,
        )


async def _check_plugin_compatibility(plugin_name: str, metadata: PluginMetadata) -> None:
    """Raise when a plugin is incompatible with the current environment."""
    if not await PluginCompatibilityChecker.check_compatibility(metadata):
        msg = f"Plugin '{plugin_name}' is not compatible with this system"
        raise RuntimeError(msg)


async def _log_plugin_permissions(
    plugin_name: str,
    metadata: PluginMetadata,
    *,
    confirm_permissions: bool,
) -> None:
    """Log requested permissions before installation."""
    if confirm_permissions and metadata.security.permissions:
        logger.info(
            "Plugin '%s' requires permissions: %s",
            plugin_name,
            ", ".join(metadata.security.permissions),
        )


def _make_plugin_installation(
    metadata: PluginMetadata,
    installation_path: Path,
) -> PluginInstallation:
    """Build a PluginInstallation from metadata and path."""
    return PluginInstallation(
        metadata=metadata,
        installed_version=metadata.version,
        installation_path=str(installation_path),
    )


def _resolve_plugin_extension_file(installation: PluginInstallation) -> Path | None:
    """Return the installed extension.py file when present."""
    if not installation.installation_path:
        return None
    ext_file = Path(installation.installation_path) / "extension.py"
    return ext_file if ext_file.exists() else None


def _warn_if_legacy_search_params(
    search_params: PluginSearchParams | None,
    legacy_request: _LegacySearchRequest,
) -> None:
    """Emit a deprecation warning for legacy search arguments."""
    if search_params is None and legacy_request.uses_legacy_arguments():
        warnings.warn(
            "Using individual query/page/page_size/category parameters is deprecated. "
            "Use the search_params parameter instead.",
            DeprecationWarning,
            stacklevel=SEARCH_DEPRECATION_STACKLEVEL,
        )


def _build_search_params(
    search_params: PluginSearchParams | None,
    legacy_request: _LegacySearchRequest,
) -> PluginSearchParams:
    """Return structured search params for the registry client."""
    _warn_if_legacy_search_params(search_params, legacy_request)
    return search_params or legacy_request.to_search_params()


def _remove_plugin_files(installation_path: str) -> None:
    """Best-effort removal of installed plugin files."""
    try:
        shutil.rmtree(installation_path, ignore_errors=True)
    except OSError as exc:
        logger.warning("Failed to remove plugin files: %s", exc)


def _load_plugin_extension_from_installation(
    load_extension_from_file: Callable[[Path, str], None],
    installation: PluginInstallation,
) -> None:
    """Load an installed plugin extension when its file exists."""
    ext_file = _resolve_plugin_extension_file(installation)
    if ext_file is None:
        return
    try:
        load_extension_from_file(ext_file, installation.metadata.name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to load extension for plugin '%s': %s",
            installation.metadata.name,
            exc,
        )


class PluginManager(ExtensionManager):
    """Extension manager with plugin marketplace support."""

    def __init__(
        self: PluginManager,
        registry_url: str = "https://registry.henchman.ai",
        data_dir: Path | None = None,
    ) -> None:
        """Initialize the plugin manager."""
        super().__init__()
        self.registry_url = registry_url
        self.data_dir = data_dir or Path.home() / ".henchman" / "plugins"
        self.db_path = self.data_dir / "plugins.db"
        self.database = PluginDatabase(self.db_path)
        self.registry_client: PluginRegistryClient | None = None
        self.installer: PluginInstaller | None = None
        self.security_scanner = PluginSecurityScanner()
        self.installed_plugins: dict[str, PluginInstallation] = {}
        self._initialized = False

    async def initialize(self: PluginManager) -> None:
        """Initialize storage, clients, and enabled plugins.
        
        Returns:
            None
        """
        if self._initialized:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        await self.database.initialize()
        self.installed_plugins = await self.database.load_installations()
        for installation in self.installed_plugins.values():
            if installation.enabled:
                await self._load_plugin_extension(installation)
        self.registry_client = PluginRegistryClient(registry_url=self.registry_url, session=None)
        await self.registry_client.initialize()
        self.installer = PluginInstaller(self.data_dir)
        self._initialized = True
        logger.info("Plugin manager initialized")

    async def close(self: PluginManager) -> None:
        """Close the registry client and reset initialization state.
        
        Returns:
            None
        """
        if self.registry_client:
            await self.registry_client.close()
            self.registry_client = None
        self.installer = None
        self._initialized = False

    async def search_plugins(
        self: PluginManager,
        query: str | None = None,
        page: int = 1,
        page_size: int = PluginConstants.DEFAULT_PAGE_SIZE,
        category: str | None = None,
        *,
        search_params: PluginSearchParams | None = None,
    ) -> PluginSearchResult:
        """Search the plugin registry.
        
        Args:
            query: Search query string. If None, returns all plugins.
            page: Page number (1-indexed). Defaults to 1.
            page_size: Results per page. Defaults to PluginConstants.DEFAULT_PAGE_SIZE.
            category: Filter by category. If None, searches all categories.
            search_params: Advanced search parameters. If provided, overrides individual
                query/page/page_size/category parameters.
        
        Returns:
            PluginSearchResult containing matching plugins and pagination info.
        
        Raises:
            RuntimeError: If plugin manager is not initialized.
        """
        if not self._initialized or not self.registry_client:
            raise RuntimeError(PLUGIN_MANAGER_NOT_INITIALIZED)
        legacy_request = _LegacySearchRequest(query, page, page_size, category)
        resolved_search_params = _build_search_params(search_params, legacy_request)
        return await self.registry_client.search_plugins(resolved_search_params)

    async def get_plugin_info(
        self: PluginManager,
        plugin_name: str,
        version: str | None = None,
    ) -> PluginMetadata | None:
        """Fetch plugin metadata from the registry.
        
        Args:
            plugin_name: Name of the plugin to fetch metadata for.
            version: Optional specific version of the plugin. If None, fetches
                the latest version.
        
        Returns:
            PluginMetadata object containing plugin information if found,
            None if the plugin does not exist in the registry.
        
        Raises:
            RuntimeError: If plugin manager is not initialized.
        """
        if not self._initialized or not self.registry_client:
            raise RuntimeError(PLUGIN_MANAGER_NOT_INITIALIZED)
        return await self.registry_client.get_plugin_info(plugin_name, version)

    async def install_plugin(
        self: PluginManager,
        plugin_name: str,
        version: str | None = None,
        *,
        confirm_permissions: bool = True,
    ) -> PluginInstallation:
        """Install a plugin from the registry.
        
        Args:
            plugin_name: Name of the plugin to install.
            version: Optional specific version of the plugin. If None, installs
                the latest version.
            confirm_permissions: Whether to log and confirm plugin permissions
                before installation. Defaults to True.
        
        Returns:
            PluginInstallation object containing installation details including
            metadata, installation path, and timestamps.
        
        Raises:
            RuntimeError: If plugin manager is not initialized or plugin is
                incompatible with the current environment.
            ValueError: If plugin is already installed or not found in registry.
        """
        self._validate_initialization()
        self._check_already_installed(plugin_name)
        metadata = await self._get_plugin_metadata(plugin_name, version)
        await _check_plugin_compatibility(plugin_name, metadata)
        await self._handle_permissions(plugin_name, metadata, confirm_permissions)
        await self._install_dependencies(metadata)
        installation_path = await self._install_plugin_package(plugin_name, metadata)
        installation = _make_plugin_installation(metadata, installation_path)
        await self.database.save_installation(installation)
        await self._load_plugin_extension(installation)
        self._update_installation_cache(plugin_name, installation)
        logger.info("Installed plugin '%s' v%s", plugin_name, metadata.version)
        return installation

    def _validate_initialization(self: PluginManager) -> None:
        """Raise when the manager has not been initialized."""
        if not self._initialized or not self.registry_client or not self.installer:
            raise RuntimeError(PLUGIN_MANAGER_NOT_INITIALIZED)

    def _check_already_installed(self: PluginManager, plugin_name: str) -> None:
        """Raise when a plugin is already installed."""
        if plugin_name in self.installed_plugins:
            msg = f"Plugin '{plugin_name}' is already installed"
            raise ValueError(msg)

    async def _get_plugin_metadata(
        self: PluginManager,
        plugin_name: str,
        version: str | None,
    ) -> PluginMetadata:
        """Return plugin metadata or raise when missing."""
        metadata = await self.get_plugin_info(plugin_name, version)
        if not metadata:
            msg = f"Plugin '{plugin_name}' not found in registry"
            raise ValueError(msg)
        return metadata

    async def _handle_permissions(
        self: PluginManager,
        plugin_name: str,
        metadata: PluginMetadata,
        confirm_permissions: bool,  # noqa: FBT001
    ) -> None:
        """Backward-compatible wrapper for permission logging."""
        await _log_plugin_permissions(
            plugin_name,
            metadata,
            confirm_permissions=confirm_permissions,
        )

    async def _install_dependencies(self: PluginManager, metadata: PluginMetadata) -> None:
        """Install plugin dependencies when any are declared."""
        if metadata.dependencies and self.installer:
            await self.installer.install_dependencies(metadata.dependencies)

    async def _install_plugin_package(
        self: PluginManager,
        plugin_name: str,
        metadata: PluginMetadata,
    ) -> Path:
        """Install the plugin package and return its directory."""
        if not self.installer:
            msg = "Plugin installer not available"
            raise RuntimeError(msg)
        try:
            return await self.installer.install_plugin_package(metadata)
        except Exception as exc:
            msg = f"Failed to install plugin '{plugin_name}': {exc}"
            raise RuntimeError(msg) from exc

    def _update_installation_cache(
        self: PluginManager,
        plugin_name: str,
        installation: PluginInstallation,
    ) -> None:
        """Update the in-memory installation cache."""
        installed_plugins = self.installed_plugins
        installed_plugins[plugin_name] = installation

    async def uninstall_plugin(self: PluginManager, plugin_name: str) -> None:
        """Uninstall a plugin and remove its local state.
        
        Args:
            plugin_name: Name of the plugin to uninstall.
            
        Returns:
            None
            
        Raises:
            RuntimeError: If plugin manager is not initialized.
            ValueError: If plugin is not installed.
        """
        installation = self._get_installation_or_raise(plugin_name)
        self.unregister(plugin_name)
        if installation.installation_path:
            _remove_plugin_files(installation.installation_path)
        await self.database.delete_installation(plugin_name)
        del self.installed_plugins[plugin_name]
        logger.info("Uninstalled plugin '%s'", plugin_name)

    async def update_plugin(self: PluginManager, plugin_name: str) -> PluginInstallation | None:
        """Update an installed plugin to the latest version.
        
        Args:
            plugin_name: Name of the plugin to update.
        
        Returns:
            PluginInstallation object for the newly installed version if update
            was successful and a newer version was available, None if the plugin
            was not found in the registry or was already up-to-date.
        
        Raises:
            RuntimeError: If plugin manager is not initialized.
            ValueError: If plugin is not installed.
            Exception: If plugin installation fails during the update process.
        """
        current_installation = self._get_installation_or_raise(plugin_name)
        latest_metadata = await self.get_plugin_info(plugin_name)
        if not latest_metadata:
            logger.warning("Plugin '%s' not found in registry", plugin_name)
            return None
        if latest_metadata.version == current_installation.installed_version:
            logger.info("Plugin '%s' is already up-to-date", plugin_name)
            return None
        await self.uninstall_plugin(plugin_name)
        try:
            return await self.install_plugin(plugin_name, confirm_permissions=False)
        except Exception:
            logger.exception("Failed to update plugin '%s'", plugin_name)
            raise

    async def check_updates(self: PluginManager) -> dict[str, PluginUpdateInfo]:
        """Return available updates for installed plugins."""
        updates: dict[str, PluginUpdateInfo] = {}
        for plugin_name, installation in self.installed_plugins.items():
            latest_metadata = await self.get_plugin_info(plugin_name)
            if not latest_metadata or latest_metadata.version == installation.installed_version:
                continue
            updates[plugin_name] = PluginUpdateInfo(
                plugin_name=plugin_name,
                current_version=installation.installed_version,
                latest_version=latest_metadata.version,
            )
        return updates

    async def scan_security(self: PluginManager, plugin_name: str) -> SecurityReport:
        """Run a security scan for an installed plugin.
        
        Args:
            plugin_name: Name of the installed plugin to scan.
            
        Returns:
            SecurityReport with scan results including warnings, errors, and risk level.
            
        Raises:
            ValueError: If the plugin is not installed.
        """
        installation = self._get_installation_or_raise(plugin_name)
        return self.security_scanner.scan(installation)

    def _get_installation_or_raise(self: PluginManager, plugin_name: str) -> PluginInstallation:
        """Return an installation or raise when it is missing."""
        if plugin_name not in self.installed_plugins:
            msg = f"Plugin '{plugin_name}' is not installed"
            raise ValueError(msg)
        return self.installed_plugins[plugin_name]

    async def _load_plugin_extension(self: PluginManager, installation: PluginInstallation) -> None:
        """Load the installed extension entry point file."""
        _load_plugin_extension_from_installation(self._load_extension_from_file, installation)
