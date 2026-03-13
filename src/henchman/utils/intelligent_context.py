"""Intelligent context management system.

This module provides an intelligent context manager that reduces token usage
while preserving important context through importance scoring, clustering,
and adaptive compression techniques.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, TypeVar

from typing_extensions import Self

from henchman.providers.base import Message
from henchman.utils.compression_strategy import CompressionStrategyFactory
from henchman.utils.intelligent_context_config import (
    IntelligentContextConfig,
    IntelligentContextParams,
)
from henchman.utils.intelligent_context_extractor import ContentExtractor

from henchman.utils.intelligent_context_detector import ConversationTypeDetector
from henchman.utils.intelligent_context_summarizer import SummaryGenerator

from henchman.utils.intelligent_context_parser import _ParserState
from henchman.utils.intelligent_context_types import FenceResult, IntelligentContextConstants, FenceParams

from henchman.utils.message_compactor import MessageCompactor
from henchman.utils.sorting_utils import sort_by_importance
from henchman.utils.tokens import TokenCounter

# Type variables for Self type annotations
T = TypeVar("T", bound="PreservedContent")
C = TypeVar("C", bound="IntelligentContextConfig")
V = TypeVar("V")  # Generic type variable for values

@dataclass
class PreservedContent:
    """Represents content that should be preserved during truncation.

    Attributes:
        content: The actual text content to preserve.
        tokens: The token count of the content.
        sections: The individual sections that make up the content.

    """

    content: str
    tokens: int
    sections: list[str] | None = None

    @classmethod
    def from_sections(cls, sections: list[str]) -> Self:
        """Create PreservedContent from a list of sections.

        Args:
            sections: List of text sections to preserve.

        Returns:
            PreservedContent instance.

        """
        content = "\n\n".join(sections)
        tokens = TokenCounter.count_text(content)
        return cls(content=content, tokens=tokens, sections=sections)

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

class MessageSafetyEnforcer:
    """Enforces safety limits on messages to prevent context overflow."""

    def __init__(self: MessageSafetyEnforcer, safety_limit_ratio: float, max_tokens: int) -> None:
        """Initialize message safety enforcer.

        Args:
            safety_limit_ratio: Ratio of max_tokens to use as safety limit.
            max_tokens: Maximum tokens allowed in context.

        """
        self.safety_limit_ratio = safety_limit_ratio
        self.max_tokens = max_tokens
        self.limit = int(max_tokens * safety_limit_ratio)

    def enforce_safety_limits(
        self: MessageSafetyEnforcer,
        messages: list[Message],
    ) -> list[Message]:
        """Enforce limits on individual message size using tokens.

        This prevents context overflow from individual massive messages
        by truncating them to fit within the context window.

        Args:
            messages: List of messages to check.

        Returns:
            List of messages with content limits enforced.

        """
        safe_messages = []
        for msg in messages:
            safe_message = self._enforce_message_safety_limit(msg)
            safe_messages.append(safe_message)
        return safe_messages

    def _enforce_message_safety_limit(self: MessageSafetyEnforcer, message: Message) -> Message:
        """Enforce safety limit on a single message.

        Args:
            message: The message to check.

        Returns:
            Message with content truncated if necessary.

        Raises:
            TypeError: If message is None.

        """
        if message is None:
            msg = "Message cannot be None"
            raise TypeError(msg)

        # If message has no content, return it unchanged
        if message.content is None:
            return message

        if not message.content:
            return message

        if len(message.content) < self.limit:
            return message

        if TokenCounter.count_text(message.content) > self.limit:
            return self._create_truncated_message(message)
        return message

    def _create_truncated_message(self: MessageSafetyEnforcer, message: Message) -> Message:
        """Create a truncated version of a message.

        Args:
            message: The original message to truncate.

        Returns:
            New Message with truncated content.

        """
        # Handle None content case
        message_content = message.content
        if not message_content:
            return message

        truncated_content = TokenCounter.truncate_text(message_content, self.limit)
        new_content = (
            truncated_content + f"\n... (truncated by safety limit: > {self.limit} tokens)"
        )

        return Message(
            role=message.role,
            content=new_content,
            tool_calls=message.tool_calls,
            tool_call_id=message.tool_call_id,
        )

class TokenCounterWrapper:
    """Wrapper for token counting operations with message-specific logic."""

    @staticmethod
    def count_messages_tokens(messages: list[Message]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: List of messages to count tokens for.

        Returns:
            Total token count.

        """
        total_tokens = 0
        for msg in messages:
            if msg.content:
                total_tokens += TokenCounter.count_text(msg.content)
            # Add tokens for tool calls if present
            if msg.tool_calls:
                # Estimate tokens for tool calls (JSON representation)
                for tool_call in msg.tool_calls:
                    tool_call_str = f"{tool_call.name}{tool_call.arguments}"
                    total_tokens += TokenCounter.count_text(tool_call_str)
        return total_tokens

