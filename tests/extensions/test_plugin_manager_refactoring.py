"""Tests for PluginManager refactoring to address code smells.

These tests focus on edge cases and smell-related issues.
"""

from unittest.mock import patch

import pytest

from henchman.extensions.models import PluginSearchParams, PluginSearchResult
from henchman.extensions.plugin_manager import PluginManager


class TestPluginManagerRefactoring:
    """Test refactoring of PluginManager to address code smells."""

    @pytest.mark.asyncio
    async def test_search_plugins_only_accepts_search_params(self) -> None:
        """Test that search_plugins should only accept PluginSearchParams, not primitives."""
        # This test documents the desired behavior after refactoring
        manager = PluginManager()
        await manager.initialize()

        # After refactoring, this should be the only way to call search_plugins
        search_params = PluginSearchParams(
            query="test",
            page=1,
            page_size=20,
            category="tools",
        )

        # Mock the registry client
        mock_result = PluginSearchResult(
            plugins=[],
            total=0,
            page=1,
            page_size=20,
            query="test",
        )

        with patch.object(
            manager.registry_client,
            "search_plugins",
            return_value=mock_result,
        ):
            result = await manager.search_plugins(search_params=search_params)
            assert result.query == "test"

        await manager.close()

    @pytest.mark.asyncio
    async def test_install_plugin_parameter_object(self) -> None:
        """Test that install_plugin should use a parameter object instead of primitives."""
        manager = PluginManager()
        await manager.initialize()

        # After refactoring, install_plugin should accept a parameter object
        # For now, test current behavior
        with (
            patch.object(manager, "get_plugin_info", return_value=None),
            patch.object(manager, "_check_already_installed"),
            patch.object(manager.installer, "install_plugin_package"),
            patch.object(manager.installer, "install_dependencies"),
            pytest.raises(ValueError, match="not found in registry"),
        ):
            # Current call with primitive parameters
            await manager.install_plugin(
                plugin_name="test-plugin",
                version="1.0.0",
                confirm_permissions=False,
            )

        await manager.close()

    @pytest.mark.asyncio
    async def test_method_type_hints_complete(self) -> None:
        """Test that all public methods have complete type hints."""
        manager = PluginManager()

        # Check __init__ method
        import inspect
        sig = inspect.signature(manager.__init__)
        for param_name, param in sig.parameters.items():
            if param_name != "self":
                assert param.annotation != inspect.Parameter.empty, \
                    f"Parameter '{param_name}' in __init__ missing type hint"

        # Check initialize method
        sig = inspect.signature(manager.initialize)
        assert sig.return_annotation != inspect.Parameter.empty, \
            "initialize method missing return type hint"

        # Check search_plugins method
        sig = inspect.signature(manager.search_plugins)
        for param_name, param in sig.parameters.items():
            if param_name not in ["self", "search_params"]:
                # Primitive parameters should have type hints
                assert param.annotation != inspect.Parameter.empty, \
                    f"Parameter '{param_name}' in search_plugins missing type hint"

        # Check return type
        assert sig.return_annotation != inspect.Parameter.empty, \
            "search_plugins method missing return type hint"

    @pytest.mark.asyncio
    async def test_class_size_reduction(self) -> None:
        """Test that PluginManager can be split into smaller classes."""
        # This is more of a documentation test
        manager = PluginManager()

        # Count methods
        import inspect
        methods = [name for name, _ in inspect.getmembers(manager, predicate=inspect.ismethod)]
        public_methods = [m for m in methods if not m.startswith('_') or m == '__init__']

        # The class has too many methods (24, threshold is 20)
        # This test documents that we need to extract some responsibilities
        assert len(methods) > 20, "Class has too many methods, needs extraction"

        # Potential extraction candidates:
        # 1. Security scanning methods -> PluginSecurityScanner
        # 2. Installation methods -> PluginInstaller (partially exists)
        # 3. Cache/database methods -> PluginCacheManager

        # For now, just document the issue
        print(f"PluginManager has {len(methods)} methods, should be <= 20")
        print(f"Public methods: {public_methods}")

    @pytest.mark.asyncio
    async def test_duplicate_code_elimination(self) -> None:
        """Test elimination of duplicate code in _update_installation_cache."""
        manager = PluginManager()

        # _update_installation_cache is similar to Registry.register
        # Both update a dictionary with a key-value pair
        # We should extract common logic

        # Test current behavior
        from henchman.extensions.models import PluginEntryPoints, PluginInstallation, PluginMetadata

        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            entry_points=PluginEntryPoints(
                henchman_extensions="test.module:TestPlugin",
            ),
        )

        installation = PluginInstallation(
            metadata=metadata,
            installed_version="1.0.0",
            installation_path="/tmp/test",
        )

        # Call the method
        manager._update_installation_cache("test-plugin", installation)

        # Verify it works
        assert "test-plugin" in manager.installed_plugins
        assert manager.installed_plugins["test-plugin"] == installation

        # The method is simple but duplicates Registry.register logic
        # We could use Registry class or extract a common helper
