"""Tests for textual_config.py module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_config import (
    ComponentConfig,
    ComponentInitializer,
    TextualConfig,
)


class TestComponentInitializer:
    """Test suite for ComponentInitializer."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        provider = MagicMock()
        provider.name = "test-provider"
        return provider

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.ui.theme = "dark"
        settings.ui.keybindings = {}
        settings.providers.default = "test-provider"
        return settings

    @pytest.fixture
    def mock_app(self):
        """Create mock Textual app."""
        return MagicMock()

    @pytest.fixture
    def component_config(self, mock_provider, mock_settings, mock_app):
        """Create component configuration."""
        return ComponentConfig(
            provider=mock_provider,
            config=TextualConfig(),
            settings=mock_settings,
            environment_context="Test context",
            app=mock_app,
        )

    def test_initialize_all_creates_input_handler_with_correct_config_type(
        self, component_config
    ):
        """Test that InputHandler is created with correct config type.

        Bug: InputHandler expects ReplConfig but receives TextualConfig.
        This should cause a type error or runtime issue.
        """
        mock_core_context = MagicMock()
        mock_core_context.plugin_manager = MagicMock()
        mock_core_context.tool_manager = MagicMock()
        mock_core_context.session_manager = MagicMock()
        mock_core_context.mcp_manager = None

        mock_command_processor_cls = MagicMock()
        mock_input_handler_cls = MagicMock()
        mock_input_handler = MagicMock()
        mock_input_handler_cls.return_value = mock_input_handler

        overrides = {
            "create_core_context": MagicMock(return_value=mock_core_context),
            "UIRenderer": MagicMock(return_value=MagicMock()),
            "OutputHandler": MagicMock(return_value=MagicMock()),
            "ToolExecutor": MagicMock(return_value=MagicMock()),
            "CommandProcessor": mock_command_processor_cls,
            "InputHandler": mock_input_handler_cls,
        }

        initializer = ComponentInitializer(component_config, class_overrides=overrides)
        initializer.initialize_all()

        mock_input_handler_cls.assert_called_once()
        call_args = mock_input_handler_cls.call_args
        config_arg = call_args[1]["config"]
        assert isinstance(config_arg, TextualConfig)

    def test_plugin_manager_ui_instance_assignment(self, component_config):
        """Test that plugin_manager.ui_instance assignment is handled gracefully.

        When plugin_manager doesn't have ui_instance, the code uses hasattr
        to check first and skips the assignment safely.
        """
        mock_core_context = MagicMock()
        mock_core_context.plugin_manager = MagicMock()
        # Simulate plugin_manager without ui_instance attribute
        delattr(mock_core_context.plugin_manager, "ui_instance")

        overrides = {
            "create_core_context": MagicMock(return_value=mock_core_context),
        }
        initializer = ComponentInitializer(component_config, class_overrides=overrides)

        # Should NOT raise — code uses hasattr guard
        initializer._initialize_core_context()
        assert initializer.core_context is mock_core_context
