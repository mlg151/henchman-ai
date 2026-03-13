"""Intelligent context management system.

This module provides an intelligent context manager that reduces token usage
while preserving important context through importance scoring, clustering,
and adaptive compression techniques.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, TypeVar

from typing_extensions import Self

from henchman.providers.base import Message
from henchman.utils.compression_strategy import CompressionStrategyFactory
from henchman.utils.intelligent_context_config import (
    IntelligentContextConfig,
    IntelligentContextParams,
)
from henchman.utils.message_compactor import MessageCompactor
from henchman.utils.sorting_utils import sort_by_importance
from henchman.utils.tokens import TokenCounter

# Type variables for Self type annotations
T = TypeVar("T", bound="PreservedContent")
C = TypeVar("C", bound="IntelligentContextConfig")
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
    def from_sections(cls, sections: list[str]) -> Self:
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


@dataclass
class _ParserState:
    """Internal state for code block parsing."""

    def __init__(self: _ParserState) -> None:
        """Initialize parser state."""
        self.in_string: bool = False
        self.string_char: str | None = None
        self.triple_quote: bool = False
        self.raw_string: bool = False
        self.escape_next: bool = False
        self.backtick_count: int = 0
        self.in_comment: bool = False  # Track if we're inside a line comment

    def handle_backslash(self: _ParserState, content: str, i: int) -> bool:
        """Handle backslash character during parsing.

        Returns:
            True if the caller should skip rest of loop and increment.

        """
        content_length = len(content)
        if self.in_string and self.raw_string:
            if i + 1 < content_length and content[i + 1] in ('"', "'"):
                # In raw strings, a backslash escapes a following quote
                # but only if there's an odd number of consecutive backslashes
                bs_count = 0
                j = i
                while j >= 0 and content[j] == "\\":
                    bs_count += 1
                    j -= 1
                if bs_count % 2 == 1:
                    self.escape_next = True
                    return True  # Caller should skip the escaped quote
            return False

        if self.in_string and not self.raw_string:
            # In regular strings, backslash always escapes next character
            self.escape_next = True
            return True

        # Not in any string - backslash has no special meaning
        # (e.g., in comments, as line continuation, or in invalid code)
        return False

    def handle_string_start(self: _ParserState, content: str, i: int) -> int:
        """Handle start of a string literal.

        Returns:
            New position after handling.

        """
        char = content[i]
        content_length = len(content)
        is_raw = self._is_raw_string_prefix(content, i)

        if i + 2 < content_length and content[i + 1] == char and content[i + 2] == char:
            self.in_string = True
            self.string_char = char
            self.triple_quote = True
            self.raw_string = is_raw
            self.backtick_count = 0  # Reset when entering string
            return i + 2

        self.in_string = True
        self.string_char = char
        self.triple_quote = False
        self.raw_string = is_raw
        self.backtick_count = 0  # Reset when entering string
        return i

    def handle_string_end(self: _ParserState, content: str, i: int) -> int:
        """Handle potential end of a string literal.

        Returns:
            New position after handling.

        """
        char = content[i]
        content_length = len(content)
        if self.triple_quote:
            if i + 2 < content_length and content[i + 1] == char and content[i + 2] == char:
                self.in_string = False
                self.string_char = None
                self.triple_quote = False
                self.raw_string = False
                self.backtick_count = 0  # Reset when exiting string
                return i + 3  # Skip past all three quotes of closing delimiter
        else:
            self.in_string = False
            self.string_char = None
            self.triple_quote = False
            self.raw_string = False
            self.backtick_count = 0  # Reset when exiting string
        return i

    def handle_backticks(self: _ParserState) -> None:
        """Handle backtick during code parsing."""
        if not self.in_string:
            self.backtick_count += 1
        # If we're inside a string, ignore backticks (don't reset count)

    def _is_raw_string_prefix(self: _ParserState, content: str, i: int) -> bool:
        """Check if character at i is preceded by a raw string prefix."""
        if i <= 0:
            return False

        prefix_end = i - 1
        prefix_start = prefix_end
        while prefix_start >= 0 and content[prefix_start].lower() in ("r", "u", "b", "f"):
            prefix_start -= 1
        prefix_start += 1

        if prefix_start > prefix_end:
            return False

        prefix = content[prefix_start : prefix_end + 1].lower()

        # Check if this is a valid Python string prefix
        if not self._is_valid_raw_string_prefix(prefix):
            return False

        # Check if prefix is part of an identifier (preceded by alnum/underscore)
        # If so, it's not a string prefix
        if prefix_start > 0:
            prev_char = content[prefix_start - 1]
            if prev_char.isalnum() or prev_char == "_":
                return False
        return True

    def _is_valid_raw_string_prefix(self: _ParserState, prefix: str) -> bool:
        """Check if a prefix is a valid Python string prefix containing 'r'.

        Valid Python 3 string prefixes containing 'r':
        - 'r' (raw)
        - 'br', 'rb' (bytes raw)
        - 'fr', 'rf' (formatted raw)
        - Note: 'ur' and 'ru' are NOT valid in Python 3 (SyntaxError)

        Invalid prefixes:
        - 'rr' (duplicate r)
        - 'ur', 'ru' (invalid in Python 3 - 'u' cannot combine with 'r')
        - 'ub', 'uf', 'bu', 'fu' (u cannot combine with b or f)
        - Any prefix with duplicate letters (bb, ff, uu, etc.)
        - Any prefix longer than 2 characters
        - Any prefix with invalid characters

        Args:
            prefix: The prefix string to validate.

        Returns:
            True if valid raw string prefix, False otherwise.

        """
        # Convert to lowercase for case-insensitive comparison
        # Python string prefixes are case-insensitive: r, R, b, B, etc.
        prefix = prefix.lower()

        # Empty string is not a valid prefix
        if len(prefix) == 0:
            return False

        # Must contain 'r', length 1-2, no duplicate characters
        if (
            "r" not in prefix
            or len(prefix) > IntelligentContextConstants.MAX_STRING_PREFIX_LENGTH
            or len(set(prefix)) != len(prefix)
        ):
            return False

        # In Python 3, 'u' cannot combine with other characters (like 'r')
        if "u" in prefix:
            return len(prefix) == 1

        # Check all characters are valid string prefix characters
        valid_chars = {"r", "b", "f", "u"}
        return all(char in valid_chars for char in prefix)

    def _is_valid_string_prefix(self: _ParserState, prefix: str) -> bool:
        """Check if a prefix is a valid Python string prefix (any type).

        Valid Python 3 string prefixes:
        - Single character: 'r' (raw), 'b' (bytes), 'f' (formatted), 'u' (Unicode)
        - Two characters: 'br', 'rb' (bytes raw), 'fr', 'rf' (formatted raw)
        - Note: 'ur' and 'ru' are NOT valid in Python 3 (SyntaxError)
        - Note: 'u' cannot combine with other characters in Python 3

        Invalid prefixes:
        - Any prefix longer than 2 characters
        - Any prefix with duplicate letters (rr, bb, ff, uu)
        - Any prefix with invalid characters
        - Invalid combinations: 'fb', 'bf', 'ur', 'ru', 'ub', 'uf', 'bu', 'fu'

        Args:
            prefix: The prefix string to validate.

        Returns:
            True if valid string prefix, False otherwise.

        """
        # Convert to lowercase for case-insensitive comparison
        prefix = prefix.lower()

        # Empty string is not a valid prefix
        if len(prefix) == 0:
            return False

        # Length 1-2, no duplicate characters
        if len(prefix) > IntelligentContextConstants.MAX_STRING_PREFIX_LENGTH or len(
            set(prefix)
        ) != len(prefix):
            return False

        # In Python 3, 'u' cannot combine with other characters
        if "u" in prefix:
            return len(prefix) == 1

        # Check all characters are valid string prefix characters
        valid_chars = {"r", "b", "f", "u"}
        if not all(char in valid_chars for char in prefix):
            return False

        # Check for invalid combinations
        # Valid 2-character combinations: br, rb, fr, rf
        # Invalid: fb, bf, ur, ru, ub, uf, bu, fu (already handled by u check)
        if len(prefix) == 2:
            # Check if it's a valid combination
            valid_combinations = {"br", "rb", "fr", "rf"}
            return prefix in valid_combinations

        # Single character prefixes are all valid (r, b, f, u)
        return True

    def _handle_newline(self: _ParserState, i: int, *, was_escaped: bool) -> int:
        """Handle newline character during parsing."""
        self.in_comment = False
        # If we're in a non-triple-quoted string and encounter newline,
        # end the string (Python strings can't span lines unless triple-quoted
        # or have backslash at end of line, which we don't track)
        # However, if the newline is escaped (was_escaped = True), don't end the string
        if self.in_string and not self.triple_quote and not was_escaped:
            self.in_string = False
            self.string_char = None
            self.raw_string = False
            self.triple_quote = False
        self.backtick_count = 0
        return i

    def _is_apostrophe_in_word(self: _ParserState, text: str, i: int) -> bool:
        """Check if single quote at i is an apostrophe in a word."""
        # Check bounds first (negative indices wrap in Python)
        if i < -len(text) or i >= len(text):
            return False

        # Convert negative index to positive for simpler logic
        if i < 0:
            i = len(text) + i

        # Check if it's a quote and not at the beginning of the string
        if text[i] != "'" or i == 0:
            return False

        # Check character before quote
        if not (text[i - 1].isalnum() or text[i - 1] == "_"):
            return False

        # Check if it's a string prefix
        j = i - 1
        while j >= 0 and text[j].lower() in ("r", "u", "b", "f"):
            j -= 1

        # If we found at least one prefix character, check if it's a valid prefix
        if j < i - 1:
            # Check if prefix is part of an identifier (preceded by alnum/underscore)
            # If so, it's not a string prefix
            if j >= 0 and (text[j].isalnum() or text[j] == "_"):
                # The prefix characters are part of an identifier, not a string prefix
                # Continue to check if it's an apostrophe
                pass
            else:
                # Extract the potential prefix
                prefix_start = j + 1
                prefix = text[prefix_start:i].lower()  # Characters between j+1 and i-1
                # Check if it's a valid string prefix
                if self._is_valid_string_prefix(prefix):
                    return False  # Valid string prefix, not an apostrophe
                # Invalid prefix combination (e.g., "fb", "ar", "ur")
                # In code context, treat as string delimiter (even if invalid syntax)
                # rather than apostrophe in word
                return False

        # It's an apostrophe if next character is alphanumeric or underscore
        # BUT: for patterns like a'hello', we should NOT treat as apostrophe in word
        # because a' is not a common English contraction.
        # We require that the character before the quote is alphanumeric or underscore
        # AND the character after is a letter or underscore for it to be an apostrophe in word.
        if i + 1 >= len(text):
            return False

        # Check if character after quote is a letter or underscore
        # (underscore for cases like word'_suffix, though rare)
        if not (text[i + 1].isalpha() or text[i + 1] == "_"):
            return False

        # Additional check: Only treat as apostrophe if it looks like a common English contraction
        # Common contraction patterns: n't, 's, 'm, 'll, 're, 've, 'd
        # We need to check if the characters after the quote match these patterns
        remaining = text[i + 1 :]  # Text after the quote

        # Check for common contraction suffixes (case-insensitive)
        common_suffixes = ["t", "s", "m", "ll", "re", "ve", "d"]
        for suffix in common_suffixes:
            if remaining.lower().startswith(suffix):
                # Found a common contraction suffix
                # Also check that it's followed by a word boundary (not another letter)
                if len(remaining) > len(suffix) and remaining[len(suffix)].isalpha():
                    # More letters after the suffix - not a contraction
                    continue

                # ADDED VALIDATION: Check that character before apostrophe forms valid contraction
                # For common English contractions:
                # - 't (n't): character before should be 'n' (don't, can't, won't)
                # - 'm: character before should be 'I' (I'm) - case-insensitive
                # - 's, 'll, 're, 've, 'd: character before should form valid contraction
                # This prevents false positives like "qb'll", "z're", "p's" while allowing valid contractions
                char_before = text[i - 1].lower()
                if suffix == "t":  # n't
                    if char_before != "n":
                        continue  # Not a valid n't contraction
                elif suffix == "m":  # 'm
                    # Only valid contraction is I'm (case-insensitive)
                    if not (text[i - 1].lower() == "i" and (i == 1 or not text[i - 2].isalpha())):
                        continue
                elif suffix == "s":  # 's
                    # Valid characters before 's: vowels, t, n, r, w, h, y (it's, that's, what's, when's, where's, how's, why's)
                    valid_before_chars = "aeioutnrhwy"
                    if char_before not in valid_before_chars:
                        continue
                elif suffix == "ll":  # 'll
                    # Valid characters before 'll: vowels, t, h (I'll, you'll, he'll, she'll, it'll, we'll, they'll, that'll, what'll, who'll)
                    valid_before_chars = "aeiouyth"
                    if char_before not in valid_before_chars:
                        continue
                elif suffix == "re":  # 're
                    # Valid characters before 're: vowels, y (you're, we're, they're, there're)
                    valid_before_chars = "aeiouy"
                    if char_before not in valid_before_chars:
                        continue
                elif suffix == "ve":  # 've
                    # Valid characters before 've: vowels, d, t, y (I've, you've, we've, they've, could've, should've, would've, might've, must've, may've)
                    # Note: 'y' can be for "they've", "may've", or other words ending in 'y'
                    # We need to ensure it's not just "y've" (single letter)
                    valid_before_chars = "aeiouydt"
                    if char_before not in valid_before_chars:
                        continue
                    
                    # Special case for 'y': ensure it's not just "y've" (single letter before apostrophe)
                    if char_before == 'y':
                        # Require at least 2 characters before apostrophe to avoid accepting "y've"
                        if i < 2:
                            continue  # "y've" - single letter 'y' is not a valid word
                        # Also ensure the character before 'y' is a letter (forming a multi-letter word)
                        # This accepts "they've", "may've", "day've", etc.
                        if not text[i - 2].isalpha():
                            continue  # Not a word ending in 'y'
                elif suffix == "d":  # 'd
                    # Valid characters before 'd: vowels, t, h (I'd, you'd, he'd, she'd, it'd, we'd, they'd, that'd, what'd, who'd)
                    valid_before_chars = "aeiouyth"
                    if char_before not in valid_before_chars:
                        continue

                return True

        # Not a common English contraction pattern
        # In code context, treat as string delimiter to be safe
        return False

    def _handle_potential_string_start(self: _ParserState, text: str, i: int) -> int:
        """Handle potential start of a string literal."""
        if self._is_apostrophe_in_word(text, i):
            self.backtick_count = 0
            return i
        return self.handle_string_start(text, i)

    def _process_char(self: _ParserState, text: str, i: int, *, was_escaped: bool) -> int:
        """Process a single character during fence search.

        Returns:
            New position after handling.

        """
        char = text[i]
        if char == "\n":
            return self._handle_newline(i, was_escaped=was_escaped)

        if not self.in_string and char == "#" and not self.in_comment:
            self.in_comment = True

        if self.in_comment:
            self.backtick_count = 0
            return i

        if not self.in_string and char in ('"', "'") and not was_escaped:
            return self._handle_potential_string_start(text, i)

        if self.in_string and char == self.string_char and not was_escaped:
            return self.handle_string_end(text, i)

        if char == "`" and not was_escaped:
            self.handle_backticks()
            return i

        self.backtick_count = 0
        return i

    def _check_closing_fence(
        self: _ParserState,
        i: int,
        params: FenceParams,
    ) -> FenceResult | None:
        """Check if we've found a valid closing fence.

        Args:
            i: Current character position in text.
            params: Parameters for fence parsing.

        Returns:
            FenceResult if closing fence found, else None.

        """
        # If we're inside a string or comment, backticks are not fence markers
        # This check MUST come first to ensure backticks inside strings/comments
        # are never considered as fence markers, regardless of backtick count
        if self.in_string or self.in_comment:
            return None

        # A closing fence must have EXACTLY the same number of backticks as the opening fence
        if self.backtick_count != params.opening_count:
            return None

        text_length = len(params.content)
        is_closing = True
        if i + 1 < text_length:
            next_char = params.content[i + 1]
            if next_char.isalnum() or next_char == "_":
                is_closing = False
            elif next_char == "`":
                # If next character is also a backtick, we're in a longer
                # backtick sequence. Continue parsing to consume all backticks.
                is_closing = False

        if is_closing:
            code_end = i - (self.backtick_count - 1)
            return FenceResult(code_end=code_end, next_pos=i + 1)
        return None

    def find_closing_fence(
        self: _ParserState,
        start_pos: int,
        params: FenceParams,
    ) -> FenceResult:
        """Find closing fence for code block.

        Args:
            start_pos: Position to start searching from.
            params: Parameters for fence parsing.

        Returns:
            FenceResult object.

        """
        text_length = len(params.content)
        i = start_pos

        while i < text_length:
            was_escaped = self.escape_next
            self.escape_next = False

            # Use combined condition to address nested if code smell
            if (
                params.content[i] == "\\"
                and not was_escaped
                and self.handle_backslash(params.content, i)
            ):
                i += 1
                continue

            i = self._process_char(params.content, i, was_escaped=was_escaped)

            fence_result = self._check_closing_fence(i, params)
            if fence_result:
                return fence_result

            i += 1
        return FenceResult.not_found(i)


class ContentExtractor:
    """Extracts critical sections from content for preservation.

    Extracted from IntelligentContextManager to address Feature Envy code smells.
    """

    # Pattern constants to avoid duplication between extract_error_sections and extract_tool_sections
    _ERROR_PATTERNS = [
        # Match traceback and continue while lines are indented or look like errors
        # Use [^\n]* (greedy) instead of .*? to match rest of line without crossing newlines
        # \w* allows zero or more word chars before error type (e.g., "Error:" or "ValueError:")
        r"(Traceback \(most recent call last\):(?:\n(?:  |\t|\w*(?:Error|Exception|warning|fail(?:ed|ure)?):)[^\n]*)*)",
        r"(?<!\w)Error:.*?(?:\n|$)",
        r"(?<!\w)Exception:.*?(?:\n|$)",
        r"(?<!\w)warning:.*?(?:\n|$)",
        r"(?<!\w)fail(?:ed|ure)?:.*?(?:\n|$)",
    ]

    _TOOL_PATTERNS = [
        r"(Tool call:.*?(?:\n|$))",
        r"(Calling tool.*?(?:\n|$))",
        r"(Executing.*?(?:\n|$))",
        r"(Function:.*?(?:\n|$))",
    ]

    # Pattern registry for cleaner access
    _PATTERN_REGISTRY: ClassVar[dict[str, list[str]]] = {
        "error": _ERROR_PATTERNS,
        "tool": _TOOL_PATTERNS,
    }

    @staticmethod
    def _count_backticks(content: str, start_pos: int) -> tuple[int, int]:
        """Count consecutive backticks starting at start_pos.

        Returns:
            Tuple of (count, next_pos).

        """
        count = 0
        j = start_pos
        content_length = len(content)
        while j < content_length and content[j] == "`":
            count += 1
            j += 1
        return count, j

    @staticmethod
    def _parse_language(content: str, start_pos: int) -> tuple[str, int]:
        """Parse language specification after opening backticks.

        Returns:
            Tuple of (language, next_pos).

        """
        i = start_pos
        content_length = len(content)
        lang_start = i
        has_language = False

        while i < content_length and (content[i].isalnum() or content[i] in ("_", "-", ".")):
            i += 1
            has_language = True

        if not has_language:
            return "", start_pos

        language = content[lang_start:i].strip()

        # Note: We don't check for whitespace after language here because:
        # 1. In empty code blocks, language is immediately followed by closing fence (backtick)
        # 2. Validation happens in _extract_single_block when finding closing fence
        # 3. If language is not followed by whitespace or closing fence, it will fail
        #    to find a closing fence and return None (malformed code block)
        return language, i

    @staticmethod
    def _extract_single_block(content: str, i: int) -> tuple[str | None, int]:
        """Extract a single code block starting at i.

        Returns:
            Tuple of (extracted_block, next_i). extracted_block is None if failed.

        """
        opening_count, _ = ContentExtractor._count_backticks(content, i)
        content_length = len(content)

        if opening_count < IntelligentContextConstants.MIN_BACKTICKS_FOR_CODE_BLOCK:
            return None, i + 1

        start_pos = i
        i += opening_count
        language, i = ContentExtractor._parse_language(content, i)

        # Skip whitespace after language
        while i < content_length and content[i] in (" ", "\t", "\n", "\r"):
            i += 1

        code_start = i
        state = _ParserState()
        params = FenceParams(content=content, opening_count=opening_count)
        fence_result = state.find_closing_fence(i, params)

        if not fence_result.found:
            # No closing backticks found - malformed code block
            return None, start_pos + opening_count

        code_content = content[code_start : fence_result.code_end].rstrip()
        block = f"```{language}\n{code_content}\n```" if language else f"```\n{code_content}\n```"

        return block, fence_result.next_pos

    @staticmethod
    def extract_code_blocks(content: str) -> list[str]:
        """Extract code blocks from content.

        Args:
            content: The content to analyze.

        Returns:
            List of code blocks.

        """
        if not content:
            return []

        code_blocks = []
        i = 0
        content_length = len(content)

        while i < content_length:
            # Code blocks should be preceded by newline or at start of content
            if content[i : i + 3] == "```" and (i == 0 or content[i - 1] in ("\n", "\r")):
                block, next_i = ContentExtractor._extract_single_block(content, i)
                if block:
                    code_blocks.append(block)
                i = next_i
                continue

            i += 1

        return code_blocks

    @staticmethod
    def _extract_by_patterns(
        content: str,
        patterns: list[str],
        flags: int = re.IGNORECASE | re.DOTALL,
    ) -> list[str]:
        """Extract sections matching given patterns from content.

        Shared implementation for pattern-based extraction.

        Args:
            content: The content to analyze.
            patterns: List of regex patterns to match.
            flags: Regex flags to use (default: IGNORECASE | DOTALL).

        Returns:
            List of matched sections.

        """
        # Handle None or empty content or patterns
        if not content or not patterns:
            return []

        sections: list[str] = []
        for pattern in patterns:
            matches = re.findall(pattern, content, flags)
            for match in matches:
                if match and match.strip():
                    ContentExtractor._add_unique_match(sections, match.strip())
        return sections

    @staticmethod
    def _add_unique_match(sections: list[str], match_str: str) -> None:
        """Add match to sections if not a duplicate or substring.

        Args:
            sections: List of existing sections.
            match_str: New match to potentially add.

        """
        # Check if this match is already contained in another section
        # or contains another section
        for i, existing in enumerate(sections):
            if match_str in existing:
                # This match is a substring of an existing section
                return

            if existing in match_str:
                # An existing section is a substring of this match
                # Replace it with the larger match
                sections[i] = match_str
                return

        sections.append(match_str)

    @staticmethod
    def _extract_sections_by_type(content: str, pattern_name: str) -> list[str]:
        """Extract sections of a specific type from content.

        Args:
            content: The content to analyze.
            pattern_name: Name of the pattern set to use ("error" or "tool").

        Returns:
            List of extracted sections.

        Raises:
            ValueError: If pattern_name is not recognized.

        """
        patterns = ContentExtractor._PATTERN_REGISTRY.get(pattern_name)
        if patterns is None:
            msg = (
                f"Unknown pattern name: {pattern_name}. "
                f"Available patterns: {list(ContentExtractor._PATTERN_REGISTRY.keys())}"
            )
            raise ValueError(
                msg,
            )

        return ContentExtractor._extract_by_patterns(content, patterns)

    @staticmethod
    def extract_error_sections(content: str) -> list[str]:
        """Extract error/exception sections from content.

        Args:
            content: The content to analyze.

        Returns:
            List of error sections.
        """
        # Specific implementation for error sections
        return ContentExtractor._extract_sections_by_type(content, "error")

    @staticmethod
    def extract_tool_sections(content: str) -> list[str]:
        """Extract tool call sections from content.

        Args:
            content: The content to analyze.

        Returns:
            List of tool sections.
        """
        # Specific implementation for tool sections
        extracted = ContentExtractor._extract_sections_by_type(content, "tool")
        return list(extracted)

    @staticmethod
    def extract_keyword_sections(content: str, keywords: list[str] | None = None) -> list[str]:
        """Extract sections with important keywords.

        Args:
            content: The content to analyze.
            keywords: List of keywords to look for. If None, uses default important keywords.

        Returns:
            List of sections containing important keywords.

        """
        if keywords is None:
            keywords = ContentExtractor._get_default_keywords()

        lines = content.split("\n")
        return ContentExtractor._find_keyword_contexts(lines, keywords)

    @staticmethod
    def _get_default_keywords() -> list[str]:
        """Get the default list of important keywords.

        Returns:
            List of default keywords to search for.

        """
        return [
            "important",
            "critical",
            "note",
            "warning",
            "error",
            "exception",
            "decision",
            "conclusion",
            "summary",
            "key",
            "essential",
            "must",
            "should",
            "required",
        ]

    @staticmethod
    def _find_keyword_contexts(lines: list[str], keywords: list[str]) -> list[str]:
        """Find context around lines containing keywords.

        Args:
            lines: List of lines from the content.
            keywords: List of keywords to search for.

        Returns:
            List of context sections containing keywords.

        """
        sections = []

        for i, line in enumerate(lines):
            if ContentExtractor._line_contains_keyword(line, keywords):
                context = ContentExtractor._get_context_around_line(lines, i)
                if context:
                    sections.append(context)

        return sections

    @staticmethod
    def _line_contains_keyword(line: str, keywords: list[str]) -> bool:
        """Check if a line contains any of the given keywords.

        Args:
            line: The line to check.
            keywords: List of keywords to search for.

        Returns:
            True if the line contains any keyword, False otherwise.

        """
        if not line or not keywords:
            return False

        line_lower = line.lower()
        # Convert keywords to lowercase once for efficiency
        keyword_lower = [kw.lower() for kw in keywords]
        return any(keyword in line_lower for keyword in keyword_lower)

    @staticmethod
    def _get_context_around_line(lines: list[str], line_index: int) -> str | None:
        """Get context around a specific line.

        Args:
            lines: List of all lines.
            line_index: Index of the target line.

        Returns:
            Context string (CONTEXT_LINES_BEFORE lines before, the line,
            CONTEXT_LINES_AFTER lines after) or None if empty.

        """
        start = max(0, line_index - IntelligentContextConstants.CONTEXT_LINES_BEFORE)
        end = min(len(lines), line_index + IntelligentContextConstants.CONTEXT_LINES_AFTER + 1)
        context = "\n".join(lines[start:end])
        return context.strip() if context and context.strip() else None

    @staticmethod
    def extract_critical_sections(content: str) -> list[str]:
        """Extract critical sections from content for preservation.

        Args:
            content: The content to analyze.

        Returns:
            List of critical sections to preserve.

        """
        sections = []

        # 1. Extract code blocks
        code_blocks = ContentExtractor.extract_code_blocks(content)
        sections.extend(code_blocks)

        # 2. Extract error/exception sections
        error_sections = ContentExtractor._extract_sections_by_type(content, "error")
        sections.extend(error_sections)

        # 3. Extract tool call sections
        tool_sections = ContentExtractor._extract_sections_by_type(content, "tool")
        sections.extend(tool_sections)
        # Remove duplicates, empty sections, and sections that are substrings of other sections
        unique_sections: list[str] = []
        # Sort by length (longest first) so we check substrings correctly
        sections_sorted = sorted([s for s in sections if s and s.strip()], key=len, reverse=True)

        for section in sections_sorted:
            # Check if this section is a substring of any already included section
            is_substring = any(section in existing for existing in unique_sections)
            if not is_substring:
                unique_sections.append(section)

        return unique_sections


class ConversationTypeDetector:
    """Detects the type of conversation based on message content."""

    # Define keyword sets as class constants to eliminate duplicate method structure
    _CODING_KEYWORDS: ClassVar[list[str]] = [
        "def ",
        "class ",
        "import ",
        "function",
        "code",
        "python",
        "javascript",
        "java",
        "typescript",
        "variable",
        "loop",
        "if ",
        "else",
        "return",
        "print(",
        "console.log",
        "git",
        "commit",
        "branch",
        "merge",
        "api",
        "endpoint",
        "request",
        "response",
        "json",
        "xml",
    ]

    _RESEARCH_KEYWORDS: ClassVar[list[str]] = [
        "research",
        "study",
        "analysis",
        "analyze",
        "investigate",
        "explore",
        "find",
        "search",
        "look up",
        "information",
        "data",
        "statistics",
        "report",
        "document",
        "summary",
        "conclusion",
        "findings",
        "according to",
        "source",
        "reference",
        "citation",
        "paper",
    ]

    _DEBUGGING_KEYWORDS: ClassVar[list[str]] = [
        "error",
        "bug",
        "debug",
        "fix",
        "issue",
        "problem",
        "crash",
        "exception",
        "traceback",
        "stack trace",
        "log",
        "warning",
        "failed",
        "failure",
        "broken",
        "doesn't work",
        "not working",
        "why is",
        "how to fix",
        "troubleshoot",
        "diagnose",
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
        return " ".join(msg.content.lower() for msg in messages if msg.content)

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

    def _determine_conversation_type(
        self: ConversationTypeDetector,
        keyword_counts: dict[str, int],
    ) -> str:
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


class ImportanceSorter:
    """Utility class for sorting items by importance scores."""

    @staticmethod
    def sort_by_importance(
        item_count: int,
        importance_scores: dict[int, float],
    ) -> list[int]:
        """Sort indices by importance scores (descending).

        Args:
            item_count: Number of items to sort.
            importance_scores: Importance scores for each item.

        Returns:
            List of indices sorted by importance (descending).

        """
        return sort_by_importance(item_count, importance_scores)


class MessageSafetyEnforcer:
    """Enforces safety limits on messages to prevent context overflow."""

    def __init__(self: MessageSafetyEnforcer, safety_limit_ratio: float, max_tokens: int) -> None:
        """Initialize message safety enforcer.

        Args:
            safety_limit_ratio: Ratio of max_tokens to use as safety limit.
            max_tokens: Maximum tokens allowed in context.

        """
        self.safety_limit_ratio = safety_limit_ratio
        self.max_tokens = max_tokens
        self.limit = int(max_tokens * safety_limit_ratio)

    def enforce_safety_limits(
        self: MessageSafetyEnforcer,
        messages: list[Message],
    ) -> list[Message]:
        """Enforce limits on individual message size using tokens.

        This prevents context overflow from individual massive messages
        by truncating them to fit within the context window.

        Args:
            messages: List of messages to check.

        Returns:
            List of messages with content limits enforced.

        """
        safe_messages = []
        for msg in messages:
            safe_message = self._enforce_message_safety_limit(msg)
            safe_messages.append(safe_message)
        return safe_messages

    def _enforce_message_safety_limit(self: MessageSafetyEnforcer, message: Message) -> Message:
        """Enforce safety limit on a single message.

        Args:
            message: The message to check.

        Returns:
            Message with content truncated if necessary.

        Raises:
            TypeError: If message is None.

        """
        if message is None:
            msg = "Message cannot be None"
            raise TypeError(msg)

        # If message has no content, return it unchanged
        if message.content is None:
            return message

        if not message.content:
            return message

        if len(message.content) < self.limit:
            return message

        if TokenCounter.count_text(message.content) > self.limit:
            return self._create_truncated_message(message)
        return message

    def _create_truncated_message(self: MessageSafetyEnforcer, message: Message) -> Message:
        """Create a truncated version of a message.

        Args:
            message: The original message to truncate.

        Returns:
            New Message with truncated content.

        """
        # Handle None content case
        message_content = message.content
        if not message_content:
            return message

        truncated_content = TokenCounter.truncate_text(message_content, self.limit)
        new_content = (
            truncated_content + f"\n... (truncated by safety limit: > {self.limit} tokens)"
        )

        return Message(
            role=message.role,
            content=new_content,
            tool_calls=message.tool_calls,
            tool_call_id=message.tool_call_id,
        )


class TokenCounterWrapper:
    """Wrapper for token counting operations with message-specific logic."""

    @staticmethod
    def count_messages_tokens(messages: list[Message]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: List of messages to count tokens for.

        Returns:
            Total token count.

        """
        total_tokens = 0
        for msg in messages:
            if msg.content:
                total_tokens += TokenCounter.count_text(msg.content)
            # Add tokens for tool calls if present
            if msg.tool_calls:
                # Estimate tokens for tool calls (JSON representation)
                for tool_call in msg.tool_calls:
                    tool_call_str = f"{tool_call.name}{tool_call.arguments}"
                    total_tokens += TokenCounter.count_text(tool_call_str)
        return total_tokens


