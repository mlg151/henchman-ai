"""Tests for the TaskLedger and its integration with the Orchestrator."""

from henchman.agents.ledger import (
    ChecklistItem,
    DelegationRecord,
    DelegationStatus,
    TaskLedger,
)


class TestDelegationRecord:
    """Tests for the DelegationRecord dataclass."""

    def test_defaults(self) -> None:
        """New record starts pending with empty summary."""
        rec = DelegationRecord(agent="coder", task="Fix bug")
        assert rec.status == DelegationStatus.PENDING
        assert rec.summary == ""

    def test_custom_status(self) -> None:
        """Can create with explicit status."""
        rec = DelegationRecord(
            agent="tester", task="Run tests", status=DelegationStatus.COMPLETED, summary="All pass"
        )
        assert rec.status == DelegationStatus.COMPLETED
        assert rec.summary == "All pass"


class TestTaskLedger:
    """Unit tests for TaskLedger."""

    def test_init(self) -> None:
        """Ledger stores the goal."""
        ledger = TaskLedger(goal="Refactor auth module")
        assert ledger.goal == "Refactor auth module"
        assert ledger.delegations == []

    def test_add_delegation(self) -> None:
        """add_delegation appends a pending record."""
        ledger = TaskLedger(goal="Fix bug")
        rec = ledger.add_delegation("coder", "Patch main.py")
        assert len(ledger.delegations) == 1
        assert rec.agent == "coder"
        assert rec.task == "Patch main.py"
        assert rec.status == DelegationStatus.PENDING

    def test_complete_delegation(self) -> None:
        """complete_delegation updates status and summary."""
        ledger = TaskLedger(goal="Fix bug")
        rec = ledger.add_delegation("coder", "Patch main.py")
        ledger.complete_delegation(rec, "Patched line 42")
        assert rec.status == DelegationStatus.COMPLETED
        assert rec.summary == "Patched line 42"

    def test_complete_delegation_truncates_summary(self) -> None:
        """Summary is truncated to 500 chars."""
        ledger = TaskLedger(goal="Fix bug")
        rec = ledger.add_delegation("coder", "Patch main.py")
        ledger.complete_delegation(rec, "x" * 1000)
        assert len(rec.summary) == 500

    def test_fail_delegation(self) -> None:
        """fail_delegation marks failure with reason."""
        ledger = TaskLedger(goal="Fix bug")
        rec = ledger.add_delegation("nonexistent", "Do something")
        ledger.fail_delegation(rec, "Agent not found")
        assert rec.status == DelegationStatus.FAILED
        assert rec.summary == "Agent not found"

    def test_fail_delegation_truncates(self) -> None:
        """Failure reason is truncated to 500 chars."""
        ledger = TaskLedger(goal="Fix bug")
        rec = ledger.add_delegation("coder", "Patch")
        ledger.fail_delegation(rec, "e" * 1000)
        assert len(rec.summary) == 500

    def test_render_empty(self) -> None:
        """Render with no delegations."""
        ledger = TaskLedger(goal="Build feature X")
        text = ledger.render()
        assert "📋 TASK LEDGER" in text
        assert "Build feature X" in text
        assert "No delegations yet." in text

    def test_render_with_delegations(self) -> None:
        """Render shows completed, failed, and pending."""
        ledger = TaskLedger(goal="Implement auth")
        r1 = ledger.add_delegation("researcher", "Find auth patterns")
        ledger.complete_delegation(r1, "Use JWT with refresh tokens")
        r2 = ledger.add_delegation("coder", "Implement JWT auth")
        ledger.complete_delegation(r2, "Added auth.py with JWT support")
        ledger.add_delegation("tester", "Test auth endpoints")
        # stays pending

        text = ledger.render()
        assert "Implement auth" in text
        assert "2 done" in text
        assert "1 in-progress" in text
        assert "0 failed" in text
        assert "✅" in text
        assert "⏳" in text
        assert "researcher" in text
        assert "coder" in text
        assert "tester" in text

    def test_render_with_failures(self) -> None:
        """Render shows failure icon."""
        ledger = TaskLedger(goal="Deploy")
        rec = ledger.add_delegation("devops", "Run deploy")
        ledger.fail_delegation(rec, "Pipeline broken")
        text = ledger.render()
        assert "❌" in text
        assert "1 failed" in text

    def test_render_collapses_old_entries(self) -> None:
        """Entries beyond max_entries are collapsed."""
        ledger = TaskLedger(goal="Big task")
        for i in range(15):
            rec = ledger.add_delegation("coder", f"Step {i}")
            ledger.complete_delegation(rec, f"Done {i}")

        text = ledger.render(max_entries=5)
        assert "10 earlier delegations omitted" in text
        # Latest entries visible
        assert "Step 14" in text
        assert "Step 10" in text
        # Oldest entry not individually listed
        assert "Step 0" not in text.split("omitted")[-1]

    def test_render_progress_counts(self) -> None:
        """Progress line includes correct totals."""
        ledger = TaskLedger(goal="Test")
        r1 = ledger.add_delegation("a", "t1")
        ledger.complete_delegation(r1, "ok")
        r2 = ledger.add_delegation("b", "t2")
        ledger.fail_delegation(r2, "err")
        ledger.add_delegation("c", "t3")  # pending

        text = ledger.render()
        assert "1 done" in text
        assert "1 in-progress" in text
        assert "1 failed" in text
        assert "3 total" in text


