"""Tests for lazy_import.py module."""

import sys
from unittest.mock import patch, MagicMock

import pytest

from henchman.utils.lazy_import import getattr_for_textual_app


class TestLazyImport:
    """Test lazy import utilities."""

    def test_getattr_for_textual_app_returns_callable(self):
        """Test that getattr_for_textual_app returns a callable function."""
        result = getattr_for_textual_app("test_module")
        assert callable(result)
        assert result.__name__ == "__getattr__"

    def test_getattr_lazy_imports_app(self):
        """Test that accessing 'app' attribute triggers lazy import."""
        # Create the __getattr__ function
        module_name = "test_module"
        getattr_func = getattr_for_textual_app(module_name)
        
        # Mock the import from henchman.cli.textual_app
        mock_app_class = MagicMock()
        with patch("henchman.cli.textual_app.HenchmanTextualApp", mock_app_class):
            # Access 'app' attribute
            result = getattr_func("app")
            
            # Should return the mocked class
            assert result is mock_app_class

    def test_getattr_raises_for_unknown_attribute(self):
        """Test that accessing unknown attribute raises AttributeError."""
        module_name = "test_module"
        getattr_func = getattr_for_textual_app(module_name)
        
        # Try to access unknown attribute
        with pytest.raises(AttributeError) as exc_info:
            getattr_func("unknown_attribute")
        
        # Check error message
        assert f"module {module_name!r} has no attribute 'unknown_attribute'" in str(exc_info.value)

    def test_getattr_raises_for_empty_name(self):
        """Test that accessing empty attribute name raises AttributeError."""
        module_name = "test_module"
        getattr_func = getattr_for_textual_app(module_name)
        
        # Try to access empty attribute name
        with pytest.raises(AttributeError) as exc_info:
            getattr_func("")
        
        # Check error message
        assert f"module {module_name!r} has no attribute ''" in str(exc_info.value)

    def test_getattr_case_sensitive(self):
        """Test that attribute access is case-sensitive."""
        module_name = "test_module"
        getattr_func = getattr_for_textual_app(module_name)
        
        # 'App' should not work, only 'app' works
        with pytest.raises(AttributeError) as exc_info:
            getattr_func("App")
        
        assert f"module {module_name!r} has no attribute 'App'" in str(exc_info.value)

    def test_module_usage_example(self):
        """Test the example usage pattern from docstring."""
        # Simulate a module using this pattern - simpler approach
        module_name = "fake_module"
        getattr_func = getattr_for_textual_app(module_name)
        
        # Mock the import from henchman.cli.textual_app
        mock_app_class = MagicMock()
        with patch("henchman.cli.textual_app.HenchmanTextualApp", mock_app_class):
            # Access 'app' attribute using the function directly
            result = getattr_func("app")
            
            # Should return the mocked class
            assert result is mock_app_class
            
            # Try to access unknown attribute
            with pytest.raises(AttributeError) as exc_info:
                getattr_func("unknown_attr")
            
            assert "module 'fake_module' has no attribute 'unknown_attr'" in str(exc_info.value)