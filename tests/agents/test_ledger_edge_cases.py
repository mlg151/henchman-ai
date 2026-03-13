"""Edge case tests for ledger.py to improve coverage and catch regressions."""

import pytest
from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    ProgressCounts,
    LedgerRenderer,
    TaskLedger,
    DEFAULT_MAX_SUMMARY_LENGTH,
    MAX_DELEGATION_SUMMARY_LENGTH,
)


class TestProgressCountsEdgeCases:
    """Edge case tests for ProgressCounts class."""
    
    def test_progress_counts_zero_values(self) -> None:
        """Test ProgressCounts with zero values."""
        counts = ProgressCounts(completed=0, pending=0, failed=0, total=0)
        assert counts.format_progress_line() == "Progress: 0 done, 0 in-progress, 0 failed / 0 total"
        assert repr(counts) == "ProgressCounts(completed=0, pending=0, failed=0, total=0)"
    
    def test_progress_counts_large_values(self) -> None:
        """Test ProgressCounts with large values."""
        counts = ProgressCounts(completed=100, pending=50, failed=25, total=175)
        assert counts.format_progress_line() == "Progress: 100 done, 50 in-progress, 25 failed / 175 total"
        assert repr(counts) == "ProgressCounts(completed=100, pending=50, failed=25, total=175)"


class TestChecklistItemEdgeCases:
    """Edge case tests for ChecklistItem class."""
    
    def test_checklist_item_empty_description(self) -> None:
        """Test ChecklistItem with empty description."""
        item = ChecklistItem(description="", done=True)
        assert item.description == ""
        assert item.done is True
        assert repr(item) == "ChecklistItem(✅ '')"
    
    def test_checklist_item_long_description(self) -> None:
        """Test ChecklistItem with long description."""
        long_desc = "a" * 1000
        item = ChecklistItem(description=long_desc, done=False)
        assert item.description == long_desc
        assert item.done is False
        # Check repr doesn't truncate
        assert long_desc in repr(item)


class TestDelegationRecordEdgeCases:
    """Edge case tests for DelegationRecord class."""
    
    def test_delegation_record_empty_strings(self) -> None:
        """Test DelegationRecord with empty strings."""
        rec = DelegationRecord(agent="", task="", status=DelegationStatus.PENDING, summary="")
        assert rec.agent == ""
        assert rec.task == ""
        assert rec.summary == ""
        assert rec.status == DelegationStatus.PENDING
        assert rec._get_icon() == "⏳"
    
    def test_delegation_record_long_summary(self) -> None:
        """Test DelegationRecord with summary longer than 50 chars."""
        long_summary = "x" * 100
        rec = DelegationRecord(agent="coder", task="fix", summary=long_summary)
        # __repr__ should truncate to 50 chars with ellipsis
        repr_str = repr(rec)
        assert "..." in repr_str
        assert len(rec.summary) == 100
    
    def test_delegation_record_format_line_empty_summary(self) -> None:
        """Test format_line with empty summary."""
        rec = DelegationRecord(agent="coder", task="fix bug", status=DelegationStatus.COMPLETED, summary="")
        line = rec.format_line()
        assert "coder → fix bug" in line
        assert "—" not in line  # No separator when no summary
    
    def test_delegation_record_format_line_newlines(self) -> None:
        """Test format_line with newlines in summary."""
        rec = DelegationRecord(
            agent="coder", 
            task="fix bug", 
            status=DelegationStatus.COMPLETED, 
            summary="First line\nSecond line\nThird line"
        )
        line = rec.format_line(max_summary_length=50)
        # Newlines should be replaced with spaces
        assert "\n" not in line
        assert "First line Second line Third line" in line or "First line" in line
    
    def test_delegation_record_format_line_custom_length(self) -> None:
        """Test format_line with custom max_summary_length."""
        rec = DelegationRecord(
            agent="coder", 
            task="fix bug", 
            status=DelegationStatus.COMPLETED, 
            summary="A very long summary that should be truncated"
        )
        line_short = rec.format_line(max_summary_length=10)
        line_long = rec.format_line(max_summary_length=100)
        # Short version should be truncated
        assert len(line_short.split("—")[-1].strip()) <= 10 if "—" in line_short else True
        # Long version should not truncate (summary is 45 chars)
        assert "A very long summary that should be truncated" in line_long


