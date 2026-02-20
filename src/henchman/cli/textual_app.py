"""Textual TUI for Henchman-AI.

This module provides a Textual-based terminal user interface for Henchman-AI,
with full feature parity with the Rich/prompt_toolkit REPL plus a multi-pane layout,
real search, provider switching, and an interactive context tree.
"""

from __future__ import annotations

import asyncio
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console as RichConsole
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    OptionList,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)

from henchman.cli.command_processor import CommandProcessor
from henchman.cli.core_init import CoreContext, create_core_context, initialize_mcp
from henchman.cli.input import expand_at_references
from henchman.cli.input_handler import InputHandler
from henchman.cli.output_handler import OutputHandler
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.ui_renderer import UIRenderer
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ModelProvider

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from henchman.config.schema import Settings
    from henchman.core.session import Session
    from henchman.tools.base import ConfirmationRequest


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class TextualConfig:
    """Configuration for the Textual TUI.

    Attributes:
        prompt: The prompt string to display.
        system_prompt: System prompt for the agent.
        auto_save: Whether to auto-save sessions on exit.
        history_file: Path to history file.
        base_tool_iterations: Base limit for tool iterations per turn.
        max_tool_calls_per_turn: Maximum tool calls allowed per turn.
        auto_approve_tools: Auto-approve all tool executions (non-interactive mode).
    """

    prompt: str = "❯ "
    system_prompt: str = ""
    auto_save: bool = True
    history_file: Path | None = None
    base_tool_iterations: int = 25
    max_tool_calls_per_turn: int = 100
    auto_approve_tools: bool = False


# ---------------------------------------------------------------------------
# Component Initializer
# ---------------------------------------------------------------------------


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
    settings: Any  # Settings type would cause circular import
    environment_context: str | None
    app: Any  # HenchmanTextualApp type would cause circular import


class ComponentInitializer:
    """Handles initialization of core Henchman components for the Textual TUI.

    This class encapsulates the complex component setup logic, making it
    more testable and maintainable.
    """

    def __init__(self, config: ComponentConfig) -> None:
        """Initialize the component initializer.

        Args:
            config: Component configuration.
        """
        self.config = config
        self.core_context: CoreContext | None = None
        self.tool_executor: ToolExecutor | None = None
        self.command_processor: CommandProcessor | None = None
        self.input_handler: InputHandler | None = None
        self.output_handler: OutputHandler | None = None
        self._tui_adapter: TuiConsoleAdapter | None = None
        self._ui_renderer: UIRenderer | None = None

    def initialize_all(self) -> None:
        """Initialize all core components."""
        self._initialize_tui_adapter()
        self._initialize_core_context()
        self._initialize_renderer()
        self._initialize_output_handler()
        self._initialize_command_processor()
        self._initialize_tool_executor()
        self._initialize_input_handler()
        self._initialize_mcp()

    def _initialize_tui_adapter(self) -> None:
        """Initialize the TUI console adapter."""
        self._tui_adapter = TuiConsoleAdapter(self.config.app)

    def _initialize_core_context(self) -> None:
        """Initialize the core context."""
        self.core_context = create_core_context(
            provider=self.config.provider,
            system_prompt=self.config.config.system_prompt,
            environment_context=self.config.environment_context,
            settings=self.config.settings,
            auto_approve_tools=self.config.config.auto_approve_tools,
        )
        self.core_context.plugin_manager.ui_instance = self.config.app  # type: ignore[attr-defined]

    def _initialize_renderer(self) -> None:
        """Initialize the UI renderer."""
        from henchman.cli.console import OutputRenderer, ThemeManager

        if not self._tui_adapter:
            raise RuntimeError("TUI adapter must be initialized first")

        console = self._tui_adapter.console
        theme_manager = ThemeManager()

        # Determine theme name with safe defaults
        theme_name = "dark"  # Default theme
        if self.config.settings and self.config.settings.ui and self.config.settings.ui.theme:
            theme_name = self.config.settings.ui.theme

        # Validate theme exists
        if theme_name not in theme_manager.list_themes():
            theme_name = "dark"

        theme = theme_manager.get_theme(theme_name)
        output_renderer = OutputRenderer(console=console, theme=theme)
        self._ui_renderer = UIRenderer(console=console, renderer=output_renderer)

    def _initialize_output_handler(self) -> None:
        """Initialize the output handler."""
        if not self.core_context or not self._ui_renderer:
            raise RuntimeError("Core context and renderer must be initialized first")

        self.output_handler = OutputHandler(
            renderer=self._ui_renderer,
            tool_manager=self.core_context.tool_manager,
            session_manager=self.core_context.session_manager,
            provider=self.config.provider,
            settings=self.config.settings,
            rag_system=None,
            mcp_manager=self.core_context.mcp_manager,
        )

    def _initialize_command_processor(self) -> None:
        """Initialize the command processor."""
        if not self.core_context or not self.output_handler:
            raise RuntimeError("Core context and output handler must be initialized first")

        self.command_processor = CommandProcessor(
            output_handler=self.output_handler,
            tool_manager=self.core_context.tool_manager,
            session_manager=self.core_context.session_manager,
            provider=self.config.provider,
            mcp_manager=self.core_context.mcp_manager,
        )

    def _initialize_tool_executor(self) -> None:
        """Initialize the tool executor."""
        if not self.core_context or not self.output_handler:
            raise RuntimeError("Core context and output handler must be initialized first")

        self.tool_executor = ToolExecutor(
            output_handler=self.output_handler,
            tool_manager=self.core_context.tool_manager,
            provider=self.config.provider,
            base_tool_iterations=self.config.config.base_tool_iterations,
            max_tool_calls_per_turn=self.config.config.max_tool_calls_per_turn,
        )

    def _initialize_input_handler(self) -> None:
        """Initialize the input handler."""
        if not self._ui_renderer:
            raise RuntimeError("Renderer must be initialized first")

        history_file = self.config.config.history_file or Path.home() / ".henchman_history"
        keybindings = (
            self.config.settings.ui.keybindings
            if self.config.settings and self.config.settings.ui
            else None
        )

        self.input_handler = InputHandler(
            config=self.config.config,  # type: ignore[arg-type]
            renderer=self._ui_renderer,
            history_file=history_file,
            keybindings=keybindings,
        )

    def _initialize_mcp(self) -> None:
        """Initialize MCP if available."""
        if self.core_context and self.core_context.mcp_manager:
            initialize_mcp(self.core_context)


# ---------------------------------------------------------------------------
# Custom input widget
# ---------------------------------------------------------------------------


class HenchmanTextArea(TextArea):
    """Custom TextArea with Enter/Shift-Enter and history navigation."""

    BINDINGS = [
        Binding("ctrl+f", "app.search", "Search", show=False),
        Binding("enter", "app.action_submit_message", "Submit Message", show=False),
        Binding("shift+enter", "newline", "Newline", show=False),
        Binding("escape", "app.clear_search", "Clear Search", show=False),
        Binding("up", "history_up", "History Up", show=False),
        Binding("down", "history_down", "History Down", show=False),
    ]

    async def on_key(self, event: events.Key) -> None:
        """Handle key events.

        Args:
            event: Incoming key event.
        """
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.app.action_submit_message()  # type: ignore[attr-defined]
            return
        if event.key == "shift+enter":
            event.stop()
            event.prevent_default()
            self.insert("\n")
            return

    def action_newline(self) -> None:
        """Insert a newline character."""
        self.insert("\n")

    def action_history_up(self) -> None:
        """Move up or navigate history."""
        if self.cursor_location[0] == 0:
            self.app._navigate_history(-1)  # type: ignore[attr-defined]
        else:
            self.action_cursor_up()

    def action_history_down(self) -> None:
        """Move down or navigate history."""
        lines = self.document.line_count - 1
        if self.cursor_location[0] >= lines:
            self.app._navigate_history(1)  # type: ignore[attr-defined]
        else:
            self.action_cursor_down()

    def on_mount(self) -> None:
        """Setup on mount."""
        pass


