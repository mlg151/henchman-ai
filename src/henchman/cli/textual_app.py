"""Textual TUI for Henchman-AI.

This module provides a Textual-based terminal user interface for
Henchman-AI, with full feature parity with the Rich/prompt_toolkit
REPL plus a multi-pane layout, real search, provider switching, and
an interactive context tree.

The implementation is split across several sibling modules for
maintainability (each kept under 500 lines):

- ``textual_config``   – configuration dataclasses & initializer
- ``textual_messages``  – Textual Message subclasses
- ``textual_widgets``   – chat pane, input area, status bar
- ``textual_bridge``    – TuiConsoleAdapter & EventBridge
- ``textual_screens``   – modal screens (confirm, help, provider)

All public symbols are re-exported here so existing imports of the
form ``from henchman.cli.textual_app import X`` continue to work.

Note: This file exceeds the 500-line target due to CSS
declarations, re-export boilerplate, and 88-char line wrapping.
To reduce further, extract message handlers into a
``TextualHandlerMixin``, search logic into ``SearchMixin``,
and proxy/convenience properties into ``ProxyMixin``.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    Footer,
    Header,
    OptionList,
    RichLog,
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
from henchman.cli.input_handler import (
    InputHandler,
)
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
from henchman.providers.base import ModelProvider

if TYPE_CHECKING:
    from henchman.config.schema import Settings
    from henchman.core.session import Session
    from henchman.tools.base import ConfirmationRequest

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
    "ProviderScreen",
    "ProgressIndicator",
    "SessionScreen",
    "Static",
    "StatusBar",
    "SwitchProviderMessage",
    "TabbedContent",
    "TabPane",
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

# Maximum characters shown when previewing a context file.
_CONTEXT_FILE_PREVIEW_LIMIT = 5000


# ------------------------------------------------------------------ #
# Main application                                                     #
# ------------------------------------------------------------------ #


class HenchmanTextualApp(App):  # type: ignore[type-arg]
    """Main Textual TUI application for Henchman-AI."""

    CSS_PATH = "henchman.tcss"

    # Active colour theme name ("dark" or "light").
    _theme_name: str = "dark"

    BINDINGS = [
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
    ) -> None:
        """Initialize the Textual TUI.

        Args:
            provider: Model provider (resolved from env if omitted).
            config: TUI configuration.
            settings: Application settings.
            environment_context: Pre-formatted environment block.
        """
        super().__init__()
        self._init_provider_and_settings(
            provider, config, settings, environment_context
        )
        self._init_state()

    # -- init helpers (keep __init__ short) --

    def _init_provider_and_settings(
        self,
        provider: ModelProvider | None,
        config: TextualConfig | None,
        settings: Settings | None,
        env_ctx: str | None,
    ) -> None:
        """Resolve provider, config, and settings.

        Args:
            provider: Optional model provider.
            config: Optional TUI configuration.
            settings: Optional application settings.
            env_ctx: Optional environment context.
        """
        if provider is not None:
            self.provider = provider
            self.config = config or TextualConfig()
            self.settings = settings
            self.environment_context = env_ctx
            return

        self._resolve_provider_from_env()

    def _resolve_provider_from_env(self) -> None:
        """Auto-detect provider from environment."""
        from henchman.cli.app import _get_provider
        from henchman.config import load_settings
        from henchman.config.environment import (
            format_environment_block,
            gather_environment,
        )

        try:
            self.provider = _get_provider()
        except Exception as exc:
            # Create a null provider without hardcoded credentials
            # This is a fallback for UI testing when no real provider is available
            from henchman.providers.base import ModelProvider

            class NullProvider(ModelProvider):
                """A null provider that raises informative errors when used."""

                def __init__(self) -> None:
                    """Initialize the null provider with empty defaults."""
                    self.name = "null"
                    self.supports_tools = False
                    self.supports_streaming = False
                    self.max_tokens = 0

                async def chat_completion(
                    self,
                    messages: list[Any],
                    tools: list[Any] | None = None,
                    **kwargs: Any,
                ) -> Any:
                    """Raise an error indicating no provider is configured."""
                    raise RuntimeError(
                        "No model provider available. "
                        "Please configure a provider via environment variables or settings."
                    )

                async def chat_completion_stream(
                    self,
                    messages: list[Any],
                    tools: list[Any] | None = None,
                    **kwargs: Any,
                ) -> AsyncIterator[Any]:
                    """Raise an error indicating no provider is configured."""
                    raise RuntimeError(
                        "No model provider available. "
                        "Please configure a provider via environment variables or settings."
                    )

                def count_tokens(self, text: str) -> int:
                    """Return zero tokens for the null provider."""
                    return 0

            self.provider = NullProvider()
            import warnings

            warnings.warn(
                f"Failed to initialize provider: {exc}. Using null provider for UI testing only.",
                RuntimeWarning,
                stacklevel=1,
            )

        # Handle potential failures in other initialization steps
        try:
            self.settings = load_settings()
        except Exception as exc:
            import warnings

            warnings.warn(
                f"Failed to load settings: {exc}. Using default settings.",
                RuntimeWarning,
                stacklevel=1,
            )
            # Create minimal default settings
            from henchman.config.schema import Settings

            self.settings = Settings()

        try:
            self.config = TextualConfig()
        except Exception as exc:
            import warnings

            warnings.warn(
                f"Failed to create Textual config: {exc}. Using default config.",
                RuntimeWarning,
                stacklevel=1,
            )
            # Create minimal default config
            self.config = TextualConfig()

        try:
            env_data = gather_environment()
            self.environment_context = format_environment_block(env_data)
        except Exception as exc:
            import warnings

            warnings.warn(
                f"Failed to gather environment: {exc}. Using empty environment context.",
                RuntimeWarning,
                stacklevel=1,
            )
            self.environment_context = "Environment context unavailable"

    def _init_state(self) -> None:
        """Initialize mutable UI state fields."""
        from henchman.cli.core_init import CoreContext

        self.core_context: CoreContext | None = None
        self.tool_executor: ToolExecutor | None = None
        self.command_processor: CommandProcessor | None = None
        self.input_handler: InputHandler | None = None
        self.output_handler: OutputHandler | None = None
        self._tui_adapter: TuiConsoleAdapter | None = None

        self.is_processing: bool = False
        self._streaming_messages: dict[str, ChatMessage] = {}

        # Search state
        self._search_mode: bool = False
        self._search_query: str = ""
        self._search_matches: list[tuple[str, int, str]] = []
        self._current_match_index: int = -1

        # History
        self.command_history: list[str] = []
        self.history_index: int = -1

        # Pending confirmation futures
        self._confirm_futures: dict[int, asyncio.Future[bool]] = {}
        self._confirm_counter: int = 0

        # Proxy compatibility stubs
        self._orchestrator_proxy: Any = None
        self._tool_registry_proxy: Any = None
        self._session_manager_proxy: Any = None

    # ---- proxy properties for CommandContext compat ----

    @property
    def orchestrator(self) -> Any:
        """Proxy to ``core_context.orchestrator``.

        Returns:
            Orchestrator or ``None``.
        """
        if self.core_context:
            return self.core_context.orchestrator
        return None

    @orchestrator.setter
    def orchestrator(self, value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def tool_registry(self) -> Any:
        """Proxy to ``core_context.tool_registry``.

        Returns:
            ToolRegistry or ``None``.
        """
        if self.core_context:
            return self.core_context.tool_registry
        return None

    @tool_registry.setter
    def tool_registry(self, value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def session_manager(self) -> Any:
        """Proxy to ``core_context.session_manager``.

        Returns:
            ReplSessionManager or ``None``.
        """
        if self.core_context:
            return self.core_context.session_manager
        return None

    @session_manager.setter
    def session_manager(self, value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def agent(self) -> Any:
        """Proxy to ``core_context.agent``.

        Returns:
            Agent or ``None``.
        """
        if self.core_context:
            return self.core_context.agent
        return None

    @agent.setter
    def agent(self, value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def rag_system(self) -> None:
        """RAG system (not yet implemented).

        Returns:
            ``None`` always.
        """
        return None

    @property
    def renderer(self) -> UIRenderer | None:
        """UIRenderer instance (backward compatibility).

        Returns:
            UIRenderer or ``None``.
        """
        return getattr(self, "_ui_renderer", None)

    @property
    def current_input(self) -> str:
        """Current text in the input widget.

        Returns:
            Current input text string.
        """
        try:
            return self.query_one("#input", TextArea).text
        except Exception:
            return ""

    # ---- lifecycle ----

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
        """Initialize core components after DOM is ready."""
        self._initialize_core_components()
        from henchman import __version__

        self.sub_title = f"Henchman-AI v{__version__} — {self.provider.name}"
        self._apply_theme()
        self._populate_context_tree()
        self._show_welcome()
        input_widget = self.query_one("#input", TextArea)
        input_widget.focus()
        self._load_history()
        self.call_after_refresh(lambda: input_widget.focus())
        self._activate_chat_tab()

    def on_unmount(self) -> None:
        """Clean up resources when the app is unmounted."""
        self._cleanup_confirm_futures()

    def _activate_chat_tab(self) -> None:
        """Force the Chat tab to be active."""
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = "tab-chat"
        except Exception:
            pass

    # ---- initialization ----

    def _initialize_core_components(self) -> None:
        """Wire up core Henchman components.

        Passes module-level references for ``create_core_context``
        and ``initialize_mcp`` so tests can patch them via
        ``henchman.cli.textual_app.<name>``.
        """
        component_config = ComponentConfig(
            provider=self.provider,
            config=self.config,
            settings=self.settings,
            environment_context=self.environment_context,
            app=self,
        )
        initializer = ComponentInitializer(
            component_config,
            class_overrides={
                "create_core_context": create_core_context,
                "UIRenderer": UIRenderer,
                "OutputHandler": OutputHandler,
                "ToolExecutor": ToolExecutor,
                "CommandProcessor": CommandProcessor,
                "InputHandler": InputHandler,
            },
        )
        initializer.initialize_all()
        self._transfer_components(initializer)
        self._initialize_mcp()
        self._install_confirmation_handler()
        self._update_status_bar()

    def _initialize_mcp(self) -> None:
        """Initialize MCP if a manager is available.

        Uses the module-level ``initialize_mcp`` so tests
        can patch ``henchman.cli.textual_app.initialize_mcp``.
        """
        ctx = self.core_context
        if ctx and ctx.mcp_manager:
            initialize_mcp(ctx)

    def _transfer_components(self, init: ComponentInitializer) -> None:
        """Copy initialized components from initializer.

        Args:
            init: Completed ComponentInitializer.
        """
        self.core_context = init.core_context
        self.tool_executor = init.tool_executor
        self.command_processor = init.command_processor
        self.input_handler = init.input_handler
        self.output_handler = init.output_handler
        self._tui_adapter = init._tui_adapter
        self._ui_renderer = init._ui_renderer

    def _install_confirmation_handler(self) -> None:
        """Replace the tool-confirmation handler with a TUI modal."""
        if self.core_context:
            self.core_context.tool_manager.set_confirmation_handler(
                self._textual_confirm
            )

    async def _textual_confirm(self, request: ConfirmationRequest) -> bool:
        """Show a modal confirmation dialog.

        Args:
            request: The tool confirmation request.

        Returns:
            ``True`` if approved, ``False`` otherwise.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        req_id = self._confirm_counter
        self._confirm_counter += 1
        self._confirm_futures[req_id] = future

        def _callback(result: bool | None) -> None:
            if not future.done():
                future.set_result(bool(result))
            # Always clean up the future from the dictionary
            self._confirm_futures.pop(req_id, None)

        try:
            await self.push_screen(ConfirmToolScreen(request), _callback)
            return await future
        except asyncio.CancelledError:
            # If cancelled, clean up and re-raise
            self._confirm_futures.pop(req_id, None)
            if not future.done():
                future.cancel()
            raise
        except Exception:
            # If any other error occurs, clean up
            self._confirm_futures.pop(req_id, None)
            if not future.done():
                future.set_exception(RuntimeError("Confirmation dialog failed"))
            raise

    def _cleanup_confirm_futures(self) -> None:
        """Clean up all pending confirmation futures to prevent memory leaks."""
        for req_id, future in list(self._confirm_futures.items()):
            if not future.done():
                future.cancel()
            self._confirm_futures.pop(req_id, None)

    # ---- status bar ----

    def _update_status_bar(self) -> None:
        """Refresh the status bar with current info."""
        try:
            bar = self.query_one("#status-bar", StatusBar)
        except Exception:
            return
        bar.status_text = self._build_status_text()

    def _build_status_text(self) -> str:
        """Assemble the status bar text.

        Returns:
            Formatted status string.
        """
        provider = self.provider.name if self.provider else "?"
        model = getattr(self.provider, "model", "?")
        tools = self._count_tools()
        mcp = self._mcp_status_fragment()
        mode = (
            "Plan"
            if (self.settings and getattr(self.settings, "plan_mode", False))
            else "Chat"
        )
        return f"{mode} | {provider}:{model} | Tools: {tools}{mcp}"

    def _count_tools(self) -> int:
        """Count registered tools.

        Returns:
            Number of tools.
        """
        if not self.core_context:
            return 0
        if not self.core_context.tool_registry:
            return 0
        return len(self.core_context.tool_registry.list_tools())

    def _mcp_status_fragment(self) -> str:
        """Build the MCP portion of the status bar.

        Returns:
            MCP status string (empty if no manager).
        """
        if not (self.core_context and self.core_context.mcp_manager):
            return ""
        clients = self.core_context.mcp_manager.clients
        connected = sum(1 for c in clients.values() if getattr(c, "_connected", False))
        return f" | MCP {connected}/{len(clients)}"

    # ---- welcome / history / context tree ----

    def _show_welcome(self) -> None:
        """Display a welcome banner in the chat pane."""
        try:
            chat = self.query_one("#chat-pane", ChatPane)
        except Exception:
            return
        provider = self.provider.name if self.provider else "unknown"
        model = getattr(self.provider, "model", "unknown")
        tools = self._count_tools()
        mcp = self._welcome_mcp_info()
        ctx = " | Context loaded" if self.config.system_prompt else ""
        chat.add_system_message(
            f"[bold]Henchman-AI[/bold] | {provider}:{model} | {tools} tools{mcp}{ctx}"
        )
        chat.add_system_message("Type /help for commands. Press F1 for keybindings.")

    def _welcome_mcp_info(self) -> str:
        """Build MCP info fragment for the welcome banner.

        Returns:
            MCP info string or empty.
        """
        if not (self.core_context and self.core_context.mcp_manager):
            return ""
        total = len(self.core_context.mcp_manager.clients)
        if total:
            return f" | {total} MCP server(s)"
        return ""

    def _load_history(self) -> None:
        """Load command history from the history file."""
        if not self.input_handler:
            return
        hf: Path = getattr(
            self.input_handler,
            "history_file",
            Path.home() / ".henchman_history",
        )
        if not hf.exists():
            return
        try:
            lines = hf.read_text().splitlines()
            self.command_history = [ln for ln in lines if ln.strip()]
            self.history_index = len(self.command_history)
        except Exception:
            pass

    def _populate_context_tree(self) -> None:
        """Populate the Context tab tree."""
        try:
            tree = self.query_one("#context-tree", Tree)
        except Exception:
            return
        self._fill_context_tree(tree)

    def _fill_context_tree(self, tree: Tree) -> None:  # type: ignore[type-arg]
        """Discover and mount context files.

        Args:
            tree: The Tree widget to populate.
        """
        try:
            from henchman.config.context import (
                ContextLoader,
            )

            loader = ContextLoader()
            files = loader.discover_files()
        except Exception as exc:
            # Log the error for debugging
            import logging

            logging.error(f"Failed to load context files: {exc}")

            # Try to show error in UI, but don't crash if it fails
            try:
                tree.root.add_leaf(f"Error loading context: {exc}")
            except Exception as ui_exc:
                logging.error(f"Failed to show error in UI: {ui_exc}")
            return

        if not files:
            tree.root.add_leaf("No context files found")
            return

        by_dir: dict[Path, list[Path]] = {}
        for f in files:
            by_dir.setdefault(f.parent, []).append(f)
        for directory, dir_files in by_dir.items():
            branch = tree.root.add(str(directory), expand=True)
            for p in dir_files:
                branch.add_leaf(p.name, data=p)
        tree.root.expand()

    # ---- input handling ----

    def action_submit_message(self) -> None:
        """Extract text from the input widget and process it."""
        if self.is_processing:
            return
        input_widget = self.query_one("#input", TextArea)
        user_input = input_widget.text.strip()
        if not user_input:
            return
        self.command_history.append(user_input)
        self.history_index = len(self.command_history)
        self._persist_history_entry(user_input)
        input_widget.load_text("")
        self.process_user_input(user_input)

    def _persist_history_entry(self, entry: str) -> None:
        """Append an entry to the history file.

        Args:
            entry: History line to persist.
        """
        if not self.input_handler:
            return
        hf: Path = getattr(
            self.input_handler,
            "history_file",
            Path.home() / ".henchman_history",
        )
        try:
            with open(hf, "a") as fh:
                fh.write(entry + "\n")
        except Exception as exc:
            # Log the error for debugging
            import logging

            logging.error(f"Failed to persist history entry: {exc}")

            # Try to show error notification to user
            try:
                chat = self.query_one("#chat-pane", ChatPane)
                chat.add_error_message(f"Failed to save command history: {exc}")
            except Exception as ui_exc:
                logging.error(f"Failed to show history error in UI: {ui_exc}")

    def _navigate_history(self, direction: int) -> None:
        """Navigate command history.

        Args:
            direction: ``-1`` for older, ``+1`` for newer.
        """
        if not self.command_history:
            return
        new_idx = self.history_index + direction
        widget = self.query_one("#input", TextArea)
        if 0 <= new_idx < len(self.command_history):
            self.history_index = new_idx
            text = self.command_history[new_idx]
            widget.load_text(text)
            widget.cursor_location = (0, len(text))
        elif new_idx >= len(self.command_history):
            self.history_index = len(self.command_history)
            widget.load_text("")

    @work(exclusive=True)
    async def process_user_input(self, user_input: str) -> None:
        """Process user input: commands or agent chat.

        Args:
            user_input: Raw text the user submitted.
        """
        self.is_processing = True
        self.current_agent_task = asyncio.current_task()
        bar = self.query_one("#status-bar", StatusBar)
        chat = self.query_one("#chat-pane", ChatPane)
        bar.status_text = "Processing…"
        chat.add_user_message(user_input)

        try:
            await self._route_input(user_input, chat)
        except asyncio.CancelledError:
            chat.add_system_message("[yellow]⚠ Cancelled by user (Esc)[/]")
        except Exception as exc:
            import traceback

            details = traceback.format_exc()
            # Escape triple backticks in traceback to prevent code fence breakout
            safe_details = details.replace("```", "` ` `")
            chat.add_error_message(f"{exc}\n```\n{safe_details}\n```")
            bar.status_text = f"Error: {exc}"
        finally:
            self.is_processing = False
            if hasattr(self, "current_agent_task"):
                del self.current_agent_task
            self._update_status_bar()

    async def _route_input(self, user_input: str, chat: ChatPane) -> None:
        """Route processed input to command or orchestrator.

        Args:
            user_input: Raw user text.
            chat: The ChatPane widget.
        """
        if not self.input_handler:
            chat.add_error_message("Input handler not initialized.")
            return
        processed, is_cmd, should_continue = await self.input_handler.process_input(
            user_input
        )
        if not should_continue or not processed:
            return
        expanded = await expand_at_references(processed)
        self._record_user_message(expanded)
        if is_cmd:
            await self._handle_command(expanded, chat)
        else:
            await self._run_orchestrator(expanded, chat)

    def _record_user_message(self, text: str) -> None:
        """Record a user message in the session.

        Args:
            text: Expanded user text.
        """
        if self.core_context and self.core_context.session_manager:
            self.core_context.session_manager.record_user_message(text)

    async def _handle_command(self, text: str, chat: ChatPane) -> None:
        """Process a slash command.

        Args:
            text: Expanded command text.
            chat: The ChatPane widget.
        """
        if text.strip().lower() == "/clear":
            chat.clear_messages()
            return
        if not self.command_processor:
            return
        should_continue = await self.command_processor.handle_command(
            text,
            (self.core_context.agent if self.core_context else None),  # type: ignore[arg-type]
            self,  # type: ignore[arg-type]
        )
        if self._tui_adapter:
            self._tui_adapter.flush_to_chat()
        if not should_continue:
            self.exit()

    async def _run_orchestrator(self, text: str, chat: ChatPane) -> None:
        """Send text through the orchestrator.

        Args:
            text: Expanded user text.
            chat: The ChatPane widget.
        """
        if not (self.core_context and self.core_context.orchestrator):
            chat.add_error_message("Core components not initialized.")
            return
        bridge = EventBridge(self)
        stream = self.core_context.orchestrator.run(text)
        await bridge.forward_events(stream)

    # ---- message handlers ----

    def on_agent_content_message(self, message: AgentContentMessage) -> None:
        """Stream text content into the chat pane.

        Args:
            message: Content chunk from an agent.
        """
        chat = self.query_one("#chat-pane", ChatPane)
        name = message.source_agent or "Assistant"
        chat.append_agent_chunk(name, message.content)

    def on_agent_thought_message(self, message: AgentThoughtMessage) -> None:
        """Add thinking content to chat pane and thinking pane.

        Args:
            message: Thought from an agent.
        """
        pane = self.query_one("#chat-pane", ChatPane)
        pane.add_thinking_message(message.thought, message.source_agent or "")

        # Also write to dedicated thinking pane
        try:
            thinking = self.query_one("#thinking-pane", ThinkingPane)
            agent = message.source_agent or "Agent"
            thinking.write(f"[dim]🤔 {agent}: {message.thought}[/]")
            thinking.scroll_end(animate=False)
        except Exception:
            pass

    def on_tool_call_request_message(self, message: ToolCallRequestMessage) -> None:
        """Add a tool call request to both chat and tool panes.

        Args:
            message: Tool call request data.
        """
        tc = message.tool_call
        args_str = self._format_tool_args(tc)
        tool_description = f"{tc.name}: {args_str}" if args_str else tc.name

        # Show in chat pane
        pane = self.query_one("#chat-pane", ChatPane)
        pane.add_tool_message(tool_description, tc)

        # Also write to dedicated tool pane
        try:
            import json

            tool_pane = self.query_one("#tool-pane", ToolPane)
            full_args = ""
            if tc.arguments:
                try:
                    raw = tc.arguments
                    parsed = json.loads(raw) if isinstance(raw, str) else raw
                    full_args = json.dumps(parsed, indent=2)
                except Exception:
                    full_args = str(tc.arguments)
            tool_pane.write(f"[yellow]▶ {tc.name}[/]\n[dim]{full_args}[/]")
            tool_pane.scroll_end(animate=False)
        except Exception:
            pass

    @staticmethod
    def _format_tool_args(tool_call: Any) -> str:
        """Format tool call arguments for display.

        Args:
            tool_call: Tool call with an arguments attr.

        Returns:
            Formatted arguments string.
        """
        if not tool_call.arguments:
            return ""
        try:
            import json

            raw = tool_call.arguments
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            # Return compact JSON for chat display
            return json.dumps(parsed, separators=(",", ":"))
        except Exception:
            return str(tool_call.arguments)

    def on_tool_call_result_message(self, message: ToolCallResultMessage) -> None:
        """Add a tool result to both chat and tool panes.

        Args:
            message: Tool execution result.
        """
        result_str = self._format_tool_result(message.result)

        # Show in chat pane
        pane = self.query_one("#chat-pane", ChatPane)
        pane.add_tool_message(f"Result: {result_str}")

        # Also write to dedicated tool pane
        try:
            tool_pane = self.query_one("#tool-pane", ToolPane)
            tool_pane.write(f"[green]← {result_str}[/]")
            tool_pane.scroll_end(animate=False)
        except Exception:
            pass

    @staticmethod
    def _format_tool_result(result: Any) -> str:
        """Format tool result for display in chat.

        Args:
            result: Tool result data (dict or other).

        Returns:
            Formatted result string.
        """
        _TRUNCATE_LIMIT = 100
        if isinstance(result, dict):
            content = str(result.get("result", result))
            success = result.get("success", True)
            display = content[:_TRUNCATE_LIMIT]
            if len(content) > _TRUNCATE_LIMIT:
                display += "…"
            label = "✓" if success else "✗"
            return f"{label} {display}"
        else:
            content = str(result)
            display = content[:_TRUNCATE_LIMIT]
            if len(content) > _TRUNCATE_LIMIT:
                display += "…"
            return display

    def on_tool_confirmation_message(self, message: ToolConfirmationMessage) -> None:
        """Fallback for TOOL_CONFIRMATION events.

        The ToolManager's handler already shows the modal.

        Args:
            message: Confirmation request message.
        """

    def on_agent_status_message(self, message: AgentStatusMessage) -> None:
        """Update the status bar.

        Args:
            message: Status update from an agent.
        """
        try:
            bar = self.query_one("#status-bar", StatusBar)
            bar.status_text = message.status
        except Exception:
            pass

    def on_agent_finished_message(self, message: AgentFinishedMessage) -> None:
        """Handle agent completion.

        Args:
            message: Finished signal from an agent.
        """
        chat = self.query_one("#chat-pane", ChatPane)
        name = message.source_agent or "Assistant"
        chat.finish_agent_stream(name)
        self._streaming_messages.pop(name, None)
        self._update_status_bar()

    def on_command_output_message(self, message: CommandOutputMessage) -> None:
        """Route command output to the chat pane.

        Args:
            message: Output text from a command.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)
            chat.add_system_message(message.text)
        except Exception:
            pass

    def on_switch_provider_message(self, message: SwitchProviderMessage) -> None:
        """Switch the active provider.

        Args:
            message: Provider switch request.
        """
        self._switch_provider(message.provider_name)

    # ---- provider switching ----

    def _switch_provider(self, provider_name: str) -> None:
        """Reinitialize with a different provider.

        Args:
            provider_name: Provider name key.
        """
        old_provider = self.provider
        old_name = old_provider.name if old_provider else "unknown"

        try:
            from henchman.providers import (
                get_default_registry,
            )

            registry = get_default_registry()
            new = registry.create(provider_name)

            # Try to initialize components with new provider
            # Temporarily set provider for initialization
            self.provider = new
            try:
                self._initialize_core_components()
            except Exception:
                # Revert provider if component initialization fails
                self.provider = old_provider
                raise

            # All operations succeeded, update UI
            from henchman import __version__

            self.sub_title = f"Henchman-AI v{__version__} — {self.provider.name}"
            chat = self.query_one("#chat-pane", ChatPane)
            chat.add_system_message(
                f"Provider switched: [cyan]{old_name}[/] → [cyan]{provider_name}[/]"
            )
            self._update_status_bar()
        except Exception as exc:
            # Ensure provider is reverted if not already done
            if self.provider != old_provider:
                self.provider = old_provider

            # Show error message, handling potential query_one failure
            try:
                chat = self.query_one("#chat-pane", ChatPane)
                chat.add_error_message(f"Failed to switch provider: {exc}")
            except Exception:
                # If we can't show error in UI, at least log it
                import logging

                logging.error(f"Failed to switch provider and show error: {exc}")

    # ---- command palette ----

    @on(TextArea.Changed)
    def on_textarea_changed(self, event: TextArea.Changed) -> None:
        """Show/hide command palette on slash input.

        Args:
            event: TextArea change event.
        """
        text = event.control.text
        if text.startswith("/"):
            self._show_command_palette(text)
        else:
            self._hide_command_palette()

    def _show_command_palette(self, current_text: str) -> None:
        """Populate and display the command palette.

        Args:
            current_text: Text starting with ``/``.
        """
        palette = self.query_one("#command-palette", OptionList)
        palette.display = True
        palette.clear_options()
        query = current_text.lower()
        commands = (
            self.command_processor.command_registry.get_commands()
            if self.command_processor
            else []
        )
        for cmd in commands:
            label = f"/{cmd.name}  — {cmd.description}"
            if f"/{cmd.name}".startswith(query) or query == "/":
                palette.add_option(label)
        if palette.option_count == 0:
            palette.display = False

    def _hide_command_palette(self) -> None:
        """Hide the command palette."""
        palette = self.query_one("#command-palette", OptionList)
        palette.display = False

    @on(OptionList.OptionSelected, "#command-palette")
    def on_command_selected(self, event: OptionList.OptionSelected) -> None:
        """Fill the input with the selected command.

        Args:
            event: Option selection event.
        """
        raw = str(event.option.prompt)
        cmd_part = raw.split("  —")[0].strip()
        widget = self.query_one("#input", TextArea)
        new_text = cmd_part + " "
        widget.load_text(new_text)
        widget.cursor_location = (0, len(new_text))
        widget.focus()
        self._hide_command_palette()

    # ---- search ----

    def action_search(self) -> None:
        """Enter search mode or find next match."""
        if self._search_mode:
            self.action_search_next()
            return
        self._search_mode = True
        bar = self.query_one("#status-bar", StatusBar)
        bar.status_text = "Search: type in input box then press F3"

    def action_cancel_or_clear(self) -> None:
        """Cancel processing or clear search."""
        if self.is_processing and hasattr(self, "current_agent_task"):
            task = self.current_agent_task
            if task is not None:
                task.cancel()
            bar = self.query_one("#status-bar", StatusBar)
            bar.status_text = "Cancelling..."
            return
        self.action_clear_search()

    def action_clear_search(self) -> None:
        """Exit search mode and reset state."""
        self._clear_highlights()
        self._search_mode = False
        self._search_query = ""
        self._search_matches = []
        self._current_match_index = -1
        try:
            bar = self.query_one("#status-bar", StatusBar)
            bar.status_text = "Ready"
        except Exception:
            pass

    def action_search_next(self) -> None:
        """Move to the next search match."""
        if not self._search_mode:
            return
        self._refresh_search_if_changed()
        if not self._search_matches:
            return
        self._current_match_index = (self._current_match_index + 1) % len(
            self._search_matches
        )
        self._scroll_to_match()
        self._update_search_status()

    def action_search_previous(self) -> None:
        """Move to the previous search match."""
        if not self._search_mode:
            return
        self._refresh_search_if_changed()
        if not self._search_matches:
            return
        self._current_match_index = (self._current_match_index - 1) % len(
            self._search_matches
        )
        self._scroll_to_match()
        self._update_search_status()

    def _refresh_search_if_changed(self) -> None:
        """Re-run search if the query text changed."""
        widget = self.query_one("#input", TextArea)
        query = widget.text.strip()
        if query != self._search_query:
            self._perform_search(query)

    def _perform_search(self, query: str) -> None:
        """Index text matches in chat, thinking, and tool panes.

        Args:
            query: Search string (case-insensitive).
        """
        # Clear previous highlights
        self._clear_highlights()

        self._search_query = query
        self._search_matches = []
        self._current_match_index = -1
        if not query:
            self._update_search_status()
            return
        ql = query.lower()
        self._search_chat_pane(ql)
        self._search_richlog_panes(ql)
        self._apply_highlights(query)
        self._update_search_status()

    def _search_chat_pane(self, query_lower: str) -> None:
        """Collect matches from the chat pane.

        Searches ChatMessage, ThinkingMessage, and ToolMessage widgets.

        Args:
            query_lower: Lowercase search query.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)
            for idx, w in enumerate(chat.children):
                content = ""
                if isinstance(w, (ChatMessage, ThinkingMessage, ToolMessage)):
                    content = w._content
                if content and query_lower in content.lower():
                    self._search_matches.append(("chat", idx, content))
        except Exception:
            pass

    def _search_richlog_panes(self, query_lower: str) -> None:
        """Search thinking and tool RichLog panes.

        Args:
            query_lower: Lowercase search query.
        """
        for css_id, pane_id, pane_cls in (
            ("#thinking-pane", "thinking", ThinkingPane),
            ("#tool-pane", "tool", ToolPane),
        ):
            try:
                pane = self.query_one(css_id, pane_cls)
                self._search_richlog(pane, pane_id, query_lower)
            except Exception:
                pass

    def _search_richlog(
        self,
        pane: RichLog,
        pane_id: str,
        query_lower: str,
    ) -> None:
        """Collect matches from a RichLog widget.

        Args:
            pane: The RichLog widget to search.
            pane_id: Identifier string for the pane.
            query_lower: Lowercase search query.
        """
        try:
            lines = getattr(pane, "lines", [])
            if not lines:
                return
            for idx, item in enumerate(lines):
                text = _extract_line_text(item)
                if query_lower in text.lower():
                    self._search_matches.append((pane_id, idx, text))
        except Exception:
            pass

    def _scroll_to_match(self) -> None:
        """Scroll to the current search match."""
        if not self._search_matches or self._current_match_index < 0:
            return
        pane_id, line_idx, _ = self._search_matches[self._current_match_index]
        if pane_id == "chat":
            self._scroll_chat_match(line_idx)
        elif pane_id in ("thinking", "tool"):
            self._scroll_richlog_match(pane_id)

    def _apply_highlights(self, term: str) -> None:
        """Apply search highlight to all matching widgets in the chat pane.

        Args:
            term: Search term to highlight.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)
            for w in chat.children:
                if hasattr(w, "set_highlight"):
                    w.set_highlight(term)
        except Exception:
            pass

    def _clear_highlights(self) -> None:
        """Remove search highlights from all widgets in the chat pane."""
        try:
            chat = self.query_one("#chat-pane", ChatPane)
            for w in chat.children:
                if hasattr(w, "set_highlight"):
                    w.set_highlight("")
        except Exception:
            pass

    def _scroll_chat_match(self, line_idx: int) -> None:
        """Scroll a chat pane child into view.

        Args:
            line_idx: Index of the matching child widget.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)
            children = list(chat.children)
            if 0 <= line_idx < len(children):
                children[line_idx].scroll_visible(animate=False)
        except Exception:
            pass

    def _scroll_richlog_match(self, pane_id: str) -> None:
        """Scroll a RichLog pane to end for visibility.

        Args:
            pane_id: 'thinking' or 'tool'.
        """
        _PANE_MAP: dict[str, tuple[str, type]] = {
            "thinking": (
                "#thinking-pane",
                ThinkingPane,
            ),
            "tool": ("#tool-pane", ToolPane),
        }
        if pane_id not in _PANE_MAP:
            return
        css_id, cls = _PANE_MAP[pane_id]
        try:
            pane: ThinkingPane | ToolPane = self.query_one(css_id, cls)
            pane.scroll_end(animate=False)
        except Exception:
            pass

    def _update_search_status(self) -> None:
        """Refresh the status bar with search info."""
        try:
            bar = self.query_one("#status-bar", StatusBar)
        except Exception:
            return
        if not self._search_mode:
            return
        if not self._search_query:
            bar.status_text = "Search: type query in input box, F3=next"
        elif not self._search_matches:
            bar.status_text = f"No matches for '{self._search_query}'"
        else:
            cur = self._current_match_index + 1
            tot = len(self._search_matches)
            bar.status_text = f"Match {cur}/{tot} for '{self._search_query}' — F3=next  Shift+F3=prev  Esc=clear"

    # ---- pane actions ----

    def action_clear_thinking_pane(self) -> None:
        """Clear the thinking pane and chat thinking messages."""
        self.query_one("#thinking-pane", ThinkingPane).clear()
        self.query_one("#chat-pane", ChatPane).clear_thinking_messages()
        bar = self.query_one("#status-bar", StatusBar)
        bar.status_text = "Thinking cleared (legacy pane and chat messages)"

    def action_clear_tool_pane(self) -> None:
        """Clear all content from the tool pane."""
        self.query_one("#tool-pane", ToolPane).clear()
        bar = self.query_one("#status-bar", StatusBar)
        bar.status_text = "Tool pane cleared"

    def action_toggle_thinking_pane(self) -> None:
        """Toggle the thinking tab."""
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = (
                "tab-chat" if tabs.active == "tab-thinking" else "tab-thinking"
            )
        except Exception:
            pass

    def action_toggle_tool_pane(self) -> None:
        """Toggle the tools tab."""
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = "tab-chat" if tabs.active == "tab-tools" else "tab-tools"
        except Exception:
            pass

    # ---- theme ----

    def _apply_theme(self) -> None:
        """Apply the current theme class to the screen."""
        try:
            for name in ("theme-dark", "theme-light"):
                self.screen.remove_class(name)
            self.screen.add_class(f"theme-{self._theme_name}")
        except Exception:
            pass

    def action_toggle_theme(self) -> None:
        """Toggle between dark and light themes."""
        self._theme_name = "light" if self._theme_name == "dark" else "dark"
        self._apply_theme()
        try:
            chat = self.query_one("#chat-pane", ChatPane)
            chat.add_system_message(f"Theme switched to [cyan]{self._theme_name}[/]")
        except Exception:
            pass
        self.app.dark = self._theme_name == "dark"

    # ---- modal actions ----

    def action_show_help(self) -> None:
        """Show the help/keybinding modal."""
        self.push_screen(HelpScreen())

    def action_switch_provider(self) -> None:
        """Show the provider switching modal."""
        self.push_screen(ProviderScreen())

    # ---- context tree interaction ----

    @work
    async def on_tree_node_selected(self, event: Tree.NodeSelected[object]) -> None:
        """Show file content when a tree node is clicked.

        Args:
            event: Tree node selection event.
        """
        node = event.node
        path: Path | None = node.data  # type: ignore[assignment]
        if not (path and isinstance(path, Path) and path.is_file()):
            return

        chat = self.query_one("#chat-pane", ChatPane)
        chat.add_system_message(f"[dim]Loading {path.name}…[/]")

        try:
            # Get file size first
            stat = await asyncio.to_thread(path.stat)
            size_kb = stat.st_size / 1024

            # Read file asynchronously to prevent UI blocking
            full = await asyncio.to_thread(path.read_text, "utf-8", "replace")
            content = full[:_CONTEXT_FILE_PREVIEW_LIMIT]
            truncated = len(full) > _CONTEXT_FILE_PREVIEW_LIMIT
            if truncated:
                content += "\n… (truncated)"

            header = f"[bold]{path.name}[/bold] ({size_kb:.1f} KB)"
            if truncated:
                header += f" — showing first {_CONTEXT_FILE_PREVIEW_LIMIT:,} chars"
            chat.add_system_message(f"{header}\n{content}")
        except Exception as exc:
            try:
                chat.add_error_message(f"Cannot read {path}: {exc}")
            except Exception:
                import logging

                logging.error(f"Cannot read {path} and show error: {exc}")

    # ---- misc public helpers ----

    def set_session(self, session: Session) -> None:
        """Activate a loaded session.

        Args:
            session: Session to activate.
        """
        if not (self.core_context and self.core_context.session_manager):
            return
        self.core_context.session_manager.set_session(
            session,
            (self.core_context.orchestrator if self.core_context else None),
        )

    def update_status(
        self,
        message: str,
        tokens: int | None = None,
        cost: float | None = None,
    ) -> None:
        """Update the status bar.

        Args:
            message: Status message.
            tokens: Optional token count.
            cost: Optional cost in USD.
        """
        try:
            bar = self.query_one("#status-bar", StatusBar)
            bar.status_text = message
            if tokens is not None:
                bar.tokens = tokens
            if cost is not None:
                bar.cost = cost
        except Exception:
            pass

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat pane.

        Args:
            role: Sender role ('user', 'assistant', 'system').
            content: Message content.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)
        except Exception:
            return
        if role == "user":
            chat.add_user_message(content)
        elif role in ("assistant", "system"):
            chat.add_system_message(content)
        else:
            chat.add_system_message(f"[{role}] {content}")


# ------------------------------------------------------------------ #
# Module-level helpers                                                 #
# ------------------------------------------------------------------ #


def _extract_line_text(item: Any) -> str:
    """Extract plain text from a RichLog line item.

    Handles different Textual version representations.

    Args:
        item: A line item from ``RichLog.lines``.

    Returns:
        Plain text content of the line.
    """
    if hasattr(item, "text"):
        return str(item.text)
    if isinstance(item, str):
        return item
    try:
        return "".join(
            str(seg.text) if hasattr(seg, "text") else str(seg) for seg in item
        )
    except (TypeError, AttributeError):
        return str(item)


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #


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
    """
    app = HenchmanTextualApp(
        provider=provider,
        config=config,
        settings=settings,
        environment_context=environment_context,
    )
    app.run()
