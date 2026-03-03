"""Console adapter and event bridge for the Textual TUI.

``TuiConsoleAdapter`` redirects Rich Console output into the TUI chat
pane.  ``EventBridge`` translates ``AgentEvent`` objects into Textual
``Message`` instances and posts them to the app.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Any

from rich.console import Console as RichConsole
from textual.message import Message

from henchman.cli.textual_messages import (
    AgentContentMessage,
    AgentFinishedMessage,
    AgentStatusMessage,
    AgentThoughtMessage,
    CommandOutputMessage,
    ToolCallRequestMessage,
    ToolCallResultMessage,
    ToolConfirmationMessage,
)
from henchman.cli.textual_widgets import StatusBar
from henchman.core.events import AgentEvent, EventType

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from henchman.cli.textual_app import HenchmanTextualApp

# ------------------------------------------------------------------ #
# TUI Console Adapter                                                  #
# ------------------------------------------------------------------ #


class TuiConsoleAdapter:
    """Intercepts Rich Console output and forwards it to the chat pane.

    Replaces the invisible stdout-backed console so that slash-command
    output, errors, and status messages appear inside the TUI.
    """

    def __init__(self, app: HenchmanTextualApp) -> None:
        """Initialize.

        Args:
            app: The Textual application.
        """
        self._app = app
        self._buf = io.StringIO()
        self._rich_console = RichConsole(
            file=self._buf,
            force_terminal=True,
            no_color=False,
            markup=True,
            highlight=True,
        )

    @property
    def console(self) -> RichConsole:
        """The underlying Rich Console wired to the buffer.

        Returns:
            RichConsole instance.
        """
        return self._rich_console

    def flush_to_chat(self) -> None:
        """Read accumulated buffer and post to the chat pane."""
        text = self._buf.getvalue()
        if text.strip():
            self._app.post_message(CommandOutputMessage(text.strip()))
        self._buf.seek(0)
        self._buf.truncate(0)

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Write to the buffer and flush to chat.

        Args:
            *args: Positional args for ``Console.print``.
            **kwargs: Keyword args for ``Console.print``.
        """
        self._rich_console.print(*args, **kwargs)
        self.flush_to_chat()


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

    def __init__(self, app: HenchmanTextualApp) -> None:
        """Initialize.

        Args:
            app: Target Textual application.
        """
        self.app = app
        self._handlers: dict[EventType, Callable[[AgentEvent], None]] = (
            self._build_handler_registry()
        )

    # -- public API --

    async def forward_events(self, event_stream: AsyncIterator[AgentEvent]) -> None:
        """Forward all events from *event_stream* to the TUI.

        Args:
            event_stream: Async iterator of ``AgentEvent``.
        """
        try:
            async for event in event_stream:
                self._dispatch(event)
        except Exception as exc:
            import traceback

            details = traceback.format_exc()
            # Escape triple backticks in traceback to prevent code fence breakout
            safe_details = details.replace("```", "` ` `")
            self._post(AgentStatusMessage(f"Stream error: {exc}"))
            self._post(AgentContentMessage(f"❌ Stream error: {exc}\n```\n{safe_details}\n```"))

    # -- internal helpers --

    def _post(self, message: Message) -> None:
        """Post a message to the Textual app.

        Args:
            message: The Textual message to post.
        """
        self.app.post_message(message)

    def _dispatch(self, event: AgentEvent) -> None:
        """Route a single event to its handler.

        Args:
            event: The event to dispatch.
        """
        handler = self._handlers.get(event.type)
        if handler:
            handler(event)
            return
        self._post(
            AgentStatusMessage(
                f"Unhandled event type: {event.type}",
                event.source_agent,
            )
        )

    # -- handler registry --

    def _build_handler_registry(
        self,
    ) -> dict[EventType, Callable[[AgentEvent], None]]:
        """Build the event-type → handler mapping.

        Returns:
            Dictionary mapping ``EventType`` to handler callables.
        """
        return {
            EventType.CONTENT: self._on_content,
            EventType.THOUGHT: self._on_thought,
            EventType.TOOL_CALL_REQUEST: self._on_tool_req,
            EventType.TOOL_CALL_RESULT: self._on_tool_res,
            EventType.TOOL_CONFIRMATION: self._on_tool_confirm,
            EventType.ERROR: self._on_error,
            EventType.FINISHED: self._on_finished,
            EventType.CONTEXT_COMPACTED: self._on_ctx_compact,
            EventType.TURN_SUMMARIZED: self._on_turn_summary,
            EventType.TURN_STATUS: self._on_turn_status,
            EventType.AGENT_STARTED: self._on_agent_start,
            EventType.AGENT_COMPLETED: self._on_agent_done,
            EventType.AGENT_DELEGATED: self._on_delegated,
            EventType.AGENT_MESSAGE: self._on_agent_msg,
            EventType.THINKING_STARTED: self._on_think_start,
            EventType.THINKING_COMPLETED: self._on_think_done,
            EventType.THINKING_REQUIRED: self._on_think_req,
            EventType.DELEGATION_DECISION: self._on_deleg_dec,
            EventType.REFLECTION: self._on_reflection,
        }

    # -- helper methods for event handling --

    def _post_data_message(
        self, event: AgentEvent, message_class: type[Any], prefix: str = ""
    ) -> None:
        """Post a message with event data if present.

        Args:
            event: The AgentEvent containing data.
            message_class: The Textual message class to instantiate.
            prefix: Optional prefix to add before event data.
        """
        if event.data:
            data_str = str(event.data)
            if prefix:
                data_str = f"{prefix}{data_str}"
            self._post(message_class(data_str, event.source_agent))

    def _post_prefixed_message(self, event: AgentEvent, prefix: str) -> None:
        """Post a prefixed message using AgentThoughtMessage.

        Args:
            event: The AgentEvent containing data.
            prefix: The prefix to add before event data.
        """
        self._post_data_message(event, AgentThoughtMessage, prefix)

    def _post_tool_message(self, event: AgentEvent, message_class: type[Any]) -> None:
        """Post a tool-related message with event data if present.

        Args:
            event: The AgentEvent containing tool data.
            message_class: The Textual message class for tools.
        """
        if event.data:
            self._post(message_class(event.data, event.source_agent))

    def _post_status_message(self, event: AgentEvent, text: str) -> None:
        """Post an AgentStatusMessage with given text.

        Args:
            event: The AgentEvent for source agent.
            text: The status text to display.
        """
        self._post(AgentStatusMessage(text, event.source_agent))



    def _update_status_bar(self, event_data: dict[str, Any]) -> None:
        """Update status bar with token and cost information.

        Args:
            event_data: Dictionary containing tokens and cost data.
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

    def _extract_from_dict(self, event: AgentEvent, key: str, default: str = "") -> str:
        """Extract a string value from event.data dictionary.

        Args:
            event: The AgentEvent containing a dictionary.
            key: The dictionary key to extract.
            default: Default value if key not found.

        Returns:
            The extracted value or default.
        """
        if event.data and isinstance(event.data, dict):
            value = event.data.get(key)
            return str(value) if value is not None else default
        return default

    # -- individual event handlers --

    def _on_content(self, event: AgentEvent) -> None:
        """Handle CONTENT events."""
        self._post_data_message(event, AgentContentMessage)

    def _on_thought(self, event: AgentEvent) -> None:
        """Handle THOUGHT events."""
        self._post_data_message(event, AgentThoughtMessage)

    def _on_tool_req(self, event: AgentEvent) -> None:
        """Handle TOOL_CALL_REQUEST events."""
        self._post_tool_message(event, ToolCallRequestMessage)

    def _on_tool_res(self, event: AgentEvent) -> None:
        """Handle TOOL_CALL_RESULT events."""
        self._post_tool_message(event, ToolCallResultMessage)

    def _on_tool_confirm(self, event: AgentEvent) -> None:
        """Handle TOOL_CONFIRMATION events."""
        self._post_tool_message(event, ToolConfirmationMessage)

    def _on_error(self, event: AgentEvent) -> None:
        """Handle ERROR events."""
        if not event.data:
            return
        msg = _format_error_text(str(event.data))
        self._post_status_message(event, f"Error: {msg}")
        self._post(AgentContentMessage(f"❌ {msg}", event.source_agent))

    def _on_finished(self, event: AgentEvent) -> None:
        """Handle FINISHED events."""
        self._post(AgentFinishedMessage(event.source_agent))

    def _on_ctx_compact(self, event: AgentEvent) -> None:
        """Handle CONTEXT_COMPACTED events."""
        self._post_status_message(event, "Context compacted to fit model limits")
        self._post(CommandOutputMessage("[dim]ℹ Context window was compacted.[/dim]"))

    def _on_turn_summary(self, event: AgentEvent) -> None:
        """Handle TURN_SUMMARIZED events."""
        self._post_status_message(event, "Previous turn summarized")

    def _on_turn_status(self, event: AgentEvent) -> None:
        """Handle TURN_STATUS events."""
        if not (event.data and isinstance(event.data, dict)):
            return
        status = _format_turn_status(event.data)
        self._post_status_message(event, status)
        self._update_status_bar(event.data)

    def _on_agent_start(self, event: AgentEvent) -> None:
        """Handle AGENT_STARTED events."""
        if not (event.data and isinstance(event.data, dict)):
            return
        name = self._extract_from_dict(event, "agent", "unknown")
        self._post_status_message(event, f"⚙ {name} working…")

    def _on_agent_done(self, event: AgentEvent) -> None:
        """Handle AGENT_COMPLETED events."""
        if not (event.data and isinstance(event.data, dict)):
            return
        name = self._extract_from_dict(event, "agent", "unknown")
        summary = self._extract_from_dict(event, "summary", "")
        msg = f"✓ {name} completed"
        if summary:
            msg += f": {summary}"
        self._post_status_message(event, msg)

    def _on_delegated(self, event: AgentEvent) -> None:
        """Handle AGENT_DELEGATED events."""
        if not (event.data and isinstance(event.data, dict)):
            return
        from_a = self._extract_from_dict(event, "from", "?")
        to_a = self._extract_from_dict(event, "to", "?")
        reason = self._extract_from_dict(event, "reason", "")
        text = f"[dim]↳ Delegating: {from_a} → {to_a}"
        if reason:
            text += f" ({reason})"
        text += "[/dim]"
        self._post(CommandOutputMessage(text))
        self._post_status_message(event, f"{from_a} → {to_a}")

    def _on_agent_msg(self, event: AgentEvent) -> None:
        """Handle AGENT_MESSAGE events."""
        if event.data:
            self._post(CommandOutputMessage(f"[dim]📨 {event.data}[/dim]"))

    def _on_think_start(self, event: AgentEvent) -> None:
        """Handle THINKING_STARTED events."""
        self._post_status_message(event, "Thinking…")

    def _on_think_done(self, event: AgentEvent) -> None:
        """Handle THINKING_COMPLETED events."""
        self._post_status_message(event, "Thinking complete")

    def _on_think_req(self, event: AgentEvent) -> None:
        """Handle THINKING_REQUIRED events."""
        self._post_status_message(event, "⚠ Thinking pattern missing in response")

    def _on_deleg_dec(self, event: AgentEvent) -> None:
        """Handle DELEGATION_DECISION events."""
        self._post_prefixed_message(event, "Delegation decision: ")

    def _on_reflection(self, event: AgentEvent) -> None:
        """Handle REFLECTION events."""
        self._post_prefixed_message(event, "Reflection: ")


# ------------------------------------------------------------------ #
# Module-level formatting helpers                                      #
# ------------------------------------------------------------------ #


def _format_error_text(error_text: str) -> str:
    """Format error message, handling API-auth special case.

    Args:
        error_text: Raw error text.

    Returns:
        Formatted error message.
    """
    lower = error_text.lower()

    # Authentication keyword groups — if any group is fully present in the
    # lowered text we treat it as a potential auth error.
    auth_keyword_groups: list[list[str]] = [
        ["api", "key"],
        ["authentication"],
        ["unauthorized"],
    ]

    # Negative indicators that confirm it is an *error* rather than a
    # positive statement like "API key validation succeeded".
    negative_indicators = [
        "invalid",
        "missing",
        "failed",
        "error",
        "unauthorized",
        "no ",
        "not ",
        "required",
    ]

    for group in auth_keyword_groups:
        if all(kw in lower for kw in group) and any(ind in lower for ind in negative_indicators):
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
