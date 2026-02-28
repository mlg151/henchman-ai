"""Compression strategies for intelligent context management.

This module provides adaptive compression strategies based on conversation type
and importance scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from henchman.providers.base import Message

if TYPE_CHECKING:
    pass


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


class CompressionStrategy:
    """Base class for compression strategies.
    
    Provides common functionality for compressing message clusters based on
    importance scores.
    """
    
    def __init__(self, config: CompressionStrategyConfig) -> None:
        """Initialize compression strategy.
        
        Args:
            config: Configuration for the strategy.
        """
        self.config = config

    def compress(
        self,
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
                # Preserve high-importance clusters fully
                for msg_idx in cluster:
                    if msg_idx < len(messages):
                        compressed_messages.append(messages[msg_idx])

            elif importance >= self.config.medium_threshold:
                # Summarize medium-importance clusters
                summary = self._summarize_cluster(messages, cluster)
                if summary:
                    # Create a summary message
                    summary_msg = Message(
                        role="system",
                        content=f"[Summarized cluster {cluster_idx}]: {summary}",
                    )
                    compressed_messages.append(summary_msg)

                # Also preserve tool sequences if requested
                if self.config.preserve_tool_sequences:
                    self._preserve_tool_sequences_in_cluster(
                        messages, cluster, compressed_messages
                    )

            else:
                # Low-importance clusters: drop or minimal preservation
                # Only preserve if they contain critical elements
                if self.config.preserve_tool_sequences:
                    self._preserve_tool_sequences_in_cluster(
                        messages, cluster, compressed_messages
                    )

                if self.config.preserve_code_blocks:
                    self._preserve_code_blocks_in_cluster(
                        messages, cluster, compressed_messages
                    )

        return compressed_messages

    def _summarize_cluster(
        self, messages: list[Message], cluster: list[int]
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
        return self._generate_cluster_summary(cluster_messages)

    def _generate_cluster_summary(self, cluster_messages: list[Message]) -> str:
        """Generate summary text from a list of messages.
        
        Args:
            cluster_messages: Messages in the cluster.
            
        Returns:
            Summary text.
        """
        if not cluster_messages:
            return ""

        # Simple extraction of key phrases
        key_phrases = []
        for msg in cluster_messages:
            if msg.content:
                # Take first 50 characters as preview
                preview = msg.content[:50]
                if len(msg.content) > 50:
                    preview += "..."
                key_phrases.append(f"{msg.role}: {preview}")

        return "; ".join(key_phrases)

    def _preserve_tool_sequences_in_cluster(
        self,
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
            if idx < len(messages):
                msg = messages[idx]
                if msg.role == "assistant" and msg.tool_calls:
                    # Preserve assistant message with tool calls
                    compressed_messages.append(msg)
                    # Also preserve the corresponding tool response if it exists
                    if idx + 1 < len(messages) and messages[idx + 1].role == "tool":
                        compressed_messages.append(messages[idx + 1])

    def _preserve_code_blocks_in_cluster(
        self,
        messages: list[Message],
        cluster: list[int],
        compressed_messages: list[Message],
    ) -> None:
        """Preserve code blocks within a cluster.
        
        Args:
            messages: All messages.
            cluster: Cluster indices.
            compressed_messages: List to add preserved messages to.
        """
        for idx in cluster:
            if idx < len(messages):
                msg = messages[idx]
                if msg.content and ("```" in msg.content or "def " in msg.content or "class " in msg.content):
                    compressed_messages.append(msg)


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
        if conversation_type == "coding":
            config = CompressionStrategyConfig(
                name="coding",
                high_threshold=CompressionStrategyConstants.CODING_HIGH_THRESHOLD,
                medium_threshold=CompressionStrategyConstants.CODING_MEDIUM_THRESHOLD,
                preserve_tool_sequences=True,
                preserve_code_blocks=True,
            )
        elif conversation_type == "debugging":
            config = CompressionStrategyConfig(
                name="debugging",
                high_threshold=CompressionStrategyConstants.DEBUGGING_HIGH_THRESHOLD,
                medium_threshold=CompressionStrategyConstants.DEBUGGING_MEDIUM_THRESHOLD,
                preserve_tool_sequences=True,
                preserve_code_blocks=True,
            )
        elif conversation_type == "research":
            # Research uses general strategy with different documentation
            config = CompressionStrategyConfig(
                name="research",
                high_threshold=CompressionStrategyConstants.DEFAULT_COMPRESSION_HIGH_THRESHOLD,
                medium_threshold=CompressionStrategyConstants.DEFAULT_COMPRESSION_MEDIUM_THRESHOLD,
                preserve_tool_sequences=True,
                preserve_code_blocks=False,
            )
        else:  # general
            config = CompressionStrategyConfig(
                name="general",
                high_threshold=CompressionStrategyConstants.DEFAULT_COMPRESSION_HIGH_THRESHOLD,
                medium_threshold=CompressionStrategyConstants.DEFAULT_COMPRESSION_MEDIUM_THRESHOLD,
                preserve_tool_sequences=True,
                preserve_code_blocks=False,
            )
        
        return CompressionStrategy(config)