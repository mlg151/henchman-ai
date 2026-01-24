"""Core Agent implementation for orchestrating LLM interactions."""

from collections.abc import AsyncIterator

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    ToolCall,
    ToolDeclaration,
)

__all__ = ["Agent"]


class Agent:
    """The main agent that orchestrates LLM interactions.

    The Agent manages conversation history, streams responses from the model,
    and handles tool call requests.

    Attributes:
        provider: The model provider to use for completions.
        tools: List of tool declarations available to the model.
        system_prompt: Optional system prompt to include in all requests.
        history: The conversation history.
    """

    def __init__(
        self,
        provider: ModelProvider,
        tools: list[ToolDeclaration] | None = None,
        system_prompt: str = "",
        max_tokens: int = 8000,
    ) -> None:
        """Initialize the agent.

        Args:
            provider: The model provider to use.
            tools: Optional list of tools available to the model.
            system_prompt: Optional system prompt.
            max_tokens: Maximum tokens to keep in context before compaction.
        """
        self.provider = provider
        self.tools = tools or []
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.history: list[Message] = []
        self._pending_tool_calls: list[ToolCall] = []
        self._pending_tool_results: dict[str, str] = {}

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.history = []
        self._pending_tool_calls = []
        self._pending_tool_results = {}

    def get_messages_for_api(self) -> list[Message]:
        """Get the messages to send to the API.

        Returns:
            List of messages including system prompt and history.
        """
        messages = []
        if self.system_prompt:
            messages.append(Message(role="system", content=self.system_prompt))
        messages.extend(self.history)

        # Apply automatic compaction if context is too large
        from henchman.utils.compaction import ContextCompactor
        compactor = ContextCompactor(max_tokens=self.max_tokens)
        return compactor.compact(messages)

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with user input.

        This is the main entry point for agent execution. It adds the user
        message to history, streams the model response, and yields events
        as they occur.

        Args:
            user_input: The user's input message.

        Yields:
            AgentEvent objects as the agent processes the request.
        """
        # Add user message to history
        self.history.append(Message(role="user", content=user_input))

        # Stream response
        async for event in self._stream_response():
            yield event

    async def continue_with_tool_results(self) -> AsyncIterator[AgentEvent]:
        """Continue execution after tool results have been submitted.

        This should be called after submit_tool_result() to continue
        the conversation with the tool results.

        Yields:
            AgentEvent objects as the agent continues processing.
        """
        # Add tool results to history
        for tool_call_id, result in self._pending_tool_results.items():
            self.history.append(
                Message(role="tool", content=result, tool_call_id=tool_call_id)
            )
        self._pending_tool_results = {}
        self._pending_tool_calls = []

        # Continue streaming
        async for event in self._stream_response():
            yield event

    def submit_tool_result(self, tool_call_id: str, result: str) -> None:
        """Submit a tool result.

        Args:
            tool_call_id: The ID of the tool call this result is for.
            result: The result from the tool execution.
        """
        self._pending_tool_results[tool_call_id] = result

    async def _stream_response(self) -> AsyncIterator[AgentEvent]:
        """Stream response from the model.

        Yields:
            AgentEvent objects for content, thinking, tool calls, etc.
        """
        try:
            messages = self.get_messages_for_api()
            tools = self.tools if self.tools else None

            accumulated_content = ""
            tool_calls: list[ToolCall] = []

            async for chunk in self.provider.chat_completion_stream(
                messages=messages,
                tools=tools,
            ):
                # Handle thinking/reasoning content
                if chunk.thinking:
                    yield AgentEvent(type=EventType.THOUGHT, data=chunk.thinking)

                # Handle regular content
                if chunk.content:
                    accumulated_content += chunk.content
                    yield AgentEvent(type=EventType.CONTENT, data=chunk.content)

                # Handle tool calls
                if chunk.tool_calls:
                    tool_calls.extend(chunk.tool_calls)

                # Handle finish
                if chunk.finish_reason:
                    # If we have tool calls, emit them
                    if chunk.finish_reason == FinishReason.TOOL_CALLS and tool_calls:
                        # Add assistant message with tool calls to history
                        self.history.append(
                            Message(
                                role="assistant",
                                content=accumulated_content if accumulated_content else None,
                                tool_calls=tool_calls,
                            )
                        )
                        self._pending_tool_calls = tool_calls

                        # Emit tool call request events
                        for tc in tool_calls:
                            yield AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc)
                    else:
                        # Normal completion - add assistant message to history
                        if accumulated_content:
                            self.history.append(
                                Message(role="assistant", content=accumulated_content)
                            )

                    yield AgentEvent(type=EventType.FINISHED)

        except Exception as e:
            yield AgentEvent(type=EventType.ERROR, data=str(e))
