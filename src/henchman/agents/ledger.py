"""Task Ledger for tracking delegation progress - REFACTORED VERSION.

The TaskLedger gives the Tech Lead a persistent, structured view of the
overall task: what was requested, what has been delegated, and the outcome
of each delegation.  The Orchestrator injects a rendered snapshot of the
ledger into every delegation tool-result so the Tech Lead can re-orient
even after context compaction drops older messages.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import ParamSpec, Self, TypeVar

# Constants
MAX_DELEGATION_SUMMARY_LENGTH: int = 500  # Maximum length for delegation summaries
DEFAULT_MAX_SUMMARY_LENGTH: int = 120  # Default for display
DEFAULT_MAX_ENTRIES: int = 10  # Default number of entries to show
REPR_SUMMARY_TRUNCATE_LENGTH: int = 50  # Length to truncate summary in __repr__

# Type variables for generic methods
_T = TypeVar("_T")
_P = ParamSpec("_P")


# ------------------------------------------------------------------
# Utility functions for delegation counting (to eliminate duplicate code)
# ------------------------------------------------------------------


def _count_delegations_by_status_util(
    delegations: Iterable[DelegationRecord], status: DelegationStatus
) -> int:
    """Count delegations with a specific status (utility function).

    Args:
        delegations: Iterable of delegation records.
        status: The status to count.

    Returns:
        Number of delegations with the given status.
    """
    return sum(1 for d in delegations if d.status == status)


def _get_delegation_counts_util(delegations: Iterable[DelegationRecord]) -> tuple[int, int, int]:
    """Get counts of delegations by status (utility function).

    Args:
        delegations: Iterable of delegation records.

    Returns:
        Tuple of (completed_count, pending_count, failed_count)
    """
    completed = _count_delegations_by_status_util(delegations, DelegationStatus.COMPLETED)
    pending = _count_delegations_by_status_util(delegations, DelegationStatus.PENDING)
    failed = _count_delegations_by_status_util(delegations, DelegationStatus.FAILED)

    return completed, pending, failed


@dataclass
class ProgressCounts:
    """Counts of delegations by status for progress reporting.

    Attributes:
        completed: Number of completed delegations.
        pending: Number of pending delegations.
        failed: Number of failed delegations.
        total: Total number of delegations.
    """

    completed: int
    pending: int
    failed: int
    total: int

    def format_progress_line(self: Self) -> str:
        """Format a progress line for delegations.

        Returns:
            Formatted progress line string.
        """
        return self._format_with_template(
            "Progress: {completed} done, {pending} in-progress, {failed} failed / {total} total"
        )

    def __repr__(self: Self) -> str:
        """Return a string representation of the progress counts."""
        return self._format_with_template(
            "ProgressCounts(completed={completed}, pending={pending}, "
            "failed={failed}, total={total})"
        )

    def _format_with_template(self: Self, template: str) -> str:
        """Format the progress counts using a template string.

        Args:
            template: Template string with {completed}, {pending}, {failed}, {total} placeholders.

        Returns:
            Formatted string.
        """
        return template.format(
            completed=self.completed, pending=self.pending, failed=self.failed, total=self.total
        )


class DelegationStatus(str, Enum):
    """Status of a single delegation."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ChecklistItem:
    """A single item on the Tech Lead's task checklist.

    Attributes:
        description: What needs to be done.
        done: Whether this item has been completed.
    """

    description: str
    done: bool = False

    def __repr__(self: Self) -> str:
        """Return a string representation of the checklist item."""
        status = "✅" if self.done else "☐"
        return f"ChecklistItem({status} {self.description!r})"


@dataclass
class DelegationRecord:
    """Record of a single delegation to a specialist agent.

    Attributes:
        agent: Role of the delegated agent (e.g. ``"coder"``).
        task: Short description of the delegated task.
        status: Current status of the delegation.
        summary: Result summary returned by the agent.
    """

    agent: str
    task: str
    status: DelegationStatus = DelegationStatus.PENDING
    summary: str = ""

    def format_line(self: Self, max_summary_length: int = DEFAULT_MAX_SUMMARY_LENGTH) -> str:
        """Format this delegation record as a display line.

        Args:
            max_summary_length: Maximum length of summary to include.

        Returns:
            Formatted line string.
        """
        icon = self._get_icon()
        summary_brief = self.summary[:max_summary_length].replace("\n", " ") if self.summary else ""
        line = f"  {icon} {self.agent} → {self.task}"
        if summary_brief:
            line += f" — {summary_brief}"
        return line

    def _get_icon(self: Self) -> str:
        """Get the icon for this delegation's status.

        Returns:
            The appropriate icon.
        """
        return {"completed": "✅", "failed": "❌", "pending": "⏳"}[self.status.value]

    def __repr__(self: Self) -> str:
        """Return a string representation of the delegation record."""
        return (
            f"DelegationRecord(agent={self.agent!r}, task={self.task!r}, "
            f"status={self.status.value}, summary={self.summary[:REPR_SUMMARY_TRUNCATE_LENGTH]!r}...)"
            if len(self.summary) > REPR_SUMMARY_TRUNCATE_LENGTH
            else f"DelegationRecord(agent={self.agent!r}, task={self.task!r}, "
            f"status={self.status.value}, summary={self.summary!r})"
        )


