"""Tests for bugs in textual_config.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_config import (
    ComponentConfig,
    ComponentInitializer,
    TextualConfig,
)


def test_bug1_duplicate_config_classes():
    """Bug 1: TextualConfig and ReplConfig are duplicate classes.
    
    Severity: Medium (code duplication, maintenance issue)
    Description: TextualConfig and ReplConfig have identical fields
    but are separate classes, causing type errors and duplication.
    """
    from henchman.cli.repl import ReplConfig
    
    # Check that they have the same fields
    textual_fields = TextualConfig.__dataclass_fields__.keys()
    repl_fields = ReplConfig.__dataclass_fields__.keys()
    
    assert set(textual_fields) == set(repl_fields), \
        f"Fields differ: TextualConfig={textual_fields}, ReplConfig={repl_fields}"
    
    # Check field types match
    for field in textual_fields:
        textual_type = TextualConfig.__dataclass_fields__[field].type
        repl_type = ReplConfig.__dataclass_fields__[field].type
        assert textual_type == repl_type, \
            f"Field {field} type mismatch: {textual_type} != {repl_type}"
    
    # This is the bug - they should be the same class or one should inherit


def test_bug2_input_handler_wrong_config_type():
    """Bug 2: InputHandler receives TextualConfig instead of ReplConfig.
    
    Severity: High (type error, potential runtime issues)
    Description: ComponentInitializer passes TextualConfig to InputHandler
    which expects ReplConfig, causing mypy errors.
    """
    # Create a minimal test
    config = ComponentConfig(
        provider=MagicMock(),
        config=TextualConfig(),
        settings=MagicMock(),
        environment_context="test",
        app=MagicMock(),
    )
    
    initializer = ComponentInitializer(config)
    
    # Mock the InputHandler class to capture what it receives
    mock_input_handler_cls = MagicMock()
    mock_input_handler_cls.return_value = MagicMock()
    
    # Replace the class override
    initializer._input_handler_cls = mock_input_handler_cls
    
    # Mock other dependencies
    initializer._tui_adapter = MagicMock()
    initializer._tui_adapter.console = MagicMock()
    initializer.core_context = MagicMock()
    initializer._ui_renderer = MagicMock()
    initializer.output_handler = MagicMock()
    initializer.command_processor = MagicMock()
    initializer.tool_executor = MagicMock()
    
    # Call the method that has the bug
    initializer._initialize_input_handler()
    
    # Verify InputHandler was called with TextualConfig
    # This is the bug - it should accept TextualConfig or expect ReplConfig
    mock_input_handler_cls.assert_called_once()
    call_kwargs = mock_input_handler_cls.call_args.kwargs
    
    assert 'config' in call_kwargs
    assert isinstance(call_kwargs['config'], TextualConfig)
    
    # The type annotation in InputHandler.__init__ expects ReplConfig
    # but we're passing TextualConfig - this is the bug


def test_bug3_plugin_manager_missing_ui_instance():
    """Bug 3: plugin_manager.ui_instance assignment may fail.
    
    Severity: Medium (potential AttributeError)
    Description: plugin_manager may not have ui_instance attribute,
    causing AttributeError at runtime.
    """
    config = ComponentConfig(
        provider=MagicMock(),
        config=TextualConfig(),
        settings=MagicMock(),
        environment_context="test",
        app=MagicMock(),
    )
    
    initializer = ComponentInitializer(config)
    
    # Mock create_core_context to return a core_context without ui_instance
    mock_core_context = MagicMock()
    mock_core_context.plugin_manager = MagicMock()
    # Remove ui_instance to simulate the bug
    if hasattr(mock_core_context.plugin_manager, 'ui_instance'):
        delattr(mock_core_context.plugin_manager, 'ui_instance')
    
    initializer._create_context_fn = lambda **kwargs: mock_core_context
    
    # This should work but the assignment may fail at runtime
    # if plugin_manager doesn't have ui_instance
    initializer._initialize_core_context()
    
    # Check if assignment was attempted
    # The bug is that we assume ui_instance exists without checking