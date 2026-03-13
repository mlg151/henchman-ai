"""Conversation type detection for intelligent context management."""

from __future__ import annotations

from typing import ClassVar

from henchman.providers.base import Message
from henchman.utils.intelligent_context_types import IntelligentContextConstants


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
