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
    from collections.abc import Callable

    from henchman.providers.base import ModelProvider


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

    def __init__(self: MessageSequence, messages: list[Message]) -> None:
        """Initialize a MessageSequence.

        Args:
            messages: List of messages that form an atomic sequence.
        """
        self.messages = messages

    @property
    def token_count(self: MessageSequence) -> int:
        """Get the token count for this sequence."""
        return TokenCounter.count_messages(self.messages)

    @property
    def is_tool_sequence(self: MessageSequence) -> bool:
        """Check if this sequence contains tool calls."""
        return any(msg.role == "assistant" and msg.tool_calls for msg in self.messages)

    def __repr__(self: MessageSequence) -> str:
        roles = [msg.role for msg in self.messages]
        return f"MessageSequence(roles={roles}, tokens={self.token_count})"


# Constants for compaction configuration
SAFETY_LIMIT_RATIO: float = 0.8
TRUNCATION_CHAR_THRESHOLD: int = 500
MIN_TRUNCATED_CONTENT: int = 200
CHARS_PER_TOKEN_ESTIMATE: int = 4
DEFAULT_MAX_TOKENS: int = 8000
DEFAULT_MAX_PROTECTED_RATIO: float = 0.3


@dataclass
class SummarizationConfig:
    """Configuration for message summarization during compaction."""
    provider: ModelProvider | None = None
    summarize: bool = True
    protect_from_index: int = -1
    max_protected_ratio: float = 0.3


