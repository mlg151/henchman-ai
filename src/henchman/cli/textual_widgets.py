"""Reusable Textual widgets for the Henchman-AI TUI.

Includes the chat pane, custom text input, message display widgets,
and the status bar.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

import contextlib
import functools
import json
import logging
import re
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, TypeVar, cast

from rich.markdown import Markdown as RichMarkdown
from rich.markup import escape as markup_escape
from rich.text import Text
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.message import Message as TextualMessage
from textual.reactive import reactive
from textual.widget import MountError
from textual.widgets import RichLog, Static, TextArea

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.textual_tool_activity import ToolActivity, ToolActivityStore, ToolEvidenceScreen

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from textual import events
    from textual.geometry import Region

    from henchman.cli.textual_app import HenchmanTextualApp

_T = TypeVar("_T", bound=Static)
_LOGGER = logging.getLogger(__name__)


class ToolCallProtocol(Protocol):
    """Protocol for tool call objects."""

    name: str
    arguments: str | dict[str, Any]


# ------------------------------------------------------------------ #
# Constants                                                            #
# ------------------------------------------------------------------ #

# Rich markup prefixes for message roles
_USER_PREFIX: str = "[bold green]You:[/]"
_SYSTEM_PREFIX: str = "[dim]»[/]"
_ERROR_PREFIX: str = "[bold red]Error:[/]"
_AGENT_PREFIX_TEMPLATE: str = "[bold cyan]{name}:[/]"

# Regex matching ANSI escape sequences (CSI codes, OSC, etc.)
_ANSI_RE: re.Pattern[str] = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b[^[\]()]")

# Maximum characters before truncation for summaries
_THINKING_SUMMARY_MAX_LENGTH: int = 20

# Emoji and icon constants
_THINKING_EMOJI: str = "🤔"
_TOOL_EMOJI: str = "🔧"
_GENERIC_TOOL_EMOJI: str = "🛠️"
_PROGRESS_ICON: str = "⏳"
_TOOL_PROGRESS_ICON: str = "🔧"

# Default text constants
_DEFAULT_TOOL_CALL_TEXT: str = "Tool call"
_THINKING_TEXT: str = "thinking: (click to expand)"


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
    cleaned: str = _ANSI_RE.sub("", str(text))
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
    lower: str = escaped_text.lower()
    tl: str = term.lower()
    result: list[str] = []
    pos: int = 0
    while True:
        idx: int = lower.find(tl, pos)
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

    def __init__(self: Self, text: str = "", **kwargs: Any) -> None:
        """Initialize with text content.

        Args:
            text: Initial text content.
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(text, **kwargs)


