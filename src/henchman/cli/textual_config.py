"""Configuration and component initialization for the Textual TUI.

This module contains configuration dataclasses and the component
initializer that wires up core Henchman services for the TUI.

Note: This module was extracted from ``textual_app.py`` to enforce
the single-responsibility principle and keep modules under 500 lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from henchman.cli.core_init import CoreContext, create_core_context, initialize_mcp
from henchman.cli.output_handler import OutputHandler
from henchman.cli.repl import ReplConfig
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.ui_renderer import UIRenderer

if TYPE_CHECKING:
    from henchman.cli.command_processor import CommandProcessor
    from henchman.cli.input_handler import InputHandler
    from henchman.cli.textual_bridge import TuiConsoleAdapter
    from henchman.providers.base import ModelProvider

# Default theme applied when none is configured or the name is invalid.
_DEFAULT_THEME_NAME = "dark"


@dataclass
class TextualConfig(ReplConfig):
    """Configuration for the Textual TUI.

    Inherits from ReplConfig to avoid duplication and ensure compatibility
    with InputHandler which expects ReplConfig.

    Attributes:
        prompt: The prompt string to display.
        system_prompt: System prompt for the agent.
        auto_save: Whether to auto-save sessions on exit.
        history_file: Path to history file.
        base_tool_iterations: Base limit for tool iterations per turn.
        max_tool_calls_per_turn: Max tool calls allowed per turn.
        auto_approve_tools: Auto-approve all tool executions.
    """


@dataclass
class ComponentConfig:
    """Configuration for component initialization.

    Attributes:
        provider: The model provider to use.
        config: Textual TUI configuration.
        settings: Application settings.
        environment_context: Pre-formatted environment context.
        app: Reference to the Textual app instance.
    """

    provider: ModelProvider
    config: TextualConfig
    settings: Any  # Settings — avoids circular import
    environment_context: str | None
    app: Any  # HenchmanTextualApp — avoids circular import


class ComponentInitializer:
    """Wires up core Henchman components for the Textual TUI.

    Encapsulates the complex setup sequence so it is testable
    and maintainable independently of the app class.
    """

    def __init__(
        self,
        config: ComponentConfig,
        class_overrides: dict[str, Any] | None = None,
    ) -> None:
        """Initialize the component initializer.

        Args:
            config: Component configuration bundle.
            class_overrides: Optional mapping of dependency names
                to replacement callables.  Supported keys:
                ``create_core_context``, ``UIRenderer``,
                ``OutputHandler``, ``ToolExecutor``,
                ``CommandProcessor``, ``InputHandler``.
                The caller passes module-level references so
                that tests can patch them on the originating
                module.
        """
        self.config = config
        ov = class_overrides or {}
        self._create_context_fn = ov.get("create_core_context", create_core_context)
        self._ui_renderer_cls = ov.get("UIRenderer", UIRenderer)
        self._output_handler_cls = ov.get("OutputHandler", OutputHandler)
        self._tool_executor_cls = ov.get("ToolExecutor", ToolExecutor)
        self._command_processor_cls: Any = ov.get("CommandProcessor", None)
        self._input_handler_cls: Any = ov.get("InputHandler", None)
        self.core_context: CoreContext | None = None
        self.tool_executor: ToolExecutor | None = None
        self.command_processor: CommandProcessor | None = None
        self.input_handler: InputHandler | None = None
        self.output_handler: OutputHandler | None = None
        self._tui_adapter: TuiConsoleAdapter | None = None
        self._ui_renderer: UIRenderer | None = None

    def initialize_all(self) -> None:
        """Initialize all core components in dependency order.

        Note:
            MCP initialization is handled by the caller
            so the module-level ``initialize_mcp`` name
            can be patched in tests.
        """
        self._initialize_tui_adapter()
        self._initialize_core_context()
        self._initialize_renderer()
        self._initialize_output_handler()
        self._initialize_command_processor()
        self._initialize_tool_executor()
        self._initialize_input_handler()

    # -- private helpers (one responsibility each) --

    def _initialize_tui_adapter(self) -> None:
        """Create the TUI console adapter."""
        from henchman.cli.textual_bridge import TuiConsoleAdapter

        self._tui_adapter = TuiConsoleAdapter(self.config.app)

    def _initialize_core_context(self) -> None:
        """Create the core context and register UI instance."""
        self.core_context = self._create_context_fn(
            provider=self.config.provider,
            system_prompt=self.config.config.system_prompt,
            environment_context=self.config.environment_context,
            settings=self.config.settings,
            auto_approve_tools=(self.config.config.auto_approve_tools),
        )
        # Store app reference in plugin manager if it has ui_instance attribute
        # This allows plugins to access the Textual UI if needed
        plugin_manager = self.core_context.plugin_manager
        if hasattr(plugin_manager, "ui_instance"):
            plugin_manager.ui_instance = self.config.app

    def _initialize_renderer(self) -> None:
        """Create the UI renderer with the configured theme."""
        from henchman.cli.console import OutputRenderer, ThemeManager

        if not self._tui_adapter:
            msg = "TUI adapter must be initialized first"
            raise RuntimeError(msg)

        console = self._tui_adapter.console
        theme_manager = ThemeManager()
        theme_name = self._resolve_theme_name(theme_manager)
        theme = theme_manager.get_theme(theme_name)
        output_renderer = OutputRenderer(console=console, theme=theme)
        self._ui_renderer = self._ui_renderer_cls(
            console=console, renderer=output_renderer,
        )

    def _resolve_theme_name(self, theme_manager: Any) -> str:
        """Determine the effective theme name.

        Falls back to the default if the configured name is invalid.

        Args:
            theme_manager: A ``ThemeManager`` instance.

        Returns:
            Valid theme name string.
        """
        settings = self.config.settings
        has_theme = settings and settings.ui and settings.ui.theme
        name = settings.ui.theme if has_theme else _DEFAULT_THEME_NAME
        if name not in theme_manager.list_themes():
            return _DEFAULT_THEME_NAME
        return name

    def _initialize_output_handler(self) -> None:
        """Create the output handler."""
        if not self.core_context or not self._ui_renderer:
            msg = "Core context and renderer must be initialized"
            raise RuntimeError(msg)
        self.output_handler = self._output_handler_cls(
            renderer=self._ui_renderer,
            tool_manager=self.core_context.tool_manager,
            session_manager=self.core_context.session_manager,
            provider=self.config.provider,
            settings=self.config.settings,
            rag_system=None,
            mcp_manager=self.core_context.mcp_manager,
        )

    def _initialize_command_processor(self) -> None:
        """Create the command processor."""
        if not self.core_context or not self.output_handler:
            msg = "Core context and output handler required"
            raise RuntimeError(msg)
        if not self._command_processor_cls:
            from henchman.cli.command_processor import (
                CommandProcessor,
            )

            self._command_processor_cls = CommandProcessor
        self.command_processor = self._command_processor_cls(
            output_handler=self.output_handler,
            tool_manager=self.core_context.tool_manager,
            session_manager=(self.core_context.session_manager),
            provider=self.config.provider,
            mcp_manager=self.core_context.mcp_manager,
        )

    def _initialize_tool_executor(self) -> None:
        """Create the tool executor."""
        if not self.core_context or not self.output_handler:
            msg = "Core context and output handler required"
            raise RuntimeError(msg)
        self.tool_executor = self._tool_executor_cls(
            output_handler=self.output_handler,
            tool_manager=self.core_context.tool_manager,
            provider=self.config.provider,
            base_tool_iterations=(self.config.config.base_tool_iterations),
            max_tool_calls_per_turn=(self.config.config.max_tool_calls_per_turn),
        )

    def _initialize_input_handler(self) -> None:
        """Create the input handler."""
        if not self._ui_renderer:
            msg = "Renderer must be initialized first"
            raise RuntimeError(msg)
        if not self._input_handler_cls:
            from henchman.cli.input_handler import (
                InputHandler,
            )

            self._input_handler_cls = InputHandler
        history_file = (
            self.config.config.history_file or Path.home() / ".henchman_history"
        )
        keybindings = self._get_keybindings()
        self.input_handler = self._input_handler_cls(
            config=self.config.config,
            renderer=self._ui_renderer,
            history_file=history_file,
            keybindings=keybindings,
        )

    def _get_keybindings(self) -> Any:
        """Extract keybindings from settings.

        Returns:
            Keybindings object or ``None``.
        """
        settings = self.config.settings
        if settings and settings.ui:
            return settings.ui.keybindings
        return None

    def _initialize_mcp(self) -> None:
        """Initialize MCP if a manager is available."""
        if self.core_context and self.core_context.mcp_manager:
            initialize_mcp(self.core_context)
