"""Test to verify type hint fixes for ledger.py."""

from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    LedgerRenderer,
    TaskLedger,
)


def test_ledger_renderer_type_hints() -> None:
    """Test that LedgerRenderer methods have proper type hints."""
    ledger = TaskLedger(goal="Test goal")
    renderer = LedgerRenderer(ledger)
    
    # Test that render method works
    result = renderer.render()
    assert isinstance(result, str)
    assert "Test goal" in result
    
    # Test _render_checklist_section
    lines: list[str] = []
    renderer._render_checklist_section(lines)
    assert lines == []  # No checklist items
    
    # Add a checklist item and test again
    ledger.add_checklist_item("Test item")
    lines = []
    renderer._render_checklist_section(lines)
    assert "Checklist:" in lines[0]
    assert "☐ Test item" in lines[1]
    
    # Test _render_delegations_section
    lines = []
    renderer._render_delegations_section(lines)
    assert "No delegations yet." in lines[0]
    
    # Test _get_visible_delegations
    visible, collapsed = renderer._get_visible_delegations()
    assert visible == []
    assert collapsed == 0
    
    # Test _get_delegation_counts
    completed, pending, failed = renderer._get_delegation_counts()
    assert completed == 0
    assert pending == 0
    assert failed == 0


def test_static_methods_type_hints() -> None:
    """Test static methods have proper type hints."""
    # Test get_visible_delegations
    delegations = [
        DelegationRecord(agent="a1", task="t1"),
        DelegationRecord(agent="a2", task="t2"),
    ]
    visible, collapsed = LedgerRenderer.get_visible_delegations(delegations, 1)
    assert len(visible) == 1
    assert collapsed == 1
    
    # Test count_delegations_by_status
    delegations = [
        DelegationRecord(agent="a1", task="t1", status=DelegationStatus.COMPLETED),
        DelegationRecord(agent="a2", task="t2", status=DelegationStatus.PENDING),
    ]
    count = LedgerRenderer.count_delegations_by_status(delegations, DelegationStatus.COMPLETED)
    assert count == 1
    
    # Test _get_delegation_counts_static
    completed, pending, failed = LedgerRenderer._get_delegation_counts_static(delegations)
    assert completed == 1
    assert pending == 1
    assert failed == 0
    
    # Test _format_progress_line
    line = LedgerRenderer._format_progress_line(1, 2, 3, 6)
    assert "1 done" in line
    assert "2 in-progress" in line
    assert "3 failed" in line
    assert "6 total" in line
    
    # Test _format_progress_line_from_counts
    from henchman.agents.ledger import ProgressCounts
    counts = ProgressCounts(completed=1, pending=2, failed=3, total=6)
    line = LedgerRenderer._format_progress_line_from_counts(counts)
    assert "1 done" in line
    assert "2 in-progress" in line
    assert "3 failed" in line
    assert "6 total" in line
    
    # Test render_checklist_section
    checklist = [ChecklistItem("Item 1"), ChecklistItem("Item 2", done=True)]
    lines: list[str] = []
    LedgerRenderer.render_checklist_section(checklist, lines)
    assert "Checklist:" in lines[0]
    assert "☐ Item 1" in lines[1]
    assert "✅ Item 2" in lines[2]
    
    # Test render_delegations_section
    delegations = [
        DelegationRecord(agent="a1", task="t1", status=DelegationStatus.COMPLETED),
        DelegationRecord(agent="a2", task="t2", status=DelegationStatus.PENDING),
    ]
    lines = []
    LedgerRenderer.render_delegations_section(delegations, lines, 10)
    assert "1 done" in lines[0]
    assert "1 in-progress" in lines[0]
    
    # Test render_static
    ledger = TaskLedger(goal="Test")
    ledger.add_checklist_item("Item 1")
    ledger.add_delegation("agent", "task")
    result = LedgerRenderer.render_static(ledger)
    assert "Test" in result
    assert "Checklist:" in result
    assert "agent → task" in result


if __name__ == "__main__":
    test_ledger_renderer_type_hints()
    test_static_methods_type_hints()
    print("All tests passed!")