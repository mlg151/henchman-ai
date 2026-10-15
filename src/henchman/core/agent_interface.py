"""Protocol defining the Agent interface for contract enforcement."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from henchman.agents.identity import AgentIdentity
    from henchman.core.events import AgentEvent
    from henchman.providers.base import Message, ModelProvider
    from henchman.tools.registry import ToolRegistry


@runtime_checkable
class AgentInterface(Protocol):
    """Protocol defining the contract for an Agent.

    This interface allows for structural typing of agents, making it easier
    to substitute different agent implementations or mocks in tests.
    """

    @property
    def provider(self) -> ModelProvider:
        """The model provider used by the agent."""
        ...

    @property
    def tool_registry(self) -> ToolRegistry:
        """The registry of tools available to the agent."""
        ...

    @property
    def messages(self) -> list[Message]:
        """The conversation history of the agent."""
        ...

    @property
    def identity(self) -> AgentIdentity | None:
        """The identity (role, id) of the agent."""
        ...

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with user input.

        Args:
            user_input: The user's input or task description.

        Yields:
            AgentEvent: Stream of events from the agent execution.
        """
        ...

    async def continue_with_tool_results(self) -> AsyncIterator[AgentEvent]:
        """Continue execution after tool results have been submitted.

        Yields:
            AgentEvent: Stream of events from the agent execution.
        """
        ...

    def record_delegation_errors(self, errors: list[str]) -> None:
        """Record tool errors from a delegation.

        Args:
            errors: List of error messages to record.
        """
        ...

    def get_delegation_errors(self) -> list[str]:
        """Get recorded delegation tool errors.

        Returns:
            List of error messages recorded.
        """
        ...