# ---------------------------------------------------------------------------
# Textual Messages (one per AgentEvent type that needs UI dispatch)
# ---------------------------------------------------------------------------


class AgentContentMessage(Message):
    """Streamed text content from an agent."""

    def __init__(self, content: str, source_agent: str | None = None) -> None:
        """Initialize.

        Args:
            content: Text chunk from the agent.
            source_agent: Originating agent name.
        """
        super().__init__()
        self.content = content
        self.source_agent = source_agent


class AgentThoughtMessage(Message):
    """Thinking/reasoning text from an agent."""

    def __init__(self, thought: str, source_agent: str | None = None) -> None:
        """Initialize.

        Args:
            thought: Reasoning text.
            source_agent: Originating agent name.
        """
        super().__init__()
        self.thought = thought
        self.source_agent = source_agent


class ToolCallRequestMessage(Message):
    """Agent is requesting a tool call."""

    def __init__(self, tool_call: Any, source_agent: str | None = None) -> None:
        """Initialize.

        Args:
            tool_call: ToolCall object (name, arguments).
            source_agent: Originating agent name.
        """
        super().__init__()
        self.tool_call = tool_call
        self.source_agent = source_agent


class ToolCallResultMessage(Message):
    """Result from a tool execution."""

    def __init__(self, result: Any, source_agent: str | None = None) -> None:
        """Initialize.

        Args:
            result: Tool result data.
            source_agent: Originating agent name.
        """
        super().__init__()
        self.result = result
        self.source_agent = source_agent


class ToolConfirmationMessage(Message):
    """Agent is awaiting user approval for a tool call."""

    def __init__(self, request: ConfirmationRequest, source_agent: str | None = None) -> None:
        """Initialize.

        Args:
            request: ConfirmationRequest with tool details.
            source_agent: Originating agent name.
        """
        super().__init__()
        self.request = request
        self.source_agent = source_agent


class AgentStatusMessage(Message):
    """Status update from the agent loop."""

    def __init__(self, status: str, source_agent: str | None = None) -> None:
        """Initialize.

        Args:
            status: Status string.
            source_agent: Originating agent name.
        """
        super().__init__()
        self.status = status
        self.source_agent = source_agent


class AgentFinishedMessage(Message):
    """Agent has finished processing the current turn."""

    def __init__(self, source_agent: str | None = None) -> None:
        """Initialize.

        Args:
            source_agent: Originating agent name.
        """
        super().__init__()
        self.source_agent = source_agent


class CommandOutputMessage(Message):
    """Output produced by a slash command (to route to chat pane)."""

    def __init__(self, text: str, style: str = "") -> None:
        """Initialize.

        Args:
            text: Output text.
            style: Optional Rich markup style.
        """
        super().__init__()
        self.text = text
        self.style = style


# ---------------------------------------------------------------------------
# Chat pane: streaming-aware with per-turn Static widgets
# ---------------------------------------------------------------------------


class ChatMessage(Static):
    """A single rendered chat message (supports live-update during streaming).

    The content is stored as raw markdown, and the widget re-renders on every
    update so streaming text flows naturally.
    """

    DEFAULT_CSS = """
    ChatMessage {
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, prefix: str, content: str = "", **kwargs: Any) -> None:
        """Initialize.

        Args:
            prefix: Rich-markup prefix (e.g. ``[bold cyan]Assistant:[/]``).
            content: Initial content (may be empty at construction for streaming).
            **kwargs: Extra kwargs forwarded to Static.
        """
        super().__init__("", **kwargs)
        self._prefix = prefix
        self._content = content
        self._update_renderable()

    def _update_renderable(self) -> None:
        """Re-render the static widget with current content."""
        self.update(f"{self._prefix} {self._content}")

    def append(self, chunk: str) -> None:
        """Append a streaming chunk and re-render.

        Args:
            chunk: Text to append.
        """
        self._content += chunk
        self._update_renderable()

    def set_content(self, content: str) -> None:
        """Replace content entirely and re-render.

        Args:
            content: Full replacement content.
        """
        self._content = content
        self._update_renderable()


class ThinkingMessage(Static):
    """Stub implementation for ThinkingMessage widget.
    
    TODO: Implement proper collapsible thinking message display.
    """
    
    def __init__(self, thought: str = "", agent_name: str = "", **kwargs: Any) -> None:
        """Initialize stub ThinkingMessage.
        
        Args:
            thought: The thinking content.
            agent_name: Name of the agent doing the thinking.
            **kwargs: Forwarded to Static.
        """
        super().__init__(f"🤔 {agent_name}: {thought}", **kwargs)


class ToolMessage(Static):
    """Stub implementation for ToolMessage widget.
    
    TODO: Implement proper collapsible tool call/result display.
    """
    
    def __init__(self, thought: str = "", tool_call: Any = None, **kwargs: Any) -> None:
        """Initialize stub ToolMessage.
        
        Args:
            thought: Tool thought/description.
            tool_call: Tool call object.
            **kwargs: Forwarded to Static.
        """
        content = f"🛠️ Tool: {thought}" if thought else "🛠️ Tool call"
        super().__init__(content, **kwargs)
    
    def append(self, chunk: str) -> None:
        """Stub append method."""
        pass
    
    def toggle_expansion(self) -> None:
        """Stub toggle expansion method."""
        pass


class ChatPane(VerticalScroll):
    """Scrollable container for chat messages."""

    DEFAULT_CSS = """
    ChatPane {
        height: 100%;
        width: 100%;
    }
    """

    # Map agent_name -> ChatMessage widget for the current streaming turn
    _active: dict[str, ChatMessage]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the chat pane.

        Args:
            **kwargs: Forwarded to VerticalScroll.
        """
        super().__init__(**kwargs)
        self.border_title = "Chat"
        # Compat attributes — ChatPane renders its own markup/styled content
        self.wrap: bool = True
        self.highlight: bool = True
        self.markup: bool = True

    def on_mount(self) -> None:
        """Initialize the active message map."""
        self._active = {}

    def _scroll_to_bottom(self) -> None:
        """Scroll to the latest message."""
        self.scroll_end(animate=False)
        if self.children:
            self.scroll_visible(self.children[-1])

    def add_user_message(self, text: str) -> None:
        """Append a user message block.

        Args:
            text: User input text.
        """
        msg = ChatMessage("[bold green]You:[/]", text)
        self.mount(msg)
        self._scroll_to_bottom()

    def add_system_message(self, text: str) -> None:
        """Append a dim system/info message.

        Args:
            text: Information text.
        """
        msg = ChatMessage("[dim]»[/]", text)
        self.mount(msg)
        self._scroll_to_bottom()

    def add_error_message(self, text: str) -> None:
        """Append a red error message.

        Args:
            text: Error text.
        """
        msg = ChatMessage("[bold red]Error:[/]", text)
        self.mount(msg)
        self._scroll_to_bottom()

    def begin_agent_stream(self, agent_name: str) -> ChatMessage:
        """Start a new streaming message for *agent_name*.

        Args:
            agent_name: Display name of the responding agent.

        Returns:
            The newly mounted ChatMessage widget.
        """
        widget = ChatMessage(f"[bold cyan]{agent_name}:[/]", "")
        self._active[agent_name] = widget
        self.mount(widget)
        self._scroll_to_bottom()
        return widget

    def append_agent_chunk(self, agent_name: str, chunk: str) -> None:
        """Append a streaming chunk to an active agent message.

        Creates a new stream widget if none exists for that agent.

        Args:
            agent_name: Agent whose message to extend.
            chunk: Text chunk to append.
        """
        if agent_name not in self._active:
            self.begin_agent_stream(agent_name)
        self._active[agent_name].append(chunk)
        self._scroll_to_bottom()

    def finish_agent_stream(self, agent_name: str) -> None:
        """Mark an agent's streaming message as complete.

        Args:
            agent_name: Agent whose stream ended.
        """
        self._active.pop(agent_name, None)

    def clear_thinking_messages(self) -> None:
        """Remove all ThinkingMessage widgets from the pane.
        
        This is used when clearing the thinking pane to also remove
        thinking messages that appear in the chat window.
        """
        # Find and remove all ThinkingMessage widgets
        thinking_widgets = [
            child for child in self.children
            if hasattr(child, '__class__') and child.__class__.__name__ == 'ThinkingMessage'
        ]
        for widget in thinking_widgets:
            widget.remove()

    def clear_messages(self) -> None:
        """Remove all messages from the pane."""
        self._active = {}
        self.remove_children()


