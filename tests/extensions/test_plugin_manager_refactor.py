"""Additional tests for PluginManager refactoring.

These tests cover edge cases and missing type hints identified in the smell report.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from henchman.extensions.models import (
    PluginInstallation,
    PluginMetadata,
    PluginSearchParams,
    PluginSearchResult,
    PluginUpdateInfo,
    SecurityReport,
)
from henchman.extensions.plugin_manager import PluginManager


class TestPluginManagerRefactoring:
    """Test edge cases and type hint coverage for PluginManager."""

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create temporary directory for tests."""
        import tempfile

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
        from henchman.extensions.models import PluginEntryPoints, PluginPermission, PluginSecurity

        return PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin for Henchman-AI",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test_plugin.module:TestPlugin",
            ),
            security=PluginSecurity(
                permissions=[PluginPermission.FILE_READ, PluginPermission.FILE_WRITE],
                risk_level="low",
            ),
            dependencies=["requests>=2.25.0"],
        )

    @pytest.mark.asyncio
    async def test_search_plugins_with_search_params(self, plugin_manager: PluginManager) -> None:
        """Test search_plugins with PluginSearchParams object (non-deprecated usage)."""
        await plugin_manager.initialize()

        # Mock response
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
        ) as mock_search:
            # Test with search_params (non-deprecated usage)
            search_params = PluginSearchParams(
                query="test",
                page=2,
                page_size=50,
                category="integration",
            )

            result = await plugin_manager.search_plugins(search_params=search_params)

            # Verify search_params was passed correctly
            mock_search.assert_called_once_with(search_params)
            assert result == mock_result

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_search_plugins_deprecation_warning(self, plugin_manager: PluginManager) -> None:
        """Test that using individual parameters emits deprecation warning."""
        await plugin_manager.initialize()

        # Mock response
        mock_result = PluginSearchResult(
            plugins=[],
            total=0,
            page=2,
            page_size=30,
            query="test",
        )

        with patch.object(
            plugin_manager.registry_client,
            "search_plugins",
            return_value=mock_result,
        ) as mock_search:
            # Capture warnings
            import warnings

            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")

                # Call with individual parameters (deprecated)
                await plugin_manager.search_plugins(
                    query="test",
                    page=2,
                    page_size=30,
                    category="integration",
                )

                # Verify deprecation warning was emitted
                assert len(w) == 1
                assert issubclass(w[0].category, DeprecationWarning)
                assert "search_params" in str(w[0].message)

                # Verify search_params was constructed correctly
                call_args = mock_search.call_args[0][0]
                assert isinstance(call_args, PluginSearchParams)
                assert call_args.query == "test"
                assert call_args.page == 2
                assert call_args.page_size == 30
                assert call_args.category == "integration"

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
            patch.object(
                PluginManager,
                "_handle_permissions",
                return_value=None,
            ) as mock_handle_perms,
        ):
            # Install with confirm_permissions=True (default)
            installation = await plugin_manager.install_plugin("test-plugin")

            # Verify permissions were handled
            mock_handle_perms.assert_called_once_with(
                "test-plugin",
                sample_plugin_metadata,
                True,  # confirm_permissions
            )

            assert installation is not None
            assert installation.metadata.name == "test-plugin"

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_install_plugin_without_permissions_confirmation(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test install_plugin without permissions confirmation."""
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
            patch.object(
                PluginManager,
                "_handle_permissions",
                return_value=None,
            ) as mock_handle_perms,
        ):
            # Install with confirm_permissions=False
            installation = await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )

            # Verify permissions were handled with False
            mock_handle_perms.assert_called_once_with(
                "test-plugin",
                sample_plugin_metadata,
                False,  # confirm_permissions
            )

            assert installation is not None

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_update_plugin_already_up_to_date(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test update_plugin when plugin is already up-to-date."""
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
            await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )

        # Mock get_plugin_info to return same version
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=sample_plugin_metadata,  # Same version
        ):
            # Update should return None (already up-to-date)
            result = await plugin_manager.update_plugin("test-plugin")
            assert result is None

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_update_plugin_not_found_in_registry(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test update_plugin when plugin is not found in registry."""
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
            await plugin_manager.install_plugin(
                "test-plugin",
                confirm_permissions=False,
            )

        # Mock get_plugin_info to return None (not found)
        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=None,
        ):
            # Update should return None
            result = await plugin_manager.update_plugin("test-plugin")
            assert result is None

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_check_updates_empty(self, plugin_manager: PluginManager) -> None:
        """Test check_updates when no updates are available."""
        await plugin_manager.initialize()

        # No plugins installed, so no updates
        updates = await plugin_manager.check_updates()
        assert updates == {}

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_scan_security_not_installed(self, plugin_manager: PluginManager) -> None:
        """Test scan_security when plugin is not installed."""
        await plugin_manager.initialize()

        # Should raise ValueError
        with pytest.raises(ValueError, match="is not installed"):
            await plugin_manager.scan_security("non-existent-plugin")

        await plugin_manager.close()

    def test_type_hints_present(self) -> None:
        """Verify that public methods defined in PluginManager have proper type hints."""
        import inspect

        # Import types that might be used in forward references
        from pathlib import Path
        from typing import get_type_hints

        from henchman.extensions.models import PluginSearchParams

        # Get only methods defined in PluginManager (not inherited)
        plugin_manager_methods = [
            (name, method)
            for name, method in inspect.getmembers(PluginManager)
            if inspect.isfunction(method)
            and not name.startswith("_")
            and method.__qualname__.startswith("PluginManager.")
        ]

        # Also include private methods that are defined in PluginManager
        # (these were mentioned in the smell report)
        plugin_manager_private_methods = [
            (name, method)
            for name, method in inspect.getmembers(PluginManager)
            if inspect.isfunction(method)
            and name.startswith("_")
            and method.__qualname__.startswith("PluginManager.")
        ]

        # Combine public and private methods defined in PluginManager
        all_plugin_manager_methods = plugin_manager_methods + plugin_manager_private_methods

        # Local namespace for evaluating forward references
        localns = {
            "Path": Path,
            "PluginSearchParams": PluginSearchParams,
            "PluginMetadata": PluginMetadata,
            "PluginInstallation": PluginInstallation,
            "PluginSearchResult": PluginSearchResult,
            "PluginUpdateInfo": PluginUpdateInfo,
            "SecurityReport": SecurityReport,
        }

        for name, method in all_plugin_manager_methods:
            try:
                # Try to get type hints with local namespace
                hints = get_type_hints(method, localns=localns)
                # At minimum should have return type
                assert "return" in hints, f"Method {name} missing return type hint"
            except (TypeError, KeyError) as e:
                # Some methods might have forward references that fail
                # Check if it's a known issue or actual missing type hint
                if "cannot be resolved" not in str(e):
                    pytest.fail(f"Method {name} has incomplete type hints: {e}")

    @pytest.mark.asyncio
    async def test_error_handling_install_plugin_failure(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test error handling when plugin installation fails."""
        await plugin_manager.initialize()

        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=sample_plugin_metadata,
            ),
            patch.object(
                plugin_manager.installer,
                "install_plugin_package",
                side_effect=RuntimeError("Installation failed"),
            ),
        ):
            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="Failed to install plugin"):
                await plugin_manager.install_plugin("test-plugin")

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_error_handling_plugin_not_found(
        self,
        plugin_manager: PluginManager,
    ) -> None:
        """Test error handling when plugin is not found in registry."""
        await plugin_manager.initialize()

        with patch.object(
            plugin_manager,
            "get_plugin_info",
            return_value=None,
        ):
            # Should raise ValueError
            with pytest.raises(ValueError, match="not found in registry"):
                await plugin_manager.install_plugin("non-existent-plugin")

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_error_handling_incompatible_plugin(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test error handling when plugin is incompatible."""
        await plugin_manager.initialize()

        # Import here to avoid circular imports
        from henchman.extensions.plugin_compatibility import PluginCompatibilityChecker

        with (
            patch.object(
                plugin_manager,
                "get_plugin_info",
                return_value=sample_plugin_metadata,
            ),
            patch.object(
                PluginCompatibilityChecker,
                "check_compatibility",
                return_value=False,
            ),
        ):
            # Should raise RuntimeError
            with pytest.raises(RuntimeError, match="not compatible"):
                await plugin_manager.install_plugin("test-plugin")

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_load_plugin_extension_missing_file(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
    ) -> None:
        """Test _load_plugin_extension when extension file doesn't exist."""
        await plugin_manager.initialize()

        # Create installation without extension file
        installation = PluginInstallation(
            metadata=sample_plugin_metadata,
            installed_version="1.0.0",
            installation_path="/tmp/nonexistent",
        )

        # Should not raise error
        await plugin_manager._load_plugin_extension(installation)

        await plugin_manager.close()

    @pytest.mark.asyncio
    async def test_load_plugin_extension_invalid_file(
        self,
        plugin_manager: PluginManager,
        sample_plugin_metadata: PluginMetadata,
        temp_dir: Path,
    ) -> None:
        """Test _load_plugin_extension with invalid extension file."""
        await plugin_manager.initialize()

        # Create installation directory
        plugin_dir = temp_dir / "test-plugin"
        plugin_dir.mkdir()

        # Create invalid extension file (syntax error)
        ext_file = plugin_dir / "extension.py"
        ext_file.write_text("invalid python syntax !@#$%")

        installation = PluginInstallation(
            metadata=sample_plugin_metadata,
            installed_version="1.0.0",
            installation_path=str(plugin_dir),
        )

        # Should not raise error (just log warning)
        await plugin_manager._load_plugin_extension(installation)

        await plugin_manager.close()
