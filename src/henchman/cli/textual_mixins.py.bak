"""Mixin classes for HenchmanTextualApp.

Extracted from textual_app.py to reduce class size and improve
maintainability. Each mixin encapsulates a specific concern of the
Textual TUI application.
"""

from __future__ import annotations

import asyncio
import json
import logging
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual import on, work
from textual.widgets import (
    OptionList,
    RichLog,
    TabbedContent,
    TextArea,
    Tree,
)

from henchman.cli.textual_bridge import EventBridge
from henchman.cli.textual_config import (
    ComponentConfig,
    ComponentInitializer,
    TextualConfig,
)
from henchman.cli.textual_widgets import (
    ChatMessage,
    ChatPane,
    StatusBar,
    ThinkingMessage,
    ThinkingPane,
    ToolMessage,
    ToolPane,
    _safe_markup,
)
from henchman.providers.base import ModelProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

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
    from henchman.providers.base import (
        Message,
        StreamChunk,
        ToolDeclaration,
    )
    from henchman.tools.base import ConfirmationRequest

__all__ = [
    "_CommandPaletteMixin",
    "_ContextTreeMixin",
    "_HistoryMixin",
    "_InitMixin",
    "_InputHandlerMixin",
    "_MessageHandlerMixin",
    "_NullProvider",
    "_PaneActionMixin",
    "_ProviderMixin",
    "_ProxyMixin",
    "_PublicAPIMixin",
    "_SearchMixin",
    "_StatusBarMixin",
    "_extract_line_text",
]

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Constants                                                            #
# ------------------------------------------------------------------ #

_CONTEXT_FILE_PREVIEW_LIMIT: int = 5000
_TOOL_RESULT_TRUNCATE_LIMIT: int = 100
_FILE_SIZE_DIVISOR: int = 1024
_NO_PROVIDER_MSG: str = (
    "No model provider available. "
    "Please configure a provider via environment variables or settings."
)
_PANE_MAP: dict[str, tuple[str, type]] = {
    "thinking": ("#thinking-pane", ThinkingPane),
    "tool": ("#tool-pane", ToolPane),
}


# ------------------------------------------------------------------ #
# NullProvider (fallback when no real provider is configured)          #
# ------------------------------------------------------------------ #


