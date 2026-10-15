"""Mixin classes for HenchmanTextualApp.

Extracted from textual_app.py to reduce class size and improve
maintainability. Each mixin encapsulates a specific concern of the
Textual TUI application.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import json
import logging
import traceback
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import yaml
from textual import on, work
from textual.widgets import (
    Button,
    OptionList,
    RichLog,
    TabbedContent,
    TextArea,
    Tree,
)

from henchman.advanced import TaskService
from henchman.cli.output_handler import resolve_active_agent
from henchman.cli.textual_config import (
    ComponentConfig,
    ComponentInitializer,
    TextualConfig,
)
from henchman.cli.textual_questions import ToolPromptChannel
from henchman.cli.textual_widgets import (
    AgentSummaryPanel,
    ChatMessage,
    ChatPane,
    MemoryIndicator,
    SettingsPanel,
    SkillPanel,
    StatusBar,
    TaskListWidget,
    TeamPanel,
    ThinkingMessage,
    ThinkingPane,
    ToolMessage,
    ToolPane,
    _safe_markup,
)
from henchman.core.goals import GoalService, save_goal_session
from henchman.core.session_export import export_as_markdown
from henchman.providers.base import ModelProvider, StreamChunk
from henchman.skills import SkillCatalog
from henchman.team import BridgeSessionService, TeamWorkspaceService

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Generator

    from textual.app import App

    from henchman.cli.core_init import CoreContext
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
    from henchman.core.events import AgentEvent
    from henchman.providers.base import (
        Message,
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


def _active_display_agent(runtime: Any) -> Any:
    """Resolve the same direct role or leader used for interactive execution."""
    agent = resolve_active_agent(runtime)
    provider = getattr(agent, "provider", None)
    return agent if isinstance(getattr(provider, "name", None), str) else None


def _active_display_provider(runtime: Any) -> Any:
    """Use the acting provider, retaining the startup fallback before core setup."""
    agent = _active_display_agent(runtime)
    return agent.provider if agent is not None else getattr(runtime, "provider", None)


def _display_model(provider: Any, fallback: str = "unknown") -> str:
    """Read compatible-provider models and legacy provider model attributes."""
    for attribute in ("default_model", "model"):
        model = getattr(provider, attribute, None)
        if isinstance(model, str) and model:
            return model
    return fallback


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
_WORKSPACE_DATA_ERRORS = (OSError, KeyError, ValueError, yaml.YAMLError)


# ------------------------------------------------------------------ #
# NullProvider (fallback when no real provider is configured)          #
# ------------------------------------------------------------------ #


class _NullStream:
    """Awaitable async iterator that reports a missing provider on iteration."""

    def __await__(self) -> Generator[Any, None, _NullStream]:
        async def _return_self() -> _NullStream:
            return self

        return _return_self().__await__()

    def __aiter__(self) -> _NullStream:
        return self

    async def __anext__(self) -> StreamChunk:
        raise RuntimeError(_NO_PROVIDER_MSG)


class _NullProvider(ModelProvider):
    """A null provider that raises informative errors when used."""

    def __init__(self: _NullProvider) -> None:
        """Initialize the null provider with empty defaults."""
        self._name = "null"
        self.supports_tools = False
        self.supports_streaming = False
        self.max_tokens = 0

    @property
    def name(self: _NullProvider) -> str:
        """The unique name of this provider."""
        return self._name

    async def chat_completion(
        self: _NullProvider,
        _messages: list[Any],
        _tools: list[Any] | None = None,
        **_kwargs: Any,
    ) -> Any:
        """Raise an error indicating no provider is configured."""
        raise RuntimeError(_NO_PROVIDER_MSG)

    def chat_completion_stream(
        self: _NullProvider,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> _NullStream:
        """Raise an error indicating no provider is configured."""
        del messages, tools, kwargs
        return _NullStream()

    def count_tokens(self: _NullProvider, _text: str) -> int:
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
        return "".join(str(seg.text) if hasattr(seg, "text") else str(seg) for seg in item)
    except (TypeError, AttributeError):
        return str(item)


def _import_module(module_name: str) -> Any:
    """Import a module at runtime.

    Args:
        module_name: Fully-qualified module name.

    Returns:
        The imported module.
    """
    return importlib.import_module(module_name)


def _query_one_or_none(
    app: Any,
    selector: str | type[Any],
    widget_type: type[Any] | None = None,
) -> Any | None:
    """Return a queried widget or ``None`` when it is unavailable.

    Args:
        app: Textual app or widget exposing ``query_one``.
        selector: CSS selector or widget type for ``query_one``.
        widget_type: Optional expected widget type.

    Returns:
        The queried widget, or ``None`` if Textual cannot resolve it.
    """
    try:
        if widget_type is None:
            return app.query_one(selector)
        return app.query_one(selector, widget_type)
    except Exception:  # noqa: BLE001
        return None


def _get_searchable_content(widget: Any) -> str:
    """Extract searchable text content from a chat widget.

    Args:
        widget: Widget that may expose search content.

    Returns:
        Searchable plain text.
    """
    content = getattr(widget, "_content", "")
    return str(content) if content else ""


async def _read_context_file_content(path: Path) -> str:
    """Read a context file and return formatted display content.

    Args:
        path: Path to the file to read.

    Returns:
        Formatted string with header and (possibly truncated) content.
    """
    try:
        stat = await asyncio.to_thread(path.stat)
        size_kb = stat.st_size / _FILE_SIZE_DIVISOR
    except OSError as exc:
        return f"[bold]{path.name}[/bold] - Error getting file info: {exc}"

    try:
        full = await asyncio.to_thread(path.read_text, "utf-8", "replace")
    except (OSError, UnicodeDecodeError) as exc:
        return f"[bold]{path.name}[/bold] ({size_kb:.1f} KB) - Error reading file: {exc}"

    content = full[:_CONTEXT_FILE_PREVIEW_LIMIT]
    truncated = len(full) > _CONTEXT_FILE_PREVIEW_LIMIT
    if truncated:
        content += "\n\u2026 (truncated)"
    header = f"[bold]{path.name}[/bold] ({size_kb:.1f} KB)"
    if truncated:
        header += f" - showing first {_CONTEXT_FILE_PREVIEW_LIMIT:,} chars"
    return f"{header}\n{content}"


def _fill_context_tree(tree: Tree) -> None:  # type: ignore[type-arg]
    """Discover and mount context files into a Tree widget.

    Args:
        tree: The Tree widget to populate.
    """
    try:
        context_loader = _import_module("henchman.config.context").ContextLoader()
        files = context_loader.discover_files()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load context files: %s", exc)  # noqa: TRY400
        with contextlib.suppress(Exception):
            tree.root.add_leaf(f"Error loading context: {exc}")
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


# ------------------------------------------------------------------ #
# Mixin: proxy properties                                             #
# ------------------------------------------------------------------ #


class _ProxyMixin:
    """Proxy properties for CommandContext compatibility."""

    def _get_context_attr(self: _ProxyMixin, name: str) -> Any:
        """Get an attribute from ``core_context``.

        Args:
            name: Attribute name on core_context.

        Returns:
            The attribute value or ``None``.
        """
        ctx = getattr(self, "core_context", None)
        return getattr(ctx, name, None) if ctx else None

    @property
    def orchestrator(self: _ProxyMixin) -> Any:
        """Proxy to ``core_context.orchestrator``."""
        return self._get_context_attr("orchestrator")

    @orchestrator.setter
    def orchestrator(self: _ProxyMixin, _value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def tool_registry(self: _ProxyMixin) -> Any:
        """Proxy to ``core_context.tool_registry``."""
        return self._get_context_attr("tool_registry")

    @tool_registry.setter
    def tool_registry(self: _ProxyMixin, _value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def session_manager(self: _ProxyMixin) -> Any:
        """Proxy to ``core_context.session_manager``."""
        return self._get_context_attr("session_manager")

    @session_manager.setter
    def session_manager(self: _ProxyMixin, _value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def agent(self: _ProxyMixin) -> Any:
        """Proxy to ``core_context.agent``."""
        return self._get_context_attr("agent")

    @agent.setter
    def agent(self: _ProxyMixin, _value: Any) -> None:
        """No-op setter; managed by core_context."""

    @property
    def rag_system(self: _ProxyMixin) -> None:
        """RAG system (not yet implemented)."""
        return None

    @property
    def renderer(self: _ProxyMixin) -> Any:
        """UIRenderer instance (backward compatibility)."""
        return getattr(self, "_ui_renderer", None)

    @property
    def current_input(self: _ProxyMixin) -> str:
        """Current text in the input widget."""
        widget = _query_one_or_none(self, "#input", TextArea)
        return widget.text if widget is not None else ""


# ------------------------------------------------------------------ #
# Mixin: initialization                                               #
# ------------------------------------------------------------------ #


class _InitMixin:
    """Lifecycle and component initialization helpers."""

    environment_context: str | None

    def _init_provider_and_settings(
        self: _InitMixin,
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
            self.provider = provider
            self.config = config or TextualConfig()
            self.settings = settings
            self.environment_context = env_ctx
            return
        self._resolve_provider_from_env()  # type: ignore[attr-defined]

    def _init_state(self: _InitMixin) -> None:
        """Initialize mutable UI state fields."""
        self.core_context: CoreContext | None = None
        self.tool_executor: Any = None
        self.command_processor: Any = None
        self.input_handler: Any = None
        self.output_handler: Any = None
        self._tui_adapter: Any = None
        self.is_processing: bool = False
        self._init_search_state()
        self._init_history_state()
        self._init_confirm_state()
        self._init_proxy_stubs()

    def _init_search_state(self: _InitMixin) -> None:
        """Initialize search-related state variables."""
        self._search_mode: bool = False
        self._search_query: str = ""
        self._search_matches: list[tuple[str, int, str]] = []
        self._current_match_index: int = -1

    def _init_history_state(self: _InitMixin) -> None:
        """Initialize command history state variables."""
        self.command_history: list[str] = []
        self.history_index: int = -1

    def _init_confirm_state(self: _InitMixin) -> None:
        """Initialize the shared question and tool-approval channel."""
        self._tool_prompts = ToolPromptChannel(cast("App[Any]", self))

    def _init_proxy_stubs(self: _InitMixin) -> None:
        """Initialize proxy compatibility stub attributes."""
        self._orchestrator_proxy: Any = None
        self._tool_registry_proxy: Any = None
        self._session_manager_proxy: Any = None

    def _initialize_core_components(self: _InitMixin) -> None:
        """Wire up core Henchman components.

        References symbols through ``henchman.cli.textual_app`` so that
        test-suite patches (``@patch("henchman.cli.textual_app.X")``)
        are picked up at runtime.
        """
        app_module = _import_module("henchman.cli.textual_app")
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
                "create_core_context": app_module.create_core_context,
                "UIRenderer": app_module.UIRenderer,
                "OutputHandler": app_module.OutputHandler,
                "ToolExecutor": app_module.ToolExecutor,
                "CommandProcessor": app_module.CommandProcessor,
                "InputHandler": app_module.InputHandler,
            },
        )
        initializer.initialize_all()
        self._transfer_components(initializer)
        self._initialize_session()
        self._initialize_mcp()
        self._install_confirmation_handler()
        self._update_status_bar()  # type: ignore[attr-defined]

    def _initialize_session(self: _InitMixin) -> None:
        """Create an active session once, preserving an explicitly resumed one."""
        ctx = self.core_context
        if ctx and ctx.session_manager:
            manager = ctx.session_manager
            manager.auto_save = self.config.auto_save
            if manager.current is None:
                project_hash = manager.compute_project_hash(Path.cwd())
                manager.set_session(manager.create_session(project_hash))

    def _initialize_mcp(self: _InitMixin) -> None:
        """Initialize MCP if a manager is available.

        Uses the module-level ``initialize_mcp`` so tests can patch
        ``henchman.cli.textual_app.initialize_mcp``.
        """
        ctx = self.core_context
        if ctx and ctx.mcp_manager:
            _import_module("henchman.cli.textual_app").initialize_mcp(ctx)

    def _transfer_components(self: _InitMixin, init: ComponentInitializer) -> None:
        """Copy initialized components from initializer.

        Args:
            init: Completed ComponentInitializer.
        """
        self.core_context = init.core_context
        self.tool_executor = init.tool_executor
        self.command_processor = init.command_processor
        self.input_handler = init.input_handler
        self.output_handler = init.output_handler
        self._tui_adapter = getattr(init, "_tui_adapter", None)
        self._ui_renderer = getattr(init, "_ui_renderer", None)

    def _install_confirmation_handler(self: _InitMixin) -> None:
        """Replace the tool-confirmation handler with a TUI modal."""
        ctx = self.core_context
        if ctx:
            ctx.tool_manager.set_confirmation_handler(self._textual_confirm)

    async def _textual_confirm(self: _InitMixin, request: ConfirmationRequest) -> bool:
        """Collect explicit approval through the serialized tool dialog channel."""
        return await self._tool_prompts.confirm(request)

    def _cleanup_confirm_futures(self: _InitMixin) -> None:
        """Cancel pending questions and approvals during shutdown."""
        self._tool_prompts.close()

    def _activate_chat_tab(self: _InitMixin) -> None:
        """Force the Chat tab to be active."""
        tabs = _query_one_or_none(self, TabbedContent)
        if tabs is not None:
            tabs.active = "tab-chat"


# ------------------------------------------------------------------ #
# Mixin: provider resolution & switching                              #
# ------------------------------------------------------------------ #


class _ProviderMixin:
    """Provider resolution and runtime switching."""

    environment_context: str | None

    def _resolve_provider_from_env(self: _ProviderMixin) -> None:
        """Auto-detect provider from environment."""
        self.provider = self._load_provider_safe()
        self.settings = self._load_settings_safe()
        self.config = self._create_config_safe()
        self.environment_context = self._gather_env_safe()

    def _load_provider_safe(self: _ProviderMixin) -> ModelProvider:
        """Load provider with fallback to ``_NullProvider``.

        Returns:
            A configured provider or a null fallback.
        """
        try:
            provider_loader = _import_module("henchman.cli.app")._get_provider  # noqa: SLF001
            return cast(ModelProvider, provider_loader())
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
        try:
            settings_module = _import_module("henchman.config")
            return settings_module.load_settings()
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Failed to load settings: {exc}. Using defaults.",
                RuntimeWarning,
                stacklevel=2,
            )
            return _import_module("henchman.config.schema").Settings()

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
        try:
            environment_module = _import_module("henchman.config.environment")
            environment = environment_module.gather_environment()
            return cast(str, environment_module.format_environment_block(environment))
        except Exception as exc:  # noqa: BLE001
            warnings.warn(
                f"Failed to gather environment: {exc}.",
                RuntimeWarning,
                stacklevel=2,
            )
            return "Environment context unavailable"

    def _switch_provider(self: _ProviderMixin, provider_name: str) -> None:
        """Switch the configured provider while retaining the active runtime state."""
        from henchman.cli.provider_switch import switch_runtime_provider
        from henchman.providers.factory import create_configured_provider

        active_agent = _active_display_agent(self)
        active_provider = _active_display_provider(self)
        old_name = active_provider.name if active_provider else "unknown"
        try:
            new = create_configured_provider(self.settings.providers, provider_name=provider_name)
            switch_runtime_provider(self, new, agent=active_agent)
        except Exception as exc:  # noqa: BLE001
            self._show_provider_error(exc)
            return
        self._announce_provider_switch(old_name, provider_name)

    def _announce_provider_switch(
        self: _ProviderMixin,
        old_name: str,
        new_name: str,
    ) -> None:
        """Update UI after a successful provider switch.

        Args:
            old_name: Previous provider name.
            new_name: New provider name.
        """
        version = _import_module("henchman").__version__
        provider = _active_display_provider(self)
        self.sub_title = f"Henchman-AI v{version} - {provider.name if provider else 'unknown'}"
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is not None:
            chat.add_system_message(
                f"Provider switched: [cyan]{old_name}[/] -> [cyan]{new_name}[/]",
            )
        self._update_status_bar()  # type: ignore[attr-defined]

    def _show_provider_error(self: _ProviderMixin, exc: Exception) -> None:
        """Show a provider-switch error in the chat pane.

        Args:
            exc: The exception that occurred.
        """
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is not None:
            chat.add_error_message(f"Failed to switch provider: {exc}")
            return
        logger.exception("Failed to switch provider")


# ------------------------------------------------------------------ #
# Mixin: status bar                                                    #
# ------------------------------------------------------------------ #


class _StatusBarMixin:
    """Status bar text assembly."""

    def _update_status_bar(self: _StatusBarMixin) -> None:
        """Refresh the status bar with current info."""
        bar = _query_one_or_none(self, "#status-bar", StatusBar)
        if bar is None:
            return
        bar.status_text = self._build_status_text()

    def _build_status_text(self: _StatusBarMixin) -> str:
        """Assemble the status bar text.

        Returns:
            Formatted status string.
        """
        active_provider = _active_display_provider(self)
        provider = active_provider.name if active_provider else "?"
        model = _display_model(active_provider, "?")
        tools = self._count_tools()
        mcp = self._mcp_status_fragment()
        settings = self.settings  # type: ignore[attr-defined]
        mode = "Plan" if (settings and getattr(settings, "plan_mode", False)) else "Chat"
        return f"{mode} | {provider}:{model} | Tools: {tools}{mcp}"

    def _count_tools(self: _StatusBarMixin) -> int:
        """Count registered tools.

        Returns:
            Number of tools.
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        if not ctx or not ctx.tool_registry:
            return 0
        return len(ctx.tool_registry.list_tools())

    def _mcp_status_fragment(self: _StatusBarMixin) -> str:
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

    history_index: int

    def _load_history(self: _HistoryMixin) -> None:
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
            self.command_history = [ln for ln in lines if ln.strip()]
            self.history_index = len(self.command_history)
        except OSError:
            return

    def _persist_history_entry(self: _HistoryMixin, entry: str) -> None:
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
            with open(hf, "a", encoding="utf-8") as fh:  # noqa: PTH123
                fh.write(entry + "\n")
        except OSError as exc:
            logger.error("Failed to persist history entry: %s", exc)  # noqa: TRY400
            with contextlib.suppress(Exception):
                chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
                chat.add_error_message(f"Failed to save command history: {exc}")

    def _navigate_history(self: _HistoryMixin, direction: int) -> None:
        """Navigate command history.

        Saves the current unsent input buffer before overwriting with
        history entries and restores it when the user navigates past
        the newest entry.

        Args:
            direction: ``-1`` for older, ``+1`` for newer.
        """
        history = self.command_history
        if not history:
            return
        new_idx = self.history_index + direction
        widget = self.query_one("#input", TextArea)  # type: ignore[attr-defined]
        # Save current unsent input before overwriting (ONCE when leaving user-typed text)
        if 0 <= new_idx < len(history) and self.history_index == len(history):
            self._saved_input_buffer = widget.text
        if 0 <= new_idx < len(history):
            self.history_index = new_idx
            text = history[new_idx]
            widget.load_text(text)
            widget.cursor_location = (0, len(text))
        elif new_idx >= len(history):
            self.history_index = len(history)
            widget.load_text(
                getattr(self, "_saved_input_buffer", ""),
            )