class IntelligentTruncator:
    """Helper class for intelligent truncation with semantic preservation.

    This class addresses the feature envy code smell by encapsulating
    token counting and truncation logic, reducing direct dependencies
    on TokenCounter throughout the IntelligentContextManager.
    """

    def __init__(self: IntelligentTruncator, safety_limit: int) -> None:
        """Initialize the truncator with a safety limit.

        Args:
            safety_limit: Maximum tokens allowed after truncation.

        """
        self.safety_limit = safety_limit

    def truncate_with_semantic_preservation(self: IntelligentTruncator, content: str) -> str:
        """Apply intelligent truncation with semantic preservation.

        Preserves:
        1. Code blocks (``` ... ```)
        2. Error markers and stack traces
        3. Tool call structures
        4. Important keywords (error, exception, fix, todo, etc.)
        5. Conversation markers (user questions, assistant responses)

        Args:
            content: The content to truncate intelligently.

        Returns:
            Intelligently truncated content.

        """
        if not content:
            return content

        # Check if content already fits within safety limit
        content_tokens = TokenCounter.count_text(content)
        if content_tokens <= self.safety_limit:
            return content

        # Step 1: Extract and preserve critical sections
        preserved_sections = ContentExtractor.extract_critical_sections(content)

        # Step 2: Apply appropriate truncation strategy
        if preserved_sections:
            final_content = self._truncate_with_preserved_sections(content, preserved_sections)
        else:
            marker = "\n\n[Content truncated by safety limit...]"
            params = TruncationParams(content=content, marker=marker)
            final_content = self._truncate_with_marker(params)

        # Step 3: Ensure we don't exceed the limit
        return self._ensure_safety_limit(final_content)

    def _truncate_with_preserved_sections(
        self: IntelligentTruncator,
        content: str,
        preserved_sections: list[str],
    ) -> str:
        """Truncate content when there are preserved sections.

        Args:
            content: The original content.
            preserved_sections: List of critical sections to preserve.

        Returns:
            Truncated content with preserved sections.

        """
        preserved = PreservedContent.from_sections(preserved_sections)

        if preserved.tokens <= self.safety_limit:
            return self._truncate_with_available_capacity(content, preserved)
        marker = "\n\n[Critical content partially truncated...]"
        params = TruncationParams(content=preserved.content, marker=marker)
        return self._truncate_with_marker(params)

    def _truncate_with_available_capacity(
        self: IntelligentTruncator,
        content: str,
        preserved: PreservedContent,
    ) -> str:
        """Truncate when preserved sections fit within safety limit.

        Args:
            content: The original content.
            preserved: Preserved content with token count.

        Returns:
            Truncated content.

        """
        remaining_limit = self.safety_limit - preserved.tokens

        if (
            remaining_limit > IntelligentContextConstants.MIN_CONTEXT_TOKENS_THRESHOLD
        ):  # Enough for some context
            return self._add_context_with_truncation(content, preserved, remaining_limit)
        return self._add_minimal_truncation_marker(preserved.content, preserved.tokens)

    def _add_context_with_truncation(
        self: IntelligentTruncator,
        content: str,
        preserved: PreservedContent,
        remaining_limit: int,
    ) -> str:
        """Add context around preserved sections with truncation marker.

        Args:
            content: The original content.
            preserved: Preserved content with token count.
            remaining_limit: Remaining token capacity.

        Returns:
            Contextual content with truncation marker.

        """
        contextual_content = self._extract_context_around_sections(
            content,
            preserved.sections or [],
            remaining_limit,
        )
        marker = "\n\n[Additional context truncated...]"
        marker_tokens = TokenCounter.count_text(marker)

        # Handle case where marker doesn't fit in remaining limit
        if marker_tokens >= remaining_limit:
            # Marker alone exceeds or equals remaining limit
            # Return just the marker (truncated to fit if necessary)
            if marker_tokens > remaining_limit:
                # Marker doesn't fit, truncate it
                return TokenCounter.truncate_text(marker, remaining_limit)
            # Marker fits exactly
            return marker

        # Calculate how much content we can preserve
        # We have remaining_limit total tokens, need marker_tokens for marker
        # So we have remaining_limit - marker_tokens tokens available for content
        available_for_content = remaining_limit - marker_tokens

        # Use min_content_tokens, but don't exceed available_for_content
        min_content_tokens = IntelligentContextConstants.MIN_TOKEN_LIMIT_FOR_TRUNCATION
        context_limit = min(min_content_tokens, available_for_content)

        if (
            len(contextual_content)
            > context_limit * IntelligentContextConstants.CHAR_TO_TOKEN_ESTIMATE_MULTIPLIER
        ):  # Rough char estimate
            contextual_content = TokenCounter.truncate_text(contextual_content, context_limit)

        return contextual_content + marker

    def _add_minimal_truncation_marker(
        self: IntelligentTruncator,
        preserved_content: str,
        preserved_tokens: int,
    ) -> str:
        """Add minimal truncation marker when little capacity remains.

        Args:
            preserved_content: Concatenated preserved sections.
            preserved_tokens: Token count of preserved content.

        Returns:
            Preserved content with truncation marker.

        """
        marker = "\n\n[Non-critical content truncated...]"
        marker_tokens = TokenCounter.count_text(marker)

        # Handle case where marker doesn't fit in safety limit
        if marker_tokens >= self.safety_limit:
            # Marker alone exceeds or equals safety limit
            # Return just the marker (truncated to fit if necessary)
            params = TruncationParams(content="", marker=marker)
            return self._truncate_with_marker(params)

        # Calculate how much content we can preserve
        # We have safety_limit total tokens, need marker_tokens for marker
        # So we have safety_limit - marker_tokens tokens available for content
        available_for_content = self.safety_limit - marker_tokens

        # Preserve as much of the preserved content as fits
        preserved_limit = available_for_content

        # Truncate preserved content if it exceeds the limit
        if preserved_tokens > preserved_limit:
            preserved_content = TokenCounter.truncate_text(preserved_content, preserved_limit)

        return preserved_content + marker

    def _truncate_with_marker(
        self: IntelligentTruncator,
        params: TruncationParams,
    ) -> str:
        """Consolidated truncation logic with marker.

        Args:
            params: Parameters for truncation.

        Returns:
            Truncated content with marker, guaranteed not to exceed safety_limit.

        """
        marker_tokens = TokenCounter.count_text(params.marker)

        # Calculate how many tokens we have available for content
        # after reserving space for the marker
        available_for_content = self.safety_limit - marker_tokens

        if available_for_content <= 0:
            # Marker alone exceeds or equals safety limit
            # Return just the marker (truncated to fit if necessary)
            if marker_tokens > self.safety_limit:
                # Marker doesn't fit, truncate it
                return TokenCounter.truncate_text(params.marker, self.safety_limit)
            # Marker fits exactly
            return params.marker

        # We have some space for content
        # Use min_content_tokens, but don't exceed available_for_content
        limit = min(params.min_content_tokens, available_for_content)

        final_content = TokenCounter.truncate_text(params.content, limit)
        return final_content + params.marker

    def _ensure_safety_limit(self: IntelligentTruncator, content: str) -> str:
        """Ensure content doesn't exceed safety limit.

        Args:
            content: The content to check.

        Returns:
            Content truncated to safety limit if necessary.

        """
        final_content_tokens = TokenCounter.count_text(content)
        if final_content_tokens > self.safety_limit:
            # This shouldn't happen, but as a safety fallback, truncate
            return TokenCounter.truncate_text(content, self.safety_limit)
        return content

    @staticmethod
    def _extract_context_around_sections(
        content: str,
        sections: list[str],
        token_limit: int,
    ) -> str:
        """Extract context around critical sections.

        Args:
            content: The original content.
            sections: List of critical sections.
            token_limit: Maximum tokens for context.

        Returns:
            Contextual content around critical sections.

        """
        # Simplified implementation - just return some context
        # In real implementation, this would extract text around each section
        if not sections:
            return ""

        # Find positions of first and last sections
        first_section = sections[0]
        last_section = sections[-1]

        start_pos = content.find(first_section)
        end_pos = content.find(last_section) + len(last_section)

        if start_pos == -1 or end_pos == -1:
            return ""

        # Extract context (simplified - just take surrounding text)
        context_start = max(
            0,
            start_pos - IntelligentContextConstants.CONTEXT_WINDOW_CHARS_SURROUNDING,
        )
        context_end = min(
            len(content),
            end_pos + IntelligentContextConstants.CONTEXT_WINDOW_CHARS_SURROUNDING,
        )
        contextual_content = content[context_start:context_end]

        # Truncate to token limit
        return TokenCounter.truncate_text(contextual_content, token_limit)