class TestLedgerRendererEdgeCases:
    """Edge case tests for LedgerRenderer class."""
    
    def test_renderer_empty_ledger(self) -> None:
        """Test rendering an empty ledger."""
        ledger = TaskLedger(goal="Test goal")
        renderer = LedgerRenderer(ledger)
        output = renderer.render()
        assert "TASK LEDGER" in output
        assert "Goal: Test goal" in output
        assert "No delegations yet." in output
        assert "Checklist:" not in output  # No checklist items
    
    def test_renderer_max_entries_zero(self) -> None:
        """Test renderer with max_entries=0."""
        ledger = TaskLedger(goal="Test")
        # Add some delegations
        for i in range(5):
            ledger.add_delegation(f"agent{i}", f"task{i}")
        
        renderer = LedgerRenderer(ledger, max_entries=0)
        output = renderer.render()
        # Should show all delegations collapsed
        assert "(5 earlier delegations omitted)" in output
    
    def test_renderer_max_entries_negative(self) -> None:
        """Test renderer with negative max_entries."""
        ledger = TaskLedger(goal="Test")
        # Add some delegations
        for i in range(3):
            ledger.add_delegation(f"agent{i}", f"task{i}")
        
        renderer = LedgerRenderer(ledger, max_entries=-1)
        output = renderer.render()
        # Should show all delegations collapsed
        assert "(3 earlier delegations omitted)" in output
    
    def test_renderer_static_method(self) -> None:
        """Test the static render method."""
        ledger = TaskLedger(goal="Static test")
        ledger.add_checklist_item("Item 1")
        ledger.add_delegation("agent", "task")
        
        output = LedgerRenderer.render_static(ledger)
        assert "TASK LEDGER" in output
        assert "Goal: Static test" in output
        assert "Checklist:" in output
        assert "Item 1" in output
    
    def test_get_visible_delegations_edge_cases(self) -> None:
        """Test edge cases for get_visible_delegations."""
        # Test with empty list
        visible, collapsed = LedgerRenderer.get_visible_delegations([], 5)
        assert visible == []
        assert collapsed == 0
        
        # Test with single item
        rec = DelegationRecord(agent="a", task="t")
        visible, collapsed = LedgerRenderer.get_visible_delegations([rec], 5)
        assert visible == [rec]
        assert collapsed == 0
        
        # Test with exact max_entries
        delegations = [DelegationRecord(agent=f"a{i}", task=f"t{i}") for i in range(5)]
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 5)
        assert visible == delegations
        assert collapsed == 0
        
        # Test with more than max_entries (should show most recent)
        delegations = [DelegationRecord(agent=f"a{i}", task=f"t{i}") for i in range(10)]
        visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 3)
        assert len(visible) == 3
        assert collapsed == 7
        # Should show the last 3
        assert visible == delegations[-3:]


class TestTaskLedgerEdgeCases:
    """Edge case tests for TaskLedger class."""
    
    def test_add_checklist_item_duplicate(self) -> None:
        """Test adding duplicate checklist items."""
        ledger = TaskLedger(goal="Test")
        item1 = ledger.add_checklist_item("Same item")
        item2 = ledger.add_checklist_item("Same item")  # Should be allowed
        assert len(ledger.checklist) == 2
        # They should be different objects even if they have the same content
        assert item1 is not item2
    
    def test_check_item_invalid_index(self) -> None:
        """Test checking item with invalid index."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        
        # Negative index should raise
        with pytest.raises(IndexError):
            ledger.check_item(-1)
        
        # Index too large should raise
        with pytest.raises(IndexError):
            ledger.check_item(1)
        
        # Valid index should work
        ledger.check_item(0)
        assert ledger.checklist[0].done is True
    
    def test_complete_delegation_long_summary(self) -> None:
        """Test completing delegation with very long summary."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "fix bug")
        
        # Create summary longer than MAX_DELEGATION_SUMMARY_LENGTH
        long_summary = "x" * (MAX_DELEGATION_SUMMARY_LENGTH + 100)
        ledger.complete_delegation(rec, long_summary)
        
        assert rec.status == DelegationStatus.COMPLETED
        assert len(rec.summary) == MAX_DELEGATION_SUMMARY_LENGTH
        assert rec.summary == "x" * MAX_DELEGATION_SUMMARY_LENGTH
    
    def test_fail_delegation_empty_reason(self) -> None:
        """Test failing delegation with empty reason."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "fix bug")
        
        ledger.fail_delegation(rec, "")
        
        assert rec.status == DelegationStatus.FAILED
        assert rec.summary == ""
    
    def test_mission_recap_edge_cases(self) -> None:
        """Test mission_recap with various edge cases."""
        # Empty ledger
        ledger = TaskLedger(goal="Test")
        recap = ledger.mission_recap()
        assert "Mission [⚠️ unverified]" in recap
        assert "0 delegations done" in recap
        
        # Ledger with only checklist
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        ledger.check_item(0)
        recap = ledger.mission_recap()
        assert "1/1 checklist items done" in recap
        
        # Verified ledger
        ledger = TaskLedger(goal="Test")
        ledger.mark_verified()
        recap = ledger.mission_recap()
        assert "Mission [✅ verified]" in recap
    
    def test_render_custom_max_entries(self) -> None:
        """Test ledger.render() with custom max_entries."""
        ledger = TaskLedger(goal="Test")
        for i in range(10):
            ledger.add_delegation(f"agent{i}", f"task{i}")
        
        # Render with small max_entries
        output = ledger.render(max_entries=2)
        assert "(8 earlier delegations omitted)" in output
        
        # Render with large max_entries
        output = ledger.render(max_entries=20)
        assert "earlier delegations omitted" not in output  # Should show all 10
    
    def test_ledger_repr(self) -> None:
        """Test ledger.__repr__ method."""
        ledger = TaskLedger(goal="Test goal")
        repr_str = repr(ledger)
        assert "TaskLedger" in repr_str
        assert "goal='Test goal'" in repr_str
        assert "checklist=0 items" in repr_str
        assert "delegations=0 records" in repr_str
        assert "verified=False" in repr_str