class TestDelegationStatus:
    """Tests for DelegationStatus enum."""

    def test_values(self) -> None:
        """Enum has expected values."""
        assert DelegationStatus.PENDING == "pending"
        assert DelegationStatus.COMPLETED == "completed"
        assert DelegationStatus.FAILED == "failed"

    def test_is_str(self) -> None:
        """DelegationStatus is a str enum."""
        assert isinstance(DelegationStatus.PENDING, str)


class TestChecklistItem:
    """Tests for the ChecklistItem dataclass."""

    def test_defaults(self) -> None:
        """New item starts unchecked."""
        item = ChecklistItem(description="Write tests")
        assert item.description == "Write tests"
        assert item.done is False

    def test_mark_done(self) -> None:
        """Can mark item as done."""
        item = ChecklistItem(description="Deploy")
        item.done = True
        assert item.done is True


class TestTaskLedgerChecklist:
    """Tests for Task 1: Checklist-First Initiation."""

    def test_add_checklist_item(self) -> None:
        """add_checklist_item appends an unchecked item."""
        ledger = TaskLedger(goal="Build feature")
        item = ledger.add_checklist_item("Research API")
        assert len(ledger.checklist) == 1
        assert item.description == "Research API"
        assert item.done is False

    def test_check_item(self) -> None:
        """check_item marks item as done by index."""
        ledger = TaskLedger(goal="Build feature")
        ledger.add_checklist_item("Step 1")
        ledger.add_checklist_item("Step 2")
        ledger.check_item(0)
        assert ledger.checklist[0].done is True
        assert ledger.checklist[1].done is False

    def test_check_item_out_of_range(self) -> None:
        """check_item raises IndexError for bad index."""
        ledger = TaskLedger(goal="Build feature")
        import pytest
        with pytest.raises(IndexError):
            ledger.check_item(0)

    def test_render_shows_checklist(self) -> None:
        """Render includes checklist items."""
        ledger = TaskLedger(goal="Build feature")
        ledger.add_checklist_item("Research API")
        ledger.add_checklist_item("Write code")
        ledger.check_item(0)
        text = ledger.render()
        assert "Checklist:" in text
        assert "✅ Research API" in text
        assert "☐ Write code" in text


class TestTaskLedgerVerification:
    """Tests for Task 3: Verification Tool-Lock."""

    def test_default_unverified(self) -> None:
        """Ledger starts unverified."""
        ledger = TaskLedger(goal="Fix bug")
        assert ledger.verified is False

    def test_mark_verified(self) -> None:
        """mark_verified sets flag."""
        ledger = TaskLedger(goal="Fix bug")
        ledger.mark_verified()
        assert ledger.verified is True

    def test_mission_recap_shows_verification(self) -> None:
        """Mission recap shows verification status."""
        ledger = TaskLedger(goal="Fix bug")
        assert "unverified" in ledger.mission_recap()
        ledger.mark_verified()
        assert "verified" in ledger.mission_recap()


class TestMissionRecap:
    """Tests for Task 9: Mission Recapitulation."""

    def test_recap_empty(self) -> None:
        """Recap with no delegations or checklist."""
        ledger = TaskLedger(goal="Test")
        recap = ledger.mission_recap()
        assert "0 delegations done" in recap
        assert "0 pending" in recap
        assert "0 failed" in recap

    def test_recap_with_checklist(self) -> None:
        """Recap includes checklist progress."""
        ledger = TaskLedger(goal="Test")
        ledger.add_checklist_item("Step 1")
        ledger.add_checklist_item("Step 2")
        ledger.check_item(0)
        recap = ledger.mission_recap()
        assert "1/2 checklist items done" in recap

    def test_recap_with_delegations(self) -> None:
        """Recap includes delegation counts."""
        ledger = TaskLedger(goal="Test")
        r1 = ledger.add_delegation("coder", "Write code")
        ledger.complete_delegation(r1, "Done")
        r2 = ledger.add_delegation("tester", "Test it")
        ledger.fail_delegation(r2, "Failed")
        ledger.add_delegation("devops", "Deploy")

        recap = ledger.mission_recap()
        assert "1 delegations done" in recap
        assert "1 pending" in recap
        assert "1 failed" in recap

    def test_render_includes_mission_recap(self) -> None:
        """Render includes mission recap line."""
        ledger = TaskLedger(goal="Build feature")
        text = ledger.render()
        assert "Mission" in text
        assert "unverified" in text
