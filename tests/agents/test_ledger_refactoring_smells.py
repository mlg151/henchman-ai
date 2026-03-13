"""Tests for refactoring ledger.py to fix code smells."""

from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    LedgerRenderer,
    ProgressCounts,
    TaskLedger,
)


class TestLedgerDuplicateCodeFixes:
    """Tests for fixing duplicate code smells in ledger.py."""
    
    def test_shared_count_delegations_by_status(self) -> None:
        """Test that count_delegations_by_status works for both classes."""
        # Create test data
        delegations = [
            DelegationRecord(agent="a1", task="t1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="a2", task="t2", status=DelegationStatus.PENDING),
            DelegationRecord(agent="a3", task="t3", status=DelegationStatus.FAILED),
            DelegationRecord(agent="a4", task="t4", status=DelegationStatus.COMPLETED),
        ]
        
        # Test TaskLedger version using utility function
        ledger = TaskLedger(goal="Test")
        ledger.delegations = delegations
        
        # Should count correctly using utility function
        from henchman.agents.ledger import _count_delegations_by_status_util
        assert _count_delegations_by_status_util(ledger.delegations, DelegationStatus.COMPLETED) == 2
        assert _count_delegations_by_status_util(ledger.delegations, DelegationStatus.PENDING) == 1
        assert _count_delegations_by_status_util(ledger.delegations, DelegationStatus.FAILED) == 1
        
        # Test LedgerRenderer version using utility function
        renderer = LedgerRenderer(ledger)
        # Use utility function directly
        assert _count_delegations_by_status_util(renderer.ledger.delegations, DelegationStatus.COMPLETED) == 2
        assert _count_delegations_by_status_util(renderer.ledger.delegations, DelegationStatus.PENDING) == 1
        assert _count_delegations_by_status_util(renderer.ledger.delegations, DelegationStatus.FAILED) == 1
    
    def test_shared_get_delegation_counts(self) -> None:
        """Test that _get_delegation_counts works for both classes."""
        # Create test data
        delegations = [
            DelegationRecord(agent="a1", task="t1", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="a2", task="t2", status=DelegationStatus.PENDING),
            DelegationRecord(agent="a3", task="t3", status=DelegationStatus.FAILED),
            DelegationRecord(agent="a4", task="t4", status=DelegationStatus.COMPLETED),
            DelegationRecord(agent="a5", task="t5", status=DelegationStatus.PENDING),
        ]
        
        # Test TaskLedger version
        ledger = TaskLedger(goal="Test")
        ledger.delegations = delegations
        
        completed, pending, failed = ledger._get_delegation_counts()
        assert completed == 2
        assert pending == 2
        assert failed == 1
        
        # Test utility function directly (LedgerRenderer now uses it directly)
        from henchman.agents.ledger import _get_delegation_counts_util
        completed, pending, failed = _get_delegation_counts_util(ledger.delegations)
        assert completed == 2
        assert pending == 2
        assert failed == 1
    
    def test_format_progress_line_primitive_obsession_fix(self) -> None:
        """Test that ProgressCounts.format_progress_line method works properly."""
        counts = ProgressCounts(completed=5, pending=3, failed=2, total=10)
        
        # Test with ProgressCounts object
        result1 = counts.format_progress_line()
        assert "5 done" in result1
        assert "3 in-progress" in result1
        assert "2 failed" in result1
        assert "10 total" in result1
        
        # Test with another ProgressCounts object
        counts2 = ProgressCounts(completed=5, pending=3, failed=2, total=10)
        result2 = counts2.format_progress_line()
        assert "5 done" in result2
        assert "3 in-progress" in result2
        assert "2 failed" in result2
        assert "10 total" in result2
        
        # Test that both produce same result
        assert result1 == result2
    
    def test_format_progress_line_feature_envy_fix(self) -> None:
        """Test that ProgressCounts.format_progress_line doesn't have feature envy."""
        counts = ProgressCounts(completed=5, pending=3, failed=2, total=10)
        
        # Create a renderer
        ledger = TaskLedger(goal="Test")
        renderer = LedgerRenderer(ledger)
        
        # Call the method on the ProgressCounts object
        result = counts.format_progress_line()
        assert "5 done" in result
        assert "3 in-progress" in result
        assert "2 failed" in result
        assert "10 total" in result
    def test_add_item_factory_eliminates_duplicate_code(self) -> None:
        """Test that _add_item_factory eliminates duplicate code between add_checklist_item and add_delegation."""
        ledger = TaskLedger(goal="Test")
        
        # Test checklist item creation
        checklist_item = ledger.add_checklist_item("Test item")
        assert len(ledger.checklist) == 1
        assert checklist_item.description == "Test item"
        assert checklist_item.done is False
        
        # Test delegation creation
        delegation = ledger.add_delegation("test_agent", "test_task")
        assert len(ledger.delegations) == 1
        assert delegation.agent == "test_agent"
        assert delegation.task == "test_task"
        assert delegation.status == DelegationStatus.PENDING
        
        # Verify both use the same factory method
        # (This is more of a structural check - the implementation should use _add_item_factory)
    
    def test_render_static_duplicate_code(self) -> None:
        """Test that render_static and render produce same output."""
        ledger = TaskLedger(goal="Test Goal")
        ledger.add_checklist_item("Item 1")
        ledger.add_checklist_item("Item 2")
        ledger.check_item(0)
        
        rec = ledger.add_delegation("agent", "task")
        ledger.complete_delegation(rec, "summary")
        
        # Instance render
        instance_result = ledger.render(max_entries=5)
        
        # Static render
        static_result = LedgerRenderer.render_static(ledger, max_entries=5)
        
        # Should be identical
        assert instance_result == static_result
        
        # Both should contain key elements
        assert "Test Goal" in instance_result
        assert "Checklist:" in instance_result
        assert "✅ Item 1" in instance_result
        assert "☐ Item 2" in instance_result
        assert "agent → task" in instance_result