class _BaseMessageWidget(_BaseTextualWidget):
    """Base class for message widgets with common append and set_content logic."""

    DEFAULT_CSS = """
    _BaseMessageWidget {
        margin: 0 0 1 0;
    }
    """

    def __init__(self: Self, text: str = "", **kwargs: Any) -> None:
        """Initialize with text content.

        Args:
            text: Initial text content.
            **kwargs: Forwarded to ``_BaseTextualWidget``.
        """
        super().__init__(text, **kwargs)
        self._content_text: str = text

    def append(self: Self, chunk: str | None) -> None:
        """Append a streaming chunk and re-render.

        Args:
            chunk: Text to append.
        """
        if chunk is None:
            return
        self._content_text += chunk
        self._update_renderable()

    def set_content(self: Self, content: str) -> None:
        """Replace content entirely and re-render.

        Args:
            content: Full replacement content.
        """
        self._content_text = content or ""
        self._update_renderable()

    @property
    def _content(self: Self) -> str:
        """Alias for ``_content_text`` used by search."""
        return self._content_text

    @abstractmethod
    def _update_renderable(self: Self) -> None:
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

    def __init__(self: Self, *, output_mode: str = "rich", **kwargs: Any) -> None:
        """Initialize the collapsible message.

        Args:
            **kwargs: Forwarded to ``_BaseMessageWidget``.
        """
        super().__init__(**kwargs)
        self._output_mode = output_mode
        self._is_expanded: bool = False
        self._highlight_term: str = ""
        self.header = _CollapsibleHeader()
        self._body = _CollapsibleContent()
        # Don't call _update_renderable here - subclasses should call it
        # after they've set up their specific attributes

    @property  # type: ignore[override]
    def content(self: Self) -> _CollapsibleContent:
        """Return the body sub-widget for expansion display.

        Returns:
            The _CollapsibleContent widget instance containing the message body.
        """
        return self._body

    @content.setter
    def content(self: Self, value: object) -> None:
        """Allow setting content (used by Static internals).

        Args:
            value: The content to set. Must be an instance of _CollapsibleContent.

        Returns:
            None
        """
        if isinstance(value, _CollapsibleContent):
            self._body = value

    def compose(self: Self) -> Iterator[_CollapsibleHeader | _CollapsibleContent]:
        """Compose the header and content sub-widgets.

        Yields:
            Header and content widgets.
        """
        yield self.header
        yield self._body

    @abstractmethod
    def _update_renderable(self: Self) -> None:
        """Re-render header and content sub-widgets. Must be implemented by subclasses."""
        raise NotImplementedError

    def toggle_expansion(self: Self) -> None:
        """Toggle between collapsed and expanded states.

        Returns:
            None
        """
        pane = next((parent for parent in self.ancestors if isinstance(parent, ChatPane)), None)
        if pane is not None:
            pane.hold_reading_position()
        self._is_expanded = not self._is_expanded
        if self._is_expanded:
            self.add_class("expanded")
        else:
            self.remove_class("expanded")
        if pane is not None:
            pane.refresh_reading_position()

    def on_click(self: Self, _event: events.Click) -> None:
        """Handle click events to toggle expansion.

        Args:
            _event: Click event (unused).

        Returns:
            None
        """
        self.toggle_expansion()

    def set_highlight(self: Self, term: str) -> None:
        """Set or clear the search highlight term and re-render.

        Args:
            term: Search term to highlight (empty to clear).

        Returns:
            None
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


def _get_private_member(owner: object, member_name: str) -> Any:
    """Return a private attribute, including MagicMock-generated members."""
    try:
        return object.__getattribute__(owner, member_name)
    except AttributeError:
        get_missing_member = object.__getattribute__(owner, "__getattr__")
        return get_missing_member(member_name)


def _call_private_member(owner: object, member_name: str, *args: Any) -> Any:
    """Call a private attribute that behaves like a method."""
    member = _get_private_member(owner, member_name)
    return member(*args)


def _perform_pane_operation(
    operation: Callable[..., object],
    pane: ChatPane,
    fallback_name: str,
    *fallback_args: Any,
) -> None:
    """Run a pane operation with detached-node fallback handling."""
    try:
        operation()
    except (RuntimeError, AttributeError, MountError):
        _call_private_member(_get_private_member(pane, "_nodes"), fallback_name, *fallback_args)


# ------------------------------------------------------------------ #
# Custom input widget                                                  #
# ------------------------------------------------------------------ #


class HenchmanTextArea(TextArea):
    """Custom TextArea with Enter/Shift-Enter and history navigation."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("ctrl+f", "app.search", "Search", show=False),
        Binding(
            "enter",
            "app.submit_message",
            "Submit Message",
            show=False,
            priority=True,
        ),
        Binding("shift+enter", "newline", "Newline", show=False),
        Binding("ctrl+j", "newline", "Newline", show=False),
        Binding(
            "escape",
            "app.cancel_or_clear",
            "Cancel/Clear",
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

    def action_newline(self: Self) -> None:
        """Insert a newline character.

        Returns:
            None
        """
        self.insert("\n")

    def action_history_up(self: Self) -> None:
        """Move up in history when cursor is at the first row.

        Returns:
            None
        """
        if self.cursor_location[0] == 0:
            self._navigate_app_history(-1)
        else:
            self.action_cursor_up()

    def action_history_down(self: Self) -> None:
        """Move down in history when cursor is at the last row.

        Returns:
            None
        """
        last_row = self.document.line_count - 1
        if self.cursor_location[0] >= last_row:
            self._navigate_app_history(1)
        else:
            self.action_cursor_down()

    def _navigate_app_history(self: Self, direction: int) -> None:
        """Delegate history navigation to the parent app."""
        app = cast("HenchmanTextualApp", self.app)
        navigate_history = cast("Any", _get_private_member(app, "_navigate_history"))
        navigate_history(direction)


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
    }
    """

    def __init__(
        self: Self,
        prefix: str,
        content: str = "",
        *,
        trusted: bool = False,
        output_mode: str = "rich",
        **kwargs: Any,
    ) -> None:
        """Initialize.

        Args:
            prefix: Rich-markup prefix (e.g. ``[bold cyan]Asst:[/]``).
            content: Initial content (may be empty for streaming).
            trusted: If True, render content Rich markup instead of escaping.
                     Use for system-generated messages only.
            **kwargs: Extra kwargs forwarded to ``_BaseMessageWidget``.
        """
        super().__init__(content, **kwargs)
        self._prefix = prefix
        self._trusted = trusted
        self._output_mode = output_mode
        self._highlight_term: str = ""
        self._is_markdown: bool = False
        self._renderable_text: str | RichMarkdown | Text = ""
        self._update_renderable()

    @property
    def renderable(self: Self) -> str | RichMarkdown | Text:
        """Return the last computed renderable for testing introspection."""
        return self._renderable_text

    def _update_renderable(self: Self) -> None:
        """Re-render the static widget with current content."""
        if self._output_mode != "rich":
            prefix = Text.from_markup(self._prefix, emoji=False).plain
            content = (
                Text.from_markup(self._content_text, emoji=False).plain
                if self._trusted else self._content_text
            )
            text = Text(f"{prefix} {content}" if content else prefix)
            if self._highlight_term:
                text.highlight_words([self._highlight_term], style="reverse", case_sensitive=False)
            self._renderable_text = text
            self.update(text)
            return
        if not self._content_text:
            self._renderable_text = self._prefix
            self.update(self._prefix)
            return
        if self._is_markdown:
            self._render_markdown()
            return
        self._render_plain_text()

    def _render_markdown(self: Self) -> None:
        """Render content as markdown."""
        md = RichMarkdown(self._content_text)
        self._renderable_text = md
        self.update(md)

    def _render_plain_text(self: Self) -> None:
        """Render content as plain text with optional highlighting."""
        content = self._content_text if self._trusted else _safe_markup(self._content_text)
        if self._highlight_term:
            content = _highlight_text(content, self._highlight_term)
        text = f"{self._prefix} {content}"
        self._renderable_text = text
        self.update(text)

    def set_highlight(self: Self, term: str) -> None:
        """Set or clear the search highlight term and re-render.

        Temporarily disables markdown rendering so highlights are visible.

        Args:
            term: Search term to highlight (empty to clear).

        Returns:
            None
        """
        self._highlight_term = term
        if term and self._is_markdown:
            self._is_markdown = False
        self._update_renderable()

    def finalize_as_markdown(self: Self) -> None:
        """Switch rendering to Rich Markdown after streaming completes.

        Only applies markdown rendering if the content appears to contain
        markdown syntax (headings, code blocks, bold, links, etc.).

        Returns:
            None
        """
        if not self._content_text or self._output_mode != "rich":
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
        self: Self,
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

    def _get_summary(self: Self) -> str:
        """Return a truncated one-line summary of the thinking content.

        Returns:
            Truncated text, at most ``_THINKING_SUMMARY_MAX_LENGTH`` chars + ``...``.
        """
        text = self._content_text.replace("\n", " ").strip()
        if len(text) > _THINKING_SUMMARY_MAX_LENGTH:
            return text[:_THINKING_SUMMARY_MAX_LENGTH] + "..."
        return text

    def _update_renderable(self: Self) -> None:
        """Re-render header and content sub-widgets."""
        agent = f"{self._agent_name} " if self._agent_name else ""
        if self._output_mode != "rich":
            self.header.update(Text(f"{agent}Thinking (expand to inspect)"))
            body = Text(self._content_text)
            if self._highlight_term:
                body.highlight_words([self._highlight_term], style="reverse", case_sensitive=False)
            self._body.update(body)
            return
        # Header sub-widget: never includes content, just "thinking: (click to expand)"
        header_text = f"{_THINKING_EMOJI} {agent}{_THINKING_TEXT}"
        self.header.update(header_text)

        full = self._content_text
        escaped = _safe_markup(full)
        if self._highlight_term:
            escaped = _highlight_text(escaped, self._highlight_term)
        body_text = f"[dim]{escaped}[/]"
        self._body.update(body_text)

    def render(self: Self) -> str:
        """Return text for render introspection.

        The top-level render includes a summary in the header line for
        programmatic access, while the header sub-widget stays minimal.

        Returns:
            Header with summary when collapsed, header + content when expanded.
        """
        agent = f"{self._agent_name} " if self._agent_name else ""
        summary = self._get_summary()
        header_line = f"{_THINKING_EMOJI} {agent}thinking: {summary} (click to expand)"
        if self._is_expanded:
            return f"{header_line}\n{self._content_text}"
        return header_line

    def append(self: Self, chunk: str | None) -> None:
        """Append a streaming chunk and re-render.

        Args:
            chunk: Text to append.

        Returns:
            None
        """
        if chunk is None:
            return
        self._content_text += chunk
        self._thought = self._content_text
        self._update_renderable()

    def set_content(self: Self, content: str) -> None:
        """Replace content entirely and re-render.

        Args:
            content: Full replacement content.

        Returns:
            None
        """
        self._content_text = content or ""
        self._thought = self._content_text
        self._update_renderable()


class ToolMessage(CollapsibleMessage):
    """Collapsible display for tool call/result content in the chat pane.

    Starts collapsed by default; detailed transcript density starts expanded.
    Clicking or ``toggle_expansion()`` changes the row without later events
    resetting that choice.
    """

    DEFAULT_CSS = """
    ToolMessage {
        padding: 0;
        color: $warning;
    }
    ToolMessage > _CollapsibleContent {
        display: none;
    }
    ToolMessage.expanded > _CollapsibleContent {
        display: block;
    }
    """

    can_focus = True
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("enter", "inspect", "Inspect evidence"), ("space", "expand", "Expand"),
    ]

    def __init__(
        self: Self,
        thought: str = "",
        tool_call: ToolCallProtocol | None = None,
        activity: ToolActivity | None = None,
        *,
        expanded: bool = False,
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
            expanded: Initial presentation only; does not change follow state.
            **kwargs: Forwarded to ``Static``.
        """
        # Support ToolMessage(tool_call_obj) as positional arg
        if tool_call is None and thought and not isinstance(thought, str):
            # If thought is not a string, assume it's a ToolCallProtocol
            tool_call = cast("ToolCallProtocol", thought)
            thought = ""
        super().__init__(**kwargs)
        self.add_class("tool-message")
        self._is_expanded = expanded
        self.set_class(expanded, "expanded")
        self._thought = thought
        self.activity = activity
        self._manual_expansion = False
        self._tool_call = tool_call
        self._content_text = self._thought
        self._result_text: str = ""
        # Override header and body with custom CSS
        self.header = _CollapsibleHeader()
        self._body = _CollapsibleContent()
        self._body.add_class("tool")
        self._update_renderable()

    def action_expand(self) -> None:
        self.toggle_expansion()

    def toggle_expansion(self) -> None:
        """Retain the user's choice across subsequent outcome projections."""
        self._manual_expansion = True
        super().toggle_expansion()

    def action_inspect(self) -> None:
        if self.activity is not None:
            self._update_renderable()
            pane = next((parent for parent in self.ancestors if isinstance(parent, ChatPane)), None)
            if pane is not None:
                pane.hold_reading_position()
            self.app.push_screen(ToolEvidenceScreen(self.activity))
        else:
            self.toggle_expansion()

    def _parse_tool_arguments(self: Self) -> dict[str, Any] | str | None:
        """Parse tool arguments from string to object if possible.

        Returns:
            Parsed arguments object, or original string if parsing fails.
        """
        if not self._tool_call or not getattr(self._tool_call, "arguments", None):
            return None

        args = self._tool_call.arguments
        if isinstance(args, str):
            try:
                return cast("dict[str, Any]", json.loads(args))
            except (json.JSONDecodeError, TypeError):
                return args
        # args should be dict[str, Any] based on ToolCallProtocol
        return cast("dict[str, Any] | str", args)

    def _format_compact_args(self: Self) -> str:
        """Return a compact one-line representation of tool arguments.

        Returns:
            Compact ``key=value`` string or empty string.
        """
        args = self._parse_tool_arguments()
        if args is None:
            return ""
        if isinstance(args, dict):
            return ",".join(f"{k}={v}" for k, v in args.items())
        return str(args)

    def _format_tool_arguments(self: Self, *, pretty: bool = True) -> str:
        """Format tool arguments as JSON.

        Args:
            pretty: If True, use indented formatting. If False, use compact.

        Returns:
            JSON string representation of tool arguments.
        """
        args = self._parse_tool_arguments()
        if args is None:
            return ""

        try:
            indent = 2 if pretty else None
            return json.dumps(args, indent=indent)
        except (TypeError, ValueError):
            return str(args)

    def _format_full_args(self: Self) -> str:
        """Return indented JSON of tool arguments.

        Returns:
            Pretty-printed JSON or string representation.
        """
        return self._format_tool_arguments(pretty=True)

    def _build_header_text(self: Self, *, apply_markup: bool = True) -> str:
        """Build header text for display.

        Args:
            apply_markup: If True, apply safe markup to text.

        Returns:
            Formatted header text.
        """
        if self.activity is not None:
            text = self.activity.summary(runtime_evidence_redactor(self.app))
            return _safe_markup(text) if apply_markup else text
        if self._tool_call and hasattr(self._tool_call, "name"):
            compact = self._format_compact_args()
            name = self._tool_call.name
            if apply_markup:
                compact = _safe_markup(compact) if compact else ""
                name = _safe_markup(name)
            return f"{_TOOL_EMOJI} {name}({compact})" if compact else f"{_TOOL_EMOJI} {name}"
        if self._thought:
            thought_text = _safe_markup(self._thought) if apply_markup else self._thought
            return f"{_GENERIC_TOOL_EMOJI}  {thought_text}"
        return f"{_GENERIC_TOOL_EMOJI}  {_DEFAULT_TOOL_CALL_TEXT}"

    def _build_header_text_for_ui(self: Self) -> str:
        """Build header text for UI display with markup applied.

        Returns:
            Formatted header text with safe markup.
        """
        return self._build_header_text(apply_markup=True)

    def _build_header_text_for_render(self: Self) -> str:
        """Build header text for render output without markup.

        Returns:
            Formatted header text without markup.
        """
        return self._build_header_text(apply_markup=False)

    def _get_header_text(self: Self) -> str:
        """Get the header text based on tool call or thought.

        Returns:
            Formatted header text with markup for UI display.
        """
        return self._build_header_text_for_ui()

    def _build_body_parts(self: Self, *, for_ui: bool = True) -> list[str]:
        """Build the parts that make up the body content.

        Args:
            for_ui: If True, use pretty formatting for UI display.
                    If False, use plain formatting for render output.

        Returns:
            List of body content parts.
        """
        if self.activity is not None:
            return [self.activity.evidence(runtime_evidence_redactor(self.app))]
        parts: list[str] = []

        # Add tool arguments if available
        if self._tool_call and getattr(self._tool_call, "arguments", None):
            if for_ui:
                parts.append(self._format_full_args())
            else:
                parts.append(self._format_tool_arguments_for_render())

        # Add result text if available
        if self._result_text:
            parts.append(self._result_text)

        # Add additional content if different from thought
        if self._content_text and self._content_text != self._thought:
            parts.append(self._content_text)

        return parts

    def _format_tool_arguments_for_render(self: Self) -> str:
        """Format tool arguments for render output.

        Returns:
            JSON string representation of tool arguments.
        """
        return self._format_tool_arguments(pretty=False)

    def _get_body_content(self: Self) -> str:
        """Get the body content with proper formatting for UI display.

        Returns:
            Formatted body content with markup.
        """
        parts = self._build_body_parts(for_ui=True)
        body = "\n".join(parts) if parts else ""
        escaped = _safe_markup(body)
        if self._highlight_term:
            escaped = _highlight_text(escaped, self._highlight_term)
        return f"[dim]{escaped}[/]"

    def _update_renderable(self: Self) -> None:
        """Re-render header and content sub-widgets."""
        if (
            self._output_mode == "quiet" and not self._manual_expansion
            and self.activity is not None
            and self.activity.outcome in {"Failed", "Unknown", "Interrupted"}
        ):
            self._is_expanded = True
            self.add_class("expanded")
        self.header.update(
            self._get_header_text() if self._output_mode == "rich"
            else Text(self._get_render_header()),
        )
        if self.activity is not None:
            self.header.styles.height = 1
            self.header.styles.text_wrap = "nowrap"
            self.header.styles.text_overflow = "ellipsis"
        if self._output_mode == "rich":
            self._body.update(self._get_body_content())
        else:
            body = Text("\n".join(self._build_body_parts(for_ui=True)))
            if self._highlight_term:
                body.highlight_words([self._highlight_term], style="reverse", case_sensitive=False)
            self._body.update(body)

    def _get_render_header(self: Self) -> str:
        """Get the header for render output.

        Returns:
            Header text without markup for render introspection.
        """
        return self._build_header_text_for_render()

    def _get_expanded_content(self: Self) -> str:
        """Get the expanded content for render output.

        Returns:
            Expanded content text.
        """
        parts = self._build_body_parts(for_ui=False)
        return "\n".join(parts)

    def render(self: Self) -> str:
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

    class FollowChanged(TextualMessage):
        """The transcript's explicit follow/hold state changed."""

        def __init__(self, pane: ChatPane) -> None:
            super().__init__()
            self.pane = pane

    def __init__(self: Self, *, detail_density: str = "normal", output_mode: str = "rich", **kwargs: Any) -> None:
        """Initialize the chat pane.

        Args:
            detail_density: Held startup preference for spacing and new tool rows.
            **kwargs: Forwarded to ``VerticalScroll``.
        """
        super().__init__(**kwargs)
        self._detail_density = detail_density
        self.output_mode = output_mode
        self.set_class(detail_density == "compact", "density-compact")
        self.border_title = "Chat"
        self.wrap: bool = True
        self.highlight: bool = True
        self.markup: bool = True
        self._active: dict[str, ChatMessage] = {}
        self._active_thinking: dict[str, ThinkingMessage] = {}
        self._tool_activity = ToolActivityStore()
        self._tool_rows: dict[str, ToolMessage] = {}
        self.follow_live = True
        self.new_activity = False
        self._reading_anchor: tuple[Static, float] | None = None
        self._viewport_refresh_pending = False
        self._restoring_viewport = False
        self._capture_after_scroll = False

    def _capture_reading_anchor(self) -> None:
        if not self.is_mounted:
            return
        # Focus/scroll animations retain fractional positions, while Textual
        # displays rows at the rounded scroll_offset. Anchor the visible row,
        # not a preceding row whose fractional tail is no longer on screen.
        visible_y = self.scroll_offset.y
        for child in self.children:
            if isinstance(child, Static) and child.virtual_region.bottom > visible_y:
                self._reading_anchor = (child, visible_y - child.virtual_region.y)
                return

    def hold_reading_position(self) -> None:
        """Hold history until the user explicitly returns live."""
        self.follow_live = False
        self._capture_reading_anchor()
        self.post_message(self.FollowChanged(self))

    def release_anchor(self) -> None:
        """Treat user scrolling and search navigation as an explicit hold."""
        super().release_anchor()
        if hasattr(self, "follow_live") and not self._restoring_viewport:
            # Explicit navigation may supersede a queued live/held refresh,
            # but only after it actually changes the scroll position.
            capture = self.follow_live or not self._viewport_refresh_pending
            self._capture_after_scroll = True
            # Textual releases again when a deferred scroll executes. If a
            # layout update moved the held message meanwhile, a no-op scroll
            # must not replace it with the row now occupying the old offset.
            # A genuine position change is captured by watch_scroll_y below.
            if capture:
                self.hold_reading_position()

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        if (hasattr(self, "follow_live") and not self.follow_live
                and not self._restoring_viewport
                and (self._capture_after_scroll or not self._viewport_refresh_pending)):
            self._capture_reading_anchor()
            self._capture_after_scroll = False

    def return_to_live(self) -> None:
        """Resume following without changing the draft or focus."""
        self.follow_live = True
        self.new_activity = False
        self._reading_anchor = None
        self._capture_after_scroll = False
        self.post_message(self.FollowChanged(self))
        self.refresh_reading_position()

    def action_scroll_end(self) -> None:
        """End in the transcript explicitly resumes following."""
        self.return_to_live()

    def refresh_reading_position(self) -> None:
        """Coalesce viewport updates after layout, preserving a held message."""
        if self.is_mounted and not self._viewport_refresh_pending:
            self._viewport_refresh_pending = True
            self.call_after_refresh(self._restore_viewport)

    def _restore_viewport(self) -> None:
        self._viewport_refresh_pending = False
        self._restoring_viewport = True
        try:
            if self.follow_live:
                self._scroll_to_bottom()
            elif self._reading_anchor is not None:
                child, offset = self._reading_anchor
                if child.parent is self:
                    self.scroll_to(
                        y=child.virtual_region.y + offset, animate=False,
                        immediate=True, force=True, release_anchor=False,
                    )
        finally:
            self._capture_after_scroll = False
            self._restoring_viewport = False

    def on_resize(self) -> None:
        """Retain the held message when earlier messages reflow."""
        self.refresh_reading_position()

    def _record_activity(self) -> None:
        if not self.follow_live and not self.new_activity:
            self.new_activity = True
            self.post_message(self.FollowChanged(self))
        self.refresh_reading_position()

    def _scroll_to_bottom(self: Self) -> None:
        """Scroll to the latest message."""
        if self.follow_live:
            self.scroll_end(animate=False, immediate=True)

    def _mount_widget(self: Self, widget: Static) -> None:
        """Mount a widget, falling back to direct append if not attached.

        Args:
            widget: Widget to add.
        """
        _perform_pane_operation(functools.partial(self.mount, widget), self, "_append", widget)

    def _try_scroll(self: Self) -> None:
        """Scroll to bottom, ignoring errors when not mounted."""
        with contextlib.suppress(Exception):
            self._scroll_to_bottom()

    # -- public API for adding messages --

    def _add_message_with_prefix(
        self: Self,
        prefix: str,
        text: str,
        *,
        trusted: bool = False,
    ) -> ChatMessage:
        """Add a message with the given prefix.

        Args:
            prefix: Rich markup prefix for the message.
            text: Message content.
            trusted: If True, render Rich markup in content. System-generated
                     messages use True; user/LLM content uses False.

        Returns:
            The created ChatMessage widget.
        """
        return self._add_message_widget(
            ChatMessage,
            prefix,
            text,
            trusted=trusted,
        )

    def add_user_message(self: Self, text: str) -> ChatMessage:
        """Add a user message (untrusted content, markup escaped).

        Args:
            text: Message content to display. Markup is escaped for security.

        Returns:
            The created ChatMessage widget.
        """
        return self._add_message_with_prefix(_USER_PREFIX, text)

    def add_system_message(self: Self, text: str, *, routine: bool = False, literal: bool = False) -> ChatMessage:
        """Add runtime or command output with explicit presentation metadata.

        Args:
            text: Message content to display.
            routine: Hide this row in quiet mode while retaining its content.
            literal: Preserve bracketed text instead of interpreting markup.

        Returns:
            The created ChatMessage widget.
        """
        return self._add_message_widget(ChatMessage, _SYSTEM_PREFIX, text, trusted=not literal, routine=routine)

    def add_error_message(self: Self, text: str) -> ChatMessage:
        """Add an error message (untrusted content, markup escaped).

        Args:
            text: Error message content to display. Markup is escaped for security.

        Returns:
            The created ChatMessage widget.
        """
        return self._add_message_with_prefix(_ERROR_PREFIX, text)

    def begin_agent_stream(self: Self, agent_name: str) -> ChatMessage:
        """Start a new streaming message for *agent_name*.

        Args:
            agent_name: Display name of the responding agent.

        Returns:
            The newly mounted ChatMessage widget.
        """
        prefix = _AGENT_PREFIX_TEMPLATE.format(name=agent_name)
        return self._add_message_widget(
            ChatMessage,
            prefix,
            "",
            tracking_dict=self._active,
            tracking_key=agent_name,
        )

    def append_agent_chunk(self: Self, agent_name: str, chunk: str) -> None:
        """Append a streaming chunk to an active agent message.

        Creates a new stream widget if none exists yet.

        Args:
            agent_name: Agent whose message to extend.
            chunk: Text chunk to append.

        Returns:
            None
        """
        if agent_name not in self._active:
            self.begin_agent_stream(agent_name)
        self._active[agent_name].append(chunk)
        self._record_activity()

    def finish_agent_stream(self: Self, agent_name: str) -> None:
        """Mark an agent's streaming message as complete.

        Finalizes the message widget with markdown rendering if applicable.

        Args:
            agent_name: Agent whose stream ended.

        Returns:
            None
        """
        widget = self._active.pop(agent_name, None)
        if widget is None:
            _LOGGER.debug("Attempted to finish non-existent agent stream: %s", agent_name)
            return
        widget.finalize_as_markdown()
        self.refresh_reading_position()

    def finish_thinking_stream(self: Self, agent_name: str) -> None:
        """Mark an agent's thinking stream as complete.

        Removes the thinking stream entry from the active tracking dict.

        Args:
            agent_name: Agent whose thinking stream ended.

        Returns:
            None
        """
        self._active_thinking.pop(agent_name, None)

    def _add_message_widget(
        self: Self,
        widget_class: type[_T],
        *args: Any,
        tracking_dict: dict[str, _T] | None = None,
        tracking_key: str | None = None,
        routine: bool = False,
        **kwargs: Any,
    ) -> _T:
        """Add a message widget to the chat pane.

        Args:
            widget_class: The widget class to instantiate.
            *args: Positional arguments for widget constructor.
            tracking_dict: Optional dictionary to track the widget.
            tracking_key: Key to use for tracking if tracking_dict is provided.
            **kwargs: Keyword arguments for widget constructor.

        Returns:
            The created widget.
        """
        kwargs.setdefault("output_mode", self.output_mode)
        widget = widget_class(*args, **kwargs)
        hidden = self.output_mode == "quiet" and (routine or isinstance(widget, ThinkingMessage))
        if hidden:
            widget.display = False
        self._mount_widget(widget)
        if not hidden:
            self._record_activity()

        if tracking_dict is not None and tracking_key is not None:
            tracking_dict[tracking_key] = widget

        return widget

    def _create_thinking_message(
        self: Self,
        widget_class: type[ThinkingMessage],
        thought: str,
        agent_name: str = "",
    ) -> ThinkingMessage:
        """Create a thinking message widget."""
        return self._add_message_widget(widget_class, thought, agent_name)

    add_thinking_message = functools.partialmethod(_create_thinking_message, ThinkingMessage)

    def begin_thinking_stream(self: Self, agent_name: str = "") -> ThinkingMessage:
        """Start a new streaming thinking message for *agent_name*.

        Args:
            agent_name: Display name of the thinking agent.

        Returns:
            The newly mounted ThinkingMessage widget.
        """
        return self._add_message_widget(
            ThinkingMessage,
            "",
            agent_name,
            tracking_dict=self._active_thinking,
            tracking_key=agent_name,
        )

    def append_thinking_chunk(self: Self, agent_name: str, chunk: str) -> None:
        """Append a streaming chunk to an active thinking message.

        Creates a new stream widget if none exists yet.

        Args:
            agent_name: Agent whose thinking to extend.
            chunk: Text chunk to append.

        Returns:
            None
        """
        if agent_name not in self._active_thinking:
            self.begin_thinking_stream(agent_name)
        self._active_thinking[agent_name].append(chunk)
        if self.output_mode != "quiet":
            self._record_activity()

    def _create_tool_message(
        self: Self,
        widget_class: type[ToolMessage],
        thought: str = "",
        tool_call: ToolCallProtocol | None = None,
    ) -> ToolMessage:
        """Create a tool message widget."""
        return self._add_message_widget(
            widget_class, thought, tool_call, expanded=self._detail_density == "detailed" and self.output_mode != "quiet",
        )

    add_tool_message = functools.partialmethod(_create_tool_message, ToolMessage)

    def record_tool_activity(self, message: Any, *, request: bool) -> ToolMessage:
        policy = runtime_evidence_redactor(self.app)
        record = self._tool_activity.observe(message, policy, request=request)
        if record.key not in self._tool_rows:
            self._tool_rows[record.key] = self._add_message_widget(
                ToolMessage, activity=record, expanded=self._detail_density == "detailed" and self.output_mode != "quiet",
            )
        self.refresh_tool_activity()
        self._record_activity()
        return self._tool_rows[record.key]

    def refresh_tool_activity(self) -> None:
        for key in self._tool_activity.changed:
            self._tool_rows[key]._update_renderable()

    def close_tool_activity(self, stream_id: str) -> None:
        self._tool_activity.close(stream_id)
        self.refresh_tool_activity()
        self._record_activity()

    def clear_thinking_messages(self: Self) -> None:
        """Remove all ``ThinkingMessage`` widgets from the pane.

        Returns:
            None
        """
        self._active_thinking = {}
        thinking = [child for child in self.children if isinstance(child, ThinkingMessage)]
        for widget in thinking:
            _perform_pane_operation(widget.remove, self, "_remove", widget)

    def clear_messages(self: Self) -> None:
        """Remove all messages from the pane.

        Returns:
            None
        """
        self._active = {}
        self._active_thinking = {}
        self._tool_activity.clear()
        self._tool_rows = {}
        if self.is_mounted:
            for pane in self.app.query(ToolPane):
                pane.bind_activity(self._tool_activity)
        _perform_pane_operation(self.remove_children, self, "_clear")
        self.return_to_live()


