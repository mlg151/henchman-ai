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

    # Constants
    DEFAULT_MAX_TOKENS = 8000
    DEFAULT_TOKEN_RATIO = 0.85  # 85% of model limit
    MAX_STALL_NUDGES = 2
    MIN_RESPONSE_LENGTH_FOR_STALL_CHECK = 20
    MAX_RESPONSE_LENGTH_FOR_INTENT_PHRASE = 120

    # Stall detection patterns
    STALL_PHRASES = [
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
    STALL_NUDGE_MESSAGE = (
        "You stopped without taking action. Do not narrate — use your tools "
        "to do the work. Call the appropriate tool NOW."
    )

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
        intelligent_context: bool = False,
        importance_threshold: float = 0.5,
        cluster_similarity_threshold: float = 0.7,
        adaptive_compression: bool = True,
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
            intelligent_context: Whether to use intelligent context management.
            importance_threshold: Minimum importance score to preserve a message.
            cluster_similarity_threshold: Similarity threshold for clustering messages.
            adaptive_compression: Whether to use adaptive compression techniques.
        """
        self.provider = provider
        self.tool_registry = tool_registry if tool_registry is not None else ToolRegistry()
        self.system_prompt = system_prompt
        self.summarize_dropped = summarize_dropped
        self.base_tool_iterations = base_tool_iterations
        self.max_protected_ratio = max_protected_ratio
        self.identity = identity
        self.intelligent_context = intelligent_context
        self.importance_threshold = importance_threshold
        self.cluster_similarity_threshold = cluster_similarity_threshold
        self.adaptive_compression = adaptive_compression

        # Auto-detect model from provider if not explicitly given
        if not model and hasattr(provider, "default_model"):
            model = provider.default_model
        self.model = model

        # Determine max tokens from model limit if not specified
        if max_tokens > 0:
            self.max_tokens = max_tokens
        elif model:
            self.max_tokens = int(get_model_limit(model) * self.DEFAULT_TOKEN_RATIO)
        else:
            self.max_tokens = self.DEFAULT_MAX_TOKENS

        self.messages: list[Message] = []

        # Turn tracking for loop protection
        self.turn = TurnState()
        self.unlimited_mode = False
        self._stall_nudge_count = 0
        self._stall_failure = False
        self._max_stall_nudges = self.MAX_STALL_NUDGES
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
        # Import both types for type hints
        from henchman.utils.compaction import ContextCompactor
        from henchman.utils.intelligent_context import IntelligentContextManager

        compactor_instance: ContextCompactor | IntelligentContextManager

        if self.intelligent_context:
            compactor_instance = IntelligentContextManager(
                max_tokens=self.max_tokens,
                max_protected_ratio=self.max_protected_ratio,
                importance_threshold=self.importance_threshold,
                cluster_similarity_threshold=self.cluster_similarity_threshold,
                adaptive_compression=self.adaptive_compression,
            )
        else:
            compactor_instance = ContextCompactor(
                max_tokens=self.max_tokens,
                max_protected_ratio=self.max_protected_ratio,
            )

        return compactor_instance.compact(
            self.messages,
            protect_from_index=self.turn.start_index,
        )

    def _update_protected_token_count(self) -> None:
        """Update the turn's protected token count."""
        if self.turn.start_index < len(self.messages):
            protected_msgs = self.messages[self.turn.start_index :]
            self.turn.protected_tokens = TokenCounter.count_messages(
                protected_msgs, model=self.model
            )

    def _calculate_protected_count(self) -> int:
        """Calculate number of protected messages.

        Protected messages are always placed at the end of the compacted
        list, so the new start_index = len(compacted) - protected_count.
        """
        return max(0, len(self.messages) - self.turn.start_index)

    async def _try_summarization_compaction(self, protected_count: int) -> bool:
        """Try compaction with summarization if enabled.

        Returns:
            True if summarization compaction was applied, False otherwise.
        """
        if not self.summarize_dropped:
            return False

        from henchman.utils.compaction import compact_with_summarization

        result = await compact_with_summarization(
            messages=self.messages,
            max_tokens=self.max_tokens,
            provider=self.provider,
            summarize=True,
            protect_from_index=self.turn.start_index,
            max_protected_ratio=self.max_protected_ratio,
        )

        if not result.was_compacted:
            return False

        # Validate and repair if needed — summarization can break
        # tool sequences in edge cases
        if not is_valid_message_sequence(result.messages):
            result.messages = repair_message_sequence(result.messages)

        self.messages = result.messages
        # Update start_index so subsequent compaction cycles don't
        # use stale offsets that could split tool sequences.
        self.turn.start_index = max(0, len(self.messages) - protected_count)
        return True

    def _apply_simple_compaction(self, protected_count: int) -> None:
        """Apply simple compaction without summarization."""
        # Import both types for type hints
        from henchman.utils.compaction import ContextCompactor
        from henchman.utils.intelligent_context import IntelligentContextManager

        compactor_instance: ContextCompactor | IntelligentContextManager

        if self.intelligent_context:
            compactor_instance = IntelligentContextManager(
                max_tokens=self.max_tokens,
                max_protected_ratio=self.max_protected_ratio,
                importance_threshold=self.importance_threshold,
                cluster_similarity_threshold=self.cluster_similarity_threshold,
                adaptive_compression=self.adaptive_compression,
            )
        else:
            compactor_instance = ContextCompactor(
                max_tokens=self.max_tokens,
                max_protected_ratio=self.max_protected_ratio,
            )

        self.messages = compactor_instance.compact(
            self.messages,
            protect_from_index=self.turn.start_index,
        )

        # Validate and repair compacted messages if tool sequences were broken
        if not is_valid_message_sequence(self.messages):
            self.messages = repair_message_sequence(self.messages)
        # Update start_index so subsequent compaction cycles don't
        # use stale offsets that could split tool sequences.
        self.turn.start_index = max(0, len(self.messages) - protected_count)

    async def _apply_compaction_if_needed(self) -> bool:
        """Apply compaction to messages if they exceed token limit.

        Returns:
            True if compaction was applied, False otherwise.
        """
        current_tokens = TokenCounter.count_messages(self.messages, model=self.model)

        # Update turn's protected token count
        self._update_protected_token_count()

        if current_tokens <= self.max_tokens:
            return False

        protected_count = self._calculate_protected_count()

        # Try summarization if enabled
        if await self._try_summarization_compaction(protected_count):
            return True

        # Fall back to simple compaction
        self._apply_simple_compaction(protected_count)
        return True

    def _should_skip_stall_check(self, response_text: str, had_tool_calls: bool) -> bool:
        """Determine if stall check should be skipped."""
        if not self.stall_detection_enabled:
            return True
        if had_tool_calls:
            self._stall_nudge_count = 0
            return True
        return len(response_text) < self.MIN_RESPONSE_LENGTH_FOR_STALL_CHECK

    def _detect_stalling_patterns(self, response_text: str) -> bool:
        """Detect stalling patterns in response text.

        Returns:
            True if stalling is detected, False otherwise.
        """
        stripped = response_text.strip()

        # Pattern 1: ends with colon — announcing but not doing
        if stripped.endswith(":"):
            return True

        # Pattern 2: intent phrases without action
        lower = response_text.lower()
        has_stall_phrase = any(phrase in lower for phrase in self.STALL_PHRASES)
        is_question = "?" in response_text and "should i" in lower

        return (
            has_stall_phrase
            and not is_question
            and (
                len(stripped) < self.MAX_RESPONSE_LENGTH_FOR_INTENT_PHRASE or stripped.endswith(":")
            )
        )

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
        if self._should_skip_stall_check(response_text, had_tool_calls):
            return None

        if not self._detect_stalling_patterns(response_text):
            return None

        self._stall_nudge_count += 1
        if self._stall_nudge_count > self._max_stall_nudges:
            self._stall_failure = True
            return None  # Stop nudging — orchestrator will handle failure

        return self.STALL_NUDGE_MESSAGE

    async def _process_streaming_response(
        self,
    ) -> tuple[list[str], list[str], list[ToolCall], list[FinishReason | None], AsyncIterator[AgentEvent]]:
        """Process streaming response from provider.

        This method handles the common streaming logic shared between
        run() and continue_with_tool_results().

        Returns:
            Tuple of (accumulated_content list, accumulated_thinking list,
                     accumulated_tool_calls list, finish_reason list, event_iterator)
            The lists are mutable and will be updated as the generator runs.
        """
        # Validate message sequence, repairing if broken
        # (can happen after compaction or session restore)
        if not is_valid_message_sequence(self.messages):
            self.messages = repair_message_sequence(self.messages)

        # Apply compaction if needed and emit event
        compacted = await self._apply_compaction_if_needed()

        # Get messages for API (may be compacted)
        api_messages = self.get_messages_for_api()

        # Final validation before API call — repair if needed
        if not is_valid_message_sequence(api_messages):
            api_messages = repair_message_sequence(api_messages)

        # Use mutable lists to accumulate values that can be updated in closure
        accumulated_content: list[str] = [""]  # Single-element list for mutable string
        accumulated_thinking: list[str] = [""]
        accumulated_tool_calls: list[ToolCall] = []
        content_yielded: list[bool] = [False]  # Track if any content was yielded during streaming
        finish_reason: list[FinishReason | None] = [None]  # Track the finish reason

        async def event_generator() -> AsyncIterator[AgentEvent]:
            """Inner generator for streaming events."""
            if compacted:
                yield self._emit(
                    type=EventType.CONTEXT_COMPACTED,
                    data={"message": "Context was compacted to fit model limits"},
                )

            try:
                # Get stream from provider - use validated messages
                async for chunk in self.provider.chat_completion_stream(
                    messages=api_messages,
                    tools=self.tool_registry.get_declarations(),
                ):
                    if chunk.thinking:
                        accumulated_thinking[0] += chunk.thinking
                        # Handle thinking/reasoning content
                        yield self._emit(
                            type=EventType.THOUGHT,
                            data=chunk.thinking,
                        )

                    # Accumulate content and tool calls as they stream
                    if chunk.content:
                        accumulated_content[0] += chunk.content
                    if chunk.tool_calls:
                        accumulated_tool_calls.extend(chunk.tool_calls)

                    # Update messages based on finish reason FIRST, before yielding events
                    # This ensures the assistant message is in history before tool results are added
                    if chunk.finish_reason == FinishReason.STOP:
                        # Add assistant message to history
                        assistant_msg = Message(
                            role="assistant",
                            content=accumulated_content[0],
                            tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
                            reasoning_content=accumulated_thinking[0]
                            if accumulated_thinking[0]
                            else None,
                        )
                        self.messages.append(assistant_msg)

                        # Yield content event if we haven't yielded any content yet
                        # (e.g., non-streaming response where all content comes with STOP)
                        if accumulated_content[0] and not content_yielded[0]:
                            yield self._emit(
                                type=EventType.CONTENT,
                                data=accumulated_content[0],
                            )
                        finish_reason[0] = chunk.finish_reason
                        break
                    elif chunk.finish_reason == FinishReason.TOOL_CALLS:
                        # Add assistant message with tool_calls to history FIRST
                        # This is needed so subsequent tool messages have a valid predecessor
                        assistant_msg = Message(
                            role="assistant",
                            content=accumulated_content[0],
                            tool_calls=accumulated_tool_calls
                            if accumulated_tool_calls
                            else chunk.tool_calls,
                            reasoning_content=accumulated_thinking[0]
                            if accumulated_thinking[0]
                            else None,
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
                        finish_reason[0] = chunk.finish_reason
                        break
                    elif chunk.finish_reason in (FinishReason.LENGTH, FinishReason.CONTENT_FILTER):
                        # Handle length and content filter finish reasons
                        # Add assistant message to history
                        assistant_msg = Message(
                            role="assistant",
                            content=accumulated_content[0],
                            tool_calls=accumulated_tool_calls if accumulated_tool_calls else None,
                            reasoning_content=accumulated_thinking[0]
                            if accumulated_thinking[0]
                            else None,
                        )
                        self.messages.append(assistant_msg)

                        # Yield any remaining content
                        if accumulated_content[0] and not content_yielded[0]:
                            yield self._emit(
                                type=EventType.CONTENT,
                                data=accumulated_content[0],
                            )
                        finish_reason[0] = chunk.finish_reason
                        break
                    else:
                        # No finish reason yet - stream content as it comes
                        # Tool calls are accumulated but NOT yielded until finish_reason
                        # to ensure proper batching
                        if chunk.content:
                            content_yielded[0] = True
                            yield self._emit(
                                type=EventType.CONTENT,
                                data=chunk.content,
                            )
            except Exception as e:
                # Provider error - yield error event
                yield self._emit(
                    type=EventType.ERROR,
                    data=f"Provider error: {e}"
                )
            finally:
                # Always yield finished event with actual finish reason if available
                finish_data = "Stream completed"
                if finish_reason[0]:
                    finish_data = finish_reason[0].value
                yield self._emit(
                    type=EventType.FINISHED,
                    data=finish_data
                )

        return accumulated_content, accumulated_thinking, accumulated_tool_calls, finish_reason, event_generator()

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        """Run the agent with user input."""
        print(f"DEBUG Agent.run: Starting with input: {user_input[:100]}")  # Debug
        # Start new turn - record where it begins in message history
        self._turn_number += 1
        self.turn.reset(new_start_index=len(self.messages))

        # Add user message
        self.messages.append(Message(role="user", content=user_input))

        # Loop to handle potential stalling (narrating without acting)
        while True:
            try:
                print("DEBUG Agent.run: Calling _process_streaming_response")  # Debug
                # Process streaming response
                (
                    accumulated_content_list,
                    accumulated_thinking_list,
                    accumulated_tool_calls,
                    finish_reason_list,
                    event_iter,
                ) = await self._process_streaming_response()

                event_count = 0
                async for event in event_iter:
                    event_count += 1
                    print(f"DEBUG Agent.run: Yielding event {event_count}: {event.type}")  # Debug
                    yield event

                print(f"DEBUG Agent.run: Finished yielding {event_count} events")  # Debug

                # Extract actual content from list (mutable container)
                accumulated_content = accumulated_content_list[0] if accumulated_content_list else ""

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

            except Exception as e:
                # Yield error event
                print(f"DEBUG Agent.run: Exception: {e}")  # Debug
                yield self._emit(
                    type=EventType.ERROR,
                    data=f"Agent execution failed: {e}"
                )
                break

        # Yield finished event with actual finish reason if available
        print("DEBUG Agent.run: Yielding FINISHED event")  # Debug
        finish_data = "Agent completed execution"
        if finish_reason_list and finish_reason_list[0]:
            finish_data = finish_reason_list[0].value
        yield self._emit(type=EventType.FINISHED, data=finish_data)

    def submit_tool_result(self, tool_call_id: str, result: str) -> None:
        """Submit a tool result to continue the conversation."""
        self.messages.append(Message(role="tool", content=result, tool_call_id=tool_call_id))

    async def continue_with_tool_results(self) -> AsyncIterator[AgentEvent]:
        """Continue agent execution after tool results have been submitted.

        This method should be called after submit_tool_result() to continue
        the conversation with the updated message history.
        """
        # Process streaming response
        _, _, _, _, event_iter = await self._process_streaming_response()

        async for event in event_iter:
            yield event
