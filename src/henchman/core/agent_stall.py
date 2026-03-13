"""Stall detection for Agent responses.

Detects when an agent narrates intent without taking action,
and provides nudge messages to redirect toward tool usage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STALL_PHRASES: list[str] = [
    "let me start by",
    "i'll start by",
    "i will start by",
    "i'll create",
    "let me create",
    "i'll write",
    "let me write",
    "i'll begin",
    "now i'll",
    "let me begin",
    "i'm going to",
    "i will now",
    "step 1:",
    "first, i will",
    "let me ",
    "going to ",
    "next i ",
]

STALL_NUDGE_MESSAGE: str = (
    "You stopped without taking action. Do not narrate or outline steps — "
    "use your tools to do the work. If the task feels large, break it into "
    "a smaller piece and call a tool for that piece NOW."
)

MAX_STALL_NUDGES: int = 2
MIN_RESPONSE_LENGTH: int = 20
MAX_INTENT_PHRASE_LENGTH: int = 120


@dataclass
class StallDetector:
    """Detects when an agent narrates intent without acting.

    Attributes:
        enabled: Whether stall detection is active.
        nudge_count: Number of nudges issued this turn.
        failure: Whether max nudges have been exceeded.
    """

    enabled: bool = True
    nudge_count: int = 0
    failure: bool = False
    _max_nudges: int = field(default=MAX_STALL_NUDGES)

    def should_skip(
        self: StallDetector,
        response_text: str,
        *,
        had_tool_calls: bool,
    ) -> bool:
        """Determine if stall check should be skipped.

        Args:
            response_text: The response text to check.
            had_tool_calls: Whether the response included tool calls.

        Returns:
            True if the check should be skipped.
        """
        if not self.enabled:
            return True
        if had_tool_calls:
            self.nudge_count = 0
            return True
        return len(response_text) < MIN_RESPONSE_LENGTH

    def detect_patterns(self: StallDetector, response_text: str) -> bool:
        """Detect stalling patterns in response text.

        Args:
            response_text: The response text to analyze.

        Returns:
            True if stalling patterns are detected.
        """
        stripped = response_text.strip()
        if stripped.endswith(":"):
            return True
        lower = response_text.lower()
        has_phrase = any(phrase in lower for phrase in STALL_PHRASES)
        is_question = "?" in response_text and "should i" in lower
        return (
            has_phrase
            and not is_question
            and (len(stripped) < MAX_INTENT_PHRASE_LENGTH or stripped.endswith(":"))
        )

    async def check(
        self: StallDetector,
        response_text: str,
        *,
        had_tool_calls: bool,
    ) -> str | None:
        """Check for stalling and return nudge message if detected.

        Args:
            response_text: The response text to check.
            had_tool_calls: Whether the response included tool calls.

        Returns:
            Nudge message string if stalling detected, None otherwise.
        """
        if self.should_skip(response_text, had_tool_calls=had_tool_calls):
            return None
        if not self.detect_patterns(response_text):
            return None
        self.nudge_count += 1
        if self.nudge_count > self._max_nudges:
            self.failure = True
            return None
        return STALL_NUDGE_MESSAGE
