"""Intelligent context management system.

This module provides an intelligent context manager that reduces token usage
while preserving important context through importance scoring, clustering,
and adaptive compression techniques.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.utils.compression_strategy import CompressionStrategyFactory
from henchman.utils.intelligent_context_aggregator import (
    ImportanceSorter,
    MessagePreserver,
    SequenceValidator,
)
from henchman.utils.intelligent_context_config import (
    IntelligentContextConfig,
    IntelligentContextParams,
)
from henchman.utils.intelligent_context_detector import ConversationTypeDetector
from henchman.utils.intelligent_context_extractor import ContentExtractor
from henchman.utils.intelligent_context_formatter import (
    IntelligentTruncator,
    MessageSafetyEnforcer,
    TokenCounterWrapper,
)
from henchman.utils.intelligent_context_summarizer import SummaryGenerator
from henchman.utils.intelligent_context_topic_extractor import TopicExtractor
from henchman.utils.intelligent_context_types import (
    CompressionConfig,
    IntelligentCompactionResult,
    IntelligentContextConstants,
    PreservedContent,
    ResultCreationParams,
)
from henchman.utils.message_compactor import MessageCompactor

__all__ = [
    "CompressionConfig",
    "CompressionStrategyFactory",
    "ContentExtractor",
    "ConversationTypeDetector",
    "ImportanceSorter",
    "IntelligentCompactionResult",
    "IntelligentContextConfig",
    "IntelligentContextConstants",
    "IntelligentContextManager",
    "IntelligentContextParams",
    "IntelligentTruncator",
    "MessageCompactor",
    "MessagePreserver",
    "MessageSafetyEnforcer",
    "PreservedContent",
    "ResultCreationParams",
    "SequenceValidator",
    "SummaryGenerator",
    "TokenCounterWrapper",
    "TopicExtractor",
]

if TYPE_CHECKING:
    from henchman.providers.base import Message


class IntelligentContextManager:
    """Intelligent context manager with advanced compaction techniques.

    Features:
    - Semantic clustering of related messages
    - Adaptive compression based on content type
    - Importance scoring for message preservation
    - Safety limits to prevent context overflow
    - Intelligent truncation with protected sections

    The manager uses multiple strategies to reduce token usage while
    preserving critical context, error messages, tool calls, and
    recent conversation history.
    """

    def __init__(
        self: IntelligentContextManager,
        params: IntelligentContextParams | None = None,
        config: IntelligentContextConfig | None = None,
    ) -> None:
        """Initialize intelligent context manager.

        Args:
            params: Parameters for intelligent context management.
            config: Pre-configured settings object. If provided, returns it unchanged.

        """
        # Ensure we have a params object
        params = params or IntelligentContextParams()

        self.config = IntelligentContextConfig.from_params(params=params, config=config)

        from henchman.utils.message_analyzer import MessageAnalyzer

        self.message_analyzer = MessageAnalyzer(self.config)
        self.message_safety_enforcer = MessageSafetyEnforcer(
            safety_limit_ratio=self.config.safety_limit_ratio,
            max_tokens=self.config.max_tokens,
        )
        self.summary_generator = SummaryGenerator(self.config)
        self.message_preserver = MessagePreserver(self.config)
        self.message_compactor = MessageCompactor(self.config)

    @classmethod
    def from_params(
        cls: type[IntelligentContextManager],
        params: IntelligentContextParams,
        config: IntelligentContextConfig | None = None,
    ) -> IntelligentContextManager:
        """Create IntelligentContextManager from params object.

        Alternative constructor to address primitive obsession code smell.

        Args:
            params: IntelligentContextParams object containing configuration parameters.
            config: Optional IntelligentContextConfig object. If provided,
                params are ignored.

        Returns:
            IntelligentContextManager instance.

        """
        # If config is provided, use it directly
        if config is not None:
            return cls(config=config)

        # Otherwise, create config from params and pass it
        config_from_params = IntelligentContextConfig.from_params(params=params)
        return cls(config=config_from_params)

    def enforce_safety_limits(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> list[Message]:
        """Enforce limits on individual message size using tokens with semantic preservation.

        This prevents context overflow from individual massive messages
        by truncating them intelligently to preserve important content.

        Args:
            messages: List of messages to check.

        Returns:
            List of messages with content limits enforced intelligently.

        """
        return self.message_safety_enforcer.enforce_safety_limits(messages)

    def apply_intelligent_truncation(
        self: IntelligentContextManager,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
        protect_from_index: int = -1,
    ) -> list[Message]:
        """Apply intelligent truncation when messages exceed token limit.

        Prioritizes preserving high-importance messages and complete clusters.

        Args:
            messages: Messages to truncate.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.
            protect_from_index: Index from which messages are protected.

        Returns:
            Truncated messages that fit within max_tokens.

        """
        return self.message_compactor.apply_intelligent_truncation(
            messages,
            importance_scores,
            clusters,
            protect_from_index,
        )

    def compact(
        self: IntelligentContextManager,
        messages: list[Message],
        protect_from_index: int = -1,
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
        # Use compact_with_result and return just the messages
        result = self.compact_with_result(messages, protect_from_index)
        return result.messages

    def compact_with_result(
        self: IntelligentContextManager,
        messages: list[Message],
        protect_from_index: int = -1,
    ) -> IntelligentCompactionResult:
        """Compact messages and return detailed result with intelligence metrics.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.

        Returns:
            IntelligentCompactionResult with compacted messages and metadata.

        """
        if not messages:
            return self._create_empty_result()

        return self._compact_messages_with_intelligence(messages, protect_from_index)

    def _compact_messages_with_intelligence(
        self: IntelligentContextManager,
        messages: list[Message],
        protect_from_index: int,
    ) -> IntelligentCompactionResult:
        """Core logic for compacting messages with intelligence metrics.

        Args:
            messages: The messages to compact.
            protect_from_index: Index from which messages are protected.

        Returns:
            IntelligentCompactionResult with compacted messages and metadata.

        """
        # Calculate importance scores and cluster messages
        importance_scores, clusters = self._analyze_messages(messages)

        # Apply compression and safety limits
        safe_messages = self._apply_compression_and_safety(messages, importance_scores, clusters)

        # Prepare results
        params = self._prepare_result_params(
            messages,
            safe_messages,
            importance_scores,
            clusters,
        )

        current_tokens = TokenCounterWrapper.count_messages_tokens(safe_messages)

        # Handle based on token limit
        if current_tokens <= self.config.max_tokens:
            return params.create_result_without_truncation(self, current_tokens)

        # Need truncation
        return params.create_result_with_truncation(self, protect_from_index)

    def _prepare_result_params(
        self: IntelligentContextManager,
        original_messages: list[Message],
        safe_messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
    ) -> ResultCreationParams:
        """Prepare parameters for creating compaction results.

        Args:
            original_messages: Original messages.
            safe_messages: Compressed and safety-limited messages.
            importance_scores: Importance scores.
            clusters: Message clusters.

        Returns:
            ResultCreationParams instance.

        """
        original_tokens = TokenCounterWrapper.count_messages_tokens(original_messages)
        current_tokens = TokenCounterWrapper.count_messages_tokens(safe_messages)

        was_compacted = self._detect_compaction(
            original_messages,
            safe_messages,
            original_tokens,
            current_tokens,
        )

        return ResultCreationParams(
            original_messages=original_messages,
            safe_messages=safe_messages,
            importance_scores=importance_scores,
            clusters=clusters,
            original_tokens=original_tokens,
            was_compacted=was_compacted,
        )

    def _create_empty_result(self: IntelligentContextManager) -> IntelligentCompactionResult:
        """Create an empty compaction result.

        Returns:
            Empty IntelligentCompactionResult.

        """
        return IntelligentCompactionResult(
            messages=[],
            was_compacted=False,
            dropped_count=0,
            summary=None,
            importance_scores={},
            clusters=[],
            compression_ratio=0.0,
        )

    def _analyze_messages(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> tuple[dict[int, float], list[list[int]]]:
        """Analyze messages for importance and clustering.

        Args:
            messages: Messages to analyze.

        Returns:
            Tuple of (importance_scores, clusters).

        """
        importance_scores = self._calculate_importance_scores(messages)
        clusters = self._cluster_messages(messages)
        return importance_scores, clusters

    def _apply_compression_and_safety(
        self: IntelligentContextManager,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
    ) -> list[Message]:
        """Apply compression and safety limits to messages.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.

        Returns:
            Compressed and safety-limited messages.

        """
        compressed_messages = self._apply_adaptive_compression(
            messages,
            importance_scores,
            clusters,
        )
        compressed_messages = self.message_preserver.preserve_critical_context(
            compressed_messages,
            importance_scores,
        )
        return self.enforce_safety_limits(compressed_messages)

    def _detect_compaction(
        self: IntelligentContextManager,
        original_messages: list[Message],
        compressed_messages: list[Message],
        original_tokens: int,
        current_tokens: int,
    ) -> bool:
        """Detect if compaction occurred.

        Args:
            original_messages: Original messages.
            compressed_messages: Compressed messages.
            original_tokens: Original token count.
            current_tokens: Current token count.

        Returns:
            True if compaction occurred, False otherwise.

        """
        return len(compressed_messages) < len(original_messages) or current_tokens < original_tokens

    def validate_compacted_sequence(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> bool:
        """Validate that a message sequence follows OpenAI API rules.

        Args:
            messages: The messages to validate.

        Returns:
            True if the sequence is valid, False otherwise.

        """
        return SequenceValidator.validate_compacted_sequence(messages)

    def _calculate_importance_scores(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> dict[int, float]:
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
        importance_scores, _, _ = self.message_analyzer.analyze_messages(messages)
        return importance_scores

    def _cluster_messages(
        self: IntelligentContextManager,
        messages: list[Message],
    ) -> list[list[int]]:
        """Cluster related messages based on semantic similarity.

        Groups messages that discuss the same topic or are part of the
        same conversational thread.

        Args:
            messages: Messages to cluster.

        Returns:
            List of clusters, where each cluster is a list of message indices.

        """
        _, clusters, _ = self.message_analyzer.analyze_messages(messages)
        return clusters

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

        # Calculate cluster importance scores using MessageCompactor
        # This addresses the feature envy code smell
        cluster_importance = self.message_compactor.calculate_cluster_importance(
            clusters,
            importance_scores,
        )

        # Apply compression strategy based on conversation type
        strategy = CompressionStrategyFactory.create_for_conversation_type(conversation_type)
        return strategy.compress(messages, clusters, cluster_importance)