# ------------------------------------------------------------------ #
# Legacy RichLog panes                                                 #
# ------------------------------------------------------------------ #


class _BaseRichLogPane(RichLog):
    """Base class for RichLog panes with common initialization."""

    def __init__(self: Self, border_title: str = "Pane", **kwargs: Any) -> None:
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

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize pane with default border title."""
        super().__init__(border_title=self._DEFAULT_BORDER_TITLE, **kwargs)


class ThinkingPane(_TitledPane):
    """Pane for agent reasoning/thinking output."""

    _DEFAULT_BORDER_TITLE: str = "Thinking (legacy)"


class ToolPane(_TitledPane):
    """Bounded current projection of the transcript's shared tool evidence."""

    _DEFAULT_BORDER_TITLE: str = "Tools"

    def __init__(self, **kwargs: Any) -> None:
        self._activity_store: ToolActivityStore | None = None
        self._minimum_revision = 0
        self._projection = ""
        self._projecting = False
        kwargs.setdefault("max_lines", 4096)
        super().__init__(**kwargs)

    def bind_activity(self, store: ToolActivityStore) -> None:
        if self._activity_store is not store:
            self._minimum_revision = 0
        self._activity_store = store
        self.refresh()

    def on_mount(self) -> None:
        self.set_interval(0.5, self._refresh_visible_projection)

    def _refresh_visible_projection(self) -> None:
        if self.is_on_screen:
            self.refresh()

    def _sync_projection(self) -> None:
        if self._projecting or self._activity_store is None or not self.is_mounted:
            return
        text = self._activity_store.tool_view(runtime_evidence_redactor(self.app), self._minimum_revision)
        if text == self._projection:
            return
        self._projection = text
        self._projecting = True
        offset = self.scroll_offset
        try:
            super().clear()
            if text:
                super().write(Text(text), scroll_end=False)
            self.scroll_to(x=offset.x, y=offset.y, animate=False, immediate=True)
        finally:
            self._projecting = False

    def refresh(self, *regions: Region, repaint: bool = True, layout: bool = False, recompose: bool = False) -> Self:
        self._sync_projection()
        return super().refresh(*regions, repaint=repaint, layout=layout, recompose=recompose)

    def clear(self) -> Self:
        if not self._projecting:
            if self._activity_store is not None:
                self._minimum_revision = self._activity_store.revision + 1
            self._projection = ""
        return super().clear()


