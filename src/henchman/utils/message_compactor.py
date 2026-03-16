"""Message compactor for intelligent context management.

Extracted from IntelligentContextManager to address Large Class code smell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from henchman.utils.cluster_utils import ClusterUtils
from henchman.utils.intelligent_context_formatter import TokenCounterWrapper
from henchman.utils.sorting_utils import sort_by_importance
from henchman.utils.tokens import TokenCounter

if TYPE_CHECKING:
    from henchman.providers.base import Message
    from henchman.utils.intelligent_context import IntelligentContextConfig


def _calc_message_tokens(msg: Message) -> int:
    """Count tokens in a single message.

    Args:
        msg: Message to count tokens for.

    Returns:
        Token count for the message content.
    """
    return TokenCounter.count_text(msg.content or "")


def _sort_to_original_order(
    original_messages: list[Message],
    messages_to_sort: list[Message],
) -> list[Message]:
    """Sort messages back to their original order.

    Uses identity-based index lookup for O(n) performance.

    Args:
        original_messages: Original message list (for order reference).
        messages_to_sort: Messages to sort.

    Returns:
        Messages sorted to match original order.
    """
    sentinel = len(original_messages)
    msg_to_index = {id(msg): i for i, msg in enumerate(original_messages)}
    indices = [msg_to_index.get(id(msg), sentinel) for msg in messages_to_sort]
    return [original_messages[i] for i in sorted(indices) if i < sentinel]


class MessageCompactor:
    """Compacts messages using intelligent truncation algorithms.

    This class handles the core logic of deciding which messages to keep
    when context exceeds token limits, while preserving important content.
    """

    def __init__(self: Self, config: IntelligentContextConfig) -> None:
        """Initialize message compactor.

        Args:
            config: Configuration for intelligent context management.
        """
        self.config = config

    def apply_intelligent_truncation(
        self: Self,
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

        if self._count_tokens(messages) <= self.config.max_tokens:
            return messages

        messages_to_keep = self._collect_messages_to_keep(
            messages, importance_scores, clusters, protect_from_index,
        )
        return _sort_to_original_order(messages, messages_to_keep)

    def _collect_messages_to_keep(
        self: Self,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
        protect_from_index: int,
    ) -> list[Message]:
        """Collect all messages that fit within the token budget.

        Applies three passes in priority order: protected messages, then
        high-importance complete clusters, then individual messages.

        Args:
            messages: All messages.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.
            protect_from_index: Index from which to protect messages.

        Returns:
            Messages selected to keep within the token budget.
        """
        sorted_indices = self._sort_by_importance(len(messages), importance_scores)
        messages_to_keep: list[Message] = []
        tokens_used = 0

        messages_to_keep, tokens_used = self._add_protected_messages(
            messages, importance_scores, protect_from_index, messages_to_keep, tokens_used,
        )

        cluster_indices = self._sort_clusters_by_importance(clusters, importance_scores)
        messages_to_keep, tokens_used = self._add_complete_clusters(
            messages, clusters, cluster_indices, messages_to_keep, tokens_used,
        )

        messages_to_keep, tokens_used = self._add_individual_messages(
            messages, sorted_indices, messages_to_keep, tokens_used,
        )
        return messages_to_keep

    def _sort_clusters_by_importance(
        self: Self,
        clusters: list[list[int]],
        importance_scores: dict[int, float],
    ) -> list[int]:
        """Sort cluster indices by their aggregate importance (descending).

        Args:
            clusters: List of message clusters.
            importance_scores: Importance scores for individual messages.

        Returns:
            Cluster indices sorted by descending importance.
        """
        cluster_importance = self.calculate_cluster_importance(clusters, importance_scores)
        return sorted(
            range(len(clusters)),
            key=lambda i: cluster_importance.get(i, 0.0),
            reverse=True,
        )

    def _count_tokens(self: Self, messages: list[Message]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: Messages to count tokens for.

        Returns:
            Total token count.
        """
        return TokenCounterWrapper.count_messages_tokens(messages)

    def _sort_by_importance(
        self: Self, item_count: int, importance_scores: dict[int, float],
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
        self: Self,
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

        protected_indices = list(range(protect_from_index, len(messages)))
        protected_indices.sort(
            key=lambda i: importance_scores.get(i, 0.0),
            reverse=True,
        )

        for idx in protected_indices:
            msg = messages[idx]
            if self._add_message_if_fits(msg, messages_to_keep, tokens_used):
                messages_to_keep.append(msg)
                tokens_used += _calc_message_tokens(msg)

        return messages_to_keep, tokens_used

    def calculate_cluster_importance(
        self: Self, clusters: list[list[int]], importance_scores: dict[int, float],
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
        self: Self,
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

            if any(idx in kept_indices for idx in cluster):
                continue

            cluster_tokens = sum(
                _calc_message_tokens(messages[idx])
                for idx in cluster
                if idx < len(messages)
            )
            if tokens_used + cluster_tokens > self.config.max_tokens:
                continue

            for idx in cluster:
                if idx >= len(messages):
                    continue
                msg = messages[idx]
                messages_to_keep.append(msg)
                tokens_used += _calc_message_tokens(msg)
                kept_indices.add(idx)

        return messages_to_keep, tokens_used

    def _add_individual_messages(
        self: Self,
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
                tokens_used += _calc_message_tokens(msg)
                kept_indices.add(idx)

        return messages_to_keep, tokens_used

    def _add_message_if_fits(
        self: Self, msg: Message, messages_to_keep: list[Message], tokens_used: int,
    ) -> bool:
        """Check whether a message fits within the token budget and is not already kept.

        Args:
            msg: Message to check.
            messages_to_keep: Current list of messages to keep.
            tokens_used: Current token count.

        Returns:
            True if message fits and is not already kept, False otherwise.
        """
        if msg in messages_to_keep:
            return False

        return tokens_used + _calc_message_tokens(msg) <= self.config.max_tokens
