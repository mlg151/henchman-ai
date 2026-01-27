"""Context compaction utilities.

This module provides tools for managing context size by compacting
older messages, with optional summarization of dropped content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from henchman.providers.base import Message
from henchman.utils.tokens import TokenCounter

if TYPE_CHECKING:
    # For type checking only
    from henchman.providers.base import Message, ModelProvider


@dataclass
class CompactionResult:
    """Result of a compaction operation.

    Attributes:
        messages: The compacted messages.
        was_compacted: Whether compaction actually occurred.
        dropped_count: Number of messages/sequences dropped.
        summary: Optional summary of dropped content.
    """

    messages: list[Message]
    was_compacted: bool = False
    dropped_count: int = 0
    summary: str | None = None


class MessageSequence:
    """Represents an atomic sequence of messages that must be kept together."""

    def __init__(self, messages: list[Message]):
        """Initialize a MessageSequence.

        Args:
            messages: List of messages that form an atomic sequence.
        """
        self.messages = messages

    @property
    def token_count(self) -> int:
        """Get the token count for this sequence."""
        return TokenCounter.count_messages(self.messages)

    @property
    def is_tool_sequence(self) -> bool:
        """Check if this sequence contains tool calls."""
        return any(
            msg.role == "assistant" and msg.tool_calls
            for msg in self.messages
        )

    def __repr__(self) -> str:
        roles = [msg.role for msg in self.messages]
        return f"MessageSequence(roles={roles}, tokens={self.token_count})"


class ContextCompactor:
    """Manages context size by pruning older messages.

    Preserves atomic sequences, especially tool call sequences.
    """

    # Safety limit for individual message size
    MAX_MESSAGE_CHARS = 100_000

    def __init__(self, max_tokens: int = 8000) -> None:
        """Initialize compactor.

        Args:
            max_tokens: Maximum tokens to keep in context.
        """
        self.max_tokens = max_tokens

    def enforce_safety_limits(self, messages: list[Message]) -> list[Message]:
        """Enforce hard safety limits on individual message content size.
        
        This prevents context overflow from individual massive messages
        that might slip through tool-specific limits.
        
        Args:
            messages: List of messages to check.
            
        Returns:
            List of messages with content limits enforced.
        """
        safe_messages = []
        for msg in messages:
            # Check content length
            if msg.content and len(msg.content) > self.MAX_MESSAGE_CHARS:
                # Create a new message with truncated content
                new_content = msg.content[:self.MAX_MESSAGE_CHARS] + f"\n... (truncated by safety limit: > {self.MAX_MESSAGE_CHARS} chars)"

                # Create copy with modified content
                safe_msg = Message(
                    role=msg.role,
                    content=new_content,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                )
                safe_messages.append(safe_msg)
            else:
                safe_messages.append(msg)

        return safe_messages

    def _group_into_sequences(self, messages: list[Message]) -> list[MessageSequence]:
        """Group messages into atomic sequences that must be kept together.

        Rules:
        1. Each user message starts a new sequence (except the first)
        2. Assistant messages with tool_calls include all following tool messages
           for those specific tool calls
        3. Other messages continue the current sequence

        Args:
            messages: The messages to group.

        Returns:
            List of MessageSequence objects.
        """
        if not messages:
            return []

        sequences: list[MessageSequence] = []
        current_sequence: list[Message] = []

        i = 0
        while i < len(messages):
            msg = messages[i]
            current_sequence.append(msg)

            # Check if this message starts a tool call sequence
            if msg.role == "assistant" and msg.tool_calls:
                # Get all tool call IDs from this assistant
                tool_call_ids = {tc.id for tc in msg.tool_calls}

                # Include all immediately following tool messages for these IDs
                j = i + 1
                while j < len(messages) and messages[j].role == "tool":
                    if messages[j].tool_call_id in tool_call_ids:
                        current_sequence.append(messages[j])
                        j += 1
                    else:
                        # Different tool call, start new sequence
                        break
                i = j
            else:
                i += 1

            # Start a new sequence on user messages (except at the very beginning)
            # This helps with more granular pruning
            if msg.role == "user" and i < len(messages):
                sequences.append(MessageSequence(current_sequence))
                current_sequence = []

        # Add the last sequence
        if current_sequence:
            sequences.append(MessageSequence(current_sequence))

        return sequences

    def compact(self, messages: list[Message]) -> list[Message]:
        """Compact messages to fit within max_tokens.

        Always preserves system messages and the last user message.
        Prunes from the beginning of history (after system prompts).
        Preserves tool call sequences as atomic units.

        Args:
            messages: The messages to compact.

        Returns:
            Compacted messages that fit within max_tokens.
        """
        if not messages:  # pragma: no cover
            return []

        # First, enforce safety limits on individual messages
        # This prevents massive messages from breaking the token counter or API
        messages = self.enforce_safety_limits(messages)

        current_tokens = TokenCounter.count_messages(messages)
        if current_tokens <= self.max_tokens:
            return messages

        # Group messages into atomic sequences
        sequences = self._group_into_sequences(messages)

        if not sequences:
            return []

        # Separate system messages (always kept)
        system_msgs = [msg for msg in messages if msg.role == "system"]
        system_tokens = TokenCounter.count_messages(system_msgs)

        # Identify the last sequence (critical to keep if it's a user message)
        last_sequence = sequences[-1]
        last_sequence_is_user = (
            last_sequence.messages and
            last_sequence.messages[-1].role == "user"
        )

        # Calculate fixed cost (system + last sequence if it's user-initiated)
        fixed_tokens = system_tokens
        if last_sequence_is_user:
            fixed_tokens += last_sequence.token_count

        budget = self.max_tokens - fixed_tokens

        if budget <= 0:  # pragma: no cover
            # Degenerate case: essential messages already exceed limit
            result = system_msgs.copy()
            if last_sequence_is_user:
                result.extend(last_sequence.messages)
            return result

        # Keep sequences from the end until budget is full
        # We skip the last sequence if it's already accounted for as fixed
        sequences_to_consider = sequences[:-1] if last_sequence_is_user else sequences

        kept_sequences: list[MessageSequence] = []
        used_tokens = 0

        for seq in reversed(sequences_to_consider):
            if used_tokens + seq.token_count <= budget:
                kept_sequences.append(seq)
                used_tokens += seq.token_count
            else:
                # Can't fit this entire sequence, stop here
                # We don't split sequences
                break

        # Reconstruct messages in correct order
        result: list[Message] = []

        # Add system messages first
        result.extend(system_msgs)

        # Add kept sequences in chronological order
        for seq in reversed(kept_sequences):
            result.extend(seq.messages)

        # Add the last sequence if it was user-initiated
        if last_sequence_is_user:
            result.extend(last_sequence.messages)

        return result

    def validate_compacted_sequence(self, messages: list[Message]) -> bool:
        """Validate that a message sequence follows OpenAI API rules.

        Args:
            messages: The messages to validate.

        Returns:
            True if the sequence is valid, False otherwise.
        """
        for i, msg in enumerate(messages):
            if msg.role == "tool":
                # Tool messages must follow assistant with tool_calls
                if i == 0:
                    return False
                prev_msg = messages[i-1]
                if prev_msg.role != "assistant" or not prev_msg.tool_calls:
                    return False

                # Tool call ID must match one of the assistant's tool calls
                tool_call_ids = {tc.id for tc in prev_msg.tool_calls}
                if msg.tool_call_id not in tool_call_ids:
                    return False

        # Additional check: assistant with tool_calls should have tool responses
        for i, msg in enumerate(messages):
            if msg.role == "assistant" and msg.tool_calls:
                tool_call_ids = {tc.id for tc in msg.tool_calls}
                j = i + 1
                while j < len(messages) and messages[j].role == "tool":
                    if messages[j].tool_call_id in tool_call_ids:
                        tool_call_ids.remove(messages[j].tool_call_id)
                    j += 1

                # If there are still tool calls without responses, it's invalid
                if tool_call_ids:
                    return False

        return True

    def compact_with_result(self, messages: list[Message]) -> CompactionResult:
        """Compact messages and return detailed result.

        Args:
            messages: The messages to compact.

        Returns:
            CompactionResult with compacted messages and metadata.
        """
        if not messages:
            return CompactionResult(messages=[], was_compacted=False)

        current_tokens = TokenCounter.count_messages(messages)
        if current_tokens <= self.max_tokens:
            return CompactionResult(messages=messages, was_compacted=False)

        # Perform compaction
        compacted = self.compact(messages)
        dropped_count = len(messages) - len(compacted)

        return CompactionResult(
            messages=compacted,
            was_compacted=True,
            dropped_count=dropped_count,
        )


class MessageSummarizer:
    """Summarizes dropped messages for context preservation.

    Uses the LLM provider to generate a concise summary of messages
    that are being dropped during compaction.
    """

    SUMMARY_PROMPT = """Summarize the following conversation excerpt in 2-3 sentences.
