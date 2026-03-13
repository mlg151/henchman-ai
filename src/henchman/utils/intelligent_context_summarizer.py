"""Summary generation for intelligent context management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.utils.intelligent_context_topic_extractor import TopicExtractor
from henchman.utils.intelligent_context_types import ContentAnalysis, IntelligentContextConstants

if TYPE_CHECKING:
    from henchman.providers.base import Message
    from henchman.utils.intelligent_context_config import IntelligentContextConfig


class SummaryGenerator:
    """Generates intelligent summaries for context compaction.

    Extracted from IntelligentContextManager to address long method
    and complex function code smells.
    """

    def __init__(self: SummaryGenerator, config: IntelligentContextConfig) -> None:
        """Initialize summary generator.

        Args:
            config: Configuration for intelligent context management.

        """
        self.config = config

    def generate_intelligent_summary(
        self: SummaryGenerator,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]] | None,
    ) -> str | None:
        """Generate intelligent summary of compressed/dropped content.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.

        Returns:
            Summary string or None if no summary needed.

        """
        if not messages or not importance_scores:
            return None

        # Identify low-importance messages likely to be dropped/compressed
        low_importance_messages = self._identify_low_importance_messages(
            messages,
            importance_scores,
        )

        if not low_importance_messages:
            return None

        # Analyze content types in low-importance messages
        content_analysis = self._analyze_dropped_content(low_importance_messages)

        # Generate summary based on analysis
        summary_parts = self._build_summary_parts(
            messages,
            low_importance_messages,
            content_analysis,
            clusters,
        )

        return "\n".join(summary_parts)

    def _identify_low_importance_messages(
        self: SummaryGenerator,
        messages: list[Message],
        importance_scores: dict[int, float],
    ) -> list[tuple[int, Message, float]]:
        """Identify messages with importance below threshold.

        Args:
            messages: List of messages.
            importance_scores: Importance scores for each message.

        Returns:
            List of (index, message, importance_score) tuples.

        """
        low_importance_messages: list[tuple[int, Message, float]] = []
        threshold = self.config.importance_threshold
        for i, msg in enumerate(messages):
            if i in importance_scores and importance_scores[i] < threshold:
                low_importance_messages.append((i, msg, importance_scores[i]))
        return low_importance_messages

    def _analyze_dropped_content(
        self: SummaryGenerator,
        low_importance_messages: list[tuple[int, Message, float]],
    ) -> ContentAnalysis:
        """Analyze content types in messages likely to be dropped.

        Args:
            low_importance_messages: List of (index, message, importance_score) tuples.

        Returns:
            ContentAnalysis instance with results.

        """
        analysis = ContentAnalysis()

        for _, msg, _ in low_importance_messages:
            if content := msg.content:
                analysis.update_from_content(content)

        return analysis

    def _build_summary_parts(
        self: SummaryGenerator,
        messages: list[Message],
        low_importance_messages: list[tuple[int, Message, float]],
        content_analysis: ContentAnalysis,
        clusters: list[list[int]] | None,
    ) -> list[str]:
        """Build summary parts from analysis.

        Args:
            messages: Original messages.
            low_importance_messages: Low importance messages.
            content_analysis: Analysis of content types.
            clusters: Detected message clusters.

        Returns:
            List of summary parts.

        """
        # Start with overview and analysis
        summary_parts = [
            self._get_overview_part(messages, low_importance_messages),
            *content_analysis.get_summary_parts(),
        ]

        # Add topic summary if we can identify clusters
        if topic_part := self._get_cluster_topics_part(messages, clusters):
            summary_parts.append(topic_part)

        # Add preservation note
        summary_parts.append(
            "Critical context (system prompts, recent messages, errors, tool sequences) "
            "will be preserved.",
        )

        return summary_parts

    def _get_overview_part(
        self: SummaryGenerator,
        messages: list[Message],
        low_importance_messages: list[tuple[int, Message, float]],
    ) -> str:
        """Generate overview part to summary.

        Args:
            messages: Original messages.
            low_importance_messages: Low importance messages.

        Returns:
            Overview string.

        """
        total_messages = len(messages)
        low_importance_count = len(low_importance_messages)

        pct_multiplier = IntelligentContextConstants.PERCENTAGE_MULTIPLIER
        percentage = (
            (low_importance_count / total_messages) * pct_multiplier
            if total_messages > 0
            else 0.0
        )

        return (
            f"Context compaction may affect {low_importance_count}/{total_messages} "
            f"messages ({percentage:.1f}%) with importance below "
            f"{self.config.importance_threshold:.2f}."
        )

    def _get_cluster_topics_part(
        self: SummaryGenerator,
        messages: list[Message],
        clusters: list[list[int]] | None,
    ) -> str | None:
        """Generate cluster topics part to summary.

        Args:
            messages: Original messages.
            clusters: Detected message clusters.

        Returns:
            Topic string or None.

        """
        if not (clusters and len(clusters) > 1):
            return None

        cluster_topics = TopicExtractor.extract_cluster_topics(messages, clusters)
        if not cluster_topics:
            return None

        max_topics = IntelligentContextConstants.MAX_TOPICS_TO_SHOW_IN_SUMMARY
        return (
            "• Topics discussed: "
            + ", ".join(cluster_topics[:max_topics])
        )