# ---------------------------------------------------------------------------
# Other pane widgets
# ---------------------------------------------------------------------------


class ThinkingPane(RichLog):
    """Pane for agent reasoning/thinking output."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize.

        Args:
            **kwargs: Forwarded to RichLog.
        """
        super().__init__(wrap=True, highlight=True, markup=True, **kwargs)
        self.border_title = "Thinking (legacy)"


class ToolPane(RichLog):
    """Pane for tool call/result display."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize.

        Args:
            **kwargs: Forwarded to RichLog.
        """
        super().__init__(wrap=True, highlight=True, markup=True, **kwargs)
        self.border_title = "Tools"


class StatusBar(Static):
    """One-line status bar at the bottom of the screen."""

    status_text: reactive[str] = reactive("Ready")

    def __init__(self, **kwargs: Any) -> None:
        """Initialize.

        Args:
            **kwargs: Forwarded to Static.
        """
        super().__init__(**kwargs)
        self.border_title = "Status"

    def render(self) -> str:
        """Render the status bar.

        Returns:
            Formatted Rich markup string.
        """
        return f"[bold cyan]{self.status_text}[/]"


# ---------------------------------------------------------------------------
# TUI Console adapter — routes Rich output to the chat pane
# ---------------------------------------------------------------------------


