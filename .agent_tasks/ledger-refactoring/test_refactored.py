"""Test the refactored ledger.py implementation."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import from our refactored module
exec(open('.agent_tasks/ledger-refactoring/ledger_refactored.py').read())

# Now run tests
import pytest

def test_repr_methods():
    """Test the new __repr__ methods."""
    # Test ProgressCounts
    counts = ProgressCounts(completed=2, pending=3, failed=1, total=6)
    assert "ProgressCounts(completed=2, pending=3, failed=1, total=6)" in repr(counts)
    
    # Test ChecklistItem
    item = ChecklistItem("Test item", done=True)
    assert "ChecklistItem(✅ 'Test item')" in repr(item)
    
    item2 = ChecklistItem("Undone item", done=False)
    assert "ChecklistItem(☐ 'Undone item')" in repr(item2)
    
    # Test DelegationRecord
    rec = DelegationRecord(agent="coder", task="Fix bug", status=DelegationStatus.COMPLETED, summary="Fixed it")
    assert "DelegationRecord(agent='coder', task='Fix bug', status=completed, summary='Fixed it')" in repr(rec)
    
    # Test with long summary
    rec2 = DelegationRecord(agent="tester", task="Test", status=DelegationStatus.PENDING, summary="x" * 100)
    assert "summary='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'..." in repr(rec2)
    
    # Test TaskLedger
    ledger = TaskLedger(goal="Test goal")
    assert "TaskLedger(goal='Test goal', checklist=0 items, delegations=0 records, verified=False)" in repr(ledger)

def test_constants():
    """Test that constants are properly defined."""
    assert MAX_DELEGATION_SUMMARY_LENGTH == 500
    assert DEFAULT_MAX_SUMMARY_LENGTH == 120
    assert DEFAULT_MAX_ENTRIES == 10

def test_backward_compatibility():
    """Test that the refactored version maintains backward compatibility."""
    # Create a ledger and add items
    ledger = TaskLedger(goal="Test compatibility")
    
    # Add checklist item
    item = ledger.add_checklist_item("Check 1")
    assert item.description == "Check 1"
    assert item.done is False
    
    # Check item
    ledger.check_item(0)
    assert ledger.checklist[0].done is True
    
    # Add delegation
    rec = ledger.add_delegation("coder", "Fix bug")
    assert rec.agent == "coder"
    assert rec.task == "Fix bug"
    assert rec.status == DelegationStatus.PENDING
    
    # Complete delegation
    ledger.complete_delegation(rec, "Fixed the bug")
    assert rec.status == DelegationStatus.COMPLETED
    assert rec.summary == "Fixed the bug"
    
    # Fail delegation
    rec2 = ledger.add_delegation("tester", "Test")
    ledger.fail_delegation(rec2, "Test failed")
    assert rec2.status == DelegationStatus.FAILED
    assert rec2.summary == "Test failed"
    
    # Mark verified
    ledger.mark_verified()
    assert ledger.verified is True
    
    # Mission recap
    recap = ledger.mission_recap()
    assert "Mission" in recap
    assert "verified" in recap
    
    # Render
    rendered = ledger.render()
    assert "📋 TASK LEDGER" in rendered
    assert "Test compatibility" in rendered

def test_edge_cases():
    """Test edge cases."""
    # Empty ledger
    ledger = TaskLedger(goal="Empty")
    rendered = ledger.render()
    assert "No delegations yet." in rendered
    
    # Many delegations with collapse
    ledger2 = TaskLedger(goal="Many")
    for i in range(15):
        rec = ledger2.add_delegation(f"agent{i}", f"task{i}")
        ledger2.complete_delegation(rec, f"done{i}")
    
    rendered = ledger2.render(max_entries=5)
    assert "10 earlier delegations omitted" in rendered
    
    # Negative max_entries
    ledger3 = TaskLedger(goal="Test")
    rec = ledger3.add_delegation("a", "t")
    # This should not crash
    rendered = ledger3.render(max_entries=-1)
    assert "📋 TASK LEDGER" in rendered

if __name__ == "__main__":
    # Run tests
    test_repr_methods()
    test_constants()
    test_backward_compatibility()
    test_edge_cases()
    print("All tests passed!")