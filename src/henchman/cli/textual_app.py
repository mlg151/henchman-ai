"""Textual TUI for Henchman-AI.

This module provides a Textual-based terminal user interface for
Henchman-AI, with full feature parity with the Rich/prompt_toolkit
REPL plus a multi-pane layout, real search, provider switching, and
an interactive context tree.

The implementation is split across several sibling modules for
maintainability (each kept under 500 lines):

- ``textual_config``   - configuration dataclasses and initializer
- ``textual_messages``  - Textual Message subclasses
- ``textual_widgets``   - chat pane, input area, status bar
- ``textual_bridge``    - TuiConsoleAdapter and EventBridge
- ``textual_screens``   - modal screens (confirm, help, provider)
- ``textual_mixins``    - mixin classes for the main application

All public symbols are re-exported here so existing imports of the
form ``from henchman.cli.textual_app import X`` continue to work.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    Footer,
    Header,
    OptionList,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)

from henchman.cli.command_processor import CommandProcessor
from henchman.cli.core_init import (
    create_core_context,
    initialize_mcp,
)
from henchman.cli.input import expand_at_references
from henchman.cli.input_handler import InputHandler
from henchman.cli.output_handler import OutputHandler
from henchman.cli.textual_bridge import EventBridge, TuiConsoleAdapter
from henchman.cli.textual_config import (
    ComponentConfig,
    ComponentInitializer,
    TextualConfig,
)
from henchman.cli.textual_messages import (
    AgentContentMessage,
    AgentFinishedMessage,
    AgentStatusMessage,
    AgentThoughtMessage,
    CommandOutputMessage,
    SwitchProviderMessage,
    ToolCallRequestMessage,
    ToolCallResultMessage,
    ToolConfirmationMessage,
)
from henchman.cli.textual_mixins import (
    _CommandPaletteMixin,
    _ContextTreeMixin,
    _extract_line_text,
    _HistoryMixin,
    _InitMixin,
    _InputHandlerMixin,
    _MessageHandlerMixin,
    _PaneActionMixin,
    _ProviderMixin,
    _ProxyMixin,
    _PublicAPIMixin,
    _SearchMixin,
    _StatusBarMixin,
)
from henchman.cli.textual_screens import (
    ConfirmToolScreen,
    HelpScreen,
    ProviderScreen,
    SessionScreen,
)
from henchman.cli.textual_widgets import (
    ChatMessage,
    ChatPane,
    HenchmanTextArea,
    ProgressIndicator,
    StatusBar,
    ThinkingMessage,
    ThinkingPane,
    ToolMessage,
    ToolPane,
)
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.ui_renderer import UIRenderer

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.providers.base import ModelProvider

# Re-export all public symbols for backward compatibility.
# Includes Textual widget classes that test suites patch via this module.
__all__ = [
    "AgentContentMessage",
    "AgentFinishedMessage",
    "AgentStatusMessage",
    "AgentThoughtMessage",
    "ChatMessage",
    "ChatPane",
    "CommandOutputMessage",
    "CommandProcessor",
    "ComponentConfig",
    "ComponentInitializer",
    "ConfirmToolScreen",
    "EventBridge",
    "Footer",
    "Header",
    "HelpScreen",
    "HenchmanTextArea",
    "HenchmanTextualApp",
    "InputHandler",
    "OutputHandler",
    "ProgressIndicator",
    "ProviderScreen",
    "SessionScreen",
    "Static",
    "StatusBar",
    "SwitchProviderMessage",
    "TabPane",
    "TabbedContent",
    "TextualConfig",
    "ThinkingMessage",
    "ToolCallRequestMessage",
    "ToolCallResultMessage",
    "ToolConfirmationMessage",
    "ToolExecutor",
    "ToolMessage",
    "Tree",
    "TuiConsoleAdapter",
    "UIRenderer",
    "create_core_context",
    "expand_at_references",
    "initialize_mcp",
    "run_textual_app",
]

# Re-export for backward-compatible imports.
_extract_line_text  # noqa: B018  # noqa: B018  # noqa: B018


# ------------------------------------------------------------------ #
# Main application                                                     #
# ------------------------------------------------------------------ #


class HenchmanTextualApp(
    _ProxyMixin,
    _InitMixin,
    _ProviderMixin,
    _StatusBarMixin,
    _HistoryMixin,
    _ContextTreeMixin,
    _InputHandlerMixin,
    _CommandPaletteMixin,
    _MessageHandlerMixin,
    _PaneActionMixin,
    _SearchMixin,
    _PublicAPIMixin,
    App,  # type: ignore[type-arg]
):
    """Main Textual TUI application for Henchman-AI."""

    CSS_PATH = "henchman.tcss"

    # Active colour theme name ("dark" or "light").
    _theme_name: ClassVar[str] = "dark"

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+f", "search", "Search", show=True),
        Binding(
            "escape",
            "cancel_or_clear",
            "Cancel/Clear",
            show=True,
        ),
        Binding("f3", "search_next", "Next Match", show=False),
        Binding(
            "shift+f3",
            "search_previous",
            "Prev Match",
            show=False,
        ),
        Binding(
            "ctrl+enter",
            "submit_message",
            "Submit",
            show=True,
        ),
        Binding("f1", "show_help", "Help", show=True),
        Binding(
            "f2",
            "switch_provider",
            "Provider",
            show=True,
        ),
        Binding(
            "f4",
            "toggle_theme",
            "Theme",
            show=True,
        ),
    ]

    def __init__(
        self,
        provider: ModelProvider | None = None,
        config: TextualConfig | None = None,
        settings: Settings | None = None,
        environment_context: str | None = None,
        driver_class: type[Any] | None = None,
    ) -> None:
        """Initialize the Textual TUI.

        Args:
            provider: Model provider (resolved from env if omitted).
            config: TUI configuration.
            settings: Application settings.
            environment_context: Pre-formatted environment block.
            driver_class: Custom driver class for terminal handling.
        """
        super().__init__(driver_class=driver_class)
        self._init_provider_and_settings(
            provider,
            config,
            settings,
            environment_context,
        )
        self._init_state()

    def compose(self) -> ComposeResult:
        """Build the widget tree.

        Returns:
            ComposeResult with the full layout.
        """
        yield Header()
        with TabbedContent():
            with TabPane("Chat", id="tab-chat"):
                yield ChatPane(id="chat-pane")
            with TabPane("Thinking", id="tab-thinking"):
                yield ThinkingPane(id="thinking-pane")
            with TabPane("Tools", id="tab-tools"):
                yield ToolPane(id="tool-pane")
            with TabPane("Context", id="tab-context"):
                yield Tree("Context Files", id="context-tree")
        yield OptionList(id="command-palette")
        yield HenchmanTextArea(id="input", show_line_numbers=False)
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize core components after DOM is ready.

        Returns:
            None
        """
        self._initialize_core_components()
        from henchman import __version__

        self.sub_title = f"Henchman-AI v{__version__} - {self.provider.name}"
        self._apply_theme()
        self._populate_context_tree()
        self._show_welcome()
        input_widget = self.query_one("#input", TextArea)
        input_widget.focus()
        self._load_history()
        self.call_after_refresh(input_widget.focus)
        self._activate_chat_tab()

    def on_unmount(self) -> None:
        """Clean up resources when the app is unmounted.

        Returns:
            None
        """
        self._cleanup_confirm_futures()


