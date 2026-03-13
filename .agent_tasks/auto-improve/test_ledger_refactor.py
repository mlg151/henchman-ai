"""Test for ledger refactoring to ensure no regression."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from henchman.agents.ledger import (
    TaskLedger,
    DelegationRecord,
    DelegationStatus,
    ChecklistItem,
    ProgressCounts,
    LedgerRenderer,
)


def test_ledger_basic_operations():
    """Test basic ledger operations."""
    ledger = TaskLedger(goal="Test goal")
    
    # Test checklist
    item = ledger.add_checklist_item("Test item")
    assert isinstance(item, ChecklistItem)
    assert item.description == "Test item"
    assert not item.done
    
    ledger.check_item(0)
    assert ledger.checklist[0].done
    
    # Test delegation
    record = ledger.add_delegation("coder", "Write test")
    assert isinstance(record, DelegationRecord)
    assert record.agent == "coder"
    assert record.task == "Write test"
    assert record.status == DelegationStatus.PENDING
    
    ledger.complete_delegation(record, "Test completed")
    assert record.status == DelegationStatus.COMPLETED
    assert "Test completed" in record.summary
    
    # Test rendering
    rendered = ledger.render()
    assert "Test goal" in rendered
    assert "coder" in rendered
    assert "Write test" in rendered


def test_progress_counts():
    """Test ProgressCounts dataclass."""
    counts = ProgressCounts(completed=2, pending=1, failed=0, total=3)
    assert counts.completed == 2
    assert counts.pending == 1
    assert counts.failed == 0
    assert counts.total == 3


def test_ledger_renderer_static_methods():
    """Test LedgerRenderer static methods."""
    delegations = [
        DelegationRecord(agent="coder", task="Task 1", status=DelegationStatus.COMPLETED),
        DelegationRecord(agent="tester", task="Task 2", status=DelegationStatus.PENDING),
        DelegationRecord(agent="planner", task="Task 3", status=DelegationStatus.FAILED),
    ]
    
    # Test counting - create a dummy ledger and renderer
    from henchman.agents.ledger import TaskLedger
    dummy_ledger = TaskLedger(goal="")
    dummy_ledger.delegations = delegations
    renderer = LedgerRenderer(dummy_ledger)
    completed, pending, failed = renderer._get_delegation_counts()
    assert completed == 1
    assert pending == 1
    assert failed == 1
    
    # Test progress line formatting
    counts = ProgressCounts(completed=1, pending=1, failed=1, total=3)
    line = LedgerRenderer._format_progress_line_from_counts_static(counts)
    assert "1 done" in line
    assert "1 in-progress" in line
    assert "1 failed" in line
    assert "3 total" in line
    
    # Test with integers
    line2 = LedgerRenderer._format_progress_line(1, 1, 1, 3)
    assert line2 == line
    
    # Test with ProgressCounts object
    line3 = LedgerRenderer._format_progress_line(counts)
    assert line3 == line


def test_mission_recap():
    """Test mission recap generation."""
    ledger = TaskLedger(goal="Test")
    recap = ledger.mission_recap()
    assert "unverified" in recap
    
    ledger.mark_verified()
    recap2 = ledger.mission_recap()
    assert "verified" in recap2
    
    # Add checklist and delegations
    ledger.add_checklist_item("Item 1")
    ledger.add_checklist_item("Item 2")
    ledger.check_item(0)
    
    record = ledger.add_delegation("coder", "Task")
    ledger.complete_delegation(record, "Done")
    
    recap3 = ledger.mission_recap()
    assert "1/2 checklist items" in recap3
    assert "1 delegations done" in recap3


if __name__ == "__main__":
    test_ledger_basic_operations()
    test_progress_counts()
    test_ledger_renderer_static_methods()
    test_mission_recap()
    print("All tests passed!")