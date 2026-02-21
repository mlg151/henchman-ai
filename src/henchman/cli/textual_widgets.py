"""Reusable Textual widgets for the Henchman-AI TUI.

Includes the chat pane, custom text input, message display widgets,
and the status bar.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

from typing import Any

from rich.markup import escape as markup_escape
from textual import events
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widgets import RichLog, Static, TextArea

# ------------------------------------------------------------------ #
# Constants                                                            #
# ------------------------------------------------------------------ #

# Rich markup prefixes for message roles
_USER_PREFIX = "[bold green]You:[/]"
_SYSTEM_PREFIX = "[dim]»[/]"
_ERROR_PREFIX = "[bold red]Error:[/]"
_AGENT_PREFIX_TEMPLATE = "[bold cyan]{name}:[/]"


# ------------------------------------------------------------------ #
# Custom input widget                                                  #
# ------------------------------------------------------------------ #


class HenchmanTextArea(TextArea):
    """Custom TextArea with Enter/Shift-Enter and history navigation."""

    BINDINGS = [
        Binding("ctrl+f", "app.search", "Search", show=False),
        Binding(
            "enter",
            "app.action_submit_message",
            "Submit Message",
            show=False,
        ),
        Binding("shift+enter", "newline", "Newline", show=False),
        Binding(
            "escape",
            "app.clear_search",
            "Clear Search",
            show=False,
        ),
        Binding("up", "history_up", "History Up", show=False),
        Binding(
            "down",
            "history_down",
            "History Down",
            show=False,
        ),
    ]

    async def on_key(self, event: events.Key) -> None:
        """Handle key events for submit and newline.

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

    def action_newline(self) -> None:
        """Insert a newline character."""
        self.insert("\n")

    def action_history_up(self) -> None:
        """Move up in history when cursor is at the first row."""
        if self.cursor_location[0] == 0:
            self.app._navigate_history(-1)  # type: ignore[attr-defined]
        else:
            self.action_cursor_up()

    def action_history_down(self) -> None:
        """Move down in history when cursor is at the last row."""
        last_row = self.document.line_count - 1
        if self.cursor_location[0] >= last_row:
            self.app._navigate_history(1)  # type: ignore[attr-defined]
        else:
            self.action_cursor_down()


# ------------------------------------------------------------------ #
# Chat message widgets                                                 #
# ------------------------------------------------------------------ #


class ChatMessage(Static):
    """A rendered chat message that supports live-update during streaming.

    Content is stored as raw markdown and the widget re-renders on
    every update so streaming text flows naturally.
    """

    DEFAULT_CSS = """
    ChatMessage {
        padding: 0 1;
        margin: 0 0 1 0;
    }
    """

    def __init__(
        self,
        prefix: str,
        content: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize.

        Args:
            prefix: Rich-markup prefix (e.g. ``[bold cyan]Asst:[/]``).
            content: Initial content (may be empty for streaming).
            **kwargs: Extra kwargs forwarded to ``Static``.
        """
        super().__init__("", **kwargs)
        self._prefix = prefix
        self._content = content
        self._update_renderable()

    def _update_renderable(self) -> None:
        """Re-render the static widget with current content."""
        self.update(f"{self._prefix} {markup_escape(self._content)}")

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
    """Display for agent thinking content in chat pane."""

    DEFAULT_CSS = """
    ThinkingMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        color: $text-muted;
    }
    ThinkingMessage > .thinking-content {
        color: $text-muted;
    }
    """

    def __init__(
        self,
        thought: str = "",
        agent_name: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize.

        Args:
            thought: The thinking content.
            agent_name: Name of the thinking agent.
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self.add_class("thinking-message")
        self._agent_name = agent_name
        self._content = thought
        self._update_renderable()

    def _update_renderable(self) -> None:
        """Re-render the static widget with current content."""
        prefix = f"🤔 {self._agent_name}: " if self._agent_name else "🤔 "
        # Format as paragraph, not line-by-line
        formatted_content = self._content.replace("\n", " ").strip()
        self.update(f"{prefix}{markup_escape(formatted_content)}")

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


class ToolMessage(Static):
    """Display for tool call/result content in chat pane."""

    DEFAULT_CSS = """
    ToolMessage {
        padding: 0 1;
        margin: 0 0 1 0;
        color: $warning;
    }
    ToolMessage > .tool-content {
        color: $warning;
    }
    """

    def __init__(
        self,
        thought: str = "",
        tool_call: Any = None,
        **kwargs: Any,
    ) -> None:
        """Initialize.

        Args:
            thought: Tool thought/description.
            tool_call: Tool call object.
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self.add_class("tool-message")
        self._thought = thought
        self._tool_call = tool_call
        self._content = thought
        self._update_renderable()

    def _update_renderable(self) -> None:
        """Re-render the static widget with current content."""
        prefix = "🛠️ "
        content = self._content if self._content else "Tool call"
        self.update(f"{prefix}{markup_escape(content)}")

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


