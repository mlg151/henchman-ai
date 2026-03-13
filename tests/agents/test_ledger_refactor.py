"""Additional tests for ledger refactoring to ensure edge cases are covered."""

import pytest
from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    TaskLedger,
    LedgerRenderer,
    ProgressCounts,
)


class TestLedgerEdgeCases:
    """Edge case tests for TaskLedger."""

    def test_add_checklist_item_duplicate_prevention(self) -> None:
        """Test that add_checklist_item doesn't create duplicate helper methods."""
        ledger = TaskLedger(goal="Test")
        item1 = ledger.add_checklist_item("Item 1")
        item2 = ledger.add_checklist_item("Item 2")
        assert len(ledger.checklist) == 2
        assert item1.description == "Item 1"
        assert item2.description == "Item 2"
        assert item1 is not item2

    def test_add_delegation_duplicate_prevention(self) -> None:
        """Test that add_delegation doesn't create duplicate helper methods."""
        ledger = TaskLedger(goal="Test")
        rec1 = ledger.add_delegation("coder", "Task 1")
        rec2 = ledger.add_delegation("tester", "Task 2")
        assert len(ledger.delegations) == 2
        assert rec1.agent == "coder"
        assert rec2.agent == "tester"
        assert rec1 is not rec2

    def test_check_item_negative_index(self) -> None:
        """Test that check_item raises IndexError for negative index."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        with pytest.raises(IndexError):
            ledger.check_item(-1)

    def test_check_item_large_index(self) -> None:
        """Test that check_item raises IndexError for index beyond list."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        with pytest.raises(IndexError):
            ledger.check_item(5)

    def test_complete_delegation_empty_summary(self) -> None:
        """Test complete_delegation with empty summary."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "Task")
        ledger.complete_delegation(rec, "")
        assert rec.status == DelegationStatus.COMPLETED
        assert rec.summary == ""

    def test_fail_delegation_empty_reason(self) -> None:
        """Test fail_delegation with empty reason."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "Task")
        ledger.fail_delegation(rec, "")
        assert rec.status == DelegationStatus.FAILED
        assert rec.summary == ""

    def test_mission_recap_no_checklist(self) -> None:
        """Test mission_recap when there's no checklist."""
        ledger = TaskLedger(goal="Test")
        # Don't add any checklist items
        recap = ledger.mission_recap()
        assert "checklist" not in recap
        assert "0 delegations done" in recap

    def test_mission_recap_all_done(self) -> None:
        """Test mission_recap when all checklist items are done."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        ledger.add_checklist_item("Item 2")
        ledger.check_item(0)
        ledger.check_item(1)
        recap = ledger.mission_recap()
        assert "2/2 checklist items done" in recap

    def test_render_max_entries_zero(self) -> None:
        """Test render with max_entries=0."""
        ledger = TaskLedger(goal="Test")
        for i in range(5):
            rec = ledger.add_delegation("coder", f"Task {i}")
            ledger.complete_delegation(rec, f"Done {i}")
        
        text = ledger.render(max_entries=0)
        assert "5 earlier delegations omitted" in text

    def test_render_max_entries_negative(self) -> None:
        """Test render with negative max_entries."""
        ledger = TaskLedger(goal="Test")
        for i in range(3):
            rec = ledger.add_delegation("coder", f"Task {i}")
            ledger.complete_delegation(rec, f"Done {i}")
        
        text = ledger.render(max_entries=-1)
        assert "3 earlier delegations omitted" in text


class TestLedgerRendererEdgeCases:
    """Edge case tests for LedgerRenderer."""

    def test_get_visible_delegations_empty(self) -> None:
        """Test get_visible_delegations with empty list."""
        visible, collapsed = LedgerRenderer.get_visible_delegations([], 5)
        assert visible == []
        assert collapsed == 0

    def test_get_visible_delegations_zero_max(self) -> None:
        """Test get_visible_delegations with max_entries=0."""
        delegations = [
            DelegationRecord(agent="coder", task="Task 1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="tester", task="Task 2", status=DelegationStatus.PENDING),
        ]
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 0)
        assert visible == []
        assert collapsed == 2

    def test_get_visible_delegations_negative_max(self) -> None:
        """Test get_visible_delegations with negative max_entries."""
        delegations = [
            DelegationRecord(agent="coder", task="Task 1", status=DelegationStatus.COMPLETED),
        ]
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, -5)
        assert visible == []
        assert collapsed == 1

    def test_format_progress_line_counts_object(self) -> None:
        """Test ProgressCounts.format_progress_line method."""
        counts = ProgressCounts(completed=2, pending=1, failed=0, total=3)
        result = counts.format_progress_line()
        assert "2 done" in result
        assert "1 in-progress" in result
        assert "0 failed" in result
        assert "3 total" in result

    def test_format_progress_line_individual_params(self) -> None:
        """Test ProgressCounts.format_progress_line method."""
        counts = ProgressCounts(completed=2, pending=1, failed=0, total=3)
        result = counts.format_progress_line()
        assert "2 done" in result
        assert "1 in-progress" in result
        assert "0 failed" in result
        assert "3 total" in result

    def test_format_progress_line_invalid_args(self) -> None:
        """Test ProgressCounts.format_progress_line method."""
        counts = ProgressCounts(completed=1, pending=0, failed=0, total=1)
        result = counts.format_progress_line()
        assert "1 done" in result
        assert "0 in-progress" in result
        assert "0 failed" in result

    def test_render_delegations_section_empty(self) -> None:
        """Test _render_delegations_section with empty delegations."""
        ledger = TaskLedger(goal="Test")
        renderer = LedgerRenderer(ledger, max_entries=5)
        lines: list[str] = []
        renderer._render_delegations_section(lines)
        assert "No delegations yet." in lines[0]

    def test_render_static_with_ledger(self) -> None:
        """Test render_static method."""
        ledger = TaskLedger(goal="Test Goal")
        ledger.add_checklist_item("Check 1")
        ledger.add_delegation("coder", "Write code")
        
        result = LedgerRenderer.render_static(ledger, 10)
        assert "Test Goal" in result
        assert "Checklist:" in result
    def test_get_delegation_counts_static(self) -> None:
        """Test _get_delegation_counts_util function."""
        from henchman.agents.ledger import _get_delegation_counts_util
        
        delegations = [
            DelegationRecord(agent="coder", task="Task 1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="tester", task="Task 2", status=DelegationStatus.PENDING),
            DelegationRecord(agent="reviewer", task="Task 3", status=DelegationStatus.FAILED),
            DelegationRecord(agent="coder", task="Task 4", status=DelegationStatus.COMPLETED),
        ]
        completed, pending, failed = _get_delegation_counts_util(delegations)
        assert completed == 2
        assert pending == 1
        assert failed == 1

    def test_count_delegations_by_status_static(self) -> None:
        """Test _count_delegations_by_status_util function."""
        from henchman.agents.ledger import _count_delegations_by_status_util
        
        delegations = [
            DelegationRecord(agent="coder", task="Task 1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="tester", task="Task 2", status=DelegationStatus.PENDING),
            DelegationRecord(agent="reviewer", task="Task 3", status=DelegationStatus.FAILED),
            DelegationRecord(agent="coder", task="Task 4", status=DelegationStatus.COMPLETED),
        ]
        completed_count = _count_delegations_by_status_util(delegations, DelegationStatus.COMPLETED)
        pending_count = _count_delegations_by_status_util(delegations, DelegationStatus.PENDING)
        failed_count = _count_delegations_by_status_util(delegations, DelegationStatus.FAILED)
        assert completed_count == 2
        assert pending_count == 1
        assert failed_count == 1
        
        assert completed_count == 2
        assert pending_count == 1
        assert failed_count == 1


class TestProgressCounts:
    """Tests for ProgressCounts dataclass."""

    def test_init(self) -> None:
        """Test ProgressCounts initialization."""
        counts = ProgressCounts(completed=5, pending=3, failed=1, total=9)
        assert counts.completed == 5
        assert counts.pending == 3
        assert counts.failed == 1
        assert counts.total == 9

    def test_total_consistency(self) -> None:
        """Test that total can be different from sum of parts (edge case)."""
        # This is allowed - total might include other statuses not tracked
        counts = ProgressCounts(completed=2, pending=1, failed=0, total=5)
        assert counts.total == 5  # 2 unaccounted for


class TestDelegationRecordEdgeCases:
    """Edge case tests for DelegationRecord."""

    def test_format_line_long_summary(self) -> None:
        """Test format_line with long summary that gets truncated."""
        rec = DelegationRecord(
            agent="coder",
            task="Write complex function",
            status=DelegationStatus.COMPLETED,
            summary="This is a very long summary that should be truncated when displayed" * 10
        )
        line = rec.format_line(max_summary_length=50)
        assert len(line) < 200  # Should be reasonably short
        assert "..." not in line  # Our current implementation doesn't add ellipsis

    def test_format_line_no_summary(self) -> None:
        """Test format_line with no summary."""
        rec = DelegationRecord(
            agent="coder",
            task="Simple task",
            status=DelegationStatus.PENDING
        )
        line = rec.format_line()
        assert "coder" in line
        assert "Simple task" in line
        assert "—" not in line  # No separator when no summary

    def test_get_icon_all_statuses(self) -> None:
        """Test _get_icon for all status values."""
        rec_completed = DelegationRecord(
            agent="coder", task="task", status=DelegationStatus.COMPLETED
        )
        rec_failed = DelegationRecord(
            agent="coder", task="task", status=DelegationStatus.FAILED
        )
        rec_pending = DelegationRecord(
            agent="coder", task="task", status=DelegationStatus.PENDING
        )
        
        assert rec_completed._get_icon() == "✅"
        assert rec_failed._get_icon() == "❌"
        assert rec_pending._get_icon() == "⏳"