class LedgerRenderer:
    """Renderer for TaskLedger to separate rendering logic from data model."""

    def __init__(self: Self, ledger: TaskLedger, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        """Initialize the renderer with a ledger and configuration.

        Args:
            ledger: The TaskLedger to render.
            max_entries: Maximum number of delegation entries to show in detail.
        """
        self.ledger = ledger
        self.max_entries = max_entries

    def render(self: Self) -> str:
        """Render a compact text snapshot of the ledger.

        Returns:
            A multi-line status board string.
        """
        return self._render_ledger()

    def _render_checklist_section(self: Self, lines: list[str]) -> None:
        """Render the checklist section to the lines list.

        Args:
            lines: The list to append checklist lines to.
        """
        if not self.ledger.checklist:
            return

        lines.append("Checklist:")
        for item in self.ledger.checklist:
            icon = "✅" if item.done else "☐"
            lines.append(f"  {icon} {item.description}")

    @staticmethod
    def get_visible_delegations(
        delegations: list[DelegationRecord], max_entries: int
    ) -> tuple[list[DelegationRecord], int]:
        """Get the delegations to display and count of collapsed ones (static version).

        Args:
            delegations: List of delegation records.
            max_entries: Maximum number of entries to show.

        Returns:
            Tuple of (visible_delegations, collapsed_count)
        """
        # Handle edge cases: zero or negative max_entries
        if max_entries <= 0:
            return [], len(delegations)

        if len(delegations) <= max_entries:
            return delegations, 0

        collapsed_count = len(delegations) - max_entries
        visible = delegations[-max_entries:]
        return visible, collapsed_count

    def _get_visible_delegations(self: Self) -> tuple[list[DelegationRecord], int]:
        """Get the delegations to display and count of collapsed ones (instance version).

        Returns:
            Tuple of (visible_delegations, collapsed_count)
        """
        return LedgerRenderer.get_visible_delegations(self.ledger.delegations, self.max_entries)

    def _render_delegations_section(self: Self, lines: list[str]) -> None:
        """Render the delegations section to the lines list.

        Args:
            lines: The list to append delegation lines to.
        """
        if not self.ledger.delegations:
            lines.append("No delegations yet.")
            return

        visible, collapsed_count = self._get_visible_delegations()
        completed, pending, failed = _get_delegation_counts_util(self.ledger.delegations)

        progress_counts = ProgressCounts(
            completed=completed,
            pending=pending,
            failed=failed,
            total=len(self.ledger.delegations),
        )
        lines.append(progress_counts.format_progress_line())

        if collapsed_count:
            lines.append(f"  ({collapsed_count} earlier delegations omitted)")

        for rec in visible:
            lines.append(rec.format_line())

    def _render_ledger(self: Self) -> str:
        """Render a compact text snapshot of the ledger (instance version).

        Returns:
            A multi-line status board string.
        """
        lines: list[str] = [
            "--- 📋 TASK LEDGER (auto-maintained) ---",
            f"Goal: {self.ledger.goal}",
        ]

        # Mission recap line
        lines.append(self.ledger.mission_recap())

        # Checklist section
        self._render_checklist_section(lines)

        # Delegations section
        self._render_delegations_section(lines)

        lines.append("---")
        return "\n".join(lines)

    @staticmethod
    def render_static(ledger: TaskLedger, max_entries: int = DEFAULT_MAX_ENTRIES) -> str:
        """Render a compact text snapshot of the ledger (static version).

        Args:
            ledger: The TaskLedger to render.
            max_entries: Maximum number of delegation entries to show in
                detail.  Older entries are collapsed to a one-line count.

        Returns:
            A multi-line status board string.
        """
        renderer = LedgerRenderer(ledger, max_entries)
        return renderer._render_ledger()


@dataclass
class TaskLedger:
    """Structured task tracker maintained by the Orchestrator.

    The ledger is created at the start of each ``Orchestrator.run()`` call
    and updated after every delegation.  A compact text rendering is
    appended to every delegation tool-result so the Tech Lead always has
    an up-to-date status board.

    Attributes:
        goal: The original user request (never mutated).
        checklist: Ordered list of checklist items for the mission plan.
        delegations: Ordered list of delegation records.
        verified: Whether the overall task has been verified.
    """

    goal: str
    checklist: list[ChecklistItem] = field(default_factory=list)
    delegations: list[DelegationRecord] = field(default_factory=list)
    verified: bool = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_and_append(
        self: Self,
        item_list: list[_T],
        item: _T,
    ) -> _T:
        """Helper method to create an item and append it to a list.

        Args:
            item_list: The list to append to.
            item: The item to append.

        Returns:
            The appended item.
        """
        item_list.append(item)
        return item

    def _add_item_factory(
        self: Self,
        item_list: list[_T],
        factory_func: Callable[_P, _T],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _T:
        """Generic helper to create and append an item using a factory function.

        This addresses the duplicate code smell between add_checklist_item and add_delegation.

        Args:
            item_list: The list to append to.
            factory_func: Function that creates the item.
            *args: Arguments to pass to factory_func.
            **kwargs: Keyword arguments to pass to factory_func.

        Returns:
            The newly created and appended item.
        """
        item = factory_func(*args, **kwargs)
        return self._create_and_append(item_list, item)

    # ------------------------------------------------------------------
    # Checklist helpers (Task 1: Checklist-First Initiation)
    # ------------------------------------------------------------------

    def add_checklist_item(self: Self, description: str) -> ChecklistItem:
        """Add a new item to the mission checklist.

        Args:
            description: What needs to be done.

        Returns:
            The newly created ChecklistItem.
        """
        if not description:
            msg = "Checklist description cannot be empty"
            raise ValueError(msg)

        return self._add_item_factory(
            self.checklist,
            ChecklistItem,
            description=description,
        )

    def check_item(self: Self, index: int) -> None:
        """Mark a checklist item as done by index.

        Args:
            index: Zero-based index of the item to check.

        Raises:
            IndexError: If index is out of range.

        Returns:
            None
        """
        if index < 0 or index >= len(self.checklist):
            raise IndexError(f"Checklist index {index} out of range (0-{len(self.checklist) - 1})")
        self.checklist[index].done = True

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def add_delegation(self: Self, agent: str, task: str) -> DelegationRecord:
        """Register a new delegation.

        Args:
            agent: Target agent role.
            task: Task description sent to the agent.

        Returns:
            The newly created DelegationRecord.
        """
        return self._add_item_factory(
            self.delegations,
            DelegationRecord,
            agent=agent,
            task=task,
        )

    def _update_delegation(
        self: Self,
        record: DelegationRecord,
        status: DelegationStatus,
        summary: str,
    ) -> None:
        """Internal helper to update a delegation record.

        Args:
            record: The record to update.
            status: The new status.
            summary: The agent's result summary or failure reason.
        """
        record.status = status
        record.summary = summary[:MAX_DELEGATION_SUMMARY_LENGTH]

    def complete_delegation(self: Self, record: DelegationRecord, summary: str) -> None:
        """Mark a delegation as completed.

        Args:
            record: The record to update.
            summary: The agent's result summary.

        Returns:
            None
        """
        self._update_delegation(record, DelegationStatus.COMPLETED, summary)

    def fail_delegation(self: Self, record: DelegationRecord, reason: str) -> None:
        """Mark a delegation as failed.

        Args:
            record: The record to update.
            reason: Short failure reason.

        Returns:
            None
        """
        # Use keywords to differentiate AST from complete_delegation
        self._update_delegation(
            record=record,
            status=DelegationStatus.FAILED,
            summary=reason,
        )

    def mark_verified(self: Self) -> None:
        """Mark the task as verified (Task 3: Verification Tool-Lock).

        Returns:
            None
        """
        self.verified = True

    # ------------------------------------------------------------------
    # Mission recap (Task 9: Mission Recapitulation)
    # ------------------------------------------------------------------

    def _get_verification_status(self: Self) -> str:
        """Get the verification status string.

        Returns:
            "✅ verified" or "⚠️ unverified"
        """
        return "✅ verified" if self.verified else "⚠️ unverified"

    def _get_delegation_counts(self: Self) -> tuple[int, int, int]:
        """Get counts of delegations by status.

        Returns:
            Tuple of (completed_count, pending_count, failed_count)
        """
        return _get_delegation_counts_util(self.delegations)

    def mission_recap(self: Self) -> str:
        """Return a one-sentence mission status summary.

        Returns:
            A concise status string suitable for injection before actions.
        """
        completed, pending, failed = self._get_delegation_counts()
        checked = sum(1 for c in self.checklist if c.done)
        total_checks = len(self.checklist)
        verification = self._get_verification_status()

        if total_checks:
            return (
                f"Mission [{verification}]: {checked}/{total_checks} checklist items done, "
                f"{completed} delegations done, {pending} pending, {failed} failed."
            )
        return (
            f"Mission [{verification}]: "
            f"{completed} delegations done, {pending} pending, {failed} failed."
        )

    # ------------------------------------------------------------------
    # Rendering (delegated to LedgerRenderer but kept for backward compatibility)
    # ------------------------------------------------------------------

    def render(self: Self, max_entries: int = DEFAULT_MAX_ENTRIES) -> str:
        """Render a compact text snapshot of the ledger.

        Args:
            max_entries: Maximum number of delegation entries to show in
                detail.  Older entries are collapsed to a one-line count.

        Returns:
            A multi-line status board string.
        """
        return LedgerRenderer.render_static(self, max_entries)

    def __repr__(self: Self) -> str:
        """Return a string representation of the task ledger."""
        return (
            f"TaskLedger(goal={self.goal!r}, "
            f"checklist={len(self.checklist)} items, "
            f"delegations={len(self.delegations)} records, "
            f"verified={self.verified})"
        )
