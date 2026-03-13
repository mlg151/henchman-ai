"""Topic extraction for intelligent context management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.utils.intelligent_context_types import IntelligentContextConstants

if TYPE_CHECKING:
    from henchman.providers.base import Message


class TopicExtractor:
    """Extracts topic keywords from message clusters."""

    @staticmethod
    def extract_cluster_topics(
        messages: list[Message],
        clusters: list[list[int]],
    ) -> list[str]:
        """Extract topic keywords from message clusters.

        Args:
            messages: List of messages.
            clusters: Detected message clusters.

        Returns:
            List of topic keywords.

        """
        topics: set[str] = set()

        for cluster in clusters:
            cluster_topics = TopicExtractor.extract_topics_from_cluster(messages, cluster)
            topics.update(cluster_topics)

        return sorted(topics)

    @staticmethod
    def extract_topics_from_cluster(
        messages: list[Message],
        cluster: list[int],
    ) -> set[str]:
        """Extract topics from a single cluster.

        Args:
            messages: List of messages.
            cluster: Single cluster of message indices.

        Returns:
            Set of topics found in the cluster.

        """
        topics: set[str] = set()
        combined_content = TopicExtractor._extract_combined_cluster_content(messages, cluster)

        if not combined_content:
            return topics

        # Look for technical keywords
        TopicExtractor._add_technical_keywords(combined_content, topics)

        # Look for code language markers
        TopicExtractor._add_code_markers(combined_content, topics)

        return topics

    @staticmethod
    def _extract_combined_cluster_content(
        messages: list[Message],
        cluster: list[int],
    ) -> str:
        """Extract and combine content from a cluster.

        Args:
            messages: List of messages.
            cluster: Single cluster of message indices.

        Returns:
            Combined lowercase content string, or empty string if no content.

        """
        cluster_content: list[str] = [
            messages[i].content
            for i in cluster
            if i < len(messages) and messages[i].content
        ]

        if not cluster_content:
            return ""

        return " ".join(cluster_content).lower()

    @staticmethod
    def _add_technical_keywords(
        content: str,
        topics: set[str],
    ) -> None:
        """Add technical keywords found in content to topics set.

        Args:
            content: Content to search.
            topics: Set to add topics to.

        """
        common_tech_keywords = IntelligentContextConstants.TECH_KEYWORDS

        for keyword in common_tech_keywords:
            if keyword in content:
                topics.add(keyword)

    @staticmethod
    def _add_code_markers(
        content: str,
        topics: set[str],
    ) -> None:
        """Add code language markers found in content to topics set.

        Args:
            content: Content to search.
            topics: Set to add topics to.

        """
        code_markers = IntelligentContextConstants.PYTHON_CODE_MARKERS
        for marker in code_markers:
            if marker in content:
                topics.add("python code")
                break