class MessageSequenceGrouper:
    """Groups messages into atomic sequences that must be kept together."""

    @staticmethod
    def group_into_sequences(messages: list[Message]) -> list[MessageSequence]:
        """Group messages into atomic sequences that must be kept together.

        Rules:
        1. Each user message starts a new sequence (except the first)
        2. Assistant messages with tool_calls include all following tool messages
           for those specific tool calls (even if not immediately consecutive)
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
        consumed_indices: set[int] = set()

        i = 0
        while i < len(messages):
            i = MessageSequenceGrouper._process_next_message(
                messages, i, current_sequence, sequences, consumed_indices,
            )

        # Add the last sequence
        if current_sequence:
            sequences.append(MessageSequence(list(current_sequence)))

        return sequences

    @staticmethod
    def _process_next_message(
        messages: list[Message],
        current_index: int,
        current_sequence: list[Message],
        sequences: list[MessageSequence],
        consumed_indices: set[int],
    ) -> int:
        """Process the next message in the sequence grouping.

        Args:
            messages: All messages to process.
            current_index: Current index in messages.
            current_sequence: Current sequence being built.
            sequences: List of completed sequences.
            consumed_indices: Set of indices already consumed.

        Returns:
            Next index to process.
        """
        if current_index in consumed_indices:
            return current_index + 1

        msg = messages[current_index]
        current_sequence.append(msg)

        # Handle tool call sequences
        if msg.role == "assistant" and msg.tool_calls:
            MessageSequenceGrouper._handle_tool_call_sequence(
                messages, current_index, current_sequence, consumed_indices,
            )

        next_index = current_index + 1

        # Start a new sequence on user messages (except at the very beginning)
        if MessageSequenceGrouper._should_start_new_sequence(msg, next_index, len(messages)):
            sequences.append(MessageSequence(list(current_sequence)))
            current_sequence.clear()

        return next_index

    @staticmethod
    def _handle_tool_call_sequence(
        messages: list[Message],
        current_index: int,
        current_sequence: list[Message],
        consumed_indices: set[int],
    ) -> None:
        """Handle tool call sequence by finding all related tool responses.

        Args:
            messages: All messages in the conversation.
            current_index: Index of the assistant message with tool calls.
            current_sequence: Current sequence being built.
            consumed_indices: Set of indices already consumed by tool sequences.
        """
        msg = messages[current_index]
        tool_call_ids = {tc.id for tc in msg.tool_calls} if msg.tool_calls else set()

        # Scan following messages for tool responses
        for j in range(current_index + 1, len(messages)):
            if messages[j].role == "user":
                break  # Stop at next user message

            tool_call_id = messages[j].tool_call_id
            if messages[j].role == "tool" and tool_call_id in tool_call_ids:
                current_sequence.append(messages[j])
                consumed_indices.add(j)
                if tool_call_id is not None:
                    tool_call_ids.discard(tool_call_id)
                if not tool_call_ids:
                    break  # All tool calls have responses

    @staticmethod
    def _should_start_new_sequence(
        current_message: Message, current_index: int, total_messages: int,
    ) -> bool:
        """Determine if a new sequence should start.

        Args:
            current_message: The current message being processed.
            current_index: Current index in the message list.
            total_messages: Total number of messages.

        Returns:
            True if a new sequence should start, False otherwise.
        """
        return current_message.role == "user" and current_index < total_messages


class ProtectedZoneManager:
    """Manages protected zone truncation and separation."""

    def __init__(self: ProtectedZoneManager, max_protected_tokens: int) -> None:
        """Initialize protected zone manager.

        Args:
            max_protected_tokens: Maximum tokens allowed in protected zone.
        """
        self.max_protected_tokens = max_protected_tokens

    def separate_protected_messages(
        self: ProtectedZoneManager, messages: list[Message], protect_from_index: int,
    ) -> tuple[list[Message], list[Message]]:
        """Separate protected and unprotected messages based on protection index.

        Args:
            messages: All messages to separate.
            protect_from_index: Index from which messages are protected.

        Returns:
            Tuple of (protected_messages, unprotected_messages).
        """
        if protect_from_index >= 0 and protect_from_index < len(messages):
            unprotected_msgs = messages[:protect_from_index]
            protected_msgs = messages[protect_from_index:]
        else:
            unprotected_msgs = messages
            protected_msgs = []

        return protected_msgs, unprotected_msgs

    def truncate_if_needed(self: ProtectedZoneManager, messages: list[Message]) -> tuple[list[Message], int]:  # noqa: E501
        """Truncate protected zone if it exceeds budget.

        Args:
            messages: Protected messages to potentially truncate.

        Returns:
            Tuple of (truncated_messages, token_count).
        """
        protected_tokens = TokenCounter.count_messages(messages) if messages else 0

        if protected_tokens > self.max_protected_tokens and messages:
            messages = self._truncate_protected_zone(messages, self.max_protected_tokens)
            protected_tokens = TokenCounter.count_messages(messages)

        return messages, protected_tokens

    def _truncate_protected_zone(
        self: ProtectedZoneManager,
        messages: list[Message],
        max_tokens: int,
    ) -> list[Message]:
        """Truncate protected zone to fit within budget.

        Truncates tool result content (oldest first) while preserving
        structure. Never drops messages entirely, just truncates content.

        Args:
            messages: Protected zone messages.
            max_tokens: Maximum tokens allowed for protected zone.

        Returns:
            Messages with truncated content to fit budget.
        """
        current_tokens = TokenCounter.count_messages(messages)
        if current_tokens <= max_tokens:
            return messages

        result = []
        tokens_to_trim = current_tokens - max_tokens

        for msg in messages:
            if tokens_to_trim <= 0 or msg.role != "tool":
                result.append(msg)
                continue

            # Truncate tool message content
            content = msg.content
            if content and len(content) > TRUNCATION_CHAR_THRESHOLD:
                truncated_msg = _truncate_tool_message_content(msg, tokens_to_trim)
                # truncated_msg.content is guaranteed to be non-None since we checked content
                trimmed_tokens = (len(content) - len(truncated_msg.content or "")) // CHARS_PER_TOKEN_ESTIMATE  # noqa: E501
                tokens_to_trim -= trimmed_tokens
                result.append(truncated_msg)
            else:
                result.append(msg)

        return result


def _truncate_tool_message_content(message: Message, tokens_to_trim: int) -> Message:
    """Truncate a single tool message's content.

    Args:
        message: Tool message to truncate.
        tokens_to_trim: Number of tokens to trim.

    Returns:
        Truncated message.
    """
    if not message.content:
        return message

    chars_to_trim = tokens_to_trim * CHARS_PER_TOKEN_ESTIMATE
    if chars_to_trim < len(message.content) - MIN_TRUNCATED_CONTENT:
        new_content = message.content[: len(message.content) - chars_to_trim]
        new_content += "\n[... truncated to fit context limit ...]"
    else:
        new_content = message.content[:MIN_TRUNCATED_CONTENT] + "\n[... heavily truncated ...]"

    return Message(
        role=message.role,
        content=new_content,
        tool_calls=message.tool_calls,
        tool_call_id=message.tool_call_id,
    )


class CompactionBudgetCalculator:
    """Calculates budgets and handles edge cases for compaction."""

    def __init__(self: CompactionBudgetCalculator, max_tokens: int) -> None:
        """Initialize budget calculator.

        Args:
            max_tokens: Maximum total tokens allowed.
        """
        self.max_tokens = max_tokens

    def calculate_budget(
        self: CompactionBudgetCalculator,
        system_tokens: int,
        protected_tokens: int,
    ) -> int:
        """Calculate budget for unprotected sequences.

        Args:
            system_tokens: Token count of system messages.
            protected_tokens: Token count of protected messages.

        Returns:
            Budget for unprotected sequences.
        """
        return self.max_tokens - system_tokens - protected_tokens

    def handle_edge_cases(
        self: CompactionBudgetCalculator,
        system_msgs: list[Message],
        system_tokens: int,
        protected_msgs: list[Message],
        protected_tokens: int,
        sequences: list[MessageSequence],
    ) -> list[Message] | None:
        """Handle edge cases where compaction is trivial or impossible.

        Args:
            system_msgs: System messages.
            system_tokens: Token count of system messages.
            protected_msgs: Protected messages.
            protected_tokens: Token count of protected messages.
            sequences: Message sequences to consider.

        Returns:
            Compacted messages if edge case handled, None otherwise.
        """
        budget = self.calculate_budget(system_tokens, protected_tokens)

        if budget <= 0:
            # Degenerate case: system + protected already exceed limit
            degenerate_result = system_msgs.copy()
            degenerate_result.extend(protected_msgs)
            return degenerate_result

        if not sequences:
            compacted_msgs = system_msgs.copy()
            compacted_msgs.extend(protected_msgs)
            return compacted_msgs

        return None


class MessageSequenceValidator:
    """Validates message sequences follow OpenAI API rules."""

    @staticmethod
    def validate_compacted_sequence(messages: list[Message]) -> bool:
        """Validate that a message sequence follows OpenAI API rules.

        Args:
            messages: The messages to validate.

        Returns:
            True if the sequence is valid, False otherwise.
        """
        for i, msg in enumerate(messages):
            if msg.role == "tool" and not MessageSequenceValidator._is_valid_tool_message(messages, i, msg):  # noqa: E501
                return False

        # Check that all tool calls have responses
        return MessageSequenceValidator._all_tool_calls_have_responses(messages)

    @staticmethod
    def _is_valid_tool_message(
        messages: list[Message], index: int, tool_message: Message,
    ) -> bool:
        """Validate a single tool message.

        Args:
            messages: All messages in the sequence.
            index: Index of the tool message.
            tool_message: The tool message to validate.

        Returns:
            True if the tool message is valid, False otherwise.
        """
        # Tool messages must follow assistant with tool_calls
        if index == 0:
            return False

        prev_msg = messages[index - 1]
        if prev_msg.role != "assistant" or not prev_msg.tool_calls:
            return False

        # Tool call ID must match one of the assistant's tool calls
        tool_call_ids = {tc.id for tc in prev_msg.tool_calls}
        return tool_message.tool_call_id in tool_call_ids

    @staticmethod
    def _all_tool_calls_have_responses(messages: list[Message]) -> bool:
        """Check that all tool calls have corresponding responses.

        Args:
            messages: All messages in the sequence.

        Returns:
            True if all tool calls have responses, False otherwise.
        """
        for i, msg in enumerate(messages):
            if msg.role == "assistant" and msg.tool_calls:
                tool_call_ids = {tc.id for tc in msg.tool_calls}
                j = i + 1
                while j < len(messages) and messages[j].role == "tool":
                    tool_call_id = messages[j].tool_call_id
                    if tool_call_id is not None and tool_call_id in tool_call_ids:
                        tool_call_ids.discard(tool_call_id)
                    j += 1

                # If there are still tool calls without responses, it's invalid
                if tool_call_ids:
                    return False

        return True


def _enforce_message_content_safety(message: Message, limit: int) -> Message:
    """Enforce safety limit on a single message's content.

    Args:
        message: Message to check.
        limit: Maximum token limit.

    Returns:
        Safe message (possibly truncated).
    """
    if not message.content:
        return message

    # Quick character check optimization
    if len(message.content) < limit:
        return message

    # Check token count
    if TokenCounter.count_text(message.content) > limit:
        truncated_content = TokenCounter.truncate_text(message.content, limit)
        new_content = (
            truncated_content + f"\n... (truncated by safety limit: > {limit} tokens)"
        )
        return Message(
            role=message.role,
            content=new_content,
            tool_calls=message.tool_calls,
            tool_call_id=message.tool_call_id,
        )

    return message


class ContextCompactor:
    """Manages context size by pruning older messages.

    Preserves atomic sequences, especially tool call sequences.
    Supports a protected zone for current-turn messages that won't be dropped.
    """

    def __init__(
        self: ContextCompactor,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_protected_ratio: float = DEFAULT_MAX_PROTECTED_RATIO,
    ) -> None:
        """Initialize compactor.

        Args:
            max_tokens: Maximum tokens to keep in context.
            max_protected_ratio: Maximum ratio of context that can be protected.
                If protected zone exceeds this, oldest protected content is truncated.
        """
        self.max_tokens = max_tokens
        self.max_protected_ratio = max_protected_ratio
        self.max_protected_tokens = int(max_tokens * max_protected_ratio)
        self.protected_zone_manager = ProtectedZoneManager(self.max_protected_tokens)
        self.budget_calculator = CompactionBudgetCalculator(max_tokens)
        self.sequence_grouper = MessageSequenceGrouper()
        self.sequence_validator = MessageSequenceValidator()

    def enforce_safety_limits(self: ContextCompactor, messages: list[Message]) -> list[Message]:
        """Enforce limits on individual message size using tokens.

        This prevents context overflow from individual massive messages
        by truncating them to fit within the context window.

        Args:
            messages: List of messages to check.

        Returns:
            List of messages with content limits enforced.
        """
        limit = int(self.max_tokens * SAFETY_LIMIT_RATIO)
        return [self._enforce_message_safety(msg, limit) for msg in messages]

    def _enforce_message_safety(self: ContextCompactor, message: Message, limit: int) -> Message:
        """Enforce safety limit on a single message.

        Args:
            message: Message to check.
            limit: Maximum token limit.

        Returns:
            Safe message (possibly truncated).
        """
        return _enforce_message_content_safety(message, limit)

    def _group_into_sequences(self: ContextCompactor, messages: list[Message]) -> list[MessageSequence]:  # noqa: E501
        """Group messages into atomic sequences that must be kept together.

        Args:
            messages: The messages to group.

        Returns:
            List of MessageSequence objects.
        """
        return self.sequence_grouper.group_into_sequences(messages)

    def compact(
        self: ContextCompactor,
        messages: list[Message],
        protect_from_index: int = -1,
    ) -> list[Message]:
        """Compact messages to fit within max_tokens.

        Always preserves system messages and the last user message.
        Messages at or after protect_from_index are protected from dropping
        (up to max_protected_ratio of context).
        Prunes from the beginning of history (after system prompts).
        Preserves tool call sequences as atomic units.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.
                Set to -1 to disable protection (default behavior).

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

        # Separate protected and unprotected messages
        protected_msgs, unprotected_msgs = self.protected_zone_manager.separate_protected_messages(
            messages, protect_from_index,
        )

        # Handle protected zone truncation if needed
        protected_msgs, protected_tokens = self.protected_zone_manager.truncate_if_needed(protected_msgs)  # noqa: E501

        # Extract system messages and group non-system messages into sequences
        system_msgs, system_tokens = self._extract_system_messages(unprotected_msgs)
        sequences = self._group_non_system_sequences(unprotected_msgs)

        # Calculate budget and handle edge cases
        budget_result = self.budget_calculator.handle_edge_cases(
            system_msgs, system_tokens, protected_msgs, protected_tokens, sequences,
        )
        if budget_result is not None:
            return budget_result

        # Select which sequences to keep based on budget
        kept_sequences, last_sequence, last_sequence_is_user = self._select_sequences_to_keep(
            sequences, protected_msgs, system_tokens, protected_tokens,
        )

        # Reconstruct final message list
        return self._reconstruct_result(
            system_msgs, kept_sequences, last_sequence,
            last_sequence_is_user=last_sequence_is_user, protected_msgs=protected_msgs,
        )





    def _extract_system_messages(
        self: ContextCompactor, unprotected_msgs: list[Message],
    ) -> tuple[list[Message], int]:
        """Extract system messages from unprotected messages.

        Args:
            unprotected_msgs: Unprotected messages to extract from.

        Returns:
            Tuple of (system_messages, system_token_count).
        """
        system_msgs = [msg for msg in unprotected_msgs if msg.role == "system"]
        system_tokens = TokenCounter.count_messages(system_msgs)
        return system_msgs, system_tokens

    def _group_non_system_sequences(self: ContextCompactor, unprotected_msgs: list[Message]) -> list[MessageSequence]:  # noqa: E501
        """Group non-system unprotected messages into atomic sequences.

        Args:
            unprotected_msgs: Unprotected messages to group.

        Returns:
            List of message sequences.
        """
        non_system_unprotected = [msg for msg in unprotected_msgs if msg.role != "system"]
        return self._group_into_sequences(non_system_unprotected)



    def _select_sequences_to_keep(
        self: ContextCompactor,
        sequences: list[MessageSequence],
        protected_msgs: list[Message],
        system_tokens: int,
        protected_tokens: int,
    ) -> tuple[list[MessageSequence], MessageSequence, bool]:
        """Select which sequences to keep based on budget.

        Args:
            sequences: All message sequences.
            protected_msgs: Protected messages.
            system_tokens: Token count of system messages.
            protected_tokens: Token count of protected messages.

        Returns:
            Tuple of (kept_sequences, last_sequence, last_sequence_is_user).
        """
        # Identify the last unprotected sequence
        last_sequence = sequences[-1]
        last_sequence_is_user = bool(last_sequence.messages) and last_sequence.messages[-1].role == "user"  # noqa: E501

        # Calculate budget
        budget = self.budget_calculator.calculate_budget(system_tokens, protected_tokens)

        # If last unprotected sequence is user-initiated and we have no protected msgs,
        # treat it as fixed (original behavior)
        if last_sequence_is_user and not protected_msgs:
            budget -= last_sequence.token_count
            sequences_to_consider = sequences[:-1]
        else:
            sequences_to_consider = sequences

        # Keep sequences from the end until budget is full
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

        return kept_sequences, last_sequence, last_sequence_is_user

    def _reconstruct_result(
        self: ContextCompactor,
        system_msgs: list[Message],
        kept_sequences: list[MessageSequence],
        last_sequence: MessageSequence,
        *,
        last_sequence_is_user: bool,
        protected_msgs: list[Message],
    ) -> list[Message]:
        """Reconstruct final message list from components.

        Args:
            system_msgs: System messages.
            kept_sequences: Sequences to keep.
            last_sequence: Last unprotected sequence.
            last_sequence_is_user: Whether last sequence is user-initiated.
            protected_msgs: Protected messages.

        Returns:
            Final compacted message list.
        """
        result: list[Message] = []

        # Add system messages first
        result.extend(system_msgs)

        # Add kept sequences in chronological order
        for seq in reversed(kept_sequences):
            result.extend(seq.messages)

        # Add the last unprotected sequence if it was user-initiated and no protected msgs
        if last_sequence_is_user and not protected_msgs:
            result.extend(last_sequence.messages)

        # Add protected messages last (current turn)
        result.extend(protected_msgs)

        return result



    def validate_compacted_sequence(self: ContextCompactor, messages: list[Message]) -> bool:
        """Validate that a message sequence follows OpenAI API rules.

        Args:
            messages: The messages to validate.

        Returns:
            True if the sequence is valid, False otherwise.
        """
        return self.sequence_validator.validate_compacted_sequence(messages)

    def compact_with_result(
        self: ContextCompactor,
        messages: list[Message],
        protect_from_index: int = -1,
    ) -> CompactionResult:
        """Compact messages and return detailed result.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.

        Returns:
            CompactionResult with compacted messages and metadata.
        """
        if not messages:
            return CompactionResult(messages=[], was_compacted=False)

        current_tokens = TokenCounter.count_messages(messages)
        if current_tokens <= self.max_tokens:
            return CompactionResult(messages=messages, was_compacted=False)

        # Perform compaction
        compacted = self.compact(messages, protect_from_index=protect_from_index)
        dropped_count = len(messages) - len(compacted)

        return CompactionResult(
            messages=compacted,
            was_compacted=True,
            dropped_count=dropped_count,
        )


