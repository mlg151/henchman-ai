"""Core Agent implementation for orchestrating LLM interactions."""

from collections.abc import AsyncIterator

from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
)
from henchman.tools.registry import ToolRegistry
from henchman.utils.validation import validate_message_sequence


class Agent:
    """Orchestrates interactions between user, LLM, and tools."""
    
    def __init__(
        self,
        provider: ModelProvider,
        tool_registry: ToolRegistry,
        system_prompt: str = "",
    ) -> None:
        self.provider = provider
        self.tool_registry = tool_registry
        self.system_prompt = system_prompt
        self.messages: list[Message] = []
        
        if system_prompt:
            self.messages.append(Message(role="system", content=system_prompt))
    
    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with user input."""
        # Add user message
        self.messages.append(Message(role="user", content=user_input))
        
        # Validate message sequence
        validate_message_sequence(self.messages)
        
        # Get stream from provider
        async for chunk in self.provider.chat_completion_stream(
            messages=self.messages,
            tools=self.tool_registry.get_declarations(),
        ):
            if chunk.tool_calls:
                # Handle tool calls
                for tool_call in chunk.tool_calls:
                    yield AgentEvent(
                        type=EventType.TOOL_CALL_REQUEST,
                        data=tool_call,
                    )
            elif chunk.content:
                # Handle content
                yield AgentEvent(
                    type=EventType.CONTENT,
                    data=chunk.content,
                )
            
            # Update messages based on finish reason
            if chunk.finish_reason == FinishReason.STOP:
                # Add assistant message to history
                assistant_msg = Message(
                    role="assistant",
                    content=chunk.content or "",
                    tool_calls=chunk.tool_calls,
                )
                self.messages.append(assistant_msg)
                break
            elif chunk.finish_reason == FinishReason.TOOL_CALLS:
                # Don't add to history yet - wait for tool results
                pass
    
    def submit_tool_result(self, tool_call_id: str, result: str) -> None:
        """Submit a tool result to continue the conversation."""
        self.messages.append(
            Message(role="tool", content=result, tool_call_id=tool_call_id)
        )
