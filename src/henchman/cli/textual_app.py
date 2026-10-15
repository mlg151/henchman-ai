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

import asyncio
import sys
from contextlib import suppress
from typing import TYPE_CHECKING, Any, ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import (
    Button,
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
    _active_display_provider,
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
    _WorkspaceMixin,
)
from henchman.cli.textual_screens import (
    AutoModeScreen,
    BridgeScreen,
    ConfirmToolScreen,
    ExportScreen,
    FeedbackScreen,
    HelpScreen,
    HistorySearchScreen,
    McpServersScreen,
    ModelPickerScreen,
    OnboardingScreen,
    ProviderScreen,
    SearchScreen,
    SessionScreen,
    ThemePickerScreen,
)
from henchman.cli.textual_widgets import (
    AgentSummaryPanel,
    ChatMessage,
    ChatPane,
    HenchmanTextArea,
    MemoryIndicator,
    ProgressIndicator,
    SettingsPanel,
    SkillPanel,
    StatusBar,
    TaskListWidget,
    TeamPanel,
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
    "AutoModeScreen",
    "BridgeScreen",
    "ChatMessage",
    "ChatPane",
    "CommandOutputMessage",
    "CommandProcessor",
    "ComponentConfig",
    "ComponentInitializer",
    "ConfirmToolScreen",
    "EventBridge",
    "ExportScreen",
    "FeedbackScreen",
    "Footer",
    "Header",
    "HelpScreen",
    "HenchmanTextArea",
    "HenchmanTextualApp",
    "HistorySearchScreen",
    "InputHandler",
    "McpServersScreen",
    "ModelPickerScreen",
    "OnboardingScreen",
    "OutputHandler",
    "ProgressIndicator",
    "ProviderScreen",
    "SearchScreen",
    "SessionScreen",
    "Static",
    "StatusBar",
    "SwitchProviderMessage",
    "TabPane",
    "TabbedContent",
    "TextualConfig",
    "ThemePickerScreen",
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
    _PublicAPIMixin,
    _SearchMixin,
    _WorkspaceMixin,
    App,  # type: ignore[type-arg]
):
    """Main Textual TUI application for Henchman-AI."""

    CSS_PATH = "henchman.tcss"

    # Active colour theme name ("dark" or "light").
    _theme_name: str = "dark"

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
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

    async def _textual_question(self, question: str) -> str | None:
        """Collect an answer through the serialized Textual tool dialog."""
        return await self._tool_prompts.ask(question)

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
            with TabPane("Workspace", id="tab-workspace"):
                yield VerticalScroll(
                    AgentSummaryPanel(id="agent-summary-panel"),
                    MemoryIndicator(id="memory-indicators"),
                    TaskListWidget(id="task-list-widget"),
                    SkillPanel(id="skill-components"),
                    TeamPanel(id="team-components"),
                    SettingsPanel(id="settings-panels"),
                    Horizontal(
                        Button("Refresh", id="workspace-refresh"),
                        Button("Bridges", id="workspace-bridges"),
                        Button("Export", id="workspace-export"),
                        id="workspace-actions",
                    ),
                    id="workspace-overview",
                )
        yield OptionList(id="command-palette")
        yield HenchmanTextArea(id="input", show_line_numbers=False)
        yield Footer()
        yield StatusBar(id="status-bar")

    def on_mount(self) -> None:
        """Initialize core components after DOM is ready.

        Returns:
            None
        """
        self._initialize_core_components()
        from henchman import __version__

        provider = _active_display_provider(self)
        self.sub_title = f"Henchman-AI v{__version__} - {provider.name if provider else 'unknown'}"
        self._apply_theme()
        self._populate_context_tree()
        self._show_welcome()
        input_widget = self.query_one("#input", TextArea)
        input_widget.focus()
        self._load_history()
        self._refresh_workspace_widgets()
        self.call_after_refresh(input_widget.focus)
        self._activate_chat_tab()

    async def on_unmount(self) -> None:
        """Clean up resources when the app is unmounted.

        Returns:
            None
        """
        self._cleanup_confirm_futures()
        self._queued_inputs().clear()
        task = getattr(self, "current_agent_task", None)
        try:
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        finally:
            ctx = self.core_context
            if ctx:
                for background in ctx.background_tasks:
                    background.cancel()
                if ctx.background_tasks:
                    await asyncio.gather(*ctx.background_tasks, return_exceptions=True)
                    ctx.background_tasks.clear()
                try:
                    await ctx.orchestrator.aclose()
                finally:
                    try:
                        if ctx.mcp_manager:
                            await ctx.mcp_manager.disconnect_all()
                    finally:
                        if ctx.session_manager:
                            self._pause_active_goal()
                            ctx.session_manager.auto_save_session()


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
