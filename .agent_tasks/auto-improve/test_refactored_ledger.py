"""Test the refactored ledger implementation."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the refactored module
exec(open(".agent_tasks/auto-improve/ledger_refactored.py").read())


def test_basic_functionality():
    """Test basic ledger functionality."""
    ledger = TaskLedger(goal="Test goal")
    
    # Test checklist
    item = ledger.add_checklist_item("Test item")
    assert isinstance(item, ChecklistItem)
    assert item.description == "Test item"
    assert not item.done
    
    ledger.check_item(0)
    assert ledger.checklist[0].done
    
    # Test delegation
    rec = ledger.add_delegation("coder", "Fix bug")
    assert isinstance(rec, DelegationRecord)
    assert rec.agent == "coder"
    assert rec.task == "Fix bug"
    assert rec.status == DelegationStatus.PENDING
    
    ledger.complete_delegation(rec, "Fixed the bug")
    assert rec.status == DelegationStatus.COMPLETED
    assert rec.summary == "Fixed the bug"
    
    # Test render
    text = ledger.render()
    assert "Test goal" in text
    assert "coder" in text
    assert "Fix bug" in text
    
    print("✓ Basic functionality test passed")


def test_ledger_renderer():
    """Test LedgerRenderer class."""
    ledger = TaskLedger(goal="Renderer test")
    
    # Add some data
    ledger.add_checklist_item("Item 1")
    ledger.add_checklist_item("Item 2")
    ledger.check_item(0)
    
    rec1 = ledger.add_delegation("agent1", "task1")
    ledger.complete_delegation(rec1, "done1")
    
    rec2 = ledger.add_delegation("agent2", "task2")
    ledger.fail_delegation(rec2, "failed")
    
    ledger.add_delegation("agent3", "task3")  # pending
    
    # Test renderer methods
    lines = []
    LedgerRenderer.render_checklist_section(ledger.checklist, lines)
    assert len(lines) == 3  # "Checklist:" + 2 items
    assert "✅ Item 1" in lines[1]
    assert "☐ Item 2" in lines[2]
    
    lines = []
    LedgerRenderer.render_delegations_section(ledger.delegations, lines, 10)
    assert "1 done" in lines[0]
    assert "1 in-progress" in lines[0]
    assert "1 failed" in lines[0]
    
    # Test get_visible_delegations
    visible, collapsed = LedgerRenderer.get_visible_delegations(ledger.delegations, 2)
    assert len(visible) == 2
    assert collapsed == 1
    assert visible[0].task == "task2"  # Most recent first (task2, task3)
    assert visible[1].task == "task3"
    
    # Test count_delegations_by_status
    completed = LedgerRenderer.count_delegations_by_status(ledger.delegations, DelegationStatus.COMPLETED)
    failed = LedgerRenderer.count_delegations_by_status(ledger.delegations, DelegationStatus.FAILED)
    pending = LedgerRenderer.count_delegations_by_status(ledger.delegations, DelegationStatus.PENDING)
    assert completed == 1
    assert failed == 1
    assert pending == 1
    
    # Test full render
    text = LedgerRenderer.render(ledger)
    assert "Renderer test" in text
    assert "Checklist:" in text
    assert "Progress:" in text
    
    print("✓ LedgerRenderer test passed")


def test_edge_cases():
    """Test edge cases."""
    ledger = TaskLedger(goal="Edge cases")
    
    # Test empty render
    text = ledger.render()
    assert "Edge cases" in text
    assert "No delegations yet." in text
    assert "Checklist:" not in text  # Should not render empty checklist
    
    # Test check_item with invalid index
    try:
        ledger.check_item(0)
        assert False, "Should have raised IndexError"
    except IndexError:
        pass
    
    # Test negative max_entries
    text = ledger.render(max_entries=-1)
    assert "No delegations yet." in text
    
    # Test zero max_entries
    ledger.add_delegation("agent", "task")
    text = ledger.render(max_entries=0)
    assert "0 earlier delegations omitted" not in text  # Different behavior with 0
    
    print("✓ Edge cases test passed")


def test_mission_recap():
    """Test mission recap functionality."""
    ledger = TaskLedger(goal="Mission test")
    
    # Empty mission
    recap = ledger.mission_recap()
    assert "unverified" in recap
    assert "0 delegations done" in recap
    
    # With checklist
    ledger.add_checklist_item("Step 1")
    ledger.add_checklist_item("Step 2")
    ledger.check_item(0)
    recap = ledger.mission_recap()
    assert "1/2 checklist items done" in recap
    
    # With delegations
    rec = ledger.add_delegation("coder", "task")
    ledger.complete_delegation(rec, "done")
    recap = ledger.mission_recap()
    assert "1 delegations done" in recap
    
    # Verified
    ledger.mark_verified()
    recap = ledger.mission_recap()
    assert "verified" in recap
    
    print("✓ Mission recap test passed")


def test_delegation_record():
    """Test DelegationRecord methods."""
    rec = DelegationRecord(agent="test", task="task", status=DelegationStatus.COMPLETED, summary="Test summary")
    
    # Test format_line
    line = rec.format_line()
    assert "test" in line
    assert "task" in line
    assert "Test summary" in line
    
    # Test with max_summary_length
    rec.summary = "A" * 200
    line = rec.format_line(max_summary_length=50)
    # Should truncate summary
    assert len(line) < 200
    
    # Test _get_icon
    rec_completed = DelegationRecord(agent="a", task="t", status=DelegationStatus.COMPLETED)
    rec_failed = DelegationRecord(agent="a", task="t", status=DelegationStatus.FAILED)
    rec_pending = DelegationRecord(agent="a", task="t", status=DelegationStatus.PENDING)
    
    assert rec_completed._get_icon() == "✅"
    assert rec_failed._get_icon() == "❌"
    assert rec_pending._get_icon() == "⏳"
    
    print("✓ DelegationRecord test passed")


if __name__ == "__main__":
    test_basic_functionality()
    test_ledger_renderer()
    test_edge_cases()
    test_mission_recap()
    test_delegation_record()
    print("\n✅ All tests passed!")