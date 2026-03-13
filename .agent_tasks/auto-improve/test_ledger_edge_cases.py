"""Additional edge case tests for ledger.py to improve coverage."""

import pytest
from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    ProgressCounts,
    TaskLedger,
    LedgerRenderer,
    _count_delegations_by_status_util,
    _get_delegation_counts_util,
)


class TestProgressCounts:
    """Tests for ProgressCounts class."""
    
    def test_format_progress_line(self) -> None:
        """Test format_progress_line method."""
        counts = ProgressCounts(completed=2, pending=1, failed=1, total=4)
        result = counts.format_progress_line()
        assert "2 done" in result
        assert "1 in-progress" in result
        assert "1 failed" in result
        assert "4 total" in result
    
    def test_repr(self) -> None:
        """Test __repr__ method."""
        counts = ProgressCounts(completed=2, pending=1, failed=1, total=4)
        result = repr(counts)
        assert "ProgressCounts" in result
        assert "completed=2" in result
        assert "pending=1" in result
        assert "failed=1" in result
        assert "total=4" in result


class TestChecklistItem:
    """Tests for ChecklistItem class."""
    
    def test_repr_done(self) -> None:
        """Test __repr__ when item is done."""
        item = ChecklistItem(description="Test", done=True)
        result = repr(item)
        assert "✅" in result
        assert "Test" in result
    
    def test_repr_not_done(self) -> None:
        """Test __repr__ when item is not done."""
        item = ChecklistItem(description="Test", done=False)
        result = repr(item)
        assert "☐" in result
        assert "Test" in result


class TestDelegationRecord:
    """Tests for DelegationRecord class."""
    
    def test_repr_short_summary(self) -> None:
        """Test __repr__ with short summary."""
        rec = DelegationRecord(
            agent="coder",
            task="Fix bug",
            status=DelegationStatus.COMPLETED,
            summary="Fixed it"
        )
        result = repr(rec)
        assert "DelegationRecord" in result
        assert "coder" in result
        assert "Fix bug" in result
        assert "completed" in result
        assert "Fixed it" in result
    
    def test_repr_long_summary(self) -> None:
        """Test __repr__ with long summary (truncated)."""
        long_summary = "x" * 100  # Longer than REPR_SUMMARY_TRUNCATE_LENGTH (50)
        rec = DelegationRecord(
            agent="coder",
            task="Fix bug",
            status=DelegationStatus.COMPLETED,
            summary=long_summary
        )
        result = repr(rec)
        assert "DelegationRecord" in result
        assert "coder" in result
        assert "Fix bug" in result
        assert "completed" in result
        assert "..." in result  # Indicates truncation


class TestLedgerRenderer:
    """Tests for LedgerRenderer class."""
    
    def test_render_method(self) -> None:
        """Test render method."""
        ledger = TaskLedger(goal="Test")
        renderer = LedgerRenderer(ledger)
        result = renderer.render()
        assert "📋 TASK LEDGER" in result
        assert "Test" in result
    
    def test_get_visible_delegations_edge_cases(self) -> None:
        """Test edge cases for get_visible_delegations."""
        delegations = [
            DelegationRecord(agent="a", task="t1"),
            DelegationRecord(agent="b", task="t2"),
            DelegationRecord(agent="c", task="t3"),
        ]
        
        # Test max_entries = 0
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 0)
        assert visible == []
        assert collapsed == 3
        
        # Test max_entries negative
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, -1)
        assert visible == []
        assert collapsed == 3
        
        # Test max_entries = len(delegations)
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 3)
        assert visible == delegations
        assert collapsed == 0
        
        # Test max_entries > len(delegations)
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 5)
        assert visible == delegations
        assert collapsed == 0
    
    def test_render_static(self) -> None:
        """Test static render method."""
        ledger = TaskLedger(goal="Test")
        result = LedgerRenderer.render_static(ledger)
        assert "📋 TASK LEDGER" in result
        assert "Test" in result


class TestTaskLedger:
    """Tests for TaskLedger class."""
    
    def test_repr(self) -> None:
        """Test __repr__ method."""
        ledger = TaskLedger(goal="Test goal")
        ledger.add_checklist_item("Item 1")
        ledger.add_delegation("coder", "Fix bug")
        
        result = repr(ledger)
        assert "TaskLedger" in result
        assert "Test goal" in result
        assert "1 items" in result  # checklist
        assert "1 records" in result  # delegations
        assert "verified=False" in result


class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_count_delegations_by_status_util(self) -> None:
        """Test _count_delegations_by_status_util."""
        delegations = [
            DelegationRecord(agent="a", task="t1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="b", task="t2", status=DelegationStatus.PENDING),
            DelegationRecord(agent="c", task="t3", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="d", task="t4", status=DelegationStatus.FAILED),
        ]
        
        completed = _count_delegations_by_status_util(delegations, DelegationStatus.COMPLETED)
        pending = _count_delegations_by_status_util(delegations, DelegationStatus.PENDING)
        failed = _count_delegations_by_status_util(delegations, DelegationStatus.FAILED)
        
        assert completed == 2
        assert pending == 1
        assert failed == 1
    
    def test_get_delegation_counts_util(self) -> None:
        """Test _get_delegation_counts_util."""
        delegations = [
            DelegationRecord(agent="a", task="t1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="b", task="t2", status=DelegationStatus.PENDING),
            DelegationRecord(agent="c", task="t3", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="d", task="t4", status=DelegationStatus.FAILED),
        ]
        
        completed, pending, failed = _get_delegation_counts_util(delegations)
        
        assert completed == 2
        assert pending == 1
        assert failed == 1