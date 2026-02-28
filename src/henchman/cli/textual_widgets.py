"""Reusable Textual widgets for the Henchman-AI TUI.

Includes the chat pane, custom text input, message display widgets,
and the status bar.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

import contextlib
import re
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar, cast

from rich.markdown import Markdown as RichMarkdown
from rich.markup import escape as markup_escape
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.widget import MountError
from textual.widgets import RichLog, Static, TextArea

if TYPE_CHECKING:
    from collections.abc import Iterator

    from textual import events

_T = TypeVar("_T", bound=Static)

# ------------------------------------------------------------------ #
# Constants                                                            #
# ------------------------------------------------------------------ #

# Rich markup prefixes for message roles
_USER_PREFIX = "[bold green]You:[/]"
_SYSTEM_PREFIX = "[dim]»[/]"
_ERROR_PREFIX = "[bold red]Error:[/]"
_AGENT_PREFIX_TEMPLATE = "[bold cyan]{name}:[/]"

# Regex matching ANSI escape sequences (CSI codes, OSC, etc.)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[^[\]()]")

# Maximum characters before truncation for summaries
_SUMMARY_MAX_LEN = 20


def _safe_markup(text: object) -> str:
    """Strip ANSI codes and escape Rich markup from arbitrary text.

    This is the **single gateway** for all untrusted content entering
    Rich-markup-enabled widgets.  It guarantees the returned string
    will never cause a ``MarkupError``.

    Args:
        text: Raw text (may contain ANSI escapes, Rich-like tags, etc.).
              ``None`` is treated as an empty string.

    Returns:
        Cleaned string safe for Rich markup rendering.
    """
    if text is None:
        return ""
    # 1. Strip ANSI escape sequences
    cleaned = _ANSI_RE.sub("", str(text))
    # 2. Escape Rich markup characters
    return markup_escape(cleaned)


def _highlight_text(escaped_text: str, term: str) -> str:
    """Wrap occurrences of *term* in Rich reverse markup.

    Both the text and term are compared case-insensitively.
    The original casing of the matched text is preserved.

    Args:
        escaped_text: Already-escaped Rich markup string.
        term: Search term to highlight.

    Returns:
        Text with matches wrapped in ``[reverse]…[/reverse]``.
    """
    if not term:
        return escaped_text
    lower = escaped_text.lower()
    tl = term.lower()
    result: list[str] = []
    pos = 0
    while True:
        idx = lower.find(tl, pos)
        if idx == -1:
            result.append(escaped_text[pos:])
            break
        result.append(escaped_text[pos:idx])
        result.append(f"[reverse]{escaped_text[idx : idx + len(tl)]}[/reverse]")
        pos = idx + len(tl)
    return "".join(result)


# ------------------------------------------------------------------ #
# Base Classes and Helper Functions                                   #
# ------------------------------------------------------------------ #


class _BaseTextualWidget(Static):
    """Base class for Textual widgets with common initialization."""

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        """Initialize with text content.

        Args:
            text: Initial text content.
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(text, **kwargs)


class _BaseMessageWidget(_BaseTextualWidget):
    """Base class for message widgets with common append and set_content logic."""

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        """Initialize with text content.

        Args:
            text: Initial text content.
            **kwargs: Forwarded to ``_BaseTextualWidget``.
        """
        super().__init__(text, **kwargs)
        self._content_text: str = text

    def append(self, chunk: str | None) -> None:
        """Append a streaming chunk and re-render.

        Args:
            chunk: Text to append.
        """
        if chunk is None:
            return
        self._content_text += chunk
        self._update_renderable()

    def set_content(self, content: str) -> None:
        """Replace content entirely and re-render.

        Args:
            content: Full replacement content.
        """
        self._content_text = content or ""
        self._update_renderable()

    @property
    def _content(self) -> str:
        """Alias for ``_content_text`` used by search."""
        return self._content_text

    @abstractmethod
    def _update_renderable(self) -> None:
        """Re-render the widget with current content. Must be implemented by subclasses."""
        raise NotImplementedError


class _CollapsibleHeader(_BaseTextualWidget):
    """Clickable header for a collapsible message."""

    DEFAULT_CSS = """
    _CollapsibleHeader {
        padding: 0 1;
    }
    """