class IntelligentTruncator:
    """Helper class for intelligent truncation with semantic preservation.

    This class addresses the feature envy code smell by encapsulating
    token counting and truncation logic, reducing direct dependencies
    on TokenCounter throughout the IntelligentContextManager.
    """

    def __init__(self: IntelligentTruncator, safety_limit: int) -> None:
        """Initialize the truncator with a safety limit.

        Args:
            safety_limit: Maximum tokens allowed after truncation.

        """
        self.safety_limit = safety_limit

    def truncate_with_semantic_preservation(self: IntelligentTruncator, content: str) -> str:
        """Apply intelligent truncation with semantic preservation.

        Preserves:
        1. Code blocks (``` ... ```)
        2. Error markers and stack traces
        3. Tool call structures
        4. Important keywords (error, exception, fix, todo, etc.)
        5. Conversation markers (user questions, assistant responses)

        Args:
            content: The content to truncate intelligently.

        Returns:
            Intelligently truncated content.

        """
        if not content:
            return content

        # Check if content already fits within safety limit
        content_tokens = TokenCounter.count_text(content)
        if content_tokens <= self.safety_limit:
            return content

        # Step 1: Extract and preserve critical sections
        preserved_sections = ContentExtractor.extract_critical_sections(content)

        # Step 2: Apply appropriate truncation strategy
        if preserved_sections:
            final_content = self._truncate_with_preserved_sections(content, preserved_sections)
        else:
            marker = "\n\n[Content truncated by safety limit...]"
            params = TruncationParams(content=content, marker=marker)
            final_content = self._truncate_with_marker(params)

        # Step 3: Ensure we don't exceed the limit
        return self._ensure_safety_limit(final_content)

    def _truncate_with_preserved_sections(
        self: IntelligentTruncator,
        content: str,
        preserved_sections: list[str],
    ) -> str:
        """Truncate content when there are preserved sections.

        Args:
            content: The original content.
            preserved_sections: List of critical sections to preserve.

        Returns:
            Truncated content with preserved sections.

        """
        preserved = PreservedContent.from_sections(preserved_sections)

        if preserved.tokens <= self.safety_limit:
            return self._truncate_with_available_capacity(content, preserved)
        marker = "\n\n[Critical content partially truncated...]"
        params = TruncationParams(content=preserved.content, marker=marker)
        return self._truncate_with_marker(params)

    def _truncate_with_available_capacity(
        self: IntelligentTruncator,
        content: str,
        preserved: PreservedContent,
    ) -> str:
        """Truncate when preserved sections fit within safety limit.

        Args:
            content: The original content.
            preserved: Preserved content with token count.

        Returns:
            Truncated content.

        """
        remaining_limit = self.safety_limit - preserved.tokens

        if (
            remaining_limit > IntelligentContextConstants.MIN_CONTEXT_TOKENS_THRESHOLD
        ):  # Enough for some context
            return self._add_context_with_truncation(content, preserved, remaining_limit)
        return self._add_minimal_truncation_marker(preserved.content, preserved.tokens)

    def _add_context_with_truncation(
        self: IntelligentTruncator,
        content: str,
        preserved: PreservedContent,
        remaining_limit: int,
    ) -> str:
        """Add context around preserved sections with truncation marker.

        Args:
            content: The original content.
            preserved: Preserved content with token count.
            remaining_limit: Remaining token capacity.

        Returns:
            Contextual content with truncation marker.

        """
        contextual_content = self._extract_context_around_sections(
            content,
            preserved.sections or [],
            remaining_limit,
        )
        marker = "\n\n[Additional context truncated...]"
        marker_tokens = TokenCounter.count_text(marker)

        # Handle case where marker doesn't fit in remaining limit
        if marker_tokens >= remaining_limit:
            # Marker alone exceeds or equals remaining limit
            # Return just the marker (truncated to fit if necessary)
            if marker_tokens > remaining_limit:
                # Marker doesn't fit, truncate it
                return TokenCounter.truncate_text(marker, remaining_limit)
            # Marker fits exactly
            return marker

        # Calculate how much content we can preserve
        # We have remaining_limit total tokens, need marker_tokens for marker
        # So we have remaining_limit - marker_tokens tokens available for content
        available_for_content = remaining_limit - marker_tokens

        # Use min_content_tokens, but don't exceed available_for_content
        min_content_tokens = IntelligentContextConstants.MIN_TOKEN_LIMIT_FOR_TRUNCATION
        context_limit = min(min_content_tokens, available_for_content)

        if (
            len(contextual_content)
            > context_limit * IntelligentContextConstants.CHAR_TO_TOKEN_ESTIMATE_MULTIPLIER
        ):  # Rough char estimate
            contextual_content = TokenCounter.truncate_text(contextual_content, context_limit)

        return contextual_content + marker

    def _add_minimal_truncation_marker(
        self: IntelligentTruncator,
        preserved_content: str,
        preserved_tokens: int,
    ) -> str:
        """Add minimal truncation marker when little capacity remains.

        Args:
            preserved_content: Concatenated preserved sections.
            preserved_tokens: Token count of preserved content.

        Returns:
            Preserved content with truncation marker.

        """
        marker = "\n\n[Non-critical content truncated...]"
        marker_tokens = TokenCounter.count_text(marker)

        # Handle case where marker doesn't fit in safety limit
        if marker_tokens >= self.safety_limit:
            # Marker alone exceeds or equals safety limit
            # Return just the marker (truncated to fit if necessary)
            params = TruncationParams(content="", marker=marker)
            return self._truncate_with_marker(params)

        # Calculate how much content we can preserve
        # We have safety_limit total tokens, need marker_tokens for marker
        # So we have safety_limit - marker_tokens tokens available for content
        available_for_content = self.safety_limit - marker_tokens

        # Preserve as much of the preserved content as fits
        preserved_limit = available_for_content

        # Truncate preserved content if it exceeds the limit
        if preserved_tokens > preserved_limit:
            preserved_content = TokenCounter.truncate_text(preserved_content, preserved_limit)

        return preserved_content + marker

    def _truncate_with_marker(
        self: IntelligentTruncator,
        params: TruncationParams,
    ) -> str:
        """Consolidated truncation logic with marker.

        Args:
            params: Parameters for truncation.

        Returns:
            Truncated content with marker, guaranteed not to exceed safety_limit.

        """
        marker_tokens = TokenCounter.count_text(params.marker)

        # Calculate how many tokens we have available for content
        # after reserving space for the marker
        available_for_content = self.safety_limit - marker_tokens

        if available_for_content <= 0:
            # Marker alone exceeds or equals safety limit
            # Return just the marker (truncated to fit if necessary)
            if marker_tokens > self.safety_limit:
                # Marker doesn't fit, truncate it
                return TokenCounter.truncate_text(params.marker, self.safety_limit)
            # Marker fits exactly
            return params.marker

        # We have some space for content
        # Use min_content_tokens, but don't exceed available_for_content
        limit = min(params.min_content_tokens, available_for_content)

        final_content = TokenCounter.truncate_text(params.content, limit)
        return final_content + params.marker

    def _ensure_safety_limit(self: IntelligentTruncator, content: str) -> str:
        """Ensure content doesn't exceed safety limit.

        Args:
            content: The content to check.

        Returns:
            Content truncated to safety limit if necessary.

        """
        final_content_tokens = TokenCounter.count_text(content)
        if final_content_tokens > self.safety_limit:
            # This shouldn't happen, but as a safety fallback, truncate
            return TokenCounter.truncate_text(content, self.safety_limit)
        return content

    @staticmethod
    def _extract_context_around_sections(
        content: str,
        sections: list[str],
        token_limit: int,
    ) -> str:
        """Extract context around critical sections.

        Args:
            content: The original content.
            sections: List of critical sections.
            token_limit: Maximum tokens for context.

        Returns:
            Contextual content around critical sections.

        """
        # Simplified implementation - just return some context
        # In real implementation, this would extract text around each section
        if not sections:
            return ""

        # Find positions of first and last sections
        first_section = sections[0]
        last_section = sections[-1]

        start_pos = content.find(first_section)
        end_pos = content.find(last_section) + len(last_section)

        if start_pos == -1 or end_pos == -1:
            return ""

        # Extract context (simplified - just take surrounding text)
        context_start = max(
            0,
            start_pos - IntelligentContextConstants.CONTEXT_WINDOW_CHARS_SURROUNDING,
        )
        context_end = min(
            len(content),
            end_pos + IntelligentContextConstants.CONTEXT_WINDOW_CHARS_SURROUNDING,
        )
        contextual_content = content[context_start:context_end]

        # Truncate to token limit
        return TokenCounter.truncate_text(contextual_content, token_limit)

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
        if self.current_assistant_index is None or not self.pending_tool_calls:
            return False

        prev_msg = self.messages[self.current_assistant_index]
        return SequenceValidator._is_duplicate_assistant_message(
            msg,
            prev_msg,
            self.current_assistant_index,
        )

