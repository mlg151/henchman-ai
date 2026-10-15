"""Compression strategies for intelligent context management.

This module provides adaptive compression strategies based on conversation type
and importance scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

from henchman.providers.base import Message
from henchman.utils.tokens import TokenCounter

# Only summarize if it reduces tokens by at least this ratio (20% reduction required)
MIN_TOKEN_REDUCTION_RATIO = 0.8


# Constants duplicated from intelligent_context.py to avoid circular imports
class CompressionStrategyConstants:
    """Constants for compression strategies."""

    # Compression strategy thresholds
    DEBUGGING_HIGH_THRESHOLD: float = 0.8
    DEBUGGING_MEDIUM_THRESHOLD: float = 0.5
    CODING_HIGH_THRESHOLD: float = 0.7
    CODING_MEDIUM_THRESHOLD: float = 0.4

    # Default compression thresholds
    DEFAULT_COMPRESSION_HIGH_THRESHOLD: float = 0.6
    DEFAULT_COMPRESSION_MEDIUM_THRESHOLD: float = 0.3
    CLUSTER_PREVIEW_LENGTH: int = 50


@dataclass
class CompressionStrategyConfig:
    """Configuration for a compression strategy.

    Attributes:
        name: Name of the strategy.
        high_threshold: High importance threshold.
        medium_threshold: Medium importance threshold.
        preserve_tool_sequences: Whether to preserve tool call sequences.
        preserve_code_blocks: Whether to preserve code blocks.
    """

    name: str
    high_threshold: float
    medium_threshold: float
    preserve_tool_sequences: bool
    preserve_code_blocks: bool


def _build_cluster_summary(cluster_messages: list[Message]) -> str:
    """Generate summary text from a list of messages.

    Args:
        cluster_messages: Messages in the cluster.

    Returns:
        Summary text joining each message's role with a content preview.
    """
    if not cluster_messages:
        return ""

    preview_length = CompressionStrategyConstants.CLUSTER_PREVIEW_LENGTH
    key_phrases = []
    for msg in cluster_messages:
        if msg.content:
            preview = msg.content[:preview_length]
            if len(msg.content) > preview_length:
                preview += "..."
            key_phrases.append(f"{msg.role}: {preview}")

    return "; ".join(key_phrases)


def _collect_code_block_messages(
    messages: list[Message],
    cluster: list[int],
) -> list[Message]:
    """Collect messages containing code blocks from a cluster.

    Args:
        messages: All messages.
        cluster: Cluster indices.

    Returns:
        Messages that contain code blocks or function/class definitions.
    """
    code_markers = ("```", "def ", "class ")
    return [
        messages[idx]
        for idx in cluster
        if idx < len(messages)
        and messages[idx].content
        and any(marker in (messages[idx].content or "") for marker in code_markers)
    ]


# Strategy configurations keyed by conversation type, built at import time
_csc = CompressionStrategyConstants
_STRATEGY_CONFIGS: dict[str, CompressionStrategyConfig] = {
    "coding": CompressionStrategyConfig(
        name="coding",
        high_threshold=_csc.CODING_HIGH_THRESHOLD,
        medium_threshold=_csc.CODING_MEDIUM_THRESHOLD,
        preserve_tool_sequences=True,
        preserve_code_blocks=True,
    ),
    "debugging": CompressionStrategyConfig(
        name="debugging",
        high_threshold=_csc.DEBUGGING_HIGH_THRESHOLD,
        medium_threshold=_csc.DEBUGGING_MEDIUM_THRESHOLD,
        preserve_tool_sequences=True,
        preserve_code_blocks=True,
    ),
    "research": CompressionStrategyConfig(
        name="research",
        high_threshold=_csc.DEFAULT_COMPRESSION_HIGH_THRESHOLD,
        medium_threshold=_csc.DEFAULT_COMPRESSION_MEDIUM_THRESHOLD,
        preserve_tool_sequences=True,
        preserve_code_blocks=False,
    ),
    "general": CompressionStrategyConfig(
        name="general",
        high_threshold=_csc.DEFAULT_COMPRESSION_HIGH_THRESHOLD,
        medium_threshold=_csc.DEFAULT_COMPRESSION_MEDIUM_THRESHOLD,
        preserve_tool_sequences=True,
        preserve_code_blocks=False,
    ),
}


class CompressionStrategy:
    """Base class for compression strategies.

    Provides common functionality for compressing message clusters based on
    importance scores.
    """

    def __init__(self: CompressionStrategy, config: CompressionStrategyConfig) -> None:
        """Initialize compression strategy.

        Args:
            config: Configuration for the strategy.
        """
        self.config = config

    def compress(
        self: CompressionStrategy,
        messages: list[Message],
        clusters: list[list[int]],
        cluster_importance: dict[int, float],
    ) -> list[Message]:
        """Apply compression based on cluster importance thresholds.

        Strategy:
        - High-importance clusters (>= high_threshold): Preserve fully
        - Medium-importance clusters (>= medium_threshold): Summarize
        - Low-importance clusters (< medium_threshold): Drop or heavily compress

        Args:
            messages: Original messages.
            clusters: Message clusters.
            cluster_importance: Importance scores for each cluster.

        Returns:
            Compressed messages.
        """
        if not messages or not clusters:
            return messages

        compressed_messages: list[Message] = []

        for cluster_idx, cluster in enumerate(clusters):
            importance = cluster_importance.get(cluster_idx, 0.0)
            if importance >= self.config.high_threshold:
                compressed_messages.extend(
                    self._compress_high_importance(messages, cluster),
                )
            elif importance >= self.config.medium_threshold:
                compressed_messages.extend(
                    self._compress_medium_importance(messages, cluster, cluster_idx),
                )
            else:
                compressed_messages.extend(
                    self._compress_low_importance(messages, cluster),
                )

        return compressed_messages

    def _compress_high_importance(
        self: CompressionStrategy,
        messages: list[Message],
        cluster: list[int],
    ) -> list[Message]:
        """Preserve all messages in a high-importance cluster."""
        return [messages[idx] for idx in cluster if idx < len(messages)]

    def _compress_medium_importance(
        self: CompressionStrategy,
        messages: list[Message],
        cluster: list[int],
        cluster_idx: int,
    ) -> list[Message]:
        """Summarize or preserve a medium-importance cluster."""
        result: list[Message] = []
        summary = self._summarize_cluster(messages, cluster)
        if summary:
            result.append(Message(
                role="system",
                content=f"[Summarized cluster {cluster_idx}]: {summary}",
            ))
        else:
            # If summarization doesn't reduce tokens, preserve original messages
            result.extend(messages[idx] for idx in cluster if idx < len(messages))

        # Also preserve tool sequences if requested
        if self.config.preserve_tool_sequences:
            self._preserve_tool_sequences_in_cluster(messages, cluster, result)

        return result

    def _compress_low_importance(
        self: CompressionStrategy,
        messages: list[Message],
        cluster: list[int],
    ) -> list[Message]:
        """Drop or minimally preserve a low-importance cluster."""
        result: list[Message] = []

        if self.config.preserve_tool_sequences:
            self._preserve_tool_sequences_in_cluster(messages, cluster, result)

        if self.config.preserve_code_blocks:
            result.extend(_collect_code_block_messages(messages, cluster))

        return result

    def _summarize_cluster(
        self: CompressionStrategy,
        messages: list[Message],
        cluster: list[int],
    ) -> str | None:
        """Generate a summary of a message cluster.

        Args:
            messages: All messages.
            cluster: Indices of messages in the cluster.

        Returns:
            Summary string, or None if cluster cannot be summarized.
        """
        if not cluster:
            return None

        # Extract key information from the cluster
        cluster_messages = [messages[idx] for idx in cluster if idx < len(messages)]

        # Don't summarize if it would increase token count significantly
        # For very short clusters, preserving original messages is better
        original_tokens = self._calculate_cluster_tokens(cluster_messages)

        summary = _build_cluster_summary(cluster_messages)
        summary_tokens = TokenCounter.count_text(summary) if summary else 0

        # Add overhead for summary message structure
        summary_overhead = TokenCounter.count_text("[Summarized cluster X]: ")
        total_summary_tokens = summary_tokens + summary_overhead

        # Only summarize if it reduces tokens by at least 20%
        if total_summary_tokens < original_tokens * MIN_TOKEN_REDUCTION_RATIO:
            return summary

        # Return None to indicate no summarization should occur
        return None

    def _generate_cluster_summary(self: CompressionStrategy, cluster_messages: list[Message]) -> str:
        """Backward-compatible wrapper for cluster-summary generation."""
        return _build_cluster_summary(cluster_messages)

    def _calculate_cluster_tokens(
        self: CompressionStrategy,
        cluster_messages: list[Message],
    ) -> int:
        """Calculate total tokens in a cluster of messages.

        Args:
            cluster_messages: Messages in the cluster.

        Returns:
            Total token count.
        """
        return sum(
            TokenCounter.count_text(msg.content or "")
            for msg in cluster_messages
        )

    def _preserve_tool_sequences_in_cluster(
        self: CompressionStrategy,
        messages: list[Message],
        cluster: list[int],
        compressed_messages: list[Message],
    ) -> None:
        """Preserve tool call sequences within a cluster.

        Args:
            messages: All messages.
            cluster: Cluster indices.
            compressed_messages: List to add preserved messages to.
        """
        for idx in cluster:
            if idx >= len(messages):
                continue
            msg = messages[idx]
            if msg.role != "assistant" or not msg.tool_calls:
                continue
            # Preserve assistant message with tool calls
            compressed_messages.append(msg)
            # Also preserve the corresponding tool response if it exists
            if idx + 1 < len(messages) and messages[idx + 1].role == "tool":
                compressed_messages.append(messages[idx + 1])

    def _preserve_code_blocks_in_cluster(
        self: CompressionStrategy,
        messages: list[Message],
        cluster: list[int],
        compressed_messages: list[Message],
    ) -> None:
        """Backward-compatible wrapper for preserving code-block messages."""
        compressed_messages.extend(_collect_code_block_messages(messages, cluster))


class CompressionStrategyFactory:
    """Factory for creating compression strategies based on conversation type."""

    @staticmethod
    def create_for_conversation_type(conversation_type: str) -> CompressionStrategy:
        """Create compression strategy for a conversation type.

        Args:
            conversation_type: Type of conversation ("coding", "research",
                "debugging", or "general").

        Returns:
            Compression strategy instance.
        """
        config = _STRATEGY_CONFIGS.get(conversation_type, _STRATEGY_CONFIGS["general"])
        return CompressionStrategy(config)
