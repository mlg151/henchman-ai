"""Internal parser state and apostrophe detection for code block extraction."""

from __future__ import annotations

from dataclasses import dataclass

from henchman.utils.intelligent_context_types import (
    FenceParams,
    FenceResult,
    IntelligentContextConstants,
)


@dataclass
class _StringState:
    """Parameters for string state management."""

    char: str
    is_raw: bool
    triple: bool


@dataclass
class _ContractionParams:
    """Parameters for contraction validation."""

    suffix: str
    char_before: str
    remaining: str
    text: str
    i: int

    def val_single(self: _ContractionParams) -> bool:
        """Validate single character contraction suffixes."""
        if len(self.remaining) > len(self.suffix) and self.remaining[len(self.suffix)].isalpha():
            return False

        if self.suffix == "t":  # n't
            return self.char_before == "n"
        if self.suffix == "m":  # I'm
            return self.char_before == "i" and (
                self.i == 1 or not self.text[self.i - 2].isalpha()
            )
        if self.suffix == "s":
            return self.char_before in "aeioutnrhwy"
        if self.suffix == "d":
            return self.char_before in "aeiouyth"
        return False

    def val_multi(self: _ContractionParams) -> bool:
        """Validate multi-character contraction suffixes."""
        if len(self.remaining) > len(self.suffix) and self.remaining[len(self.suffix)].isalpha():
            return False

        if self.suffix == "ll":
            return self.char_before in "aeiouyth"
        if self.suffix == "re":
            return self.char_before in "aeiouy"
        if self.suffix == "ve":
            return self._val_ve()
        return False

    def _val_ve(self: _ContractionParams) -> bool:
        if self.char_before in "aeioudt":
            return True
        if self.char_before == "y":
            min_len = IntelligentContextConstants.MIN_THEY_VE_LENGTH
            hey_start = IntelligentContextConstants.THEY_HEY_START
            if self.i >= min_len and self.text[self.i - hey_start : self.i].lower() == "hey":
                return True
            may_len = IntelligentContextConstants.TRIPLE_QUOTE_LENGTH
            return self.i >= may_len and self.text[self.i - may_len : self.i].lower() == "may"
        return False


class _ApostropheDetector:
    """Specialized logic for detecting apostrophes in English contractions."""

    @staticmethod
    def is_apostrophe_in_word(state: _ParserState, text: str, i: int) -> bool:
        """Check if single quote at i is an apostrophe in a word."""
        if not _ApostropheDetector._is_basic_candidate(text, i):
            return False

        idx = i if i >= 0 else len(text) + i

        if state.is_string_prefix_at(text, idx):
            return False

        if idx + 1 >= len(text):
            return False

        if not (text[idx + 1].isalpha() or text[idx + 1] == "_"):
            return False

        return _ApostropheDetector._is_known_contraction(text, idx)

    @staticmethod
    def _is_basic_candidate(text: str, i: int) -> bool:
        """Quick check if character at i could be an apostrophe."""
        if i < -len(text) or i >= len(text):
            return False

        idx = i if i >= 0 else len(text) + i
        if text[idx] != "'" or idx == 0:
            return False

        return text[idx - 1].isalnum() or text[idx - 1] == "_"

    @staticmethod
    def _is_known_contraction(text: str, i: int) -> bool:
        """Check if quote at i belongs to a known English contraction."""
        remaining = text[i + 1 :].lower()
        char_before = text[i - 1].lower()

        single_suffixes = ["t", "s", "m", "d"]
        multi_suffixes = ["ll", "re", "ve"]

        for suffix in single_suffixes:
            if remaining.startswith(suffix):
                params = _ContractionParams(suffix, char_before, remaining, text, i)
                if params.val_single():
                    return True

        for suffix in multi_suffixes:
            if remaining.startswith(suffix):
                params = _ContractionParams(suffix, char_before, remaining, text, i)
                if params.val_multi():
                    return True

        return False