# ------------------------------------------------------------------ #
# Status bar                                                           #
# ------------------------------------------------------------------ #


class StatusBar(Static):
    """One-line status bar at the bottom of the screen."""

    status_text: reactive[str] = reactive("Ready")
    activity_text: reactive[str] = reactive("")
    notice_text: reactive[str] = reactive("")
    context_text: reactive[str] = reactive("")
    decision_action: reactive[bool] = reactive(False)
    tokens: reactive[int] = reactive(0)
    cost: reactive[float] = reactive(0.0)
    can_focus = True
    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [("enter", "pending_decision", "Decision")]

    def action_pending_decision(self) -> None:
        if self.decision_action:
            self.app.action_pending_decision()  # type: ignore[attr-defined]

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self.border_title = "Status"

    def render(self: Self) -> str:
        """Render the status bar.

        Returns:
            Formatted Rich markup string.
        """
        label = _safe_markup(self.activity_text) if self.activity_text else self.status_text
        parts = [f"[bold cyan]{label}[/]"]
        policy = runtime_evidence_redactor(self.app) if self.is_mounted else None
        if self.activity_text and self.notice_text:
            notice = policy.text(self.notice_text) if policy else self.notice_text
            parts.append(_safe_markup(notice))
        if self.activity_text and self.context_text:
            context = policy.text(self.context_text) if policy else self.context_text
            parts.append(f"[dim]{_safe_markup(context)}[/]")
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

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize the progress indicator.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self._message = ""
        self._kind = ""

    def show(self: Self, message: str = "Working...", kind: str = "agent") -> None:
        """Show the progress indicator with a message.

        Args:
            message: Status message to display.
            kind: Category of work (``agent``, ``tool``).

        Returns:
            None
        """
        self._message = message
        self._kind = kind
        self.add_class("visible")
        self.update(self.render())

    def hide(self: Self) -> None:
        """Hide the progress indicator.

        Returns:
            None
        """
        self._message = ""
        self._kind = ""
        self.remove_class("visible")
        self.update("")

    @property
    def is_visible(self: Self) -> bool:
        """Whether the indicator is currently displayed.

        Returns:
            True if showing.
        """
        return "visible" in self.classes

    def render(self: Self) -> str:
        """Render the progress line.

        Returns:
            Rich markup string.
        """
        if not self._message:
            return ""
        icon = _TOOL_PROGRESS_ICON if self._kind == "tool" else _PROGRESS_ICON
        return f"[dim]{icon} {self._message}[/]"


