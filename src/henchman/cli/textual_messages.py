"""Textual ``Message`` subclasses for Henchman-AI TUI events.

Each message type maps to an ``AgentEvent`` variant that needs to be
dispatched through the Textual event system.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from textual.message import Message

if TYPE_CHECKING:
    from henchman.tools.base import ConfirmationRequest


class _AgentPayloadMessage(Message):
    """Base class for agent messages carrying a payload and optional source_agent."""

    def __init__(
        self: _AgentPayloadMessage,
        _payload: Any,
        source_agent: str | None = None,
    ) -> None:
        """Initialize.

        Args:
            _payload: The primary data carried by this message.
            source_agent: Originating agent name.
        """
        super().__init__()
        self._payload = _payload
        self.source_agent = source_agent

    @property
    def _str_payload(self: _AgentPayloadMessage) -> str:
        """Internal helper for string payloads."""
        return cast("str", self._payload)


class AgentContentMessage(_AgentPayloadMessage):
    """Streamed text content from an agent."""

    @property
    def content(self: AgentContentMessage) -> str:
        """The streamed text content."""
        return self._str_payload


class AgentThoughtMessage(_AgentPayloadMessage):
    """Thinking/reasoning text from an agent."""

    @property
    def thought(self: AgentThoughtMessage) -> str:
        """The thinking text."""
        return self._str_payload


class ToolCallRequestMessage(_AgentPayloadMessage):
    """Agent is requesting a tool call."""

    @property
    def tool_call(self: ToolCallRequestMessage) -> Any:
        """The tool call request data."""
        return self._payload


class ToolCallResultMessage(_AgentPayloadMessage):
    """Result from a tool execution."""

    @property
    def result(self: ToolCallResultMessage) -> Any:
        """The tool execution result data."""
        return self._payload


class ToolConfirmationMessage(_AgentPayloadMessage):
    """Agent is awaiting user approval for a tool call."""

    @property
    def request(self: ToolConfirmationMessage) -> ConfirmationRequest:
        """The confirmation request data."""
        conf_req: ConfirmationRequest = cast("ConfirmationRequest", self._payload)
        return conf_req


class AgentStatusMessage(_AgentPayloadMessage):
    """Status update from the agent loop."""

    @property
    def status(self: AgentStatusMessage) -> str:
        """The status message."""
        return self._str_payload


class AgentFinishedMessage(_AgentPayloadMessage):
    """Agent has finished processing the current turn.

    Stores ``None`` as the payload; the meaningful field is ``source_agent``
    which is inherited from ``_AgentPayloadMessage``.
    """

    def __init__(
        self: AgentFinishedMessage,
        source_agent: str | None = None,
    ) -> None:
        """Initialize.

        Args:
            source_agent: Originating agent name.
        """
        super().__init__(None, source_agent)


class CommandOutputMessage(_AgentPayloadMessage):
    """Output produced by a slash command."""

    def __init__(
        self: CommandOutputMessage,
        text: str,
        style: str = "",
    ) -> None:
        """Initialize.

        Args:
            text: Output text.
            style: Optional Rich markup style.
        """
        super().__init__(text)
        self.style = style

    @property
    def text(self: CommandOutputMessage) -> str:
        """The command output text."""
        return self._str_payload


class SwitchProviderMessage(_AgentPayloadMessage):
    """Internal message to switch the active provider."""

    def __init__(
        self: SwitchProviderMessage,
        provider_name: str,
    ) -> None:
        """Initialize.

        Args:
            provider_name: Provider to switch to.
        """
        super().__init__(provider_name)

    @property
    def provider_name(self: SwitchProviderMessage) -> str:
        """The name of the provider to switch to."""
        return self._str_payload
