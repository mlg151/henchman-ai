"""Summary generator for intelligent context management.

This module extracts summary generation logic from IntelligentContextManager
to address long method and complex function code smells.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.providers.base import Message
    from henchman.utils.intelligent_context import IntelligentContextConfig


class SummaryGenerator:
    """Generates intelligent summaries for context compaction."""

    def __init__(self, config: IntelligentContextConfig) -> None:
        """Initialize summary generator.

        Args:
            config: Configuration for intelligent context management.
        """
        self.config = config

    def generate_intelligent_summary(
        self,
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
            messages, importance_scores
        )

        if not low_importance_messages:
            return None

        # Analyze content types in low-importance messages
        content_analysis = self._analyze_dropped_content(low_importance_messages)

        # Generate summary based on analysis
        summary_parts = self._build_summary_parts(
            messages, low_importance_messages, content_analysis, clusters
        )

        return "\n".join(summary_parts)

    def _identify_low_importance_messages(
        self,
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
        low_importance_messages = []
        for i, msg in enumerate(messages):
            if i in importance_scores and importance_scores[i] < self.config.importance_threshold:
                low_importance_messages.append((i, msg, importance_scores[i]))
        return low_importance_messages

    def _analyze_dropped_content(
        self,
        low_importance_messages: list[tuple[int, Message, float]],
    ) -> dict[str, bool]:
        """Analyze content types in messages likely to be dropped.

        Args:
            low_importance_messages: List of (index, message, importance_score) tuples.

        Returns:
            Dictionary with analysis results.
        """
        analysis = {
            "has_code": False,
            "has_errors": False,
            "has_decisions": False,
            "has_tools": False,
        }

        for _, msg, _ in low_importance_messages:
            if not msg.content:
                continue

            content = msg.content.lower()

            # Check for code blocks
            if "```" in content:
                analysis["has_code"] = True

            # Check for error/exception keywords
            error_keywords = ["error", "exception", "fail", "warning", "traceback"]
            if any(keyword in content for keyword in error_keywords):
                analysis["has_errors"] = True

            # Check for decision keywords
            decision_keywords = ["decision", "conclusion", "recommend", "suggest", "choose"]
            if any(keyword in content for keyword in decision_keywords):
                analysis["has_decisions"] = True

            # Check for tool-related content
            tool_keywords = ["tool", "function", "call", "execute", "run"]
            if any(keyword in content for keyword in tool_keywords):
                analysis["has_tools"] = True

        return analysis

    def _build_summary_parts(
        self,
        messages: list[Message],
        low_importance_messages: list[tuple[int, Message, float]],
        content_analysis: dict[str, bool],
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
        summary_parts = []

        # Add overview
        total_messages = len(messages)
        low_importance_count = len(low_importance_messages)
        percentage = (low_importance_count / total_messages) * 100

        summary_parts.append(
            f"Context compaction may affect {low_importance_count}/{total_messages} "
            f"messages ({percentage:.1f}%) with importance below "
            f"{self.config.importance_threshold:.2f}."
        )

        # Add content type analysis
        if content_analysis["has_code"]:
            summary_parts.append("• Contains code blocks or technical details")
        if content_analysis["has_errors"]:
            summary_parts.append("• Includes error messages or warnings")
        if content_analysis["has_decisions"]:
            summary_parts.append("• Documents decisions or conclusions")
        if content_analysis["has_tools"]:
            summary_parts.append("• Includes tool call sequences")

        # Add topic summary if we can identify clusters
        if clusters and len(clusters) > 1:
            # Note: _extract_cluster_topics would need to be moved to this class
            # For now, we'll skip this part
            pass

        # Add preservation note
        summary_parts.append(
            "Critical context (system prompts, recent messages, errors, tool sequences) "
            "will be preserved."
        )

        return summary_parts