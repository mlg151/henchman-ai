"""Plugin manager for Henchman-AI plugin marketplace.

This module extends the basic ExtensionManager with remote plugin
discovery, installation, and management capabilities.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

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
from henchman.utils.registry import _set_dict_item

logger = logging.getLogger(__name__)


class PluginManager(ExtensionManager):
    """Enhanced extension manager with plugin marketplace capabilities.

    This class extends ExtensionManager with:
    - Remote plugin discovery via registry API
    - Plugin installation from various sources (PyPI, GitHub, etc.)
    - Version management and updates
    - Security scanning and sandboxing
    - Local plugin database for tracking installations

    Example:
        >>> manager = PluginManager()
        >>> await manager.initialize()
        >>> results = await manager.search_plugins("github")
        >>> await manager.install_plugin("github-integration")
    """

    def __init__(
        self: PluginManager,
        registry_url: str = "https://registry.henchman.ai",
        data_dir: Path | None = None,
    ) -> None:
        """Initialize plugin manager.

        Args:
            registry_url: Base URL for plugin registry API.
            data_dir: Directory for plugin data (default: ~/.henchman/plugins).
        """
        super().__init__()
        self.registry_url = registry_url
        self.data_dir = data_dir or Path.home() / ".henchman" / "plugins"
        self.db_path = self.data_dir / "plugins.db"
        self.database = PluginDatabase(self.db_path)
        self.registry_client: PluginRegistryClient | None = None
        self.installer: PluginInstaller | None = None
        self.security_scanner: PluginSecurityScanner = PluginSecurityScanner()
        self.installed_plugins: dict[str, PluginInstallation] = {}
        self._initialized = False

    async def initialize(self: PluginManager) -> None:
        """Initialize plugin manager.

        Creates necessary directories, initializes database,
        and loads installed plugins.

        Returns:
            None
        """
        if self._initialized:
            return

        # Create data directory
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize database
        await self.database.initialize()

        # Load installed plugins
        self.installed_plugins = await self.database.load_installations()

        # Load extensions for enabled plugins
        for installation in self.installed_plugins.values():
            if installation.enabled:
                await self._load_plugin_extension(installation)

        # Create registry client
        self.registry_client = PluginRegistryClient(
            registry_url=self.registry_url,
            session=None,  # Let client create its own session
        )
        await self.registry_client.initialize()

        # Create installer
        self.installer = PluginInstaller(self.data_dir)

        self._initialized = True
        logger.info("Plugin manager initialized")

    async def close(self: PluginManager) -> None:
        """Close plugin manager and release resources.

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
        """Search for plugins in the registry.

        Args:
            query: Search query string. Use `search_params` parameter for more control.
                Deprecated: Prefer using `search_params` parameter.
            page: Page number (1-indexed). Use `search_params` parameter for more control.
                Deprecated: Prefer using `search_params` parameter.
            page_size: Results per page. Use `search_params` parameter for more control.
                Deprecated: Prefer using `search_params` parameter.
            category: Filter by category. Deprecated: Include category in `search_params`.
            search_params: Complete search parameters object. If provided, individual
                query/page/page_size/category parameters are ignored.

        Returns:
            PluginSearchResult with matching plugins.

        Raises:
            aiohttp.ClientError: If registry request fails.
            RuntimeError: If plugin manager not initialized.
        """
        if not self._initialized or not self.registry_client:
            msg = "Plugin manager not initialized"
            raise RuntimeError(msg)

        # Emit deprecation warning if primitive parameters are used
        if search_params is None and any(
            [
                query is not None,
                page != 1,
                page_size != PluginConstants.DEFAULT_PAGE_SIZE,
                category is not None,
            ]
        ):
            warnings.warn(
                "Using individual query/page/page_size/category parameters is deprecated. "
                "Use the search_params parameter instead.",
                DeprecationWarning,
                stacklevel=2,
            )

        if search_params is None:
            search_params = PluginSearchParams(
                query=query,
                page=page,
                page_size=page_size,
                category=category,
            )

        # search_params already has category, so we don't pass the separate category parameter
        return await self.registry_client.search_plugins(search_params)

    async def get_plugin_info(
        self: PluginManager,
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
            RuntimeError: If plugin manager not initialized.
        """
        if not self._initialized or not self.registry_client:
            msg = "Plugin manager not initialized"
            raise RuntimeError(msg)

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
            version: Specific version to install (default: latest).
            confirm_permissions: Whether to confirm permissions before installation.

        Returns:
            PluginInstallation record for the installed plugin.

        Raises:
            ValueError: If plugin is already installed.
            RuntimeError: If plugin installation fails.
        """
        self._validate_initialization()
        self._check_already_installed(plugin_name)

        metadata = await self._get_plugin_metadata(plugin_name, version)
        await self._validate_compatibility(plugin_name, metadata)
        await self._handle_permissions(plugin_name, metadata, confirm_permissions)
        await self._install_dependencies(metadata)

        installation_path = await self._install_plugin_package(plugin_name, metadata)
        installation = self._create_installation_record(metadata, installation_path)

        await self._save_installation(installation)
        await self._load_plugin_extension(installation)
        self._update_installation_cache(plugin_name, installation)

        logger.info("Installed plugin '%s' v%s", plugin_name, metadata.version)
        return installation

    def _validate_initialization(self: PluginManager) -> None:
        """Validate that plugin manager is initialized."""
        if not self._initialized or not self.registry_client or not self.installer:
            msg = "Plugin manager not initialized"
            raise RuntimeError(msg)

    def _check_already_installed(self: PluginManager, plugin_name: str) -> None:
        """Check if plugin is already installed."""
        if plugin_name in self.installed_plugins:
            msg = f"Plugin '{plugin_name}' is already installed"
            raise ValueError(msg)

    async def _get_plugin_metadata(
        self: PluginManager,
        plugin_name: str,
        version: str | None,
    ) -> PluginMetadata:
        """Get plugin metadata from registry."""
        metadata = await self.get_plugin_info(plugin_name, version)
        if not metadata:
            msg = f"Plugin '{plugin_name}' not found in registry"
            raise ValueError(msg)
        return metadata

    async def _validate_compatibility(
        self: PluginManager,
        plugin_name: str,
        metadata: PluginMetadata,
    ) -> None:
        """Validate plugin compatibility with the system."""
        if not await PluginCompatibilityChecker.check_compatibility(metadata):
            msg = f"Plugin '{plugin_name}' is not compatible with this system"
            raise RuntimeError(msg)

    async def _handle_permissions(
        self: PluginManager,
        plugin_name: str,
        metadata: PluginMetadata,
        confirm_permissions: bool,
    ) -> None:
        """Handle plugin permissions confirmation."""
        if confirm_permissions and metadata.security.permissions:
            # TODO: Implement permission confirmation UI
            logger.info(
                "Plugin '%s' requires permissions: %s",
                plugin_name,
                ", ".join(metadata.security.permissions),
            )

    async def _install_dependencies(self: PluginManager, metadata: PluginMetadata) -> None:
        """Install plugin dependencies."""
        if metadata.dependencies and self.installer:
            await self.installer.install_dependencies(metadata.dependencies)

    async def _install_plugin_package(
        self: PluginManager,
        plugin_name: str,
        metadata: PluginMetadata,
    ) -> Path:
        """Install plugin package."""
        if not self.installer:
            msg = "Plugin installer not available"
            raise RuntimeError(msg)

        try:
            return await self.installer.install_plugin_package(metadata)
        except Exception as e:
            msg = f"Failed to install plugin '{plugin_name}': {e}"
            raise RuntimeError(msg) from e

    def _create_installation_record(
        self: PluginManager,
        metadata: PluginMetadata,
        installation_path: Path,
    ) -> PluginInstallation:
        """Create installation record for the plugin."""
        return PluginInstallation(
            metadata=metadata,
            installed_version=metadata.version,
            installation_path=str(installation_path),
        )

    async def _save_installation(self: PluginManager, installation: PluginInstallation) -> None:
        """Save installation to database."""
        await self.database.save_installation(installation)

    def _update_installation_cache(
        self: PluginManager,
        plugin_name: str,
        installation: PluginInstallation,
    ) -> None:
        """Update installation cache."""
        _set_dict_item(self.installed_plugins, plugin_name, installation)

    async def uninstall_plugin(self: PluginManager, plugin_name: str) -> None:
        """Uninstall a plugin.

        Args:
            plugin_name: Name of the plugin to uninstall.

        Returns:
            None

        Raises:
            ValueError: If plugin is not installed.
        """
        if plugin_name not in self.installed_plugins:
            msg = f"Plugin '{plugin_name}' is not installed"
            raise ValueError(msg)

        installation = self.installed_plugins[plugin_name]

        # Unregister extension
        self.unregister(plugin_name)

        # Remove from filesystem
        if installation.installation_path:
            try:
                import shutil  # noqa: PLC0415

                shutil.rmtree(installation.installation_path, ignore_errors=True)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to remove plugin files: %s", e)

        # Remove from database
        await self.database.delete_installation(plugin_name)

        # Remove from cache
        del self.installed_plugins[plugin_name]

        logger.info("Uninstalled plugin '%s'", plugin_name)

    async def update_plugin(self: PluginManager, plugin_name: str) -> PluginInstallation | None:
        """Update a plugin to the latest version.

        Args:
            plugin_name: Name of the plugin to update.

        Returns:
            Updated PluginInstallation or None if already up-to-date.

        Raises:
            ValueError: If plugin is not installed.
        """
        if plugin_name not in self.installed_plugins:
            msg = f"Plugin '{plugin_name}' is not installed"
            raise ValueError(msg)

        current_installation = self.installed_plugins[plugin_name]
        latest_metadata = await self.get_plugin_info(plugin_name)

        if not latest_metadata:
            logger.warning("Plugin '%s' not found in registry", plugin_name)
            return None

        if latest_metadata.version == current_installation.installed_version:
            logger.info("Plugin '%s' is already up-to-date", plugin_name)
            return None

        # Uninstall current version
        await self.uninstall_plugin(plugin_name)

        # Install latest version
        try:
            return await self.install_plugin(plugin_name, confirm_permissions=False)
        except Exception as e:
            # Try to reinstall old version on failure
            logger.exception("Failed to update plugin '%s': %s", plugin_name, e)  # noqa: TRY401
            # TODO: Implement rollback to previous version
            raise

    async def check_updates(self: PluginManager) -> dict[str, PluginUpdateInfo]:
        """Check for available plugin updates.

        Returns:
            Dictionary mapping plugin names to update information.
        """
        updates: dict[str, PluginUpdateInfo] = {}

        for plugin_name, installation in self.installed_plugins.items():
            latest_metadata = await self.get_plugin_info(plugin_name)
            if not latest_metadata:
                continue

            if latest_metadata.version != installation.installed_version:
                updates[plugin_name] = PluginUpdateInfo(
                    plugin_name=plugin_name,
                    current_version=installation.installed_version,
                    latest_version=latest_metadata.version,
                )

        return updates

    async def scan_security(self: PluginManager, plugin_name: str) -> SecurityReport:
        """Run security scan on a plugin.

        Args:
            plugin_name: Name of the plugin to scan.

        Returns:
            SecurityReport with scan results.

        Raises:
            ValueError: If plugin is not installed.
        """
        installation = self._get_installation_or_raise(plugin_name)
        return self.security_scanner.scan(installation)

    def _get_installation_or_raise(self: PluginManager, plugin_name: str) -> PluginInstallation:
        """Get installation or raise ValueError if not installed."""
        if plugin_name not in self.installed_plugins:
            msg = f"Plugin '{plugin_name}' is not installed"
            raise ValueError(msg)
        return self.installed_plugins[plugin_name]

    # Private methods

    async def _load_plugin_extension(self: PluginManager, installation: PluginInstallation) -> None:
        """Load extension from installed plugin.

        Args:
            installation: Plugin installation record.
        """
        if not installation.installation_path:
            return

        plugin_dir = Path(installation.installation_path)
        ext_file = plugin_dir / "extension.py"

        if ext_file.exists():
            try:
                self._load_extension_from_file(ext_file, installation.metadata.name)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Failed to load extension for plugin '%s': %s",
                    installation.metadata.name,
                    e,
                )
