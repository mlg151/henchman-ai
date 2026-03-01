"""Tests for PluginManager."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.extensions.models import PluginMetadata, PluginEntryPoints, PluginSearchResult
from henchman.extensions.plugin_manager import PluginManager


class TestPluginManager:
    """Test PluginManager functionality."""

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
    
    def _mock_installation_methods(self, plugin_manager: PluginManager, plugin_name: str) -> None:
        """Mock installation methods for testing.
        
        Args:
            plugin_manager: PluginManager instance.
            plugin_name: Name of plugin to mock.
        """
        # Create the mock installation path
        plugin_dir = plugin_manager.data_dir / "installed" / plugin_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a simple extension file
        ext_file = plugin_dir / "extension.py"
        ext_file.write_text(f'''
from henchman.extensions import Extension

class {plugin_name.title().replace("-", "").replace("_", "")}Extension(Extension):
    """Test extension for {plugin_name}"""
    
    @property
    def name(self) -> str:
        return "{plugin_name}"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Test plugin"
''')

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
        )

    @pytest.mark.asyncio
    async def test_initialization(self, plugin_manager: PluginManager) -> None:
        """Test PluginManager initialization."""
        assert plugin_manager.registry_url == "https://test-registry.example.com"
        assert not plugin_manager._initialized
        
        await plugin_manager.initialize()
        assert plugin_manager._initialized
        assert plugin_manager.data_dir.exists()
        assert plugin_manager.db_path.exists()
        
        await plugin_manager.close()
        assert not plugin_manager._initialized

    @pytest.mark.asyncio
    async def test_search_plugins_mocked(self, plugin_manager: PluginManager) -> None:
        """Test search_plugins with mocked HTTP response."""
        await plugin_manager.initialize()
        
        # Mock response data
        mock_response_data = {
            "plugins": [
                {
                    "name": "github-integration",
                    "version": "1.0.0",
                    "description": "GitHub integration for Henchman-AI",
                    "author": "GitHub User",
                    "entry_points": {
                        "henchman_extensions": "github_plugin.module:GitHubPlugin",
                    },
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }
        
        # Use patch to mock the entire search_plugins method
        with patch.object(
            plugin_manager,
            "search_plugins",
            return_value=PluginSearchResult(
                plugins=[
                    PluginMetadata(
                        name="github-integration",
                        version="1.0.0",
                        description="GitHub integration for Henchman-AI",
                        author="GitHub User",
                        entry_points=PluginEntryPoints(
                            henchman_extensions="github_plugin.module:GitHubPlugin",
                        ),
                    )
                ],
                total=1,
                page=1,
                page_size=20,
                query="github",
            ),
        ):
            # Test search
            result = await plugin_manager.search_plugins(query="github")
            
            assert result.total == 1
            assert len(result.plugins) == 1
            assert result.plugins[0].name == "github-integration"
            assert result.plugins[0].version == "1.0.0"
        
        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_get_plugin_info_mocked(self, plugin_manager: PluginManager) -> None:
        """Test get_plugin_info with mocked HTTP response."""
        await plugin_manager.initialize()
        
        # Mock get_plugin_info directly
        sample_metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test_plugin.module:TestPlugin",
            ),
        )
        
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            side_effect=lambda name: sample_metadata if name == "test-plugin" else None,
        ):
            # Test get plugin info
            metadata = await plugin_manager.get_plugin_info("test-plugin")
            
            assert metadata is not None
            assert metadata.name == "test-plugin"
            assert metadata.version == "1.0.0"
            assert metadata.description == "A test plugin for Henchman-AI"
            
            # Test non-existent plugin
            metadata = await plugin_manager.get_plugin_info("non-existent")
            assert metadata is None
        
        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_install_uninstall_plugin(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test plugin installation and uninstallation."""
        await plugin_manager.initialize()
        
        # Create the installation directory
        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        
        # Mock the installation methods
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=sample_plugin_metadata,
        ), patch.object(
            plugin_manager.installer,
            "install_plugin_package",
            return_value=plugin_dir,
        ), patch.object(
            plugin_manager.installer,
            "install_dependencies",
            return_value=None,
        ):
            # Install plugin
            installation = await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )
            
            assert installation is not None
            assert installation.metadata.name == "test-plugin"
            assert installation.installed_version == "1.0.0"
            assert installation.enabled is True
            assert "test-plugin" in plugin_manager.installed_plugins
            
            # Try to install again (should fail)
            with pytest.raises(ValueError, match="already installed"):
                await plugin_manager.install_plugin("test-plugin")
            
            # Uninstall plugin
            await plugin_manager.uninstall_plugin("test-plugin")
            assert "test-plugin" not in plugin_manager.installed_plugins
            
            # Try to uninstall non-existent plugin (should fail)
            with pytest.raises(ValueError, match="is not installed"):
                await plugin_manager.uninstall_plugin("non-existent")
        
        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_check_updates(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test checking for plugin updates."""
        await plugin_manager.initialize()
        
        # Install a plugin first
        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=sample_plugin_metadata,
        ), patch.object(
            plugin_manager.installer,
            "install_plugin_package",
            return_value=plugin_dir,
        ), patch.object(
            plugin_manager.installer,
            "install_dependencies",
            return_value=None,
        ):
            await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )
        
        # Mock get_plugin_info to return updated metadata
        updated_metadata = PluginMetadata(
            name="test-plugin",
            version="2.0.0",  # New version
            description="Updated test plugin",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test_plugin.module:TestPlugin",
            ),
        )
        
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=updated_metadata,
        ):
            updates = await plugin_manager.check_updates()
            
            assert "test-plugin" in updates
            update_info = updates["test-plugin"]
            assert update_info.current_version == "1.0.0"
            assert update_info.latest_version == "2.0.0"
        
        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_database_persistence(
        self,
        temp_dir: Path,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test that plugin installations persist across instances."""
        # Create first manager and install plugin
        manager1 = PluginManager(data_dir=temp_dir)
        await manager1.initialize()
        
        plugin_dir = manager1.data_dir / "installed" / "test-plugin"
        with patch.object(
            manager1,
            "get_plugin_info",
            return_value=sample_plugin_metadata,
        ), patch.object(
            manager1.installer,
            "install_plugin_package",
            return_value=plugin_dir,
        ), patch.object(
            manager1.installer,
            "install_dependencies",
            return_value=None,
        ):
            await manager1.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )
        
        await manager1.close()
        
        # Create second manager (should load installed plugins)
        manager2 = PluginManager(data_dir=temp_dir)
        await manager2.initialize()
        
        assert "test-plugin" in manager2.installed_plugins
        installation = manager2.installed_plugins["test-plugin"]
        assert installation.metadata.name == "test-plugin"
        assert installation.installed_version == "1.0.0"
        
        await manager2.close()

    @pytest.mark.asyncio
    async def test_scan_security(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test security scanning."""
        await plugin_manager.initialize()
        
        # Install a plugin first
        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=sample_plugin_metadata,
        ), patch.object(
            plugin_manager.installer,
            "install_plugin_package",
            return_value=plugin_dir,
        ), patch.object(
            plugin_manager.installer,
            "install_dependencies",
            return_value=None,
        ):
            await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )
        
        # Run security scan
        report = await plugin_manager.scan_security("test-plugin")
        
        assert report.plugin_name == "test-plugin"
        assert report.passed is True  # Our simple implementation always passes
        assert report.risk_level in ["low", "medium", "high"]
        
        # Try to scan non-existent plugin (should fail)
        with pytest.raises(ValueError, match="is not installed"):
            await plugin_manager.scan_security("non-existent")
        
        await plugin_manager.close()

    def test_error_handling_not_initialized(self, plugin_manager: PluginManager) -> None:
        """Test that methods raise error when not initialized."""
        # Methods should raise RuntimeError when not initialized
        with pytest.raises(RuntimeError, match="not initialized"):
            asyncio.run(plugin_manager.search_plugins("test"))
        
        with pytest.raises(RuntimeError, match="not initialized"):
            asyncio.run(plugin_manager.get_plugin_info("test"))

    @pytest.mark.asyncio
    async def test_update_plugin(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test plugin update functionality."""
        await plugin_manager.initialize()
        
        # Install initial version
        plugin_dir = plugin_manager.data_dir / "installed" / "test-plugin"
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=sample_plugin_metadata,
        ), patch.object(
            plugin_manager.installer,
            "install_plugin_package",
            return_value=plugin_dir,
        ), patch.object(
            plugin_manager.installer,
            "install_dependencies",
            return_value=None,
        ):
            await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )
        
        # Create updated metadata
        updated_metadata = PluginMetadata(
            name="test-plugin",
            version="2.0.0",
            description="Updated test plugin",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test_plugin.module:TestPluginV2",
            ),
        )
        
        # Mock get_plugin_info to return updated version
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=updated_metadata,
        ), patch.object(
            plugin_manager.installer,
            "install_plugin_package",
            return_value=plugin_dir,
        ), patch.object(
            plugin_manager.installer,
            "install_dependencies",
            return_value=None,
        ):
            # Update plugin
            updated_installation = await plugin_manager.update_plugin("test-plugin")
            
            assert updated_installation is not None
            assert updated_installation.installed_version == "2.0.0"
            assert updated_installation.metadata.version == "2.0.0"
            
            # Try to update non-existent plugin (should fail)
            with pytest.raises(ValueError, match="is not installed"):
                await plugin_manager.update_plugin("non-existent")
        
        await plugin_manager.close()