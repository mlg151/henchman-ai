"""Turn state tracking for loop protection and adaptive limits.

This module provides turn-aware context management to prevent infinite
loops caused by context compaction dropping recent tool results.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from henchman.tools.base import ToolResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HASH_PREFIX_LENGTH = 8
READ_ONLY_DUPLICATE_THRESHOLD = 5
MAX_RECENT_HASHES = 10
MIN_HASHES_FOR_PROGRESS = 3
RECENT_HASH_WINDOW = 5
MIN_UNIQUE_FOR_PROGRESS = 3
CONSECUTIVE_DUPLICATE_THRESHOLD = 3
MIN_HASHES_FOR_SPIN_CHECK = 6
SPIN_HASH_WINDOW = 6
SPIN_HASH_REPEAT_THRESHOLD = 4
IDLE_ITERATION_THRESHOLD = 7
IDLE_TOOL_COUNT_THRESHOLD = 15
PROGRESS_LIMIT_BONUS = 10
SPINNING_LIMIT_PENALTY = 10
SPINNING_LIMIT_FLOOR = 5
PERCENT_MULTIPLIER = 100
TOKENS_PER_K = 1000

READ_ONLY_TOOLS: frozenset[str] = frozenset(
    {"read_file", "ls", "glob", "grep", "rag_search"},
)
WRITE_TOOLS: frozenset[str] = frozenset({"write_file", "edit_file"})


def _hash_content(content: str) -> str:
    """Create a short hash of content for comparison.

    Args:
        content: The string content to hash.

    Returns:
        An 8-character hex digest prefix.
    """
    return hashlib.md5(content.encode()).hexdigest()[:HASH_PREFIX_LENGTH]


@dataclass
class TurnState:
    """Tracks state for the current agent turn.

    A "turn" starts when the user sends a message and ends when the
    agent responds without requesting more tool calls.

    Attributes:
        start_index: Index in message history where this turn began.
            Default -1 means no protection (for backward compatibility).
        tool_call_ids: Set of tool call IDs made this turn.
        tool_count: Total number of tool calls this turn.
        iteration: Current iteration (tool call round) within this turn.
        protected_tokens: Estimated tokens in protected zone.
        files_modified: Set of file paths modified this turn.
        errors_seen: List of error messages encountered.
        recent_result_hashes: Recent tool result hashes for loop detection.
    """

    start_index: int = -1
    tool_call_ids: set[str] = field(default_factory=set)
    tool_count: int = 0
    iteration: int = 0
    protected_tokens: int = 0
    files_modified: set[str] = field(default_factory=set)
    errors_seen: list[str] = field(default_factory=list)
    recent_result_hashes: list[str] = field(default_factory=list)
    _consecutive_duplicates: int = 0
    _last_call_signature: str = ""
    _last_call_is_read_only: bool = False

    def record_tool_call(
        self: TurnState,
        tool_call_id: str,
        tool_name: str,
        arguments: dict[str, object],
        result: ToolResult | None = None,
    ) -> None:
        """Record a tool call for tracking.

        Args:
            tool_call_id: Unique ID of the tool call.
            tool_name: Name of the tool called.
            arguments: Arguments passed to the tool.
            result: Optional result from tool execution.

        Returns:
            None
        """
        self.tool_call_ids.add(tool_call_id)
        self.tool_count += 1
        self._track_duplicates(tool_name, arguments)
        self._track_result_hash(result)
        if tool_name in WRITE_TOOLS and "path" in arguments:
            self.files_modified.add(str(arguments["path"]))
        if result and not result.success and result.error:
            self.errors_seen.append(result.error)

    def _track_duplicates(
        self: TurnState,
        tool_name: str,
        arguments: dict[str, object],
    ) -> None:
        """Track consecutive duplicate tool calls.

        The counter always increments on a repeated call so that
        ``is_spinning()`` can apply a tool-type-aware threshold.  The previous
        logic only incremented for read-only tools when the counter was already
        at ``READ_ONLY_DUPLICATE_THRESHOLD``, making it impossible to ever
        reach that threshold — read-only tool loops were never detected.
        """
        is_read_only = tool_name in READ_ONLY_TOOLS
        call_sig = f"{tool_name}:{_hash_content(str(sorted(arguments.items())))}"
        if call_sig == self._last_call_signature:
            self._consecutive_duplicates += 1
        else:
            self._consecutive_duplicates = 0
            self._last_call_signature = call_sig
            self._last_call_is_read_only = is_read_only

    def _track_result_hash(self: TurnState, result: ToolResult | None) -> None:
        """Track result hash for spinning detection."""
        if result and result.content:
            self.recent_result_hashes.append(_hash_content(result.content))
            if len(self.recent_result_hashes) > MAX_RECENT_HASHES:
                self.recent_result_hashes.pop(0)

    def increment_iteration(self: TurnState) -> None:
        """Increment iteration counter (called after each tool batch).

        Returns:
            None
        """
        self.iteration += 1

    def is_making_progress(self: TurnState) -> bool:
        """Check if the turn is making meaningful progress.

        Returns:
            True if progress indicators are present.
        """
        if self.files_modified:
            return True
        if len(self.recent_result_hashes) >= MIN_HASHES_FOR_PROGRESS:
            unique = len(set(self.recent_result_hashes[-RECENT_HASH_WINDOW:]))
            if unique >= MIN_UNIQUE_FOR_PROGRESS:
                return True
        return False

    def is_spinning(self: TurnState) -> bool:
        """Check if the turn appears to be stuck in a loop.

        Read-only tools (grep, read_file, ls, etc.) use a higher duplicate
        threshold (``READ_ONLY_DUPLICATE_THRESHOLD``) than write/execute tools
        (``CONSECUTIVE_DUPLICATE_THRESHOLD``) because repeated reads are
        common during exploration and are less alarming than repeated writes.

        Returns:
            True if loop indicators are detected.
        """
        dup_threshold = (
            READ_ONLY_DUPLICATE_THRESHOLD
            if self._last_call_is_read_only
            else CONSECUTIVE_DUPLICATE_THRESHOLD
        )
        if self._consecutive_duplicates >= dup_threshold:
            return True
        if len(self.recent_result_hashes) >= MIN_HASHES_FOR_SPIN_CHECK:
            recent = self.recent_result_hashes[-SPIN_HASH_WINDOW:]
            for h in set(recent):
                if recent.count(h) >= SPIN_HASH_REPEAT_THRESHOLD:
                    return True
        return bool(
            self.iteration >= IDLE_ITERATION_THRESHOLD
            and not self.files_modified
            and self.tool_count > IDLE_TOOL_COUNT_THRESHOLD,
        )

    def get_adaptive_limit(self: TurnState, base_limit: int = 25) -> int:
        """Get the adaptive iteration limit based on progress.

        Args:
            base_limit: Base iteration limit.

        Returns:
            Adjusted limit based on progress/spinning detection.
        """
        limit = base_limit
        if self.is_making_progress():
            limit += PROGRESS_LIMIT_BONUS
        if self.is_spinning():
            limit = max(SPINNING_LIMIT_FLOOR, limit - SPINNING_LIMIT_PENALTY)
        return limit

    def is_approaching_limit(
        self: TurnState,
        base_limit: int = 25,
        threshold: float = 0.75,
    ) -> bool:
        """Check if approaching iteration limit.

        Args:
            base_limit: Base iteration limit.
            threshold: Fraction of limit to trigger warning.

        Returns:
            True if past threshold.
        """
        return self.iteration >= int(self.get_adaptive_limit(base_limit) * threshold)

    def is_at_limit(self: TurnState, base_limit: int = 25) -> bool:
        """Check if at or past iteration limit.

        Args:
            base_limit: Base iteration limit.

        Returns:
            True if at or past limit.
        """
        return self.iteration >= self.get_adaptive_limit(base_limit)

    def get_status_string(
        self: TurnState,
        base_limit: int = 25,
        max_tokens: int = 100_000,
    ) -> str:
        """Get a status string for display.

        Args:
            base_limit: Base iteration limit for display.
            max_tokens: Max tokens for percentage calculation.

        Returns:
            Formatted status string.
        """
        adaptive_limit = self.get_adaptive_limit(base_limit)
        if self.is_spinning():
            progress = "⚠ spinning"
        elif self.is_making_progress():
            progress = "✓ progress"
        else:
            progress = "…"
        token_pct = (
            int(PERCENT_MULTIPLIER * self.protected_tokens / max_tokens) if max_tokens > 0 else 0
        )
        return (
            f"[Iter {self.iteration}/{adaptive_limit} | "
            f"{self.tool_count} calls | "
            f"{self.protected_tokens // TOKENS_PER_K}K tokens ({token_pct}% protected) | "
            f"{progress}]"
        )

    def reset(self: TurnState, new_start_index: int = 0) -> None:
        """Reset state for a new turn.

        Args:
            new_start_index: Starting message index for the new turn.

        Returns:
            None
        """
        self.start_index = new_start_index
        self.tool_call_ids = set()
        self.tool_count = 0
        self.iteration = 0
        self.protected_tokens = 0
        self.files_modified = set()
        self.errors_seen = []
        self.recent_result_hashes = []
        self._consecutive_duplicates = 0
        self._last_call_signature = ""
        self._last_call_is_read_only = False


@dataclass
class TurnSummary:
    """Summary of a completed turn for persistence.

    Attributes:
        turn_number: Sequential turn number in session.
        summary_text: LLM-generated summary of the turn.
        files_modified: List of files modified during the turn.
        tool_count: Number of tool calls made.
        timestamp: ISO timestamp when turn completed.
    """

    turn_number: int
    summary_text: str
    files_modified: list[str]
    tool_count: int
    timestamp: str
