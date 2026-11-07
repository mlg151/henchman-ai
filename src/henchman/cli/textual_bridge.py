"""Console adapter and event bridge for the Textual TUI.

``TuiConsoleAdapter`` redirects Rich Console output into the TUI chat
pane.  ``EventBridge`` translates ``AgentEvent`` objects into Textual
``Message`` instances and posts them to the app.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeAlias, cast
from uuid import uuid4

from rich.console import Console as RichConsole
from rich.errors import MarkupError
from rich.text import Text
from textual.message import Message

from henchman.cli.evidence import runtime_evidence_redactor
from henchman.cli.textual_messages import (
    AgentContentMessage,
    AgentFinishedMessage,
    AgentStatusMessage,
    AgentThoughtMessage,
    CommandOutputMessage,
    ToolActivityClosedMessage,
    ToolCallRequestMessage,
    ToolCallResultMessage,
    ToolConfirmationMessage,
)
from henchman.cli.textual_widgets import StatusBar
from henchman.core.event_evidence import EventEvidenceRedactor
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall
from henchman.utils.evidence_redaction import EvidenceRedactor, EvidenceStreamRedactor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable

    from rich.console import ConsoleOptions, RenderableType
    from rich.segment import Segment

    from henchman.cli.textual_app import HenchmanTextualApp

# Type aliases for better readability
MessageClass: TypeAlias = type[Message]
DataTransformer: TypeAlias = Callable[[Any], Any] | None

# ------------------------------------------------------------------ #
# TUI Console Adapter                                                  #
# ------------------------------------------------------------------ #


try:
    from typing import Self
except ImportError:  # pragma: no cover
    from typing import Self


class _AnsiPlainText:
    """Discard ANSI controls, retaining only bounded parser state across writes."""

    def __init__(self) -> None:
        self._state = "text"

    def feed(self, value: str) -> str:
        output = []
        for char in value:
            if self._state == "text":
                if char == "\x1b":
                    self._state = "escape"
                elif char in ("\x9b", "\x9d"):
                    self._state = "csi" if char == "\x9b" else "osc"
                else:
                    output.append(char)
            elif self._state == "escape":
                self._state = {"[": "csi", "]": "osc"}.get(char, "text")
            elif self._state == "csi":
                if "@" <= char <= "~":
                    self._state = "text"
            elif self._state == "osc":
                if char in ("\x07", "\x9c"):
                    self._state = "text"
                elif char == "\x1b":
                    self._state = "osc_escape"
            else:
                self._state = "text" if char == "\\" else "osc"
        return "".join(output)


class _EvidenceConsole(RichConsole):
    """Project text before Rich can wrap, crop, or consume its markup."""

    def __init__(self, policy: Callable[[], EvidenceRedactor], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._policy = policy
        self._raw_stream: EvidenceStreamRedactor | None = None
        self._visible_stream: EvidenceStreamRedactor | None = None
        self._ansi = _AnsiPlainText()

    @staticmethod
    def _replace_text(original: Text, value: str) -> Text:
        if value == original.plain:
            return original
        # A changed projection cannot reuse offsets into the original spans.
        return Text(
            value, style=original.style, justify=original.justify,
            overflow=original.overflow, no_wrap=original.no_wrap,
            end=original.end, tab_size=original.tab_size,
        )

    def render_str(self, text: str, **kwargs: Any) -> Text:
        policy = self._policy()
        safe = _AnsiPlainText().feed(policy.text(text))
        rendered = self._render_projected_str(text, safe, kwargs)
        return self._replace_text(rendered, policy.text(rendered.plain))

    def _render_projected_str(self, original: str, safe: str, options: dict[str, Any]) -> Text:
        try:
            return super().render_str(safe, **options)
        except MarkupError:
            if safe == original:
                raise
            # Masking an opening tag can leave its closing tag unmatched.
            # Preserve the safe evidence literally in that case.
            return super().render_str(safe, **{**options, "markup": False})

    def render(
        self, renderable: RenderableType, options: ConsoleOptions | None = None,
    ) -> Iterable[Segment]:
        if isinstance(renderable, Text):
            plain = _AnsiPlainText().feed(self._policy().text(renderable.plain))
            renderable = self._replace_text(renderable, self._policy().text(plain))
        yield from super().render(renderable, options)

    def _stream_text(self, value: str | Text, options: dict[str, Any]) -> Text:
        assert self._raw_stream is not None and self._visible_stream is not None
        original = value.plain if isinstance(value, Text) else value
        safe = self._ansi.feed(self._raw_stream.feed(original))
        if isinstance(value, Text):
            rendered = self._replace_text(value, safe)
        else:
            rendered = self._render_projected_str(original, safe, {
                key: options[key] for key in ("markup", "highlight", "emoji", "justify")
                if key in options
            })
        return self._replace_text(rendered, self._visible_stream.feed(rendered.plain))

    def _finish_text(self) -> None:
        if self._raw_stream is not None and self._visible_stream is not None:
            pending = self._ansi.feed(self._raw_stream.finish())
            pending = self._visible_stream.feed(pending) + self._visible_stream.finish()
            if pending:
                super().print(Text(pending), end="")
        self._ansi = _AnsiPlainText()

    def print(self, *objects: Any, **kwargs: Any) -> None:
        policy = self._policy()
        policy.register_config(objects)
        if self._raw_stream is None or self._raw_stream.redactor is not policy:
            self._finish_text()
            self._raw_stream = EvidenceStreamRedactor(policy)
            self._visible_stream = EvidenceStreamRedactor(policy)
        if all(isinstance(value, (str, Text)) for value in objects):
            options = kwargs.copy()
            separator = options.pop("sep", " ")
            ending = options.pop("end", "\n")
            projected = []
            for index, value in enumerate(objects):
                if index:
                    projected.append(self._stream_text(Text(separator), options))
                projected.append(self._stream_text(value, options))
            projected.append(self._stream_text(Text(ending), options))
            super().print(*projected, sep="", end="", **options)
        else:
            self._finish_text()
            super().print(*objects, **kwargs)


class TuiConsoleAdapter:
    """Intercepts Rich Console output and forwards it to the chat pane.

    Replaces the invisible stdout-backed console so that slash-command
    output, errors, and status messages appear inside the TUI.
    """

    def __init__(self: Self, app: HenchmanTextualApp) -> None:
        """Initialize.

        Args:
            app: The Textual application.
        """
        self._app = app
        self._evidence_stream: EvidenceStreamRedactor | None = None
        self._ansi = _AnsiPlainText()
        self._buf = io.StringIO()
        self._rich_console = _EvidenceConsole(
            lambda: runtime_evidence_redactor(self._app),
            file=self._buf,
            force_terminal=True,
            no_color=False,
            markup=True,
            highlight=True,
        )

    @property
    def console(self: Self) -> RichConsole:
        """The underlying Rich Console wired to the buffer.

        Returns:
            RichConsole instance.
        """
        return self._rich_console

    def flush_to_chat(self: Self) -> None:
        """Read accumulated buffer and post to the chat pane.

        Returns:
            None
        """
        text = self._buf.getvalue()
        if text:
            policy = runtime_evidence_redactor(self._app)
            if self._evidence_stream is None or self._evidence_stream.redactor is not policy:
                if self._evidence_stream is not None:
                    pending = self._evidence_stream.finish()
                    if pending:
                        self._app.post_message(CommandOutputMessage(pending))
                self._evidence_stream = EvidenceStreamRedactor(policy)
            # Final guard for custom renderables and sensitive hyperlink targets.
            plain = self._ansi.feed(text)
            safe = self._evidence_stream.feed(plain)
            shown = text if safe == plain and policy.text(text) == text else safe
            shown = shown.rstrip("\r\n")
            if shown:
                self._app.post_message(CommandOutputMessage(shown))
        self._buf.seek(0)
        self._buf.truncate(0)

    def print(self: Self, *args: Any, **kwargs: Any) -> None:
        """Write to the buffer and flush to chat.

        Args:
            *args: Positional args for ``Console.print``.
            **kwargs: Keyword args for ``Console.print``.

        Returns:
            None
        """
        runtime_evidence_redactor(self._app).register_config(args)
        self._rich_console.print(*args, **kwargs)
        self.flush_to_chat()


# ------------------------------------------------------------------ #
# Module-level helpers (exempt from Feature-Envy checks)             #
# ------------------------------------------------------------------ #


def _build_message_from_event(
    event: AgentEvent,
    message_class: MessageClass,
    prefix: str = "",
    transform_data: DataTransformer = None,
) -> Message | None:
    """Build a Textual message from *event*, returning ``None`` if no data.

    Args:
        event: The AgentEvent containing data.
        message_class: The Textual message class to instantiate.
        prefix: Optional prefix prepended to the event data string.
        transform_data: Optional callable to transform event data before use.

    Returns:
        A ready-to-post ``Message`` instance, or ``None`` when event has no data.
    """
    if not event.data:
        return None
    data = transform_data(event.data) if transform_data else event.data
    if message_class is ToolCallResultMessage:
        return ToolCallResultMessage(data, event.source_agent)
    data_str = f"{prefix}{data}" if prefix else str(data)
    msg_class = cast("type[Any]", message_class)
    return cast(Message, msg_class(data_str, event.source_agent))


def _extract_dict_field(
    event: AgentEvent,
    key: str,
    default: str = "",
) -> str:
    """Extract a string value from *event.data* when it is a dictionary.

    Args:
        event: The AgentEvent whose ``data`` attribute is inspected.
        key: The dictionary key to look up.
        default: Fallback value returned when the key is absent or data is
            not a dict.

    Returns:
        The string value for *key*, or *default*.
    """
    if event.data and isinstance(event.data, dict):
        value = event.data.get(key)
        return str(value) if value is not None else default
    return default


# ------------------------------------------------------------------ #
# Message Poster Helper                                                 #
# ------------------------------------------------------------------ #


class MessagePoster:
    """Helper class for posting messages to the Textual UI.

    Extracted from EventBridge to reduce class size and improve cohesion.
    """

    def __init__(self: Self, app: HenchmanTextualApp) -> None:
        """Initialize.

        Args:
            app: Target Textual application.
        """
        self.app = app
        self.stream_id = uuid4().hex
        self.has_tool_activity = False

    def post(self: Self, message: Message) -> None:
        """Post a message to the Textual app.

        Args:
            message: The Textual message to post.

        Returns:
            None
        """
        if isinstance(message, (ToolCallRequestMessage, ToolCallResultMessage)):
            message.stream_id = self.stream_id
            self.has_tool_activity = True
        self.app.post_message(message)

    def post_message(
        self: Self,
        event: AgentEvent,
        message_class: MessageClass,
        prefix: str = "",
        transform_data: DataTransformer = None,
    ) -> None:
        """Build and post a message from *event* data if present.

        Args:
            event: The AgentEvent containing data.
            message_class: The Textual message class to instantiate.
            prefix: Optional prefix prepended to event data.
            transform_data: Optional callable to transform event data.

        Returns:
            None
        """
        msg = _build_message_from_event(event, message_class, prefix, transform_data)
        if msg is not None:
            self.post(msg)

    def post_status_message(self: Self, event: AgentEvent, text: str) -> None:
        """Post an AgentStatusMessage with given text.

        Args:
            event: The AgentEvent for source agent.
            text: The status text to display.

        Returns:
            None
        """
        self.post(AgentStatusMessage(text, event.source_agent))


# ------------------------------------------------------------------ #
# Event Bridge                                                         #
# ------------------------------------------------------------------ #

# Error keywords that indicate an authentication issue.
_AUTH_ERROR_KEYWORDS = ("API key", "authentication")


class EventBridge:
    """Forwards ``AgentEvent`` objects to the Textual UI.

    All ``EventType`` variants are handled via a dispatch table so
    that new event types only require a single-line addition.
    """

    def __init__(self: Self, app: HenchmanTextualApp) -> None:
        """Initialize.

        Args:
            app: Target Textual application.
        """
        self.app = app
        self._message_poster = MessagePoster(app)
        self._evidence = EventEvidenceRedactor(runtime_evidence_redactor(app))
        self._handlers: dict[EventType, Callable[[AgentEvent], None]] = (
            self._build_handler_registry()
        )

    # -- public API --

    async def forward_events(
        self: Self,
        event_stream: AsyncIterator[AgentEvent],
    ) -> None:
        """Forward all events from *event_stream* to the TUI.

        Args:
            event_stream: Async iterator of ``AgentEvent``.

        Returns:
            None
        """
        self._message_poster.stream_id = uuid4().hex
        self._message_poster.has_tool_activity = False
        try:
            async for event in event_stream:
                for safe in self._evidence.project(event):
                    if safe.type == EventType.TOOL_CALL_REQUEST and isinstance(event.data, ToolCall):
                        safe.data = ToolCall(**safe.data)
                    self._dispatch(safe)
        except Exception as exc:
            import traceback

            for safe in self._evidence.flush():
                self._dispatch(safe)
            details = self._evidence.redactor.text(traceback.format_exc())
            message = self._evidence.redactor.text(str(exc))
            # Escape triple backticks in traceback to prevent code fence breakout
            safe_details = details.replace("```", "` ` `")
            self._message_poster.post(AgentStatusMessage(f"Stream error: {message}"))
            self._message_poster.post(
                AgentContentMessage(
                    f"❌ Stream error: {message}\n```\n{safe_details}\n```",
                ),
            )
        finally:
            for safe in self._evidence.flush():
                self._dispatch(safe)
            if self._message_poster.has_tool_activity:
                self._message_poster.post(ToolActivityClosedMessage(self._message_poster.stream_id))

    # -- internal helpers --

    def _dispatch(self: Self, event: AgentEvent) -> None:
        """Route a single event to its handler.

        Args:
            event: The event to dispatch.

        Returns:
            None
        """
        handler = self._handlers.get(event.type)
        if handler:
            handler(event)
            return
        self._message_poster.post_status_message(
            event,
            f"Unhandled event type: {event.type}",
        )

    # -- handler registry --

    def _build_handler_registry(
        self: Self,
    ) -> dict[EventType, Callable[[AgentEvent], None]]:
        """Build the event-type → handler mapping.

        Returns:
            Dictionary mapping ``EventType`` to handler callables.
        """
        return {
            **self._build_core_handlers(),
            **self._build_agent_and_thinking_handlers(),
        }

    def _build_core_handlers(
        self: Self,
    ) -> dict[EventType, Callable[[AgentEvent], None]]:
        """Build handlers for core content, tool, and status events.

        Returns:
            Partial event-type → handler mapping for core events.
        """
        return {
            EventType.CONTENT: self._create_handler(message_class=AgentContentMessage),
            EventType.THOUGHT: self._create_handler(message_class=AgentThoughtMessage),
            EventType.TOOL_CALL_REQUEST: self._on_tool_req,
            EventType.TOOL_CALL_RESULT: self._create_handler(
                message_class=ToolCallResultMessage,
            ),
            EventType.TOOL_CONFIRMATION: self._create_handler(
                message_class=ToolConfirmationMessage,
            ),
            EventType.ERROR: self._on_error,
            EventType.FINISHED: self._on_finished,
            EventType.CONTEXT_COMPACTED: self._on_ctx_compact,
            EventType.TURN_SUMMARIZED: self._create_handler(
                status_text="Previous turn summarized",
            ),
            EventType.TURN_STATUS: self._on_turn_status,
        }

    def _build_agent_and_thinking_handlers(
        self: Self,
    ) -> dict[EventType, Callable[[AgentEvent], None]]:
        """Build handlers for multi-agent and thinking events.

        Returns:
            Partial event-type → handler mapping for agent/thinking events.
        """
        return {
            EventType.AGENT_STARTED: self._on_agent_start,
            EventType.AGENT_COMPLETED: self._on_agent_done,
            EventType.AGENT_DELEGATED: self._on_delegated,
            EventType.AGENT_MESSAGE: self._on_agent_msg,
            EventType.THINKING_STARTED: self._create_handler(status_text="Thinking…"),
            EventType.THINKING_COMPLETED: self._create_handler(
                status_text="Thinking complete",
            ),
            EventType.THINKING_REQUIRED: self._create_handler(
                status_text="⚠ Thinking pattern missing in response",
            ),
            EventType.DELEGATION_DECISION: self._create_handler(
                prefix="Delegation decision: ",
            ),
            EventType.REFLECTION: self._create_handler(prefix="Reflection: "),
        }

    # -- helper methods for event handling --

    def _update_status_bar(self: Self, event_data: dict[str, Any]) -> None:
        """Update status bar with token and cost information.

        Args:
            event_data: Dictionary containing tokens and cost data.

        Returns:
            None
        """
        tokens = event_data.get("tokens")
        cost = event_data.get("cost")
        if tokens or cost:
            try:
                bar = self.app.query_one("#status-bar", StatusBar)
                if tokens:
                    bar.tokens = int(tokens)
                if cost:
                    bar.cost = float(cost)
            except Exception:
                pass

    # -- factory methods for event handlers --

    def _create_handler(
        self: Self,
        *,
        message_class: type[Any] | None = None,
        status_text: str | None = None,
        prefix: str | None = None,
    ) -> Callable[[AgentEvent], None]:
        """Create a handler for different types of events.

        Args:
            message_class: The message class to use for posting (for data/tool messages).
            status_text: The status text to display (for status messages).
            prefix: The prefix to add before event data (for prefixed messages).

        Returns:
            A handler function for AgentEvent.

        Raises:
            ValueError: If no valid handler type is specified.
        """
        if message_class is not None:

            def handler(event: AgentEvent) -> None:
                self._message_poster.post_message(event, message_class)

            return handler
        if status_text is not None:

            def handler(event: AgentEvent) -> None:
                self._message_poster.post_status_message(event, status_text)

            return handler
        if prefix is not None:

            def handler(event: AgentEvent) -> None:
                self._message_poster.post_message(
                    event,
                    AgentThoughtMessage,
                    prefix=prefix,
                )

            return handler
        msg = "Must specify one of: message_class, status_text, or prefix"
        raise ValueError(msg)

    # -- individual event handlers --

    def _on_tool_req(self: Self, event: AgentEvent) -> None:
        """Handle TOOL_CALL_REQUEST events.

        Returns:
            None
        """
        data = event.data
        if data:
            self._message_poster.post(ToolCallRequestMessage(data, event.source_agent))

    def _on_error(self: Self, event: AgentEvent) -> None:
        """Handle ERROR events.

        Returns:
            None
        """
        data = event.data
        if not data:
            return
        msg = _format_error_text(str(data))
        self._message_poster.post_status_message(event, f"Error: {msg}")
        self._message_poster.post(AgentContentMessage(f"❌ {msg}", event.source_agent))

    def _on_finished(self: Self, event: AgentEvent) -> None:
        """Handle FINISHED events.

        Returns:
            None
        """
        finished_msg = AgentFinishedMessage(event.source_agent)
        self._message_poster.post(finished_msg)

    def _on_ctx_compact(self: Self, event: AgentEvent) -> None:
        """Handle CONTEXT_COMPACTED events.

        Returns:
            None
        """
        self._message_poster.post_status_message(
            event,
            "Context compacted to fit model limits",
        )
        compacted_notice = "[dim]ℹ Context window was compacted.[/dim]"
        self._message_poster.post(CommandOutputMessage(compacted_notice))

    def _on_turn_status(self: Self, event: AgentEvent) -> None:
        """Handle TURN_STATUS events.

        Returns:
            None
        """
        data = event.data
        if not (data and isinstance(data, dict)):
            return
        status = _format_turn_status(data)
        self._message_poster.post_status_message(event, status)
        self._update_status_bar(data)

    def _on_agent_start(self: Self, event: AgentEvent) -> None:
        """Handle AGENT_STARTED events.

        Returns:
            None
        """
        if not (event.data and isinstance(event.data, dict)):
            return
        name = _extract_dict_field(event, "agent", "unknown")
        self._message_poster.post_status_message(event, f"⚙ {name} working…")

    def _on_agent_done(self: Self, event: AgentEvent) -> None:
        """Handle AGENT_COMPLETED events.

        Returns:
            None
        """
        if not (event.data and isinstance(event.data, dict)):
            return
        name = _extract_dict_field(event, "agent", "unknown")
        summary = _extract_dict_field(event, "summary", "")
        status = event.data.get("status")
        match status:
            case "completed":
                completion_msg = f"{name} finished execution"
            case "responded":
                completion_msg = f"{name} responded"
            case "failed":
                completion_msg = f"✗ {name} failed"
            case "stalled":
                completion_msg = f"⚠ {name} stalled — no actions taken after nudges"
            case "timed_out":
                completion_msg = f"⚠ {name} hit turn limit"
            case "no_work_done":
                completion_msg = f"⚠ {name} ended without making changes"
            case _:
                completion_msg = f"⚠ {name} ended — outcome unknown"
        if summary:
            completion_msg += f": {summary}"
        self._message_poster.post_status_message(event, completion_msg)

    def _on_delegated(self: Self, event: AgentEvent) -> None:
        """Handle AGENT_DELEGATED events.

        Returns:
            None
        """
        if not (event.data and isinstance(event.data, dict)):
            return
        from_a = _extract_dict_field(event, "from", "?")
        to_a = _extract_dict_field(event, "to", "?")
        reason = _extract_dict_field(event, "reason", "")
        text = f"[dim]↳ Delegating: {from_a} → {to_a}"
        if reason:
            text += f" ({reason})"
        text += "[/dim]"
        self._message_poster.post(CommandOutputMessage(text))
        self._message_poster.post_status_message(event, f"{from_a} → {to_a}")

    def _on_agent_msg(self: Self, event: AgentEvent) -> None:
        """Handle AGENT_MESSAGE events.

        Returns:
            None
        """
        if event.data:
            self._message_poster.post(
                CommandOutputMessage(f"[dim]📨 {event.data}[/dim]"),
            )


# ------------------------------------------------------------------ #
# Module-level formatting helpers                                      #
# ------------------------------------------------------------------ #

# Keyword groups for detecting authentication errors.
_AUTH_KEYWORD_GROUPS: list[list[str]] = [
    ["api", "key"],
    ["authentication"],
    ["unauthorized"],
]

# Words that confirm a message is an error, not a success notice.
_NEGATIVE_INDICATORS: tuple[str, ...] = (
    "invalid",
    "missing",
    "failed",
    "error",
    "unauthorized",
    "no ",
    "not ",
    "required",
)


def _format_error_text(error_text: str) -> str:
    """Format error message, handling API-auth special case.

    Args:
        error_text: Raw error text.

    Returns:
        Formatted error message.
    """
    lower = error_text.lower()
    is_negative = any(ind in lower for ind in _NEGATIVE_INDICATORS)
    if is_negative and any(all(kw in lower for kw in group) for group in _AUTH_KEYWORD_GROUPS):
        return "❌ API Error: Invalid or missing API key."
    return error_text


def _format_turn_status(data: dict[str, Any]) -> str:
    """Format a turn-status dictionary into a display string.

    Args:
        data: Dictionary with turn status information.

    Returns:
        Formatted status string.
    """
    iteration = data.get("iteration", "?")
    max_iter = data.get("max_iterations", "?")
    tokens = data.get("tokens")
    status = f"Turn {iteration}/{max_iter}"
    if tokens:
        status += f" | {tokens} tokens"
    return status
