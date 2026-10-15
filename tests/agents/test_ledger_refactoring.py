"""Tests for ledger refactoring to address code smells."""

from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    LedgerRenderer,
    TaskLedger,
)


class TestLedgerRefactoring:
    """Tests for refactored ledger code to address code smells."""

    def test_get_delegation_counts_as_static_method(self) -> None:
        """Test that _get_delegation_counts works as a static method."""
        delegations = [
            DelegationRecord("a", "t1", DelegationStatus.COMPLETED),
            DelegationRecord("b", "t2", DelegationStatus.PENDING),
            DelegationRecord("c", "t3", DelegationStatus.FAILED),
            DelegationRecord("d", "t4", DelegationStatus.COMPLETED),
            DelegationRecord("e", "t5", DelegationStatus.PENDING),
        ]

        # Test as utility function (after refactoring)
        from henchman.agents.ledger import _get_delegation_counts_util
        completed, pending, failed = _get_delegation_counts_util(delegations)
        assert completed == 2
        assert pending == 2
        assert failed == 1

    def test_render_delegations_section_feature_envy_fix(self) -> None:
        """Test _render_delegations_section after addressing feature envy."""
        ledger = TaskLedger(goal="Test")
        for i in range(15):
            rec = ledger.add_delegation("agent", f"Task {i}")
            ledger.complete_delegation(rec, f"Done {i}")

        renderer = LedgerRenderer(ledger, max_entries=5)
        lines: list[str] = []

        # Test the method
        renderer._render_delegations_section(lines)

        # Should have progress line, collapsed notice, and 5 visible entries
        assert len(lines) == 7  # Progress line + collapsed notice + 5 entries
        assert "15 total" in lines[0]
        assert "10 earlier delegations omitted" in lines[1]
        assert "Task 10" in lines[2]
        assert "Task 14" in lines[6]

    def test_count_delegations_by_status_duplicate_code_fix(self) -> None:
        """Test count_delegations_by_status after addressing duplicate code."""
        delegations = [
            DelegationRecord("a", "t1", DelegationStatus.COMPLETED),
            DelegationRecord("b", "t2", DelegationStatus.PENDING),
            DelegationRecord("c", "t3", DelegationStatus.COMPLETED),
            DelegationRecord("d", "t4", DelegationStatus.FAILED),
            DelegationRecord("e", "t5", DelegationStatus.COMPLETED),
        ]

        # Test the utility function (after refactoring)
        from henchman.agents.ledger import _count_delegations_by_status_util
        count = _count_delegations_by_status_util(delegations, DelegationStatus.COMPLETED)
        assert count == 3

    def test_render_method_duplicate_code_fix(self) -> None:
        """Test render method after addressing duplicate code."""
        ledger = TaskLedger(goal="Test")
        r1 = ledger.add_delegation("coder", "Write code")
        ledger.complete_delegation(r1, "Done")
        r2 = ledger.add_delegation("tester", "Test it")
        ledger.fail_delegation(r2, "Failed")
        ledger.add_delegation("devops", "Deploy")

        # Test render method
        text = ledger.render()
        assert "📋 TASK LEDGER" in text
        assert "Test" in text
        assert "1 done" in text
        assert "1 in-progress" in text
        assert "1 failed" in text

    def test_complete_delegation_duplicate_code_fix(self) -> None:
        """Test complete_delegation after addressing duplicate code."""
        ledger = TaskLedger(goal="Test")
        rec = ledger.add_delegation("coder", "Write code")

        # Test complete_delegation
        ledger.complete_delegation(rec, "Code written successfully")
        assert rec.status == DelegationStatus.COMPLETED
        assert rec.summary == "Code written successfully"

    def test_add_checklist_item_and_add_delegation_common_pattern(self) -> None:
        """Test that add_checklist_item and add_delegation share common pattern."""
        ledger = TaskLedger(goal="Test")

        # Both should use the same internal helper
        checklist_item = ledger.add_checklist_item("Test item")
        delegation_record = ledger.add_delegation("coder", "Write code")

        assert isinstance(checklist_item, ChecklistItem)
        assert isinstance(delegation_record, DelegationRecord)
        assert len(ledger.checklist) == 1
        assert len(ledger.delegations) == 1