def _format_messages_for_summary_content(messages: list[Message]) -> str:
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


async def _generate_summary_with_provider(
    provider: ModelProvider,
    messages: list[Message],
    format_func: Callable[[list[Message]], str],
) -> str | None:
    """Generate summary using the provider.

    Args:
        provider: Model provider for generating summaries.
        messages: Messages to summarize.
        format_func: Function to format messages for summarization.

    Returns:
        Summary string, or None if summarization failed.
    """
    formatted = format_func(messages)
    prompt = MessageSummarizer.SUMMARY_PROMPT.format(messages=formatted)

    try:
        summary_parts: list[str] = []
        async for chunk in provider.chat_completion_stream(
            messages=[Message(role="user", content=prompt)],
            tools=None,
        ):
            if chunk.content:
                summary_parts.append(chunk.content)
            if chunk.finish_reason:
                break

        summary = "".join(summary_parts).strip()
        if summary:
            return summary
    except Exception:  # noqa: BLE001
        # Summarization failed, return None to fall back to simple dropping
        pass

    return None


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

    def __init__(self: MessageSummarizer, provider: ModelProvider | None = None) -> None:
        """Initialize the summarizer.

        Args:
            provider: Model provider for generating summaries.
                If None, summarization will be skipped.
        """
        self.provider = provider
        self._cached_summary: str | None = None

    def _format_messages_for_summary(self: MessageSummarizer, messages: list[Message]) -> str:
        """Format messages into a readable string for summarization.

        Args:
            messages: Messages to format.

        Returns:
            Formatted string representation.
        """
        return _format_messages_for_summary_content(messages)

    async def summarize(self: MessageSummarizer, messages: list[Message]) -> str | None:
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

        summary = await _generate_summary_with_provider(
            self.provider, msgs_to_summarize, self._format_messages_for_summary,
        )
        self._cached_summary = summary
        return summary

    def create_summary_message(self: MessageSummarizer, summary: str) -> Message:
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