class _ToolSequenceValidator:
    """Helper class to validate tool call sequences.

    This class addresses the feature envy code smell by encapsulating
    the validation logic and state management.
    """

    def __init__(self: _ToolSequenceValidator, messages: list[Message]) -> None:
        """Initialize validator with messages to check.

        Args:
            messages: The messages to validate.

        """
        self.messages = messages
        self.pending_tool_calls: set[str] = set()
        self.current_assistant_index: int | None = None

    def validate(self: _ToolSequenceValidator) -> bool:
        """Validate the entire message sequence.

        Returns:
            True if tool sequences are valid, False otherwise.

        """
        for i, msg in enumerate(self.messages):
            if not self._process_message(i, msg):
                return False

        # At the end, check if all tool calls were responded to
        return not self.pending_tool_calls

    def _process_message(self: _ToolSequenceValidator, index: int, msg: Message) -> bool:
        """Process a single message in the sequence.

        Args:
            index: Message index in the sequence.
            msg: The message to process.

        Returns:
            True if message is valid, False otherwise.

        """
        if msg.role == "tool":
            return self._process_tool_message(index, msg)

        if msg.role == "assistant":
            return self._process_assistant_message(index, msg)

        # User and system messages don't affect tool sequence validation
        return True

    def _process_tool_message(self: _ToolSequenceValidator, index: int, msg: Message) -> bool:
        """Process a tool message.

        Args:
            index: Message index.
            msg: Tool message to process.

        Returns:
            True if tool message is valid, False otherwise.

        """
        # Tool messages must not be first
        if index == 0:
            return False

        # Tool must follow an assistant with pending tool calls
        if self.current_assistant_index is None:
            return False

        # Check if tool_call_id matches a pending tool call
        if msg.tool_call_id not in self.pending_tool_calls:
            return False

        # Remove this tool call from pending set
        self.pending_tool_calls.discard(msg.tool_call_id)

        # If all tool calls are responded to, reset for next assistant
        if not self.pending_tool_calls:
            self.current_assistant_index = None

        return True

    def _process_assistant_message(self: _ToolSequenceValidator, index: int, msg: Message) -> bool:
        """Process an assistant message.

        Args:
            index: Message index.
            msg: Assistant message to process.

        Returns:
            True if assistant message is valid, False otherwise.

        """
        if msg.tool_calls:
            return self._process_assistant_with_tools(index, msg)

        return self._process_assistant_without_tools()

    def _process_assistant_with_tools(
        self: _ToolSequenceValidator,
        index: int,
        msg: Message,
    ) -> bool:
        """Process an assistant message with tool calls.

        Args:
            index: Message index.
            msg: Assistant message with tool calls.

        Returns:
            True if assistant message with tools is valid, False otherwise.

        """
        # Check if this is a duplicate of the current assistant message
        is_duplicate = self._check_if_duplicate_assistant(msg)

        # If we encounter a new assistant with tool calls while we still have
        # pending tool calls from previous assistant, that's invalid unless it's a duplicate
        if self.pending_tool_calls and not is_duplicate:
            return False

        # Start tracking new set of tool calls (or continue tracking same set for duplicate)
        if not is_duplicate and msg.tool_calls:
            self.pending_tool_calls = {tc.id for tc in msg.tool_calls}
            self.current_assistant_index = index

        return True

    def _process_assistant_without_tools(self: _ToolSequenceValidator) -> bool:
        """Process an assistant message without tool calls.

        Returns:
            True if assistant message without tools is valid, False otherwise.

        """
        # Regular assistant message - if we have pending tool calls, that's invalid
        return not self.pending_tool_calls

    def _check_if_duplicate_assistant(
        self: _ToolSequenceValidator,
        msg: Message,
    ) -> bool:
        """Check if assistant message is a duplicate of current assistant.

        Args:
            msg: Assistant message to check.

        Returns:
            True if message is a duplicate, False otherwise.

        """
        if self.current_assistant_index is None or not self.pending_tool_calls:
            return False

        prev_msg = self.messages[self.current_assistant_index]
        return SequenceValidator._is_duplicate_assistant_message(
            msg,
            prev_msg,
            self.current_assistant_index,
        )


