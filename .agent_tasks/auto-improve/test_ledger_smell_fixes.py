"""Test edge cases for ledger.py smell fixes."""

import pytest
from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    ProgressCounts,
    TaskLedger,
    LedgerRenderer,
)


class TestProgressCountsTypeHints:
    """Test type hints for ProgressCounts class."""
    
    def test_format_progress_line_return_type(self) -> None:
        """Test that format_progress_line has proper return type."""
        counts = ProgressCounts(completed=2, pending=1, failed=0, total=3)
        result = counts.format_progress_line()
        assert isinstance(result, str)
        assert "Progress:" in result


class TestLedgerRendererInit:
    """Test LedgerRenderer initialization edge cases."""
    
    def test_init_with_different_max_entries(self) -> None:
        """Test LedgerRenderer with various max_entries values."""
        ledger = TaskLedger(goal="Test")
        
        # Test default
        renderer1 = LedgerRenderer(ledger)
        assert renderer1.max_entries == 10
        
        # Test custom
        renderer2 = LedgerRenderer(ledger, max_entries=5)
        assert renderer2.max_entries == 5
        
        # Test zero (edge case)
        renderer3 = LedgerRenderer(ledger, max_entries=0)
        assert renderer3.max_entries == 0


class TestDuplicateCodeRefactoring:
    """Test that duplicate code patterns have been properly refactored."""
    
    def test_add_checklist_item_and_add_delegation_use_factory(self) -> None:
        """Test that both methods use the _add_item_factory helper."""
        ledger = TaskLedger(goal="Test")
        
        # Test checklist item
        checklist_item = ledger.add_checklist_item("Test item")
        assert isinstance(checklist_item, ChecklistItem)
        assert checklist_item.description == "Test item"
        assert len(ledger.checklist) == 1
        
        # Test delegation
        delegation = ledger.add_delegation("coder", "Fix bug")
        assert isinstance(delegation, DelegationRecord)
        assert delegation.agent == "coder"
        assert delegation.task == "Fix bug"
        assert len(ledger.delegations) == 1
        
        # Verify they use the same pattern
        assert ledger.checklist[0] is checklist_item
        assert ledger.delegations[0] is delegation
    
    def test_complete_and_fail_delegation_use_helper(self) -> None:
        """Test that complete_delegation and fail_delegation use _update_delegation."""
        ledger = TaskLedger(goal="Test")
        record = ledger.add_delegation("coder", "Fix bug")
        
        # Test complete_delegation
        ledger.complete_delegation(record, "Fixed successfully")
        assert record.status == DelegationStatus.COMPLETED
        assert record.summary == "Fixed successfully"
        
        # Test fail_delegation
        record2 = ledger.add_delegation("tester", "Run tests")
        ledger.fail_delegation(record2, "Tests failed")
        assert record2.status == DelegationStatus.FAILED
        assert record2.summary == "Tests failed"
    
    def test_count_utility_functions(self) -> None:
        """Test that count utility functions work correctly."""
        from henchman.agents.ledger import (
            _count_delegations_by_status_util,
            _get_delegation_counts_util,
        )
        
        delegations = [
            DelegationRecord(agent="a", task="1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="b", task="2", status=DelegationStatus.PENDING),
            DelegationRecord(agent="c", task="3", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="d", task="4", status=DelegationStatus.FAILED),
        ]
        
        # Test _count_delegations_by_status_util
        completed_count = _count_delegations_by_status_util(delegations, DelegationStatus.COMPLETED)
        assert completed_count == 2
        
        pending_count = _count_delegations_by_status_util(delegations, DelegationStatus.PENDING)
        assert pending_count == 1
        
        failed_count = _count_delegations_by_status_util(delegations, DelegationStatus.FAILED)
        assert failed_count == 1
        
        # Test _get_delegation_counts_util
        completed, pending, failed = _get_delegation_counts_util(delegations)
        assert completed == 2
        assert pending == 1
        assert failed == 1


class TestRenderMethodEdgeCases:
    """Test edge cases for render methods."""
    
    def test_render_empty_ledger(self) -> None:
        """Test rendering an empty ledger."""
        ledger = TaskLedger(goal="Empty test")
        result = ledger.render()
        assert "Goal: Empty test" in result
        assert "No delegations yet" in result
    
    def test_render_with_many_delegations(self) -> None:
        """Test rendering with more delegations than max_entries."""
        ledger = TaskLedger(goal="Many delegations")
        
        # Add 15 delegations
        for i in range(15):
            ledger.add_delegation(f"agent{i}", f"task{i}")
        
        # Render with default max_entries (10)
        result = ledger.render(max_entries=10)
        assert "(5 earlier delegations omitted)" in result
        
        # Render with max_entries=5
        result2 = ledger.render(max_entries=5)
        assert "(10 earlier delegations omitted)" in result2
    
    def test_render_with_checklist(self) -> None:
        """Test rendering with checklist items."""
        ledger = TaskLedger(goal="Checklist test")
        ledger.add_checklist_item("First item")
        ledger.add_checklist_item("Second item")
        ledger.check_item(0)  # Mark first as done
        
        result = ledger.render()
        assert "Checklist:" in result
        assert "✅ First item" in result
        assert "☐ Second item" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])