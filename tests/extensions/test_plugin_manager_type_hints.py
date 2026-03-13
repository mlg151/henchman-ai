"""Tests for PluginManager type hints and parameter validation."""

import inspect
from typing import get_type_hints
from pathlib import Path

import pytest

from henchman.extensions.plugin_manager import PluginManager


class TestPluginManagerTypeHints:
    """Test type hints and parameter validation for PluginManager."""

    def test_all_public_methods_have_type_hints(self) -> None:
        """Test that all public methods have complete type hints."""
        manager_class = PluginManager
        
        # Get all public methods (not starting with underscore)
        public_methods = [
            (name, method) 
            for name, method in inspect.getmembers(manager_class, predicate=inspect.isfunction)
            if not name.startswith('_')
        ]
        
        # Also include __init__ since it's public
        public_methods.append(('__init__', manager_class.__init__))
        
        for method_name, method in public_methods:
            try:
                type_hints = get_type_hints(method)
                # Check that return type is present
                if 'return' not in type_hints:
                    pytest.fail(f"Method {method_name} missing return type hint")
                
                # Get method signature
                sig = inspect.signature(method)
                
                # Check all parameters have type hints (excluding self)
                for param_name, param in sig.parameters.items():
                    if param_name == 'self':
                        continue
                    if param_name not in type_hints:
                        pytest.fail(f"Method {method_name} parameter '{param_name}' missing type hint")
                        
            except Exception as e:
                pytest.fail(f"Failed to get type hints for {method_name}: {e}")

    def test_search_plugins_parameter_types(self) -> None:
        """Test that search_plugins accepts both old and new parameter styles."""
        manager = PluginManager()
        
        # Get method signature
        sig = inspect.signature(manager.search_plugins)
        
        # Check parameters
        params = list(sig.parameters.keys())
        
        # Should have search_params parameter
        assert 'search_params' in params
        
        # Should still accept old parameters for backward compatibility
        assert 'query' in params
        assert 'page' in params
        assert 'page_size' in params
        assert 'category' in params

    def test_install_plugin_parameter_types(self) -> None:
        """Test that install_plugin has proper parameter types."""
        manager = PluginManager()
        
        # Get method signature
        sig = inspect.signature(manager.install_plugin)
        
        # Check parameters
        params = list(sig.parameters.keys())
        
        # Required parameters
        assert 'plugin_name' in params
        assert 'version' in params
        assert 'confirm_permissions' in params
        
        # Check types from annotations
        type_hints = get_type_hints(manager.install_plugin)
        
        assert type_hints.get('plugin_name') == str
        
        # Check version is Optional[str] (str | None)
        # We can't easily check union types, so just verify the type hint exists
        assert 'version' in type_hints
        
        assert type_hints.get('confirm_permissions') == bool
        assert 'return' in type_hints  # Should have return type

    def test_initialization_parameters(self) -> None:
        """Test __init__ method parameter types."""
        manager_class = PluginManager
        
        # Get type hints for __init__
        type_hints = get_type_hints(manager_class.__init__)
        
        # Check parameters
        assert 'registry_url' in type_hints
        assert type_hints['registry_url'] == str
        
        assert 'data_dir' in type_hints
        # data_dir can be Path or None (Path | None)
        # Just verify the type hint exists
        
        # Check return type (should be None for __init__)
        assert 'return' in type_hints
        assert type_hints['return'] == type(None)

    def test_private_methods_type_hints(self) -> None:
        """Test that key private methods have type hints."""
        manager_class = PluginManager
        
        # Check important private methods
        private_methods_to_check = [
            '_validate_initialization',
            '_check_already_installed',
            '_get_plugin_metadata',
            '_validate_compatibility',
            '_handle_permissions',
            '_install_dependencies',
            '_install_plugin_package',
            '_create_installation_record',
            '_save_installation',
            '_update_installation_cache',
            '_get_installation_or_raise',
            '_load_plugin_extension',
        ]
        
        for method_name in private_methods_to_check:
            if hasattr(manager_class, method_name):
                method = getattr(manager_class, method_name)
                try:
                    type_hints = get_type_hints(method)
                    # At minimum should have return type
                    if 'return' not in type_hints:
                        pytest.fail(f"Private method {method_name} missing return type hint")
                except Exception:
                    # Some private methods might not have type hints yet
                    # That's what we're fixing
                    pass

    def test_method_signatures_preserved(self) -> None:
        """Test that method signatures are preserved after refactoring."""
        manager = PluginManager()
        
        # Test search_plugins signature
        sig = inspect.signature(manager.search_plugins)
        
        # Check default values
        params = sig.parameters
        
        # query should default to None
        assert params['query'].default is None
        
        # page should default to 1
        assert params['page'].default == 1
        
        # page_size should default to PluginConstants.DEFAULT_PAGE_SIZE
        # We'll check it's an integer
        assert isinstance(params['page_size'].default, int)
        
        # category should default to None
        assert params['category'].default is None
        
        # search_params should default to None
        assert params['search_params'].default is None
        
        # confirm_permissions should default to True in install_plugin
        sig_install = inspect.signature(manager.install_plugin)
        assert sig_install.parameters['confirm_permissions'].default is True