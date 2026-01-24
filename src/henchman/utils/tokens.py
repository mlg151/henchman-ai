from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.providers.base import Message


class TokenCounter:
    """Estimates token usage."""

    @staticmethod
    def count_text(text: str) -> int:
        """Estimate tokens in text (char/4 heuristic)."""
        if not text:
            return 0
        return len(text) // 4

    @classmethod
    def count_messages(cls, messages: list[Message]) -> int:
        """Estimate tokens in a list of messages."""
        total = 0
        for msg in messages:
            if msg.content:
                total += cls.count_text(msg.content)
            # Add heuristic for tool calls overhead
            if msg.tool_calls:
                total += 100 # base overhead
                for tc in msg.tool_calls:
                    total += cls.count_text(str(tc))
        return total