class _NullProvider(ModelProvider):
    """A null provider that raises informative errors when used."""

    def __init__(self) -> None:
        """Initialize the null provider with empty defaults."""
        self._name = "null"
        self.supports_tools = False
        self.supports_streaming = False
        self.max_tokens = 0

    @property
    def name(self) -> str:
        """The unique name of this provider."""
        return self._name

    async def chat_completion(
        self,
        messages: list[Any],  # noqa: ARG002
        tools: list[Any] | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> Any:
        """Raise an error indicating no provider is configured."""
        raise RuntimeError(_NO_PROVIDER_MSG)

    async def chat_completion_stream(
        self,
        messages: list[Message],  # noqa: ARG002
        tools: list[ToolDeclaration] | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> AsyncIterator[StreamChunk]:
        """Raise an error indicating no provider is configured."""
        raise RuntimeError(_NO_PROVIDER_MSG)
        yield  # type: ignore[misc]  # pragma: no cover — makes it a generator

    def count_tokens(self, _text: str) -> int:
        """Return zero tokens for the null provider."""
        return 0


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
# Mixin: proxy properties                                             #
# ------------------------------------------------------------------ #


class _ProxyMixin:
    """Proxy properties for CommandContext compatibility."""

    def _get_context_attr(self, name: str) -> Any:
        """Get an attribute from ``core_context``.

        Args:
            name: Attribute name on core_context.

        Returns:
            The attribute value or ``None``.
        """
        ctx = getattr(self, "core_context", None)
        return getattr(ctx, name, None) if ctx else None

    @property
    def orchestrator(self) -> Any:
        """Proxy to ``core_context.orchestrator``."""
        return self._get_context_attr("orchestrator")

    @orchestrator.setter
    def orchestrator(self, _value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def tool_registry(self) -> Any:
        """Proxy to ``core_context.tool_registry``."""
        return self._get_context_attr("tool_registry")

    @tool_registry.setter
    def tool_registry(self, _value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def session_manager(self) -> Any:
        """Proxy to ``core_context.session_manager``."""
        return self._get_context_attr("session_manager")

    @session_manager.setter
    def session_manager(self, _value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def agent(self) -> Any:
        """Proxy to ``core_context.agent``."""
        return self._get_context_attr("agent")

    @agent.setter
    def agent(self, _value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def rag_system(self) -> None:
        """RAG system (not yet implemented)."""
        return None

    @property
    def renderer(self) -> Any:
        """UIRenderer instance (backward compatibility)."""
        return getattr(self, "_ui_renderer", None)

    @property
    def current_input(self) -> str:
        """Current text in the input widget."""
        try:
            return self.query_one("#input", TextArea).text  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return ""


# ------------------------------------------------------------------ #
# Mixin: initialization                                               #
# ------------------------------------------------------------------ #


class _InitMixin:
    """Lifecycle and component initialization helpers."""

    def _init_provider_and_settings(
        self,
        provider: ModelProvider | None,
        config: TextualConfig | None,
        settings: Any | None,
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
            self.provider = provider  # type: ignore[attr-defined]
            self.config = config or TextualConfig()  # type: ignore[attr-defined]
            self.settings = settings  # type: ignore[attr-defined]
            self.environment_context = env_ctx  # type: ignore[attr-defined]
            return
        self._resolve_provider_from_env()  # type: ignore[attr-defined]

    def _init_state(self) -> None:
        """Initialize mutable UI state fields."""
        from henchman.cli.core_init import CoreContext  # noqa: PLC0415, TC001

        self.core_context: CoreContext | None = None
        self.tool_executor: Any = None
        self.command_processor: Any = None
        self.input_handler: Any = None
        self.output_handler: Any = None
        self._tui_adapter: Any = None

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

    def _initialize_core_components(self) -> None:
        """Wire up core Henchman components.

        References symbols through ``henchman.cli.textual_app`` so that
        test-suite patches (``@patch("henchman.cli.textual_app.X")``)
        are picked up at runtime.
        """
        import henchman.cli.textual_app as _app  # noqa: PLC0415

        component_config = ComponentConfig(
            provider=self.provider,  # type: ignore[attr-defined]
            config=self.config,  # type: ignore[attr-defined]
            settings=self.settings,  # type: ignore[attr-defined]
            environment_context=self.environment_context,  # type: ignore[attr-defined]
            app=self,  # type: ignore[arg-type]
        )
        initializer = ComponentInitializer(
            component_config,
            class_overrides={
                "create_core_context": _app.create_core_context,
                "UIRenderer": _app.UIRenderer,
                "OutputHandler": _app.OutputHandler,
                "ToolExecutor": _app.ToolExecutor,
                "CommandProcessor": _app.CommandProcessor,
                "InputHandler": _app.InputHandler,
            },
        )
        initializer.initialize_all()
        self._transfer_components(initializer)
        self._initialize_mcp()
        self._install_confirmation_handler()
        self._update_status_bar()  # type: ignore[attr-defined]

    def _initialize_mcp(self) -> None:
        """Initialize MCP if a manager is available.

        Uses the module-level ``initialize_mcp`` so tests can patch
        ``henchman.cli.textual_app.initialize_mcp``.
        """
        import henchman.cli.textual_app as _app  # noqa: PLC0415

        ctx = self.core_context  # type: ignore[attr-defined]
        if ctx and ctx.mcp_manager:
            _app.initialize_mcp(ctx)

    def _transfer_components(self, init: ComponentInitializer) -> None:
        """Copy initialized components from initializer.

        Args:
            init: Completed ComponentInitializer.
        """
        self.core_context = init.core_context  # type: ignore[attr-defined]
        self.tool_executor = init.tool_executor  # type: ignore[attr-defined]
        self.command_processor = init.command_processor  # type: ignore[attr-defined]
        self.input_handler = init.input_handler  # type: ignore[attr-defined]
        self.output_handler = init.output_handler  # type: ignore[attr-defined]
        self._tui_adapter = getattr(init, "_tui_adapter", None)  # type: ignore[attr-defined]
        self._ui_renderer = getattr(init, "_ui_renderer", None)  # type: ignore[attr-defined]

    def _install_confirmation_handler(self) -> None:
        """Replace the tool-confirmation handler with a TUI modal."""
        ctx = self.core_context  # type: ignore[attr-defined]
        if ctx:
            ctx.tool_manager.set_confirmation_handler(self._textual_confirm)

    async def _textual_confirm(self, request: ConfirmationRequest) -> bool:
        """Show a modal confirmation dialog.

        Args:
            request: The tool confirmation request.

        Returns:
            ``True`` if approved, ``False`` otherwise.
        """
        from henchman.cli.textual_screens import ConfirmToolScreen  # noqa: PLC0415

        loop = asyncio.get_running_loop()
        future: asyncio.Future[bool] = loop.create_future()
        req_id = self._confirm_counter  # type: ignore[attr-defined]
        self._confirm_counter += 1  # type: ignore[attr-defined]
        self._confirm_futures[req_id] = future  # type: ignore[attr-defined]

        def _callback(result: bool | None) -> None:  # noqa: FBT001
            if not future.done():
                future.set_result(bool(result))
            self._confirm_futures.pop(req_id, None)  # type: ignore[attr-defined]

        try:
            await self.push_screen(ConfirmToolScreen(request), _callback)  # type: ignore[attr-defined]
            return await future
        except asyncio.CancelledError:
            self._confirm_futures.pop(req_id, None)  # type: ignore[attr-defined]
            if not future.done():
                future.cancel()
            raise
        except Exception:
            self._confirm_futures.pop(req_id, None)  # type: ignore[attr-defined]
            if not future.done():
                _msg = "Confirmation dialog failed"
                future.set_exception(RuntimeError(_msg))
            raise

    def _cleanup_confirm_futures(self) -> None:
        """Clean up all pending confirmation futures."""
        for req_id, future in list(self._confirm_futures.items()):  # type: ignore[attr-defined]
            if not future.done():
                future.cancel()
            self._confirm_futures.pop(req_id, None)  # type: ignore[attr-defined]

    def _activate_chat_tab(self) -> None:
        """Force the Chat tab to be active."""
        try:
            tabs = self.query_one(TabbedContent)  # type: ignore[attr-defined]
            tabs.active = "tab-chat"
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------ #
# Mixin: provider resolution & switching                              #
# ------------------------------------------------------------------ #


class _ProviderMixin:
    """Provider resolution and runtime switching."""

    def _resolve_provider_from_env(self) -> None:
        """Auto-detect provider from environment."""
        self.provider = self._load_provider_safe()  # type: ignore[attr-defined]
        self.settings = self._load_settings_safe()  # type: ignore[attr-defined]
        self.config = self._create_config_safe()  # type: ignore[attr-defined]
        self.environment_context = self._gather_env_safe()  # type: ignore[attr-defined]

    def _load_provider_safe(self) -> ModelProvider:
        """Load provider with fallback to ``_NullProvider``.

        Returns:
            A configured provider or a null fallback.
        """
        from henchman.cli.app import _get_provider  # noqa: PLC0415

        try:
            return _get_provider()
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Failed to initialize provider: {exc}. Using null provider.",
                RuntimeWarning,
                stacklevel=2,
            )
            return _NullProvider()

    @staticmethod
    def _load_settings_safe() -> Any:
        """Load settings with fallback to defaults.

        Returns:
            Loaded or default settings.
        """
        from henchman.config import load_settings  # noqa: PLC0415
        from henchman.config.schema import Settings  # noqa: PLC0415

        try:
            return load_settings()
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Failed to load settings: {exc}. Using defaults.",
                RuntimeWarning,
                stacklevel=2,
            )
            return Settings()

    @staticmethod
    def _create_config_safe() -> TextualConfig:
        """Create TUI config with fallback to defaults.

        Returns:
            TextualConfig instance.
        """
        try:
            return TextualConfig()
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Failed to create config: {exc}. Using defaults.",
                RuntimeWarning,
                stacklevel=2,
            )
            return TextualConfig()

    @staticmethod
    def _gather_env_safe() -> str:
        """Gather environment context with fallback.

        Returns:
            Formatted environment block string.
        """
        from henchman.config.environment import (  # noqa: PLC0415
            format_environment_block,
            gather_environment,
        )

        try:
            return format_environment_block(gather_environment())
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Failed to gather environment: {exc}.",
                RuntimeWarning,
                stacklevel=2,
            )
            return "Environment context unavailable"

    def _switch_provider(self, provider_name: str) -> None:
        """Reinitialize with a different provider.

        Args:
            provider_name: Provider name key.
        """
        from henchman.providers import get_default_registry  # noqa: PLC0415

        old_provider = self.provider  # type: ignore[attr-defined]
        old_name = old_provider.name if old_provider else "unknown"

        try:
            registry = get_default_registry()
            new = registry.create(provider_name)
            self.provider = new  # type: ignore[attr-defined]
            try:
                self._initialize_core_components()  # type: ignore[attr-defined]
            except Exception:
                self.provider = old_provider  # type: ignore[attr-defined]
                raise
            self._announce_provider_switch(old_name, provider_name)
        except Exception as exc:  # noqa: BLE001
            if self.provider != old_provider:  # type: ignore[attr-defined]
                self.provider = old_provider  # type: ignore[attr-defined]
            self._show_provider_error(exc)

    def _announce_provider_switch(
        self,
        old_name: str,
        new_name: str,
    ) -> None:
        """Update UI after a successful provider switch.

        Args:
            old_name: Previous provider name.
            new_name: New provider name.
        """
        from henchman import __version__  # noqa: PLC0415

        self.sub_title = (  # type: ignore[attr-defined]
            f"Henchman-AI v{__version__} - {self.provider.name}"  # type: ignore[attr-defined]
        )
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
            chat.add_system_message(
                f"Provider switched: [cyan]{old_name}[/] -> [cyan]{new_name}[/]",
            )
        except Exception:  # noqa: BLE001
            pass
        self._update_status_bar()  # type: ignore[attr-defined]

    def _show_provider_error(self, exc: Exception) -> None:
        """Show a provider-switch error in the chat pane.

        Args:
            exc: The exception that occurred.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
            chat.add_error_message(f"Failed to switch provider: {exc}")
        except Exception:
            logger.exception("Failed to switch provider: %s", exc)


# ------------------------------------------------------------------ #
# Mixin: status bar                                                    #
# ------------------------------------------------------------------ #


class _StatusBarMixin:
    """Status bar text assembly."""

    def _update_status_bar(self) -> None:
        """Refresh the status bar with current info."""
        try:
            bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return
        bar.status_text = self._build_status_text()

    def _build_status_text(self) -> str:
        """Assemble the status bar text.

        Returns:
            Formatted status string.
        """
        provider = self.provider.name if self.provider else "?"  # type: ignore[attr-defined]
        model = getattr(self.provider, "model", "?")  # type: ignore[attr-defined]
        tools = self._count_tools()
        mcp = self._mcp_status_fragment()
        settings = self.settings  # type: ignore[attr-defined]
        mode = (
            "Plan" if (settings and getattr(settings, "plan_mode", False)) else "Chat"
        )
        return f"{mode} | {provider}:{model} | Tools: {tools}{mcp}"

    def _count_tools(self) -> int:
        """Count registered tools.

        Returns:
            Number of tools.
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        if not ctx or not ctx.tool_registry:
            return 0
        return len(ctx.tool_registry.list_tools())

    def _mcp_status_fragment(self) -> str:
        """Build the MCP portion of the status bar.

        Returns:
            MCP status string (empty if no manager).
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        if not (ctx and ctx.mcp_manager):
            return ""
        clients = ctx.mcp_manager.clients
        connected = sum(1 for c in clients.values() if getattr(c, "_connected", False))
        return f" | MCP {connected}/{len(clients)}"


# ------------------------------------------------------------------ #
# Mixin: command history                                              #
# ------------------------------------------------------------------ #


class _HistoryMixin:
    """Command history loading, persistence, and navigation."""

    def _load_history(self) -> None:
        """Load command history from the history file."""
        handler = self.input_handler  # type: ignore[attr-defined]
        if not handler:
            return
        hf: Path = getattr(
            handler,
            "history_file",
            Path.home() / ".henchman_history",
        )
        if not hf.exists():
            return
        try:
            lines = hf.read_text().splitlines()
            self.command_history = [ln for ln in lines if ln.strip()]  # type: ignore[attr-defined]
            self.history_index = len(self.command_history)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass

    def _persist_history_entry(self, entry: str) -> None:
        """Append an entry to the history file.

        Args:
            entry: History line to persist.
        """
        handler = self.input_handler  # type: ignore[attr-defined]
        if not handler:
            return
        hf: Path = getattr(
            handler,
            "history_file",
            Path.home() / ".henchman_history",
        )
        try:
            with open(hf, "a") as fh:  # noqa: PTH123
                fh.write(entry + "\n")
        except Exception as exc:  # noqa: BLE001
            logging.error(
                f"Failed to persist history entry: {exc}"
            )  # noqa: G004, LOG015, TRY400
            try:
                chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
                chat.add_error_message(
                    f"Failed to save command history: {exc}",
                )
            except Exception as ui_exc:  # noqa: BLE001
                logging.error(
                    f"Failed to show history error in UI: {ui_exc}"
                )  # noqa: G004, LOG015, TRY400

    def _navigate_history(self, direction: int) -> None:
        """Navigate command history.

        Args:
            direction: ``-1`` for older, ``+1`` for newer.
        """
        history = self.command_history  # type: ignore[attr-defined]
        if not history:
            return
        new_idx = self.history_index + direction  # type: ignore[attr-defined]
        widget = self.query_one("#input", TextArea)  # type: ignore[attr-defined]
        if 0 <= new_idx < len(history):
            self.history_index = new_idx  # type: ignore[attr-defined]
            text = history[new_idx]
            widget.load_text(text)
            widget.cursor_location = (0, len(text))
        elif new_idx >= len(history):
            self.history_index = len(history)  # type: ignore[attr-defined]
            widget.load_text("")


# ------------------------------------------------------------------ #
# Mixin: context tree & welcome                                       #
# ------------------------------------------------------------------ #


class _ContextTreeMixin:
    """Context tree population, welcome banner, and theme."""

    def _show_welcome(self) -> None:
        """Display a welcome banner in the chat pane."""
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return
        provider = self.provider.name if self.provider else "unknown"  # type: ignore[attr-defined]
        model = getattr(self.provider, "model", "unknown")  # type: ignore[attr-defined]
        tools = self._count_tools()  # type: ignore[attr-defined]
        mcp = self._welcome_mcp_info()
        cfg = self.config  # type: ignore[attr-defined]
        ctx = " | Context loaded" if cfg.system_prompt else ""
        chat.add_system_message(
            f"[bold]Henchman-AI[/bold] | {provider}:{model} | {tools} tools{mcp}{ctx}",
        )
        chat.add_system_message(
            "Type /help for commands. Press F1 for keybindings.",
        )

    def _welcome_mcp_info(self) -> str:
        """Build MCP info fragment for the welcome banner.

        Returns:
            MCP info string or empty.
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        if not (ctx and ctx.mcp_manager):
            return ""
        total = len(ctx.mcp_manager.clients)
        if total:
            return f" | {total} MCP server(s)"
        return ""

    def _populate_context_tree(self) -> None:
        """Populate the Context tab tree."""
        try:
            tree = self.query_one("#context-tree", Tree)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return
        self._fill_context_tree(tree)

    def _fill_context_tree(  # type: ignore[type-arg]
        self,
        tree: Tree,
    ) -> None:
        """Discover and mount context files.

        Args:
            tree: The Tree widget to populate.
        """
        from henchman.config.context import ContextLoader  # noqa: PLC0415

        try:
            files = ContextLoader().discover_files()
        except Exception as exc:  # noqa: BLE001
            logging.error(
                f"Failed to load context files: {exc}"
            )  # noqa: G004, LOG015, TRY400
            try:
                tree.root.add_leaf(f"Error loading context: {exc}")
            except Exception as ui_exc:  # noqa: BLE001
                logging.error(
                    f"Failed to show error in UI: {ui_exc}"
                )  # noqa: G004, LOG015, TRY400
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

    @work
    async def on_tree_node_selected(
        self,
        event: Tree.NodeSelected[object],
    ) -> None:
        """Show file content when a tree node is clicked.

        Args:
            event: Tree node selection event.
        """
        node = event.node
        path: Path | None = node.data  # type: ignore[assignment]
        if not (path and isinstance(path, Path) and path.is_file()):  # noqa: ASYNC240
            return

        chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        chat.add_system_message(f"[dim]Loading {path.name}...[/]")

        try:
            stat = await asyncio.to_thread(path.stat)
            size_kb = stat.st_size / _FILE_SIZE_DIVISOR
            full = await asyncio.to_thread(path.read_text, "utf-8", "replace")
            content = full[:_CONTEXT_FILE_PREVIEW_LIMIT]
            truncated = len(full) > _CONTEXT_FILE_PREVIEW_LIMIT
            if truncated:
                content += "\n\u2026 (truncated)"
            header = f"[bold]{path.name}[/bold] ({size_kb:.1f} KB)"
            if truncated:
                header += f" - showing first {_CONTEXT_FILE_PREVIEW_LIMIT:,} chars"
            chat.add_system_message(f"{header}\n{content}")
        except Exception as exc:  # noqa: BLE001
            try:
                chat.add_error_message(f"Cannot read {path}: {exc}")
            except Exception:  # noqa: BLE001
                logging.error(  # noqa: LOG015, TRY400
                    "Cannot read %s and show error: %s",
                    path,
                    exc,
                )

    def _apply_theme(self) -> None:
        """Apply the current theme class to the screen."""
        try:
            for name in ("theme-dark", "theme-light"):
                self.screen.remove_class(name)  # type: ignore[attr-defined]
            self.screen.add_class(  # type: ignore[attr-defined]
                f"theme-{self._theme_name}",  # type: ignore[attr-defined]
            )
        except Exception:  # noqa: BLE001
            pass

    def action_toggle_theme(self) -> None:
        """Toggle between dark and light themes."""
        current = self._theme_name  # type: ignore[attr-defined]
        self._theme_name = "light" if current == "dark" else "dark"  # type: ignore[attr-defined]
        self._apply_theme()
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
            chat.add_system_message(
                f"Theme switched to [cyan]{self._theme_name}[/]",  # type: ignore[attr-defined]
            )
        except Exception:  # noqa: BLE001
            pass
        self.dark = self._theme_name == "dark"  # type: ignore[attr-defined]


# ------------------------------------------------------------------ #
# Mixin: input handling                                               #
# ------------------------------------------------------------------ #


class _InputHandlerMixin:
    """User input submission and routing."""

    def action_submit_message(self) -> None:
        """Extract text from the input widget and process it."""
        if self.is_processing:  # type: ignore[attr-defined]
            return
        input_widget = self.query_one("#input", TextArea)  # type: ignore[attr-defined]
        user_input = input_widget.text.strip()
        if not user_input:
            return
        self.command_history.append(user_input)  # type: ignore[attr-defined]
        self.history_index = len(self.command_history)  # type: ignore[attr-defined]
        self._persist_history_entry(user_input)  # type: ignore[attr-defined]
        input_widget.load_text("")
        self.process_user_input(user_input)

    @work(exclusive=True)
    async def process_user_input(self, user_input: str) -> None:
        """Process user input: commands or agent chat.

        Args:
            user_input: Raw text the user submitted.
        """
        self.is_processing = True  # type: ignore[attr-defined]
        self.current_agent_task = asyncio.current_task()  # type: ignore[attr-defined]
        bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        bar.status_text = "Processing..."
        chat.add_user_message(user_input)

        try:
            await self._route_input(user_input, chat)
        except asyncio.CancelledError:
            chat.add_system_message("[yellow]\u26a0 Cancelled by user (Esc)[/]")
        except Exception as exc:  # noqa: BLE001
            import traceback  # noqa: PLC0415

            details = traceback.format_exc()
            safe_details = details.replace("```", "` ` `")
            chat.add_error_message(
                f"{exc}\n```\n{safe_details}\n```",
            )
            bar.status_text = f"Error: {exc}"
        finally:
            self.is_processing = False  # type: ignore[attr-defined]
            if hasattr(self, "current_agent_task"):
                del self.current_agent_task
            self._update_status_bar()  # type: ignore[attr-defined]

    async def _route_input(self, user_input: str, chat: ChatPane) -> None:
        """Route processed input to command or orchestrator.

        Args:
            user_input: Raw user text.
            chat: The ChatPane widget.
        """
        handler = self.input_handler  # type: ignore[attr-defined]
        if not handler:
            chat.add_error_message("Input handler not initialized.")
            return
        processed, is_cmd, should_continue = await handler.process_input(
            user_input,
        )
        if not should_continue or not processed:
            return

        import henchman.cli.textual_app as _app  # noqa: PLC0415

        expanded = await _app.expand_at_references(processed)
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
        ctx = self.core_context  # type: ignore[attr-defined]
        if ctx and ctx.session_manager:
            ctx.session_manager.record_user_message(text)

    async def _handle_command(self, text: str, chat: ChatPane) -> None:
        """Process a slash command.

        Args:
            text: Expanded command text.
            chat: The ChatPane widget.
        """
        if text.strip().lower() == "/clear":
            chat.clear_messages()
            return
        processor = self.command_processor  # type: ignore[attr-defined]
        if not processor:
            return
        ctx = self.core_context  # type: ignore[attr-defined]
        should_continue = await processor.handle_command(
            text,
            (ctx.agent if ctx else None),  # type: ignore[arg-type]
            self,  # type: ignore[arg-type]
        )
        adapter = self._tui_adapter  # type: ignore[attr-defined]
        if adapter:
            adapter.flush_to_chat()
        if not should_continue:
            self.exit()  # type: ignore[attr-defined]

    async def _run_orchestrator(self, text: str, chat: ChatPane) -> None:
        """Send text through the orchestrator.

        Args:
            text: Expanded user text.
            chat: The ChatPane widget.
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        if not (ctx and ctx.orchestrator):
            chat.add_error_message("Core components not initialized.")
            return
        import henchman.cli.textual_app as _app  # noqa: PLC0415

        bridge = _app.EventBridge(self)  # type: ignore[arg-type]

        cfg = self.config  # type: ignore[attr-defined]
        if cfg.agent_role:
            stream = ctx.orchestrator.run_direct(cfg.agent_role, text)
        else:
            stream = ctx.orchestrator.run(text)

        await bridge.forward_events(stream)


# ------------------------------------------------------------------ #
# Mixin: command palette                                              #
# ------------------------------------------------------------------ #


class _CommandPaletteMixin:
    """Command palette show/hide and selection."""

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
        palette = self.query_one(  # type: ignore[attr-defined]
            "#command-palette",
            OptionList,
        )
        palette.display = True
        palette.clear_options()
        query = current_text.lower()
        processor = self.command_processor  # type: ignore[attr-defined]
        commands = processor.command_registry.get_commands() if processor else []
        for cmd in commands:
            label = f"/{cmd.name}  -- {cmd.description}"
            if f"/{cmd.name}".startswith(query) or query == "/":
                palette.add_option(label)
        if palette.option_count == 0:
            palette.display = False

    def _hide_command_palette(self) -> None:
        """Hide the command palette."""
        palette = self.query_one(  # type: ignore[attr-defined]
            "#command-palette",
            OptionList,
        )
        palette.display = False

    @on(OptionList.OptionSelected, "#command-palette")
    def on_command_selected(
        self,
        event: OptionList.OptionSelected,
    ) -> None:
        """Fill the input with the selected command.

        Args:
            event: Option selection event.
        """
        raw = str(event.option.prompt)
        cmd_part = raw.split("  --", maxsplit=1)[0].strip()
        widget = self.query_one("#input", TextArea)  # type: ignore[attr-defined]
        new_text = cmd_part + " "
        widget.load_text(new_text)
        widget.cursor_location = (0, len(new_text))
        widget.focus()
        self._hide_command_palette()

    def action_show_help(self) -> None:
        """Show the help/keybinding modal."""
        import henchman.cli.textual_app as _app  # noqa: PLC0415

        self.push_screen(_app.HelpScreen())  # type: ignore[attr-defined]

    def action_switch_provider(self) -> None:
        """Show the provider switching modal."""
        import henchman.cli.textual_app as _app  # noqa: PLC0415

        self.push_screen(_app.ProviderScreen())  # type: ignore[attr-defined]


# ------------------------------------------------------------------ #
# Mixin: message handlers                                             #
# ------------------------------------------------------------------ #


class _MessageHandlerMixin:
    """Textual message handlers for agent events."""

    def on_agent_content_message(
        self,
        message: AgentContentMessage,
    ) -> None:
        """Stream text content into the chat pane.

        Args:
            message: Content chunk from an agent.
        """
        chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        name = message.source_agent or "Assistant"
        chat.append_agent_chunk(name, message.content)

    def on_agent_thought_message(
        self,
        message: AgentThoughtMessage,
    ) -> None:
        """Add thinking content to chat pane and thinking pane.

        Args:
            message: Thought from an agent.
        """
        pane = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        agent_name = message.source_agent or ""
        pane.append_thinking_chunk(agent_name, message.thought)

        try:
            thinking = self.query_one(  # type: ignore[attr-defined]
                "#thinking-pane",
                ThinkingPane,
            )
            label = message.source_agent or "Agent"
            thinking.write(
                f"[dim]\U0001f914 {_safe_markup(label)}: "
                f"{_safe_markup(message.thought)}[/]",
            )
            thinking.scroll_end(animate=False)
        except Exception:  # noqa: BLE001
            pass

    def on_tool_call_request_message(
        self,
        message: ToolCallRequestMessage,
    ) -> None:
        """Add a tool call request to both chat and tool panes.

        Args:
            message: Tool call request data.
        """
        tc = message.tool_call
        args_str = self._format_tool_args(tc)
        tool_description = f"{tc.name}: {args_str}" if args_str else tc.name

        pane = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        pane.add_tool_message(tool_description, tc)

        try:
            tool_pane = self.query_one(  # type: ignore[attr-defined]
                "#tool-pane",
                ToolPane,
            )
            full_args = self._format_full_tool_args(tc)
            tool_pane.write(
                f"[yellow]\u25b6 {_safe_markup(tc.name)}[/]\n"
                f"[dim]{_safe_markup(full_args)}[/]",
            )
            tool_pane.scroll_end(animate=False)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _format_tool_args(tool_call: Any) -> str:
        """Format tool call arguments for compact display.

        Args:
            tool_call: Tool call with an arguments attr.

        Returns:
            Formatted arguments string.
        """
        if not tool_call.arguments:
            return ""
        try:
            raw = tool_call.arguments
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            return json.dumps(parsed, separators=(",", ":"))
        except Exception:  # noqa: BLE001
            return str(tool_call.arguments)

    @staticmethod
    def _format_full_tool_args(tool_call: Any) -> str:
        """Format tool call arguments for the tool pane (pretty).

        Args:
            tool_call: Tool call with an arguments attr.

        Returns:
            Pretty-printed arguments or empty string.
        """
        if not tool_call.arguments:
            return ""
        try:
            raw = tool_call.arguments
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            return json.dumps(parsed, indent=2)
        except Exception:  # noqa: BLE001
            return str(tool_call.arguments)

    def on_tool_call_result_message(
        self,
        message: ToolCallResultMessage,
    ) -> None:
        """Add a tool result to both chat and tool panes.

        Args:
            message: Tool execution result.
        """
        result_str = self._format_tool_result(message.result)

        pane = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        pane.add_tool_message(f"Result: {result_str}")

        try:
            tool_pane = self.query_one(  # type: ignore[attr-defined]
                "#tool-pane",
                ToolPane,
            )
            tool_pane.write(f"[green]\u2190 {_safe_markup(result_str)}[/]")
            tool_pane.scroll_end(animate=False)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _format_tool_result(result: Any) -> str:
        """Format tool result for display in chat.

        Args:
            result: Tool result data (dict or other).

        Returns:
            Formatted result string.
        """
        if isinstance(result, dict):
            content = str(result.get("result", result))
            success = result.get("success", True)
            display = content[:_TOOL_RESULT_TRUNCATE_LIMIT]
            if len(content) > _TOOL_RESULT_TRUNCATE_LIMIT:
                display += "\u2026"
            label = "\u2713" if success else "\u2717"
            return f"{label} {display}"
        content = str(result)
        display = content[:_TOOL_RESULT_TRUNCATE_LIMIT]
        if len(content) > _TOOL_RESULT_TRUNCATE_LIMIT:
            display += "\u2026"
        return display

    def on_tool_confirmation_message(
        self,
        message: ToolConfirmationMessage,
    ) -> None:
        """Fallback for TOOL_CONFIRMATION events.

        The ToolManager's handler already shows the modal.

        Args:
            message: Confirmation request message.
        """

    def on_agent_status_message(
        self,
        message: AgentStatusMessage,
    ) -> None:
        """Update the status bar.

        Args:
            message: Status update from an agent.
        """
        try:
            bar = self.query_one(  # type: ignore[attr-defined]
                "#status-bar",
                StatusBar,
            )
            bar.status_text = message.status
        except Exception:  # noqa: BLE001
            pass

    def on_agent_finished_message(
        self,
        message: AgentFinishedMessage,
    ) -> None:
        """Handle agent completion.

        Args:
            message: Finished signal from an agent.
        """
        chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        name = message.source_agent or "Assistant"
        chat.finish_agent_stream(name)
        self._streaming_messages.pop(name, None)  # type: ignore[attr-defined]
        self._update_status_bar()  # type: ignore[attr-defined]

    def on_command_output_message(
        self,
        message: CommandOutputMessage,
    ) -> None:
        """Route command output to the chat pane.

        Args:
            message: Output text from a command.
        """
        try:
            chat = self.query_one(  # type: ignore[attr-defined]
                "#chat-pane",
                ChatPane,
            )
            chat.add_system_message(message.text)
        except Exception:  # noqa: BLE001
            pass

    def on_switch_provider_message(
        self,
        message: SwitchProviderMessage,
    ) -> None:
        """Switch the active provider.

        Args:
            message: Provider switch request.
        """
        self._switch_provider(message.provider_name)  # type: ignore[attr-defined]


# ------------------------------------------------------------------ #
# Mixin: pane actions                                                  #
# ------------------------------------------------------------------ #


class _PaneActionMixin:
    """Pane clearing and tab toggling."""

    def _toggle_tab(self, tab_id: str) -> None:
        """Toggle a tabbed-content tab.

        Args:
            tab_id: CSS id of the tab to toggle.
        """
        try:
            tabs = self.query_one(TabbedContent)  # type: ignore[attr-defined]
            tabs.active = "tab-chat" if tabs.active == tab_id else tab_id
        except Exception:  # noqa: BLE001
            pass

    def action_toggle_thinking_pane(self) -> None:
        """Toggle the thinking tab."""
        self._toggle_tab("tab-thinking")

    def action_toggle_tool_pane(self) -> None:
        """Toggle the tools tab."""
        self._toggle_tab("tab-tools")

    def action_clear_thinking_pane(self) -> None:
        """Clear the thinking pane and chat thinking messages."""
        self.query_one(  # type: ignore[attr-defined]
            "#thinking-pane",
            ThinkingPane,
        ).clear()
        self.query_one(  # type: ignore[attr-defined]
            "#chat-pane",
            ChatPane,
        ).clear_thinking_messages()
        bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        bar.status_text = "Thinking cleared (legacy pane and chat messages)"

    def action_clear_tool_pane(self) -> None:
        """Clear all content from the tool pane."""
        self.query_one(  # type: ignore[attr-defined]
            "#tool-pane",
            ToolPane,
        ).clear()
        bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        bar.status_text = "Tool pane cleared"


# ------------------------------------------------------------------ #
# Mixin: search                                                       #
# ------------------------------------------------------------------ #


class _SearchMixin:
    """Full-text search across chat, thinking, and tool panes."""

    def action_search(self) -> None:
        """Enter search mode or find next match."""
        if self._search_mode:  # type: ignore[attr-defined]
            self.action_search_next()
            return
        self._search_mode = True  # type: ignore[attr-defined]
        bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        bar.status_text = "Search: type in input box then press F3"

    def action_cancel_or_clear(self) -> None:
        """Cancel processing or clear search."""
        if self.is_processing and hasattr(self, "current_agent_task"):  # type: ignore[attr-defined]
            task = self.current_agent_task  # type: ignore[attr-defined]
            if task is not None:
                task.cancel()
            bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
            bar.status_text = "Cancelling..."
            return
        self.action_clear_search()

    def action_clear_search(self) -> None:
        """Exit search mode and reset state."""
        self._clear_highlights()
        self._search_mode = False  # type: ignore[attr-defined]
        self._search_query = ""  # type: ignore[attr-defined]
        self._search_matches = []  # type: ignore[attr-defined]
        self._current_match_index = -1  # type: ignore[attr-defined]
        try:
            bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
            bar.status_text = "Ready"
        except Exception:  # noqa: BLE001
            pass

    def action_search_next(self) -> None:
        """Move to the next search match."""
        if not self._search_mode:  # type: ignore[attr-defined]
            return
        self._refresh_search_if_changed()
        matches = self._search_matches  # type: ignore[attr-defined]
        if not matches:
            return
        self._current_match_index = (  # type: ignore[attr-defined]
            self._current_match_index + 1  # type: ignore[attr-defined]
        ) % len(matches)
        self._scroll_to_match()
        self._update_search_status()

    def action_search_previous(self) -> None:
        """Move to the previous search match."""
        if not self._search_mode:  # type: ignore[attr-defined]
            return
        self._refresh_search_if_changed()
        matches = self._search_matches  # type: ignore[attr-defined]
        if not matches:
            return
        self._current_match_index = (  # type: ignore[attr-defined]
            self._current_match_index - 1  # type: ignore[attr-defined]
        ) % len(matches)
        self._scroll_to_match()
        self._update_search_status()

    def _refresh_search_if_changed(self) -> None:
        """Re-run search if the query text changed."""
        widget = self.query_one("#input", TextArea)  # type: ignore[attr-defined]
        query = widget.text.strip()
        if query != self._search_query:  # type: ignore[attr-defined]
            self._perform_search(query)

    def _perform_search(self, query: str) -> None:
        """Index text matches in chat, thinking, and tool panes.

        Args:
            query: Search string (case-insensitive).
        """
        self._clear_highlights()

        self._search_query = query  # type: ignore[attr-defined]
        self._search_matches = []  # type: ignore[attr-defined]
        self._current_match_index = -1  # type: ignore[attr-defined]
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

        Args:
            query_lower: Lowercase search query.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
            for idx, w in enumerate(chat.children):
                content = ""
                if isinstance(w, (ChatMessage, ThinkingMessage, ToolMessage)):
                    content = w._content  # noqa: SLF001
                if content and query_lower in content.lower():
                    self._search_matches.append(  # type: ignore[attr-defined]
                        ("chat", idx, content),
                    )
        except Exception:  # noqa: BLE001
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
                pane = self.query_one(css_id, pane_cls)  # type: ignore[attr-defined]
                self._search_richlog(pane, pane_id, query_lower)
            except Exception:  # noqa: BLE001, PERF203
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
        lines = getattr(pane, "lines", [])
        if not lines:
            return
        for idx, item in enumerate(lines):
            text = _extract_line_text(item)
            if query_lower in text.lower():
                self._search_matches.append(  # type: ignore[attr-defined]
                    (pane_id, idx, text),
                )

    def _scroll_to_match(self) -> None:
        """Scroll to the current search match."""
        matches = self._search_matches  # type: ignore[attr-defined]
        idx = self._current_match_index  # type: ignore[attr-defined]
        if not matches or idx < 0:
            return
        pane_id, line_idx, _ = matches[idx]
        if pane_id == "chat":
            self._scroll_chat_match(line_idx)
        elif pane_id in _PANE_MAP:
            self._scroll_richlog_match(pane_id)

    def _apply_highlights(self, term: str) -> None:
        """Apply search highlight to matching widgets in the chat pane.

        Args:
            term: Search term to highlight.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
            for w in chat.children:
                if hasattr(w, "set_highlight"):
                    w.set_highlight(term)
        except Exception:  # noqa: BLE001
            pass

    def _clear_highlights(self) -> None:
        """Remove search highlights from all widgets in the chat pane."""
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
            for w in chat.children:
                if hasattr(w, "set_highlight"):
                    w.set_highlight("")
        except Exception:  # noqa: BLE001
            pass

    def _scroll_chat_match(self, line_idx: int) -> None:
        """Scroll a chat pane child into view.

        Args:
            line_idx: Index of the matching child widget.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
            children = list(chat.children)
            if 0 <= line_idx < len(children):
                children[line_idx].scroll_visible(animate=False)
        except Exception:  # noqa: BLE001
            pass

    def _scroll_richlog_match(self, pane_id: str) -> None:
        """Scroll a RichLog pane to end for visibility.

        Args:
            pane_id: ``'thinking'`` or ``'tool'``.
        """
        if pane_id not in _PANE_MAP:
            return
        css_id, cls = _PANE_MAP[pane_id]
        try:
            pane: ThinkingPane | ToolPane = self.query_one(  # type: ignore[attr-defined]
                css_id,
                cls,
            )
            pane.scroll_end(animate=False)
        except Exception:  # noqa: BLE001
            pass

    def _update_search_status(self) -> None:
        """Refresh the status bar with search info."""
        try:
            bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return
        if not self._search_mode:  # type: ignore[attr-defined]
            return
        query = self._search_query  # type: ignore[attr-defined]
        matches = self._search_matches  # type: ignore[attr-defined]
        if not query:
            bar.status_text = "Search: type query in input box, F3=next"
        elif not matches:
            bar.status_text = f"No matches for '{query}'"
        else:
            cur = self._current_match_index + 1  # type: ignore[attr-defined]
            tot = len(matches)
            bar.status_text = (
                f"Match {cur}/{tot} for '{query}'"
                " - F3=next  Shift+F3=prev  Esc=clear"
            )


# ------------------------------------------------------------------ #
# Mixin: public API helpers                                            #
# ------------------------------------------------------------------ #


class _PublicAPIMixin:
    """Public helper methods for external callers."""

    def set_session(self, session: Any) -> None:
        """Activate a loaded session.

        Args:
            session: Session to activate.
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        if not (ctx and ctx.session_manager):
            return
        ctx.session_manager.set_session(
            session,
            (ctx.orchestrator if ctx else None),
        )

    def update_status(
        self,
        message: str,
        *,
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
            bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
            bar.status_text = message
            if tokens is not None:
                bar.tokens = tokens
            if cost is not None:
                bar.cost = cost
        except Exception:  # noqa: BLE001
            pass

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat pane.

        Args:
            role: Sender role ('user', 'assistant', 'system').
            content: Message content.
        """
        try:
            chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            return
        if role == "user":
            chat.add_user_message(content)
        elif role in ("assistant", "system"):
            chat.add_system_message(content)
        else:
            chat.add_system_message(f"[{role}] {content}")
