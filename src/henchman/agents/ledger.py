"""Task Ledger for tracking delegation progress.

The TaskLedger gives the Tech Lead a persistent, structured view of the
overall task: what was requested, what has been delegated, and the outcome
of each delegation.  The Orchestrator injects a rendered snapshot of the
ledger into every delegation tool-result so the Tech Lead can re-orient
even after context compaction drops older messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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
    # Checklist helpers (Task 1: Checklist-First Initiation)
    # ------------------------------------------------------------------

    def add_checklist_item(self, description: str) -> ChecklistItem:
        """Add a new item to the mission checklist.

        Args:
            description: What needs to be done.

        Returns:
            The newly created ChecklistItem.
        """
        item = ChecklistItem(description=description)
        self.checklist.append(item)
        return item

    def check_item(self, index: int) -> None:
        """Mark a checklist item as done by index.

        Args:
            index: Zero-based index of the item to check.

        Raises:
            IndexError: If index is out of range.
        """
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
        record = DelegationRecord(agent=agent, task=task)
        self.delegations.append(record)
        return record

    def complete_delegation(self, record: DelegationRecord, summary: str) -> None:
        """Mark a delegation as completed.

        Args:
            record: The record to update.
            summary: The agent's result summary.
        """
        record.status = DelegationStatus.COMPLETED
        record.summary = summary[:500]

    def fail_delegation(self, record: DelegationRecord, reason: str) -> None:
        """Mark a delegation as failed.

        Args:
            record: The record to update.
            reason: Short failure reason.
        """
        record.status = DelegationStatus.FAILED
        record.summary = reason[:500]

    def mark_verified(self) -> None:
        """Mark the task as verified (Task 3: Verification Tool-Lock)."""
        self.verified = True

    # ------------------------------------------------------------------
    # Mission recap (Task 9: Mission Recapitulation)
    # ------------------------------------------------------------------

    def mission_recap(self) -> str:
        """Return a one-sentence mission status summary.

        Returns:
            A concise status string suitable for injection before actions.
        """
        completed = sum(1 for d in self.delegations if d.status == DelegationStatus.COMPLETED)
        failed = sum(1 for d in self.delegations if d.status == DelegationStatus.FAILED)
        pending = sum(1 for d in self.delegations if d.status == DelegationStatus.PENDING)
        checked = sum(1 for c in self.checklist if c.done)
        total_checks = len(self.checklist)
        verification = "✅ verified" if self.verified else "⚠️ unverified"

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
    # Rendering
    # ------------------------------------------------------------------

    def render(self, max_entries: int = 10) -> str:
        """Render a compact text snapshot of the ledger.

        Args:
            max_entries: Maximum number of delegation entries to show in
                detail.  Older entries are collapsed to a one-line count.

        Returns:
            A multi-line status board string.
        """
        lines: list[str] = [
            "--- 📋 TASK LEDGER (auto-maintained) ---",
            f"Goal: {self.goal}",
        ]

        # Mission recap line
        lines.append(self.mission_recap())

        # Checklist section
        if self.checklist:
            lines.append("Checklist:")
            for item in self.checklist:
                icon = "✅" if item.done else "☐"
                lines.append(f"  {icon} {item.description}")

        if not self.delegations:
            lines.append("No delegations yet.")
            lines.append("---")
            return "\n".join(lines)

        # Collapse very old entries into a count if needed
        visible = self.delegations
        collapsed_count = 0
        if len(self.delegations) > max_entries:
            collapsed_count = len(self.delegations) - max_entries
            visible = self.delegations[-max_entries:]

        completed = sum(1 for d in self.delegations if d.status == DelegationStatus.COMPLETED)
        failed = sum(1 for d in self.delegations if d.status == DelegationStatus.FAILED)
        pending = sum(1 for d in self.delegations if d.status == DelegationStatus.PENDING)

        lines.append(
            f"Progress: {completed} done, {pending} in-progress, {failed} failed "
            f"/ {len(self.delegations)} total",
        )

        if collapsed_count:
            lines.append(f"  ({collapsed_count} earlier delegations omitted)")

        for rec in visible:
            icon = {"completed": "✅", "failed": "❌", "pending": "⏳"}[rec.status.value]
            summary_brief = rec.summary[:120].replace("\n", " ") if rec.summary else ""
            line = f"  {icon} {rec.agent} → {rec.task}"
            if summary_brief:
                line += f" — {summary_brief}"
            lines.append(line)

        lines.append("---")
        return "\n".join(lines)