class _CollapsibleContent(_BaseTextualWidget):
    """Body of a collapsible message (hidden when collapsed)."""

    DEFAULT_CSS = """
    _CollapsibleContent {
        padding: 0 1 0 3;
    }
    _CollapsibleContent.thinking {
        color: $text-muted;
    }
    _CollapsibleContent.tool {
        color: $warning;
    }
    """


class CollapsibleMessage(_BaseMessageWidget):
    """Base class for collapsible messages with common functionality."""

    DEFAULT_CSS = """
    CollapsibleMessage {
        padding: 0;
        margin: 0 0 1 0;
    }
    CollapsibleMessage > _CollapsibleContent {
        display: none;
    }
    CollapsibleMessage.expanded > _CollapsibleContent {
        display: block;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the collapsible message.

        Args:
            **kwargs: Forwarded to ``_BaseMessageWidget``.
        """
        super().__init__(**kwargs)
        self._is_expanded: bool = False
        self._highlight_term: str = ""
        self.header = _CollapsibleHeader()
        self._body = _CollapsibleContent()
        # Don't call _update_renderable here - subclasses should call it
        # after they've set up their specific attributes

    @property  # type: ignore[override]
    def content(self) -> _CollapsibleContent:
        """Return the body sub-widget for expansion display."""
        return self._body

    @content.setter
    def content(self, value: object) -> None:
        """Allow setting content (used by Static internals)."""
        if isinstance(value, _CollapsibleContent):
            self._body = value

    def compose(self) -> Iterator[_CollapsibleHeader | _CollapsibleContent]:
        """Compose the header and content sub-widgets.

        Yields:
            Header and content widgets.
        """
        yield self.header
        yield self._body

    @abstractmethod
    def _update_renderable(self) -> None:
        """Re-render header and content sub-widgets. Must be implemented by subclasses."""
        raise NotImplementedError

    def toggle_expansion(self) -> None:
        """Toggle between collapsed and expanded states."""
        self._is_expanded = not self._is_expanded
        if self._is_expanded:
            self.add_class("expanded")
        else:
            self.remove_class("expanded")

    def on_click(self, event: events.Click) -> None:
        """Handle click events to toggle expansion.

        Args:
            event: Click event (unused).
        """
        self.toggle_expansion()

    def set_highlight(self, term: str) -> None:
        """Set or clear the search highlight term and re-render.

        Args:
            term: Search term to highlight (empty to clear).
        """
        self._highlight_term = term
        self._update_renderable()


# Patterns that indicate content should be rendered as markdown.
_MARKDOWN_INDICATORS = (
    "```",  # code blocks
    "**",  # bold
    "##",  # headings
    "- ",  # unordered lists
    "1. ",  # ordered lists
    "[",  # links / images
    "> ",  # blockquotes
)


def _looks_like_markdown(text: str) -> bool:
    """Heuristic check whether *text* contains markdown formatting.

    Args:
        text: Raw text content.

    Returns:
        ``True`` if the text appears to contain markdown syntax.
    """
    return any(indicator in text for indicator in _MARKDOWN_INDICATORS)


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
            self._handle_enter_key(event)
        elif event.key == "shift+enter":
            self._handle_shift_enter_key(event)

    def _handle_enter_key(self, event: events.Key) -> None:
        """Handle the Enter key press.

        Args:
            event: Key event.
        """
        event.stop()
        event.prevent_default()
        # Cast app to HenchmanTextualApp to access its methods
        from henchman.cli.textual_app import HenchmanTextualApp

        app = cast(HenchmanTextualApp, self.app)
        app.action_submit_message()

    def _handle_shift_enter_key(self, event: events.Key) -> None:
        """Handle the Shift+Enter key press.

        Args:
            event: Key event.
        """
        event.stop()
        event.prevent_default()
        self.insert("\n")

    def action_newline(self) -> None:
        """Insert a newline character."""
        self.insert("\n")

    def action_history_up(self) -> None:
        """Move up in history when cursor is at the first row."""
        if self.cursor_location[0] == 0:
            # Cast app to HenchmanTextualApp to access its methods
            from henchman.cli.textual_app import HenchmanTextualApp

            app = cast(HenchmanTextualApp, self.app)
            app._navigate_history(-1)
        else:
            self.action_cursor_up()

    def action_history_down(self) -> None:
        """Move down in history when cursor is at the last row."""
        last_row = self.document.line_count - 1
        if self.cursor_location[0] >= last_row:
            # Cast app to HenchmanTextualApp to access its methods
            from henchman.cli.textual_app import HenchmanTextualApp

            app = cast(HenchmanTextualApp, self.app)
            app._navigate_history(1)
        else:
            self.action_cursor_down()