class SequenceValidator:
    """Validates message sequences follow API rules and semantic constraints."""

    @classmethod
    def validate_compacted_sequence(cls: type[SequenceValidator], messages: list[Message]) -> bool:
        """Validate that a message sequence follows OpenAI API rules with semantic checks.

        Enhanced validation includes:
        - Structural API compliance (tool call sequences, role ordering)
        - Semantic consistency (related content, logical flow)
        - Context preservation (critical information not lost)

        Args:
            messages: The messages to validate.

        Returns:
            True if the sequence is valid, False otherwise.

        """
        if not messages:
            return True

        # 0. Validate roles are valid (lowercase)
        if not cls._validate_role_names(messages):
            return False

        # 1. Structural validation
        if not cls._validate_tool_sequences(messages):
            return False

        # 2. Semantic validation - check for logical conversation flow
        if not cls._validate_conversation_flow(messages):
            return False

        # 3. Context preservation check
        if not cls._validate_system_prompt(messages):
            return False

        # 4. Check for duplicate consecutive messages (compression artifact)
        return cls._validate_no_duplicate_consecutive_messages(messages)

    @staticmethod
    def _validate_tool_sequences(messages: list[Message]) -> bool:
        """Validate tool call sequences follow OpenAI API rules.

        Rules:
        - Tool messages must not be first
        - Tool messages must follow assistant messages with tool_calls
        - Tool message tool_call_id must match a tool call ID from preceding assistant
        - All tool calls from an assistant must have corresponding tool responses
          before another assistant message appears (unless it's a duplicate message)

        Args:
            messages: The messages to validate.

        Returns:
            True if tool sequences are valid, False otherwise.

        """
        validator = _ToolSequenceValidator(messages)
        return validator.validate()

    @staticmethod
    def _is_duplicate_assistant_message(
        current_msg: Message,
        prev_msg: Message,
        prev_msg_index: int | None,
    ) -> bool:
        """Check if current assistant message is a duplicate of previous.

        Args:
            current_msg: Current assistant message.
            prev_msg: Previous assistant message.
            prev_msg_index: Index of previous assistant message.

        Returns:
            True if messages are duplicates, False otherwise.

        """
        if prev_msg_index is None:
            return False

        # Check content and tool calls match
        if current_msg.content != prev_msg.content:
            return False

        # Check tool calls match
        if not current_msg.tool_calls or not prev_msg.tool_calls:
            return False

        current_ids = {tc.id for tc in current_msg.tool_calls}
        prev_ids = {tc.id for tc in prev_msg.tool_calls}
        return current_ids == prev_ids

    @staticmethod
    def _validate_conversation_flow(messages: list[Message]) -> bool:
        """Validate logical conversation flow.

        Rules:
        - Assistant messages should generally follow user or tool messages
        - Exceptions:
          * Assistant continuing after tool calls (previous assistant had tool_calls)
          * First message after system prompt (i == 1 and messages[0].role == "system")

        Args:
            messages: The messages to validate.

        Returns:
            True if conversation flow is valid, False otherwise.

        """
        for i in range(1, len(messages)):
            curr = messages[i]
            prev = messages[i - 1]

            # Assistant should generally follow user or tool messages
            if curr.role == "assistant" and prev.role not in ["user", "tool"]:
                # Unless it's a continuation of a multi-turn assistant response
                # (check if previous assistant had tool calls that are now complete)
                if prev.role == "assistant" and prev.tool_calls:
                    # This is fine - assistant continuing after tool calls
                    continue
                # Also fine if it's the first message (system prompt scenario)
                if i == 1 and messages[0].role == "system":
                    continue
                return False
        return True

    @staticmethod
    def _validate_system_prompt(messages: list[Message]) -> bool:
        """Validate system prompt is preserved and not corrupted.

        Rules:
        - If first message is system role, it must have non-empty content

        Args:
            messages: The messages to validate.

        Returns:
            True if system prompt is valid, False otherwise.

        """
        return not (
            messages
            and messages[0].role == "system"
            and (not messages[0].content or len(messages[0].content.strip()) == 0)
        )

    @staticmethod
    def _validate_role_names(messages: list[Message]) -> bool:
        """Validate that message roles are valid OpenAI API roles (lowercase).

        Valid roles are: "system", "user", "assistant", "tool"

        Args:
            messages: The messages to validate.

        Returns:
            True if all roles are valid, False otherwise.

        """
        valid_roles = {"system", "user", "assistant", "tool"}
        return all(msg.role in valid_roles for msg in messages)

    @staticmethod
    def _validate_no_duplicate_consecutive_messages(messages: list[Message]) -> bool:
        """Check for duplicate consecutive messages (compression artifact).

        Rules:
        - Consecutive messages with same role and identical content are invalid
        - Exception: Messages with tool_calls are allowed (tool call sequences)

        Args:
            messages: The messages to validate.

        Returns:
            True if no duplicate consecutive messages, False otherwise.

        """
        for i in range(1, len(messages)):
            curr = messages[i]
            prev = messages[i - 1]
            if (
                curr.role == prev.role
                and curr.content
                and prev.content
                and curr.content.strip() == prev.content.strip()
                and not curr.tool_calls
                and not prev.tool_calls
            ):
                return False
        return True


