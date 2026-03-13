"""Test file for ledger refactoring to address code smells."""

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


class TestLedgerSmellFixes:
    """Tests to verify fixes for code smells in ledger.py."""
    
    def test_duplicate_get_delegation_counts_methods(self) -> None:
        """Test that duplicate _get_delegation_counts methods work correctly."""
        ledger = TaskLedger(goal="Test goal")
        
        # Add some delegations
        rec1 = ledger.add_delegation("coder", "Fix bug")
        rec2 = ledger.add_delegation("tester", "Run tests")
        rec3 = ledger.add_delegation("planner", "Design solution")
        
        # Complete one, fail one, leave one pending
        ledger.complete_delegation(rec1, "Bug fixed")
        ledger.fail_delegation(rec2, "Tests failed")
        # rec3 remains pending
        
        # Test the utility function
        counts = _get_delegation_counts_util(ledger.delegations)
        assert counts == (1, 1, 1)  # completed, pending, failed
        
        # Test LedgerRenderer's method
        renderer = LedgerRenderer(ledger)
        renderer_counts = renderer._get_delegation_counts()
        assert renderer_counts == (1, 1, 1)
        
        # Test TaskLedger's method
        ledger_counts = ledger._get_delegation_counts()
        assert ledger_counts == (1, 1, 1)
        
        # Test static method
        static_counts = LedgerRenderer._get_delegation_counts_static(ledger.delegations)
        assert static_counts == (1, 1, 1)
    
    def test_count_delegations_by_status_utility(self) -> None:
        """Test the _count_delegations_by_status_util function."""
        ledger = TaskLedger(goal="Test goal")
        
        # Add delegations
        rec1 = ledger.add_delegation("coder", "Fix bug")
        rec2 = ledger.add_delegation("tester", "Run tests")
        rec3 = ledger.add_delegation("planner", "Design solution")
        
        # Complete one, fail one
        ledger.complete_delegation(rec1, "Bug fixed")
        ledger.fail_delegation(rec2, "Tests failed")
        
        # Test utility function
        completed = _count_delegations_by_status_util(
            ledger.delegations, DelegationStatus.COMPLETED
        )
        assert completed == 1
        
        pending = _count_delegations_by_status_util(
            ledger.delegations, DelegationStatus.PENDING
        )
        assert pending == 1
        
        failed = _count_delegations_by_status_util(
            ledger.delegations, DelegationStatus.FAILED
        )
        assert failed == 1
        
        # Test static method
        static_completed = LedgerRenderer.count_delegations_by_status(
            ledger.delegations, DelegationStatus.COMPLETED
        )
        assert static_completed == 1
    
    def test_feature_envy_format_progress_line(self) -> None:
        """Test _format_progress_line_from_counts doesn't have feature envy."""
        counts = ProgressCounts(completed=2, pending=3, failed=1, total=6)
        
        # This should work without accessing counts excessively
        result = LedgerRenderer._format_progress_line_from_counts(counts)
        assert "Progress: 2 done, 3 in-progress, 1 failed / 6 total" in result
    
    def test_duplicate_add_methods(self) -> None:
        """Test that add_checklist_item and add_delegation use shared factory."""
        ledger = TaskLedger(goal="Test goal")
        
        # Both should use _add_item_factory internally
        checklist_item = ledger.add_checklist_item("Test checklist item")
        assert isinstance(checklist_item, ChecklistItem)
        assert checklist_item.description == "Test checklist item"
        assert len(ledger.checklist) == 1
        
        delegation = ledger.add_delegation("coder", "Fix bug")
        assert isinstance(delegation, DelegationRecord)
        assert delegation.agent == "coder"
        assert delegation.task == "Fix bug"
        assert len(ledger.delegations) == 1
    
    def test_complete_delegation_truncation(self) -> None:
        """Test that complete_delegation truncates summary."""
        ledger = TaskLedger(goal="Test goal")
        rec = ledger.add_delegation("coder", "Fix bug")
        
        # Create a very long summary
        long_summary = "x" * 1000
        ledger.complete_delegation(rec, long_summary)
        
        # Should be truncated to SUMMARY_MAX_LENGTH (500)
        assert len(rec.summary) == 500
        assert rec.summary == "x" * 500
    
    def test_render_methods(self) -> None:
        """Test that render methods produce consistent output."""
        ledger = TaskLedger(goal="Test goal")
        ledger.add_checklist_item("First item")
        ledger.add_checklist_item("Second item")
        ledger.check_item(0)  # Mark first as done
        
        rec = ledger.add_delegation("coder", "Fix bug")
        ledger.complete_delegation(rec, "Bug fixed")
        
        # Test instance render
        instance_output = ledger.render()
        assert "Test goal" in instance_output
        assert "Checklist:" in instance_output
        assert "✅ First item" in instance_output
        assert "☐ Second item" in instance_output
        assert "Progress:" in instance_output
        
        # Test static render
        static_output = LedgerRenderer.render_static(ledger)
        assert static_output == instance_output
        
        # Test renderer instance
        renderer = LedgerRenderer(ledger)
        renderer_output = renderer.render()
        assert renderer_output == instance_output
    
    def test_mission_recap_includes_verification(self) -> None:
        """Test mission_recap shows verification status."""
        ledger = TaskLedger(goal="Test goal")
        
        # Initially unverified
        recap = ledger.mission_recap()
        assert "⚠️ unverified" in recap
        
        # Mark as verified
        ledger.mark_verified()
        recap = ledger.mission_recap()
        assert "✅ verified" in recap
    
    def test_edge_case_empty_lists(self) -> None:
        """Test edge cases with empty delegations and checklist."""
        ledger = TaskLedger(goal="Test goal")
        
        # Empty delegations
        counts = ledger._get_delegation_counts()
        assert counts == (0, 0, 0)
        
        # Empty checklist
        recap = ledger.mission_recap()
        assert "0 checklist items done" not in recap  # Should not mention checklist
        
        # Render with empty state
        output = ledger.render()
        assert "No delegations yet." in output
    
    def test_check_item_boundary_conditions(self) -> None:
        """Test check_item with boundary conditions."""
        ledger = TaskLedger(goal="Test goal")
        ledger.add_checklist_item("Item 1")
        ledger.add_checklist_item("Item 2")
        
        # Valid index
        ledger.check_item(0)
        assert ledger.checklist[0].done
        
        # Invalid index should raise
        with pytest.raises(IndexError):
            ledger.check_item(2)
        
        with pytest.raises(IndexError):
            ledger.check_item(-1)
    
    def test_get_visible_delegations(self) -> None:
        """Test get_visible_delegations with various max_entries."""
        ledger = TaskLedger(goal="Test goal")
        
        # Add 5 delegations
        for i in range(5):
            ledger.add_delegation(f"agent{i}", f"task{i}")
        
        renderer = LedgerRenderer(ledger, max_entries=3)
        visible, collapsed = renderer._get_visible_delegations()
        
        # Should show last 3, collapse 2
        assert len(visible) == 3
        assert collapsed == 2
        
        # Test static method
        visible_static, collapsed_static = LedgerRenderer.get_visible_delegations(
            ledger.delegations, max_entries=2
        )
        assert len(visible_static) == 2
        assert collapsed_static == 3
        
        # Test edge case: max_entries <= 0
        visible_zero, collapsed_zero = LedgerRenderer.get_visible_delegations(
            ledger.delegations, max_entries=0
        )
        assert len(visible_zero) == 0
        assert collapsed_zero == 5
        
        # Test edge case: max_entries >= total
        visible_all, collapsed_all = LedgerRenderer.get_visible_delegations(
            ledger.delegations, max_entries=10
        )
        assert len(visible_all) == 5
        assert collapsed_all == 0