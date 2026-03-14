"""Content extraction for intelligent context management.

This module provides functions for extracting critical sections
from content, such as code blocks, error messages, and tool calls.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from henchman.utils.intelligent_context_parser import _ParserState
from henchman.utils.intelligent_context_types import (
    FenceParams,
    IntelligentContextConstants,
)

if TYPE_CHECKING:
    from henchman.utils.intelligent_context_types import FenceResult

# Error patterns for traceback and exception detection
_ERROR_PATTERN_TRACEBACK: str = (
    r"(Traceback \(most recent call last\):(?:\n(?:  |\t|\w*"
    r"(?:Error|Exception|warning|fail(?:ed|ure)?):)[^\n]*)*)"
)
_ERROR_PATTERNS: list[str] = [
    _ERROR_PATTERN_TRACEBACK,
    r"(?<!\w)Error:.*?(?:\n|$)",
    r"(?<!\w)Exception:.*?(?:\n|$)",
    r"(?<!\w)warning:.*?(?:\n|$)",
    r"(?<!\w)fail(?:ed|ure)?:.*?(?:\n|$)",
]

_TOOL_PATTERNS: list[str] = [
    r"(Tool call:.*?(?:\n|$))",
    r"(Calling tool.*?(?:\n|$))",
    r"(Executing.*?(?:\n|$))",
    r"(Function:.*?(?:\n|$))",
]

_PATTERN_REGISTRY: dict[str, list[str]] = {
    "error": _ERROR_PATTERNS,
    "tool": _TOOL_PATTERNS,
}


def extract_code_blocks(content: str | None) -> list[str]:
    """Extract code blocks from content.
    
    Args:
        content: The text content to extract code blocks from. Can be None.
        
    Returns:
        A list of code blocks found in the content. Each block is a string
        containing the complete code block including triple backticks and
        optional language specifier. Returns an empty list if content is None
        or no code blocks are found.
    """
    if not content:
        return []

    code_blocks: list[str] = []
    i = 0
    content_length = len(content)
    triple_len = IntelligentContextConstants.TRIPLE_QUOTE_LENGTH

    while i < content_length:
        # Code blocks should be preceded by newline or at start of content
        if content[i : i + triple_len] == "```" and (i == 0 or content[i - 1] in ("\n", "\r")):
            block, next_i = _extract_single_block(content, i)
            if block:
                code_blocks.append(block)
            i = next_i
            continue
        i += 1

    return code_blocks


def _extract_single_block(content: str, i: int) -> tuple[str | None, int]:
    """Extract a single code block starting at i."""
    opening_count, _ = _count_backticks(content, i)

    if opening_count < IntelligentContextConstants.MIN_BACKTICKS_FOR_CODE_BLOCK:
        return None, i + 1

    start_pos = i
    i += opening_count
    language, i = _parse_language(content, i)

    # Skip whitespace after language
    i = _skip_whitespace(content, i)

    code_start = i
    state = _ParserState()
    params = FenceParams(content=content, opening_count=opening_count)
    res: FenceResult = state.find_closing_fence(i, params)

    if not res.found:
        return None, start_pos + opening_count

    code_content = content[code_start : res.code_end].rstrip()
    block = f"```{language}\n{code_content}\n```" if language else f"```\n{code_content}\n```"

    return block, res.next_pos


def _skip_whitespace(content: str, i: int) -> int:
    """Skip whitespace characters."""
    content_length = len(content)
    while i < content_length and content[i] in (" ", "\t", "\n", "\r"):
        i += 1
    return i


def _count_backticks(content: str, start_pos: int) -> tuple[int, int]:
    """Count consecutive backticks starting at start_pos."""
    count = 0
    j = start_pos
    content_length = len(content)
    while j < content_length and content[j] == "`":
        count += 1
        j += 1
    return count, j


def _parse_language(content: str, start_pos: int) -> tuple[str, int]:
    """Parse language specification after opening backticks."""
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
    return language, i


def extract_error_sections(content: str | None) -> list[str]:
    """Extract error/exception sections from content.
    
    Args:
        content: The text content to search for error sections, or None.
            If None, returns an empty list.
    
    Returns:
        A list of strings containing error/exception sections found in the content.
        Each section includes tracebacks, exceptions, warnings, or failure messages.
        Returns an empty list if no error sections are found or if content is None.
    
    Examples:
        >>> extract_error_sections("Traceback (most recent call last):\\n  File ...")
        ['Traceback (most recent call last):\\n  File ...']
        >>> extract_error_sections(None)
        []
    """
    return _extract_sections_by_type(content, "error")


def extract_tool_sections(content: str | None) -> list[str]:
    """Extract tool call sections from content."""
    sections = _extract_sections_by_type(content, "tool")
    return list(sections)


def _extract_sections_by_type(
    content: str | None,
    pattern_name: str,
) -> list[str]:
    """Extract sections of a specific type from content."""
    if content is None:
        return []
    patterns = _PATTERN_REGISTRY.get(pattern_name)
    if patterns is None:
        msg = f"Unknown pattern name: {pattern_name}."
        raise ValueError(msg)

    return _extract_by_patterns(content, patterns)


def _extract_by_patterns(
    content: str,
    patterns: list[str],
) -> list[str]:
    """Extract sections matching given patterns from content."""
    if not content or not patterns:
        return []

    sections: list[str] = []
    regex_flags = re.IGNORECASE | re.DOTALL

    for pattern in patterns:
        matches = re.findall(pattern, content, regex_flags)
        for match in matches:
            if match and match.strip():
                _add_unique_match(sections, match.strip())
    return sections


def _add_unique_match(sections: list[str], match_str: str) -> None:
    """Add match to sections if not a duplicate or substring."""
    for i, existing in enumerate(sections):
        if match_str in existing:
            return
        if existing in match_str:
            sections[i] = match_str
            return
    sections.append(match_str)


def extract_keyword_sections(
    content: str | None,
    keywords: list[str] | None = None,
) -> list[str]:
    """Extract sections with important keywords."""
    if content is None:
        return []
    target_keywords = keywords if keywords is not None else _get_default_keywords()

    lines = content.split("\n")
    return _find_keyword_contexts(lines, target_keywords)


def _get_default_keywords() -> list[str]:
    """Get the default list of important keywords."""
    return [
        "important", "critical", "note", "warning", "error", "exception",
        "decision", "conclusion", "summary", "key", "essential", "must",
        "should", "required",
    ]


def _find_keyword_contexts(lines: list[str], keywords: list[str]) -> list[str]:
    """Find context around lines containing keywords."""
    sections: list[str] = []

    for i, line in enumerate(lines):
        if _line_contains_keyword(line, keywords):
            context = _get_context_around_line(lines, i)
            if context:
                sections.append(context)
    return sections


def _line_contains_keyword(line: str, keywords: list[str]) -> bool:
    """Check if a line contains any of the given keywords."""
    if not line or not keywords:
        return False
    line_lower = line.lower()
    return any(kw.lower() in line_lower for kw in keywords)


def _get_context_around_line(lines: list[str], line_index: int) -> str | None:
    """Get context around a specific line."""
    start = max(0, line_index - IntelligentContextConstants.CONTEXT_LINES_BEFORE)
    end = min(len(lines), line_index + IntelligentContextConstants.CONTEXT_LINES_AFTER + 1)
    context = "\n".join(lines[start:end])
    return context.strip() if context and context.strip() else None


def extract_critical_sections(content: str | None) -> list[str]:
    """Extract critical sections from content for preservation."""
    if content is None:
        return []

    sections: list[str] = []
    sections.extend(extract_code_blocks(content))
    sections.extend(extract_error_sections(content))
    sections.extend(extract_tool_sections(content))

    return _get_unique_longest_sections(sections)


def _get_unique_longest_sections(sections: list[str]) -> list[str]:
    """Remove duplicates and substrings, keeping longest sections."""
    unique: list[str] = []
    # Sort by length (longest first)
    candidates = sorted([s for s in sections if s and s.strip()], key=len, reverse=True)

    for section in candidates:
        is_substring = any(section in existing for existing in unique)
        if not is_substring:
            unique.append(section)

    return unique


class ContentExtractor:
    """Extracts critical sections from content for preservation (legacy class)."""

    extract_code_blocks = staticmethod(extract_code_blocks)
    extract_error_sections = staticmethod(extract_error_sections)
    extract_tool_sections = staticmethod(extract_tool_sections)
    extract_keyword_sections = staticmethod(extract_keyword_sections)
    extract_critical_sections = staticmethod(extract_critical_sections)

    _extract_single_block = staticmethod(_extract_single_block)
    _skip_whitespace = staticmethod(_skip_whitespace)
    _count_backticks = staticmethod(_count_backticks)
    _parse_language = staticmethod(_parse_language)
    _extract_sections_by_type = staticmethod(_extract_sections_by_type)
    _extract_by_patterns = staticmethod(_extract_by_patterns)
    _add_unique_match = staticmethod(_add_unique_match)
    _get_default_keywords = staticmethod(_get_default_keywords)
    _find_keyword_contexts = staticmethod(_find_keyword_contexts)
    _line_contains_keyword = staticmethod(_line_contains_keyword)
    _get_context_around_line = staticmethod(_get_context_around_line)
    _get_unique_longest_sections = staticmethod(_get_unique_longest_sections)
