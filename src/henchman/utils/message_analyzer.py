"""Message analyzer for intelligent context management.

Extracted from IntelligentContextManager to reduce class size and improve
separation of concerns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.providers.base import Message

from .importance_scorer import ImportanceScorer
from .intelligent_context_config import IntelligentContextConfig
from .intelligent_context_detector import ConversationTypeDetector
from .intelligent_context_extractor import ContentExtractor
from .message_clusterer import MessageClusterer


class MessageAnalyzer:
    """Analyzes messages for intelligent context management.

    Responsibilities:
    - Calculate importance scores for messages
    - Cluster related messages
    - Detect conversation type
    - Extract critical sections
    """

    def __init__(self: MessageAnalyzer, config: IntelligentContextConfig) -> None:
        """Initialize message analyzer.

        Args:
            config: Configuration for analysis.
        """
        self.config = config
        self.conversation_type_detector = ConversationTypeDetector()
        self.message_clusterer = MessageClusterer(
            cluster_similarity_threshold=config.cluster_similarity_threshold,
        )
        self.importance_scorer = ImportanceScorer()

    def analyze_messages(
        self: MessageAnalyzer, messages: list[Message],
    ) -> tuple[dict[int, float], list[list[int]], str]:
        """Analyze messages to calculate importance scores and clusters.

        Args:
            messages: Messages to analyze.

        Returns:
            Tuple of (importance_scores, clusters, conversation_type)
        """
        if not messages:
            return {}, [], "general"

        # Calculate importance scores
        importance_scores = self._calculate_importance_scores(messages)

        # Cluster related messages
        clusters = self._cluster_messages(messages)

        # Detect conversation type
        conversation_type = self._detect_conversation_type(messages)

        return importance_scores, clusters, conversation_type

    def _calculate_importance_scores(
        self: MessageAnalyzer, messages: list[Message],
    ) -> dict[int, float]:
        """Calculate importance scores for each message.

        Args:
            messages: Messages to score.

        Returns:
            Dictionary mapping message index to importance score (0.0-1.0).
        """
        return self.importance_scorer.calculate_importance_scores(messages)

    def _cluster_messages(
        self: MessageAnalyzer, messages: list[Message],
    ) -> list[list[int]]:
        """Cluster related messages together.

        Args:
            messages: Messages to cluster.

        Returns:
            List of clusters, where each cluster is a list of message indices.
        """
        return self.message_clusterer.cluster_messages(messages)

    def _detect_conversation_type(self: MessageAnalyzer, messages: list[Message]) -> str:
        """Detect the type of conversation.

        Args:
            messages: Messages to analyze.

        Returns:
            Conversation type: "coding", "debugging", "research", or "general".
        """
        return self.conversation_type_detector.detect(messages)

    def extract_critical_sections(self: MessageAnalyzer, content: str) -> list[str]:
        """Extract critical sections from content.

        Args:
            content: Content to analyze.

        Returns:
            List of critical sections.
        """
        return ContentExtractor.extract_critical_sections(content)
