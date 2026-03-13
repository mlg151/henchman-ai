"""Task Ledger for tracking delegation progress - REFACTORED VERSION.

The TaskLedger gives the Tech Lead a persistent, structured view of the
overall task: what was requested, what has been delegated, and the outcome
of each delegation.  The Orchestrator injects a rendered snapshot of the
ledger into every delegation tool-result so the Tech Lead can re-orient
even after context compaction drops older messages.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

# Constants
SUMMARY_MAX_LENGTH: int = 500  # Maximum length for delegation summaries

# Type variables for generic methods
_T = TypeVar("_T")


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

    def format_line(self, max_summary_length: int = 120) -> str:
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

    def _get_icon(self) -> str:
        """Get the icon for this delegation's status.

        Returns:
            The appropriate icon.
        """
        return {"completed": "✅", "failed": "❌", "pending": "⏳"}[self.status.value]


class LedgerRenderer:
    """Renderer for TaskLedger to separate rendering logic from data model."""
    
    @staticmethod
    def render_checklist_section(checklist: list[ChecklistItem], lines: list[str]) -> None:
        """Render the checklist section to the lines list.

        Args:
            checklist: The checklist to render.
            lines: The list to append checklist lines to.
        """
        if not checklist:
            return

        lines.append("Checklist:")
        for item in checklist:
            icon = "✅" if item.done else "☐"
            lines.append(f"  {icon} {item.description}")
    
    @staticmethod
    def get_visible_delegations(
        delegations: list[DelegationRecord], max_entries: int
    ) -> tuple[list[DelegationRecord], int]:
        """Get the delegations to display and count of collapsed ones.

        Args:
            delegations: The list of delegation records.
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
    
    @staticmethod
    def count_delegations_by_status(
        delegations: list[DelegationRecord], status: DelegationStatus
    ) -> int:
        """Count delegations with a specific status.

        Args:
            delegations: The list of delegation records.
            status: The status to count.

        Returns:
            Number of delegations with the given status.
        """
        return sum(1 for d in delegations if d.status == status)
    
    @staticmethod
    def render_delegations_section(
        delegations: list[DelegationRecord], lines: list[str], max_entries: int
    ) -> None:
        """Render the delegations section to the lines list.

        Args:
            delegations: The list of delegation records.
            lines: The list to append delegation lines to.
            max_entries: Maximum number of entries to show.
        """
        if not delegations:
            lines.append("No delegations yet.")
            return

        visible, collapsed_count = LedgerRenderer.get_visible_delegations(delegations, max_entries)

        completed = LedgerRenderer.count_delegations_by_status(delegations, DelegationStatus.COMPLETED)
        failed = LedgerRenderer.count_delegations_by_status(delegations, DelegationStatus.FAILED)
        pending = LedgerRenderer.count_delegations_by_status(delegations, DelegationStatus.PENDING)

        lines.append(
            f"Progress: {completed} done, {pending} in-progress, {failed} failed "
            f"/ {len(delegations)} total",
        )

        if collapsed_count:
            lines.append(f"  ({collapsed_count} earlier delegations omitted)")

        for rec in visible:
            lines.append(rec.format_line())
    
    @staticmethod
    def render(ledger: TaskLedger, max_entries: int = 10) -> str:
        """Render a compact text snapshot of the ledger.

        Args:
            ledger: The TaskLedger to render.
            max_entries: Maximum number of delegation entries to show in
                detail.  Older entries are collapsed to a one-line count.

        Returns:
            A multi-line status board string.
        """
        lines: list[str] = [
            "--- 📋 TASK LEDGER (auto-maintained) ---",
            f"Goal: {ledger.goal}",
        ]

        # Mission recap line
        lines.append(ledger.mission_recap())

        # Checklist section
        LedgerRenderer.render_checklist_section(ledger.checklist, lines)

        # Delegations section
        LedgerRenderer.render_delegations_section(ledger.delegations, lines, max_entries)

        lines.append("---")
        return "\n".join(lines)


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
        self,
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
        self,
        item_list: list[_T],
        factory_func: Callable[..., _T],
        *args: Any,
        **kwargs: Any,
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

    def add_checklist_item(self, description: str) -> ChecklistItem:
        """Add a new item to the mission checklist.

        Args:
            description: What needs to be done.

        Returns:
            The newly created ChecklistItem.
        """
        return self._add_item_factory(
            self.checklist,
            ChecklistItem,
            description=description,
        )

    def check_item(self, index: int) -> None:
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

    def add_delegation(self, agent: str, task: str) -> DelegationRecord:
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
        self,
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
        record.summary = summary[:SUMMARY_MAX_LENGTH]

    def complete_delegation(self, record: DelegationRecord, summary: str) -> None:
        """Mark a delegation as completed.

        Args:
            record: The record to update.
            summary: The agent's result summary.

        Returns:
            None
        """
        self._update_delegation(record, DelegationStatus.COMPLETED, summary)

    def fail_delegation(self, record: DelegationRecord, reason: str) -> None:
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

    def mark_verified(self) -> None:
        """Mark the task as verified (Task 3: Verification Tool-Lock).

        Returns:
            None
        """
        self.verified = True

    # ------------------------------------------------------------------
    # Mission recap (Task 9: Mission Recapitulation)
    # ------------------------------------------------------------------

    def _count_delegations_by_status(self, status: DelegationStatus) -> int:
        """Count delegations with a specific status.

        Args:
            status: The status to count.

        Returns:
            Number of delegations with the given status.
        """
        return LedgerRenderer.count_delegations_by_status(self.delegations, status)

    def _get_verification_status(self) -> str:
        """Get the verification status string.

        Returns:
            "✅ verified" or "⚠️ unverified"
        """
        return "✅ verified" if self.verified else "⚠️ unverified"

    def mission_recap(self) -> str:
        """Return a one-sentence mission status summary.

        Returns:
            A concise status string suitable for injection before actions.
        """
        completed = self._count_delegations_by_status(DelegationStatus.COMPLETED)
        failed = self._count_delegations_by_status(DelegationStatus.FAILED)
        pending = self._count_delegations_by_status(DelegationStatus.PENDING)
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
    # Rendering (delegated to LedgerRenderer)
    # ------------------------------------------------------------------

    def render(self, max_entries: int = 10) -> str:
        """Render a compact text snapshot of the ledger.

        Args:
            max_entries: Maximum number of delegation entries to show in
                detail.  Older entries are collapsed to a one-line count.

        Returns:
            A multi-line status board string.
        """
        return LedgerRenderer.render(self, max_entries)