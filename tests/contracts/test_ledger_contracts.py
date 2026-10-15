"""Contract tests for TaskLedger records (DelegationRecord, ChecklistItem, ProgressCounts).

These tests validate that the serialised shapes of DelegationRecord, ChecklistItem,
ProgressCounts, and TaskLedger conform to their published JSON Schema contracts.

Consumers include:
- The orchestrator execution pipeline (reads delegation records for completion assessment)
- The orchestrator event layer (emits events based on ledger state)
- The CLI renderer (formats ledger output for user display)
- Future persistence/serialization paths

Current limitation: these types are plain dataclasses without to_dict().
We use serialize_contract_value() which handles asdict() + enum conversion.
"""

from __future__ import annotations

from dataclasses import asdict

from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    ProgressCounts,
    TaskLedger,
)
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value

# ---------------------------------------------------------------------------
# ChecklistItem contracts
# ---------------------------------------------------------------------------


class TestChecklistItemContract:
    """ChecklistItem serialised shape must match its contract."""

    def test_default_not_done_matches_contract(self, contract_suite: object) -> None:
        """Default ChecklistItem (not done)."""
        item = ChecklistItem(description="Write unit tests")
        payload = serialize_contract_value(item)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/checklist_item",
        )

    def test_done_matches_contract(self, contract_suite: object) -> None:
        """ChecklistItem marked as done."""
        item = ChecklistItem(description="Refactor parser module", done=True)
        payload = serialize_contract_value(item)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/checklist_item",
        )

    def test_multiple_items_all_match_contract(self, contract_suite: object) -> None:
        """Multiple checklist items in various states."""
        items = [
            ChecklistItem(description="Task A", done=True),
            ChecklistItem(description="Task B", done=False),
            ChecklistItem(description="Task C", done=True),
        ]
        for item in items:
            payload = serialize_contract_value(item)
            assert_contract_matches(
                contract_suite=contract_suite,
                payload=payload,
                schema_name="runtime/checklist_item",
            )

    def test_description_with_special_chars_matches_contract(self, contract_suite: object) -> None:
        """Description with special characters should still match."""
        item = ChecklistItem(
            description="Handle edge-case: input/output buffer overflow (max 1024 KiB)",
            done=True,
        )
        payload = serialize_contract_value(item)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/checklist_item",
        )


# ---------------------------------------------------------------------------
# DelegationRecord contracts
# ---------------------------------------------------------------------------


class TestDelegationRecordContract:
    """DelegationRecord serialised shape must match its contract."""

    def test_pending_delegation_matches_contract(self, contract_suite: object) -> None:
        """DelegationRecord in default PENDING state."""
        record = DelegationRecord(agent="coder", task="Write CSV parser")
        payload = serialize_contract_value(record)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/delegation_record",
        )

    def test_completed_delegation_matches_contract(self, contract_suite: object) -> None:
        """DelegationRecord marked as COMPLETED with a summary."""
        record = DelegationRecord(
            agent="coder",
            task="Write CSV parser",
            status=DelegationStatus.COMPLETED,
            summary="Implemented parser with pandas backend, tests passing.",
        )
        payload = serialize_contract_value(record)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/delegation_record",
        )

    def test_failed_delegation_matches_contract(self, contract_suite: object) -> None:
        """DelegationRecord marked as FAILED with a reason."""
        record = DelegationRecord(
            agent="data_engineer",
            task="Optimize query pipeline",
            status=DelegationStatus.FAILED,
            summary="Insufficient memory on target node",
        )
        payload = serialize_contract_value(record)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/delegation_record",
        )

    def test_empty_summary_matches_contract(self, contract_suite: object) -> None:
        """DelegationRecord with default empty summary."""
        record = DelegationRecord(
            agent="reviewer",
            task="Review PR #42",
            status=DelegationStatus.PENDING,
            summary="",
        )
        payload = serialize_contract_value(record)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/delegation_record",
        )

    def test_long_summary_truncated_matches_contract(self, contract_suite: object) -> None:
        """DelegationRecord summary respects MAX_DELEGATION_SUMMARY_LENGTH."""
        long_summary = "x" * 600  # Exceeds 500-char limit
        record = DelegationRecord(
            agent="coder",
            task="Write large module",
            status=DelegationStatus.COMPLETED,
            summary=long_summary,
        )
        # Simulate what the ledger does: truncate at MAX_DELEGATION_SUMMARY_LENGTH
        from henchman.agents.ledger import MAX_DELEGATION_SUMMARY_LENGTH

        record.summary = long_summary[:MAX_DELEGATION_SUMMARY_LENGTH]
        payload = serialize_contract_value(record)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/delegation_record",
        )
        assert len(payload["summary"]) == MAX_DELEGATION_SUMMARY_LENGTH