class MessagePreserver:
    """Preserves critical messages during context compaction.

    Responsible for ensuring important context is not lost during
    compression operations.
    """

    def __init__(self: MessagePreserver, config: IntelligentContextConfig) -> None:
        """Initialize message preserver.

        Args:
            config: Configuration for preservation logic.

        """
        self.config = config

    def preserve_critical_context(
        self: MessagePreserver,
        messages: list[Message],
        importance_scores: dict[int, float],
    ) -> list[Message]:
        """Ensure critical context is preserved regardless of token limits.

        Critical context includes:
        - System prompts and initial instructions
        - Recent user queries and assistant responses
        - Tool call sequences (assistant with tool_calls -> tool responses)
        - Error messages and debug information
        - Decisions and conclusions
        - Code blocks and structured data

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.

        Returns:
            Messages with critical context preserved.

        """
        if not messages:
            return []

        preserved_messages: list[Message] = []

        # Track which messages we've preserved
        preserved_indices: set[int] = set()

        # Phase 1: Always preserve system messages (highest priority)
        self._preserve_system_messages(messages, preserved_messages, preserved_indices)

        # Phase 2: Preserve recent high-importance messages
        self._preserve_recent_high_importance_messages(
            messages,
            importance_scores,
            preserved_messages,
            preserved_indices,
        )

        # Phase 3: Preserve tool call sequences
        self._preserve_tool_call_sequences(messages, preserved_messages, preserved_indices)

        # Phase 4: Preserve messages with critical content
        self._preserve_critical_content_messages(messages, preserved_messages, preserved_indices)

        # Phase 5: Ensure we preserve at least some conversation flow
        self._preserve_conversation_flow(messages, preserved_messages, preserved_indices)

        # Sort preserved messages back to original order
        preserved_messages.sort(key=lambda msg: messages.index(msg) if msg in messages else -1)

        return preserved_messages

    def _preserve_system_messages(
        self: MessagePreserver,
        messages: list[Message],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve all system messages.

        Args:
            messages: Original messages.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        for i, msg in enumerate(messages):
            if msg.role == "system":
                preserved_messages.append(msg)
                preserved_indices.add(i)

    def _preserve_recent_high_importance_messages(
        self: MessagePreserver,
        messages: list[Message],
        importance_scores: dict[int, float],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve recent messages with high importance scores.

        Args:
            messages: Original messages.
            importance_scores: Importance scores for each message.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        # Start from the end (most recent) and work backwards
        for i in range(len(messages) - 1, -1, -1):
            if i in preserved_indices:
                continue

            importance = importance_scores.get(i, 0.0)
            if importance >= self.config.importance_threshold:
                preserved_messages.append(messages[i])
                preserved_indices.add(i)

                # Limit to reasonable number of recent high-importance messages
                recent_count = sum(
                    1
                    for idx in preserved_indices
                    if idx >= len(messages) - IntelligentContextConstants.RECENT_MESSAGES_WINDOW
                )
                if recent_count >= IntelligentContextConstants.MIN_RECENT_MESSAGES_TO_PRESERVE:
                    break

    def _preserve_tool_call_sequences(
        self: MessagePreserver,
        messages: list[Message],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve complete tool call sequences.

        Args:
            messages: Original messages.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        for i in range(len(messages) - 1):
            if i in preserved_indices or (i + 1) in preserved_indices:
                continue

            curr_msg = messages[i]
            next_msg = messages[i + 1]

            if (
                curr_msg.role == "assistant"
                and curr_msg.tool_calls
                and next_msg.role == "tool"
                and next_msg.tool_call_id
            ):
                # Verify tool_call_id matches
                tool_call_ids = {tc.id for tc in curr_msg.tool_calls}
                if next_msg.tool_call_id in tool_call_ids:
                    preserved_messages.append(curr_msg)
                    preserved_messages.append(next_msg)
                    preserved_indices.add(i)
                    preserved_indices.add(i + 1)

    def _preserve_critical_content_messages(
        self: MessagePreserver,
        messages: list[Message],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Preserve messages with critical content (errors, decisions, code blocks).

        Args:
            messages: Original messages.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        critical_keywords = IntelligentContextConstants.CRITICAL_KEYWORDS

        for i, msg in enumerate(messages):
            if i in preserved_indices:
                continue

            if not msg.content:
                continue

            # Check for critical keywords
            content_lower = msg.content.lower()
            if (
                any(keyword in content_lower for keyword in critical_keywords)
                or "```" in msg.content
            ):
                preserved_messages.append(msg)
                preserved_indices.add(i)

    def _preserve_conversation_flow(
        self: MessagePreserver,
        messages: list[Message],
        preserved_messages: list[Message],
        preserved_indices: set[int],
    ) -> None:
        """Ensure we preserve at least some conversation flow.

        Try to preserve alternating user-assistant pairs.

        Args:
            messages: Original messages.
            preserved_messages: List to add preserved messages to.
            preserved_indices: Set of indices already preserved.

        """
        for i, msg in enumerate(messages):
            if i in preserved_indices:
                continue

            if msg.role in ["user", "assistant"]:
                # Try to preserve pairs
                preserved_messages.append(msg)
                preserved_indices.add(i)

                # Limit to reasonable number
                if len(preserved_indices) >= min(
                    IntelligentContextConstants.MAX_PRESERVED_INDICES,
                    len(messages),
                ):
                    break


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
        truncated_messages = context_manager._apply_intelligent_truncation(
            self.safe_messages,
            self.importance_scores,
            self.clusters,
            protect_from_index,
        )
        truncated_tokens = context_manager._count_tokens(truncated_messages)
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
        low_importance_messages = []
        for i, msg in enumerate(messages):
            if i in importance_scores and importance_scores[i] < self.config.importance_threshold:
                low_importance_messages.append((i, msg, importance_scores[i]))
        return low_importance_messages

    def _analyze_dropped_content(
        self: SummaryGenerator,
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

        # Define keyword groups based on constants
        error_keywords = ["error", "exception", "fail", "warning", "traceback"]
        decision_keywords = ["decision", "conclusion", "recommend", "suggest", "choose"]
        tool_keywords = ["tool", "function", "call", "execute", "run"]

        for _, msg, _ in low_importance_messages:
            if not msg.content:
                continue

            content = msg.content.lower()

            # Check for code blocks
            if "```" in content:
                analysis["has_code"] = True

            # Check for error/exception keywords
            if any(keyword in content for keyword in error_keywords):
                analysis["has_errors"] = True

            # Check for decision keywords
            if any(keyword in content for keyword in decision_keywords):
                analysis["has_decisions"] = True

            # Check for tool-related content
            if any(keyword in content for keyword in tool_keywords):
                analysis["has_tools"] = True

        return analysis

    def _build_summary_parts(
        self: SummaryGenerator,
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
        summary_parts: list[str] = []

        # Add overview
        self._add_overview_part(summary_parts, messages, low_importance_messages)

        # Add content type analysis
        self._add_content_analysis_parts(summary_parts, content_analysis)

        # Add topic summary if we can identify clusters
        self._add_cluster_topics_part(summary_parts, messages, clusters)

        # Add preservation note
        summary_parts.append(
            "Critical context (system prompts, recent messages, errors, tool sequences) "
            "will be preserved.",
        )

        return summary_parts

    def _add_overview_part(
        self: SummaryGenerator,
        summary_parts: list[str],
        messages: list[Message],
        low_importance_messages: list[tuple[int, Message, float]],
    ) -> None:
        """Add overview part to summary.

        Args:
            summary_parts: List to add to.
            messages: Original messages.
            low_importance_messages: Low importance messages.

        """
        total_messages = len(messages)
        low_importance_count = len(low_importance_messages)

        # Handle edge case where total_messages is 0 to avoid division by zero
        if total_messages == 0:
            percentage = 0.0
        else:
            percentage = (low_importance_count / total_messages) * 100

        summary_parts.append(
            f"Context compaction may affect {low_importance_count}/{total_messages} "
            f"messages ({percentage:.1f}%) with importance below "
            f"{self.config.importance_threshold:.2f}.",
        )

    def _add_content_analysis_parts(
        self: SummaryGenerator,
        summary_parts: list[str],
        content_analysis: dict[str, bool],
    ) -> None:
        """Add content analysis parts to summary.

        Args:
            summary_parts: List to add to.
            content_analysis: Analysis of content types.

        """
        if content_analysis["has_code"]:
            summary_parts.append("• Contains code blocks or technical details")
        if content_analysis["has_errors"]:
            summary_parts.append("• Includes error messages or warnings")
        if content_analysis["has_decisions"]:
            summary_parts.append("• Documents decisions or conclusions")
        if content_analysis["has_tools"]:
            summary_parts.append("• Includes tool call sequences")

    def _add_cluster_topics_part(
        self: SummaryGenerator,
        summary_parts: list[str],
        messages: list[Message],
        clusters: list[list[int]] | None,
    ) -> None:
        """Add cluster topics part to summary.

        Args:
            summary_parts: List to add to.
            messages: Original messages.
            clusters: Detected message clusters.

        """
        if clusters and len(clusters) > 1:
            cluster_topics = self._extract_cluster_topics(messages, clusters)
            if cluster_topics:
                summary_parts.append(
                    "• Topics discussed: "
                    + ", ".join(
                        cluster_topics[: IntelligentContextConstants.MAX_TOPICS_TO_SHOW_IN_SUMMARY],
                    ),
                )

    def _extract_cluster_topics(
        self: SummaryGenerator,
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
            cluster_topics = self._extract_topics_from_cluster(messages, cluster)
            topics.update(cluster_topics)

        return sorted(topics)

    def _extract_topics_from_cluster(
        self: SummaryGenerator,
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
        combined_content = self._extract_combined_cluster_content(messages, cluster)

        if not combined_content:
            return topics

        # Look for technical keywords
        self._add_technical_keywords(combined_content, topics)

        # Look for code language markers
        self._add_code_markers(combined_content, topics)

        return topics

    def _extract_combined_cluster_content(
        self: SummaryGenerator,
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
        cluster_content = []
        for msg_idx in cluster:
            if msg_idx < len(messages) and messages[msg_idx].content:
                cluster_content.append(messages[msg_idx].content)

        if not cluster_content:
            return ""

        # Filter out None values
        filtered_content = [c for c in cluster_content if c is not None]
        if not filtered_content:
            return ""

        return " ".join(filtered_content).lower()

    def _add_technical_keywords(
        self: SummaryGenerator,
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

    def _add_code_markers(
        self: SummaryGenerator,
        content: str,
        topics: set[str],
    ) -> None:
        """Add code language markers found in content to topics set.

        Args:
            content: Content to search.
            topics: Set to add topics to.

        """
        code_markers = ["def ", "class ", "import ", "from ", "async ", "await "]
        for marker in code_markers:
            if marker in content:
                topics.add("python code")
                break


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
        by truncating them intelligently to preserve:
        - Code blocks and structured content
        - Error messages and stack traces
        - Tool call sequences
        - Important keywords and decision points
        - Conversation flow markers

        Args:
            messages: List of messages to check.

        Returns:
            List of messages with content limits enforced intelligently.

        """
        if not messages:
            return []

        safe_messages = []
        for msg in messages:
            if self._needs_safety_limit(msg):
                safe_message = self._apply_intelligent_truncation_with_semantic_preservation(msg)
                safe_messages.append(safe_message)
            else:
                safe_messages.append(msg)

        return safe_messages

    def _needs_safety_limit(self: IntelligentContextManager, message: Message) -> bool:
        """Check if a message needs safety limit enforcement.

        Args:
            message: The message to check.

        Returns:
            True if message exceeds safety limit, False otherwise.

        """
        if not message.content:
            return False

        token_count = TokenCounter.count_text(message.content)
        safety_limit = int(self.config.max_tokens * self.config.safety_limit_ratio)

        return token_count > safety_limit

    def _apply_intelligent_truncation_with_semantic_preservation(
        self: IntelligentContextManager,
        message: Message,
    ) -> Message:
        """Apply intelligent truncation with semantic preservation.

        Preserves:
        1. Code blocks (``` ... ```)
        2. Error markers and stack traces
        3. Tool call structures
        4. Important keywords (error, exception, fix, todo, etc.)
        5. Conversation markers (user questions, assistant responses)

        Args:
            message: The message to truncate intelligently.

        Returns:
            Intelligently truncated message.

        """
        if not message.content:
            return message

        safety_limit = int(self.config.max_tokens * self.config.safety_limit_ratio)

        # Use IntelligentTruncator to address feature envy code smell
        truncator = IntelligentTruncator(safety_limit)
        final_content = truncator.truncate_with_semantic_preservation(message.content)

        return Message(
            role=message.role,
            content=final_content,
            tool_calls=message.tool_calls,
            tool_call_id=message.tool_call_id,
        )

    def _count_tokens(self: IntelligentContextManager, messages: list[Message]) -> int:
        """Count total tokens in a list of messages.

        Args:
            messages: List of messages to count tokens for.

        Returns:
            Total token count.

        """
        return TokenCounterWrapper.count_messages_tokens(messages)

    def _apply_intelligent_truncation(
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

        # Check if truncation is needed
        original_tokens = self._count_tokens(messages)
        current_tokens = self._count_tokens(safe_messages)
        was_compacted = self._detect_compaction(
            messages,
            safe_messages,
            original_tokens,
            current_tokens,
        )

        # Handle based on token limit
        if current_tokens <= self.config.max_tokens:
            params = ResultCreationParams(
                original_messages=messages,
                safe_messages=safe_messages,
                importance_scores=importance_scores,
                clusters=clusters,
                original_tokens=original_tokens,
                was_compacted=was_compacted,
            )
            return params.create_result_without_truncation(self, current_tokens)

        # Need truncation
        params = ResultCreationParams(
            original_messages=messages,
            safe_messages=safe_messages,
            importance_scores=importance_scores,
            clusters=clusters,
            original_tokens=original_tokens,
            was_compacted=was_compacted,
        )
        return params.create_result_with_truncation(self, protect_from_index)

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
        cluster_importance = self.message_compactor._calculate_cluster_importance(
            clusters,
            importance_scores,
        )

        # Apply compression strategy based on conversation type
        strategy = CompressionStrategyFactory.create_for_conversation_type(conversation_type)
        return strategy.compress(messages, clusters, cluster_importance)
