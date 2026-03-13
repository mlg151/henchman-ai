"""Edge case tests for ledger.py to improve test coverage and address code smells."""

import pytest
from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    TaskLedger,
    LedgerRenderer,
    ProgressCounts,
    _count_delegations_by_status_util,
    _get_delegation_counts_util,
)


class TestEdgeCases:
    """Edge case tests for ledger functionality."""

    def test_progress_counts_format_progress_line(self) -> None:
        """Test ProgressCounts.format_progress_line with various values."""
        # Test with zeros
        counts = ProgressCounts(completed=0, pending=0, failed=0, total=0)
        assert counts.format_progress_line() == "Progress: 0 done, 0 in-progress, 0 failed / 0 total"
        
        # Test with all completed
        counts = ProgressCounts(completed=5, pending=0, failed=0, total=5)
        assert counts.format_progress_line() == "Progress: 5 done, 0 in-progress, 0 failed / 5 total"
        
        # Test with mixed values
        counts = ProgressCounts(completed=2, pending=3, failed=1, total=6)
        assert counts.format_progress_line() == "Progress: 2 done, 3 in-progress, 1 failed / 6 total"

    def test_delegation_record_format_line_edge_cases(self) -> None:
        """Test DelegationRecord.format_line with edge cases."""
        # Test with empty summary
        rec = DelegationRecord(agent="coder", task="Fix bug", status=DelegationStatus.COMPLETED, summary="")
        line = rec.format_line()
        assert "coder → Fix bug" in line
        assert "—" not in line  # No summary separator when summary is empty
        
        # Test with very long summary
        long_summary = "x" * 200
        rec = DelegationRecord(agent="coder", task="Fix bug", status=DelegationStatus.COMPLETED, summary=long_summary)
        line = rec.format_line(max_summary_length=50)
        assert len(line.split("—")[1].strip()) <= 50  # Summary truncated
        
        # Test with newlines in summary
        rec = DelegationRecord(agent="coder", task="Fix bug", status=DelegationStatus.COMPLETED, summary="Line1\nLine2\nLine3")
        line = rec.format_line()
        assert "\n" not in line  # Newlines should be replaced with spaces

    def test_delegation_record_get_icon_edge_cases(self) -> None:
        """Test DelegationRecord._get_icon with all statuses."""
        rec_completed = DelegationRecord(agent="coder", task="Fix bug", status=DelegationStatus.COMPLETED)
        assert rec_completed._get_icon() == "✅"
        
        rec_failed = DelegationRecord(agent="coder", task="Fix bug", status=DelegationStatus.FAILED)
        assert rec_failed._get_icon() == "❌"
        
        rec_pending = DelegationRecord(agent="coder", task="Fix bug", status=DelegationStatus.PENDING)
        assert rec_pending._get_icon() == "⏳"

    def test_ledger_renderer_init_type_hints(self) -> None:
        """Test LedgerRenderer.__init__ with various max_entries values."""
        ledger = TaskLedger(goal="Test")
        
        # Test default max_entries
        renderer = LedgerRenderer(ledger)
        assert renderer.max_entries == 10
        
        # Test custom max_entries
        renderer = LedgerRenderer(ledger, max_entries=5)
        assert renderer.max_entries == 5
        
        # Test zero max_entries (edge case)
        renderer = LedgerRenderer(ledger, max_entries=0)
        assert renderer.max_entries == 0

    def test_ledger_renderer_render_type_hints(self) -> None:
        """Test LedgerRenderer.render returns string."""
        ledger = TaskLedger(goal="Test")
        renderer = LedgerRenderer(ledger)
        result = renderer.render()
        assert isinstance(result, str)
        assert "📋 TASK LEDGER" in result

    def test_get_visible_delegations_edge_cases(self) -> None:
        """Test LedgerRenderer.get_visible_delegations with edge cases."""
        delegations = [
            DelegationRecord(agent=f"agent{i}", task=f"task{i}", status=DelegationStatus.COMPLETED)
            for i in range(15)
        ]
        
        # Test max_entries = 0
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 0)
        assert visible == []
        assert collapsed == 15
        
        # Test max_entries negative
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, -5)
        assert visible == []
        assert collapsed == 15
        
        # Test max_entries equals list length
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 15)
        assert len(visible) == 15
        assert collapsed == 0
        
        # Test max_entries greater than list length
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 20)
        assert len(visible) == 15
        assert collapsed == 0

    def test_format_progress_line_static_method(self) -> None:
        """Test ProgressCounts.format_progress_line method (replaces removed static method)."""
        counts = ProgressCounts(completed=2, pending=3, failed=1, total=6)
        result = counts.format_progress_line()
        assert result == "Progress: 2 done, 3 in-progress, 1 failed / 6 total"

    def test_utility_functions_type_hints(self) -> None:
        """Test utility functions have proper return types."""
        delegations = [
            DelegationRecord(agent="a", task="t1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="b", task="t2", status=DelegationStatus.PENDING),
            DelegationRecord(agent="c", task="t3", status=DelegationStatus.FAILED),
        ]
        
        # Test _count_delegations_by_status_util
        count = _count_delegations_by_status_util(delegations, DelegationStatus.COMPLETED)
        assert isinstance(count, int)
        assert count == 1
        
        # Test _get_delegation_counts_util
        completed, pending, failed = _get_delegation_counts_util(delegations)
        assert isinstance(completed, int)
        assert isinstance(pending, int)
        assert isinstance(failed, int)
        assert (completed, pending, failed) == (1, 1, 1)

    def test_task_ledger_add_item_factory_edge_cases(self) -> None:
        """Test TaskLedger._add_item_factory with edge cases."""
        ledger = TaskLedger(goal="Test")
        
        # Test with empty list
        empty_list: list[str] = []
        result = ledger._add_item_factory(empty_list, lambda x: x, "test")
        assert result == "test"
        assert empty_list == ["test"]
        
        # Test with factory that takes kwargs
        def create_item(name: str, value: int = 0) -> dict[str, int]:
            return {name: value}
        
        item_list: list[dict[str, int]] = []
        result = ledger._add_item_factory(item_list, create_item, "test", value=42)
        assert result == {"test": 42}
        assert item_list == [{"test": 42}]

    def test_task_ledger_check_item_edge_cases(self) -> None:
        """Test TaskLedger.check_item with edge cases."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        ledger.add_checklist_item("Item 2")
        
        # Test negative index
        with pytest.raises(IndexError):
            ledger.check_item(-1)
        
        # Test index out of range
        with pytest.raises(IndexError):
            ledger.check_item(2)
        
        # Test valid index
        ledger.check_item(0)
        assert ledger.checklist[0].done is True
        assert ledger.checklist[1].done is False

    def test_task_ledger_update_delegation_edge_cases(self) -> None:
        """Test TaskLedger._update_delegation with edge cases."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "Fix bug")
        
        # Test with empty summary
        ledger._update_delegation(rec, DelegationStatus.COMPLETED, "")
        assert rec.status == DelegationStatus.COMPLETED
        assert rec.summary == ""
        
        # Test with very long summary (should be truncated)
        long_summary = "x" * 1000
        ledger._update_delegation(rec, DelegationStatus.FAILED, long_summary)
        assert rec.status == DelegationStatus.FAILED
        assert len(rec.summary) == 500  # MAX_DELEGATION_SUMMARY_LENGTH

    def test_task_ledger_mission_recap_edge_cases(self) -> None:
        """Test TaskLedger.mission_recap with edge cases."""
        # Test with no checklist and no delegations
        ledger = TaskLedger(goal="Test")
        recap = ledger.mission_recap()
        assert "0 delegations done" in recap
        assert "0 pending" in recap
        assert "0 failed" in recap
        assert "checklist items" not in recap
        
        # Test with checklist but no delegations
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        ledger.add_checklist_item("Item 2")
        ledger.check_item(0)
        recap = ledger.mission_recap()
        assert "1/2 checklist items done" in recap
        
        # Test verified status
        ledger.mark_verified()
        recap = ledger.mission_recap()
        assert "✅ verified" in recap

    def test_task_ledger_render_edge_cases(self) -> None:
        """Test TaskLedger.render with edge cases."""
        # Test with max_entries = 0
        ledger = TaskLedger(goal="Test")
        for i in range(5):
            rec = ledger.add_delegation(f"agent{i}", f"task{i}")
            ledger.complete_delegation(rec, f"done{i}")
        
        result = ledger.render(max_entries=0)
        assert "5 earlier delegations omitted" in result
        
        # Test with max_entries negative
        result = ledger.render(max_entries=-5)
        assert "5 earlier delegations omitted" in result