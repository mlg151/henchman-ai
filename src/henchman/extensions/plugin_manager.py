"""Plugin manager for Henchman-AI plugin marketplace.

This module extends the basic ExtensionManager with remote plugin
discovery, installation, and management capabilities.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import aiohttp
from pydantic import ValidationError

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
from henchman.extensions.plugin_database import PluginDatabase

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
        self.installed_plugins: dict[str, PluginInstallation] = {}
        self._session: aiohttp.ClientSession | None = None
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

        # Create HTTP session for registry API
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=PluginConstants.REGISTRY_TIMEOUT),
            headers={"User-Agent": f"Henchman-AI/{__version__}"},
        )

        self._initialized = True
        logger.info("Plugin manager initialized")

    async def close(self) -> None:
        """Close plugin manager and release resources."""
        if self._session:
            await self._session.close()
            self._session = None
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
        """
        search_params = PluginSearchParams(
            query=query,
            page=page,
            page_size=page_size,
        )
        # Note: category is not part of PluginSearchParams model
        # We'll handle it separately
        return await self._search_plugins_with_params(search_params, category)

    async def _search_plugins_with_params(
        self,
        search_params: PluginSearchParams,
        category: str | None = None,
    ) -> PluginSearchResult:
        """Search for plugins using PluginSearchParams object.

        Args:
            search_params: Search parameters.
            category: Filter by category (not in PluginSearchParams model).

        Returns:
            PluginSearchResult with matching plugins.

        Raises:
            aiohttp.ClientError: If registry request fails.
        """
        if not self._session:
            raise RuntimeError("Plugin manager not initialized")

        params: dict[str, Any] = {
            "page": search_params.page,
            "page_size": search_params.page_size,
        }
        if search_params.query:
            params["q"] = search_params.query
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
            logger.error("Invalid plugin data from registry: %s", e)
            # Return empty result on validation error
            return PluginSearchResult(
                plugins=[],
                total=0,
                page=search_params.page,
                page_size=search_params.page_size,
                query=search_params.query,
            )

    async def get_plugin_info(self, plugin_name: str, version: str | None = None) -> PluginMetadata | None:
        """Get detailed information about a plugin.

        Args:
            plugin_name: Name of the plugin.
            version: Specific version to fetch (default: latest).

        Returns:
            PluginMetadata or None if not found.

        Raises:
            aiohttp.ClientError: If registry request fails.
        """
        if not self._session:
            raise RuntimeError("Plugin manager not initialized")

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
            logger.error("Invalid plugin data from registry: %s", e)
            return None

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
        if plugin_name in self.installed_plugins:
            raise ValueError(f"Plugin '{plugin_name}' is already installed")

        # Get plugin metadata for the specified version (or latest if None)
        metadata = await self.get_plugin_info(plugin_name, version)
        if not metadata:
            raise ValueError(f"Plugin '{plugin_name}' not found in registry")

        # Check compatibility
        if not await self._check_compatibility(metadata):
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
        if metadata.dependencies:
            await self._install_dependencies(metadata.dependencies)

        # Install plugin
        try:
            installation_path = await self._install_plugin_package(metadata)
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

    async def _check_compatibility(self, metadata: PluginMetadata) -> bool:
        """Check if plugin is compatible with current system.

        Args:
            metadata: Plugin metadata.

        Returns:
            True if compatible, False otherwise.
        """
        import sys
        from packaging.version import Version
        from packaging.specifiers import SpecifierSet, InvalidSpecifier
        from henchman.version import VERSION

        try:
            # Check Henchman version
            if not self._check_henchman_compatibility(metadata.compatibility.henchman, VERSION):
                return False

            # Check Python version
            if not self._check_python_compatibility(metadata.compatibility.python, sys):
                return False

            # Check OS compatibility
            if metadata.compatibility.os:
                if not self._check_os_compatibility(metadata.compatibility.os, sys.platform):
                    return False

            return True

        except (InvalidSpecifier, ValueError):
            return False

    def _check_henchman_compatibility(self, henchman_spec: str, current_version: str) -> bool:
        """Check Henchman version compatibility.
        
        Args:
            henchman_spec: Version specifier for Henchman.
            current_version: Current Henchman version.
            
        Returns:
            True if compatible, False otherwise.
        """
        from packaging.version import Version
        from packaging.specifiers import SpecifierSet
        
        current_henchman = Version(current_version)
        return SpecifierSet(henchman_spec).contains(current_henchman)

    def _check_python_compatibility(self, python_spec: str, sys_module) -> bool:
        """Check Python version compatibility.
        
        Args:
            python_spec: Version specifier for Python.
            sys_module: The sys module (passed as parameter for testability).
            
        Returns:
            True if compatible, False otherwise.
        """
        from packaging.version import Version
        from packaging.specifiers import SpecifierSet
        
        current_python = Version(
            f"{sys_module.version_info.major}.{sys_module.version_info.minor}.{sys_module.version_info.micro}"
        )
        return SpecifierSet(python_spec).contains(current_python)

    def _check_os_compatibility(self, supported_os_list: list[str], current_platform: str) -> bool:
        """Check OS compatibility.
        
        Args:
            supported_os_list: List of supported operating systems.
            current_platform: Current platform identifier.
            
        Returns:
            True if compatible, False otherwise.
        """
        platform_map = {
            "linux": "linux",
            "win32": "windows",
            "darwin": "macos",
        }
        current_os = platform_map.get(current_platform, current_platform)
        return current_os in supported_os_list

    async def _install_plugin_package(self, metadata: PluginMetadata) -> Path:
        """Install plugin package from source.

        Args:
            metadata: Plugin metadata.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        # Create installation directory
        plugin_dir = self.data_dir / "installed" / metadata.name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Install based on source type
        if metadata.source == PluginSource.PYPI:
            return await self._install_from_pypi(metadata, plugin_dir)
        elif metadata.source == PluginSource.GITHUB:
            return await self._install_from_github(metadata, plugin_dir)
        elif metadata.source == PluginSource.GIT:
            return await self._install_from_git(metadata, plugin_dir)
        elif metadata.source == PluginSource.URL:
            return await self._install_from_url(metadata, plugin_dir)
        elif metadata.source == PluginSource.LOCAL:
            return await self._install_from_local(metadata, plugin_dir)
        else:
            raise RuntimeError(f"Unsupported plugin source: {metadata.source}")

    async def _install_from_pypi(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from PyPI.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        import sys

        # Build package specification
        package_spec = f"{metadata.name}=={metadata.version}"

        # Use pip to install the package
        # We install to a temporary directory first, then copy to target
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                await self._install_package_with_pip(package_spec, temp_dir)
                self._copy_installed_files(temp_dir, target_dir)
                logger.info("Successfully installed package to: %s", target_dir)
            except Exception as e:
                raise RuntimeError(f"Failed to install from PyPI: {e}") from e

        return target_dir

    async def _install_package_with_pip(self, package_spec: str, target_dir: str) -> None:
        """Install package using pip.
        
        Args:
            package_spec: Package specification (e.g., "package==1.0.0").
            target_dir: Directory to install into.
            
        Raises:
            RuntimeError: If pip installation fails.
        """
        import sys
        
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            package_spec,
            "--target",
            target_dir,
            "--no-deps",  # We'll handle dependencies separately
        ]

        logger.info("Installing package from PyPI: %s", package_spec)
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            raise RuntimeError(f"Failed to install package: {error_msg}")

    def _copy_installed_files(self, source_dir: str, target_dir: Path) -> None:
        """Copy installed files from source to target directory.
        
        Args:
            source_dir: Source directory with installed files.
            target_dir: Target directory to copy to.
        """
        import shutil
        temp_path = Path(source_dir)
        for item in temp_path.iterdir():
            if item.is_file() or item.is_dir():
                dest = target_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

    async def _install_from_github(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from GitHub repository.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        if not metadata.source_url:
            raise RuntimeError("GitHub source URL is required")

        # Parse GitHub URL
        # Expected format: https://github.com/user/repo or https://github.com/user/repo/tree/branch
        import re
        github_pattern = r"github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+))?"
        match = re.search(github_pattern, metadata.source_url)

        if not match:
            raise RuntimeError(f"Invalid GitHub URL: {metadata.source_url}")

        user, repo, branch = match.groups()
        branch = branch or PluginConstants.DEFAULT_GITHUB_BRANCH

        # Clone repository

        try:
            # Create temporary directory for clone
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                # Clone repository
                clone_url = f"https://github.com/{user}/{repo}.git"
                cmd = ["git", "clone", "--branch", branch, "--depth", str(PluginConstants.GIT_CLONE_DEPTH), clone_url, temp_dir]

                logger.info("Cloning repository: %s (branch: %s)", clone_url, branch)
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await result.communicate()

                if result.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    raise RuntimeError(f"Failed to clone repository: {error_msg}")

                # Copy files to target directory
                import shutil
                temp_path = Path(temp_dir)
                for item in temp_path.iterdir():
                    if item.name != ".git":  # Skip .git directory
                        dest = target_dir / item.name
                        if item.is_dir():
                            shutil.copytree(item, dest, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, dest)

                logger.info("Successfully installed from GitHub to: %s", target_dir)

        except Exception as e:
            raise RuntimeError(f"Failed to install from GitHub: {e}") from e

        return target_dir

    async def _install_from_git(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from generic git repository.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        if not metadata.source_url:
            raise RuntimeError("Git source URL is required")


        try:
            # Create temporary directory for clone
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                # Clone repository
                cmd = ["git", "clone", "--depth", str(PluginConstants.GIT_CLONE_DEPTH), metadata.source_url, temp_dir]

                logger.info("Cloning git repository: %s", metadata.source_url)
                result = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                stdout, stderr = await result.communicate()

                if result.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    raise RuntimeError(f"Failed to clone git repository: {error_msg}")

                # Copy files to target directory
                import shutil
                temp_path = Path(temp_dir)
                for item in temp_path.iterdir():
                    if item.name != ".git":  # Skip .git directory
                        dest = target_dir / item.name
                        if item.is_dir():
                            shutil.copytree(item, dest, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, dest)

                logger.info("Successfully installed from git to: %s", target_dir)

        except Exception as e:
            raise RuntimeError(f"Failed to install from git: {e}") from e

        return target_dir

    async def _install_from_url(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from direct URL (zip/tar archive).

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        if not metadata.source_url:
            raise RuntimeError("URL source is required")

        # Download archive to temporary file
        temp_path = await self._download_archive_from_url(metadata.source_url)

        try:
            # Extract archive based on file type
            await self._extract_archive(temp_path, metadata.source_url, target_dir)
            logger.info("Successfully installed from URL to: %s", target_dir)
        finally:
            # Clean up temporary file
            temp_path.unlink(missing_ok=True)

        return target_dir

    async def _download_archive_from_url(self, url: str) -> Path:
        """Download archive from URL to temporary file.
        
        Args:
            url: URL to download from.
            
        Returns:
            Path to temporary file with downloaded content.
            
        Raises:
            RuntimeError: If download fails.
        """
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"Failed to download from URL: HTTP {response.status}")

                # Create temporary file for download
                with tempfile.NamedTemporaryFile(suffix=".archive", delete=False) as temp_file:
                    temp_path = Path(temp_file.name)
                    # Download content
                    content = await response.read()
                    temp_file.write(content)
                    return temp_path
        except Exception as e:
            raise RuntimeError(f"Failed to download from URL: {e}") from e

    async def _extract_archive(self, archive_path: Path, source_url: str, target_dir: Path) -> None:
        """Extract archive file to target directory.
        
        Args:
            archive_path: Path to archive file.
            source_url: Source URL for archive type detection.
            target_dir: Directory to extract into.
            
        Raises:
            RuntimeError: If extraction fails or format is unsupported.
        """
        import tarfile
        import zipfile

        # Determine archive type and extract
        if source_url.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
        elif source_url.endswith('.tar.gz') or source_url.endswith('.tgz'):
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extractall(target_dir)
        elif source_url.endswith('.tar'):
            with tarfile.open(archive_path, 'r') as tar_ref:
                tar_ref.extractall(target_dir)
        else:
            raise RuntimeError(f"Unsupported archive format: {source_url}")

    async def _install_from_local(self, metadata: PluginMetadata, target_dir: Path) -> Path:
        """Install plugin from local directory.

        Args:
            metadata: Plugin metadata.
            target_dir: Directory to install into.

        Returns:
            Path where plugin was installed.

        Raises:
            RuntimeError: If installation fails.
        """
        if not metadata.source_url:
            raise RuntimeError("Local source path is required")

        source_path = Path(metadata.source_url)

        if not source_path.exists():
            raise RuntimeError(f"Local path does not exist: {source_path}")

        try:
            import shutil

            if source_path.is_file():
                # Copy single file
                shutil.copy2(source_path, target_dir / source_path.name)
            else:
                # Copy directory
                for item in source_path.iterdir():
                    dest = target_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)

            logger.info("Successfully installed from local path to: %s", target_dir)

        except Exception as e:
            raise RuntimeError(f"Failed to install from local path: {e}") from e

        return target_dir

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
                logger.warning("Failed to load extension for plugin '%s': %s", installation.metadata.name, e)

    async def _install_dependencies(self, dependencies: list[str]) -> None:
        """Install plugin dependencies.

        Args:
            dependencies: List of dependency specifications.

        Raises:
            RuntimeError: If dependency installation fails.
        """
        if not dependencies:
            return

        import sys

        logger.info("Installing %d dependencies", len(dependencies))

        try:
            # Install dependencies using pip
            cmd = [sys.executable, "-m", "pip", "install"] + dependencies

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                # Don't fail the entire installation if dependencies fail
                # Just log a warning and continue
                logger.warning("Failed to install some dependencies: %s", error_msg)
            else:
                logger.info("Successfully installed dependencies")

        except Exception as e:
            logger.warning("Error installing dependencies: %s", e)
            # Continue with plugin installation even if dependencies fail


# Import at bottom to avoid circular imports
import logging

from henchman.version import VERSION as __version__
