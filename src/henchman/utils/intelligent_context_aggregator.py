"""Aggregator and validator for intelligent context management.

This module provides tools for message preservation and sequence validation
during context compaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.utils.intelligent_context_types import IntelligentContextConstants
from henchman.utils.sorting_utils import sort_by_importance

if TYPE_CHECKING:
    from henchman.providers.base import Message
    from henchman.utils.intelligent_context_config import IntelligentContextConfig


class ImportanceSorter:
    """Utility class for sorting items by importance scores."""

    @staticmethod
    def sort_by_importance(
        item_count: int,
        importance_scores: dict[int, float],
    ) -> list[int]:
        """Sort indices by importance scores (descending).

        Args:
            item_count: Number of items to sort.
            importance_scores: Importance scores for each item.

        Returns:
            List of indices sorted by importance (descending).

        """
        return sort_by_importance(item_count, importance_scores)


class _ToolSequenceValidator:
    """Helper class to validate tool call sequences.

    This class addresses the feature envy code smell by encapsulating
    the validation logic and state management.
    """

    def __init__(self: _ToolSequenceValidator, messages: list[Message]) -> None:
        """Initialize validator with messages to check.

        Args:
            messages: The messages to validate.

        """
        self.messages = messages
        self.pending_tool_calls: set[str] = set()
        self.current_assistant_index: int | None = None

    def validate(self: _ToolSequenceValidator) -> bool:
        """Validate the entire message sequence.

        Returns:
            True if tool sequences are valid, False otherwise.

        """
        for i, msg in enumerate(self.messages):
            if not self._process_message(i, msg):
                return False

        # At the end, check if all tool calls were responded to
        return not self.pending_tool_calls

    def _process_message(self: _ToolSequenceValidator, index: int, msg: Message) -> bool:
        """Process a single message in the sequence.

        Args:
            index: Message index in the sequence.
            msg: The message to process.

        Returns:
            True if message is valid, False otherwise.

        """
        if msg.role == "tool":
            return self._process_tool_message(index, msg)

        if msg.role == "assistant":
            return self._process_assistant_message(index, msg)

        # User and system messages don't affect tool sequence validation
        return True

    def _process_tool_message(self: _ToolSequenceValidator, index: int, msg: Message) -> bool:
        """Process a tool message.

        Args:
            index: Message index.
            msg: Tool message to process.

        Returns:
            True if tool message is valid, False otherwise.

        """
        # Tool messages must not be first
        if index == 0:
            return False

        # Tool must follow an assistant with pending tool calls
        if self.current_assistant_index is None:
            return False

        # Check if tool_call_id matches a pending tool call
        if msg.tool_call_id not in self.pending_tool_calls:
            return False

        # Remove this tool call from pending set
        self.pending_tool_calls.discard(msg.tool_call_id)

        # If all tool calls are responded to, reset for next assistant
        if not self.pending_tool_calls:
            self.current_assistant_index = None

        return True

    def _process_assistant_message(self: _ToolSequenceValidator, index: int, msg: Message) -> bool:
        """Process an assistant message.

        Args:
            index: Message index.
            msg: Assistant message to process.

        Returns:
            True if assistant message is valid, False otherwise.

        """
        if msg.tool_calls:
            return self._process_assistant_with_tools(index, msg)

        return self._process_assistant_without_tools()

    def _process_assistant_with_tools(
        self: _ToolSequenceValidator,
        index: int,
        msg: Message,
    ) -> bool:
        """Process an assistant message with tool calls.

        Args:
            index: Message index.
            msg: Assistant message with tool calls.

        Returns:
            True if assistant message with tools is valid, False otherwise.

        """
        # Check if this is a duplicate of the current assistant message
        is_duplicate = self._check_if_duplicate_assistant(msg)

        # If we encounter a new assistant with tool calls while we still have
        # pending tool calls from previous assistant, that's invalid unless it's a duplicate
        if self.pending_tool_calls and not is_duplicate:
            return False

        # Start tracking new set of tool calls (or continue tracking same set for duplicate)
        if not is_duplicate and msg.tool_calls:
            self.pending_tool_calls = {tc.id for tc in msg.tool_calls}
            self.current_assistant_index = index

        return True

    def _process_assistant_without_tools(self: _ToolSequenceValidator) -> bool:
        """Process an assistant message without tool calls.

        Returns:
            True if assistant message without tools is valid, False otherwise.

        """
        # Regular assistant message - if we have pending tool calls, that's invalid
        return not self.pending_tool_calls

    def _check_if_duplicate_assistant(
        self: _ToolSequenceValidator,
        msg: Message,
    ) -> bool:
        """Check if assistant message is a duplicate of current assistant.

        Args:
            msg: Assistant message to check.

        Returns:
            True if message is a duplicate, False otherwise.

        """
        idx = self.current_assistant_index
        if idx is None or not self.pending_tool_calls:
            return False

        prev_msg = self.messages[idx]
        return _are_duplicate_assistant_messages(msg, prev_msg, idx)


class SequenceValidator:
    """Validates message sequences follow API rules and semantic constraints."""

    @staticmethod
    def validate_compacted_sequence(messages: list[Message]) -> bool:
        """Validate that a message sequence follows OpenAI API rules with semantic checks.

        Enhanced validation includes:
        - Structural API compliance (tool call sequences, role ordering)
        - Semantic consistency (related content, logical flow)
        - Context preservation (critical information not lost)

        Args:
            messages: The messages to validate.

        Returns:
            True if the sequence is valid, False otherwise.

        """
        if not messages:
            return True

        # 0. Validate roles are valid (lowercase)
        if not _validate_role_names(messages):
            return False

        # 1. Structural validation
        if not _validate_tool_sequences(messages):
            return False

        # 2. Semantic validation - check for logical conversation flow
        if not _validate_conversation_flow(messages):
            return False

        # 3. Context preservation check
        if not _validate_system_prompt(messages):
            return False

        # 4. Check for duplicate consecutive messages (compression artifact)
        return _validate_no_duplicate_consecutive_messages(messages)


def _validate_tool_sequences(messages: list[Message]) -> bool:
    """Validate tool call sequences follow OpenAI API rules.

    Args:
        messages: The messages to validate.

    Returns:
        True if tool sequences are valid, False otherwise.

    """
    validator = _ToolSequenceValidator(messages)
    return validator.validate()


def _are_duplicate_assistant_messages(
    current_msg: Message,
    prev_msg: Message,
    prev_msg_index: int | None,
) -> bool:
    """Check if current assistant message is a duplicate of previous.

    Args:
        current_msg: Current assistant message.
        prev_msg: Previous assistant message.
        prev_msg_index: Index of previous assistant message.

    Returns:
        True if messages are duplicates, False otherwise.

    """
    if prev_msg_index is None:
        return False

    # Check content and tool calls match
    if current_msg.content != prev_msg.content:
        return False

    # Check tool calls match
    if not current_msg.tool_calls or not prev_msg.tool_calls:
        return False

    current_ids = {tc.id for tc in current_msg.tool_calls}
    prev_ids = {tc.id for tc in prev_msg.tool_calls}
    return current_ids == prev_ids


def _validate_conversation_flow(messages: list[Message]) -> bool:
    """Validate logical conversation flow.

    Args:
        messages: The messages to validate.

    Returns:
        True if conversation flow is valid, False otherwise.

    """
    for i in range(1, len(messages)):
        curr = messages[i]
        prev = messages[i - 1]

        # Assistant should generally follow user or tool messages
        if curr.role == "assistant" and prev.role not in ["user", "tool"]:
            # Unless it's a continuation of a multi-turn assistant response
            if prev.role == "assistant" and prev.tool_calls:
                # This is fine - assistant continuing after tool calls
                continue
            # Also fine if it's the first message (system prompt scenario)
            if i == 1 and messages[0].role == "system":
                continue
            return False
    return True


def _validate_system_prompt(messages: list[Message]) -> bool:
    """Validate system prompt is preserved and not corrupted.

    Args:
        messages: The messages to validate.

    Returns:
        True if system prompt is valid, False otherwise.

    """
    if not messages:
        return True

    first_msg = messages[0]
    if first_msg.role == "system":
        content = first_msg.content
        return bool(content and len(content.strip()) > 0)
    return True


def _validate_role_names(messages: list[Message]) -> bool:
    """Validate that message roles are valid OpenAI API roles (lowercase).

    Args:
        messages: The messages to validate.

    Returns:
        True if all roles are valid, False otherwise.

    """
    valid_roles = {"system", "user", "assistant", "tool"}
    return all(msg.role in valid_roles for msg in messages)


def _validate_no_duplicate_consecutive_messages(messages: list[Message]) -> bool:
    """Check for duplicate consecutive messages (compression artifact).

    Args:
        messages: The messages to validate.

    Returns:
        True if no duplicate consecutive messages, False otherwise.

    """
    for i in range(1, len(messages)):
        curr = messages[i]
        prev = messages[i - 1]
        if (
            curr.role == prev.role
            and curr.content
            and prev.content
            and curr.content.strip() == prev.content.strip()
            and not curr.tool_calls
            and not prev.tool_calls
        ):
            return False
    return True


class MessagePreserver:
    """Preserves critical messages during context compaction.

    Responsible for ensuring important context is not lost during
    compression operations.
    """

    def __init__(self: MessagePreserver, config: IntelligentContextConfig) -> None:
        """Initialize message preserver.

        Args:
            config: Configuration for preservation logic.

        """
        self.config = config

    def preserve_critical_context(
        self: MessagePreserver,
        messages: list[Message],
        importance_scores: dict[int, float],
    ) -> list[Message]:
        """Ensure critical context is preserved regardless of token limits.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.

        Returns:
            Messages with critical context preserved.

        """
        if not messages:
            return []

        # Track which messages we've preserved
        preserved_indices: set[int] = set()

        # Phases of preservation
        self._run_preservation_phases(messages, importance_scores, preserved_indices)

        # Sort preserved messages back to original order
        indexed_preserved = []
        for i, msg in enumerate(messages):
            if i in preserved_indices:
                indexed_preserved.append(msg)

        return indexed_preserved

    def _run_preservation_phases(
        self: MessagePreserver,
        messages: list[Message],
        importance_scores: dict[int, float],
        preserved_indices: set[int],
    ) -> None:
        """Run all phases of message preservation.

        Args:
            messages: Original messages.
            importance_scores: Importance scores.
            preserved_indices: Set to track preserved indices.

        """
        # Phase 1: Always preserve system messages (highest priority)
        self._preserve_system_messages(messages, preserved_indices)

        # Phase 2: Preserve recent high-importance messages
        self._preserve_recent_high_importance_messages(
            messages,
            importance_scores,
            preserved_indices,
        )

        # Phase 3: Preserve tool call sequences
        _preserve_tool_call_sequences(messages, preserved_indices)

        # Phase 4: Preserve messages with critical content
        self._preserve_critical_content_messages(messages, preserved_indices)

        # Phase 5: Ensure we preserve at least some conversation flow
        self._preserve_conversation_flow(messages, preserved_indices)

    def _preserve_system_messages(
        self: MessagePreserver,
        messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve all system messages.

        Args:
            messages: Original messages.
            preserved_indices: Set of indices already preserved.

        """
        for i, msg in enumerate(messages):
            if msg.role == "system":
                preserved_indices.add(i)

    def _preserve_recent_high_importance_messages(
        self: MessagePreserver,
        messages: list[Message],
        importance_scores: dict[int, float],
        preserved_indices: set[int],
    ) -> None:
        """Preserve recent messages with high importance scores.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            preserved_indices: Set of indices already preserved.

        """
        # Start from the end (most recent) and work backwards
        for i in range(len(messages) - 1, -1, -1):
            if i in preserved_indices:
                continue

            importance = importance_scores.get(i, 0.0)
            if importance >= self.config.importance_threshold:
                preserved_indices.add(i)

                # Limit to reasonable number of recent high-importance messages
                recent_window = IntelligentContextConstants.RECENT_MESSAGES_WINDOW
                recent_limit = IntelligentContextConstants.MIN_RECENT_MESSAGES_TO_PRESERVE
                recent_count = sum(
                    1
                    for idx in preserved_indices
                    if idx >= len(messages) - recent_window
                )
                if recent_count >= recent_limit:
                    break

    def _preserve_critical_content_messages(
        self: MessagePreserver,
        messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve messages with critical content (errors, decisions, code blocks).

        Args:
            messages: Original messages.
            preserved_indices: Set of indices already preserved.

        """
        critical_keywords = IntelligentContextConstants.CRITICAL_KEYWORDS

        for i, msg in enumerate(messages):
            if i in preserved_indices:
                continue

            content = msg.content
            if not content:
                continue

            # Check for critical keywords
            content_lower = content.lower()
            if (
                any(keyword in content_lower for keyword in critical_keywords)
                or "```" in content
            ):
                preserved_indices.add(i)

    def _preserve_conversation_flow(
        self: MessagePreserver,
        messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Ensure we preserve at least some conversation flow.

        Args:
            messages: Original messages.
            preserved_indices: Set of indices already preserved.

        """
        for i, msg in enumerate(messages):
            if i in preserved_indices:
                continue

            if msg.role in ["user", "assistant"]:
                # Try to preserve pairs
                preserved_indices.add(i)

                # Limit to reasonable number
                max_preserved = IntelligentContextConstants.MAX_PRESERVED_INDICES
                if len(preserved_indices) >= min(
                    max_preserved,
                    len(messages),
                ):
                    break


def _preserve_tool_call_sequences(
    messages: list[Message],
    preserved_indices: set[int],
) -> None:
    """Preserve complete tool call sequences.

    Scans adjacent message pairs for assistant-to-tool hand-offs and
    ensures both sides of each pair are kept in ``preserved_indices``.

    Args:
        messages: Original messages.
        preserved_indices: Set of indices already preserved (mutated in place).

    """
    for i in range(len(messages) - 1):
        if i in preserved_indices or (i + 1) in preserved_indices:
            continue

        curr_msg = messages[i]
        next_msg = messages[i + 1]

        if (
            curr_msg.role == "assistant"
            and curr_msg.tool_calls
            and next_msg.role == "tool"
            and next_msg.tool_call_id
        ):
            # Verify tool_call_id matches one of the pending tool calls
            tool_call_ids = {tc.id for tc in curr_msg.tool_calls}
            if next_msg.tool_call_id in tool_call_ids:
                preserved_indices.add(i)
                preserved_indices.add(i + 1)
