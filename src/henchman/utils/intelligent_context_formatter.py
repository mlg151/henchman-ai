"""Formatter and truncator for intelligent context management.

This module provides tools for intelligent truncation and safety limit enforcement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.utils.intelligent_context_extractor import ContentExtractor
from henchman.utils.intelligent_context_types import (
    IntelligentContextConstants,
    MarkerParams,
    PreservedContent,
    TruncationParams,
)
from henchman.utils.tokens import TokenCounter

if TYPE_CHECKING:
    from henchman.providers.base import Message


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
        self.truncator = IntelligentTruncator(self.limit)

    def enforce_safety_limits(
        self: MessageSafetyEnforcer,
        messages: list[Message],
    ) -> list[Message]:
        """Enforce limits on individual message size using tokens with semantic preservation.

        This prevents context overflow from individual massive messages
        by truncating them intelligently to preserve important content.

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
                safe_message = self._apply_intelligent_truncation(msg)
                safe_messages.append(safe_message)
            else:
                safe_messages.append(msg)

        return safe_messages

    def _needs_safety_limit(self: MessageSafetyEnforcer, message: Message) -> bool:
        """Check if a message needs safety limit enforcement.

        Args:
            message: The message to check.

        Returns:
            True if message exceeds safety limit, False otherwise.

        """
        content = message.content
        if not content:
            return False

        token_count = TokenCounter.count_text(content)
        return token_count > self.limit

    def _apply_intelligent_truncation(
        self: MessageSafetyEnforcer,
        message: Message,
    ) -> Message:
        """Apply intelligent truncation with semantic preservation.

        Args:
            message: The message to truncate intelligently.

        Returns:
            Intelligently truncated message.

        """
        content = message.content
        if not content:
            return message

        final_content = self.truncator.truncate_with_semantic_preservation(content)

        # Create new message with truncated content
        msg_cls = message.__class__
        return msg_cls(
            role=message.role,
            content=final_content,
            tool_calls=message.tool_calls,
            tool_call_id=message.tool_call_id,
            reasoning_content=getattr(message, "reasoning_content", None),
        )

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
        content = message.content
        if not content:
            return message

        limit = self.limit
        if len(content) < limit:
            return message

        if TokenCounter.count_text(content) > limit:
            return _create_truncated_message(message, limit, self.safety_limit_ratio)
        return message

def _create_truncated_message(message: Message, limit: int, safety_ratio: float) -> Message:
    """Create a truncated version of a message.

    Args:
        message: The original message to truncate.
        limit: Token limit.
        safety_ratio: Safety limit ratio.

    Returns:
        New Message with truncated content.

    """
    content = message.content
    role = message.role
    calls = message.tool_calls
    call_id = message.tool_call_id
    msg_cls = message.__class__

    if not content:
        return message

    truncated = TokenCounter.truncate_text(content, limit)
    info = f"(truncated by safety limit: > {limit} tokens, ratio: {safety_ratio})"

    return msg_cls(
        role=role,
        content=f"{truncated}\n... {info}",
        tool_calls=calls,
        tool_call_id=call_id,
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
            content = msg.content
            if content:
                total_tokens += TokenCounter.count_text(content)
            # Add tokens for tool calls if present
            calls = msg.tool_calls
            if calls:
                # Estimate tokens for tool calls (JSON representation)
                for tc in calls:
                    tc_str = f"{tc.name}{tc.arguments}"
                    total_tokens += TokenCounter.count_text(tc_str)
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

        Args:
            content: The content to truncate intelligently.

        Returns:
            Intelligently truncated content.

        """
        if not content:
            return content

        limit = self.safety_limit

        # Check if content already fits within safety limit
        if TokenCounter.count_text(content) <= limit:
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
        limit = self.safety_limit
        preserved = PreservedContent.from_sections(preserved_sections)

        if preserved.tokens <= limit:
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
        limit = self.safety_limit
        remaining_limit = limit - preserved.tokens

        threshold = IntelligentContextConstants.MIN_CONTEXT_TOKENS_THRESHOLD
        if remaining_limit > threshold:  # Enough for some context
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
        sections = preserved.sections or []
        contextual_content = self._extract_context_around_sections(
            content,
            sections,
            remaining_limit,
        )
        marker = "\n\n[Additional context truncated...]"
        marker_tokens = TokenCounter.count_text(marker)

        # Handle case where marker doesn't fit in remaining limit
        if marker_tokens >= remaining_limit:
            return MarkerParams(marker, marker_tokens).handle_overflow(remaining_limit)

        # Calculate how much content we can preserve
        available_for_content = remaining_limit - marker_tokens

        # Use min_content_tokens, but don't exceed available_for_content
        min_limit = IntelligentContextConstants.MIN_TOKEN_LIMIT_FOR_TRUNCATION
        context_limit = min(min_limit, available_for_content)

        multiplier = IntelligentContextConstants.CHAR_TO_TOKEN_ESTIMATE_MULTIPLIER
        if len(contextual_content) > context_limit * multiplier:
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
        limit = self.safety_limit
        marker = "\n\n[Non-critical content truncated...]"
        marker_tokens = TokenCounter.count_text(marker)

        # Handle case where marker doesn't fit in safety limit
        if marker_tokens >= limit:
            params = TruncationParams(content="", marker=marker)
            return self._truncate_with_marker(params)

        # Calculate how much content we can preserve
        available_for_content = limit - marker_tokens

        # Truncate preserved content if it exceeds the limit
        if preserved_tokens > available_for_content:
            preserved_content = TokenCounter.truncate_text(preserved_content, available_for_content)

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
        return params.apply(self.safety_limit)

    def _ensure_safety_limit(self: IntelligentTruncator, content: str) -> str:
        """Ensure content doesn't exceed safety limit.

        Args:
            content: The content to check.

        Returns:
            Content truncated to safety limit if necessary.

        """
        limit = self.safety_limit
        if TokenCounter.count_text(content) > limit:
            # This shouldn't happen, but as a safety fallback, truncate
            return TokenCounter.truncate_text(content, limit)
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
        surrounding = IntelligentContextConstants.CONTEXT_WINDOW_CHARS_SURROUNDING
        context_start = max(0, start_pos - surrounding)
        context_end = min(len(content), end_pos + surrounding)
        contextual_content = content[context_start:context_end]

        # Truncate to token limit
        return TokenCounter.truncate_text(contextual_content, token_limit)