# ------------------------------------------------------------------ #
# Mixin: context tree & welcome                                       #
# ------------------------------------------------------------------ #


class _ContextTreeMixin:
    """Context tree population, welcome banner, and theme."""

    _theme_name: str

    def _show_welcome(self: _ContextTreeMixin) -> None:
        """Display a welcome banner in the chat pane."""
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is None:
            return
        active_provider = _active_display_provider(self)
        provider = active_provider.name if active_provider else "unknown"
        model = _display_model(active_provider)
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

    def _welcome_mcp_info(self: _ContextTreeMixin) -> str:
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

    def _populate_context_tree(self: _ContextTreeMixin) -> None:
        """Populate the Context tab tree."""
        tree = _query_one_or_none(self, "#context-tree", Tree)
        if tree is None:
            return
        _fill_context_tree(tree)

    @work
    async def on_tree_node_selected(
        self: _ContextTreeMixin,
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
        await self._load_and_show_file(path)

    async def _load_and_show_file(self: _ContextTreeMixin, path: Path) -> None:
        """Load a context file and display its contents in the chat pane.

        Args:
            path: Path to the file to display.
        """
        chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        chat.add_system_message(f"[dim]Loading {path.name}...[/]")
        try:
            content_msg = await _read_context_file_content(path)
            chat.add_system_message(content_msg)
        except OSError as exc:
            self._handle_file_read_error(chat, exc, path)

    def _handle_file_read_error(
        self: _ContextTreeMixin,
        chat: ChatPane,
        exc: Exception,
        path: Path,
    ) -> None:
        """Show a file-read error in the chat pane.

        Args:
            chat: The ChatPane widget.
            exc: The exception that occurred.
            path: Path that failed to read.
        """
        with contextlib.suppress(Exception):
            chat.add_error_message(f"Cannot read {path}: {exc}")

    def _apply_theme(self: _ContextTreeMixin) -> None:
        """Apply the current theme class to the screen."""
        with contextlib.suppress(Exception):
            screen = self.screen  # type: ignore[attr-defined]
            for name in ("theme-dark", "theme-light"):
                screen.remove_class(name)
            screen.add_class(f"theme-{self._theme_name}")

    def action_toggle_theme(self: _ContextTreeMixin) -> None:
        """Toggle between dark and light themes."""
        current = self._theme_name
        self._theme_name = "light" if current == "dark" else "dark"
        self._apply_theme()
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is not None:
            chat.add_system_message(
                f"Theme switched to [cyan]{self._theme_name}[/]",
            )
        self.dark = self._theme_name == "dark"


# ------------------------------------------------------------------ #
# Mixin: input handling                                               #
# ------------------------------------------------------------------ #


class _InputHandlerMixin:
    """User input submission and routing."""

    history_index: int
    is_processing: bool

    def action_submit_message(self: _InputHandlerMixin) -> None:
        """Extract text from the input widget and process it."""
        input_widget = self.query_one("#input", TextArea)  # type: ignore[attr-defined]
        user_input = input_widget.text.strip()
        if not user_input:
            return
        self.command_history.append(user_input)  # type: ignore[attr-defined]
        self.history_index = len(self.command_history)  # type: ignore[attr-defined]
        self._persist_history_entry(user_input)  # type: ignore[attr-defined]
        input_widget.load_text("")
        if self.is_processing:
            if user_input.split()[0] in {"/goal", "/quit"}:
                self._process_live_command(user_input)
            else:
                self._queued_inputs().append(user_input)
                chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
                chat.add_system_message("Message queued for the next agent turn.")
            return
        self.is_processing = True
        self.process_user_input(user_input)

    def _queued_inputs(self) -> list[str]:
        """Keep submitted messages in order while one agent turn owns history."""
        if "_pending_inputs" not in self.__dict__:
            self._pending_inputs: list[str] = []
        return self._pending_inputs

    def _goal_session(self) -> Any:
        """Resolve the current session without retaining stale session state."""
        ctx = self.core_context  # type: ignore[attr-defined]
        return ctx.session_manager.current if ctx and ctx.session_manager else None

    def _pause_active_goal(self) -> None:
        """Stop automatic continuation after cancellation or a runtime error."""
        session = self._goal_session()
        goal = GoalService().get(session) if session is not None else None
        if goal is not None and goal.status == "active":
            GoalService().pause(session)
            save_goal_session(self.core_context.session_manager, session)  # type: ignore[attr-defined]

    def _next_turn_input(self) -> str | None:
        """Give queued user input priority over goal continuation."""
        pending = self._queued_inputs()
        if pending:
            return pending.pop(0)
        session = self._goal_session()
        return GoalService().continuation_prompt(session) if session is not None else None

    @work(group="goal-controls", exclusive=False)
    async def _process_live_command(self, text: str) -> None:
        """Allow goal controls during work without starting another agent turn."""
        chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        chat.add_user_message(text)
        await self._handle_command(text, chat)
        if not self.is_processing:
            next_input = self._next_turn_input()
            if next_input is not None:
                self.process_user_input(next_input, show_message=False)

    @work(group="chat", exclusive=False)
    async def process_user_input(
        self: _InputHandlerMixin, user_input: str, *, show_message: bool = True,
    ) -> None:
        """Process user input: commands or agent chat.

        Args:
            user_input: Raw text the user submitted.
            show_message: Display human input; hide generated continuation instructions.
        """
        if getattr(self, "current_agent_task", None) is not None:
            self._queued_inputs().append(user_input)
            return
        self.is_processing = True
        self.current_agent_task = asyncio.current_task()
        bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        bar.status_text = "Processing..."

        try:
            next_input: str | None = user_input
            while next_input is not None:
                if show_message:
                    chat.add_user_message(next_input)
                await self._route_input(next_input, chat)
                await asyncio.sleep(0.05)
                show_message = bool(self._queued_inputs())
                next_input = self._next_turn_input()
        except asyncio.CancelledError:
            self._pause_active_goal()
            self._queued_inputs().clear()
            chat.add_system_message("[yellow]\u26a0 Cancelled by user (Esc)[/]")
            for name in list(chat._active):
                chat.finish_agent_stream(name)
        except Exception as exc:  # noqa: BLE001
            self._pause_active_goal()
            details = traceback.format_exc()
            safe_details = details.replace("```", "` ` `")
            chat.add_error_message(
                f"{exc}\n```\n{safe_details}\n```",
            )
            bar.status_text = f"Error: {exc}"
            for name in list(chat._active):
                chat.finish_agent_stream(name)
        finally:
            self.is_processing = False
            if hasattr(self, "current_agent_task"):
                del self.current_agent_task
            self._update_status_bar()  # type: ignore[attr-defined]
            if self._queued_inputs():
                self.is_processing = True
                self.process_user_input(self._queued_inputs().pop(0))

    async def _route_input(self: _InputHandlerMixin, user_input: str, chat: ChatPane) -> None:
        """Route processed input to command or orchestrator.

        Args:
            user_input: Raw user text.
            chat: The ChatPane widget.
        """
        handler = self.input_handler  # type: ignore[attr-defined]
        if not handler:
            self._pause_active_goal()
            chat.add_error_message("Input handler not initialized.")
            return
        processed, is_cmd, should_continue = await handler.process_input(
            user_input,
        )
        if not should_continue or not processed:
            return

        app_module = _import_module("henchman.cli.textual_app")
        expanded = await app_module.expand_at_references(processed)
        if is_cmd:
            await self._handle_command(expanded, chat)
        else:
            await self._run_orchestrator(expanded, chat)

    def _record_user_message(self: _InputHandlerMixin, text: str) -> None:
        """Record a user message in the session.

        Args:
            text: Expanded user text.
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        if ctx and ctx.session_manager:
            ctx.session_manager.record_user_message(text)

    async def _handle_command(self: _InputHandlerMixin, text: str, chat: ChatPane) -> None:
        """Process a slash command.

        Args:
            text: Expanded command text.
            chat: The ChatPane widget.
        """
        if text.strip().lower() == "/clear":
            chat.clear_messages()
        processor = self.command_processor  # type: ignore[attr-defined]
        if not processor:
            return
        should_continue = await processor.handle_command(
            text,
            resolve_active_agent(self),
            self,
        )
        adapter = self._tui_adapter  # type: ignore[attr-defined]
        if adapter:
            adapter.flush_to_chat()
        if not should_continue:
            self.exit()  # type: ignore[attr-defined]

    async def _run_orchestrator(self: _InputHandlerMixin, text: str, chat: ChatPane) -> None:
        """Send text through the orchestrator.

        Args:
            text: Expanded user text.
            chat: The ChatPane widget.
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        orchestrator = ctx.orchestrator if ctx else None
        if not orchestrator:
            self._pause_active_goal()
            chat.add_error_message("Core components not initialized.")
            return
        bridge = _import_module("henchman.cli.textual_app").EventBridge(self)
        cfg = self.config  # type: ignore[attr-defined]
        manager = ctx.session_manager
        session_start = len(manager.current.messages) if manager.current else 0
        manager.record_user_message(text)
        if cfg.agent_role:
            agent = orchestrator.pool.get_agent(cfg.agent_role)
            stream = orchestrator.run_direct(cfg.agent_role, text)
        else:
            agent = orchestrator.tech_lead
            stream = orchestrator.run(text)

        previous_turn = agent._turn_number

        async def checked_stream() -> AsyncIterator[AgentEvent]:
            from henchman.core.events import EventType

            async for event in stream:
                if event.type == EventType.ERROR:
                    self._pause_active_goal()
                yield event

        try:
            await bridge.forward_events(checked_stream())
        finally:
            try:
                close = getattr(stream, "aclose", None)
                if close:
                    await close()
            finally:
                if agent._turn_number != previous_turn:
                    manager.sync_agent_turn(agent, session_start=session_start)
                manager.auto_save_session()


# ------------------------------------------------------------------ #
# Mixin: command palette                                              #
# ------------------------------------------------------------------ #


class _CommandPaletteMixin:
    """Command palette show/hide and selection."""

    @on(TextArea.Changed)
    def on_textarea_changed(self: _CommandPaletteMixin, event: TextArea.Changed) -> None:
        """Show/hide command palette on slash input.

        Args:
            event: TextArea change event.
        """
        text = event.control.text
        if text.startswith("/"):
            self._show_command_palette(text)
        else:
            self._hide_command_palette()

    def _show_command_palette(self: _CommandPaletteMixin, current_text: str) -> None:
        """Populate and display the command palette.

        Args:
            current_text: Text starting with ``/``.
        """
        options = self._build_palette_options(current_text.lower())
        self._render_command_options(options)

    def _build_palette_options(
        self: _CommandPaletteMixin,
        query: str,
    ) -> list[str]:
        """Build the list of matching command label strings.

        Args:
            query: Lowercase query text (starts with ``/``).

        Returns:
            Formatted option labels for matching commands.
        """
        processor = self.command_processor  # type: ignore[attr-defined]
        if not processor:
            return []
        commands = self._get_matching_commands(processor, query)
        return [f"/{cmd.name}  -- {cmd.description}" for cmd in commands]

    @staticmethod
    def _get_matching_commands(processor: Any, query: str) -> list[Any]:
        """Filter commands that match the query prefix.

        Args:
            processor: The command processor with a registry.
            query: Lowercase query text.

        Returns:
            Commands whose name prefix matches the query.
        """
        commands = processor.command_registry.get_commands()
        return [cmd for cmd in commands if f"/{cmd.name}".startswith(query) or query == "/"]

    def _render_command_options(
        self: _CommandPaletteMixin,
        options: list[str],
    ) -> None:
        """Populate the palette widget and set its visibility.

        Args:
            options: Formatted option label strings to display.
        """
        palette = self.query_one("#command-palette", OptionList)  # type: ignore[attr-defined]
        palette.clear_options()
        for opt in options:
            palette.add_option(opt)
        self._set_palette_visible(visible=bool(options))

    def _set_palette_visible(
        self: _CommandPaletteMixin,
        *,
        visible: bool,
    ) -> None:
        """Set the command palette display state.

        Args:
            visible: Whether the palette should be displayed.
        """
        palette = self.query_one("#command-palette", OptionList)  # type: ignore[attr-defined]
        palette.display = visible

    def _hide_command_palette(self: _CommandPaletteMixin) -> None:
        """Hide the command palette."""
        self._set_palette_visible(visible=False)

    @on(OptionList.OptionSelected, "#command-palette")
    def on_command_selected(
        self: _CommandPaletteMixin,
        event: OptionList.OptionSelected,
    ) -> None:
        """Fill the input with the selected command.

        Args:
            event: Option selection event.
        """
        raw = str(event.option.prompt)
        cmd_part = raw.split("  --", maxsplit=1)[0].strip()
        self._fill_input_with_text(cmd_part + " ")
        self._hide_command_palette()

    def _fill_input_with_text(self: _CommandPaletteMixin, text: str) -> None:
        """Load text into the input widget and position the cursor.

        Args:
            text: The text to load.
        """
        widget = self.query_one("#input", TextArea)  # type: ignore[attr-defined]
        widget.load_text(text)
        widget.cursor_location = (0, len(text))
        widget.focus()

    def action_show_help(self: _CommandPaletteMixin) -> None:
        """Show the help/keybinding modal."""
        self._push_textual_screen("HelpScreen")

    def action_switch_provider(self: _CommandPaletteMixin) -> None:
        """Show the provider switching modal."""
        self._push_textual_screen("ProviderScreen")

    def _push_textual_screen(self: _CommandPaletteMixin, screen_name: str) -> None:
        """Push a named screen from the textual_app module.

        Args:
            screen_name: Class name of the screen to push.
        """
        screen_cls = getattr(_import_module("henchman.cli.textual_app"), screen_name)
        self.push_screen(screen_cls())  # type: ignore[attr-defined]

    # -- Tier 10 screen actions --

    def action_show_search_dialog(self: _CommandPaletteMixin) -> None:
        """Show the search dialog."""
        self._push_textual_screen("SearchScreen")

    def action_show_history_search(self: _CommandPaletteMixin) -> None:
        """Show the history search dialog."""
        self._push_textual_screen("HistorySearchScreen")

    def action_show_theme_picker(self: _CommandPaletteMixin) -> None:
        """Show the theme picker dialog."""
        self._push_textual_screen("ThemePickerScreen")

    def action_show_model_picker(self: _CommandPaletteMixin) -> None:
        """Show the model picker dialog."""
        self._push_textual_screen("ModelPickerScreen")

    def action_show_auto_mode_dialog(self: _CommandPaletteMixin) -> None:
        """Show the auto-mode dialog."""
        self._push_textual_screen("AutoModeScreen")

    def action_show_bridge_dialog(self: _CommandPaletteMixin) -> None:
        """Show the bridge dialog."""
        try:
            entries = self._build_bridge_dialog_entries()  # type: ignore[attr-defined]
        except _WORKSPACE_DATA_ERRORS as exc:
            self._show_workspace_error("bridges", exc)  # type: ignore[attr-defined]
            return
        screen_cls = _import_module("henchman.cli.textual_app").BridgeScreen
        self.push_screen(screen_cls(entries))  # type: ignore[attr-defined]

    def action_show_export_dialog(self: _CommandPaletteMixin) -> None:
        """Show the export dialog."""
        screen_cls = _import_module("henchman.cli.textual_app").ExportScreen
        self.push_screen(  # type: ignore[attr-defined]
            screen_cls(),
            self._handle_export_result,  # type: ignore[attr-defined]
        )

    def action_show_feedback_dialog(self: _CommandPaletteMixin) -> None:
        """Show the feedback dialog."""
        self._push_textual_screen("FeedbackScreen")

    def action_show_mcp_servers(self: _CommandPaletteMixin) -> None:
        """Show the MCP servers dialog."""
        self._push_textual_screen("McpServersScreen")

    def action_show_onboarding(self: _CommandPaletteMixin) -> None:
        """Show the onboarding dialog."""
        screen_cls = _import_module("henchman.cli.textual_app").OnboardingScreen
        self.push_screen(  # type: ignore[attr-defined]
            screen_cls(),
            self._handle_onboarding_result,  # type: ignore[attr-defined]
        )


# ------------------------------------------------------------------ #
# Mixin: message handlers                                             #
# ------------------------------------------------------------------ #


class _MessageHandlerMixin:
    """Textual message handlers for agent events."""

    def on_agent_content_message(
        self: _MessageHandlerMixin,
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
        self: _MessageHandlerMixin,
        message: AgentThoughtMessage,
    ) -> None:
        """Add thinking content to chat pane and thinking pane.

        Args:
            message: Thought from an agent.
        """
        source = message.source_agent
        thought = message.thought
        pane = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        pane.append_thinking_chunk(source or "", thought)

        thinking = _query_one_or_none(self, "#thinking-pane", ThinkingPane)
        if thinking is not None:
            label = source or "Agent"
            thinking.write(
                f"[dim]\U0001f914 {_safe_markup(label)}: {_safe_markup(thought)}[/]",
            )
            thinking.scroll_end(animate=False)

    def on_tool_call_request_message(
        self: _MessageHandlerMixin,
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

        tool_pane = _query_one_or_none(self, "#tool-pane", ToolPane)
        if tool_pane is not None:
            full_args = self._format_full_tool_args(tc)
            tool_pane.write(
                f"[yellow]\u25b6 {_safe_markup(tc.name)}[/]\n[dim]{_safe_markup(full_args)}[/]",
            )
            tool_pane.scroll_end(animate=False)

    @staticmethod
    def _format_tool_args(tool_call: Any) -> str:
        """Format tool call arguments for compact display.

        Args:
            tool_call: Tool call with an arguments attr.

        Returns:
            Formatted arguments string.
        """
        args = tool_call.arguments
        if not args:
            return ""
        try:
            parsed = json.loads(args) if isinstance(args, str) else args
            return json.dumps(parsed, separators=(",", ":"))
        except (TypeError, ValueError):
            return str(args)

    @staticmethod
    def _format_full_tool_args(tool_call: Any) -> str:
        """Format tool call arguments for the tool pane (pretty).

        Args:
            tool_call: Tool call with an arguments attr.

        Returns:
            Pretty-printed arguments or empty string.
        """
        args = tool_call.arguments
        if not args:
            return ""
        try:
            parsed = json.loads(args) if isinstance(args, str) else args
            return json.dumps(parsed, indent=2)
        except (TypeError, ValueError):
            return str(args)

    def on_tool_call_result_message(
        self: _MessageHandlerMixin,
        message: ToolCallResultMessage,
    ) -> None:
        """Add a tool result to both chat and tool panes.

        Args:
            message: Tool execution result.
        """
        result_str = self._format_tool_result(message.result)

        pane = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        pane.add_tool_message(f"Result: {result_str}")

        tool_pane = _query_one_or_none(self, "#tool-pane", ToolPane)
        if tool_pane is not None:
            tool_pane.write(f"[green]\u2190 {_safe_markup(result_str)}[/]")
            tool_pane.scroll_end(animate=False)

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
        self: _MessageHandlerMixin,
        message: ToolConfirmationMessage,
    ) -> None:
        """Fallback for TOOL_CONFIRMATION events.

        The ToolManager's handler already shows the modal.

        Args:
            message: Confirmation request message.
        """

    def on_agent_status_message(
        self: _MessageHandlerMixin,
        message: AgentStatusMessage,
    ) -> None:
        """Update the status bar.

        Args:
            message: Status update from an agent.
        """
        bar = _query_one_or_none(self, "#status-bar", StatusBar)
        if bar is not None:
            bar.status_text = message.status

    def on_agent_finished_message(
        self: _MessageHandlerMixin,
        message: AgentFinishedMessage,
    ) -> None:
        """Handle agent completion.

        Args:
            message: Finished signal from an agent.
        """
        chat = self.query_one("#chat-pane", ChatPane)  # type: ignore[attr-defined]
        name = message.source_agent or "Assistant"
        chat.finish_agent_stream(name)
        self._update_status_bar()  # type: ignore[attr-defined]

    def on_command_output_message(
        self: _MessageHandlerMixin,
        message: CommandOutputMessage,
    ) -> None:
        """Route command output to the chat pane.

        Args:
            message: Output text from a command.
        """
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is not None:
            chat.add_system_message(message.text)

    def on_switch_provider_message(
        self: _MessageHandlerMixin,
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

    def _toggle_tab(self: _PaneActionMixin, tab_id: str) -> None:
        """Toggle a tabbed-content tab.

        Args:
            tab_id: CSS id of the tab to toggle.
        """
        tabs = _query_one_or_none(self, TabbedContent)
        if tabs is not None:
            tabs.active = "tab-chat" if tabs.active == tab_id else tab_id

    def action_toggle_thinking_pane(self: _PaneActionMixin) -> None:
        """Toggle the thinking tab."""
        self._toggle_tab("tab-thinking")

    def action_toggle_tool_pane(self: _PaneActionMixin) -> None:
        """Toggle the tools tab."""
        self._toggle_tab("tab-tools")

    def action_clear_thinking_pane(self: _PaneActionMixin) -> None:
        """Clear the thinking pane and chat thinking messages."""
        self.query_one("#chat-pane", ChatPane).clear_thinking_messages()  # type: ignore[attr-defined]
        self._clear_pane_and_set_status(
            "#thinking-pane",
            ThinkingPane,
            "Thinking cleared (legacy pane and chat messages)",
        )

    def action_clear_tool_pane(self: _PaneActionMixin) -> None:
        """Clear all content from the tool pane."""
        self._clear_pane_and_set_status("#tool-pane", ToolPane, "Tool pane cleared")

    def _clear_pane_and_set_status(
        self: _PaneActionMixin,
        css_id: str,
        pane_cls: type,
        status: str,
    ) -> None:
        """Clear a pane widget and update the status bar message.

        Args:
            css_id: CSS selector for the pane widget.
            pane_cls: Widget class for the query.
            status: Status text to show after clearing.
        """
        self.query_one(css_id, pane_cls).clear()  # type: ignore[attr-defined]
        bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        bar.status_text = status


# ------------------------------------------------------------------ #
# Mixin: search                                                       #
# ------------------------------------------------------------------ #


class _SearchMixin:
    """Full-text search across chat, thinking, and tool panes."""

    _search_mode: bool
    _search_query: str
    _search_matches: list[tuple[str, int, str]]
    _current_match_index: int

    def action_search(self: _SearchMixin) -> None:
        """Enter search mode or find next match."""
        if self._search_mode:
            self.action_search_next()
            return
        self._search_mode = True
        bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
        bar.status_text = "Search: type in input box then press F3"

    def action_cancel_or_clear(self: _SearchMixin) -> None:
        """Cancel processing or clear search."""
        if self.is_processing and hasattr(self, "current_agent_task"):  # type: ignore[attr-defined]
            task = self.current_agent_task
            if task is not None:
                task.cancel()
            bar = self.query_one("#status-bar", StatusBar)  # type: ignore[attr-defined]
            bar.status_text = "Cancelling..."
            return
        self.action_clear_search()

    def action_clear_search(self: _SearchMixin) -> None:
        """Exit search mode and reset state."""
        self._clear_highlights()
        self._search_mode = False
        self._search_query = ""
        self._search_matches = []
        self._current_match_index = -1
        bar = _query_one_or_none(self, "#status-bar", StatusBar)
        if bar is not None:
            bar.status_text = "Ready"

    def action_search_next(self: _SearchMixin) -> None:
        """Move to the next search match."""
        if not self._search_mode:
            return
        self._refresh_search_if_changed()
        matches = self._search_matches
        if not matches:
            return
        self._current_match_index = (self._current_match_index + 1) % len(matches)
        self._scroll_to_match()
        self._update_search_status()

    def action_search_previous(self: _SearchMixin) -> None:
        """Move to the previous search match."""
        if not self._search_mode:
            return
        self._refresh_search_if_changed()
        matches = self._search_matches
        if not matches:
            return
        self._current_match_index = (self._current_match_index - 1) % len(matches)
        self._scroll_to_match()
        self._update_search_status()

    def _refresh_search_if_changed(self: _SearchMixin) -> None:
        """Re-run search if the query text changed."""
        widget = self.query_one("#input", TextArea)  # type: ignore[attr-defined]
        query = widget.text.strip()
        if query != self._search_query:
            self._perform_search(query)

    def _perform_search(self: _SearchMixin, query: str) -> None:
        """Index text matches in chat, thinking, and tool panes.

        Args:
            query: Search string (case-insensitive).
        """
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

    def _search_chat_pane(self: _SearchMixin, query_lower: str) -> None:
        """Collect matches from the chat pane.

        Args:
            query_lower: Lowercase search query.
        """
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is None:
            return
        for idx, widget in enumerate(chat.children):
            content = ""
            if isinstance(widget, (ChatMessage, ThinkingMessage, ToolMessage)):
                content = _get_searchable_content(widget)
            if content and query_lower in content.lower():
                self._search_matches.append(
                    ("chat", idx, content),
                )

    def _search_richlog_panes(self: _SearchMixin, query_lower: str) -> None:
        """Search thinking and tool RichLog panes.

        Args:
            query_lower: Lowercase search query.
        """
        pane_configs = (
            ("#thinking-pane", "thinking", ThinkingPane),
            ("#tool-pane", "tool", ToolPane),
        )
        for css_id, pane_id, pane_cls in pane_configs:
            pane = _query_one_or_none(self, css_id, pane_cls)
            if pane is not None:
                self._search_richlog(pane, pane_id, query_lower)

    def _search_richlog(
        self: _SearchMixin,
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
                self._search_matches.append(
                    (pane_id, idx, text),
                )

    def _scroll_to_match(self: _SearchMixin) -> None:
        """Scroll to the current search match."""
        matches = self._search_matches
        idx = self._current_match_index
        if not matches or idx < 0:
            return
        pane_id, line_idx, _ = matches[idx]
        if pane_id == "chat":
            self._scroll_chat_match(line_idx)
        elif pane_id in _PANE_MAP:
            self._scroll_richlog_match(pane_id)

    def _apply_highlights(self: _SearchMixin, term: str) -> None:
        """Apply search highlight to matching widgets in the chat pane.

        Args:
            term: Search term to highlight.
        """
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is None:
            return
        for widget in chat.children:
            set_highlight = getattr(widget, "set_highlight", None)
            if callable(set_highlight):
                set_highlight(term)

    def _clear_highlights(self: _SearchMixin) -> None:
        """Remove search highlights from all widgets in the chat pane."""
        self._apply_highlights("")

    def _scroll_chat_match(self: _SearchMixin, line_idx: int) -> None:
        """Scroll a chat pane child into view.

        Args:
            line_idx: Index of the matching child widget.
        """
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is None:
            return
        children = list(chat.children)
        if 0 <= line_idx < len(children):
            children[line_idx].scroll_visible(animate=False)

    def _scroll_richlog_match(self: _SearchMixin, pane_id: str) -> None:
        """Scroll a RichLog pane to end for visibility.

        Args:
            pane_id: ``'thinking'`` or ``'tool'``.
        """
        if pane_id not in _PANE_MAP:
            return
        css_id, cls = _PANE_MAP[pane_id]
        pane: ThinkingPane | ToolPane | None = _query_one_or_none(self, css_id, cls)
        if pane is not None:
            pane.scroll_end(animate=False)

    def _update_search_status(self: _SearchMixin) -> None:
        """Refresh the status bar with search info."""
        bar = _query_one_or_none(self, "#status-bar", StatusBar)
        if bar is None:
            return
        if not self._search_mode:
            return
        query = self._search_query
        matches = self._search_matches
        if not query:
            bar.status_text = "Search: type query in input box, F3=next"
        elif not matches:
            bar.status_text = f"No matches for '{query}'"
        else:
            cur = self._current_match_index + 1
            tot = len(matches)
            bar.status_text = f"Match {cur}/{tot} for '{query}' - F3=next  Shift+F3=prev  Esc=clear"


# ------------------------------------------------------------------ #
# Mixin: public API helpers                                            #
# ------------------------------------------------------------------ #


class _PublicAPIMixin:
    """Public helper methods for external callers."""

    def set_session(self: _PublicAPIMixin, session: Any) -> None:
        """Activate a loaded session.

        Args:
            session: Session to activate.
        """
        ctx = self.core_context  # type: ignore[attr-defined]
        if not ctx:
            return
        mgr = ctx.session_manager
        if not mgr:
            return
        role = self.config.agent_role  # type: ignore[attr-defined]
        history_agent = ctx.orchestrator.pool.get_agent(role) if role else ctx.orchestrator.tech_lead
        mgr.set_session(session, history_agent=history_agent)

    def update_status(
        self: _PublicAPIMixin,
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
        bar = _query_one_or_none(self, "#status-bar", StatusBar)
        if bar is not None:
            bar.status_text = message
            self._apply_bar_stats(bar, tokens, cost)

    def _apply_bar_stats(
        self: _PublicAPIMixin,
        bar: StatusBar,
        tokens: int | None,
        cost: float | None,
    ) -> None:
        """Apply token and cost stats to the status bar widget.

        Args:
            bar: The StatusBar widget.
            tokens: Optional token count.
            cost: Optional cost in USD.
        """
        if tokens is not None:
            bar.tokens = tokens
        if cost is not None:
            bar.cost = cost

    def add_message(self: _PublicAPIMixin, role: str, content: str) -> None:
        """Add a message to the chat pane.

        Args:
            role: Sender role ('user', 'assistant', 'system').
            content: Message content.
        """
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if chat is None:
            return
        self._dispatch_to_chat(chat, role, content)

    def _dispatch_to_chat(
        self: _PublicAPIMixin,
        chat: ChatPane,
        role: str,
        content: str,
    ) -> None:
        """Route a message to the correct chat pane method by role.

        Args:
            chat: The ChatPane widget.
            role: Sender role.
            content: Message content.
        """
        text = content if role in ("user", "assistant", "system") else f"[{role}] {content}"
        if role == "user":
            chat.add_user_message(text)
        else:
            chat.add_system_message(text)


# ------------------------------------------------------------------ #
# Tier 10 workspace refresh helpers                                    #
# ------------------------------------------------------------------ #


class _WorkspaceMixin:
    """Workspace panel refresh and export helpers."""

    def _notify_user(
        self: _WorkspaceMixin,
        message: str,
        *,
        severity: str = "information",
    ) -> None:
        """Send a global Textual notification when the app provides one."""

        notifier = getattr(self, "notify", None)
        if callable(notifier):
            notifier(message, severity=severity, markup=False)

    def _show_workspace_error(
        self: _WorkspaceMixin,
        surface: str,
        exc: Exception,
    ) -> str:
        """Report a persisted workspace read failure and return its message."""

        message = f"Failed to load {surface}: {exc}"
        self._notify_user(message, severity="error")
        return message

    def on_button_pressed(
        self: _WorkspaceMixin,
        event: Button.Pressed,
    ) -> None:
        """Route buttons mounted in the workspace overview."""

        button_id = event.button.id
        if button_id == "workspace-refresh":
            self._refresh_workspace_widgets()
        elif button_id == "workspace-bridges":
            self.action_show_bridge_dialog()  # type: ignore[attr-defined]
        elif button_id == "workspace-export":
            self.action_show_export_dialog()  # type: ignore[attr-defined]

    def _refresh_workspace_widgets(self: _WorkspaceMixin) -> None:
        """Refresh all workspace panels with current state."""
        summary = _query_one_or_none(self, "#agent-summary-panel", AgentSummaryPanel)
        memory = _query_one_or_none(self, "#memory-indicators", MemoryIndicator)
        tasks_widget = _query_one_or_none(self, "#task-list-widget", TaskListWidget)
        skills = _query_one_or_none(self, "#skill-components", SkillPanel)
        team = _query_one_or_none(self, "#team-components", TeamPanel)
        settings_panel = _query_one_or_none(self, "#settings-panels", SettingsPanel)

        provider = _active_display_provider(self)
        settings = getattr(self, "settings", None)
        ctx = getattr(self, "core_context", None)
        mgr = getattr(ctx, "session_manager", None) if ctx else None
        current = getattr(mgr, "current", None) if mgr else None
        plan_mode = bool(getattr(current, "plan_mode", False))

        if summary is not None:
            summary.update_summary(
                provider_name=provider.name if provider else "",
                model_name=_display_model(provider, ""),
                mode="Plan" if plan_mode else "Chat",
                active_agent="",
                tools=0,
            )

        if memory is not None:
            msg_count = len(getattr(current, "messages", []))
            history = getattr(self, "command_history", [])
            memory.update_counts(
                session_messages=msg_count,
                history_entries=len(history),
                context_loaded=bool(getattr(settings, "system_prompt", None)),
            )

        if tasks_widget is not None:
            try:
                service = TaskService()
                task_list = service.list_tasks()
                tasks_widget.set_tasks(
                    [f"{t.task_id} [{t.status}] {t.title}" for t in task_list],
                )
            except _WORKSPACE_DATA_ERRORS as exc:
                message = self._show_workspace_error("tasks", exc)
                tasks_widget.set_tasks([f"[red]{_safe_markup(message)}[/]"])

        if skills is not None:
            try:
                catalog = SkillCatalog()
                skill_list = catalog.list_skills()
                skills.set_skills([s.name for s in skill_list])
            except _WORKSPACE_DATA_ERRORS as exc:
                message = self._show_workspace_error("skills", exc)
                skills.set_skills([f"[red]{_safe_markup(message)}[/]"])

        if team is not None:
            try:
                ws_service = TeamWorkspaceService()
                ws_list = ws_service.list_workspaces()
                team.set_workspaces(
                    [f"{w.name} ({len(w.members)} members)" for w in ws_list],
                )
            except _WORKSPACE_DATA_ERRORS as exc:
                message = self._show_workspace_error("teams", exc)
                team.set_workspaces([f"[red]{_safe_markup(message)}[/]"])

        if settings_panel is not None:
            mcp_count = 0
            if ctx and ctx.mcp_manager:
                mcp_count = len(ctx.mcp_manager.clients)
            ui_settings = getattr(settings, "ui", None) if settings else None
            tool_manager = getattr(ctx, "tool_manager", None) if ctx else None
            runtime_auto = getattr(tool_manager, "auto_approve", None)
            config = getattr(self, "config", None)
            auto_mode = (
                runtime_auto
                if isinstance(runtime_auto, bool)
                else bool(getattr(config, "auto_approve_tools", False))
            )
            settings_panel.update_settings(
                theme=getattr(ui_settings, "theme", "") if ui_settings else "",
                auto_mode=auto_mode,
                provider=provider.name if provider else "",
                mcp_servers=mcp_count,
            )

    def _build_bridge_dialog_entries(self: _WorkspaceMixin) -> list[str]:
        """Build bridge dialog entries from persisted metadata.

        Returns:
            List of bridge entry description strings.
        """
        entries: list[str] = []
        ws_service = TeamWorkspaceService()
        bridge_service = BridgeSessionService()
        workspaces = ws_service.list_workspaces()
        for ws in workspaces:
            bridges = bridge_service.list_bridges(workspace_id=ws.workspace_id)
            for b in bridges:
                entries.append(
                    f"{ws.name} / {b.bridge_id} ({b.status})"
                    f" - {b.remote_session} by {b.created_by}",
                )
        return entries

    def _handle_export_result(self: _WorkspaceMixin, result: str | None) -> None:
        """Handle export dialog result.

        Args:
            result: Export format selected, or ``None`` if cancelled.
        """
        chat = _query_one_or_none(self, "#chat-pane", ChatPane)
        if not result:
            if chat is not None:
                chat.add_system_message("[dim]Export cancelled.[/]")
            return

        ctx = getattr(self, "core_context", None)
        mgr = ctx.session_manager if ctx else None
        current = getattr(mgr, "current", None) if mgr else None
        if current is None:
            message = "Failed to export session: No active session to export."
            if chat is not None:
                chat.add_error_message(message)
            self._notify_user(message, severity="error")
            return

        try:
            output = export_as_markdown(current, include_metadata=True)
            output_path = Path.cwd() / f"session_{current.id}.md"
            output_path.write_text(output, encoding="utf-8")
            if chat is not None:
                chat.add_system_message(
                    f"[dim]Session exported to [cyan]{output_path}[/][/]",
                )
            self._notify_user(f"Session exported to {output_path}")
        except (OSError, TypeError, ValueError) as exc:
            message = f"Failed to export session: {exc}"
            if chat is not None:
                chat.add_error_message(message)
            self._notify_user(message, severity="error")

    def _handle_onboarding_result(self: _WorkspaceMixin, result: str | None) -> None:
        """Handle onboarding dialog result.

        Args:
            result: Onboarding action selected, or ``None`` if cancelled.
        """
        if result == "settings":
            tabs = _query_one_or_none(self, TabbedContent)
            if tabs is not None:
                tabs.active = "tab-workspace"
            self._refresh_workspace_widgets()
        elif result == "theme":
            self.action_show_theme_picker()  # type: ignore[attr-defined]
