"""Message clustering for intelligent context management.

This module provides functionality to cluster related messages in a conversation
based on semantic similarity, role patterns, and temporal proximity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.providers.base import Message


class MessageClusterer:
    """Clusters related messages based on semantic similarity.

    Groups messages that discuss the same topic or are part of the
    same conversational thread.
    """

    def __init__(
        self: MessageClusterer,
        cluster_similarity_threshold: float = 0.7,
        minimum_word_length: int = 3,
        minimum_shared_words: int = 2,
    ) -> None:
        """Initialize message clusterer.

        Args:
            cluster_similarity_threshold: Similarity threshold for clustering messages.
                Higher values create more specific clusters.
            minimum_word_length: Minimum word length for keyword extraction.
            minimum_shared_words: Minimum shared words for role pattern clustering.
        """
        self.cluster_similarity_threshold = cluster_similarity_threshold
        self.minimum_word_length = minimum_word_length
        self.minimum_shared_words = minimum_shared_words

    def cluster_messages(self: MessageClusterer, messages: list[Message]) -> list[list[int]]:
        """Cluster related messages based on semantic similarity.

        Args:
            messages: Messages to cluster.

        Returns:
            List of clusters, where each cluster is a list of message indices.
        """
        if not messages:
            return []

        # Start with each message in its own cluster
        clusters: list[list[int]] = [[i] for i in range(len(messages))]

        # Step 1: Group tool call sequences as atomic clusters
        clusters = self._cluster_tool_call_sequences(messages, clusters)

        # Step 2: Merge adjacent messages with temporal proximity
        clusters = self._cluster_temporal_proximity(messages, clusters)

        # Step 3: Merge clusters by topic similarity
        clusters = self._cluster_topic_similarity(messages, clusters)

        # Step 4: Merge by role patterns (user-assistant pairs)
        return self._cluster_role_patterns(messages, clusters)


    def _cluster_tool_call_sequences(
        self: MessageClusterer, messages: list[Message], clusters: list[list[int]],
    ) -> list[list[int]]:
        """Group tool call sequences as atomic clusters.

        A tool call sequence is: assistant message with tool_calls -> tool response.
        These should stay together as they represent a single atomic operation.

        Args:
            messages: All messages.
            clusters: Current clusters.

        Returns:
            Updated clusters with tool sequences merged.
        """
        if len(messages) < 2:
            return clusters

        # Find assistant messages with tool calls
        for i in range(len(messages) - 1):
            curr_msg = messages[i]
            next_msg = messages[i + 1]

            # Check if current is assistant with tool calls and next is tool response
            if (
                curr_msg.role == "assistant"
                and curr_msg.tool_calls
                and next_msg.role == "tool"
                and next_msg.tool_call_id
            ):
                # Verify tool_call_id matches one of the tool calls
                tool_call_ids = {tc.id for tc in curr_msg.tool_calls}
                if next_msg.tool_call_id in tool_call_ids:
                    # Merge clusters containing i and i+1
                    clusters = self._merge_clusters_containing_indices(clusters, [i, i + 1])

        return clusters

    def _cluster_temporal_proximity(
        self: MessageClusterer, messages: list[Message], clusters: list[list[int]],
    ) -> list[list[int]]:
        """Merge adjacent messages that are temporally close.

        Messages that are adjacent in the conversation and share similar
        characteristics should be clustered together.

        Args:
            messages: All messages.
            clusters: Current clusters.

        Returns:
            Updated clusters with temporally adjacent messages merged.
        """
        if len(clusters) < 2:
            return clusters

        i = 0
        while i < len(clusters) - 1:
            curr_cluster = clusters[i]
            next_cluster = clusters[i + 1]

            # Check if clusters are adjacent in the message sequence
            if self._should_merge_adjacent_clusters(messages, curr_cluster, next_cluster):
                # Merge the two clusters
                merged_cluster = curr_cluster + next_cluster
                clusters[i] = merged_cluster
                del clusters[i + 1]
                # Don't increment i since we need to check the new merged cluster
                # with the next one
                continue

            i += 1

        return clusters

    def _should_merge_adjacent_clusters(
        self: MessageClusterer, messages: list[Message], curr_cluster: list[int], next_cluster: list[int],  # noqa: E501
    ) -> bool:
        """Determine if two adjacent clusters should be merged.

        Args:
            messages: All messages.
            curr_cluster: Current cluster indices.
            next_cluster: Next cluster indices.

        Returns:
            True if clusters should be merged, False otherwise.
        """
        # Check if clusters are adjacent in the message sequence
        curr_max = max(curr_cluster)
        next_min = min(next_cluster)

        if next_min != curr_max + 1:
            return False

        # Get the last message of current cluster and first of next
        last_msg_idx = curr_cluster[-1]
        first_msg_idx = next_cluster[0]

        last_msg = messages[last_msg_idx]
        first_msg = messages[first_msg_idx]

        # Merge if same role (except tool responses which are handled separately)
        return (
            (last_msg.role == first_msg.role
            and last_msg.role != "tool")
            or (last_msg.role == "user"
            and first_msg.role == "assistant")
            or (last_msg.role == "assistant"
            and first_msg.role == "user")
        )

    def _cluster_topic_similarity(
        self: MessageClusterer, messages: list[Message], clusters: list[list[int]],
    ) -> list[list[int]]:
        """Merge clusters that discuss similar topics.

        Uses simple keyword extraction and Jaccard similarity to identify
        clusters discussing the same topic.

        Args:
            messages: All messages.
            clusters: Current clusters.

        Returns:
            Updated clusters with similar topics merged.
        """
        if len(clusters) < 2:
            return clusters

        # Extract keywords for each cluster
        cluster_keywords = []
        for cluster in clusters:
            keywords = self._extract_cluster_keywords(messages, cluster)
            cluster_keywords.append(keywords)

        # Try to merge clusters with similar keywords
        i = 0
        while i < len(clusters):
            j = i + 1
            while j < len(clusters):
                if not cluster_keywords[i] or not cluster_keywords[j]:
                    j += 1
                    continue

                # Calculate Jaccard similarity
                intersection = len(cluster_keywords[i] & cluster_keywords[j])
                union = len(cluster_keywords[i] | cluster_keywords[j])
                similarity = intersection / union if union > 0 else 0

                if similarity >= self.cluster_similarity_threshold:
                    # Merge clusters
                    clusters[i].extend(clusters[j])
                    # Update keywords for merged cluster
                    cluster_keywords[i] = cluster_keywords[i] | cluster_keywords[j]
                    # Remove merged cluster
                    del clusters[j]
                    del cluster_keywords[j]
                    # Continue checking against remaining clusters
                    continue

                j += 1
            i += 1

        return clusters

    def _extract_cluster_keywords(
        self: MessageClusterer, messages: list[Message], cluster: list[int],
    ) -> set[str]:
        """Extract keywords from messages in a cluster.

        Args:
            messages: All messages.
            cluster: Indices of messages in the cluster.

        Returns:
            Set of significant keywords from the cluster.
        """
        keywords = set()
        for idx in cluster:
            msg = messages[idx]
            if msg.content:
                # Simple keyword extraction: split by common delimiters
                # and take words longer than minimum_word_length characters
                words = msg.content.lower().split()
                for word in words:
                    # Remove punctuation
                    word = word.strip(".,!?;:\"'()[]{}")
                    if len(word) > self.minimum_word_length and not word.startswith("http"):
                        keywords.add(word)
        return keywords

    def _cluster_role_patterns(
        self: MessageClusterer, messages: list[Message], clusters: list[list[int]],
    ) -> list[list[int]]:
        """Merge clusters based on role patterns.

        Specifically looks for user-assistant pairs that should be kept together.

        Args:
            messages: All messages.
            clusters: Current clusters.

        Returns:
            Updated clusters with role patterns merged.
        """
        if len(clusters) < 2:
            return clusters

        i = 0
        while i < len(clusters) - 1:
            if self._should_merge_clusters_by_role_pattern(messages, clusters, i):
                # Merge the clusters
                merged_cluster = clusters[i] + clusters[i + 1]
                clusters[i] = merged_cluster
                del clusters[i + 1]
                # Don't increment i since we need to check the new merged cluster
                continue

            i += 1

        return clusters

    def _should_merge_clusters_by_role_pattern(
        self: MessageClusterer, messages: list[Message], clusters: list[list[int]], index: int,
    ) -> bool:
        """Determine if two adjacent clusters should be merged based on role patterns.

        Args:
            messages: All messages.
            clusters: Current clusters.
            index: Index of the first cluster to check.

        Returns:
            True if clusters should be merged, False otherwise.
        """
        curr_cluster = clusters[index]
        next_cluster = clusters[index + 1]

        # Check if clusters form a user-assistant or assistant-user pair
        if not self._are_clusters_role_complementary(messages, curr_cluster, next_cluster):
            return False

        # Check if they're discussing the same topic
        return self._do_clusters_share_significant_words(messages, curr_cluster, next_cluster)

    def _are_clusters_role_complementary(
        self: MessageClusterer, messages: list[Message], cluster1: list[int], cluster2: list[int],
    ) -> bool:
        """Check if two clusters have complementary roles (user-assistant pair).

        Args:
            messages: All messages.
            cluster1: First cluster indices.
            cluster2: Second cluster indices.

        Returns:
            True if clusters have complementary roles.
        """
        cluster1_roles = {messages[idx].role for idx in cluster1}
        cluster2_roles = {messages[idx].role for idx in cluster2}

        return ("user" in cluster1_roles and "assistant" in cluster2_roles) or (
            "assistant" in cluster1_roles and "user" in cluster2_roles
        )

    def _do_clusters_share_significant_words(
        self: MessageClusterer, messages: list[Message], cluster1: list[int], cluster2: list[int],
    ) -> bool:
        """Check if two clusters share enough significant words to be merged.

        Args:
            messages: All messages.
            cluster1: First cluster indices.
            cluster2: Second cluster indices.

        Returns:
            True if clusters share enough significant words.
        """
        # Extract content from clusters
        cluster1_content = self._extract_cluster_content(messages, cluster1)
        cluster2_content = self._extract_cluster_content(messages, cluster2)

        # Extract significant words
        cluster1_words = self._extract_significant_words(cluster1_content)
        cluster2_words = self._extract_significant_words(cluster2_content)

        # Check for common words
        common_words = cluster1_words & cluster2_words
        return len(common_words) >= self.minimum_shared_words

    def _extract_cluster_content(self: MessageClusterer, messages: list[Message], cluster: list[int]) -> str:  # noqa: E501
        """Extract and concatenate content from messages in a cluster.

        Args:
            messages: All messages.
            cluster: Cluster indices.

        Returns:
            Concatenated content from the cluster.
        """
        content_parts = []
        for idx in cluster:
            msg = messages[idx]
            if msg.content:
                content_parts.append(msg.content)
        return " ".join(content_parts).lower()

    def _extract_significant_words(self: MessageClusterer, text: str) -> set[str]:
        """Extract significant words from text.

        Args:
            text: Text to extract words from.

        Returns:
            Set of significant words.
        """
        words = set()
        for word in text.split():
            # Remove punctuation
            word = word.strip(".,!?;:\"'()[]{}")
            if len(word) > self.minimum_word_length and not word.startswith("http"):
                words.add(word)
        return words

    def _merge_clusters_containing_indices(
        self: MessageClusterer, clusters: list[list[int]], indices: list[int],
    ) -> list[list[int]]:
        """Merge clusters that contain any of the given indices.

        Args:
            clusters: Current clusters.
            indices: Indices that should be in the same cluster.

        Returns:
            Updated clusters with specified indices merged into one cluster.
        """
        # Find which clusters contain the indices
        clusters_to_merge = []
        for idx in indices:
            for cluster_idx, cluster in enumerate(clusters):
                if idx in cluster and cluster_idx not in clusters_to_merge:
                    clusters_to_merge.append(cluster_idx)

        if len(clusters_to_merge) <= 1:
            return clusters  # Nothing to merge

        # Sort in descending order so we can delete safely
        clusters_to_merge.sort(reverse=True)

        # Create merged cluster
        merged_cluster = []
        for cluster_idx in clusters_to_merge:
            merged_cluster.extend(clusters[cluster_idx])

        # Remove duplicates and sort
        merged_cluster = sorted(set(merged_cluster))

        # Remove old clusters and add merged one
        first_idx = clusters_to_merge[-1]  # Smallest index
        for cluster_idx in clusters_to_merge:
            del clusters[cluster_idx]

        clusters.insert(first_idx, merged_cluster)

        return clusters
