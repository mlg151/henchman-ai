"""Edge case tests for PluginManager refactoring."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.extensions.models import (
    PluginEntryPoints,
    PluginInstallation,
    PluginMetadata,
    PluginSearchParams,
    PluginSearchResult,
    PluginSecurity,
)
from henchman.extensions.plugin_compatibility import PluginCompatibilityChecker
from henchman.extensions.plugin_manager import PluginManager


class TestPluginManagerEdgeCases:
    """Test edge cases for PluginManager refactoring."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def plugin_manager(self, temp_dir: Path) -> PluginManager:
        """Create PluginManager instance for tests."""
        return PluginManager(
            registry_url="https://test-registry.example.com",
            data_dir=temp_dir,
        )

    @pytest.fixture
    def sample_plugin_metadata(self) -> PluginMetadata:
        """Create sample plugin metadata for tests."""
        return PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test_plugin.module:TestPlugin",
            ),
            dependencies=[],
            security=PluginSecurity(
                permissions=["file_read", "file_write"],
                requires_sandbox=True,
            ),
        )

    @pytest.mark.asyncio
    async def test_search_plugins_with_none_query(self, plugin_manager: PluginManager) -> None:
        """Test search_plugins with None query."""
        await plugin_manager.initialize()

        mock_result = PluginSearchResult(
            plugins=[],
            total=0,
            page=1,
            page_size=20,
            query=None,
        )

        with patch.object(
            plugin_manager.registry_client,
            "search_plugins",
            return_value=mock_result,
        ):
            result = await plugin_manager.search_plugins(query=None)
            assert result.total == 0
            assert len(result.plugins) == 0

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_search_plugins_with_category_filter(self, plugin_manager: PluginManager) -> None:
        """Test search_plugins with category filter."""
        await plugin_manager.initialize()

        mock_result = PluginSearchResult(
            plugins=[],
            total=0,
            page=1,
            page_size=20,
            query="test",
        )

        with patch.object(
            plugin_manager.registry_client,
            "search_plugins",
            return_value=mock_result,
        ):
            result = await plugin_manager.search_plugins(query="test", category="tools")
            assert result.total == 0

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_get_plugin_info_with_specific_version(self, plugin_manager: PluginManager) -> None:
        """Test get_plugin_info with specific version."""
        await plugin_manager.initialize()

        mock_metadata = PluginMetadata(
            name="test-plugin",
            version="2.0.0",
            description="Specific version",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test_plugin.module:TestPlugin",
            ),
        )

        with patch.object(
            plugin_manager.registry_client,
            "get_plugin_info",
            return_value=mock_metadata,
        ):
            metadata = await plugin_manager.get_plugin_info("test-plugin", version="2.0.0")
            assert metadata is not None
            assert metadata.version == "2.0.0"

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_install_plugin_with_permissions_confirmation(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test install_plugin with permissions confirmation."""
        await plugin_manager.initialize()

        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        
        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=sample_plugin_metadata,
            ),
            patch.object(
                plugin_manager.installer,
                "install_plugin_package",
                return_value=plugin_dir,
            ),
            patch.object(
                plugin_manager.installer,
                "install_dependencies",
                return_value=None,
            ),
        ):
            # Test with confirm_permissions=True (default)
            installation = await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=True,
            )
            assert installation is not None

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_install_plugin_compatibility_check_fails(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test install_plugin when compatibility check fails."""
        await plugin_manager.initialize()

        # Mock the compatibility check to fail
        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=sample_plugin_metadata,
            ),
            patch(
                "henchman.extensions.plugin_manager.PluginCompatibilityChecker.check_compatibility",
                return_value=False,
            ),
        ):
            with pytest.raises(RuntimeError, match="not compatible"):
                await plugin_manager.install_plugin("test-plugin", confirm_permissions=False)

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_install_plugin_dependencies_installation(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test install_plugin with dependencies."""
        await plugin_manager.initialize()

        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        
        # Create metadata with dependencies
        metadata_with_deps = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Plugin with dependencies",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test_plugin.module:TestPlugin",
            ),
            dependencies=["requests>=2.25.0", "pydantic>=2.0.0"],
            security=PluginSecurity(permissions=[], requires_sandbox=False),
        )

        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=metadata_with_deps,
            ),
            patch.object(
                plugin_manager.installer,
                "install_plugin_package",
                return_value=plugin_dir,
            ),
            patch.object(
                plugin_manager.installer,
                "install_dependencies",
                return_value=None,
            ) as mock_install_deps,
        ):
            installation = await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )
            assert installation is not None
            # Verify dependencies were installed
            mock_install_deps.assert_called_once_with(metadata_with_deps.dependencies)

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_uninstall_plugin_with_missing_files(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test uninstall_plugin when plugin files are missing."""
        await plugin_manager.initialize()

        # First install a plugin
        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=sample_plugin_metadata,
            ),
            patch.object(
                plugin_manager.installer,
                "install_plugin_package",
                return_value=plugin_dir,
            ),
            patch.object(
                plugin_manager.installer,
                "install_dependencies",
                return_value=None,
            ),
        ):
            await plugin_manager.install_plugin("test-plugin", confirm_permissions=False)

        # Now uninstall - simulate missing files
        with patch("shutil.rmtree", side_effect=Exception("File not found")):
            # Should still succeed (ignore_errors=True)
            await plugin_manager.uninstall_plugin("test-plugin")
            assert "test-plugin" not in plugin_manager.installed_plugins

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_update_plugin_already_up_to_date(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test update_plugin when already up-to-date."""
        await plugin_manager.initialize()

        # Install plugin
        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=sample_plugin_metadata,
            ),
            patch.object(
                plugin_manager.installer,
                "install_plugin_package",
                return_value=plugin_dir,
            ),
            patch.object(
                plugin_manager.installer,
                "install_dependencies",
                return_value=None,
            ),
        ):
            await plugin_manager.install_plugin("test-plugin", confirm_permissions=False)

        # Mock get_plugin_info to return same version
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=sample_plugin_metadata,
        ):
            result = await plugin_manager.update_plugin("test-plugin")
            assert result is None  # Already up-to-date

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_scan_security_with_warnings(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test scan_security with warnings."""
        await plugin_manager.initialize()

        # Install plugin with sandbox requirement
        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=sample_plugin_metadata,
            ),
            patch.object(
                plugin_manager.installer,
                "install_plugin_package",
                return_value=plugin_dir,
            ),
            patch.object(
                plugin_manager.installer,
                "install_dependencies",
                return_value=None,
            ),
        ):
            await plugin_manager.install_plugin("test-plugin", confirm_permissions=False)

        # Run security scan
        report = await plugin_manager.scan_security("test-plugin")
        
        assert report.plugin_name == "test-plugin"
        assert report.passed is True  # No errors
        assert len(report.warnings) > 0  # Should have warning about sandbox
        assert "sandboxed execution" in report.warnings[0]

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_initialize_twice(self, plugin_manager: PluginManager) -> None:
        """Test that initialize can be called twice safely."""
        await plugin_manager.initialize()
        assert plugin_manager._initialized

        # Call initialize again
        await plugin_manager.initialize()
        assert plugin_manager._initialized  # Should still be initialized

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_close_before_initialize(self, plugin_manager: PluginManager) -> None:
        """Test close when not initialized."""
        assert not plugin_manager._initialized
        await plugin_manager.close()  # Should not raise
        assert not plugin_manager._initialized

    @pytest.mark.asyncio
    async def test_methods_raise_when_not_initialized(self, plugin_manager: PluginManager) -> None:
        """Test that methods raise RuntimeError when not initialized."""
        # Test search_plugins
        with pytest.raises(RuntimeError, match="not initialized"):
            await plugin_manager.search_plugins("test")

        # Test get_plugin_info
        with pytest.raises(RuntimeError, match="not initialized"):
            await plugin_manager.get_plugin_info("test")

        # Test install_plugin
        with pytest.raises(RuntimeError, match="not initialized"):
            await plugin_manager.install_plugin("test")

        # Test check_updates (should work even when not initialized)
        updates = await plugin_manager.check_updates()
        assert updates == {}  # Empty dict when not initialized

    @pytest.mark.asyncio
    async def test_install_plugin_already_installed(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test install_plugin when plugin is already installed."""
        await plugin_manager.initialize()

        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=sample_plugin_metadata,
            ),
            patch.object(
                plugin_manager.installer,
                "install_plugin_package",
                return_value=plugin_dir,
            ),
            patch.object(
                plugin_manager.installer,
                "install_dependencies",
                return_value=None,
            ),
        ):
            # First installation should succeed
            await plugin_manager.install_plugin("test-plugin", confirm_permissions=False)

            # Second installation should fail
            with pytest.raises(ValueError, match="already installed"):
                await plugin_manager.install_plugin("test-plugin", confirm_permissions=False)

        await plugin_manager.close()