"""Additional tests to improve coverage for ledger.py."""

import pytest
from henchman.agents.ledger import (
    LedgerRenderer,
    ProgressCounts,
    TaskLedger,
)


class TestCoverageGaps:
    """Tests to cover missing lines in ledger.py."""
    
    def test_format_progress_line_type_error(self) -> None:
        """Test ProgressCounts.format_progress_line method (replaces removed static method)."""
        counts = ProgressCounts(completed=2, pending=3, failed=1, total=6)
        result = counts.format_progress_line()
        assert result == "Progress: 2 done, 3 in-progress, 1 failed / 6 total"
    
    def test_render_checklist_section_empty(self) -> None:
        """Test _render_checklist_section with empty checklist."""
        ledger = TaskLedger(goal="Test")
        renderer = LedgerRenderer(ledger)
        
        # This should not crash or add anything
        lines: list[str] = []
        renderer._render_checklist_section(lines)
        assert lines == []  # No checklist items added
    
    def test_render_checklist_section_with_items(self) -> None:
        """Test _render_checklist_section with checklist items."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        ledger.add_checklist_item("Item 2")
        ledger.check_item(0)  # Mark first as done
        
        renderer = LedgerRenderer(ledger)
        lines: list[str] = []
        renderer._render_checklist_section(lines)
        
        assert lines == [
            "Checklist:",
            "  ✅ Item 1",
            "  ☐ Item 2",
        ]
    
    def test_check_item_valid_index(self) -> None:
        """Test check_item with valid index."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Item 1")
        ledger.add_checklist_item("Item 2")
        
        ledger.check_item(1)
        assert ledger.checklist[1].done is True
        assert ledger.checklist[0].done is False
    
    def test_fail_delegation_with_keyword_args(self) -> None:
        """Test fail_delegation uses keyword arguments correctly."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("agent", "task")
        
        # This should work with keyword arguments
        ledger.fail_delegation(record=rec, reason="Failed reason")
        assert rec.status.value == "failed"
        assert rec.summary == "Failed reason"
    
    def test_mission_recap_with_checklist_and_delegations(self) -> None:
        """Test mission_recap with both checklist and delegations."""
        ledger = TaskLedger(goal="Test")
        
        # Add checklist items
        ledger.add_checklist_item("Check 1")
        ledger.add_checklist_item("Check 2")
        ledger.check_item(0)
        
        # Add delegations
        rec1 = ledger.add_delegation("agent1", "task1")
        ledger.complete_delegation(rec1, "Done")
        
        rec2 = ledger.add_delegation("agent2", "task2")
        ledger.fail_delegation(rec2, "Failed")
        
        ledger.add_delegation("agent3", "task3")  # Pending
        
        recap = ledger.mission_recap()
        assert "1/2 checklist items done" in recap
        assert "1 delegations done" in recap
        assert "1 pending" in recap
        assert "1 failed" in recap
    
    def test_render_delegations_section_empty(self) -> None:
        """Test _render_delegations_section with empty delegations."""
        ledger = TaskLedger(goal="Test")
        renderer = LedgerRenderer(ledger)
        
        lines: list[str] = []
        renderer._render_delegations_section(lines)
        assert lines == ["No delegations yet."]
    
    def test_render_delegations_section_with_collapsed(self) -> None:
        """Test _render_delegations_section with collapsed entries."""
        ledger = TaskLedger(goal="Test")
        
        # Add more delegations than max_entries
        for i in range(15):
            rec = ledger.add_delegation(f"agent{i}", f"task{i}")
            ledger.complete_delegation(rec, f"done{i}")
        
        renderer = LedgerRenderer(ledger, max_entries=5)
        lines: list[str] = []
        renderer._render_delegations_section(lines)
        
        # Should show progress line and collapsed count
        assert "Progress:" in lines[0]
        assert "10 earlier delegations omitted" in lines[1]
        # Should show 5 most recent delegations
        # lines[2] is the first delegation line
        assert any("agent14" in line for line in lines)
        assert any("agent10" in line for line in lines)
        assert not any("agent9" in line for line in lines)  # Not shown (collapsed)