class TuiConsoleAdapter:
    """Intercepts Rich Console output and forwards it to the Textual chat pane.

    This replaces the invisible stdout-backed console that the OutputHandler
    and UIRenderer write to, so that slash command output, errors, and status
    messages appear inside the TUI rather than behind it.
    """

    def __init__(self, app: HenchmanTextualApp) -> None:
        """Initialize.

        Args:
            app: The Textual application.
        """
        self._app = app
        self._buf = io.StringIO()
        # A Rich Console that writes to our StringIO buffer.
        # force_terminal=True ensures ANSI/markup is rendered by Rich into plain
        # text that we can then forward as Rich markup to RichLog.
        self._rich_console = RichConsole(
            file=self._buf,
            force_terminal=True,
            no_color=False,
            markup=True,
            highlight=True,
        )

    @property
    def console(self) -> RichConsole:
        """The underlying Rich Console wired to the string buffer.

        Returns:
            RichConsole instance.
        """
        return self._rich_console

    def flush_to_chat(self) -> None:
        """Read accumulated buffer and post it to the chat pane."""
        text = self._buf.getvalue()
        if text.strip():
            self._app.post_message(CommandOutputMessage(text.strip()))
        self._buf.seek(0)
        self._buf.truncate(0)

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Write to the buffer and immediately flush to chat.

        Args:
            *args: Positional args forwarded to Rich Console.print.
            **kwargs: Keyword args forwarded to Rich Console.print.
        """
        self._rich_console.print(*args, **kwargs)
        self.flush_to_chat()


# ---------------------------------------------------------------------------
# EventBridge
# ---------------------------------------------------------------------------


class EventBridge:
    """Forwards agent events to the Textual UI via post_message.

    All 20 EventType variants are handled here.
    """

    def __init__(self, app: HenchmanTextualApp) -> None:
        """Initialize.

        Args:
            app: The Textual application to target.
        """
        self.app = app
        self._handlers = self._create_handler_registry()

    def _post(self, message: Message) -> None:
        """Post a message to the Textual app.

        Args:
            message: The Textual message to post.
        """
        # @work coroutines run on the main event loop — direct post is safe.
        self.app.post_message(message)

    async def forward_events(self, event_stream: AsyncIterator[AgentEvent]) -> None:
        """Forward all events from *event_stream* to the Textual UI.

        Args:
            event_stream: Async iterator of AgentEvent objects.
        """
        try:
            async for event in event_stream:
                await self._handle_event(event)
        except Exception as exc:
            import traceback

            details = traceback.format_exc()
            self._post(AgentStatusMessage(f"Stream error: {exc}"))
            self._post(AgentContentMessage(f"❌ Stream error: {exc}\n```\n{details}\n```"))

    async def _handle_event(self, event: AgentEvent) -> None:
        """Dispatch a single AgentEvent to the appropriate Textual Message.

        Args:
            event: The event to dispatch.
        """
        handler = self._handlers.get(event.type)
        if handler:
            handler(event)  # Handlers are synchronous, don't await
        else:
            # Log unhandled event type for debugging
            self._post(
                AgentStatusMessage(f"Unhandled event type: {event.type}", event.source_agent)
            )

    def _create_handler_registry(self) -> dict[EventType, Callable[[AgentEvent], None]]:
        """Create a registry of event type to handler function mappings.

        Returns:
            Dictionary mapping EventType to handler functions.
        """
        return {
            EventType.CONTENT: self._handle_content,
            EventType.THOUGHT: self._handle_thought,
            EventType.TOOL_CALL_REQUEST: self._handle_tool_call_request,
            EventType.TOOL_CALL_RESULT: self._handle_tool_call_result,
            EventType.TOOL_CONFIRMATION: self._handle_tool_confirmation,
            EventType.ERROR: self._handle_error,
            EventType.FINISHED: self._handle_finished,
            EventType.CONTEXT_COMPACTED: self._handle_context_compacted,
            EventType.TURN_SUMMARIZED: self._handle_turn_summarized,
            EventType.TURN_STATUS: self._handle_turn_status,
            EventType.AGENT_STARTED: self._handle_agent_started,
            EventType.AGENT_COMPLETED: self._handle_agent_completed,
            EventType.AGENT_DELEGATED: self._handle_agent_delegated,
            EventType.AGENT_MESSAGE: self._handle_agent_message,
            EventType.THINKING_STARTED: self._handle_thinking_started,
            EventType.THINKING_COMPLETED: self._handle_thinking_completed,
            EventType.THINKING_REQUIRED: self._handle_thinking_required,
            EventType.DELEGATION_DECISION: self._handle_delegation_decision,
            EventType.REFLECTION: self._handle_reflection,
        }

    def _handle_content(self, event: AgentEvent) -> None:
        """Handle CONTENT events."""
        if event.data:
            self._post(AgentContentMessage(str(event.data), event.source_agent))

    def _handle_thought(self, event: AgentEvent) -> None:
        """Handle THOUGHT events."""
        if event.data:
            self._post(AgentThoughtMessage(str(event.data), event.source_agent))

    def _handle_tool_call_request(self, event: AgentEvent) -> None:
        """Handle TOOL_CALL_REQUEST events."""
        if event.data:
            self._post(ToolCallRequestMessage(event.data, event.source_agent))

    def _handle_tool_call_result(self, event: AgentEvent) -> None:
        """Handle TOOL_CALL_RESULT events."""
        if event.data:
            self._post(ToolCallResultMessage(event.data, event.source_agent))

    def _handle_tool_confirmation(self, event: AgentEvent) -> None:
        """Handle TOOL_CONFIRMATION events."""
        if event.data:
            self._post(ToolConfirmationMessage(event.data, event.source_agent))

    def _handle_error(self, event: AgentEvent) -> None:
        """Handle ERROR events."""
        if event.data:
            error_message = self._format_error_message(str(event.data))
            self._post(AgentStatusMessage(f"Error: {error_message}", event.source_agent))
            self._post(AgentContentMessage(f"❌ {error_message}", event.source_agent))

    def _handle_finished(self, event: AgentEvent) -> None:
        """Handle FINISHED events."""
        self._post(AgentFinishedMessage(event.source_agent))

    def _handle_context_compacted(self, event: AgentEvent) -> None:
        """Handle CONTEXT_COMPACTED events."""
        self._post(AgentStatusMessage("Context compacted to fit model limits", event.source_agent))
        self._post(CommandOutputMessage("[dim]ℹ Context window was compacted.[/dim]"))

    def _handle_turn_summarized(self, event: AgentEvent) -> None:
        """Handle TURN_SUMMARIZED events."""
        self._post(AgentStatusMessage("Previous turn summarized", event.source_agent))

    def _handle_turn_status(self, event: AgentEvent) -> None:
        """Handle TURN_STATUS events."""
        if event.data and isinstance(event.data, dict):
            status = self._format_turn_status(event.data)
            self._post(AgentStatusMessage(status, event.source_agent))

    def _handle_agent_started(self, event: AgentEvent) -> None:
        """Handle AGENT_STARTED events."""
        if event.data and isinstance(event.data, dict):
            name = event.data.get("agent", "unknown")
            self._post(AgentStatusMessage(f"⚙ {name} working…", event.source_agent))

    def _handle_agent_completed(self, event: AgentEvent) -> None:
        """Handle AGENT_COMPLETED events."""
        if event.data and isinstance(event.data, dict):
            name = event.data.get("agent", "unknown")
            summary = event.data.get("summary", "")
            message = self._format_agent_completed_message(name, summary)
            self._post(AgentStatusMessage(message, event.source_agent))

    def _handle_agent_delegated(self, event: AgentEvent) -> None:
        """Handle AGENT_DELEGATED events."""
        if event.data and isinstance(event.data, dict):
            from_agent = event.data.get("from", "?")
            to_agent = event.data.get("to", "?")
            reason = event.data.get("reason", "")
            text = self._format_delegation_message(from_agent, to_agent, reason)
            self._post(CommandOutputMessage(text))
            self._post(AgentStatusMessage(f"{from_agent} → {to_agent}", event.source_agent))

    def _handle_agent_message(self, event: AgentEvent) -> None:
        """Handle AGENT_MESSAGE events."""
        if event.data:
            self._post(CommandOutputMessage(f"[dim]📨 {event.data}[/dim]"))

    def _handle_thinking_started(self, event: AgentEvent) -> None:
        """Handle THINKING_STARTED events."""
        self._post(AgentStatusMessage("Thinking…", event.source_agent))

    def _handle_thinking_completed(self, event: AgentEvent) -> None:
        """Handle THINKING_COMPLETED events."""
        self._post(AgentStatusMessage("Thinking complete", event.source_agent))

    def _handle_thinking_required(self, event: AgentEvent) -> None:
        """Handle THINKING_REQUIRED events."""
        self._post(AgentStatusMessage("⚠ Thinking pattern missing in response", event.source_agent))

    def _handle_delegation_decision(self, event: AgentEvent) -> None:
        """Handle DELEGATION_DECISION events."""
        if event.data:
            self._post(
                AgentThoughtMessage(f"Delegation decision: {event.data}", event.source_agent)
            )

    def _handle_reflection(self, event: AgentEvent) -> None:
        """Handle REFLECTION events."""
        if event.data:
            self._post(AgentThoughtMessage(f"Reflection: {event.data}", event.source_agent))

    # Helper methods for formatting
    def _format_error_message(self, error_text: str) -> str:
        """Format error message, handling special cases like API errors.

        Args:
            error_text: Raw error text.

        Returns:
            Formatted error message.
        """
        if "API key" in error_text or "authentication" in error_text.lower():
            return "❌ API Error: Invalid or missing API key."
        return error_text

    def _format_turn_status(self, status_data: dict[str, Any]) -> str:
        """Format turn status message.

        Args:
            status_data: Dictionary with turn status information.

        Returns:
            Formatted status string.
        """
        iteration = status_data.get("iteration", "?")
        max_iter = status_data.get("max_iterations", "?")
        tokens = status_data.get("tokens")
        status = f"Turn {iteration}/{max_iter}"
        if tokens:
            status += f" | {tokens} tokens"
        return status

    def _format_agent_completed_message(self, agent_name: str, summary: str) -> str:
        """Format agent completed message.

        Args:
            agent_name: Name of the agent.
            summary: Summary of what was completed.

        Returns:
            Formatted completion message.
        """
        message = f"✓ {agent_name} completed"
        if summary:
            message += f": {summary}"
        return message

    def _format_delegation_message(self, from_agent: str, to_agent: str, reason: str) -> str:
        """Format delegation message.

        Args:
            from_agent: Name of delegating agent.
            to_agent: Name of receiving agent.
            reason: Reason for delegation.

        Returns:
            Formatted delegation message.
        """
        text = f"[dim]↳ Delegating: {from_agent} → {to_agent}"
        if reason:
            text += f" ({reason})"
        text += "[/dim]"
        return text


# ---------------------------------------------------------------------------
# Modal screens
# ---------------------------------------------------------------------------


class ConfirmToolScreen(ModalScreen[bool]):
    """Modal dialog for tool execution confirmation.

    Returns True if the user approves, False otherwise.
    """

    DEFAULT_CSS = """
    ConfirmToolScreen {
        align: center middle;
    }
    #confirm-dialog {
        padding: 2;
        border: solid $warning;
        background: $surface;
        width: 70;
        height: auto;
        max-height: 20;
    }
    #confirm-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #confirm-details {
        margin-bottom: 1;
        color: $text-muted;
    }
    #confirm-buttons {
        align: right middle;
        height: auto;
        margin-top: 1;
    }
    """

    BINDINGS = [
        ("y", "approve", "Yes"),
        ("n", "deny", "No"),
        ("escape", "deny", "No"),
    ]

    def __init__(self, request: ConfirmationRequest) -> None:
        """Initialize.

        Args:
            request: The tool confirmation request to show.
        """
        super().__init__()
        self._request = request

    def compose(self) -> ComposeResult:
        """Build the confirmation dialog.

        Returns:
            ComposeResult with the dialog layout.
        """
        from rich.markup import escape

        risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(
            self._request.risk_level, "yellow"
        )
        tool_name = escape(self._request.tool_name)
        description = escape(self._request.description)

        params_text = ""
        if self._request.params:
            try:
                params_text = json.dumps(self._request.params, indent=2)
            except Exception:
                params_text = str(self._request.params)

        yield Vertical(
            Label(
                f"[bold {risk_color}]⚠ Tool Approval Required[/]",
                id="confirm-title",
            ),
            Label(
                f"Tool [bold cyan]{tool_name}[/] wants to: {description}",
                id="confirm-details",
            ),
            *(
                [Label(f"[dim]Parameters:[/]\n[yellow]{escape(params_text)}[/]")]
                if params_text
                else []
            ),
            Label(f"[dim]Risk level: [{risk_color}]{self._request.risk_level}[/][/dim]"),
            Vertical(
                Button("Yes  (y)", variant="success", id="btn-yes"),
                Button("No   (n)", variant="error", id="btn-no"),
                id="confirm-buttons",
            ),
            id="confirm-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Dismiss the modal with the user's choice.

        Args:
            event: Button press event.
        """
        self.dismiss(event.button.id == "btn-yes")

    def action_approve(self) -> None:
        """Approve the tool call."""
        self.dismiss(True)

    def action_deny(self) -> None:
        """Deny the tool call."""
        self.dismiss(False)