async def compact_with_summarization(  # noqa: PLR0913
    messages: list[Message],
    max_tokens: int,
    provider: ModelProvider | None = None,
    *,
    summarize: bool = True,
    protect_from_index: int = -1,
    max_protected_ratio: float = 0.3,
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
        protect_from_index: Index from which messages are protected from dropping.
        max_protected_ratio: Maximum ratio of context that can be protected.

    Returns:
        CompactionResult with compacted messages and metadata.
    """
    config = SummarizationConfig(
        provider=provider,
        summarize=summarize,
        protect_from_index=protect_from_index,
        max_protected_ratio=max_protected_ratio,
    )
    return await _compact_with_summarization_impl(messages, max_tokens, config)


async def _compact_with_summarization_impl(
    messages: list[Message],
    max_tokens: int,
    config: SummarizationConfig,
) -> CompactionResult:
    """Implementation of compact_with_summarization using SummarizationConfig.

    Args:
        messages: Messages to compact.
        max_tokens: Maximum tokens to keep.
        config: Summarization configuration.

    Returns:
        CompactionResult with compacted messages and metadata.
    """
    compactor = ContextCompactor(
        max_tokens=max_tokens,
        max_protected_ratio=config.max_protected_ratio,
    )

    # Check if compaction is needed
    current_tokens = TokenCounter.count_messages(messages)
    if current_tokens <= max_tokens:
        return CompactionResult(messages=messages, was_compacted=False)

    # Get the compacted result
    result = compactor.compact_with_result(messages, protect_from_index=config.protect_from_index)

    if not result.was_compacted:
        return result

    # Attempt summarization if enabled
    if config.summarize and config.provider:
        result = await _attempt_summarization(result, messages, config.provider)

    return result


async def _attempt_summarization(
    result: CompactionResult,
    original_messages: list[Message],
    provider: ModelProvider,
) -> CompactionResult:
    """Attempt to summarize dropped messages and update result.

    Args:
        result: Current compaction result.
        original_messages: Original messages before compaction.
        provider: Model provider for summarization.

    Returns:
        Updated CompactionResult with summary if successful.
    """
    # Identify dropped messages for summarization
    kept_set = {id(m) for m in result.messages}
    dropped_messages = [m for m in original_messages if id(m) not in kept_set]

    if not dropped_messages:
        return result

    summarizer = MessageSummarizer(provider=provider)
    try:
        summary = await summarizer.summarize(dropped_messages)
        if summary:
            # Insert summary after system messages
            system_msgs = [m for m in result.messages if m.role == "system"]
            non_system = [m for m in result.messages if m.role != "system"]
            summary_msg = summarizer.create_summary_message(summary)

            result.messages = [*system_msgs, summary_msg, *non_system]
            result.summary = summary
    except Exception:  # noqa: BLE001
        # Summarization failed, continue with simple dropping
        pass

    return result
