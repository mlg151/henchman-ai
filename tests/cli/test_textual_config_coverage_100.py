"""Tests to achieve 100% coverage for cli/textual_config.py.

Targets missing lines:
- 160-161: RuntimeError when _tui_adapter is None in _initialize_renderer
- 194-195: RuntimeError when conditions not met in _initialize_output_handler
- 209-210: RuntimeError when conditions not met in _initialize_command_processor
- 212-216: Import path for CommandProcessor when _command_processor_cls is None
- 228-229: RuntimeError when conditions not met in _initialize_tool_executor
- 241-242: RuntimeError when _ui_renderer is None in _initialize_input_handler
- 244-248: Import path for InputHandler when _input_handler_cls is None
- 271-272: _initialize_mcp when core_context.mcp_manager exists
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.textual_config import ComponentConfig, ComponentInitializer, TextualConfig


def make_component_config(**kwargs: Any) -> ComponentConfig:
    """Create a ComponentConfig for testing.

    Returns:
        ComponentConfig with mocked dependencies.
    """
    provider = MagicMock()
    provider.name = "test"
    settings = MagicMock()
    settings.ui.theme = "dark"
    settings.ui.keybindings = {}
    app = MagicMock()

    defaults = {
        "provider": provider,
        "config": TextualConfig(),
        "settings": settings,
        "environment_context": "",
        "app": app,
    }
    defaults.update(kwargs)
    return ComponentConfig(**defaults)


def make_initializer(**kwargs: Any) -> ComponentInitializer:
    """Create a ComponentInitializer with mocked class overrides.

    Returns:
        ComponentInitializer ready for testing individual methods.
    """
    config = make_component_config()
    overrides = {
        "create_core_context": MagicMock(return_value=MagicMock()),
        "UIRenderer": MagicMock(return_value=MagicMock()),
        "OutputHandler": MagicMock(return_value=MagicMock()),
        "ToolExecutor": MagicMock(return_value=MagicMock()),
    }
    overrides.update(kwargs)
    return ComponentInitializer(config, class_overrides=overrides)


class TestComponentInitializerErrorPaths:
    """Tests for RuntimeError paths in ComponentInitializer."""

    def test_initialize_renderer_no_tui_adapter_raises(self) -> None:
        """Lines 160-161: RuntimeError when _tui_adapter is None."""
        init = make_initializer()
        init._tui_adapter = None  # Not set

        with pytest.raises(RuntimeError, match="TUI adapter must be initialized first"):
            init._initialize_renderer()

    def test_initialize_output_handler_no_core_context_raises(self) -> None:
        """Lines 194-195: RuntimeError when core_context is None."""
        init = make_initializer()
        init.core_context = None
        init._ui_renderer = None

        with pytest.raises(RuntimeError, match="Core context and renderer must be initialized"):
            init._initialize_output_handler()

    def test_initialize_output_handler_no_renderer_raises(self) -> None:
        """Lines 194-195: RuntimeError when _ui_renderer is None."""
        init = make_initializer()
        init.core_context = MagicMock()
        init._ui_renderer = None  # Missing renderer

        with pytest.raises(RuntimeError, match="Core context and renderer must be initialized"):
            init._initialize_output_handler()

    def test_initialize_command_processor_no_core_context_raises(self) -> None:
        """Lines 209-210: RuntimeError when core_context is None."""
        init = make_initializer()
        init.core_context = None
        init.output_handler = None

        with pytest.raises(RuntimeError, match="Core context and output handler required"):
            init._initialize_command_processor()

    def test_initialize_command_processor_no_output_handler_raises(self) -> None:
        """Lines 209-210: RuntimeError when output_handler is None."""
        init = make_initializer()
        init.core_context = MagicMock()
        init.output_handler = None  # Missing

        with pytest.raises(RuntimeError, match="Core context and output handler required"):
            init._initialize_command_processor()

    def test_initialize_tool_executor_no_core_context_raises(self) -> None:
        """Lines 228-229: RuntimeError when core_context is None."""
        init = make_initializer()
        init.core_context = None
        init.output_handler = None

        with pytest.raises(RuntimeError, match="Core context and output handler required"):
            init._initialize_tool_executor()

    def test_initialize_input_handler_no_renderer_raises(self) -> None:
        """Lines 241-242: RuntimeError when _ui_renderer is None."""
        init = make_initializer()
        init._ui_renderer = None  # Not initialized

        with pytest.raises(RuntimeError, match="Renderer must be initialized first"):
            init._initialize_input_handler()


class TestComponentInitializerImportPaths:
    """Tests for lazy import paths in ComponentInitializer."""

    def test_initialize_command_processor_imports_when_class_none(self) -> None:
        """Lines 212-216: CommandProcessor is imported when _command_processor_cls is None."""
        init = make_initializer()
        init.core_context = MagicMock()
        init.core_context.tool_manager = MagicMock()
        init.core_context.session_manager = MagicMock()
        init.core_context.mcp_manager = None
        init.output_handler = MagicMock()
        # _command_processor_cls is None by default (not in overrides above)
        assert init._command_processor_cls is None

        mock_cp_cls = MagicMock()
        mock_cp_instance = MagicMock()
        mock_cp_cls.return_value = mock_cp_instance

        with patch("henchman.cli.command_processor.CommandProcessor", mock_cp_cls):
            init._initialize_command_processor()

        # After initialization, _command_processor_cls should be set
        assert init._command_processor_cls is not None

    def test_initialize_input_handler_imports_when_class_none(self) -> None:
        """Lines 244-248: InputHandler is imported when _input_handler_cls is None."""
        init = make_initializer()
        init._ui_renderer = MagicMock()
        # _input_handler_cls is None by default
        assert init._input_handler_cls is None

        mock_ih_cls = MagicMock()
        mock_ih_instance = MagicMock()
        mock_ih_cls.return_value = mock_ih_instance

        with patch("henchman.cli.input_handler.InputHandler", mock_ih_cls):
            init._initialize_input_handler()

        assert init._input_handler_cls is not None

    def test_initialize_mcp_calls_initialize_mcp_when_manager_exists(self) -> None:
        """Lines 271-272: _initialize_mcp calls initialize_mcp when mcp_manager exists."""
        init = make_initializer()
        mock_ctx = MagicMock()
        mock_ctx.mcp_manager = MagicMock()  # Non-None manager
        init.core_context = mock_ctx

        with patch("henchman.cli.textual_config.initialize_mcp") as mock_init_mcp:
            init._initialize_mcp()

        mock_init_mcp.assert_called_once_with(mock_ctx)

    def test_initialize_mcp_does_nothing_when_no_manager(self) -> None:
        """_initialize_mcp does nothing when mcp_manager is None."""
        init = make_initializer()
        mock_ctx = MagicMock()
        mock_ctx.mcp_manager = None
        init.core_context = mock_ctx

        with patch("henchman.cli.textual_config.initialize_mcp") as mock_init_mcp:
            init._initialize_mcp()

        mock_init_mcp.assert_not_called()
