"""Importance scoring for intelligent context management.

This module provides importance scoring functionality for messages in a conversation.
Importance is based on message features, role, content, and position.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.providers.base import Message


class ImportanceScorer:
    """Calculates importance scores for messages in a conversation.

    Importance is based on:
    - Message role (system > user > assistant > tool)
    - Content length and complexity
    - Position in conversation
    - Presence of tool calls or important keywords
    - Semantic significance
    """

    # Importance scoring constants
    _TOOL_CALL_IMPORTANCE: float = 0.9
    _ERROR_KEYWORD_IMPORTANCE: float = 0.8
    _SYSTEM_ROLE_IMPORTANCE: float = 0.7
    _USER_ROLE_IMPORTANCE: float = 0.6
    _ASSISTANT_LONG_CONTENT_IMPORTANCE: float = 0.5
    _ASSISTANT_SHORT_CONTENT_IMPORTANCE: float = 0.3
    _TOOL_WITH_CONTENT_IMPORTANCE: float = 0.7
    _TOOL_WITHOUT_CONTENT_IMPORTANCE: float = 0.4
    _POSITION_BOOST_MAX: float = 0.2
    _VERY_LONG_CONTENT_THRESHOLD: int = 500
    _VERY_LONG_CONTENT_BOOST: float = 0.1
    _LONG_CONTENT_THRESHOLD: int = 100
    _LONG_CONTENT_BOOST: float = 0.05
    _TOOL_CONTENT_THRESHOLD: int = 20
    _MINIMUM_IMPORTANCE: float = 0.1

    def calculate_importance_scores(self: ImportanceScorer, messages: list[Message]) -> dict[int, float]:  # noqa: E501
        """Calculate importance scores for each message.

        Args:
            messages: Messages to score.

        Returns:
            Dictionary mapping message indices to importance scores (0.0-1.0).
        """
        if not messages:
            return {}

        importance_scores: dict[int, float] = {}

        for i, message in enumerate(messages):
            score = self._calculate_message_importance(message, i, len(messages))
            importance_scores[i] = score

        return importance_scores

    def _calculate_message_importance(
        self: ImportanceScorer, message: Message, index: int, total_messages: int,
    ) -> float:
        """Calculate importance score for a single message.

        Args:
            message: The message to score.
            index: Position of the message in the conversation.
            total_messages: Total number of messages in the conversation.

        Returns:
            Importance score between 0.0 and 1.0.
        """
        # Start with base score from role and content features
        score = self._calculate_base_importance(message)

        # Apply position-based boost (recent messages are more important)
        score = self._apply_position_boost(score, index, total_messages)

        # Apply content length boost (longer messages might be more important)
        score = self._apply_content_length_boost(score, message)

        # Ensure score is within valid range
        score = self._clamp_score(score)

        # Apply minimum score if no other factors applied
        return self._apply_minimum_score(score)


    def _calculate_base_importance(self: ImportanceScorer, message: Message) -> float:
        """Calculate base importance score based on message features.

        Considers:
        - Tool calls (highest priority)
        - Error keywords in content
        - Message role

        Args:
            message: The message to score.

        Returns:
            Base importance score.
        """
        score = 0.0

        # 1. Check for tool calls (high importance)
        if self._has_tool_calls(message):
            score = max(score, self._TOOL_CALL_IMPORTANCE)

        # 2. Check for errors in content (high importance)
        if self._contains_error_keywords(message):
            score = max(score, self._ERROR_KEYWORD_IMPORTANCE)

        # 3. Check message role
        return max(score, self._get_role_based_importance(message))


    def _has_tool_calls(self: ImportanceScorer, message: Message) -> bool:
        """Check if message has tool calls.

        Args:
            message: The message to check.

        Returns:
            True if message has tool calls, False otherwise.
        """
        return bool(message.tool_calls and len(message.tool_calls) > 0)

    def _contains_error_keywords(self: ImportanceScorer, message: Message) -> bool:
        """Check if message content contains error keywords.

        Args:
            message: The message to check.

        Returns:
            True if message contains error keywords, False otherwise.
        """
        if not message.content:
            return False

        content_lower = message.content.lower()
        error_indicators = [
            "error",
            "exception",
            "failed",
            "failure",
            "invalid",
            "unexpected",
        ]

        return any(indicator in content_lower for indicator in error_indicators)

    def _get_role_based_importance(self: ImportanceScorer, message: Message) -> float:
        """Get importance score based on message role.

        Args:
            message: The message to score.

        Returns:
            Role-based importance score.
        """
        if message.role == "system":
            return self._SYSTEM_ROLE_IMPORTANCE
        if message.role == "user":
            return self._USER_ROLE_IMPORTANCE
        if message.role == "assistant":
            return self._get_assistant_importance(message)
        if message.role == "tool":
            return self._get_tool_importance(message)
        return 0.0

    def _get_assistant_importance(self: ImportanceScorer, message: Message) -> float:
        """Get importance score for assistant messages.

        Args:
            message: The assistant message to score.

        Returns:
            Importance score for assistant message.
        """
        # Tool calls already handled with higher priority
        if message.tool_calls:
            return 0.0  # Already accounted for in base importance

        if message.content and len(message.content) > self._LONG_CONTENT_THRESHOLD:
            return self._ASSISTANT_LONG_CONTENT_IMPORTANCE
        return self._ASSISTANT_SHORT_CONTENT_IMPORTANCE

    def _get_tool_importance(self: ImportanceScorer, message: Message) -> float:
        """Get importance score for tool messages.

        Args:
            message: The tool message to score.

        Returns:
            Importance score for tool message.
        """
        if message.content and len(message.content) > self._TOOL_CONTENT_THRESHOLD:
            return self._TOOL_WITH_CONTENT_IMPORTANCE
        return self._TOOL_WITHOUT_CONTENT_IMPORTANCE

    def _apply_position_boost(
        self: ImportanceScorer, score: float, index: int, total_messages: int,
    ) -> float:
        """Apply position-based boost to score.

        Recent messages get higher importance.

        Args:
            score: Current importance score.
            index: Position of the message (0-based).
            total_messages: Total number of messages.

        Returns:
            Score with position boost applied.
        """
        if total_messages <= 1:
            return score

        position_factor = index / (total_messages - 1)  # 0.0 to 1.0
        position_boost = position_factor * self._POSITION_BOOST_MAX
        return min(1.0, score + position_boost)

    def _apply_content_length_boost(self: ImportanceScorer, score: float, message: Message) -> float:  # noqa: E501
        """Apply content length boost to score.

        Longer messages might be more important.

        Args:
            score: Current importance score.
            message: The message to check.

        Returns:
            Score with content length boost applied.
        """
        if not message.content:
            return score

        content_length = len(message.content)

        if content_length > self._VERY_LONG_CONTENT_THRESHOLD:
            return min(1.0, score + self._VERY_LONG_CONTENT_BOOST)
        if content_length > self._LONG_CONTENT_THRESHOLD:
            return min(1.0, score + self._LONG_CONTENT_BOOST)
        return score

    def _clamp_score(self: ImportanceScorer, score: float) -> float:
        """Clamp score to valid range [0.0, 1.0].

        Args:
            score: The score to clamp.

        Returns:
            Clamped score between 0.0 and 1.0.
        """
        return max(0.0, min(1.0, score))

    def _apply_minimum_score(self: ImportanceScorer, score: float) -> float:
        """Apply minimum score if no other factors applied.

        Args:
            score: Current importance score.

        Returns:
            Score with minimum applied if needed.
        """
        if score == 0.0:
            return self._MINIMUM_IMPORTANCE
        return score
