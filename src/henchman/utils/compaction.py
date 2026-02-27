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
        return any(msg.role == "assistant" and msg.tool_calls for msg in self.messages)

    def __repr__(self) -> str:
        roles = [msg.role for msg in self.messages]
        return f"MessageSequence(roles={roles}, tokens={self.token_count})"


class ContextCompactor:
    """Manages context size by pruning older messages.

    Preserves atomic sequences, especially tool call sequences.
    Supports a protected zone for current-turn messages that won't be dropped.
    """

    def __init__(
        self,
        max_tokens: int = 8000,
        max_protected_ratio: float = 0.3,
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

    def enforce_safety_limits(self, messages: list[Message]) -> list[Message]:
        """Enforce limits on individual message size using tokens.

        This prevents context overflow from individual massive messages
        by truncating them to fit within the context window.

        Args:
            messages: List of messages to check.

        Returns:
            List of messages with content limits enforced.
        """
        safe_messages = []
        # Reserve tokens for overhead/other messages.
        # We use 75% of max_tokens to allow for message overhead, system prompts,
        # and the truncation suffix itself.
        limit = int(self.max_tokens * 0.75)

        for msg in messages:
            if not msg.content:
                safe_messages.append(msg)
                continue

            # Quick character check optimization:
            # If chars < limit, tokens are definitely < limit (1 token >= 1 char usually)
            # Actually, 1 token ~ 4 chars. So if chars < limit, it's definitely safe?
            # No, if chars < limit, tokens could be anything.
            # But if chars < limit (tokens), then tokens < limit is guaranteed since token count <= char count?
            # Tiktoken: "hello" (5 chars) -> 1 token. " " (1 char) -> 1 token.
            # Generally token count < char count.
            # So if len(msg.content) < limit, we are safe.
            if len(msg.content) < limit:
                safe_messages.append(msg)
                continue

            # Check token count
            if TokenCounter.count_text(msg.content) > limit:
                # Truncate
                truncated_content = TokenCounter.truncate_text(msg.content, limit)
                new_content = (
                    truncated_content + f"\n... (truncated by safety limit: > {limit} tokens)"
                )

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
        # Track which message indices have been consumed by a tool sequence
        consumed_indices: set[int] = set()

        i = 0
        while i < len(messages):
            if i in consumed_indices:
                i += 1
                continue

            msg = messages[i]
            current_sequence.append(msg)

            # Check if this message starts a tool call sequence
            if msg.role == "assistant" and msg.tool_calls:
                # Get all tool call IDs from this assistant
                tool_call_ids = {tc.id for tc in msg.tool_calls}

                # Scan ALL following messages to find tool responses for these IDs
                # This handles cases where tool messages might not be immediately consecutive
                for j in range(i + 1, len(messages)):
                    tool_call_id = messages[j].tool_call_id
                    if messages[j].role == "tool" and tool_call_id in tool_call_ids:
                        current_sequence.append(messages[j])
                        consumed_indices.add(j)
                        if tool_call_id is not None:
                            tool_call_ids.discard(tool_call_id)
                        # Stop if all tool calls have responses
                        if not tool_call_ids:
                            break
                    elif messages[j].role == "user":
                        # Stop at next user message - tool responses should be before this
                        break

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

    def compact(
        self,
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
        protected_msgs, unprotected_msgs = self._separate_protected_messages(
            messages, protect_from_index
        )

        # Handle protected zone truncation if needed
        protected_msgs, protected_tokens = self._handle_protected_zone_truncation(protected_msgs)

        # Extract system messages and group non-system messages into sequences
        system_msgs, system_tokens = self._extract_system_messages(unprotected_msgs)
        sequences = self._group_non_system_sequences(unprotected_msgs)

        # Calculate budget and handle edge cases
        budget_result = self._calculate_budget_and_handle_edge_cases(
            system_msgs, system_tokens, protected_msgs, protected_tokens, sequences
        )
        if budget_result is not None:
            return budget_result

        # Select which sequences to keep based on budget
        kept_sequences, last_sequence, last_sequence_is_user = self._select_sequences_to_keep(
            sequences, protected_msgs, system_tokens, protected_tokens
        )

        # Reconstruct final message list
        return self._reconstruct_result(
            system_msgs, kept_sequences, last_sequence, last_sequence_is_user, protected_msgs
        )

    def _separate_protected_messages(
        self, messages: list[Message], protect_from_index: int
    ) -> tuple[list[Message], list[Message]]:
        """Separate protected and unprotected messages based on protection index.

        Args:
            messages: All messages to separate.
            protect_from_index: Index from which messages are protected.

        Returns:
            Tuple of (protected_messages, unprotected_messages).
        """
        protected_msgs: list[Message] = []
        unprotected_msgs: list[Message] = []

        if protect_from_index >= 0 and protect_from_index < len(messages):
            unprotected_msgs = messages[:protect_from_index]
            protected_msgs = messages[protect_from_index:]
        else:
            unprotected_msgs = messages

        return protected_msgs, unprotected_msgs

    def _handle_protected_zone_truncation(
        self, protected_msgs: list[Message]
    ) -> tuple[list[Message], int]:
        """Handle truncation of protected zone if it exceeds budget.

        Args:
            protected_msgs: Protected messages to potentially truncate.

        Returns:
            Tuple of (truncated_protected_messages, protected_token_count).
        """
        protected_tokens = TokenCounter.count_messages(protected_msgs) if protected_msgs else 0

        if protected_tokens > self.max_protected_tokens and protected_msgs:
            protected_msgs = self._truncate_protected_zone(
                protected_msgs, self.max_protected_tokens
            )
            protected_tokens = TokenCounter.count_messages(protected_msgs)

        return protected_msgs, protected_tokens

    def _extract_system_messages(
        self, unprotected_msgs: list[Message]
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

    def _group_non_system_sequences(self, unprotected_msgs: list[Message]) -> list[MessageSequence]:
        """Group non-system unprotected messages into atomic sequences.

        Args:
            unprotected_msgs: Unprotected messages to group.

        Returns:
            List of message sequences.
        """
        non_system_unprotected = [msg for msg in unprotected_msgs if msg.role != "system"]
        return self._group_into_sequences(non_system_unprotected)

    def _calculate_budget_and_handle_edge_cases(
        self,
        system_msgs: list[Message],
        system_tokens: int,
        protected_msgs: list[Message],
        protected_tokens: int,
        sequences: list[MessageSequence],
    ) -> list[Message] | None:
        """Calculate budget for unprotected sequences and handle edge cases.

        Args:
            system_msgs: System messages.
            system_tokens: Token count of system messages.
            protected_msgs: Protected messages.
            protected_tokens: Token count of protected messages.
            sequences: Message sequences to consider.

        Returns:
            Compacted messages if edge case handled, None otherwise.
        """
        # Calculate budget for unprotected sequences
        # Must fit: system + kept sequences + protected zone
        budget = self.max_tokens - system_tokens - protected_tokens

        if budget <= 0:
            # Degenerate case: system + protected already exceed limit
            # Keep system and as much of protected as possible
            degenerate_result = system_msgs.copy()
            degenerate_result.extend(protected_msgs)
            return degenerate_result

        if not sequences:
            compacted_msgs = system_msgs.copy()
            compacted_msgs.extend(protected_msgs)
            return compacted_msgs

        return None

    def _select_sequences_to_keep(
        self,
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
        last_sequence_is_user = bool(last_sequence.messages) and last_sequence.messages[-1].role == "user"

        # Calculate budget
        budget = self.max_tokens - system_tokens - protected_tokens

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
        self,
        system_msgs: list[Message],
        kept_sequences: list[MessageSequence],
        last_sequence: MessageSequence,
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

    def _truncate_protected_zone(
        self,
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

        # Make copies to avoid mutating originals
        result = []
        tokens_to_trim = current_tokens - max_tokens

        for msg in messages:
            if tokens_to_trim <= 0 or msg.role != "tool":
                result.append(msg)
                continue

            # Truncate tool message content
            if msg.content and len(msg.content) > 500:
                # Estimate how much to keep (rough: 4 chars per token)
                chars_to_trim = tokens_to_trim * 4
                if chars_to_trim < len(msg.content) - 200:
                    new_content = msg.content[: len(msg.content) - chars_to_trim]
                    new_content += "\n[... truncated to fit context limit ...]"
                else:
                    new_content = msg.content[:200] + "\n[... heavily truncated ...]"

                trimmed_tokens = (len(msg.content) - len(new_content)) // 4
                tokens_to_trim -= trimmed_tokens

                result.append(
                    Message(
                        role=msg.role,
                        content=new_content,
                        tool_calls=msg.tool_calls,
                        tool_call_id=msg.tool_call_id,
                    )
                )
            else:
                result.append(msg)

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
                prev_msg = messages[i - 1]
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
                    tool_call_id = messages[j].tool_call_id
                    if tool_call_id is not None and tool_call_id in tool_call_ids:
                        tool_call_ids.discard(tool_call_id)
                    j += 1

                # If there are still tool calls without responses, it's invalid
                if tool_call_ids:
                    return False

        return True

    def compact_with_result(
        self,
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
    compactor = ContextCompactor(
        max_tokens=max_tokens,
        max_protected_ratio=max_protected_ratio,
    )

    # Check if compaction is needed
    current_tokens = TokenCounter.count_messages(messages)
    if current_tokens <= max_tokens:
        return CompactionResult(messages=messages, was_compacted=False)

    # Get the compacted result
    result = compactor.compact_with_result(messages, protect_from_index=protect_from_index)

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