class HelpScreen(ModalScreen[None]):
    """Keybinding / help modal."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 60;
        height: auto;
        align: center middle;
    }
    """
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def compose(self) -> ComposeResult:
        """Compose the help dialog.

        Returns:
            ComposeResult with help content.
        """
        yield Vertical(
            Label("[bold]Henchman-AI — Keybindings[/bold]"),
            Label(""),
            Label("[bold]Input[/bold]"),
            Label("  Enter          Submit message"),
            Label("  Shift+Enter    New line"),
            Label("  ↑ / ↓         Navigate history"),
            Label(""),
            Label("[bold]Search[/bold]"),
            Label("  Ctrl+F         Enter search mode"),
            Label("  F3             Next match"),
            Label("  Shift+F3       Previous match"),
            Label("  Escape         Exit search / close modal"),
            Label(""),
            Label("[bold]App[/bold]"),
            Label("  Ctrl+Q / Ctrl+C    Quit"),
            Label("  Ctrl+Shift+T       Clear thinking pane"),
            Label("  Ctrl+Shift+Y       Clear tool pane"),
            Label("  /               Slash command palette"),
            Label(""),
            Button("Close", variant="primary", id="close-help"),
            id="help-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Close the help screen.

        Args:
            event: Button press event.
        """
        if event.button.id == "close-help":
            self.app.pop_screen()


class ProviderScreen(ModalScreen[None]):
    """Provider selection modal."""

    DEFAULT_CSS = """
    ProviderScreen {
        align: center middle;
    }
    #provider-dialog {
        padding: 2;
        border: solid $accent;
        background: $surface;
        width: 60;
        height: auto;
    }
    #provider-select {
        margin: 1 0;
    }
    """
    BINDINGS = [("escape", "app.pop_screen", "Close")]

    def compose(self) -> ComposeResult:
        """Compose the provider dialog.

        Returns:
            ComposeResult with provider selection.
        """
        app: HenchmanTextualApp = self.app  # type: ignore[assignment]
        settings = app.settings

        options: list[tuple[str, str]] = []
        if settings and settings.providers:
            ps = settings.providers
            for name in ("deepseek", "anthropic", "ollama", "openai"):
                cfg = getattr(ps, name, None)
                if cfg and isinstance(cfg, dict) and cfg:
                    model = cfg.get("model", name)
                    options.append((f"{name} ({model})", name))

        if not options:
            options = [("No providers configured", "none")]

        current = settings.providers.default if settings and settings.providers else "unknown"
        current_in_options = any(v == current for _, v in options)

        select_widget = Select(
            options,
            id="provider-select",
            allow_blank=True,
            # Only pre-select if the current provider is actually in the options list.
            # Passing value=Select.BLANK (False) to the constructor crashes Textual 8.
            value=current if current_in_options else Select.NULL,
        )

        yield Vertical(
            Label("[bold]Switch Provider[/bold]"),
            Label(f"Current: [cyan]{current}[/cyan]"),
            select_widget,
            Vertical(
                Button("Switch", variant="success", id="btn-switch"),
                Button("Cancel", variant="default", id="btn-cancel"),
            ),
            id="provider-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press.

        Args:
            event: Button press event.
        """
        if event.button.id == "btn-cancel":
            self.app.pop_screen()
        elif event.button.id == "btn-switch":
            sel = self.query_one("#provider-select", Select)
            if sel.value and sel.value != Select.BLANK:
                self.app.post_message(SwitchProviderMessage(str(sel.value)))
            self.app.pop_screen()


class SwitchProviderMessage(Message):
    """Internal message to switch the provider."""

    def __init__(self, provider_name: str) -> None:
        """Initialize.

        Args:
            provider_name: Name of the provider to switch to.
        """
        super().__init__()
        self.provider_name = provider_name


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------