@dataclass
class CharProcessParams:
    """Parameters for processing a single character."""

    text: str
    i: int
    escaped: bool


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
        self.in_comment: bool = False

    def handle_backslash(self: _ParserState, content: str, i: int) -> bool:
        """Handle backslash character during parsing."""
        if self.in_string and self.raw_string:
            return self._handle_raw_bs(content, i)

        if self.in_string and not self.raw_string:
            self.escape_next = True
            return True

        return False

    def _handle_raw_bs(self: _ParserState, content: str, i: int) -> bool:
        """Handle backslash specifically in raw strings."""
        if i + 1 < len(content) and content[i + 1] in ('"', "'"):
            bs_count = 0
            j = i
            while j >= 0 and content[j] == "\\":
                bs_count += 1
                j -= 1
            if bs_count % 2 == 1:
                self.escape_next = True
                return True
        return False

    def handle_string_start(self: _ParserState, content: str, i: int) -> int:
        """Handle start of a string literal."""
        char = content[i]
        is_raw = self._is_raw_string_prefix(content, i)
        triple_min = IntelligentContextConstants.TRIPLE_QUOTE_MIN_LENGTH

        if (
            i + triple_min < len(content)
            and content[i + 1] == char
            and content[i + triple_min] == char
        ):
            self._apply_string_state(_StringState(char, is_raw, triple=True))
            return i + triple_min

        self._apply_string_state(_StringState(char, is_raw, triple=False))
        return i

    def _apply_string_state(self: _ParserState, state: _StringState) -> None:
        """Set internal string tracking state."""
        self.in_string = True
        self.string_char = state.char
        self.triple_quote = state.triple
        self.raw_string = state.is_raw
        self.backtick_count = 0

    def handle_string_end(self: _ParserState, content: str, i: int) -> int:
        """Handle potential end of a string literal."""
        char = content[i]
        if self.triple_quote:
            triple_min = IntelligentContextConstants.TRIPLE_QUOTE_MIN_LENGTH
            if (
                i + triple_min < len(content)
                and content[i + 1] == char
                and content[i + triple_min] == char
            ):
                self._reset_string_state()
                return i + triple_min + 1
        else:
            self._reset_string_state()
        return i

    def _reset_string_state(self: _ParserState) -> None:
        """Reset internal string tracking state."""
        self.in_string = False
        self.string_char = None
        self.triple_quote = False
        self.raw_string = False
        self.backtick_count = 0

    def handle_backticks(self: _ParserState) -> None:
        """Handle backtick during code parsing."""
        if not self.in_string:
            self.backtick_count += 1

    def _is_raw_string_prefix(self: _ParserState, content: str, i: int) -> bool:
        """Check if character at i is preceded by a raw string prefix."""
        if i <= 0:
            return False

        j = i - 1
        while j >= 0 and content[j].lower() in ("r", "u", "b", "f"):
            j -= 1

        prefix_start = j + 1
        if prefix_start >= i:
            return False

        prefix = content[prefix_start:i].lower()
        if not self._is_valid_raw_string_prefix(prefix):
            return False

        if prefix_start > 0:
            prev = content[prefix_start - 1]
            if prev.isalnum() or prev == "_":
                return False
        return True

    def _is_valid_raw_string_prefix(self: _ParserState, prefix: str) -> bool:
        """Check if a prefix is a valid raw string prefix."""
        prefix = prefix.lower()
        if not prefix or "r" not in prefix:
            return False

        max_len = IntelligentContextConstants.MAX_STRING_PREFIX_LENGTH
        if len(prefix) > max_len or len(set(prefix)) != len(prefix):
            return False

        if "u" in prefix:
            return len(prefix) == 1

        valid_chars = {"r", "b", "f", "u"}
        return all(char in valid_chars for char in prefix)

    def is_string_prefix_at(self: _ParserState, text: str, i: int) -> bool:
        """Check if character at i is preceded by a valid string prefix."""
        j = i - 1
        while j >= 0 and text[j].lower() in ("r", "u", "b", "f"):
            j -= 1

        if j >= i - 1:
            return False

        if j >= 0 and (text[j].isalnum() or text[j] == "_"):
            return False

        prefix = text[j + 1 : i].lower()
        return self._is_valid_string_prefix(prefix)

    def _is_valid_string_prefix(self: _ParserState, prefix: str) -> bool:
        """Check if a prefix is a valid Python string prefix."""
        prefix = prefix.lower()
        if not prefix:
            return False

        max_len = IntelligentContextConstants.MAX_STRING_PREFIX_LENGTH
        if len(prefix) > max_len or len(set(prefix)) != len(prefix):
            return False

        if "u" in prefix:
            return len(prefix) == 1

        valid_chars = {"r", "b", "f", "u"}
        if not all(char in valid_chars for char in prefix):
            return False

        if len(prefix) == IntelligentContextConstants.MAX_STRING_PREFIX_LENGTH:
            return prefix in {"br", "rb", "fr", "rf"}

        return True

    def _handle_newline(self: _ParserState, i: int, *, escaped: bool) -> int:
        """Handle newline character during parsing."""
        self.in_comment = False
        if self.in_string and not self.triple_quote and not escaped:
            self._reset_string_state()
        self.backtick_count = 0
        return i

    def _process_char(self: _ParserState, params: CharProcessParams) -> int:
        """Process a single character during fence search."""
        text = params.text
        i = params.i
        escaped = params.escaped
        char = text[i]

        if char == "\n":
            return self._handle_newline(i, escaped=escaped)

        if not self.in_string and char == "#" and not self.in_comment:
            self.in_comment = True

        if self.in_comment:
            self.backtick_count = 0
            return i

        return self._process_active_char(params)

    def _process_active_char(self: _ParserState, params: CharProcessParams) -> int:
        text = params.text
        i = params.i
        escaped = params.escaped
        char = text[i]

        if not self.in_string and char in ('"', "'") and not escaped:
            return self._handle_quote_start(text, i)

        if self.in_string and char == self.string_char and not escaped:
            return self.handle_string_end(text, i)

        if char == "`" and not escaped:
            self.handle_backticks()
            return i

        self.backtick_count = 0
        return i

    def _handle_quote_start(self: _ParserState, text: str, i: int) -> int:
        if _ApostropheDetector.is_apostrophe_in_word(self, text, i):
            self.backtick_count = 0
            return i
        return self.handle_string_start(text, i)

    def _check_fence(
        self: _ParserState,
        i: int,
        params: FenceParams,
    ) -> FenceResult | None:
        """Check if we've found a valid closing fence."""
        if self.in_string or self.in_comment:
            return None

        if self.backtick_count != params.opening_count:
            return None

        text_length = len(params.content)
        if i + 1 < text_length:
            nxt = params.content[i + 1]
            if nxt.isalnum() or nxt in ("_", "`"):
                return None

        code_end = i - (self.backtick_count - 1)
        return FenceResult(code_end=code_end, next_pos=i + 1)

    def find_closing_fence(
        self: _ParserState,
        start_pos: int,
        params: FenceParams,
    ) -> FenceResult:
        """Find closing fence for code block."""
        text_length = len(params.content)
        i = start_pos

        while i < text_length:
            escaped = self.escape_next
            self.escape_next = False

            if (
                params.content[i] == "\\"
                and not escaped
                and self.handle_backslash(params.content, i)
            ):
                i += 1
                continue

            c_params = CharProcessParams(text=params.content, i=i, escaped=escaped)
            i = self._process_char(c_params)

            res = self._check_fence(i, params)
            if res:
                return res

            i += 1
        return FenceResult.not_found(i)
