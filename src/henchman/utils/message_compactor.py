"""Message compactor for intelligent context management.

Extracted from IntelligentContextManager to address Large Class code smell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.providers.base import Message
from henchman.utils.cluster_utils import ClusterUtils
from henchman.utils.sorting_utils import sort_by_importance
from henchman.utils.tokens import TokenCounter

if TYPE_CHECKING:
    from henchman.utils.intelligent_context import IntelligentContextConfig


class MessageCompactor:
    """Compacts messages using intelligent truncation algorithms.

    This class handles the core logic of deciding which messages to keep
    when context exceeds token limits, while preserving important content.
    """

    def __init__(self, config: IntelligentContextConfig) -> None:
        """Initialize message compactor.

        Args:
            config: Configuration for intelligent context management.
        """
        self.config = config

    def apply_intelligent_truncation(
        self,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
        protect_from_index: int,
    ) -> list[Message]:
        """Apply intelligent truncation when messages exceed token limit.

        Preserves:
        1. Protected messages (from protect_from_index to end)
        2. Complete high-importance clusters
        3. High-importance individual messages
        4. Tool call sequences and critical content

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.
            protect_from_index: Index from which to protect messages.

        Returns:
            Intelligently truncated messages.
        """
        if not messages:
            return []

        # Count tokens in original messages
        total_tokens = self._count_tokens(messages)

        # If within limit, return all messages
        if total_tokens <= self.config.max_tokens:
            return messages

        # Sort messages by importance (descending)
        sorted_indices = self._sort_by_importance(len(messages), importance_scores)

        # Initialize result
        messages_to_keep: list[Message] = []
        tokens_used = 0

        # Add protected messages first
        messages_to_keep, tokens_used = self._add_protected_messages(
            messages, importance_scores, protect_from_index, messages_to_keep, tokens_used
        )

        # Calculate cluster importance
        cluster_importance = self.calculate_cluster_importance(clusters, importance_scores)

        # Sort clusters by importance (descending)
        cluster_indices = sorted(
            range(len(clusters)),
            key=lambda i: cluster_importance.get(i, 0.0),
            reverse=True,
        )

        # Add complete high-importance clusters
        messages_to_keep, tokens_used = self._add_complete_clusters(
            messages, clusters, cluster_indices, messages_to_keep, tokens_used
        )

        # Add high-importance individual messages
        messages_to_keep, tokens_used = self._add_individual_messages(
            messages, sorted_indices, messages_to_keep, tokens_used
        )

        # Sort messages back to original order
        return self._sort_messages_to_original_order(messages, messages_to_keep)

    def _count_tokens(self, messages: list[Message]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: Messages to count tokens for.

        Returns:
            Total token count.
        """
        # Import here to avoid circular imports
        from henchman.utils.intelligent_context import TokenCounterWrapper

        return TokenCounterWrapper.count_messages_tokens(messages)

    def _sort_by_importance(
        self, item_count: int, importance_scores: dict[int, float]
    ) -> list[int]:
        """Sort indices by importance scores (descending).

        Args:
            item_count: Total number of items.
            importance_scores: Importance scores for each item.

        Returns:
            List of indices sorted by importance (descending).
        """
        return sort_by_importance(item_count, importance_scores)

    def _add_protected_messages(
        self,
        messages: list[Message],
        importance_scores: dict[int, float],
        protect_from_index: int,
        messages_to_keep: list[Message],
        tokens_used: int,
    ) -> tuple[list[Message], int]:
        """Add protected messages to the keep list.

        Args:
            messages: All messages.
            importance_scores: Importance scores for each message.
            protect_from_index: Index from which to protect messages.
            messages_to_keep: Current list of messages to keep.
            tokens_used: Current token count.

        Returns:
            Updated messages_to_keep and tokens_used.
        """
        if protect_from_index < 0 or protect_from_index >= len(messages):
            return messages_to_keep, tokens_used

        # Sort protected indices by importance (most important first)
        protected_indices = list(range(protect_from_index, len(messages)))
        protected_indices.sort(
            key=lambda i: importance_scores.get(i, 0.0),
            reverse=True,
        )

        for idx in protected_indices:
            msg = messages[idx]
            if self._add_message_if_fits(msg, messages_to_keep, tokens_used):
                messages_to_keep.append(msg)
                tokens_used = self._update_tokens_used(msg, tokens_used)

        return messages_to_keep, tokens_used

    def calculate_cluster_importance(
        self, clusters: list[list[int]], importance_scores: dict[int, float]
    ) -> dict[int, float]:
        """Calculate importance score for each cluster.

        Args:
            clusters: List of message clusters.
            importance_scores: Importance scores for individual messages.

        Returns:
            Dictionary mapping cluster indices to importance scores.
        """
        return ClusterUtils.calculate_cluster_importance(clusters, importance_scores, self.config)

    def _add_complete_clusters(
        self,
        messages: list[Message],
        clusters: list[list[int]],
        cluster_indices: list[int],
        messages_to_keep: list[Message],
        tokens_used: int,
    ) -> tuple[list[Message], int]:
        """Add complete high-importance clusters to the keep list.

        Args:
            messages: All messages.
            clusters: List of message clusters.
            cluster_indices: Cluster indices sorted by importance.
            messages_to_keep: Current list of messages to keep.
            tokens_used: Current token count.

        Returns:
            Updated messages_to_keep and tokens_used.
        """
        kept_indices = {i for i, msg in enumerate(messages) if msg in messages_to_keep}

        for cluster_idx in cluster_indices:
            cluster = clusters[cluster_idx]

            # Skip if cluster is already partially kept
            if any(idx in kept_indices for idx in cluster):
                continue

            # Check if entire cluster fits
            cluster_tokens = sum(
                TokenCounter.count_text(messages[idx].content or "")
                for idx in cluster
                if idx < len(messages)
            )

            if tokens_used + cluster_tokens <= self.config.max_tokens:
                # Add all messages in cluster
                for idx in cluster:
                    if idx < len(messages):
                        msg = messages[idx]
                        messages_to_keep.append(msg)
                        tokens_used = self._update_tokens_used(msg, tokens_used)
                        kept_indices.add(idx)

        return messages_to_keep, tokens_used

    def _add_individual_messages(
        self,
        messages: list[Message],
        message_indices: list[int],
        messages_to_keep: list[Message],
        tokens_used: int,
    ) -> tuple[list[Message], int]:
        """Add high-importance individual messages to the keep list.

        Args:
            messages: All messages.
            message_indices: Message indices sorted by importance.
            messages_to_keep: Current list of messages to keep.
            tokens_used: Current token count.

        Returns:
            Updated messages_to_keep and tokens_used.
        """
        kept_indices = {i for i, msg in enumerate(messages) if msg in messages_to_keep}

        for idx in message_indices:
            if idx in kept_indices:
                continue

            msg = messages[idx]
            if self._add_message_if_fits(msg, messages_to_keep, tokens_used):
                messages_to_keep.append(msg)
                tokens_used = self._update_tokens_used(msg, tokens_used)
                kept_indices.add(idx)

        return messages_to_keep, tokens_used

    def _add_message_if_fits(
        self, msg: Message, messages_to_keep: list[Message], tokens_used: int
    ) -> bool:
        """Add a message to the keep list if it fits within token limit.

        Args:
            msg: Message to add.
            messages_to_keep: Current list of messages to keep.
            tokens_used: Current token count.

        Returns:
            True if message was added, False otherwise.
        """
        if msg in messages_to_keep:
            return False

        msg_tokens = TokenCounter.count_text(msg.content or "")
        return tokens_used + msg_tokens <= self.config.max_tokens

    def _update_tokens_used(self, msg: Message, tokens_used: int) -> int:
        """Update token count after adding a message.

        Args:
            msg: Message that was added.
            tokens_used: Current token count.

        Returns:
            Updated token count.
        """
        msg_tokens = TokenCounter.count_text(msg.content or "")
        return tokens_used + msg_tokens

    def _sort_messages_to_original_order(
        self, original_messages: list[Message], messages_to_sort: list[Message]
    ) -> list[Message]:
        """Sort messages back to their original order.

        Args:
            original_messages: Original message list (for order reference).
            messages_to_sort: Messages to sort.

        Returns:
            Messages sorted to match original order.
        """
        # Create a list of indices for messages to sort
        indices_to_sort = []
        for msg in messages_to_sort:
            try:
                idx = original_messages.index(msg)
                indices_to_sort.append(idx)
            except ValueError:
                # Message not found in original list (shouldn't happen)
                indices_to_sort.append(len(original_messages))

        # Sort indices and get corresponding messages
        sorted_indices = sorted(indices_to_sort)
        return [original_messages[idx] for idx in sorted_indices if idx < len(original_messages)]