Focus on key decisions, facts learned, and important context that should be remembered.
Be concise but preserve critical information.

Conversation:
{messages}

Summary:"""

    def __init__(self, provider: ModelProvider | None = None) -> None:
        """Initialize the summarizer.

        Args:
            provider: Model provider for generating summaries.
                If None, summarization will be skipped.
        """
        self.provider = provider
        self._cached_summary: str | None = None

    def _format_messages_for_summary(self, messages: list[Message]) -> str:
        """Format messages into a readable string for summarization.

        Args:
            messages: Messages to format.

        Returns:
            Formatted string representation.
        """
        lines = []
        for msg in messages:
            if msg.role == "system":
                continue  # Skip system messages
            prefix = msg.role.upper()
            content = msg.content or ""
            if msg.tool_calls:
                tool_names = [tc.name for tc in msg.tool_calls]
                content += f" [Called tools: {', '.join(tool_names)}]"
            if msg.tool_call_id:
                content = f"[Tool result] {content[:200]}..."
            lines.append(f"{prefix}: {content[:500]}")
        return "\n".join(lines)

    async def summarize(self, messages: list[Message]) -> str | None:
        """Generate a summary of the given messages.

        Args:
            messages: Messages to summarize.

        Returns:
            Summary string, or None if summarization failed/unavailable.
        """
        if not self.provider or not messages:
            return None

        # Filter out system messages for summarization
        msgs_to_summarize = [m for m in messages if m.role != "system"]
        if not msgs_to_summarize:
            return None

        formatted = self._format_messages_for_summary(msgs_to_summarize)
        prompt = self.SUMMARY_PROMPT.format(messages=formatted)

        try:
            summary_parts: list[str] = []
            async for chunk in self.provider.chat_completion_stream(
                messages=[Message(role="user", content=prompt)],
                tools=None,
            ):
                if chunk.content:
                    summary_parts.append(chunk.content)
                if chunk.finish_reason:
                    break

            summary = "".join(summary_parts).strip()
            if summary:
                self._cached_summary = summary
                return summary
        except Exception:
            # Summarization failed, return None to fall back to simple dropping
            pass

        return None

    def create_summary_message(self, summary: str) -> Message:
        """Create a system message containing the conversation summary.

        Args:
            summary: The summary text.

        Returns:
            A Message object with the summary.
        """
        return Message(
            role="system",
            content=f"[Summary of earlier conversation: {summary}]",
        )


async def compact_with_summarization(
    messages: list[Message],
    max_tokens: int,
    provider: ModelProvider | None = None,
    summarize: bool = True,
) -> CompactionResult:
    """Compact messages with optional summarization of dropped content.

    This function performs compaction and optionally summarizes the
    dropped messages to preserve context. If summarization fails,
    it falls back to simple dropping.

    Args:
        messages: Messages to compact.
        max_tokens: Maximum tokens to keep.
        provider: Model provider for summarization (optional).
        summarize: Whether to attempt summarization.

    Returns:
        CompactionResult with compacted messages and metadata.
    """
    compactor = ContextCompactor(max_tokens=max_tokens)

    # Check if compaction is needed
    current_tokens = TokenCounter.count_messages(messages)
    if current_tokens <= max_tokens:
        return CompactionResult(messages=messages, was_compacted=False)

    # Get the compacted result
    result = compactor.compact_with_result(messages)

    if not result.was_compacted:
        return result

    # Identify dropped messages for summarization
    kept_set = {id(m) for m in result.messages}
    dropped_messages = [m for m in messages if id(m) not in kept_set]

    # Attempt summarization if enabled and we have a provider
    if summarize and provider and dropped_messages:
        summarizer = MessageSummarizer(provider=provider)
        try:
            summary = await summarizer.summarize(dropped_messages)
            if summary:
                # Insert summary after system messages
                system_msgs = [m for m in result.messages if m.role == "system"]
                non_system = [m for m in result.messages if m.role != "system"]
                summary_msg = summarizer.create_summary_message(summary)

                result.messages = system_msgs + [summary_msg] + non_system
                result.summary = summary
        except Exception:
            # Summarization failed, continue with simple dropping
            pass

    return result