# ------------------------------------------------------------------ #
# Agent summary panel                                                  #
# ------------------------------------------------------------------ #


class AgentSummaryPanel(Static):
    """Panel displaying a summary of the agent's current state."""

    DEFAULT_CSS = """
    AgentSummaryPanel {
        height: auto;
        padding: 1;
    }
    """

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize the agent summary panel.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self._provider_name: str = ""
        self._model_name: str = ""
        self._mode: str = ""
        self._active_agent: str = ""
        self._tools: int | None = None

    def update_summary(
        self: Self,
        provider_name: str = "",
        model_name: str = "",
        mode: str = "",
        active_agent: str = "",
        tools: int | None = None,
    ) -> None:
        """Update the summary information.

        Args:
            provider_name: The provider name.
            model_name: The model name.
            mode: The current mode (Chat/Plan).
            active_agent: Selected actor identity, without implying execution.
            tools: Registered tool count, or None when unavailable.
        """
        self._provider_name = provider_name
        self._model_name = model_name
        self._mode = mode
        self._active_agent = active_agent
        self._tools = tools
        self.update(self.render())

    def render(self: Self) -> str:
        """Render the summary panel.

        Returns:
            Formatted summary string.
        """
        return (
            f"{self._provider_name}:{self._model_name} | "
            f"Mode: {self._mode} | Selected agent: {self._active_agent} | "
            f"Tools: {self._tools if self._tools is not None else 'unavailable'}"
        )