# ------------------------------------------------------------------ #
# Chat message widgets                                                 #
# ------------------------------------------------------------------ #


class ChatMessage(_BaseMessageWidget):
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
            **kwargs: Extra kwargs forwarded to ``_BaseMessageWidget``.
        """
        super().__init__(content, **kwargs)
        self._prefix = prefix
        self._highlight_term: str = ""
        self._is_markdown: bool = False
        self._renderable_text: str = ""
        self._update_renderable()

    @property
    def renderable(self) -> str | RichMarkdown:
        """Return the last computed renderable for testing introspection."""
        return self._renderable_text

    def _update_renderable(self) -> None:
        """Re-render the static widget with current content."""
        if not self._content_text:
            self._renderable_text = self._prefix
            self.update(self._prefix)
            return
        if self._is_markdown:
            md = RichMarkdown(self._content_text)
            self._renderable_text = md  # type: ignore[assignment]
            self.update(md)
            return
        escaped = _safe_markup(self._content_text)
        if self._highlight_term:
            escaped = _highlight_text(escaped, self._highlight_term)
        text = f"{self._prefix} {escaped}"
        self._renderable_text = text
        self.update(text)

    def set_highlight(self, term: str) -> None:
        """Set or clear the search highlight term and re-render.

        Temporarily disables markdown rendering so highlights are visible.

        Args:
            term: Search term to highlight (empty to clear).
        """
        self._highlight_term = term
        if term and self._is_markdown:
            self._is_markdown = False
        self._update_renderable()

    def finalize_as_markdown(self) -> None:
        """Switch rendering to Rich Markdown after streaming completes.

        Only applies markdown rendering if the content appears to contain
        markdown syntax (headings, code blocks, bold, links, etc.).
        """
        if not self._content_text:
            return
        if _looks_like_markdown(self._content_text):
            self._is_markdown = True
            self._update_renderable()


class ThinkingMessage(CollapsibleMessage):
    """Collapsible display for agent thinking content in the chat pane.

    Starts collapsed — only a one-line summary is visible.  Clicking the
    widget (or calling ``toggle_expansion()``) reveals the full text.
    """

    DEFAULT_CSS = """
    ThinkingMessage {
        padding: 0;
        margin: 0 0 1 0;
        color: $text-muted;
    }
    ThinkingMessage > _CollapsibleContent {
        display: none;
    }
    ThinkingMessage.expanded > _CollapsibleContent {
        display: block;
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
        self._content_text = thought
        self._thought = thought
        # Override header and body with custom CSS
        self.header = _CollapsibleHeader()
        self._body = _CollapsibleContent()
        self._body.add_class("thinking")
        self._update_renderable()

    def _get_summary(self) -> str:
        """Return a truncated one-line summary of the thinking content.

        Returns:
            Truncated text, at most ``_SUMMARY_MAX_LEN`` chars + ``...``.
        """
        text = self._content_text.replace("\n", " ").strip()
        if len(text) > _SUMMARY_MAX_LEN:
            return text[:_SUMMARY_MAX_LEN] + "..."
        return text

    def _update_renderable(self) -> None:
        """Re-render header and content sub-widgets."""
        agent = f"{self._agent_name} " if self._agent_name else ""
        # Header sub-widget: never includes content, just "thinking: (click to expand)"
        self._header_text = f"🤔 {agent}thinking: (click to expand)"
        self.header.update(self._header_text)

        full = self._content_text
        escaped = _safe_markup(full)
        if self._highlight_term:
            escaped = _highlight_text(escaped, self._highlight_term)
        self._body_text = f"[dim]{escaped}[/]"
        self._body.update(self._body_text)

    def render(self) -> str:
        """Return text for render introspection.

        The top-level render includes a summary in the header line for
        programmatic access, while the header sub-widget stays minimal.

        Returns:
            Header with summary when collapsed, header + content when expanded.
        """
        agent = f"{self._agent_name} " if self._agent_name else ""
        summary = self._get_summary()
        header_line = f"🤔 {agent}thinking: {summary} (click to expand)"
        if self._is_expanded:
            return f"{header_line}\n{self._content_text}"
        return header_line

    def append(self, chunk: str | None) -> None:
        """Append a streaming chunk and re-render.

        Args:
            chunk: Text to append.
        """
        if chunk is None:
            return
        self._content_text += chunk
        self._thought = self._content_text
        self._update_renderable()

    def set_content(self, content: str) -> None:
        """Replace content entirely and re-render.

        Args:
            content: Full replacement content.
        """
        self._content_text = content or ""
        self._thought = self._content_text
        self._update_renderable()


class ToolMessage(CollapsibleMessage):
    """Collapsible display for tool call/result content in the chat pane.

    Starts collapsed — only a one-line summary header with tool name and
    compact args is visible.  Clicking or ``toggle_expansion()`` reveals
    the full JSON arguments and result text.
    """

    DEFAULT_CSS = """
    ToolMessage {
        padding: 0;
        margin: 0 0 1 0;
        color: $warning;
    }
    ToolMessage > _CollapsibleContent {
        display: none;
    }
    ToolMessage.expanded > _CollapsibleContent {
        display: block;
    }
    """

    def __init__(
        self,
        thought: str = "",
        tool_call: Any = None,
        **kwargs: Any,
    ) -> None:
        """Initialize.

        Accepts either a positional ``thought`` string or a ``tool_call``
        object (with ``.name`` and ``.arguments``).  When *only* a
        ``ToolCall`` is supplied as the first positional argument it is
        detected automatically.

        Args:
            thought: Tool thought/description.
            tool_call: Tool call object with ``name`` and ``arguments``.
            **kwargs: Forwarded to ``Static``.
        """
        # Support ToolMessage(tool_call_obj) as positional arg
        if tool_call is None and thought and not isinstance(thought, str):
            tool_call = thought
            thought = ""
        super().__init__(**kwargs)
        self.add_class("tool-message")
        self._thought = thought if isinstance(thought, str) else ""
        self._tool_call = tool_call
        self._content_text = self._thought
        self._result_text: str = ""
        # Override header and body with custom CSS
        self.header = _CollapsibleHeader()
        self._body = _CollapsibleContent()
        self._body.add_class("tool")
        self._update_renderable()

    def _format_compact_args(self) -> str:
        """Return a compact one-line representation of tool arguments.

        Returns:
            Compact ``key=value`` string or empty string.
        """
        if not self._tool_call or not getattr(self._tool_call, "arguments", None):
            return ""
        import json

        args = self._tool_call.arguments
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                return str(args)
        if isinstance(args, dict):
            return ",".join(f"{k}={v}" for k, v in args.items())
        return str(args)

    def _format_full_args(self) -> str:
        """Return indented JSON of tool arguments.

        Returns:
            Pretty-printed JSON or string representation.
        """
        if not self._tool_call or not getattr(self._tool_call, "arguments", None):
            return ""
        import json

        args = self._tool_call.arguments
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                return str(args)
        try:
            return json.dumps(args, indent=2)
        except (TypeError, ValueError):
            return str(args)

    def _get_header_text(self) -> str:
        """Get the header text based on tool call or thought.

        Returns:
            Formatted header text.
        """
        if self._tool_call and hasattr(self._tool_call, "name"):
            compact = _safe_markup(self._format_compact_args())
            name = _safe_markup(self._tool_call.name)
            return f"🔧 {name}({compact})" if compact else f"🔧 {name}"
        elif self._thought:
            return f"🛠️  {_safe_markup(self._thought)}"
        else:
            return "🛠️  Tool call"

    def _get_body_content(self) -> str:
        """Get the body content with proper formatting.

        Returns:
            Formatted body content.
        """
        parts: list[str] = []
        full_args = self._format_full_args()
        if full_args:
            parts.append(full_args)
        if self._result_text:
            parts.append(self._result_text)
        if self._content_text and self._content_text != self._thought:
            parts.append(self._content_text)
        body = "\n".join(parts) if parts else ""
        escaped = _safe_markup(body)
        if self._highlight_term:
            escaped = _highlight_text(escaped, self._highlight_term)
        return f"[dim]{escaped}[/]"

    def _update_renderable(self) -> None:
        """Re-render header and content sub-widgets."""
        self.header.update(self._get_header_text())
        self._body.update(self._get_body_content())

    def _get_render_header(self) -> str:
        """Get the header for render output.

        Returns:
            Header text.
        """
        if self._tool_call and hasattr(self._tool_call, "name"):
            compact = self._format_compact_args()
            name = self._tool_call.name
            return f"🔧 {name}({compact})" if compact else f"🔧 {name}"
        elif self._thought:
            return f"🛠️  {_safe_markup(self._thought)}"
        else:
            return "🛠️  Tool call"

    def _get_expanded_content(self) -> str:
        """Get the expanded content for render output.

        Returns:
            Expanded content text.
        """
        parts: list[str] = []
        if self._tool_call and getattr(self._tool_call, "arguments", None):
            import json

            args = self._tool_call.arguments
            if isinstance(args, str):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    args = json.loads(args)
            try:
                parts.append(json.dumps(args))
            except (TypeError, ValueError):
                parts.append(str(args))
        if self._result_text:
            parts.append(self._result_text)
        if self._content_text and self._content_text != self._thought:
            parts.append(self._content_text)
        return "\n".join(parts)

    def render(self) -> str:
        """Return text representation for render introspection.

        Returns:
            Header text when collapsed, header + full args when expanded.
        """
        header = self._get_render_header()
        if self._is_expanded:
            expanded_content = self._get_expanded_content()
            return f"{header}\n{expanded_content}" if expanded_content else header
        return header


class ChatPane(VerticalScroll):
    """Scrollable container for chat messages."""

    DEFAULT_CSS = """
    ChatPane {
        height: 100%;
        width: 100%;
    }
    """

    _active: dict[str, ChatMessage]
    _active_thinking: dict[str, ThinkingMessage]

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
        self._active: dict[str, ChatMessage] = {}
        self._active_thinking: dict[str, ThinkingMessage] = {}

    def on_mount(self) -> None:
        """Re-initialize the active message maps on mount."""
        self._active = {}
        self._active_thinking = {}

    def _scroll_to_bottom(self) -> None:
        """Scroll to the latest message."""
        self.scroll_end(animate=False)
        if self.children:
            self.children[-1].scroll_visible(animate=False)

    def _mount_widget(self, widget: Static) -> None:
        """Mount a widget, falling back to direct append if not attached.

        Args:
            widget: Widget to add.
        """
        try:
            self.mount(widget)
        except (RuntimeError, AttributeError, MountError):
            # Widget not attached to an app — store as child directly
            self._nodes._append(widget)

    def _try_scroll(self) -> None:
        """Scroll to bottom, ignoring errors when not mounted."""
        with contextlib.suppress(Exception):
            self._scroll_to_bottom()

    # -- public API for adding messages --

    def _add_message_with_prefix(self, prefix: str, text: str) -> None:
        """Add a message with the given prefix.

        Args:
            prefix: Rich markup prefix for the message.
            text: Message content.
        """
        msg = ChatMessage(prefix, text)
        self._mount_widget(msg)
        self._try_scroll()

    def add_user_message(self, text: str) -> None:
        """Append a user message block.

        Args:
            text: User input text.
        """
        self._add_message_with_prefix(_USER_PREFIX, text)

    def add_system_message(self, text: str) -> None:
        """Append a dim system/info message.

        Args:
            text: Information text.
        """
        self._add_message_with_prefix(_SYSTEM_PREFIX, text)

    def add_error_message(self, text: str) -> None:
        """Append a red error message.

        Args:
            text: Error text.
        """
        self._add_message_with_prefix(_ERROR_PREFIX, text)

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
        self._mount_widget(widget)
        self._try_scroll()
        return widget

    def append_agent_chunk(self, agent_name: str, chunk: str) -> None:
        """Append a streaming chunk to an active agent message.

        Creates a new stream widget if none exists yet.

        Args:
            agent_name: Agent whose message to extend.
            chunk: Text chunk to append.
        """
        newly_created = agent_name not in self._active
        if newly_created:
            self.begin_agent_stream(agent_name)
        self._active[agent_name].append(chunk)
        # Only scroll if we didn't just create a new stream (begin_agent_stream already scrolls)
        if not newly_created:
            self._scroll_to_bottom()

    def finish_agent_stream(self, agent_name: str) -> None:
        """Mark an agent's streaming message as complete.

        Finalizes the message widget with markdown rendering if applicable.

        Args:
            agent_name: Agent whose stream ended.
        """
        widget = self._active.pop(agent_name, None)
        if widget is None:
            import logging

            logging.debug(f"Attempted to finish non-existent agent stream: {agent_name}")
            return
        widget.finalize_as_markdown()

    def _add_widget(self, widget: Static) -> Static:
        """Helper method to add a widget to the pane.

        Args:
            widget: Widget to add.

        Returns:
            The added widget.
        """
        self._mount_widget(widget)
        self._try_scroll()
        return widget

    def _create_and_add_widget(
        self, widget_class: type[Static], *args: Any, **kwargs: Any
    ) -> Static:
        """Create and add a widget to the pane.

        Args:
            widget_class: The widget class to instantiate.
            *args: Positional arguments for widget constructor.
            **kwargs: Keyword arguments for widget constructor.

        Returns:
            The created and added widget.
        """
        widget = widget_class(*args, **kwargs)
        return self._add_widget(widget)

    def _add_typed_message_widget(
        self,
        widget_class: type[_T],
        *args: Any,
        **kwargs: Any
    ) -> _T:
        """Type-safe method to add a message widget with proper return type.

        Args:
            widget_class: The widget class to instantiate.
            *args: Positional arguments for widget constructor.
            **kwargs: Keyword arguments for widget constructor.

        Returns:
            The created widget with correct type.
        """
        widget = self._create_and_add_widget(widget_class, *args, **kwargs)
        return widget  # type: ignore[return-value]

    def _add_message_by_type(
        self,
        widget_class: type[_T],
        *args: Any,
        **kwargs: Any
    ) -> _T:
        """Generic method to add a message widget of specified type.

        Args:
            widget_class: The widget class to instantiate.
            *args: Positional arguments for widget constructor.
            **kwargs: Keyword arguments for widget constructor.

        Returns:
            The created widget.
        """
        return self._add_typed_message_widget(widget_class, *args, **kwargs)

    def add_thinking_message(self, thought: str, agent_name: str = "") -> ThinkingMessage:
        """Add a thinking message to the chat pane.

        Args:
            thought: The thinking content.
            agent_name: Name of the thinking agent.

        Returns:
            The created ThinkingMessage widget.
        """
        return self._add_message_by_type(ThinkingMessage, thought, agent_name)

    def begin_thinking_stream(self, agent_name: str = "") -> ThinkingMessage:
        """Start a new streaming thinking message for *agent_name*.

        Args:
            agent_name: Display name of the thinking agent.

        Returns:
            The newly mounted ThinkingMessage widget.
        """
        widget = self._add_message_by_type(ThinkingMessage, "", agent_name)
        self._active_thinking[agent_name] = widget
        return widget

    def append_thinking_chunk(self, agent_name: str, chunk: str) -> None:
        """Append a streaming chunk to an active thinking message.

        Creates a new stream widget if none exists yet.

        Args:
            agent_name: Agent whose thinking to extend.
            chunk: Text chunk to append.
        """
        if agent_name not in self._active_thinking:
            self.begin_thinking_stream(agent_name)
        self._active_thinking[agent_name].append(chunk)

    def add_tool_message(self, thought: str = "", tool_call: Any = None) -> ToolMessage:
        """Add a tool message to the chat pane.

        Args:
            thought: Tool thought/description.
            tool_call: Tool call object.

        Returns:
            The created ToolMessage widget.
        """
        return self._add_message_by_type(ToolMessage, thought, tool_call)

    def clear_thinking_messages(self) -> None:
        """Remove all ``ThinkingMessage`` widgets from the pane."""
        self._active_thinking = {}
        thinking = [child for child in self.children if isinstance(child, ThinkingMessage)]
        for widget in thinking:
            try:
                widget.remove()
            except (RuntimeError, AttributeError, MountError):
                self._nodes._remove(widget)

    def clear_messages(self) -> None:
        """Remove all messages from the pane."""
        self._active = {}
        self._active_thinking = {}
        try:
            self.remove_children()
        except (RuntimeError, AttributeError, MountError):
            self._nodes._clear()


# ------------------------------------------------------------------ #
# Legacy RichLog panes                                                 #
# ------------------------------------------------------------------ #


class _BaseRichLogPane(RichLog):
    """Base class for RichLog panes with common initialization."""

    def __init__(self, border_title: str = "Pane", **kwargs: Any) -> None:
        """Initialize.

        Args:
            border_title: Title for the pane border.
            **kwargs: Forwarded to ``RichLog``.
        """
        super().__init__(
            wrap=True,
            highlight=True,
            markup=True,
            **kwargs,
        )
        self.border_title = border_title


class _TitledPane(_BaseRichLogPane):
    """Base class for panes with a specific border title."""

    _DEFAULT_BORDER_TITLE: str = "Pane"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize pane with default border title."""
        super().__init__(border_title=self._DEFAULT_BORDER_TITLE, **kwargs)


class ThinkingPane(_TitledPane):
    """Pane for agent reasoning/thinking output."""

    _DEFAULT_BORDER_TITLE: str = "Thinking (legacy)"


class ToolPane(_TitledPane):
    """Pane for tool call/result display."""

    _DEFAULT_BORDER_TITLE: str = "Tools"


# ------------------------------------------------------------------ #
# Status bar                                                           #
# ------------------------------------------------------------------ #


class StatusBar(Static):
    """One-line status bar at the bottom of the screen."""

    status_text: reactive[str] = reactive("Ready")
    tokens: reactive[int] = reactive(0)
    cost: reactive[float] = reactive(0.0)

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
        parts = [f"[bold cyan]{self.status_text}[/]"]
        if self.tokens > 0:
            parts.append(f"[dim]{self.tokens:,} tokens[/]")
        if self.cost > 0:
            parts.append(f"[dim]${self.cost:.4f}[/]")
        return " | ".join(parts)


# ------------------------------------------------------------------ #
# Progress indicator                                                   #
# ------------------------------------------------------------------ #


class ProgressIndicator(Static):
    """Inline progress indicator shown between chat and input.

    Displays a spinning/pulsing message while the agent or tool is
    working.  Call :meth:`show` / :meth:`hide` to control visibility.
    """

    DEFAULT_CSS = """
    ProgressIndicator {
        height: auto;
        width: 100%;
        padding: 0 1;
        display: none;
    }
    ProgressIndicator.visible {
        display: block;
    }
    """

    _message: str = ""
    _kind: str = ""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the progress indicator.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self._message = ""
        self._kind = ""

    def show(self, message: str = "Working...", kind: str = "agent") -> None:
        """Show the progress indicator with a message.

        Args:
            message: Status message to display.
            kind: Category of work (``agent``, ``tool``).
        """
        self._message = message
        self._kind = kind
        self.add_class("visible")
        self.update(self.render())

    def hide(self) -> None:
        """Hide the progress indicator."""
        self._message = ""
        self._kind = ""
        self.remove_class("visible")
        self.update("")

    @property
    def is_visible(self) -> bool:
        """Whether the indicator is currently displayed.

        Returns:
            True if showing.
        """
        return "visible" in self.classes

    def render(self) -> str:
        """Render the progress line.

        Returns:
            Rich markup string.
        """
        if not self._message:
            return ""
        icon = "🔧" if self._kind == "tool" else "⏳"
        return f"[dim]{icon} {self._message}[/]"
