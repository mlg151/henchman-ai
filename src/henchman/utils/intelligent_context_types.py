"""Shared types and constants for intelligent context management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TypeVar

from henchman.utils.tokens import TokenCounter

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