class SequenceValidator:
    """Validates message sequences follow API rules and semantic constraints."""

    @classmethod
    def validate_compacted_sequence(cls: type[SequenceValidator], messages: list[Message]) -> bool:
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
        if not cls._validate_role_names(messages):
            return False

        # 1. Structural validation
        if not cls._validate_tool_sequences(messages):
            return False

        # 2. Semantic validation - check for logical conversation flow
        if not cls._validate_conversation_flow(messages):
            return False

        # 3. Context preservation check
        if not cls._validate_system_prompt(messages):
            return False

        # 4. Check for duplicate consecutive messages (compression artifact)
        return cls._validate_no_duplicate_consecutive_messages(messages)

    @staticmethod
    def _validate_tool_sequences(messages: list[Message]) -> bool:
        """Validate tool call sequences follow OpenAI API rules.

        Rules:
        - Tool messages must not be first
        - Tool messages must follow assistant messages with tool_calls
        - Tool message tool_call_id must match a tool call ID from preceding assistant
        - All tool calls from an assistant must have corresponding tool responses
          before another assistant message appears (unless it's a duplicate message)

        Args:
            messages: The messages to validate.

        Returns:
            True if tool sequences are valid, False otherwise.

        """
        validator = _ToolSequenceValidator(messages)
        return validator.validate()

    @staticmethod
    def _is_duplicate_assistant_message(
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

    @staticmethod
    def _validate_conversation_flow(messages: list[Message]) -> bool:
        """Validate logical conversation flow.

        Rules:
        - Assistant messages should generally follow user or tool messages
        - Exceptions:
          * Assistant continuing after tool calls (previous assistant had tool_calls)
          * First message after system prompt (i == 1 and messages[0].role == "system")

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
                # (check if previous assistant had tool calls that are now complete)
                if prev.role == "assistant" and prev.tool_calls:
                    # This is fine - assistant continuing after tool calls
                    continue
                # Also fine if it's the first message (system prompt scenario)
                if i == 1 and messages[0].role == "system":
                    continue
                return False
        return True

    @staticmethod
    def _validate_system_prompt(messages: list[Message]) -> bool:
        """Validate system prompt is preserved and not corrupted.

        Rules:
        - If first message is system role, it must have non-empty content

        Args:
            messages: The messages to validate.

        Returns:
            True if system prompt is valid, False otherwise.

        """
        return not (
            messages
            and messages[0].role == "system"
            and (not messages[0].content or len(messages[0].content.strip()) == 0)
        )

    @staticmethod
    def _validate_role_names(messages: list[Message]) -> bool:
        """Validate that message roles are valid OpenAI API roles (lowercase).

        Valid roles are: "system", "user", "assistant", "tool"

        Args:
            messages: The messages to validate.

        Returns:
            True if all roles are valid, False otherwise.

        """
        valid_roles = {"system", "user", "assistant", "tool"}
        return all(msg.role in valid_roles for msg in messages)

    @staticmethod
    def _validate_no_duplicate_consecutive_messages(messages: list[Message]) -> bool:
        """Check for duplicate consecutive messages (compression artifact).

        Rules:
        - Consecutive messages with same role and identical content are invalid
        - Exception: Messages with tool_calls are allowed (tool call sequences)

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

        Critical context includes:
        - System prompts and initial instructions
        - Recent user queries and assistant responses
        - Tool call sequences (assistant with tool_calls -> tool responses)
        - Error messages and debug information
        - Decisions and conclusions
        - Code blocks and structured data

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.

        Returns:
            Messages with critical context preserved.

        """
        if not messages:
            return []

        preserved_messages: list[Message] = []

        # Track which messages we've preserved
        preserved_indices: set[int] = set()

        # Phase 1: Always preserve system messages (highest priority)
        self._preserve_system_messages(messages, preserved_messages, preserved_indices)

        # Phase 2: Preserve recent high-importance messages
        self._preserve_recent_high_importance_messages(
            messages,
            importance_scores,
            preserved_messages,
            preserved_indices,
        )

        # Phase 3: Preserve tool call sequences
        self._preserve_tool_call_sequences(messages, preserved_messages, preserved_indices)

        # Phase 4: Preserve messages with critical content
        self._preserve_critical_content_messages(messages, preserved_messages, preserved_indices)

        # Phase 5: Ensure we preserve at least some conversation flow
        self._preserve_conversation_flow(messages, preserved_messages, preserved_indices)

        # Sort preserved messages back to original order
        preserved_messages.sort(key=lambda msg: messages.index(msg) if msg in messages else -1)

        return preserved_messages

    def _preserve_system_messages(
        self: MessagePreserver,
        messages: list[Message],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve all system messages.

        Args:
            messages: Original messages.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        for i, msg in enumerate(messages):
            if msg.role == "system":
                preserved_messages.append(msg)
                preserved_indices.add(i)

    def _preserve_recent_high_importance_messages(
        self: MessagePreserver,
        messages: list[Message],
        importance_scores: dict[int, float],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve recent messages with high importance scores.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        # Start from the end (most recent) and work backwards
        for i in range(len(messages) - 1, -1, -1):
            if i in preserved_indices:
                continue

            importance = importance_scores.get(i, 0.0)
            if importance >= self.config.importance_threshold:
                preserved_messages.append(messages[i])
                preserved_indices.add(i)

                # Limit to reasonable number of recent high-importance messages
                recent_count = sum(
                    1
                    for idx in preserved_indices
                    if idx >= len(messages) - IntelligentContextConstants.RECENT_MESSAGES_WINDOW
                )
                if recent_count >= IntelligentContextConstants.MIN_RECENT_MESSAGES_TO_PRESERVE:
                    break

    def _preserve_tool_call_sequences(
        self: MessagePreserver,
        messages: list[Message],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve complete tool call sequences.

        Args:
            messages: Original messages.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

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
                # Verify tool_call_id matches
                tool_call_ids = {tc.id for tc in curr_msg.tool_calls}
                if next_msg.tool_call_id in tool_call_ids:
                    preserved_messages.append(curr_msg)
                    preserved_messages.append(next_msg)
                    preserved_indices.add(i)
                    preserved_indices.add(i + 1)

    def _preserve_critical_content_messages(
        self: MessagePreserver,
        messages: list[Message],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve messages with critical content (errors, decisions, code blocks).

        Args:
            messages: Original messages.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        critical_keywords = IntelligentContextConstants.CRITICAL_KEYWORDS

        for i, msg in enumerate(messages):
            if i in preserved_indices:
                continue

            if not msg.content:
                continue

            # Check for critical keywords
            content_lower = msg.content.lower()
            if (
                any(keyword in content_lower for keyword in critical_keywords)
                or "```" in msg.content
            ):
                preserved_messages.append(msg)
                preserved_indices.add(i)

    def _preserve_conversation_flow(
        self: MessagePreserver,
        messages: list[Message],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Ensure we preserve at least some conversation flow.

        Try to preserve alternating user-assistant pairs.

        Args:
            messages: Original messages.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        for i, msg in enumerate(messages):
            if i in preserved_indices:
                continue

            if msg.role in ["user", "assistant"]:
                # Try to preserve pairs
                preserved_messages.append(msg)
                preserved_indices.add(i)

                # Limit to reasonable number
                if len(preserved_indices) >= min(
                    IntelligentContextConstants.MAX_PRESERVED_INDICES,
                    len(messages),
                ):
                    break

@dataclass
class CompressionConfig:
    """Configuration for compression strategies.

    Attributes:
        high_threshold: Threshold for high-importance clusters.
        medium_threshold: Threshold for medium-importance clusters.
        preserve_tool_sequences: Whether to preserve tool call sequences.
        preserve_code_blocks: Whether to preserve code blocks.

    """

    high_threshold: float
    medium_threshold: float
    preserve_tool_sequences: bool
    preserve_code_blocks: bool

@dataclass
class IntelligentCompactionResult:
    """Result of an intelligent compaction operation.

    Attributes:
        messages: The compacted messages.
        was_compacted: Whether compaction actually occurred.
        dropped_count: Number of messages/sequences dropped.
        summary: Optional summary of dropped content.
        importance_scores: Mapping of message indices to importance scores.
        clusters: Detected conversation clusters.
        compression_ratio: Achieved compression ratio.

    """

    messages: list[Message]
    was_compacted: bool = False
    dropped_count: int = 0
    summary: str | None = None
    importance_scores: dict[int, float] | None = None
    clusters: list[list[int]] | None = None
    compression_ratio: float | None = None

@dataclass
class ResultCreationParams:
    """Parameters for creating compaction results.

    Groups common parameters used by _create_result_without_truncation
    and _create_result_with_truncation to address primitive obsession.

    Attributes:
        original_messages: Original messages before compaction.
        safe_messages: Messages after compression but before truncation.
        importance_scores: Importance scores for each message.
        clusters: Detected conversation clusters.
        original_tokens: Original token count.
        was_compacted: Whether compaction occurred.

    """

    original_messages: list[Message]
    safe_messages: list[Message]
    importance_scores: dict[int, float]
    clusters: list[list[int]]
    original_tokens: int
    was_compacted: bool

    def get_dropped_count(self: ResultCreationParams) -> int:
        """Get the number of messages dropped during compaction.

        Returns:
            Number of messages dropped (original count minus safe count).

        """
        return len(self.original_messages) - len(self.safe_messages)

    def get_compression_ratio(self: ResultCreationParams, current_tokens: int) -> float:
        """Get compression ratio based on current token count.

        Args:
            current_tokens: Current token count after compression/truncation.

        Returns:
            Compression ratio (0.0 to 1.0).

        """
        if self.original_tokens > 0:
            return (self.original_tokens - current_tokens) / self.original_tokens
        return 0.0

    def create_result_without_truncation(
        self: ResultCreationParams,
        context_manager: IntelligentContextManager,
        current_tokens: int,
    ) -> IntelligentCompactionResult:
        """Create compaction result when no truncation is needed.

        Args:
            context_manager: The intelligent context manager for generating summaries.
            current_tokens: Current token count after compression.

        Returns:
            IntelligentCompactionResult without truncation.

        """
        compression_ratio = self.get_compression_ratio(current_tokens)

        return IntelligentCompactionResult(
            messages=self.safe_messages,
            was_compacted=self.was_compacted,
            dropped_count=self.get_dropped_count(),
            summary=context_manager.summary_generator.generate_intelligent_summary(
                self.original_messages,
                self.importance_scores,
                self.clusters,
            ),
            importance_scores=self.importance_scores,
            clusters=self.clusters,
            compression_ratio=compression_ratio,
        )

    def create_result_with_truncation(
        self: ResultCreationParams,
        context_manager: IntelligentContextManager,
        protect_from_index: int,
    ) -> IntelligentCompactionResult:
        """Create compaction result when truncation is needed.

        Args:
            context_manager: The intelligent context manager for truncation.
            protect_from_index: Protected message index.

        Returns:
            IntelligentCompactionResult with truncation.

        """
        truncated_messages = context_manager._apply_intelligent_truncation(
            self.safe_messages,
            self.importance_scores,
            self.clusters,
            protect_from_index,
        )
        truncated_tokens = context_manager._count_tokens(truncated_messages)
        final_compression_ratio = self.get_compression_ratio(truncated_tokens)

        return IntelligentCompactionResult(
            messages=truncated_messages,
            was_compacted=True,
            dropped_count=len(self.original_messages) - len(truncated_messages),
            summary=context_manager.summary_generator.generate_intelligent_summary(
                self.original_messages,
                self.importance_scores,
                self.clusters,
            ),
            importance_scores=self.importance_scores,
            clusters=self.clusters,
            compression_ratio=final_compression_ratio,
        )

class IntelligentContextManager:
    """Intelligent context manager with advanced compaction techniques.

    Features:
    - Semantic clustering of related messages
    - Adaptive compression based on content type
    - Importance scoring for message preservation
    - Safety limits to prevent context overflow
    - Intelligent truncation with protected sections

    The manager uses multiple strategies to reduce token usage while
    preserving critical context, error messages, tool calls, and
    recent conversation history.
    """

    def __init__(
        self: IntelligentContextManager,
        params: IntelligentContextParams | None = None,
        config: IntelligentContextConfig | None = None,
    ) -> None:
        """Initialize intelligent context manager.

        Args:
            params: Parameters for intelligent context management.
            config: Pre-configured settings object. If provided, returns it unchanged.

        """
        # Ensure we have a params object
        params = params or IntelligentContextParams()

        self.config = IntelligentContextConfig.from_params(params=params, config=config)

        from henchman.utils.message_analyzer import MessageAnalyzer

        self.message_analyzer = MessageAnalyzer(self.config)
        self.message_safety_enforcer = MessageSafetyEnforcer(
            safety_limit_ratio=self.config.safety_limit_ratio,
            max_tokens=self.config.max_tokens,
        )
        self.summary_generator = SummaryGenerator(self.config)
        self.message_preserver = MessagePreserver(self.config)
        self.message_compactor = MessageCompactor(self.config)

    @classmethod
    def from_params(
        cls: type[IntelligentContextManager],
        params: IntelligentContextParams,
        config: IntelligentContextConfig | None = None,
    ) -> IntelligentContextManager:
        """Create IntelligentContextManager from params object.

        Alternative constructor to address primitive obsession code smell.

        Args:
            params: IntelligentContextParams object containing configuration parameters.
            config: Optional IntelligentContextConfig object. If provided,
                params are ignored.

        Returns:
            IntelligentContextManager instance.

        """
        # If config is provided, use it directly
        if config is not None:
            return cls(config=config)

        # Otherwise, create config from params and pass it
        config_from_params = IntelligentContextConfig.from_params(params=params)
        return cls(config=config_from_params)

    def enforce_safety_limits(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> list[Message]:
        """Enforce limits on individual message size using tokens with semantic preservation.

        This prevents context overflow from individual massive messages
        by truncating them intelligently to preserve:
        - Code blocks and structured content
        - Error messages and stack traces
        - Tool call sequences
        - Important keywords and decision points
        - Conversation flow markers

        Args:
            messages: List of messages to check.

        Returns:
            List of messages with content limits enforced intelligently.

        """
        if not messages:
            return []

        safe_messages = []
        for msg in messages:
            if self._needs_safety_limit(msg):
                safe_message = self._apply_intelligent_truncation_with_semantic_preservation(msg)
                safe_messages.append(safe_message)
            else:
                safe_messages.append(msg)

        return safe_messages

    def _needs_safety_limit(self: IntelligentContextManager, message: Message) -> bool:
        """Check if a message needs safety limit enforcement.

        Args:
            message: The message to check.

        Returns:
            True if message exceeds safety limit, False otherwise.

        """
        if not message.content:
            return False

        token_count = TokenCounter.count_text(message.content)
        safety_limit = int(self.config.max_tokens * self.config.safety_limit_ratio)

        return token_count > safety_limit

    def _apply_intelligent_truncation_with_semantic_preservation(
        self: IntelligentContextManager,
        message: Message,
    ) -> Message:
        """Apply intelligent truncation with semantic preservation.

        Preserves:
        1. Code blocks (``` ... ```)
        2. Error markers and stack traces
        3. Tool call structures
        4. Important keywords (error, exception, fix, todo, etc.)
        5. Conversation markers (user questions, assistant responses)

        Args:
            message: The message to truncate intelligently.

        Returns:
            Intelligently truncated message.

        """
        if not message.content:
            return message

        safety_limit = int(self.config.max_tokens * self.config.safety_limit_ratio)

        # Use IntelligentTruncator to address feature envy code smell
        truncator = IntelligentTruncator(safety_limit)
        final_content = truncator.truncate_with_semantic_preservation(message.content)

        return Message(
            role=message.role,
            content=final_content,
            tool_calls=message.tool_calls,
            tool_call_id=message.tool_call_id,
        )

    def _count_tokens(self: IntelligentContextManager, messages: list[Message]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: List of messages to count tokens for.

        Returns:
            Total token count.

        """
        return TokenCounterWrapper.count_messages_tokens(messages)

    def _apply_intelligent_truncation(
        self: IntelligentContextManager,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
        protect_from_index: int = -1,
    ) -> list[Message]:
        """Apply intelligent truncation when messages exceed token limit.

        Prioritizes preserving high-importance messages and complete clusters.

        Args:
            messages: Messages to truncate.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.
            protect_from_index: Index from which messages are protected.

        Returns:
            Truncated messages that fit within max_tokens.

        """
        return self.message_compactor.apply_intelligent_truncation(
            messages,
            importance_scores,
            clusters,
            protect_from_index,
        )

    def compact(
        self: IntelligentContextManager,
        messages: list[Message],
        protect_from_index: int = -1,
    ) -> list[Message]:
        """Compact messages to fit within max_tokens using intelligent techniques.

        Uses importance scoring, clustering, and adaptive compression to
        preserve critical context while reducing token usage.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.
                Set to -1 to disable protection (default behavior).

        Returns:
            Compacted messages that fit within max_tokens.

        """
        # Use compact_with_result and return just the messages
        result = self.compact_with_result(messages, protect_from_index)
        return result.messages

    def compact_with_result(
        self: IntelligentContextManager,
        messages: list[Message],
        protect_from_index: int = -1,
    ) -> IntelligentCompactionResult:
        """Compact messages and return detailed result with intelligence metrics.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.

        Returns:
            IntelligentCompactionResult with compacted messages and metadata.

        """
        if not messages:
            return self._create_empty_result()

        return self._compact_messages_with_intelligence(messages, protect_from_index)

    def _compact_messages_with_intelligence(
        self: IntelligentContextManager,
        messages: list[Message],
        protect_from_index: int,
    ) -> IntelligentCompactionResult:
        """Core logic for compacting messages with intelligence metrics.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.

        Returns:
            IntelligentCompactionResult with compacted messages and metadata.

        """
        # Calculate importance scores and cluster messages
        importance_scores, clusters = self._analyze_messages(messages)

        # Apply compression and safety limits
        safe_messages = self._apply_compression_and_safety(messages, importance_scores, clusters)

        # Check if truncation is needed
        original_tokens = self._count_tokens(messages)
        current_tokens = self._count_tokens(safe_messages)
        was_compacted = self._detect_compaction(
            messages,
            safe_messages,
            original_tokens,
            current_tokens,
        )

        # Handle based on token limit
        if current_tokens <= self.config.max_tokens:
            params = ResultCreationParams(
                original_messages=messages,
                safe_messages=safe_messages,
                importance_scores=importance_scores,
                clusters=clusters,
                original_tokens=original_tokens,
                was_compacted=was_compacted,
            )
            return params.create_result_without_truncation(self, current_tokens)

        # Need truncation
        params = ResultCreationParams(
            original_messages=messages,
            safe_messages=safe_messages,
            importance_scores=importance_scores,
            clusters=clusters,
            original_tokens=original_tokens,
            was_compacted=was_compacted,
        )
        return params.create_result_with_truncation(self, protect_from_index)

    def _create_empty_result(self: IntelligentContextManager) -> IntelligentCompactionResult:
        """Create an empty compaction result.

        Returns:
            Empty IntelligentCompactionResult.

        """
        return IntelligentCompactionResult(
            messages=[],
            was_compacted=False,
            dropped_count=0,
            summary=None,
            importance_scores={},
            clusters=[],
            compression_ratio=0.0,
        )

    def _analyze_messages(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> tuple[dict[int, float], list[list[int]]]:
        """Analyze messages for importance and clustering.

        Args:
            messages: Messages to analyze.

        Returns:
            Tuple of (importance_scores, clusters).

        """
        importance_scores = self._calculate_importance_scores(messages)
        clusters = self._cluster_messages(messages)
        return importance_scores, clusters

    def _apply_compression_and_safety(
        self: IntelligentContextManager,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
    ) -> list[Message]:
        """Apply compression and safety limits to messages.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.

        Returns:
            Compressed and safety-limited messages.

        """
        compressed_messages = self._apply_adaptive_compression(
            messages,
            importance_scores,
            clusters,
        )
        compressed_messages = self.message_preserver.preserve_critical_context(
            compressed_messages,
            importance_scores,
        )
        return self.enforce_safety_limits(compressed_messages)

    def _detect_compaction(
        self: IntelligentContextManager,
        original_messages: list[Message],
        compressed_messages: list[Message],
        original_tokens: int,
        current_tokens: int,
    ) -> bool:
        """Detect if compaction occurred.

        Args:
            original_messages: Original messages.
            compressed_messages: Compressed messages.
            original_tokens: Original token count.
            current_tokens: Current token count.

        Returns:
            True if compaction occurred, False otherwise.

        """
        return len(compressed_messages) < len(original_messages) or current_tokens < original_tokens

    def validate_compacted_sequence(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> bool:
        """Validate that a message sequence follows OpenAI API rules.

        Args:
            messages: The messages to validate.

        Returns:
            True if the sequence is valid, False otherwise.

        """
        return SequenceValidator.validate_compacted_sequence(messages)

    def _calculate_importance_scores(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> dict[int, float]:
        """Calculate importance scores for each message.

        Importance is based on:
        - Message role (system > user > assistant > tool)
        - Content length and complexity
        - Position in conversation
        - Presence of tool calls or important keywords
        - Semantic significance

        Args:
            messages: Messages to score.

        Returns:
            Dictionary mapping message indices to importance scores (0.0-1.0).

        """
        importance_scores, _, _ = self.message_analyzer.analyze_messages(messages)
        return importance_scores

    def _cluster_messages(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> list[list[int]]:
        """Cluster related messages based on semantic similarity.

        Groups messages that discuss the same topic or are part of the
        same conversational thread.

        Args:
            messages: Messages to cluster.

        Returns:
            List of clusters, where each cluster is a list of message indices.

        """
        _, clusters, _ = self.message_analyzer.analyze_messages(messages)
        return clusters

    def _apply_adaptive_compression(
        self: IntelligentContextManager,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
    ) -> list[Message]:
        """Apply adaptive compression based on importance and clustering.

        Compression techniques:
        - Summarization of low-importance clusters
        - Extraction of key points from verbose messages
        - Removal of redundant information
        - Preservation of critical decision points

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.

        Returns:
            Compressed messages.

        """
        if not messages or not clusters:
            return messages

        # Detect conversation type
        detector = ConversationTypeDetector()
        conversation_type = detector.detect(messages)

        # Calculate cluster importance scores using MessageCompactor
        cluster_importance = self.message_compactor._calculate_cluster_importance(
            clusters,
            importance_scores,
        )

        # Apply compression strategy based on conversation type
        strategy = CompressionStrategyFactory.create_for_conversation_type(conversation_type)
        return strategy.compress(messages, clusters, cluster_importance)