# ------------------------------------------------------------------ #
# Memory indicator                                                     #
# ------------------------------------------------------------------ #


class MemoryIndicator(Static):
    """Widget displaying memory usage and context size."""

    DEFAULT_CSS = """
    MemoryIndicator {
        height: auto;
        padding: 1;
    }
    """

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize the memory indicator.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self._session_messages: int = 0
        self._history_entries: int = 0
        self._context_loaded: bool = False

    def update_counts(
        self: Self,
        session_messages: int = 0,
        history_entries: int = 0,
        context_loaded: bool = False,
    ) -> None:
        """Update memory usage counts.

        Args:
            session_messages: Number of messages in session.
            history_entries: Number of history entries.
            context_loaded: Whether context is loaded.
        """
        self._session_messages = session_messages
        self._history_entries = history_entries
        self._context_loaded = context_loaded
        self.update(self.render())

    def render(self: Self) -> str:
        """Render the memory indicator.

        Returns:
            Formatted string with memory stats.
        """
        ctx = "loaded" if self._context_loaded else "not loaded"
        return (
            f"Session: {self._session_messages} msgs | "
            f"History: {self._history_entries} entries | "
            f"Context: {ctx}"
        )


# ------------------------------------------------------------------ #
# Settings panel                                                       #
# ------------------------------------------------------------------ #


