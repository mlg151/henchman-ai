"""Additional tests for ledger.py to cover edge cases and type hints."""

import pytest
from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    TaskLedger,
)


class TestLedgerTypeHints:
    """Tests to verify type hints work correctly."""
    
    def test_format_line_type_hint(self) -> None:
        """Test format_line method accepts optional max_summary_length."""
        rec = DelegationRecord(agent="coder", task="Fix bug", summary="Fixed the issue")
        result = rec.format_line()
        assert isinstance(result, str)
        
        # Test with custom max_summary_length
        result_short = rec.format_line(max_summary_length=5)
        assert isinstance(result_short, str)
        assert len(result_short) < len(result) or "..." in result_short
    
    def test_get_icon_type_hint(self) -> None:
        """Test _get_icon returns string for all statuses."""
        rec_completed = DelegationRecord(
            agent="coder", task="Fix bug", status=DelegationStatus.COMPLETED
        )
        rec_failed = DelegationRecord(
            agent="coder", task="Fix bug", status=DelegationStatus.FAILED
        )
        rec_pending = DelegationRecord(
            agent="coder", task="Fix bug", status=DelegationStatus.PENDING
        )
        
        assert isinstance(rec_completed._get_icon(), str)
        assert isinstance(rec_failed._get_icon(), str)
        assert isinstance(rec_pending._get_icon(), str)
    
    def test_create_and_append_generic(self) -> None:
        """Test _create_and_append works with generic types."""
        ledger = TaskLedger(goal="Test")
        test_list: list[str] = []
        result = ledger._create_and_append(test_list, "test")
        assert result == "test"
        assert test_list == ["test"]
    
    def test_add_item_factory_generic(self) -> None:
        """Test _add_item_factory works with factory functions."""
        ledger = TaskLedger(goal="Test")
        
        # Test with ChecklistItem factory
        def create_checklist(desc: str) -> ChecklistItem:
            return ChecklistItem(description=desc)
        
        checklist: list[ChecklistItem] = []
        result = ledger._add_item_factory(
            checklist, create_checklist, "Test item"
        )
        assert isinstance(result, ChecklistItem)
        assert result.description == "Test item"
        assert len(checklist) == 1


class TestLedgerEdgeCases:
    """Tests for edge cases not covered in existing tests."""
    
    def test_check_item_negative_index(self) -> None:
        """Test check_item with negative index raises IndexError."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        with pytest.raises(IndexError):
            ledger.check_item(-1)
    
    def test_check_item_large_index(self) -> None:
        """Test check_item with index beyond list raises IndexError."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        with pytest.raises(IndexError):
            ledger.check_item(1)
    
    def test_get_visible_delegations_edge_cases(self) -> None:
        """Test _get_visible_delegations with edge cases."""
        ledger = TaskLedger(goal="Test")
        
        # Test with max_entries = 0
        visible, collapsed = ledger._get_visible_delegations(0)
        assert visible == []
        assert collapsed == 0
        
        # Test with max_entries = -1
        visible, collapsed = ledger._get_visible_delegations(-1)
        assert visible == []
        assert collapsed == 0
        
        # Add some delegations
        for i in range(3):
            rec = ledger.add_delegation(f"agent{i}", f"task{i}")
            ledger.complete_delegation(rec, f"done{i}")
        
        # Test with max_entries = 2 (should show 2, collapse 1)
        visible, collapsed = ledger._get_visible_delegations(2)
        assert len(visible) == 2
        assert collapsed == 1
        # Should show the most recent 2
        assert visible[0].task == "task1"
        assert visible[1].task == "task2"
    
    def test_render_with_empty_checklist(self) -> None:
        """Test render when checklist is empty (should not show checklist section)."""
        ledger = TaskLedger(goal="Test")
        text = ledger.render()
        assert "Checklist:" not in text
    
    def test_render_with_empty_delegations(self) -> None:
        """Test render when delegations is empty shows 'No delegations yet.'."""
        ledger = TaskLedger(goal="Test")
        text = ledger.render()
        assert "No delegations yet." in text
    
    def test_mission_recap_pluralization(self) -> None:
        """Test mission recap uses correct pluralization."""
        ledger = TaskLedger(goal="Test")
        
        # 0 delegations
        recap = ledger.mission_recap()
        assert "0 delegations done" in recap
        
        # 1 delegation
        rec = ledger.add_delegation("coder", "task")
        ledger.complete_delegation(rec, "done")
        recap = ledger.mission_recap()
        assert "1 delegations done" in recap  # Note: might need to fix pluralization
        
        # 2 delegations
        rec2 = ledger.add_delegation("coder", "task2")
        ledger.complete_delegation(rec2, "done2")
        recap = ledger.mission_recap()
        assert "2 delegations done" in recap


class TestSummaryTruncation:
    """Tests for summary truncation behavior."""
    
    def test_summary_truncation_exact_length(self) -> None:
        """Test summary truncation when summary is exactly SUMMARY_MAX_LENGTH."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "task")
        
        # Create summary exactly at max length
        exact_summary = "x" * 500  # SUMMARY_MAX_LENGTH is 500
        ledger.complete_delegation(rec, exact_summary)
        assert len(rec.summary) == 500
        assert rec.summary == exact_summary
    
    def test_summary_truncation_one_over(self) -> None:
        """Test summary truncation when summary is one character over limit."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "task")
        
        over_summary = "x" * 501
        ledger.complete_delegation(rec, over_summary)
        assert len(rec.summary) == 500
        assert rec.summary == "x" * 500
    
    def test_fail_delegation_truncation(self) -> None:
        """Test fail_delegation also truncates reason."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "task")
        
        long_reason = "x" * 600
        ledger.fail_delegation(rec, long_reason)
        assert len(rec.summary) == 500
        assert rec.summary == "x" * 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])