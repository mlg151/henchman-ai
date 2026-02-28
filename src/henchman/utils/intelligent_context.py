"""Intelligent context management system.

This module provides an intelligent context manager that reduces token usage
while preserving important context through importance scoring, clustering,
and adaptive compression techniques.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from henchman.providers.base import Message
from henchman.utils.tokens import TokenCounter

if TYPE_CHECKING:
    # For type checking only
    from henchman.providers.base import Message


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
    
    @staticmethod
    def detect(messages: list[Message]) -> str:
        """Detect the type of conversation based on message content.

        Args:
            messages: List of messages to analyze.

        Returns:
            Conversation type: "coding", "research", "debugging", or "general".
        """
        if not messages:
            return "general"

        all_content = ConversationTypeDetector._extract_all_content(messages)
        keyword_counts = ConversationTypeDetector._count_keywords_by_type(all_content)
        
        return ConversationTypeDetector._determine_conversation_type(keyword_counts)

    @staticmethod
    def _extract_all_content(messages: list[Message]) -> str:
        """Extract and combine all message content.
        
        Args:
            messages: List of messages.
            
        Returns:
            Combined content as lowercase string.
        """
        return " ".join(
            msg.content.lower() for msg in messages if msg.content
        )

    @staticmethod
    def _count_keywords_by_type(content: str) -> dict[str, int]:
        """Count keyword occurrences by conversation type.
        
        Args:
            content: Text content to analyze.
            
        Returns:
            Dictionary with counts for each conversation type.
        """
        return {
            "coding": ConversationTypeDetector._count_keywords(content, ConversationTypeDetector._get_coding_keywords()),
            "research": ConversationTypeDetector._count_keywords(content, ConversationTypeDetector._get_research_keywords()),
            "debugging": ConversationTypeDetector._count_keywords(content, ConversationTypeDetector._get_debugging_keywords()),
        }

    @staticmethod
    def _get_coding_keywords() -> list[str]:
        """Get keywords for coding conversations."""
        return [
            "def ", "class ", "import ", "function", "code", "python", "javascript",
            "java", "typescript", "variable", "loop", "if ", "else", "return",
            "print(", "console.log", "git", "commit", "branch", "merge",
            "api", "endpoint", "request", "response", "json", "xml",
        ]

    @staticmethod
    def _get_research_keywords() -> list[str]:
        """Get keywords for research conversations."""
        return [
            "research", "study", "analysis", "analyze", "investigate", "explore",
            "find", "search", "look up", "information", "data", "statistics",
            "report", "document", "summary", "conclusion", "findings",
            "according to", "source", "reference", "citation", "paper",
        ]

    @staticmethod
    def _get_debugging_keywords() -> list[str]:
        """Get keywords for debugging conversations."""
        return [
            "error", "bug", "debug", "fix", "issue", "problem", "crash",
            "exception", "traceback", "stack trace", "log", "warning",
            "failed", "failure", "broken", "doesn't work", "not working",
            "why is", "how to fix", "troubleshoot", "diagnose",
        ]

    @staticmethod
    def _count_keywords(content: str, keywords: list[str]) -> int:
        """Count how many keywords appear in content.
        
        Args:
            content: Text to search in.
            keywords: List of keywords to search for.
            
        Returns:
            Number of keywords found.
        """
        return sum(1 for keyword in keywords if keyword in content)

    @staticmethod
    def _determine_conversation_type(keyword_counts: dict[str, int]) -> str:
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
        elif coding_count > max(research_count, debugging_count, min_count):
            return "coding"
        elif research_count > max(coding_count, debugging_count, min_count):
            return "research"
        else:
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
    cluster_similarity_threshold: float = IntelligentContextConstants.DEFAULT_CLUSTER_SIMILARITY_THRESHOLD
    adaptive_compression: bool = True
    safety_limit_ratio: float = IntelligentContextConstants.DEFAULT_SAFETY_LIMIT_RATIO
    minimum_word_length: int = IntelligentContextConstants.DEFAULT_MINIMUM_WORD_LENGTH
    minimum_shared_words: int = IntelligentContextConstants.DEFAULT_MINIMUM_SHARED_WORDS
    cluster_size_boost_factor: float = IntelligentContextConstants.DEFAULT_CLUSTER_SIZE_BOOST_FACTOR
    compression_high_threshold: float = IntelligentContextConstants.DEFAULT_COMPRESSION_HIGH_THRESHOLD
    compression_medium_threshold: float = IntelligentContextConstants.DEFAULT_COMPRESSION_MEDIUM_THRESHOLD


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
        self,
        max_tokens: int | None = None,
        max_protected_ratio: float | None = None,
        importance_threshold: float | None = None,
        cluster_similarity_threshold: float | None = None,
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
            max_protected_ratio=max_protected_ratio or IntelligentContextConstants.DEFAULT_MAX_PROTECTED_RATIO,
            importance_threshold=importance_threshold or IntelligentContextConstants.DEFAULT_IMPORTANCE_THRESHOLD,
            cluster_similarity_threshold=cluster_similarity_threshold or IntelligentContextConstants.DEFAULT_CLUSTER_SIMILARITY_THRESHOLD,
            adaptive_compression=adaptive_compression if adaptive_compression is not None else True,
        )
        self.max_protected_tokens = int(
            self.config.max_tokens * self.config.max_protected_ratio
        )

    def enforce_safety_limits(self, messages: list[Message]) -> list[Message]:
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

    def _enforce_message_safety_limit(self, message: Message, limit: int) -> Message:
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
        else:
            return message

    def _create_truncated_message(self, message: Message, limit: int) -> Message:
        """Create a truncated version of a message.
        
        Args:
            message: The original message to truncate.
            limit: Token limit for truncation.
            
        Returns:
            New Message with truncated content.
        """
        truncated_content = TokenCounter.truncate_text(message.content, limit)
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
        self,
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
        # TODO: Implement intelligent compaction with importance scoring
        # For now, return messages unchanged as placeholder
        return messages

    def compact_with_result(
        self,
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

    def validate_compacted_sequence(self, messages: list[Message]) -> bool:
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

    def _calculate_importance_scores(self, messages: list[Message]) -> dict[int, float]:
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
        if not messages:
            return {}

        importance_scores = {}

        for i, message in enumerate(messages):
            score = self._calculate_message_importance(message, i, len(messages))
            importance_scores[i] = score

        return importance_scores

    def _calculate_message_importance(
        self, message: Message, index: int, total_messages: int
    ) -> float:
        """Calculate importance score for a single message.

        Args:
            message: The message to score.
            index: Position of the message in the conversation.
            total_messages: Total number of messages in the conversation.

        Returns:
            Importance score between 0.0 and 1.0.
        """
        # Start with base score from role and content features
        score = self._calculate_base_importance(message)

        # Apply position-based boost (recent messages are more important)
        score = self._apply_position_boost(score, index, total_messages)

        # Apply content length boost (longer messages might be more important)
        score = self._apply_content_length_boost(score, message)

        # Ensure score is within valid range
        score = self._clamp_score(score)

        # Apply minimum score if no other factors applied
        score = self._apply_minimum_score(score)

        return score

    def _calculate_base_importance(self, message: Message) -> float:
        """Calculate base importance score based on message features.
        
        Considers:
        - Tool calls (highest priority)
        - Error keywords in content
        - Message role
        
        Args:
            message: The message to score.
            
        Returns:
            Base importance score.
        """
        score = 0.0

        # 1. Check for tool calls (high importance)
        if self._has_tool_calls(message):
            score = max(score, self._TOOL_CALL_IMPORTANCE)

        # 2. Check for errors in content (high importance)
        if self._contains_error_keywords(message):
            score = max(score, self._ERROR_KEYWORD_IMPORTANCE)

        # 3. Check message role
        score = max(score, self._get_role_based_importance(message))

        return score

    def _has_tool_calls(self, message: Message) -> bool:
        """Check if message has tool calls.
        
        Args:
            message: The message to check.
            
        Returns:
            True if message has tool calls, False otherwise.
        """
        return bool(message.tool_calls and len(message.tool_calls) > 0)

    def _contains_error_keywords(self, message: Message) -> bool:
        """Check if message content contains error keywords.
        
        Args:
            message: The message to check.
            
        Returns:
            True if message contains error keywords, False otherwise.
        """
        if not message.content:
            return False

        content_lower = message.content.lower()
        error_indicators = [
            "error",
            "exception",
            "failed",
            "failure",
            "invalid",
            "unexpected",
        ]

        return any(indicator in content_lower for indicator in error_indicators)

    def _get_role_based_importance(self, message: Message) -> float:
        """Get importance score based on message role.
        
        Args:
            message: The message to score.
            
        Returns:
            Role-based importance score.
        """
        if message.role == "system":
            return self._SYSTEM_ROLE_IMPORTANCE
        elif message.role == "user":
            return self._USER_ROLE_IMPORTANCE
        elif message.role == "assistant":
            return self._get_assistant_importance(message)
        elif message.role == "tool":
            return self._get_tool_importance(message)
        else:
            return 0.0

    def _get_assistant_importance(self, message: Message) -> float:
        """Get importance score for assistant messages.
        
        Args:
            message: The assistant message to score.
            
        Returns:
            Importance score for assistant message.
        """
        # Tool calls already handled with higher priority
        if message.tool_calls:
            return 0.0  # Already accounted for in base importance

        if message.content and len(message.content) > self._LONG_CONTENT_THRESHOLD:
            return self._ASSISTANT_LONG_CONTENT_IMPORTANCE
        else:
            return self._ASSISTANT_SHORT_CONTENT_IMPORTANCE

    def _get_tool_importance(self, message: Message) -> float:
        """Get importance score for tool messages.
        
        Args:
            message: The tool message to score.
            
        Returns:
            Importance score for tool message.
        """
        if message.content and len(message.content) > self._TOOL_CONTENT_THRESHOLD:
            return self._TOOL_WITH_CONTENT_IMPORTANCE
        else:
            return self._TOOL_WITHOUT_CONTENT_IMPORTANCE

    def _apply_position_boost(
        self, score: float, index: int, total_messages: int
    ) -> float:
        """Apply position-based boost to score.
        
        Recent messages get higher importance.
        
        Args:
            score: Current importance score.
            index: Position of the message (0-based).
            total_messages: Total number of messages.
            
        Returns:
            Score with position boost applied.
        """
        if total_messages <= 1:
            return score

        position_factor = index / (total_messages - 1)  # 0.0 to 1.0
        position_boost = position_factor * self._POSITION_BOOST_MAX
        return min(1.0, score + position_boost)

    def _apply_content_length_boost(self, score: float, message: Message) -> float:
        """Apply content length boost to score.
        
        Longer messages might be more important.
        
        Args:
            score: Current importance score.
            message: The message to check.
            
        Returns:
            Score with content length boost applied.
        """
        if not message.content:
            return score

        content_length = len(message.content)

        if content_length > self._VERY_LONG_CONTENT_THRESHOLD:
            return min(1.0, score + self._VERY_LONG_CONTENT_BOOST)
        elif content_length > self._LONG_CONTENT_THRESHOLD:
            return min(1.0, score + self._LONG_CONTENT_BOOST)
        else:
            return score

    def _clamp_score(self, score: float) -> float:
        """Clamp score to valid range [0.0, 1.0].
        
        Args:
            score: The score to clamp.
            
        Returns:
            Clamped score between 0.0 and 1.0.
        """
        return max(0.0, min(1.0, score))

    def _apply_minimum_score(self, score: float) -> float:
        """Apply minimum score if no other factors applied.
        
        Args:
            score: Current importance score.
            
        Returns:
            Score with minimum applied if needed.
        """
        if score == 0.0:
            return self._MINIMUM_IMPORTANCE
        return score

    # Importance scoring constants
    _TOOL_CALL_IMPORTANCE: float = 0.9
    _ERROR_KEYWORD_IMPORTANCE: float = 0.8
    _SYSTEM_ROLE_IMPORTANCE: float = 0.7
    _USER_ROLE_IMPORTANCE: float = 0.6
    _ASSISTANT_LONG_CONTENT_IMPORTANCE: float = 0.5
    _ASSISTANT_SHORT_CONTENT_IMPORTANCE: float = 0.3
    _TOOL_WITH_CONTENT_IMPORTANCE: float = 0.7
    _TOOL_WITHOUT_CONTENT_IMPORTANCE: float = 0.4
    _POSITION_BOOST_MAX: float = 0.2
    _VERY_LONG_CONTENT_THRESHOLD: int = 500
    _VERY_LONG_CONTENT_BOOST: float = 0.1
    _LONG_CONTENT_THRESHOLD: int = 100
    _LONG_CONTENT_BOOST: float = 0.05
    _TOOL_CONTENT_THRESHOLD: int = 20
    _MINIMUM_IMPORTANCE: float = 0.1

    def _cluster_messages(self, messages: list[Message]) -> list[list[int]]:
        """Cluster related messages based on semantic similarity.

        Groups messages that discuss the same topic or are part of the
        same conversational thread.

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
        clusters = self._cluster_role_patterns(messages, clusters)

        return clusters

    def _cluster_tool_call_sequences(
        self, messages: list[Message], clusters: list[list[int]]
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
        self, messages: list[Message], clusters: list[list[int]]
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
        self, messages: list[Message], curr_cluster: list[int], next_cluster: list[int]
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
            last_msg.role == first_msg.role
            and last_msg.role != "tool"
            or last_msg.role == "user"
            and first_msg.role == "assistant"
            or last_msg.role == "assistant"
            and first_msg.role == "user"
        )

    def _cluster_topic_similarity(
        self, messages: list[Message], clusters: list[list[int]]
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

                if similarity >= self.config.cluster_similarity_threshold:
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
        self, messages: list[Message], cluster: list[int]
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
                    if len(word) > self.config.minimum_word_length and not word.startswith("http"):
                        keywords.add(word)
        return keywords

    def _cluster_role_patterns(
        self, messages: list[Message], clusters: list[list[int]]
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
        self, messages: list[Message], clusters: list[list[int]], index: int
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
        self, messages: list[Message], cluster1: list[int], cluster2: list[int]
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
        self, messages: list[Message], cluster1: list[int], cluster2: list[int]
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
        return len(common_words) >= self.config.minimum_shared_words

    def _extract_cluster_content(self, messages: list[Message], cluster: list[int]) -> str:
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

    def _extract_significant_words(self, text: str) -> set[str]:
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
            if len(word) > self.config.minimum_word_length and not word.startswith("http"):
                words.add(word)
        return words

    def _merge_clusters_containing_indices(
        self, clusters: list[list[int]], indices: list[int]
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

    def _apply_adaptive_compression(
        self,
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
        conversation_type = ConversationTypeDetector.detect(messages)

        # Calculate cluster importance scores
        cluster_importance = self._calculate_cluster_importance(
            clusters, importance_scores
        )

        # Apply compression strategy based on conversation type
        if conversation_type == "coding":
            compressed_messages = self._apply_coding_compression_strategy(
                messages, clusters, cluster_importance
            )
        elif conversation_type == "research":
            compressed_messages = self._apply_research_compression_strategy(
                messages, clusters, cluster_importance
            )
        elif conversation_type == "debugging":
            compressed_messages = self._apply_debugging_compression_strategy(
                messages, clusters, cluster_importance
            )
        else:
            # Default strategy for general conversations
            compressed_messages = self._apply_general_compression_strategy(
                messages, clusters, cluster_importance
            )

        return compressed_messages

    def _detect_conversation_type(self, messages: list[Message]) -> str:
        """Detect the type of conversation based on message content.
        
        This method is kept for backward compatibility with tests.
        It delegates to ConversationTypeDetector.
        
        Args:
            messages: List of messages to analyze.

        Returns:
            Conversation type: "coding", "research", "debugging", or "general".
        """
        return ConversationTypeDetector.detect(messages)


    def _calculate_cluster_importance(
        self,
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

    def _apply_coding_compression_strategy(
        self,
        messages: list[Message],
        clusters: list[list[int]],
        cluster_importance: dict[int, float],
    ) -> list[Message]:
        """Apply compression strategy optimized for coding conversations.

        For coding conversations, preserve:
        - Tool call sequences (critical for execution flow)
        - Code snippets and function definitions
        - Error messages and stack traces
        - Recent user requirements

        Args:
            messages: Original messages.
            clusters: Message clusters.
            cluster_importance: Importance scores for each cluster.

        Returns:
            Compressed messages.
        """
        return self._apply_importance_based_compression(
            messages, clusters, cluster_importance,
            high_threshold=IntelligentContextConstants.CODING_HIGH_THRESHOLD,
            medium_threshold=IntelligentContextConstants.CODING_MEDIUM_THRESHOLD,
            preserve_tool_sequences=True,
            preserve_code_blocks=True,
        )

    def _apply_research_compression_strategy(
        self,
        messages: list[Message],
        clusters: list[list[int]],
        cluster_importance: dict[int, float],
    ) -> list[Message]:
        """Apply compression strategy optimized for research conversations.

        For research conversations, preserve:
        - Key findings and conclusions
        - Important data points and statistics
        - Source references and citations
        - Research questions and hypotheses

        Args:
            messages: Original messages.
            clusters: Message clusters.
            cluster_importance: Importance scores for each cluster.

        Returns:
            Compressed messages.
        """
        # Research conversations use the same compression strategy as general conversations
        # but with different documentation to clarify intent
        return self._apply_general_compression_strategy(
            messages, clusters, cluster_importance
        )

    def _apply_debugging_compression_strategy(
        self,
        messages: list[Message],
        clusters: list[list[int]],
        cluster_importance: dict[int, float],
    ) -> list[Message]:
        """Apply compression strategy optimized for debugging conversations.

        For debugging conversations, preserve:
        - Error messages and stack traces
        - Problem descriptions and symptoms
        - Debugging steps and attempts
        - Solutions and fixes

        Args:
            messages: Original messages.
            clusters: Message clusters.
            cluster_importance: Importance scores for each cluster.

        Returns:
            Compressed messages.
        """
        return self._apply_importance_based_compression(
            messages, clusters, cluster_importance,
            high_threshold=IntelligentContextConstants.DEBUGGING_HIGH_THRESHOLD,
            medium_threshold=IntelligentContextConstants.DEBUGGING_MEDIUM_THRESHOLD,
            preserve_tool_sequences=True,
            preserve_code_blocks=True,
        )

    def _apply_general_compression_strategy(
        self,
        messages: list[Message],
        clusters: list[list[int]],
        cluster_importance: dict[int, float],
    ) -> list[Message]:
        """Apply compression strategy for general conversations.

        Args:
            messages: Original messages.
            clusters: Message clusters.
            cluster_importance: Importance scores for each cluster.

        Returns:
            Compressed messages.
        """
        return self._apply_importance_based_compression(
            messages, clusters, cluster_importance,
            high_threshold=self.config.compression_high_threshold,
            medium_threshold=self.config.compression_medium_threshold,
            preserve_tool_sequences=True,
            preserve_code_blocks=False,
        )

    def _apply_importance_based_compression(
        self,
        messages: list[Message],
        clusters: list[list[int]],
        cluster_importance: dict[int, float],
        high_threshold: float,
        medium_threshold: float,
        preserve_tool_sequences: bool,
        preserve_code_blocks: bool,
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
            high_threshold: Threshold for high-importance clusters.
            medium_threshold: Threshold for medium-importance clusters.
            preserve_tool_sequences: Whether to preserve tool call sequences.
            preserve_code_blocks: Whether to preserve code blocks.

        Returns:
            Compressed messages.
        """
        compressed_messages = []

        for cluster_idx, cluster in enumerate(clusters):
            importance = cluster_importance.get(cluster_idx, 0.0)

            if importance >= high_threshold:
                # Preserve high-importance clusters fully
                for msg_idx in cluster:
                    if msg_idx < len(messages):
                        compressed_messages.append(messages[msg_idx])

            elif importance >= medium_threshold:
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
                if preserve_tool_sequences:
                    self._preserve_tool_sequences_in_cluster(
                        messages, cluster, compressed_messages
                    )

            else:
                # Low-importance clusters: drop or minimal preservation
                # Only preserve if they contain critical elements
                if preserve_tool_sequences:
                    self._preserve_tool_sequences_in_cluster(
                        messages, cluster, compressed_messages
                    )

                if preserve_code_blocks:
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
        if not cluster_messages:
            return None

        # Simple summarization based on message roles and content
        roles = [msg.role for msg in cluster_messages]
        content_parts = []

        for msg in cluster_messages:
            if msg.content:
                # Take first 100 chars as summary
                preview = msg.content[:100].strip()
                if len(msg.content) > 100:
                    preview += "..."
                content_parts.append(f"{msg.role}: {preview}")

        if content_parts:
            return " | ".join(content_parts)
        else:
            return f"Cluster with roles: {', '.join(set(roles))}"

    def _preserve_tool_sequences_in_cluster(
        self,
        messages: list[Message],
        cluster: list[int],
        compressed_messages: list[Message],
    ) -> None:
        """Preserve tool call sequences within a cluster.

        Args:
            messages: All messages.
            cluster: Indices of messages in the cluster.
            compressed_messages: List to append preserved messages to.
        """
        for idx in cluster:
            if idx >= len(messages):
                continue

            msg = messages[idx]
            # Check if this is part of a tool call sequence
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
            cluster: Indices of messages in the cluster.
            compressed_messages: List to append preserved messages to.
        """
        for idx in cluster:
            if idx >= len(messages):
                continue

            msg = messages[idx]
            if msg.content and ("```" in msg.content or "def " in msg.content or "class " in msg.content):
                # This message contains code, preserve it
                compressed_messages.append(msg)

    def _generate_intelligent_summary(
        self,
        messages: list[Message],
        importance_scores: dict[int, float],
        clusters: list[list[int]],
    ) -> str | None:
        """Generate intelligent summary of compressed/dropped content.

        Focuses on preserving:
        - Key decisions and conclusions
        - Important facts and data
        - Action items and next steps
        - Critical context for future turns

        Args:
            messages: Messages being summarized.
            importance_scores: Importance scores for each message.
            clusters: Detected message clusters.

        Returns:
            Concise summary string, or None if summarization not needed.
        """
        # TODO: Implement intelligent summary generation
        return None

    def _preserve_critical_context(
        self,
        messages: list[Message],
        importance_scores: dict[int, float],
    ) -> list[Message]:
        """Ensure critical context is preserved regardless of token limits.

        Critical context includes:
        - System prompts and instructions
        - Recent user queries
        - Tool call sequences
        - Important decisions and conclusions

        Args:
            messages: Messages to filter.
            importance_scores: Importance scores for each message.

        Returns:
            Messages with critical context preserved.
        """
        # TODO: Implement critical context preservation
        return messages