class SettingsPanel(Static):
    """Panel displaying current settings."""

    DEFAULT_CSS = """
    SettingsPanel {
        height: auto;
        padding: 1;
    }
    """

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize the settings panel.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self._theme: str = ""
        self._auto_mode: bool = False
        self._provider: str = ""
        self._mcp_servers: int = 0

    def update_settings(
        self: Self,
        theme: str = "",
        auto_mode: bool = False,
        provider: str = "",
        mcp_servers: int = 0,
    ) -> None:
        """Update the settings display.

        Args:
            theme: UI theme name.
            auto_mode: Whether auto mode is enabled.
            provider: Active provider name.
            mcp_servers: Number of MCP servers.
        """
        self._theme = theme
        self._auto_mode = auto_mode
        self._provider = provider
        self._mcp_servers = mcp_servers
        self.update(self.render())

    def render(self: Self) -> str:
        """Render the settings panel.

        Returns:
            Formatted settings string.
        """
        auto = "enabled" if self._auto_mode else "disabled"
        return (
            f"Theme: {self._theme} | Auto: {auto} | "
            f"Provider: {self._provider} | MCP: {self._mcp_servers}"
        )


# ------------------------------------------------------------------ #
# Skill panel                                                          #
# ------------------------------------------------------------------ #


