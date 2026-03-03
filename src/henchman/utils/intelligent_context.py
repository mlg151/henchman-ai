"""Intelligent context management system.

This module provides an intelligent context manager that reduces token usage
while preserving important context through importance scoring, clustering,
and adaptive compression techniques.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from henchman.providers.base import Message
from henchman.utils.compression_strategy import CompressionStrategyFactory
from henchman.utils.importance_scorer import ImportanceScorer
from henchman.utils.message_clusterer import MessageClusterer
from henchman.utils.tokens import TokenCounter


class IntelligentContextConstants:
    """Constants for intelligent context management."""

    # Default configuration values
    DEFAULT_MAX_TOKENS: int = 8000
    DEFAULT_MAX_PROTECTED_RATIO: float = 0.3
    DEFAULT_IMPORTANCE_THRESHOLD: float = 0.5
    DEFAULT_CLUSTER_SIMILARITY_THRESHOLD: float = 0.7
    DEFAULT_SAFETY_LIMIT_RATIO: float = 0.75
    DEFAULT_MINIMUM_WORD_LENGTH: int = 3
    DEFAULT_MINIMUM_SHARED_WORDS: int = 2
    DEFAULT_CLUSTER_SIZE_BOOST_FACTOR: float = 0.1
    DEFAULT_COMPRESSION_HIGH_THRESHOLD: float = 0.6
    DEFAULT_COMPRESSION_MEDIUM_THRESHOLD: float = 0.3

    # Compression strategy thresholds
    DEBUGGING_HIGH_THRESHOLD: float = 0.8
    DEBUGGING_MEDIUM_THRESHOLD: float = 0.5
    CODING_HIGH_THRESHOLD: float = 0.7
    CODING_MEDIUM_THRESHOLD: float = 0.4

    # Cluster analysis constants
    MAX_CLUSTER_SIZE_FOR_BOOST: int = 10
    MINIMUM_KEYWORD_COUNT_FOR_TYPE_DETECTION: int = 2


class ConversationTypeDetector:
    """Detects the type of conversation based on message content."""

    # Define keyword sets as class constants to eliminate duplicate method structure
    _CODING_KEYWORDS: ClassVar[list[str]] = [
        "def ", "class ", "import ", "function", "code", "python", "javascript",
        "java", "typescript", "variable", "loop", "if ", "else", "return",
        "print(", "console.log", "git", "commit", "branch", "merge",
        "api", "endpoint", "request", "response", "json", "xml",
    ]

    _RESEARCH_KEYWORDS: ClassVar[list[str]] = [
        "research", "study", "analysis", "analyze", "investigate", "explore",
        "find", "search", "look up", "information", "data", "statistics",
        "report", "document", "summary", "conclusion", "findings",
        "according to", "source", "reference", "citation", "paper",
    ]

    _DEBUGGING_KEYWORDS: ClassVar[list[str]] = [
        "error", "bug", "debug", "fix", "issue", "problem", "crash",
        "exception", "traceback", "stack trace", "log", "warning",
        "failed", "failure", "broken", "doesn't work", "not working",
        "why is", "how to fix", "troubleshoot", "diagnose",
    ]

    # Map conversation types to their keyword sets
    _KEYWORD_SETS: ClassVar[dict[str, list[str]]] = {
        "coding": _CODING_KEYWORDS,
        "research": _RESEARCH_KEYWORDS,
        "debugging": _DEBUGGING_KEYWORDS,
    }

    def detect(self: ConversationTypeDetector, messages: list[Message]) -> str:
        """Detect the type of conversation based on message content.

        Args:
            messages: List of messages to analyze.

        Returns:
            Conversation type: "coding", "research", "debugging", or "general".
        """
        if not messages:
            return "general"

        all_content = self._extract_all_content(messages)
        keyword_counts = self._count_keywords_by_type(all_content)

        return self._determine_conversation_type(keyword_counts)

    def _extract_all_content(self: ConversationTypeDetector, messages: list[Message]) -> str:
        """Extract and combine all message content.

        Args:
            messages: List of messages.

        Returns:
            Combined content as lowercase string.
        """
        return " ".join(
            msg.content.lower() for msg in messages if msg.content
        )

    def _count_keywords_by_type(self: ConversationTypeDetector, content: str) -> dict[str, int]:
        """Count keyword occurrences by conversation type.

        Args:
            content: Text content to analyze.

        Returns:
            Dictionary with counts for each conversation type.
        """
        return {
            conversation_type: self._count_keywords(content, keywords)
            for conversation_type, keywords in self._KEYWORD_SETS.items()
        }

    def _count_keywords(self: ConversationTypeDetector, content: str, keywords: list[str]) -> int:
        """Count how many keywords appear in content.

        Args:
            content: Text to search in.
            keywords: List of keywords to search for.

        Returns:
            Number of keywords found.
        """
        return sum(1 for keyword in keywords if keyword in content)

    def _determine_conversation_type(self: ConversationTypeDetector, keyword_counts: dict[str, int]) -> str:  # noqa: E501
        """Determine conversation type based on keyword counts.

        Args:
            keyword_counts: Dictionary with counts for each conversation type.

        Returns:
            Conversation type string.
        """
        coding_count = keyword_counts["coding"]
        research_count = keyword_counts["research"]
        debugging_count = keyword_counts["debugging"]

        min_count = IntelligentContextConstants.MINIMUM_KEYWORD_COUNT_FOR_TYPE_DETECTION

        if debugging_count > max(coding_count, research_count, min_count):
            return "debugging"
        if coding_count > max(research_count, debugging_count, min_count):
            return "coding"
        if research_count > max(coding_count, debugging_count, min_count):
            return "research"
        return "general"


@dataclass
class IntelligentContextConfig:
    """Configuration for intelligent context management.

    Attributes:
        max_tokens: Maximum tokens to keep in context.
        max_protected_ratio: Maximum ratio of context that can be protected.
            If protected zone exceeds this, oldest protected content is truncated.
        importance_threshold: Minimum importance score to preserve a message.
            Messages below this threshold are candidates for compression or removal.
        cluster_similarity_threshold: Similarity threshold for clustering messages.
            Higher values create more specific clusters.
        adaptive_compression: Whether to use adaptive compression techniques
            based on conversation structure and content type.
        safety_limit_ratio: Ratio of max_tokens to use as safety limit for individual messages.
        minimum_word_length: Minimum word length for keyword extraction.
        minimum_shared_words: Minimum shared words for role pattern clustering.
        cluster_size_boost_factor: Factor for boosting cluster importance based on size.
        compression_high_threshold: High importance threshold for compression.
        compression_medium_threshold: Medium importance threshold for compression.
    """

    max_tokens: int = IntelligentContextConstants.DEFAULT_MAX_TOKENS
    max_protected_ratio: float = IntelligentContextConstants.DEFAULT_MAX_PROTECTED_RATIO
    importance_threshold: float = IntelligentContextConstants.DEFAULT_IMPORTANCE_THRESHOLD
    cluster_similarity_threshold: float = IntelligentContextConstants.DEFAULT_CLUSTER_SIMILARITY_THRESHOLD  # noqa: E501
    adaptive_compression: bool = True
    safety_limit_ratio: float = IntelligentContextConstants.DEFAULT_SAFETY_LIMIT_RATIO
    minimum_word_length: int = IntelligentContextConstants.DEFAULT_MINIMUM_WORD_LENGTH
    minimum_shared_words: int = IntelligentContextConstants.DEFAULT_MINIMUM_SHARED_WORDS
    cluster_size_boost_factor: float = IntelligentContextConstants.DEFAULT_CLUSTER_SIZE_BOOST_FACTOR
    compression_high_threshold: float = IntelligentContextConstants.DEFAULT_COMPRESSION_HIGH_THRESHOLD  # noqa: E501
    compression_medium_threshold: float = IntelligentContextConstants.DEFAULT_COMPRESSION_MEDIUM_THRESHOLD  # noqa: E501


@dataclass
class CompressionConfig:
    """Configuration for compression strategies.

    Attributes:
        high_threshold: Threshold for high-importance clusters.
        medium_threshold: Threshold for medium-importance clusters.
        preserve_tool_sequences: Whether to preserve tool call sequences.
        preserve_code_blocks: Whether to preserve code blocks.
    """
    high_threshold: float
    medium_threshold: float
    preserve_tool_sequences: bool
    preserve_code_blocks: bool


@dataclass
class IntelligentCompactionResult:
    """Result of an intelligent compaction operation.

    Attributes:
        messages: The compacted messages.
        was_compacted: Whether compaction actually occurred.
        dropped_count: Number of messages/sequences dropped.
        summary: Optional summary of dropped content.
        importance_scores: Mapping of message indices to importance scores.
        clusters: Detected conversation clusters.
        compression_ratio: Achieved compression ratio.
    """

    messages: list[Message]
    was_compacted: bool = False
    dropped_count: int = 0
    summary: str | None = None
    importance_scores: dict[int, float] | None = None
    clusters: list[list[int]] | None = None
    compression_ratio: float | None = None
class IntelligentContextManager:
    """Intelligent context manager with advanced compaction techniques.

    This class provides drop-in replacement for ContextCompactor with
    additional intelligent features:
    - Importance scoring of messages based on content, role, and position
    - Semantic clustering of related messages
    - Adaptive compression based on conversation structure
    - Preservation of critical information and decision points
    """

    def __init__(
        self: IntelligentContextManager,
        max_tokens: int | None = None,
        max_protected_ratio: float | None = None,
        importance_threshold: float | None = None,
        cluster_similarity_threshold: float | None = None,
        *,
        adaptive_compression: bool | None = None,
    ) -> None:
        """Initialize intelligent context manager.

        Args:
            max_tokens: Maximum tokens to keep in context.
            max_protected_ratio: Maximum ratio of context that can be protected.
                If protected zone exceeds this, oldest protected content is truncated.
            importance_threshold: Minimum importance score to preserve a message.
                Messages below this threshold are candidates for compression or removal.
            cluster_similarity_threshold: Similarity threshold for clustering messages.
                Higher values create more specific clusters.
            adaptive_compression: Whether to use adaptive compression techniques
                based on conversation structure and content type.
        """
        # Use provided values or defaults from constants
        self.config = IntelligentContextConfig(
            max_tokens=max_tokens or IntelligentContextConstants.DEFAULT_MAX_TOKENS,
            max_protected_ratio=max_protected_ratio or IntelligentContextConstants.DEFAULT_MAX_PROTECTED_RATIO,  # noqa: E501
            importance_threshold=importance_threshold or IntelligentContextConstants.DEFAULT_IMPORTANCE_THRESHOLD,  # noqa: E501
            cluster_similarity_threshold=cluster_similarity_threshold or IntelligentContextConstants.DEFAULT_CLUSTER_SIMILARITY_THRESHOLD,  # noqa: E501
            adaptive_compression=adaptive_compression if adaptive_compression is not None else True,
        )
        self.max_protected_tokens = int(
            self.config.max_tokens * self.config.max_protected_ratio,
        )

        # Initialize component classes
        self.importance_scorer = ImportanceScorer()
        self.message_clusterer = MessageClusterer(
            cluster_similarity_threshold=self.config.cluster_similarity_threshold,
            minimum_word_length=self.config.minimum_word_length,
            minimum_shared_words=self.config.minimum_shared_words,
        )

    def enforce_safety_limits(self: IntelligentContextManager, messages: list[Message]) -> list[Message]:  # noqa: E501
        """Enforce limits on individual message size using tokens.

        This prevents context overflow from individual massive messages
        by truncating them to fit within the context window.

        Args:
            messages: List of messages to check.

        Returns:
            List of messages with content limits enforced.
        """
        # TODO: Implement intelligent safety limits with semantic preservation
        safe_messages = []
        limit = int(self.config.max_tokens * self.config.safety_limit_ratio)

        for msg in messages:
            safe_message = self._enforce_message_safety_limit(msg, limit)
            safe_messages.append(safe_message)

        return safe_messages

    def _enforce_message_safety_limit(self: IntelligentContextManager, message: Message, limit: int) -> Message:  # noqa: E501
        """Enforce safety limit on a single message.

        Args:
            message: The message to check.
            limit: Token limit for the message.

        Returns:
            Message with content truncated if necessary.
        """
        if not message.content:
            return message

        if len(message.content) < limit:
            return message

        if TokenCounter.count_text(message.content) > limit:
            return self._create_truncated_message(message, limit)
        return message

    @staticmethod
    @staticmethod
    def _create_truncated_message(message: Message, limit: int) -> Message:
        """Create a truncated version of a message.

        Args:
            message: The original message to truncate.
            limit: Token limit for truncation.

        Returns:
            New Message with truncated content.
        """
        # Handle None content case
        message_content = message.content
        if not message_content:
            return message

        truncated_content = TokenCounter.truncate_text(message_content, limit)
        new_content = (
            truncated_content + f"\n... (truncated by safety limit: > {limit} tokens)"
        )

        return Message(
            role=message.role,
            content=new_content,
            tool_calls=message.tool_calls,
            tool_call_id=message.tool_call_id,
        )

    def compact(
        self: IntelligentContextManager,
        messages: list[Message],
        protect_from_index: int = -1,  # noqa: ARG002
    ) -> list[Message]:
        """Compact messages to fit within max_tokens using intelligent techniques.

        Uses importance scoring, clustering, and adaptive compression to
        preserve critical context while reducing token usage.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.
                Set to -1 to disable protection (default behavior).

        Returns:
            Compacted messages that fit within max_tokens.
        """
        # TODO: Implement intelligent compaction with importance scoring
        # For now, return messages unchanged as placeholder
        return messages

    def compact_with_result(
        self: IntelligentContextManager,
        messages: list[Message],
        protect_from_index: int = -1,  # noqa: ARG002
    ) -> IntelligentCompactionResult:
        """Compact messages and return detailed result with intelligence metrics.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.

        Returns:
            IntelligentCompactionResult with compacted messages and metadata.
        """
        # TODO: Implement intelligent compaction with metrics
        # For now, return placeholder result
        return IntelligentCompactionResult(
            messages=messages,
            was_compacted=False,
            dropped_count=0,
            summary=None,
            importance_scores=None,
            clusters=None,
            compression_ratio=None,
        )

    def validate_compacted_sequence(self: IntelligentContextManager, messages: list[Message]) -> bool:  # noqa: E501
        """Validate that a message sequence follows OpenAI API rules.

        Args:
            messages: The messages to validate.

        Returns:
            True if the sequence is valid, False otherwise.
        """
        # TODO: Implement enhanced validation with semantic checks
        # For now, use basic validation
        for i, msg in enumerate(messages):
            if msg.role == "tool":
                if i == 0:
                    return False
                prev_msg = messages[i - 1]
                if prev_msg.role != "assistant" or not prev_msg.tool_calls:
                    return False

                tool_call_ids = {tc.id for tc in prev_msg.tool_calls}
                if msg.tool_call_id not in tool_call_ids:
                    return False

        return True

    def _calculate_importance_scores(self: IntelligentContextManager, messages: list[Message]) -> dict[int, float]:  # noqa: E501
        """Calculate importance scores for each message.

        Importance is based on:
        - Message role (system > user > assistant > tool)
        - Content length and complexity
        - Position in conversation
        - Presence of tool calls or important keywords
        - Semantic significance

        Args:
            messages: Messages to score.

        Returns:
            Dictionary mapping message indices to importance scores (0.0-1.0).
        """
        return self.importance_scorer.calculate_importance_scores(messages)

    def _cluster_messages(self: IntelligentContextManager, messages: list[Message]) -> list[list[int]]:  # noqa: E501
        """Cluster related messages based on semantic similarity.

        Groups messages that discuss the same topic or are part of the
        same conversational thread.

        Args:
            messages: Messages to cluster.

        Returns:
            List of clusters, where each cluster is a list of message indices.
        """
        return self.message_clusterer.cluster_messages(messages)

    def _apply_adaptive_compression(
        self: IntelligentContextManager,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
    ) -> list[Message]:
        """Apply adaptive compression based on importance and clustering.

        Compression techniques:
        - Summarization of low-importance clusters
        - Extraction of key points from verbose messages
        - Removal of redundant information
        - Preservation of critical decision points

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.

        Returns:
            Compressed messages.
        """
        if not messages or not clusters:
            return messages

        # Detect conversation type
        detector = ConversationTypeDetector()
        conversation_type = detector.detect(messages)

        # Calculate cluster importance scores
        cluster_importance = self._calculate_cluster_importance(
            clusters, importance_scores,
        )

        # Apply compression strategy based on conversation type
        strategy = CompressionStrategyFactory.create_for_conversation_type(conversation_type)
        return strategy.compress(messages, clusters, cluster_importance)

    def _detect_conversation_type(self: IntelligentContextManager, messages: list[Message]) -> str:
        """Detect the type of conversation based on message content.

        This method is kept for backward compatibility with tests.
        It delegates to ConversationTypeDetector.

        Args:
            messages: List of messages to analyze.

        Returns:
            Conversation type: "coding", "research", "debugging", or "general".
        """
        detector = ConversationTypeDetector()
        return detector.detect(messages)

    def _calculate_cluster_importance(
        self: IntelligentContextManager,
        clusters: list[list[int]],
        importance_scores: dict[int, float],
    ) -> dict[int, float]:
        """Calculate importance score for each cluster.

        Args:
            clusters: List of message clusters.
            importance_scores: Importance scores for individual messages.

        Returns:
            Dictionary mapping cluster index to importance score (0.0-1.0).
        """
        cluster_importance = {}
        for cluster_idx, cluster in enumerate(clusters):
            if not cluster:
                cluster_importance[cluster_idx] = 0.0
                continue

            # Calculate average importance of messages in cluster
            total_score = 0.0
            valid_scores = 0
            for msg_idx in cluster:
                if msg_idx in importance_scores:
                    total_score += importance_scores[msg_idx]
                    valid_scores += 1

            avg_score = total_score / valid_scores if valid_scores > 0 else 0.0

            # Boost score for larger clusters (more context)
            size_factor = min(len(cluster) / 10.0, 1.0) * self.config.cluster_size_boost_factor
            cluster_score = min(1.0, avg_score + size_factor)

            cluster_importance[cluster_idx] = cluster_score

        return cluster_importance

    def _generate_intelligent_summary(
        self: IntelligentContextManager, messages: list[Message], importance_scores: dict[int, float], clusters: list[list[int]],  # noqa: ARG002, E501
    ) -> str | None:
        """Generate intelligent summary of compressed/dropped content.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.

        Returns:
            Summary string, or None if no summary needed.
        """
        # TODO: Implement intelligent summary generation
        return None

    def _preserve_critical_context(
        self: IntelligentContextManager, messages: list[Message], importance_scores: dict[int, float],  # noqa: ARG002, E501
    ) -> list[Message]:
        """Ensure critical context is preserved regardless of token limits.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.

        Returns:
        Returns:
            Messages with critical context preserved.
        """
        # TODO: Implement critical context preservation
        return messages

