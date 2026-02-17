"""Core Agent implementation for orchestrating LLM interactions."""

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from henchman.core.events import AgentEvent, EventType
from henchman.core.turn import TurnState
from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    ToolCall,
)
from henchman.tools.registry import ToolRegistry
from henchman.utils.tokens import TokenCounter, get_model_limit
from henchman.utils.validation import (
    is_valid_message_sequence,
    repair_message_sequence,
)

if TYPE_CHECKING:
    from henchman.agents.identity import AgentIdentity


class Agent:
    """Orchestrates interactions between user, LLM, and tools."""

    def __init__(
        self,
        provider: ModelProvider,
        tool_registry: ToolRegistry | None = None,
        system_prompt: str = "",
        max_tokens: int = 0,
        model: str | None = None,
        summarize_dropped: bool = True,
        base_tool_iterations: int = 25,
        max_protected_ratio: float = 0.3,
        identity: "AgentIdentity | None" = None,
    ) -> None:
        """Initialize the Agent.

        Args:
            provider: The model provider to use for LLM interactions.
            tool_registry: Registry containing available tools. Creates empty one if None.
            system_prompt: Optional system prompt for the agent.
            max_tokens: Maximum tokens for context. If 0, uses model-specific limit.
            model: Model name for determining context limits.
            summarize_dropped: Whether to summarize dropped messages during compaction.
            base_tool_iterations: Base limit for tool call iterations per turn.
            max_protected_ratio: Max ratio of context to protect from compaction.
            identity: Optional identity of the agent.
        """
        self.provider = provider
        self.tool_registry = tool_registry if tool_registry is not None else ToolRegistry()
        self.system_prompt = system_prompt
        self.summarize_dropped = summarize_dropped
        self.base_tool_iterations = base_tool_iterations
        self.max_protected_ratio = max_protected_ratio
        self.identity = identity

        # Auto-detect model from provider if not explicitly given
        if not model and hasattr(provider, "default_model"):
            model = provider.default_model
        self.model = model

        # Determine max tokens from model limit if not specified
        if max_tokens > 0:
            self.max_tokens = max_tokens
        elif model:
            self.max_tokens = int(get_model_limit(model) * 0.85)  # 85% of limit
        else:
            self.max_tokens = 8000  # Safe default

        self.messages: list[Message] = []

        # Turn tracking for loop protection
        self.turn = TurnState()
        self.unlimited_mode = False
        self._stall_nudge_count = 0
        self._stall_failure = False
        self._max_stall_nudges = 2
        self.stall_detection_enabled = True
        self._turn_number = 0

        if system_prompt:
            self.messages.append(Message(role="system", content=system_prompt))

    @property
    def history(self) -> list[Message]:
        """Get the conversation history."""
        return self.messages

    @property
    def tools(self) -> ToolRegistry:
        """Get the available tools from the registry."""
        return self.tool_registry

    def _emit(self, type: EventType, data: Any = None) -> AgentEvent:
        """Create an AgentEvent with the correct source_agent."""
        return AgentEvent(
            type=type,
            data=data,
            source_agent=self.identity.id if self.identity else None,
        )

    def clear_history(self) -> None:
        """Clear the conversation history."""
        # Keep system prompt if it exists
        system_messages = [msg for msg in self.messages if msg.role == "system"]
        self.messages = system_messages

    def get_messages_for_api(self) -> list[Message]:
        """Get the messages to send to the API, with compaction if needed.

        Returns:
            List of messages, potentially compacted to fit within max_tokens.
        """
        from henchman.utils.compaction import ContextCompactor

        compactor = ContextCompactor(
            max_tokens=self.max_tokens,
            max_protected_ratio=self.max_protected_ratio,
        )
        return compactor.compact(
            self.messages,
            protect_from_index=self.turn.start_index,
        )

    async def _apply_compaction_if_needed(self) -> bool:
        """Apply compaction to messages if they exceed token limit.

        Returns:
            True if compaction was applied, False otherwise.
        """
        current_tokens = TokenCounter.count_messages(self.messages, model=self.model)

        # Update turn's protected token count
        if self.turn.start_index < len(self.messages):
            protected_msgs = self.messages[self.turn.start_index :]
            self.turn.protected_tokens = TokenCounter.count_messages(
                protected_msgs, model=self.model
            )

        if current_tokens <= self.max_tokens:
            return False

        # Try summarization if enabled
        if self.summarize_dropped:
            from henchman.utils.compaction import compact_with_summarization

            result = await compact_with_summarization(
                messages=self.messages,
                max_tokens=self.max_tokens,
                provider=self.provider,
                summarize=True,
                protect_from_index=self.turn.start_index,
                max_protected_ratio=self.max_protected_ratio,
            )
            if result.was_compacted:
                # Validate and repair if needed — summarization can break
                # tool sequences in edge cases
                if not is_valid_message_sequence(result.messages):
                    result.messages = repair_message_sequence(result.messages)
                self.messages = result.messages
                return True

        # Fall back to simple compaction
        from henchman.utils.compaction import ContextCompactor

        compactor = ContextCompactor(
            max_tokens=self.max_tokens,
            max_protected_ratio=self.max_protected_ratio,
        )
        self.messages = compactor.compact(
            self.messages,
            protect_from_index=self.turn.start_index,
        )

        # Validate and repair compacted messages if tool sequences were broken
        if not is_valid_message_sequence(self.messages):
            self.messages = repair_message_sequence(self.messages)
        return True

    async def _check_for_stalling(self, response_text: str, had_tool_calls: bool) -> str | None:
        """Detect when the agent narrates intent without acting.

        Checks for two patterns:
          1. Response ends with ``:``, announcing work without doing it.
          2. Response contains intent phrases (``let me create``, etc.)
             without any tool calls.

        After ``_max_stall_nudges`` unsuccessful nudges, sets
        ``_stall_failure`` so the orchestrator can report the failure
        to the Tech Lead.

        Returns a nudge message if stalling is detected, None otherwise.
        """
        if not self.stall_detection_enabled:
            return None

        if had_tool_calls:
            self._stall_nudge_count = 0
            return None

        # If the response is very short, it might just be specific non-action query
        if len(response_text) < 20:
            return None

        is_stalling = False
        stripped = response_text.strip()

        # Pattern 1: ends with colon — announcing but not doing
        if stripped.endswith(":"):
            is_stalling = True

        # Pattern 2: intent phrases without action
        if not is_stalling:
            stall_phrases = [
                "let me start by",
                "i'll start by",
                "i will start by",
                "i'll create",
                "let me create",
                "i'll write",
                "let me write",
                "i'll begin",
                "now i'll",
                "let me begin",
                "i'm going to",
                "i will now",
                "step 1:",
                "first, i will",
                "let me ",
                "going to ",
                "next i ",
            ]
            lower = response_text.lower()
            if (
                any(phrase in lower for phrase in stall_phrases)
                and not ("?" in response_text and "should i" in lower)
                and (len(stripped) < 120 or stripped.endswith(":"))
            ):
                is_stalling = True

        if not is_stalling:
            return None

        self._stall_nudge_count += 1
        if self._stall_nudge_count > self._max_stall_nudges:
            self._stall_failure = True
            return None  # Stop nudging — orchestrator will handle failure

        return (
            "You stopped without taking action. Do not narrate — use your tools "
            "to do the work. Call the appropriate tool NOW."
        )

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with user input."""
        # Start new turn - record where it begins in message history
        self._turn_number += 1
        self.turn.reset(new_start_index=len(self.messages))

        # Add user message
        self.messages.append(Message(role="user", content=user_input))

        # Loop to handle potential stalling (narrating without acting)
        while True:
            # Validate message sequence, repairing if broken
            # (can happen after compaction or session restore)
            if not is_valid_message_sequence(self.messages):
                self.messages = repair_message_sequence(self.messages)

            # Apply compaction if needed and emit event
            compacted = await self._apply_compaction_if_needed()
            if compacted:
                yield self._emit(
                    type=EventType.CONTEXT_COMPACTED,
                    data={"message": "Context was compacted to fit model limits"},
                )

            # Track accumulated content and tool calls for building the assistant message
            accumulated_content = ""
            accumulated_thinking = ""
            accumulated_tool_calls: list[ToolCall] = []

            # Get messages for API (may be compacted)
            api_messages = self.get_messages_for_api()

            # Final validation before API call — repair if needed
            if not is_valid_message_sequence(api_messages):
                api_messages = repair_message_sequence(api_messages)

            # Get stream from provider - use validated messages
            async for chunk in self.provider.chat_completion_stream(
                messages=api_messages,
                tools=self.tool_registry.get_declarations(),
            ):
                if chunk.thinking:
                    accumulated_thinking += chunk.thinking
                    # Handle thinking/reasoning content
                    yield self._emit(
                        type=EventType.THOUGHT,
                        data=chunk.thinking,
                    )

                # Accumulate content and tool calls as they stream
                if chunk.content:
                    accumulated_content += chunk.content
                if chunk.tool_calls:
                    accumulated_tool_calls.extend(chunk.tool_calls)

                # Update messages based on finish reason FIRST, before yielding events
                # This ensures the assistant message is in history before tool results are added
                if chunk.finish_reason == FinishReason.STOP:
                    # Add assistant message to history
                    assistant_msg = Message(
                        role="assistant",
                        content=accumulated_content,
                        tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
                        reasoning_content=accumulated_thinking if accumulated_thinking else None,
                    )
                    self.messages.append(assistant_msg)

                    # Now yield content event if any
                    if accumulated_content:
                        yield self._emit(
                            type=EventType.CONTENT,
                            data=accumulated_content,
                        )
                    break
                elif chunk.finish_reason == FinishReason.TOOL_CALLS:
                    # Add assistant message with tool_calls to history FIRST
                    # This is needed so subsequent tool messages have a valid predecessor
                    assistant_msg = Message(
                        role="assistant",
                        content=accumulated_content,
                        tool_calls=accumulated_tool_calls
                        if accumulated_tool_calls
                        else chunk.tool_calls,
                        reasoning_content=accumulated_thinking if accumulated_thinking else None,
                    )
                    self.messages.append(assistant_msg)

                    # Now yield tool call events
                    tool_calls_to_yield = (
                        accumulated_tool_calls
                        if accumulated_tool_calls
                        else (chunk.tool_calls or [])
                    )
                    for tool_call in tool_calls_to_yield:
                        yield self._emit(
                            type=EventType.TOOL_CALL_REQUEST,
                            data=tool_call,
                        )
                    break
                else:
                    # No finish reason yet - stream content as it comes
                    # Tool calls are accumulated but NOT yielded until finish_reason
                    # to ensure proper batching
                    if chunk.content:
                        yield self._emit(
                            type=EventType.CONTENT,
                            data=chunk.content,
                        )

            # Check for stalling
            nudge = await self._check_for_stalling(
                accumulated_content, bool(accumulated_tool_calls)
            )
            if nudge:
                # Add nudge to messages and continue loop
                self.messages.append(Message(role="user", content=nudge))
                continue

            # If no stalling, exit the loop
            break

    def submit_tool_result(self, tool_call_id: str, result: str) -> None:
        """Submit a tool result to continue the conversation."""
        self.messages.append(Message(role="tool", content=result, tool_call_id=tool_call_id))

    async def continue_with_tool_results(self) -> AsyncIterator[AgentEvent]:
        """Continue agent execution after tool results have been submitted.

        This method should be called after submit_tool_result() to continue
        the conversation with the updated message history.
        """
        # Validate full message history, repairing if broken
        if not is_valid_message_sequence(self.messages):
            self.messages = repair_message_sequence(self.messages)

        # Apply compaction if needed and emit event
        compacted = await self._apply_compaction_if_needed()
        if compacted:
            yield self._emit(
                type=EventType.CONTEXT_COMPACTED,
                data={"message": "Context was compacted to fit model limits"},
            )

        # Track accumulated content and tool calls for building the assistant message
        accumulated_content = ""
        accumulated_thinking = ""
        accumulated_tool_calls: list[ToolCall] = []

        # Get messages for API (may be compacted)
        api_messages = self.get_messages_for_api()

        # Final validation before API call — repair if needed
        if not is_valid_message_sequence(api_messages):
            api_messages = repair_message_sequence(api_messages)

        # Get stream from provider - use validated messages
        async for chunk in self.provider.chat_completion_stream(
            messages=api_messages,
            tools=self.tool_registry.get_declarations(),
        ):
            if chunk.thinking:
                accumulated_thinking += chunk.thinking
                # Handle thinking/reasoning content
                yield self._emit(
                    type=EventType.THOUGHT,
                    data=chunk.thinking,
                )

            # Accumulate content and tool calls as they stream
            if chunk.content:
                accumulated_content += chunk.content
            if chunk.tool_calls:
                accumulated_tool_calls.extend(chunk.tool_calls)

            # Update messages based on finish reason FIRST, before yielding events
            if chunk.finish_reason == FinishReason.STOP:
                # Add assistant message to history
                assistant_msg = Message(
                    role="assistant",
                    content=accumulated_content,
                    tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
                    reasoning_content=accumulated_thinking if accumulated_thinking else None,
                )
                self.messages.append(assistant_msg)

                # Now yield content event if any
                if accumulated_content:
                    yield self._emit(
                        type=EventType.CONTENT,
                        data=accumulated_content,
                    )
                break
            elif chunk.finish_reason == FinishReason.TOOL_CALLS:
                # Add assistant message with tool_calls to history FIRST
                assistant_msg = Message(
                    role="assistant",
                    content=accumulated_content,
                    tool_calls=accumulated_tool_calls
                    if accumulated_tool_calls
                    else chunk.tool_calls,
                    reasoning_content=accumulated_thinking if accumulated_thinking else None,
                )
                self.messages.append(assistant_msg)

                # Now yield tool call events
                tool_calls_to_yield = (
                    accumulated_tool_calls if accumulated_tool_calls else (chunk.tool_calls or [])
                )
                for tool_call in tool_calls_to_yield:
                    yield self._emit(
                        type=EventType.TOOL_CALL_REQUEST,
                        data=tool_call,
                    )
                break
            else:
                # No finish reason yet - stream content as it comes
                # Tool calls are accumulated but NOT yielded until finish_reason
                # to ensure proper batching
                if chunk.content:
                    yield self._emit(
                        type=EventType.CONTENT,
                        data=chunk.content,
                    )