# ------------------------------------------------------------------ #
# Chat pane                                                            #
# ------------------------------------------------------------------ #


class ChatPane(VerticalScroll):
    """Scrollable container for chat messages."""

    DEFAULT_CSS = """
    ChatPane {
        height: 100%;
        width: 100%;
    }
    """

    _active: dict[str, ChatMessage]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the chat pane.

        Args:
            **kwargs: Forwarded to ``VerticalScroll``.
        """
        super().__init__(**kwargs)
        self.border_title = "Chat"
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
            self.children[-1].scroll_visible(animate=False)

    # -- public API for adding messages --

    def add_user_message(self, text: str) -> None:
        """Append a user message block.

        Args:
            text: User input text.
        """
        msg = ChatMessage(_USER_PREFIX, text)
        self.mount(msg)
        self._scroll_to_bottom()

    def add_system_message(self, text: str) -> None:
        """Append a dim system/info message.

        Args:
            text: Information text.
        """
        msg = ChatMessage(_SYSTEM_PREFIX, text)
        self.mount(msg)
        self._scroll_to_bottom()

    def add_error_message(self, text: str) -> None:
        """Append a red error message.

        Args:
            text: Error text.
        """
        msg = ChatMessage(_ERROR_PREFIX, text)
        self.mount(msg)
        self._scroll_to_bottom()

    def begin_agent_stream(self, agent_name: str) -> ChatMessage:
        """Start a new streaming message for *agent_name*.

        Args:
            agent_name: Display name of the responding agent.

        Returns:
            The newly mounted ChatMessage widget.
        """
        prefix = _AGENT_PREFIX_TEMPLATE.format(name=agent_name)
        widget = ChatMessage(prefix, "")
        self._active[agent_name] = widget
        self.mount(widget)
        self._scroll_to_bottom()
        return widget

    def append_agent_chunk(self, agent_name: str, chunk: str) -> None:
        """Append a streaming chunk to an active agent message.

        Creates a new stream widget if none exists yet.

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

    def add_thinking_message(self, thought: str, agent_name: str = "") -> ThinkingMessage:
        """Add a thinking message to the chat pane.

        Args:
            thought: The thinking content.
            agent_name: Name of the thinking agent.

        Returns:
            The created ThinkingMessage widget.
        """
        widget = ThinkingMessage(thought, agent_name)
        self.mount(widget)
        self._scroll_to_bottom()
        return widget

    def add_tool_message(self, thought: str = "", tool_call: Any = None) -> ToolMessage:
        """Add a tool message to the chat pane.

        Args:
            thought: Tool thought/description.
            tool_call: Tool call object.

        Returns:
            The created ToolMessage widget.
        """
        widget = ToolMessage(thought, tool_call)
        self.mount(widget)
        self._scroll_to_bottom()
        return widget

    def clear_thinking_messages(self) -> None:
        """Remove all ``ThinkingMessage`` widgets from the pane."""
        # Identify by class name to avoid import coupling
        thinking = [
            child
            for child in self.children
            if child.__class__.__name__ == "ThinkingMessage"
        ]
        for widget in thinking:
            widget.remove()

    def clear_messages(self) -> None:
        """Remove all messages from the pane."""
        self._active = {}
        self.remove_children()


# ------------------------------------------------------------------ #
# Legacy RichLog panes                                                 #
# ------------------------------------------------------------------ #


class ThinkingPane(RichLog):
    """Pane for agent reasoning/thinking output."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize.

        Args:
            **kwargs: Forwarded to ``RichLog``.
        """
        super().__init__(
            wrap=True,
            highlight=True,
            markup=True,
            **kwargs,
        )
        self.border_title = "Thinking (legacy)"


class ToolPane(RichLog):
    """Pane for tool call/result display."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize.

        Args:
            **kwargs: Forwarded to ``RichLog``.
        """
        super().__init__(
            wrap=True,
            highlight=True,
            markup=True,
            **kwargs,
        )
        self.border_title = "Tools"


# ------------------------------------------------------------------ #
# Status bar                                                           #
# ------------------------------------------------------------------ #


class StatusBar(Static):
    """One-line status bar at the bottom of the screen."""

    status_text: reactive[str] = reactive("Ready")

    def __init__(self, **kwargs: Any) -> None:
        """Initialize.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self.border_title = "Status"

    def render(self) -> str:
        """Render the status bar.

        Returns:
            Formatted Rich markup string.
        """
        return f"[bold cyan]{self.status_text}[/]"
