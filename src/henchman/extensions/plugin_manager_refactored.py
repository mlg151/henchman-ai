"""Plugin manager for Henchman-AI plugin marketplace.

This module extends the basic ExtensionManager with remote plugin
discovery, installation, and management capabilities.
"""

from __future__ import annotations

import logging
from pathlib import Path

from henchman.extensions.constants import PluginConstants
from henchman.extensions.manager import ExtensionManager
from henchman.extensions.models import (
    PluginInstallation,
    PluginMetadata,
    PluginSearchParams,
    PluginSearchResult,
    PluginSource,
    PluginUpdateInfo,
    SecurityReport,
)
from henchman.extensions.plugin_compatibility import PluginCompatibilityChecker
from henchman.extensions.plugin_database import PluginDatabase
from henchman.extensions.plugin_installer import PluginInstaller
from henchman.extensions.plugin_registry_client import PluginRegistryClient

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
        self,
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
        self.installed_plugins: dict[str, PluginInstallation] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize plugin manager.

        Creates necessary directories, initializes database,
        and loads installed plugins.
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

    async def close(self) -> None:
        """Close plugin manager and release resources."""
        if self.registry_client:
            await self.registry_client.close()
            self.registry_client = None
        
        self.installer = None
        self._initialized = False

    async def search_plugins(
        self,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
        category: str | None = None,
    ) -> PluginSearchResult:
        """Search for plugins in the registry.

        Args:
            query: Search query string.
            page: Page number (1-indexed).
            page_size: Results per page.
            category: Filter by category.

        Returns:
            PluginSearchResult with matching plugins.

        Raises:
            aiohttp.ClientError: If registry request fails.
            RuntimeError: If plugin manager not initialized.
        """
        if not self._initialized or not self.registry_client:
            raise RuntimeError("Plugin manager not initialized")

        search_params = PluginSearchParams(
            query=query,
            page=page,
            page_size=page_size,
        )
        return await self.registry_client.search_plugins(search_params, category)

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
            RuntimeError: If plugin manager not initialized.
        """
        if not self._initialized or not self.registry_client:
            raise RuntimeError("Plugin manager not initialized")

        return await self.registry_client.get_plugin_info(plugin_name, version)

    async def install_plugin(
        self,
        plugin_name: str,
        version: str | None = None,
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
        if not self._initialized or not self.registry_client or not self.installer:
            raise RuntimeError("Plugin manager not initialized")

        if plugin_name in self.installed_plugins:
            raise ValueError(f"Plugin '{plugin_name}' is already installed")

        # Get plugin metadata for the specified version (or latest if None)
        metadata = await self.get_plugin_info(plugin_name, version)
        if not metadata:
            raise ValueError(f"Plugin '{plugin_name}' not found in registry")

        # Check compatibility
        if not await PluginCompatibilityChecker.check_compatibility(metadata):
            raise RuntimeError(f"Plugin '{plugin_name}' is not compatible with this system")

        # Check permissions
        if confirm_permissions and metadata.security.permissions:
            # TODO: Implement permission confirmation UI
            logger.info(
                "Plugin '%s' requires permissions: %s",
                plugin_name,
                ", ".join(metadata.security.permissions),
            )

        # Install dependencies first
        if metadata.dependencies and self.installer:
            await self.installer.install_dependencies(metadata.dependencies)

        # Install plugin
        try:
            installation_path = await self.installer.install_plugin_package(metadata)
        except Exception as e:
            raise RuntimeError(f"Failed to install plugin '{plugin_name}': {e}") from e

        # Create installation record
        installation = PluginInstallation(
            metadata=metadata,
            installed_version=metadata.version,
            installation_path=str(installation_path),
        )

        # Save to database
        await self.database.save_installation(installation)

        # Load extension
        await self._load_plugin_extension(installation)

        # Update cache
        self.installed_plugins[plugin_name] = installation

        logger.info("Installed plugin '%s' v%s", plugin_name, metadata.version)
        return installation

    async def uninstall_plugin(self, plugin_name: str) -> None:
        """Uninstall a plugin.

        Args:
            plugin_name: Name of the plugin to uninstall.

        Raises:
            ValueError: If plugin is not installed.
        """
        if plugin_name not in self.installed_plugins:
            raise ValueError(f"Plugin '{plugin_name}' is not installed")

        installation = self.installed_plugins[plugin_name]

        # Unregister extension
        self.unregister(plugin_name)

        # Remove from filesystem
        if installation.installation_path:
            try:
                import shutil

                shutil.rmtree(installation.installation_path, ignore_errors=True)
            except Exception as e:
                logger.warning("Failed to remove plugin files: %s", e)

        # Remove from database
        await self.database.delete_installation(plugin_name)

        # Remove from cache
        del self.installed_plugins[plugin_name]

        logger.info("Uninstalled plugin '%s'", plugin_name)

    async def update_plugin(self, plugin_name: str) -> PluginInstallation | None:
        """Update a plugin to the latest version.

        Args:
            plugin_name: Name of the plugin to update.

        Returns:
            Updated PluginInstallation or None if already up-to-date.

        Raises:
            ValueError: If plugin is not installed.
        """
        if plugin_name not in self.installed_plugins:
            raise ValueError(f"Plugin '{plugin_name}' is not installed")

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
            logger.error("Failed to update plugin '%s': %s", plugin_name, e)
            # TODO: Implement rollback to previous version
            raise

    async def check_updates(self) -> dict[str, PluginUpdateInfo]:
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

    async def scan_security(self, plugin_name: str) -> SecurityReport:
        """Run security scan on a plugin.

        Args:
            plugin_name: Name of the plugin to scan.

        Returns:
            SecurityReport with scan results.

        Raises:
            ValueError: If plugin is not installed.
        """
        if plugin_name not in self.installed_plugins:
            raise ValueError(f"Plugin '{plugin_name}' is not installed")

        installation = self.installed_plugins[plugin_name]

        # TODO: Implement actual security scanning
        # This is a placeholder implementation
        warnings = []
        errors = []

        # Check permissions vs declared
        declared_permissions = installation.metadata.security.permissions
        # TODO: Analyze code for actual permission usage

        # Simple checks
        if installation.metadata.security.requires_sandbox:
            warnings.append("Plugin requires sandboxed execution")

        risk_level = PluginConstants.DEFAULT_RISK_LEVEL if warnings else PluginConstants.LOW_RISK_LEVEL

        return SecurityReport(
            plugin_name=plugin_name,
            passed=len(errors) == 0,
            warnings=warnings,
            errors=errors,
            permissions_used=declared_permissions,
            risk_level=risk_level,
        )

    # Private methods

    async def _load_plugin_extension(self, installation: PluginInstallation) -> None:
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
            except Exception as e:
                logger.warning(
                    "Failed to load extension for plugin '%s': %s",
                    installation.metadata.name,
                    e,
                )