class HenchmanTextualApp(App):  # type: ignore[type-arg]
    """Main Textual TUI application for Henchman-AI."""

    CSS = """
    Screen {
        layout: vertical;
    }
    TabbedContent, TabPane {
        height: 1fr;
    }
    ChatPane, #chat-pane {
        height: 1fr;
        width: 100%;
        overflow-y: auto;
        scrollbar-gutter: stable;
    }
    #thinking-pane, #tool-pane {
        height: 1fr;
        width: 100%;
        overflow-y: auto;
    }
    ChatMessage {
        margin: 1 1 1 1;
        padding: 1;
    }
    #command-palette {
        width: 100%;
        height: auto;
        max-height: 12;
        dock: bottom;
        layer: overlay;
        display: none;
        border: solid $accent;
        background: $surface;
    }
    #input {
        width: 100%;
        height: 3;
        border: solid $panel;
        margin: 0 1;
    }
    #status-bar {
        height: 1;
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+shift+t", "clear_thinking_pane", "Clear Thinking", show=True),
        Binding("ctrl+shift+y", "clear_tool_pane", "Clear Tools", show=True),
        Binding("ctrl+f", "search", "Search", show=True),
        Binding("escape", "clear_search", "Clear Search", show=False),
        Binding("f3", "search_next", "Next Match", show=False),
        Binding("shift+f3", "search_previous", "Prev Match", show=False),
        Binding("ctrl+enter", "submit_message", "Submit", show=True),
        Binding("f1", "show_help", "Help", show=True),
        Binding("f2", "switch_provider", "Provider", show=True),
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
            provider: Model provider.  Resolved from environment if omitted.
            config: TUI configuration.
            settings: Application settings.
            environment_context: Pre-formatted environment context block.
        """
        super().__init__()

        if provider is None:
            from henchman.cli.app import _get_provider
            from henchman.config import load_settings
            from henchman.config.environment import format_environment_block, gather_environment

            try:
                self.provider = _get_provider()
            except Exception as exc:
                from henchman.providers.deepseek import DeepSeekProvider

                self.provider = DeepSeekProvider(api_key="mock-key-for-ui-testing")
                import warnings

                warnings.warn(
                    f"Failed to initialize provider from environment: {exc}. "
                    "Using mock provider for UI testing only.",
                    RuntimeWarning,
                    stacklevel=1,
                )
            self.settings = load_settings()
            self.config = TextualConfig()
            self.environment_context = format_environment_block(gather_environment())
        else:
            self.provider = provider
            self.config = config or TextualConfig()
            self.settings = settings  # type: ignore[assignment]
            self.environment_context = environment_context  # type: ignore[assignment]

        # Core context — populated in on_mount
        self.core_context: CoreContext | None = None
        self.tool_executor: ToolExecutor | None = None
        self.command_processor: CommandProcessor | None = None
        self.input_handler: InputHandler | None = None
        self.output_handler: OutputHandler | None = None
        self._tui_adapter: TuiConsoleAdapter | None = None

        # UI state
        self.is_processing: bool = False

        # Streaming: agent_name -> ChatMessage widget
        self._streaming_messages: dict[str, ChatMessage] = {}

        # Search state
        self._search_mode: bool = False
        self._search_query: str = ""
        # list of (pane_id, line_index, match_text) tuples
        self._search_matches: list[tuple[str, int, str]] = []
        self._current_match_index: int = -1

        # History
        self.command_history: list[str] = []
        self.history_index: int = -1

        # Pending confirmation futures  {request_id -> asyncio.Future[bool]}
        self._confirm_futures: dict[int, asyncio.Future[bool]] = {}
        self._confirm_counter: int = 0

        # Proxy attributes for CommandContext compatibility
        self._orchestrator_proxy: Any = None
        self._tool_registry_proxy: Any = None
        self._session_manager_proxy: Any = None

    # ---- proxy properties for CommandContext compatibility ----

    @property
    def orchestrator(self) -> Any:
        """Proxy to core_context.orchestrator.

        Returns:
            Orchestrator or None.
        """
        return self.core_context.orchestrator if self.core_context else None

    @orchestrator.setter
    def orchestrator(self, value: Any) -> None:
        """No-op setter; managed by core_context.

        Args:
            value: Ignored.
        """

    @property
    def tool_registry(self) -> Any:
        """Proxy to core_context.tool_registry.

        Returns:
            ToolRegistry or None.
        """
        return self.core_context.tool_registry if self.core_context else None

    @tool_registry.setter
    def tool_registry(self, value: Any) -> None:
        """No-op setter; managed by core_context.

        Args:
            value: Ignored.
        """

    @property
    def session_manager(self) -> Any:
        """Proxy to core_context.session_manager.

        Returns:
            ReplSessionManager or None.
        """
        return self.core_context.session_manager if self.core_context else None

    @session_manager.setter
    def session_manager(self, value: Any) -> None:
        """No-op setter; managed by core_context.

        Args:
            value: Ignored.
        """

    @property
    def agent(self) -> Any:
        """Proxy to core_context.agent.

        Returns:
            Agent or None.
        """
        return self.core_context.agent if self.core_context else None

    @agent.setter
    def agent(self, value: Any) -> None:
        """No-op setter; managed by core_context.

        Args:
            value: Ignored.
        """

    @property
    def rag_system(self) -> None:
        """RAG system (not yet implemented).

        Returns:
            None always.
        """
        return None

    @property
    def renderer(self) -> UIRenderer | None:
        """UIRenderer instance (backward compatibility).

        Returns:
            UIRenderer or None.
        """
        return getattr(self, "_ui_renderer", None)

    @property
    def current_input(self) -> str:
        """Current text in the input widget (backward compatibility).

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
        """Initialize core components after the DOM is available."""
        self._initialize_core_components()
        from henchman import __version__

        self.sub_title = f"Henchman-AI v{__version__} — {self.provider.name}"
        self._populate_context_tree()
        self._show_welcome()
        input_widget = self.query_one("#input", TextArea)
        input_widget.focus()
        self._load_history()
        self.call_after_refresh(lambda: input_widget.focus())

        # Force Chat tab
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = "tab-chat"
        except Exception:
            pass

    # ---- initialization helpers ----

    def _initialize_core_components(self) -> None:
        """Initialize core Henchman components shared with the REPL."""
        # Create component configuration
        component_config = ComponentConfig(
            provider=self.provider,
            config=self.config,
            settings=self.settings,
            environment_context=self.environment_context,
            app=self,
        )

        # Initialize all components using the ComponentInitializer
        initializer = ComponentInitializer(component_config)
        initializer.initialize_all()

        # Transfer initialized components to app instance
        self.core_context = initializer.core_context
        self.tool_executor = initializer.tool_executor
        self.command_processor = initializer.command_processor
        self.input_handler = initializer.input_handler
        self.output_handler = initializer.output_handler
        self._tui_adapter = initializer._tui_adapter
        self._ui_renderer = initializer._ui_renderer

        # Replace confirmation handler with Textual-native modal
        if self.core_context:
            self.core_context.tool_manager.set_confirmation_handler(self._textual_confirm)

        self._update_status_bar()

    async def _textual_confirm(self, request: ConfirmationRequest) -> bool:
        """Native Textual confirmation handler that shows a modal dialog.

        Args:
            request: The tool confirmation request.

        Returns:
            True if the user approves, False otherwise.
        """
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        req_id = self._confirm_counter
        self._confirm_counter += 1
        self._confirm_futures[req_id] = future

        def callback(result: bool | None) -> None:
            """Handle confirmation dialog result and resolve the future.

            Args:
                result: The user's confirmation choice, or None if dismissed.
            """
            if not future.done():
                future.set_result(bool(result))
            self._confirm_futures.pop(req_id, None)

        await self.push_screen(ConfirmToolScreen(request), callback)
        return await future

    def _update_status_bar(self) -> None:
        """Refresh the status bar with provider / tool / MCP info."""
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
        except Exception:
            return

        provider_name = self.provider.name if self.provider else "?"
        model_name = getattr(self.provider, "model", "?")
        tool_count = (
            len(self.core_context.tool_registry.list_tools())
            if self.core_context and self.core_context.tool_registry
            else 0
        )
        mcp_status = ""
        if self.core_context and self.core_context.mcp_manager:
            connected = len(
                [
                    c
                    for c in self.core_context.mcp_manager.clients.values()
                    if getattr(c, "_connected", False)
                ]
            )
            total = len(self.core_context.mcp_manager.clients)
            mcp_status = f" | MCP {connected}/{total}"
        mode = "Plan" if (self.settings and getattr(self.settings, "plan_mode", False)) else "Chat"
        status_bar.status_text = (
            f"{mode} | {provider_name}:{model_name} | Tools: {tool_count}{mcp_status}"
        )

    def _show_welcome(self) -> None:
        """Display a welcome banner in the chat pane."""
        try:
            chat = self.query_one("#chat-pane", ChatPane)
        except Exception:
            return
        provider_name = self.provider.name if self.provider else "unknown"
        model_name = getattr(self.provider, "model", "unknown")
        tool_count = (
            len(self.core_context.tool_registry.list_tools())
            if self.core_context and self.core_context.tool_registry
            else 0
        )
        mcp_info = ""
        if self.core_context and self.core_context.mcp_manager:
            total = len(self.core_context.mcp_manager.clients)
            if total:
                mcp_info = f" | {total} MCP server(s)"
        context_info = ""
        if self.config.system_prompt:
            context_info = " | Context loaded"
        chat.add_system_message(
            f"[bold]Henchman-AI[/bold] | {provider_name}:{model_name}"
            f" | {tool_count} tools{mcp_info}{context_info}"
        )
        chat.add_system_message("Type /help for commands. Press F1 for keybindings.")

    def _load_history(self) -> None:
        """Load command history from the history file."""
        if not self.input_handler:
            return
        hf: Path = getattr(self.input_handler, "history_file", Path.home() / ".henchman_history")
        if hf.exists():
            try:
                lines = hf.read_text().splitlines()
                self.command_history = [line for line in lines if line.strip()]
                self.history_index = len(self.command_history)
            except Exception:
                pass

    def _populate_context_tree(self) -> None:
        """Populate the Context tab tree with discovered context files."""
        try:
            tree = self.query_one("#context-tree", Tree)
        except Exception:
            return
        try:
            from henchman.config.context import ContextLoader

            loader = ContextLoader()
            files = loader.discover_files()
            if not files:
                tree.root.add_leaf("No context files found")
                return
            # Group by directory
            by_dir: dict[Path, list[Path]] = {}
            for f in files:
                by_dir.setdefault(f.parent, []).append(f)
            for directory, dir_files in by_dir.items():
                branch = tree.root.add(str(directory), expand=True)
                for path in dir_files:
                    branch.add_leaf(path.name, data=path)
            tree.root.expand()
        except Exception as exc:
            import contextlib

            with contextlib.suppress(Exception):
                tree.root.add_leaf(f"Error loading context: {exc}")

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

        if self.input_handler:
            hf: Path = getattr(
                self.input_handler, "history_file", Path.home() / ".henchman_history"
            )
            try:
                with open(hf, "a") as fh:
                    fh.write(user_input + "\n")
            except Exception:
                pass

        # Clear input using load_text (proper API for replacing all text)
        input_widget.load_text("")
        self.process_user_input(user_input)

    def _navigate_history(self, direction: int) -> None:
        """Navigate command history.

        Args:
            direction: -1 for older, +1 for newer.
        """
        if not self.command_history:
            return
        new_index = self.history_index + direction
        input_widget = self.query_one("#input", TextArea)
        if 0 <= new_index < len(self.command_history):
            self.history_index = new_index
            new_text = self.command_history[self.history_index]
            input_widget.load_text(new_text)
            # Move cursor to end of line
            input_widget.cursor_location = (0, len(new_text))
        elif new_index >= len(self.command_history):
            self.history_index = len(self.command_history)
            input_widget.load_text("")

    @work(exclusive=True)
    async def process_user_input(self, user_input: str) -> None:
        """Process user input: commands routed to CommandProcessor; other text to Orchestrator.

        Args:
            user_input: Raw text the user submitted.
        """
        self.is_processing = True
        status_bar = self.query_one("#status-bar", StatusBar)
        chat_pane = self.query_one("#chat-pane", ChatPane)
        status_bar.status_text = "Processing…"
        chat_pane.add_user_message(user_input)

        try:
            if not self.input_handler:
                chat_pane.add_error_message("Input handler not initialized.")
                return

            processed_input, is_command, should_continue = await self.input_handler.process_input(
                user_input
            )
            if not should_continue or not processed_input:
                return

            expanded_input = await expand_at_references(processed_input)

            if self.core_context and self.core_context.session_manager:
                self.core_context.session_manager.record_user_message(expanded_input)

            if is_command:
                # TUI-native /clear: clear the chat pane instead of writing ANSI escapes
                if expanded_input.strip().lower() == "/clear":
                    chat_pane.clear_messages()
                    return

                if self.command_processor:
                    should_continue = await self.command_processor.handle_command(
                        expanded_input,
                        self.core_context.agent if self.core_context else None,  # type: ignore[arg-type]
                        self,  # type: ignore[arg-type]
                    )
                    # Flush any output the command wrote to the console adapter
                    if self._tui_adapter:
                        self._tui_adapter.flush_to_chat()
                    if not should_continue:
                        self.exit()
            else:
                if self.core_context and self.core_context.orchestrator:
                    event_bridge = EventBridge(self)
                    event_stream = self.core_context.orchestrator.run(expanded_input)
                    await event_bridge.forward_events(event_stream)
                else:
                    chat_pane.add_error_message("Core components not initialized.")

        except Exception as exc:
            import traceback

            details = traceback.format_exc()
            chat_pane.add_error_message(f"{exc}\n```\n{details}\n```")
            status_bar.status_text = f"Error: {exc}"
        finally:
            self.is_processing = False
            self._update_status_bar()

    # ---- message handlers ----

    def on_agent_content_message(self, message: AgentContentMessage) -> None:
        """Stream text content into the chat pane.

        Args:
            message: Content chunk from an agent.
        """
        chat_pane = self.query_one("#chat-pane", ChatPane)
        agent_name = message.source_agent or "Assistant"
        chat_pane.append_agent_chunk(agent_name, message.content)

    def on_agent_thought_message(self, message: AgentThoughtMessage) -> None:
        """Write thinking content to the thinking pane.

        Args:
            message: Thought from an agent.
        """
        thinking_pane = self.query_one("#thinking-pane", ThinkingPane)
        thinking_pane.write(f"[dim]{message.thought}[/]")
        thinking_pane.scroll_end(animate=False)

    def on_tool_call_request_message(self, message: ToolCallRequestMessage) -> None:
        """Write a tool call request to the tools pane.

        Args:
            message: Tool call request data.
        """
        tool_pane = self.query_one("#tool-pane", ToolPane)
        tc = message.tool_call
        args_str = ""
        if tc.arguments:
            try:
                args_str = json.dumps(
                    json.loads(tc.arguments) if isinstance(tc.arguments, str) else tc.arguments,
                    indent=2,
                )
            except Exception:
                args_str = str(tc.arguments)
        tool_pane.write(f"[yellow]▶ {tc.name}[/]\n[dim]{args_str}[/]")
        tool_pane.scroll_end(animate=False)

    def on_tool_call_result_message(self, message: ToolCallResultMessage) -> None:
        """Write a tool result to the tools pane.

        Args:
            message: Tool execution result.
        """
        tool_pane = self.query_one("#tool-pane", ToolPane)
        result = message.result
        if isinstance(result, dict):
            content = str(result.get("result", result))
            success = result.get("success", True)
            display = content[:200] + ("…" if len(content) > 200 else "")
            color = "green" if success else "red"
            label = "✓" if success else "✗"
            tool_pane.write(f"[{color}]{label} {display}[/]")
        else:
            display = str(result)[:200]
            tool_pane.write(f"[green]✓ {display}[/]")
        tool_pane.scroll_end(animate=False)

    def on_tool_confirmation_message(self, message: ToolConfirmationMessage) -> None:
        """Handle TOOL_CONFIRMATION events by showing the confirm modal.

        In most cases the confirmation is handled via _textual_confirm (which the
        ToolManager calls directly).  This handler exists as a fallback for events
        that arrive through the EventBridge stream.

        Args:
            message: Confirmation request message.
        """
        # The ToolManager's confirmation handler already pushed the modal; nothing to do.
        pass

    def on_agent_status_message(self, message: AgentStatusMessage) -> None:
        """Update the status bar with an agent status string.

        Args:
            message: Status update from an agent.
        """
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            status_bar.status_text = message.status
        except Exception:
            pass

    def on_agent_finished_message(self, message: AgentFinishedMessage) -> None:
        """Handle agent completion: finish streaming, update status.

        Args:
            message: Finished signal from an agent.
        """
        chat_pane = self.query_one("#chat-pane", ChatPane)
        agent_name = message.source_agent or "Assistant"
        chat_pane.finish_agent_stream(agent_name)
        self._streaming_messages.pop(agent_name, None)
        self._update_status_bar()

    def on_command_output_message(self, message: CommandOutputMessage) -> None:
        """Route command/system output to the chat pane.

        Args:
            message: Output text from a slash command or system event.
        """
        try:
            chat_pane = self.query_one("#chat-pane", ChatPane)
            chat_pane.add_system_message(message.text)
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

        Preserves session history and conversation context while switching the LLM provider.

        Args:
            provider_name: Name key of the provider to activate.
        """
        try:
            from henchman.providers import get_default_registry

            registry = get_default_registry()
            new_provider = registry.create(provider_name)
            old_provider_name = self.provider.name if self.provider else "unknown"
            self.provider = new_provider

            # Reinitialize core components but preserve session state
            self._initialize_core_components()

            # Update title with version
            from henchman import __version__

            self.sub_title = f"Henchman-AI v{__version__} — {self.provider.name}"

            chat_pane = self.query_one("#chat-pane", ChatPane)
            chat_pane.add_system_message(
                f"Provider switched: [cyan]{old_provider_name}[/] → [cyan]{provider_name}[/]"
            )

            # Update status bar
            self._update_status_bar()
        except Exception as exc:
            chat_pane = self.query_one("#chat-pane", ChatPane)
            chat_pane.add_error_message(f"Failed to switch provider: {exc}")

    # ---- command palette ----

    @on(TextArea.Changed)
    def on_textarea_changed(self, event: TextArea.Changed) -> None:
        """Show/hide the command palette on slash-prefix input.

        Args:
            event: TextArea change event.
        """
        text = event.control.text
        if text.startswith("/"):
            self._show_command_palette(text)
        else:
            self._hide_command_palette()

    def _show_command_palette(self, current_text: str) -> None:
        """Populate and display the command palette filtered by current input.

        Args:
            current_text: Current text in the input widget (starts with /).
        """
        palette = self.query_one("#command-palette", OptionList)
        palette.display = True

        palette.clear_options()

        query = current_text.lower()
        if self.command_processor:
            commands = self.command_processor.command_registry.get_commands()
        else:
            commands = []

        for cmd in commands:
            display = f"/{cmd.name}  — {cmd.description}"
            if f"/{cmd.name}".startswith(query) or query == "/":
                palette.add_option(display)

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
        # The option prompt may be "/<cmd>  — description"; extract just /<cmd>
        raw = str(event.option.prompt)
        cmd_part = raw.split("  —")[0].strip()
        input_widget = self.query_one("#input", TextArea)
        # Use the proper API to set text and trigger change events
        new_text = cmd_part + " "
        input_widget.load_text(new_text)
        # Move cursor to end of input
        input_widget.cursor_location = (0, len(new_text))
        input_widget.focus()
        self._hide_command_palette()

    # ---- search ----

    def action_search(self) -> None:
        """Enter search mode or find next match if already searching."""
        if self._search_mode:
            self.action_search_next()
            return
        self._search_mode = True
        status_bar = self.query_one("#status-bar", StatusBar)
        status_bar.status_text = "Search: type in input box then press F3"

    def action_clear_search(self) -> None:
        """Exit search mode and restore normal status bar."""
        if not self._search_mode:
            return
        self._search_mode = False
        self._search_query = ""
        self._search_matches = []
        self._current_match_index = -1
        self._update_status_bar()

    def action_search_next(self) -> None:
        """Move to the next search match."""
        if not self._search_mode:
            return
        # Trigger a search if query changed
        input_widget = self.query_one("#input", TextArea)
        query = input_widget.text.strip()
        if query != self._search_query:
            self._perform_search(query)
        if not self._search_matches:
            return
        self._current_match_index = (self._current_match_index + 1) % len(self._search_matches)
        self._scroll_to_match()
        self._update_search_status()

    def action_search_previous(self) -> None:
        """Move to the previous search match."""
        if not self._search_mode:
            return
        input_widget = self.query_one("#input", TextArea)
        query = input_widget.text.strip()
        if query != self._search_query:
            self._perform_search(query)
        if not self._search_matches:
            return
        self._current_match_index = (self._current_match_index - 1) % len(self._search_matches)
        self._scroll_to_match()
        self._update_search_status()

    def _perform_search(self, query: str) -> None:
        """Index text matches in all visible pane content.

        Args:
            query: Search string (case-insensitive).
        """
        self._search_query = query
        self._search_matches = []
        self._current_match_index = -1

        if not query:
            self._update_search_status()
            return

        ql = query.lower()

        # Search the chat pane children (ChatMessage widgets)
        try:
            chat_pane = self.query_one("#chat-pane", ChatPane)
            for idx, widget in enumerate(chat_pane.children):
                if isinstance(widget, ChatMessage):
                    full_text = widget._content.lower()
                    if ql in full_text:
                        self._search_matches.append(("chat", idx, widget._content))
        except Exception:
            pass

        # Search the thinking pane (RichLog lines)
        try:
            thinking_pane = self.query_one("#thinking-pane", ThinkingPane)
            self._search_richlog(thinking_pane, "thinking", ql)
        except Exception:
            pass

        # Search the tool pane (RichLog lines)
        try:
            tool_pane = self.query_one("#tool-pane", ToolPane)
            self._search_richlog(tool_pane, "tool", ql)
        except Exception:
            pass

        self._update_search_status()

    def _search_richlog(self, pane: RichLog, pane_id: str, query_lower: str) -> None:
        """Collect matches from a RichLog widget.

        Handles different Textual versions' RichLog.lines API.

        Args:
            pane: The RichLog widget to search.
            pane_id: Identifier string for the pane ("thinking", "tool").
            query_lower: Lowercase search query.
        """
        try:
            # Try to get line content - handle different Textual versions
            lines = getattr(pane, "lines", [])
            if not lines:
                return

            for idx, item in enumerate(lines):
                # Handle different representations across Textual versions
                # Option 1: Has .text attribute (Textual 8 Strip)
                # Option 2: Has __iter__ (Segment iterable)
                # Option 3: Is a string directly
                text = ""
                if hasattr(item, "text"):
                    text = str(item.text)
                elif isinstance(item, str):
                    text = item
                else:
                    # Try to iterate as segments
                    try:
                        text = "".join(
                            str(seg.text) if hasattr(seg, "text") else str(seg)
                            for seg in item
                        )
                    except (TypeError, AttributeError):
                        text = str(item)

                if query_lower in text.lower():
                    self._search_matches.append((pane_id, idx, text))
        except Exception:
            pass

    def _scroll_to_match(self) -> None:
        """Scroll the relevant pane to the current match."""
        if not self._search_matches or self._current_match_index < 0:
            return
        pane_id, line_idx, _ = self._search_matches[self._current_match_index]
        try:
            if pane_id == "chat":
                chat_pane = self.query_one("#chat-pane", ChatPane)
                children = list(chat_pane.children)
                if 0 <= line_idx < len(children):
                    children[line_idx].scroll_visible(animate=False)
            elif pane_id == "thinking":
                pane = self.query_one("#thinking-pane", ThinkingPane)
                # Estimate line height as total height divided by line count
                line_height = max(1, pane.size.height // max(1, len(pane.lines)))
                pane.scroll_to(y=line_idx * line_height, animate=False)
            elif pane_id == "tool":
                tool_pane = self.query_one("#tool-pane", ToolPane)
                # Estimate line height as total height divided by line count
                line_height = max(1, tool_pane.size.height // max(1, len(tool_pane.lines)))
                tool_pane.scroll_to(y=line_idx * line_height, animate=False)
        except Exception:
            pass

    def _update_search_status(self) -> None:
        """Refresh the status bar with search result information."""
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
        except Exception:
            return
        if not self._search_mode:
            return
        if not self._search_query:
            status_bar.status_text = "Search: type query in input box, F3=next"
        elif not self._search_matches:
            status_bar.status_text = f"No matches for '{self._search_query}'"
        else:
            cur = self._current_match_index + 1
            tot = len(self._search_matches)
            status_bar.status_text = (
                f"Match {cur}/{tot} for '{self._search_query}' — F3=next  Shift+F3=prev  Esc=clear"
            )

    # ---- pane actions ----

    def action_clear_thinking_pane(self) -> None:
        """Clear all content from the thinking pane and thinking messages in chat."""
        self.query_one("#thinking-pane", ThinkingPane).clear()
        self.query_one("#chat-pane", ChatPane).clear_thinking_messages()
        self.query_one("#status-bar", StatusBar).status_text = "Thinking cleared (legacy pane and chat messages)"

    def action_clear_tool_pane(self) -> None:
        """Clear all content from the tool pane."""
        self.query_one("#tool-pane", ToolPane).clear()
        self.query_one("#status-bar", StatusBar).status_text = "Tool pane cleared"

    def action_toggle_thinking_pane(self) -> None:
        """Switch to (or away from) the thinking tab — backward compat."""
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = "tab-chat" if tabs.active == "tab-thinking" else "tab-thinking"
        except Exception:
            pass

    def action_toggle_tool_pane(self) -> None:
        """Switch to (or away from) the tools tab — backward compat."""
        try:
            tabs = self.query_one(TabbedContent)
            tabs.active = "tab-chat" if tabs.active == "tab-tools" else "tab-tools"
        except Exception:
            pass

    # ---- modal actions ----

    def action_show_help(self) -> None:
        """Show the help/keybinding modal."""
        self.push_screen(HelpScreen())

    def action_switch_provider(self) -> None:
        """Show the provider switching modal."""
        self.push_screen(ProviderScreen())

    # ---- context tree interaction ----

    def on_tree_node_selected(self, event: Tree.NodeSelected[object]) -> None:
        """Show file content when a context file tree node is clicked.

        Args:
            event: Tree node selection event.
        """
        node = event.node
        path: Path | None = node.data  # type: ignore[assignment]
        if path and isinstance(path, Path) and path.is_file():
            try:
                full_content = path.read_text()
                content = full_content[:2000]
                if len(full_content) > 2000:
                    content += "\n… (truncated)"
                chat_pane = self.query_one("#chat-pane", ChatPane)
                chat_pane.add_system_message(f"[bold]{path.name}[/bold]\n{content}")
            except Exception as exc:
                chat_pane = self.query_one("#chat-pane", ChatPane)
                chat_pane.add_error_message(f"Cannot read {path}: {exc}")

    # ---- misc public helpers ----

    def set_session(self, session: Session) -> None:
        """Activate a loaded session.

        Args:
            session: Session to activate.
        """
        if self.core_context and self.core_context.session_manager:
            self.core_context.session_manager.set_session(
                session,
                self.core_context.orchestrator if self.core_context else None,
            )

    def update_status(
        self, message: str, tokens: int | None = None, cost: float | None = None
    ) -> None:
        """Update the status bar.

        Args:
            message: Status message.
            tokens: Optional token count.
            cost: Optional cost in USD.
        """
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
            text = message
            if tokens is not None:
                text += f" | {tokens} tokens"
            if cost is not None:
                text += f" | ${cost:.4f}"
            status_bar.status_text = text
        except Exception:
            pass

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat pane (used by plugins/commands).

        Args:
            role: Sender role ('user', 'assistant', 'system').
            content: Message content.
        """
        try:
            chat_pane = self.query_one("#chat-pane", ChatPane)
            if role == "user":
                chat_pane.add_user_message(content)
            elif role in ("assistant", "system"):
                chat_pane.add_system_message(content)
            else:
                chat_pane.add_system_message(f"[{role}] {content}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


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
