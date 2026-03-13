"""Comprehensive tests for ledger.py refactoring to ensure no regression."""

import pytest
from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    TaskLedger,
    LedgerRenderer,
    ProgressCounts,
)


def test_ledger_renderer_init():
    """Test LedgerRenderer.__init__ method."""
    ledger = TaskLedger(goal="Test goal")
    renderer = LedgerRenderer(ledger, max_entries=5)
    assert renderer.ledger == ledger
    assert renderer.max_entries == 5


def test_ledger_renderer_render():
    """Test LedgerRenderer.render method."""
    ledger = TaskLedger(goal="Test goal")
    renderer = LedgerRenderer(ledger)
    result = renderer.render()
    assert "📋 TASK LEDGER" in result
    assert "Test goal" in result


def test_ledger_renderer_render_static():
    """Test LedgerRenderer.render_static method."""
    ledger = TaskLedger(goal="Test goal")
    result = LedgerRenderer.render_static(ledger, max_entries=5)
    assert "📋 TASK LEDGER" in result
    assert "Test goal" in result


def test_format_progress_line():
    """Test _format_progress_line method."""
    result = LedgerRenderer._format_progress_line(2, 1, 0, 3)
    assert "2 done" in result
    assert "1 in-progress" in result
    assert "0 failed" in result
    assert "3 total" in result


def test_format_progress_line_from_counts():
    """Test _format_progress_line_from_counts method."""
    counts = ProgressCounts(completed=2, pending=1, failed=0, total=3)
    result = LedgerRenderer._format_progress_line_from_counts(counts)
    assert "2 done" in result
    assert "1 in-progress" in result
    assert "0 failed" in result
    assert "3 total" in result


def test_get_delegation_counts_static():
    """Test _get_delegation_counts_static method."""
    delegations = [
        DelegationRecord(agent="a", task="t1", status=DelegationStatus.COMPLETED),
        DelegationRecord(agent="b", task="t2", status=DelegationStatus.PENDING),
        DelegationRecord(agent="c", task="t3", status=DelegationStatus.FAILED),
        DelegationRecord(agent="d", task="t4", status=DelegationStatus.COMPLETED),
    ]
    completed, pending, failed = LedgerRenderer._get_delegation_counts_static(delegations)
    assert completed == 2
    assert pending == 1
    assert failed == 1


def test_render_delegations_section():
    """Test render_delegations_section method."""
    delegations = [
        DelegationRecord(agent="a", task="t1", status=DelegationStatus.COMPLETED),
        DelegationRecord(agent="b", task="t2", status=DelegationStatus.PENDING),
    ]
    lines = []
    LedgerRenderer.render_delegations_section(delegations, lines, max_entries=5)
    assert len(lines) == 3  # Progress line + 2 delegation lines
    assert "1 done" in lines[0]
    assert "1 in-progress" in lines[0]
    assert "a → t1" in lines[1]
    assert "b → t2" in lines[2]


def test_add_checklist_item():
    """Test TaskLedger.add_checklist_item method."""
    ledger = TaskLedger(goal="Test")
    item = ledger.add_checklist_item("Test item")
    assert len(ledger.checklist) == 1
    assert item.description == "Test item"
    assert item.done is False


def test_add_delegation():
    """Test TaskLedger.add_delegation method."""
    ledger = TaskLedger(goal="Test")
    record = ledger.add_delegation("coder", "Write code")
    assert len(ledger.delegations) == 1
    assert record.agent == "coder"
    assert record.task == "Write code"
    assert record.status == DelegationStatus.PENDING


def test_complete_delegation():
    """Test TaskLedger.complete_delegation method."""
    ledger = TaskLedger(goal="Test")
    record = ledger.add_delegation("coder", "Write code")
    ledger.complete_delegation(record, "Code written successfully")
    assert record.status == DelegationStatus.COMPLETED
    assert record.summary == "Code written successfully"


def test_fail_delegation():
    """Test TaskLedger.fail_delegation method."""
    ledger = TaskLedger(goal="Test")
    record = ledger.add_delegation("coder", "Write code")
    ledger.fail_delegation(record, "Timeout error")
    assert record.status == DelegationStatus.FAILED
    assert record.summary == "Timeout error"


def test_check_item():
    """Test TaskLedger.check_item method."""
    ledger = TaskLedger(goal="Test")
    ledger.add_checklist_item("Item 1")
    ledger.add_checklist_item("Item 2")
    ledger.check_item(0)
    assert ledger.checklist[0].done is True
    assert ledger.checklist[1].done is False


def test_mission_recap():
    """Test TaskLedger.mission_recap method."""
    ledger = TaskLedger(goal="Test")
    ledger.add_checklist_item("Item 1")
    ledger.check_item(0)
    ledger.add_delegation("coder", "Task 1")
    recap = ledger.mission_recap()
    assert "Mission" in recap
    assert "1/1 checklist items done" in recap
    assert "0 delegations done" in recap


def test_mark_verified():
    """Test TaskLedger.mark_verified method."""
    ledger = TaskLedger(goal="Test")
    assert ledger.verified is False
    ledger.mark_verified()
    assert ledger.verified is True


def test_render_method():
    """Test TaskLedger.render method."""
    ledger = TaskLedger(goal="Test")
    result = ledger.render()
    assert "📋 TASK LEDGER" in result
    assert "Test" in result


if __name__ == "__main__":
    # Run all tests
    test_ledger_renderer_init()
    test_ledger_renderer_render()
    test_ledger_renderer_render_static()
    test_format_progress_line()
    test_format_progress_line_from_counts()
    test_get_delegation_counts_static()
    test_render_delegations_section()
    test_add_checklist_item()
    test_add_delegation()
    test_complete_delegation()
    test_fail_delegation()
    test_check_item()
    test_mission_recap()
    test_mark_verified()
    test_render_method()
    print("All tests passed!")