# ---------------------------------------------------------------------------
# ProgressCounts contracts
# ---------------------------------------------------------------------------


class TestProgressCountsContract:
    """ProgressCounts serialised shape must match its contract."""

    def test_zero_counts_matches_contract(self, contract_suite: object) -> None:
        """ProgressCounts with all zeros."""
        counts = ProgressCounts(completed=0, pending=0, failed=0, total=0)
        payload = serialize_contract_value(counts)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/progress_counts",
        )

    def test_mixed_counts_matches_contract(self, contract_suite: object) -> None:
        """ProgressCounts with mixed non-zero values."""
        counts = ProgressCounts(completed=5, pending=3, failed=1, total=9)
        payload = serialize_contract_value(counts)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/progress_counts",
        )

    def test_all_completed_matches_contract(self, contract_suite: object) -> None:
        """ProgressCounts with all completed."""
        counts = ProgressCounts(completed=10, pending=0, failed=0, total=10)
        payload = serialize_contract_value(counts)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/progress_counts",
        )

    def test_large_counts_matches_contract(self, contract_suite: object) -> None:
        """ProgressCounts with large numbers."""
        counts = ProgressCounts(completed=1000, pending=500, failed=50, total=1550)
        payload = serialize_contract_value(counts)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/progress_counts",
        )


# ---------------------------------------------------------------------------
# TaskLedger contracts
# ---------------------------------------------------------------------------


class TestTaskLedgerContract:
    """TaskLedger serialised shape must match its contract."""

    def test_empty_ledger_matches_contract(self, contract_suite: object) -> None:
        """Empty TaskLedger with no checklist or delegations."""
        ledger = TaskLedger(goal="Implement feature X")
        payload = serialize_contract_value(ledger)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/task_ledger",
        )

    def test_populated_ledger_matches_contract(self, contract_suite: object) -> None:
        """Fully-populated TaskLedger with checklist items and delegations."""
        ledger = TaskLedger(goal="Build authentication module")

        # Add checklist items
        ledger.add_checklist_item("Design auth interface")
        ledger.add_checklist_item("Implement JWT flow")
        ledger.add_checklist_item("Add tests")
        ledger.check_item(0)

        # Add delegations in various states
        rec1 = ledger.add_delegation("coder", "Write auth interface")
        ledger.complete_delegation(rec1, "Interface written and reviewed")

        rec2 = ledger.add_delegation("coder", "Implement JWT tokens")
        ledger.fail_delegation(rec2, "Security review flagged concerns")

        ledger.add_delegation("tester", "Write integration tests")  # pending

        payload = serialize_contract_value(ledger)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/task_ledger",
        )

    def test_verified_ledger_matches_contract(self, contract_suite: object) -> None:
        """TaskLedger with verified=True."""
        ledger = TaskLedger(goal="Fix login bug")
        ledger.mark_verified()

        rec = ledger.add_delegation("coder", "Fix null pointer in auth")
        ledger.complete_delegation(rec, "Bug fixed, tests passing")

        payload = serialize_contract_value(ledger)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/task_ledger",
        )

    def test_ledger_via_asdict_matches_contract(self, contract_suite: object) -> None:
        """Verify asdict() produces contract-compliant payload (no to_dict() needed)."""
        ledger = TaskLedger(goal="Refactor logging")
        ledger.add_checklist_item("Extract base logger")
        ledger.check_item(0)
        rec = ledger.add_delegation("coder", "Extract logger class")
        ledger.complete_delegation(rec, "Done")

        # asdict() is what serialize_contract_value uses under the hood
        payload = asdict(ledger)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="runtime/task_ledger",
        )
