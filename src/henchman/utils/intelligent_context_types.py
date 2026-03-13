"""Shared types and constants for intelligent context management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, TypeVar

from henchman.utils.tokens import TokenCounter

if TYPE_CHECKING:
    from henchman.providers.base import Message
    from henchman.utils.intelligent_context import IntelligentContextManager

V = TypeVar("V")  # Generic type variable for values


@dataclass
class PreservedContent:
    """Represents content that should be preserved during truncation.

    Attributes:
        content: The actual text content to preserve.
        tokens: The token count of the content.
        sections: The individual sections that make up the content.

    """

    content: str
    tokens: int
    sections: list[str] | None = None

    @classmethod
    def from_sections(cls: type[PreservedContent], sections: list[str]) -> PreservedContent:
        """Create PreservedContent from a list of sections.

        Args:
            sections: List of text sections to preserve.

        Returns:
            PreservedContent instance.

        """
        content = "\n\n".join(sections)
        tokens = TokenCounter.count_text(content)
        return cls(content=content, tokens=tokens, sections=sections)


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

    # Context extraction constants
    CONTEXT_WINDOW_CHARS_BEFORE: int = 200  # ~50 tokens before a section
    CONTEXT_WINDOW_CHARS_AFTER: int = 500  # ~125 tokens after a section
    CONTEXT_WINDOW_CHARS_SURROUNDING: int = 500  # For simple surrounding context extraction

    # Magic number replacements for code smell fixes
    MIN_CONTEXT_TOKENS_THRESHOLD: int = 100  # Minimum tokens needed for meaningful context
    MIN_CONTENT_TOKENS_DEFAULT: int = 10  # Default minimum content tokens for truncation
    CHAR_TO_TOKEN_ESTIMATE_MULTIPLIER: int = 5  # Rough char to token estimate multiplier
    RECENT_MESSAGES_WINDOW: int = 10  # Window for considering "recent" messages
    MIN_RECENT_MESSAGES_TO_PRESERVE: int = 5  # Minimum recent messages to preserve
    MAX_PRESERVED_INDICES: int = 15  # Maximum number of indices to preserve

    # Context window constants for line-based context extraction
    CONTEXT_LINES_BEFORE: int = 2  # Lines before a section to include in context
    CONTEXT_LINES_AFTER: int = 2  # Lines after a section to include in context
    MIN_TOKEN_LIMIT_FOR_TRUNCATION: int = 10  # Minimum token limit for truncation operations
    MAX_STRING_PREFIX_LENGTH: int = 2  # Maximum length of Python string prefixes (e.g., 'br', 'fr')
    MIN_BACKTICKS_FOR_CODE_BLOCK: int = 3  # Minimum backticks to open a code block

    # Python syntax constants
    TRIPLE_QUOTE_LENGTH: int = 3
    TRIPLE_QUOTE_MIN_LENGTH: int = 2
    MIN_THEY_VE_LENGTH: int = 4
    THEY_HEY_START: int = 3

    # Summary generation constants
    MAX_TOPICS_TO_SHOW_IN_SUMMARY: int = 3  # Maximum number of topics to show in summary
    PERCENTAGE_MULTIPLIER: float = 100.0

    # Keyword analysis categories
    ERROR_KEYWORDS: ClassVar[list[str]] = ["error", "exception", "fail", "warning", "traceback"]
    DECISION_KEYWORDS: ClassVar[list[str]] = [
        "decision",
        "conclusion",
        "recommend",
        "suggest",
        "choose",
    ]
    TOOL_KEYWORDS: ClassVar[list[str]] = ["tool", "function", "call", "execute", "run"]
    PYTHON_CODE_MARKERS: ClassVar[list[str]] = [
        "def ",
        "class ",
        "import ",
        "from ",
        "async ",
        "await ",
    ]

    # Critical keywords for preservation and analysis
    CRITICAL_KEYWORDS: ClassVar[list[str]] = [
        "error",
        "exception",
        "failed",
        "failure",
        "broken",
        "fix",
        "bug",
        "issue",
        "problem",
        "critical",
        "important",
        "note",
        "warning",
        "alert",
        "urgent",
        "decision",
        "conclusion",
        "summary",
        "result",
        "outcome",
        "todo",
        "fixme",
        "hack",
        "xxx",
        "note:",
        "recommend",
        "suggest",
        "choose",
        "traceback",
    ]

    # Technical keywords for topic extraction
    TECH_KEYWORDS: ClassVar[list[str]] = [
        "python",
        "code",
        "function",
        "class",
        "import",
        "api",
        "database",
        "server",
        "client",
        "request",
        "test",
        "debug",
        "file",
        "directory",
        "path",
        "config",
        "setting",
    ]


@dataclass
class FenceParams:
    """Parameters for code block fence parsing.

    This dataclass addresses primitive obsession code smell by grouping
    stable parameters for fence parsing.

    Attributes:
        content: The text content being parsed for fences.
        opening_count: The number of backticks in the opening fence.

    """

    content: str
    opening_count: int


@dataclass
class TruncationParams:
    """Parameters for text truncation with markers.

    This dataclass addresses primitive obsession code smell by grouping
    stable parameters for truncation logic.

    Attributes:
        content: The text content to truncate.
        marker: The truncation marker text to append.
        min_content_tokens: Minimum tokens to preserve in content.

    """

    content: str
    marker: str
    min_content_tokens: int = IntelligentContextConstants.MIN_CONTENT_TOKENS_DEFAULT

    def apply(self: TruncationParams, limit: int) -> str:
        """Apply truncation with the given limit.

        Args:
            limit: Maximum tokens allowed.

        Returns:
            Truncated content with marker.

        """
        marker_tokens = TokenCounter.count_text(self.marker)
        available_for_content = limit - marker_tokens

        if available_for_content <= 0:
            return MarkerParams(self.marker, marker_tokens).handle_overflow(limit)

        # We have some space for content
        content_limit = min(self.min_content_tokens, available_for_content)
        final_content = TokenCounter.truncate_text(self.content, content_limit)
        return final_content + self.marker


@dataclass
class MarkerParams:
    """Parameters for truncation markers.

    Attributes:
        text: The marker text.
        tokens: The token count of the marker.

    """

    text: str
    tokens: int

    def handle_overflow(self: MarkerParams, limit: int) -> str:
        """Handle case where marker doesn't fit in limit.

        Args:
            limit: Maximum tokens allowed.

        Returns:
            Truncated marker text.

        """
        if self.tokens > limit:
            return TokenCounter.truncate_text(self.text, limit)
        return self.text


@dataclass
class ContentAnalysis:
    """Analysis of content types in messages.

    Attributes:
        has_code: Whether content has code blocks.
        has_errors: Whether content has error messages.
        has_decisions: Whether content has decisions.
        has_tools: Whether content has tool calls.

    """

    has_code: bool = False
    has_errors: bool = False
    has_decisions: bool = False
    has_tools: bool = False

    def update_from_content(self: ContentAnalysis, content: str) -> None:
        """Update analysis based on content.

        Args:
            content: The text content to analyze.

        """
        lower_content = content.lower()
        if "```" in content:
            self.has_code = True

        constants = IntelligentContextConstants
        if any(kw in lower_content for kw in constants.ERROR_KEYWORDS):
            self.has_errors = True

        if any(kw in lower_content for kw in constants.DECISION_KEYWORDS):
            self.has_decisions = True

        if any(kw in lower_content for kw in constants.TOOL_KEYWORDS):
            self.has_tools = True

    def get_summary_parts(self: ContentAnalysis) -> list[str]:
        """Get summary parts based on analysis.

        Returns:
            List of summary strings.

        """
        parts: list[str] = []
        if self.has_code:
            parts.append("• Contains code blocks or technical details")
        if self.has_errors:
            parts.append("• Includes error messages or warnings")
        if self.has_decisions:
            parts.append("• Documents decisions or conclusions")
        if self.has_tools:
            parts.append("• Includes tool call sequences")
        return parts


@dataclass
class FenceResult:
    """Result of finding a closing fence for a code block.

    Attributes:
        code_end: The position where the code content ends.
        next_pos: The position after the closing fence.
        found: Whether a closing fence was found.

    """

    code_end: int
    next_pos: int
    found: bool = True

    @classmethod
    def not_found(cls: type[FenceResult], next_pos: int) -> FenceResult:
        """Create a result indicating no closing fence was found.

        Args:
            next_pos: The position to resume parsing from.

        Returns:
            FenceResult indicating failure.

        """
        return cls(code_end=-1, next_pos=next_pos, found=False)


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


@dataclass
class ResultCreationParams:
    """Parameters for creating compaction results.

    Groups common parameters used by _create_result_without_truncation
    and _create_result_with_truncation to address primitive obsession.

    Attributes:
        original_messages: Original messages before compaction.
        safe_messages: Messages after compression but before truncation.
        importance_scores: Importance scores for each message.
        clusters: Detected conversation clusters.
        original_tokens: Original token count.
        was_compacted: Whether compaction occurred.

    """

    original_messages: list[Message]
    safe_messages: list[Message]
    importance_scores: dict[int, float]
    clusters: list[list[int]]
    original_tokens: int
    was_compacted: bool

    def get_dropped_count(self: ResultCreationParams) -> int:
        """Get the number of messages dropped during compaction.

        Returns:
            Number of messages dropped (original count minus safe count).

        """
        return len(self.original_messages) - len(self.safe_messages)

    def get_compression_ratio(self: ResultCreationParams, current_tokens: int) -> float:
        """Get compression ratio based on current token count.

        Args:
            current_tokens: Current token count after compression/truncation.

        Returns:
            Compression ratio (0.0 to 1.0).

        """
        if self.original_tokens > 0:
            return (self.original_tokens - current_tokens) / self.original_tokens
        return 0.0

    def create_result_without_truncation(
        self: ResultCreationParams,
        context_manager: IntelligentContextManager,
        current_tokens: int,
    ) -> IntelligentCompactionResult:
        """Create compaction result when no truncation is needed.

        Args:
            context_manager: The intelligent context manager for generating summaries.
            current_tokens: Current token count after compression.

        Returns:
            IntelligentCompactionResult without truncation.

        """
        compression_ratio = self.get_compression_ratio(current_tokens)

        return IntelligentCompactionResult(
            messages=self.safe_messages,
            was_compacted=self.was_compacted,
            dropped_count=self.get_dropped_count(),
            summary=context_manager.summary_generator.generate_intelligent_summary(
                self.original_messages,
                self.importance_scores,
                self.clusters,
            ),
            importance_scores=self.importance_scores,
            clusters=self.clusters,
            compression_ratio=compression_ratio,
        )

    def create_result_with_truncation(
        self: ResultCreationParams,
        context_manager: IntelligentContextManager,
        protect_from_index: int,
    ) -> IntelligentCompactionResult:
        """Create compaction result when truncation is needed.

        Args:
            context_manager: The intelligent context manager for truncation.
            protect_from_index: Protected message index.

        Returns:
            IntelligentCompactionResult with truncation.

        """
        truncated_messages = context_manager.apply_intelligent_truncation(
            self.safe_messages,
            self.importance_scores,
            self.clusters,
            protect_from_index,
        )
        truncated_tokens = TokenCounter.count_messages(truncated_messages)
        final_compression_ratio = self.get_compression_ratio(truncated_tokens)

        return IntelligentCompactionResult(
            messages=truncated_messages,
            was_compacted=True,
            dropped_count=len(self.original_messages) - len(truncated_messages),
            summary=context_manager.summary_generator.generate_intelligent_summary(
                self.original_messages,
                self.importance_scores,
                self.clusters,
            ),
            importance_scores=self.importance_scores,
            clusters=self.clusters,
            compression_ratio=final_compression_ratio,
        )