class SkillPanel(Static):
    """Panel displaying available skills."""

    DEFAULT_CSS = """
    SkillPanel {
        height: auto;
        padding: 1;
    }
    """

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize the skill panel.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self._skills: list[str] = []

    def set_skills(self: Self, skills: list[str]) -> None:
        """Set the skill list.

        Args:
            skills: List of skill names.
        """
        self._skills = list(skills)
        self.update(self.render())

    def render(self: Self) -> str:
        """Render the skill panel.

        Returns:
            Formatted skills string.
        """
        return "\n".join(f"  - {s}" for s in self._skills) if self._skills else "No skills"


# ------------------------------------------------------------------ #
# Task list widget                                                     #
# ------------------------------------------------------------------ #


class TaskListWidget(Static):
    """Widget displaying the current task list."""

    DEFAULT_CSS = """
    TaskListWidget {
        height: auto;
        padding: 1;
    }
    """

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize the task list widget.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self._tasks: list[str] = []

    def set_tasks(self: Self, tasks: list[str]) -> None:
        """Set the task list.

        Args:
            tasks: List of task descriptions.
        """
        self._tasks = list(tasks)
        self.update(self.render())

    def render(self: Self) -> str:
        """Render the task list widget.

        Returns:
            Formatted task list string.
        """
        return "\n".join(f"  - {t}" for t in self._tasks) if self._tasks else "No tasks"


# ------------------------------------------------------------------ #
# Team panel                                                           #
# ------------------------------------------------------------------ #


class TeamPanel(Static):
    """Panel displaying team member information."""

    DEFAULT_CSS = """
    TeamPanel {
        height: auto;
        padding: 1;
    }
    """

    def __init__(self: Self, **kwargs: Any) -> None:
        """Initialize the team panel.

        Args:
            **kwargs: Forwarded to ``Static``.
        """
        super().__init__(**kwargs)
        self._workspaces: list[str] = []

    def set_workspaces(self: Self, workspaces: list[str]) -> None:
        """Set the workspace list.

        Args:
            workspaces: List of workspace descriptions.
        """
        self._workspaces = list(workspaces)
        self.update(self.render())

    def render(self: Self) -> str:
        """Render the team panel.

        Returns:
            Formatted team workspace string.
        """
        return "\n".join(f"  - {w}" for w in self._workspaces) if self._workspaces else "No teams"