# ------------------------------------------------------------------ #
# Entry point helpers                                                  #
# ------------------------------------------------------------------ #

_UNICODE_ERROR_MSG: str = (
    "\n[ERROR] Textual crashed due to UnicodeDecodeError.\n"
    "        Please ensure your terminal is set to UTF-8.\n"
    "        Try running: export LC_ALL=C.UTF-8\n"
)


def _check_utf8_encoding() -> None:
    """Warn if the terminal encoding is not UTF-8."""
    if sys.platform == "win32":  # pragma: no cover
        return
    try:
        encoding = getattr(sys.stdin, "encoding", "").lower()
        if encoding and encoding != "utf-8":
            print(
                f"[WARN] Terminal encoding is '{sys.stdin.encoding}', "
                "not 'utf-8'.\n"
                "       Textual TUI requires UTF-8. Please set:\n"
                "       export LANG=C.UTF-8\n"
                "       export LC_ALL=C.UTF-8",
                file=sys.stderr,
            )
    except Exception:
        pass


def run_textual_app(
    provider: ModelProvider,
    config: TextualConfig | None = None,
    settings: Settings | None = None,
    environment_context: str | None = None,
) -> None:
    """Launch the Textual TUI.

    Args:
        provider: Model provider for LLM interactions.
        config: TUI configuration.
        settings: Application settings.
        environment_context: Pre-formatted environment block.

    Returns:
        None
    """
    _check_utf8_encoding()
    from henchman.cli.textual_driver import RobustLinuxDriver

    driver_class = None
    if sys.platform == "linux" and RobustLinuxDriver is not None:
        driver_class = RobustLinuxDriver
    app = HenchmanTextualApp(
        provider=provider,
        config=config,
        settings=settings,
        environment_context=environment_context,
        driver_class=driver_class,
    )
    try:
        app.run()
    except UnicodeDecodeError:
        print(_UNICODE_ERROR_MSG, file=sys.stderr)
        raise
    except Exception as exc:
        if "UnicodeDecodeError" in str(exc):
            print(_UNICODE_ERROR_MSG, file=sys.stderr)
        raise
