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


def _hash_content(content: str) -> str:
    """Create a short hash of content for comparison."""
    return hashlib.md5(content.encode()).hexdigest()[:8]


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

    start_index: int = -1  # -1 means no protection (backward compat)
    tool_call_ids: set[str] = field(default_factory=set)
    tool_count: int = 0
    iteration: int = 0
    protected_tokens: int = 0
    files_modified: set[str] = field(default_factory=set)
    errors_seen: list[str] = field(default_factory=list)
    recent_result_hashes: list[str] = field(default_factory=list)
    _consecutive_duplicates: int = 0
    _last_call_signature: str = ""

    def record_tool_call(
        self,
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
        """
        self.tool_call_ids.add(tool_call_id)
        self.tool_count += 1

        # Track for duplicate detection
        # Be more lenient with read-only operations
        is_read_only = tool_name in ("read_file", "ls", "glob", "grep", "rag_search")
        call_sig = f"{tool_name}:{_hash_content(str(sorted(arguments.items())))}"
        if call_sig == self._last_call_signature:
            # Only count as duplicate if not a read operation or if it's excessive
            if not is_read_only or self._consecutive_duplicates >= 5:
                self._consecutive_duplicates += 1
        else:
            self._consecutive_duplicates = 0
            self._last_call_signature = call_sig

        # Track result hash for spinning detection
        if result and result.content:
            result_hash = _hash_content(result.content)
            self.recent_result_hashes.append(result_hash)
            # Keep only last 10
            if len(self.recent_result_hashes) > 10:
                self.recent_result_hashes.pop(0)

        # Track files modified
        if tool_name in ("write_file", "edit_file") and "path" in arguments:
            self.files_modified.add(str(arguments["path"]))

        # Track errors
        if result and not result.success and result.error:
            self.errors_seen.append(result.error)

    def increment_iteration(self) -> None:
        """Increment iteration counter (called after each tool batch)."""
        self.iteration += 1

    def is_making_progress(self) -> bool:
        """Check if the turn is making meaningful progress.

        Returns:
            True if progress indicators are present.
        """
        # Progress = new files modified recently, or diverse tool results
        if self.files_modified:
            return True

        # Check for result diversity (not same results over and over)
        if len(self.recent_result_hashes) >= 3:
            unique_recent = len(set(self.recent_result_hashes[-5:]))
            if unique_recent >= 3:
                return True

        return False

    def is_spinning(self) -> bool:
        """Check if the turn appears to be stuck in a loop.

        Returns:
            True if loop indicators are detected.
        """
        # Same tool+args called 4+ times consecutively (increased from 3)
        if self._consecutive_duplicates >= 3:  # 0-indexed, so 3 = 4 calls
            return True

        # Same result hash repeated 4+ times in last 6 results (more lenient)
        if len(self.recent_result_hashes) >= 6:
            recent = self.recent_result_hashes[-6:]
            for h in set(recent):
                if recent.count(h) >= 4:
                    return True

        # No new files touched in 7+ iterations with many tool calls (increased threshold)
        return bool(self.iteration >= 7 and not self.files_modified and self.tool_count > 15)

    def get_adaptive_limit(self, base_limit: int = 25) -> int:
        """Get the adaptive iteration limit based on progress.

        Args:
            base_limit: Base iteration limit.

        Returns:
            Adjusted limit based on progress/spinning detection.
        """
        limit = base_limit

        if self.is_making_progress():
            limit += 10  # Extend for productive work

        if self.is_spinning():
            limit = max(5, limit - 10)  # Reduce for spinning

        return limit

    def is_approaching_limit(self, base_limit: int = 25, threshold: float = 0.75) -> bool:
        """Check if approaching iteration limit.

        Args:
            base_limit: Base iteration limit.
            threshold: Fraction of limit to trigger warning.

        Returns:
            True if past threshold.
        """
        adaptive_limit = self.get_adaptive_limit(base_limit)
        return self.iteration >= int(adaptive_limit * threshold)

    def is_at_limit(self, base_limit: int = 25) -> bool:
        """Check if at or past iteration limit.

        Args:
            base_limit: Base iteration limit.

        Returns:
            True if at or past limit.
        """
        return self.iteration >= self.get_adaptive_limit(base_limit)

    def get_status_string(
        self,
        base_limit: int = 25,
        max_tokens: int = 100000,
    ) -> str:
        """Get a status string for display.

        Args:
            base_limit: Base iteration limit for display.
            max_tokens: Max tokens for percentage calculation.

        Returns:
            Formatted status string.
        """
        adaptive_limit = self.get_adaptive_limit(base_limit)

        # Progress indicator
        if self.is_spinning():
            progress = "⚠ spinning"
        elif self.is_making_progress():
            progress = "✓ progress"
        else:
            progress = "…"

        # Token percentage
        token_pct = int(100 * self.protected_tokens / max_tokens) if max_tokens > 0 else 0

        return (
            f"[Iter {self.iteration}/{adaptive_limit} | "
            f"{self.tool_count} calls | "
            f"{self.protected_tokens // 1000}K tokens ({token_pct}% protected) | "
            f"{progress}]"
        )

    def reset(self, new_start_index: int = 0) -> None:
        """Reset state for a new turn.

        Args:
            new_start_index: Starting message index for the new turn.
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
