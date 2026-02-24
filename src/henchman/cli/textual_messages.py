"""Textual ``Message`` subclasses for Henchman-AI TUI events.

Each message type maps to an ``AgentEvent`` variant that needs to be
dispatched through the Textual event system.

Note: Extracted from ``textual_app.py`` to keep modules under 500 lines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.message import Message

if TYPE_CHECKING:
    from henchman.tools.base import ConfirmationRequest


class AgentContentMessage(Message):
    """Streamed text content from an agent."""

    def __init__(
        self,
        content: str,
        source_agent: str | None = None,
    ) -> None:
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

    def __init__(
        self,
        thought: str,
        source_agent: str | None = None,
    ) -> None:
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

    def __init__(
        self,
        tool_call: Any,
        source_agent: str | None = None,
    ) -> None:
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

    def __init__(
        self,
        result: Any,
        source_agent: str | None = None,
    ) -> None:
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

    def __init__(
        self,
        request: ConfirmationRequest,
        source_agent: str | None = None,
    ) -> None:
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

    def __init__(
        self,
        status: str,
        source_agent: str | None = None,
    ) -> None:
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
    """Output produced by a slash command."""

    def __init__(self, text: str, style: str = "") -> None:
        """Initialize.

        Args:
            text: Output text.
            style: Optional Rich markup style.
        """
        super().__init__()
        self.text = text
        self.style = style


class SwitchProviderMessage(Message):
    """Internal message to switch the active provider."""

    def __init__(self, provider_name: str) -> None:
        """Initialize.

        Args:
            provider_name: Provider to switch to.
        """
        super().__init__()
        self.provider_name = provider_name
