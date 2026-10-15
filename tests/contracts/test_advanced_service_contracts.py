"""Contract tests for advanced services and skills catalog behavioral boundaries.

These tests enforce behavioral contracts for service-layer components that manage
stateful operations like plan execution, task lifecycle, and skill discovery.
"""

from __future__ import annotations

import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from henchman.advanced.plans import (
    PlanExecutionService,
    PlanRecord,
    PlanStepRecord,
    _normalize_steps,
)

# ---------------------------------------------------------------------------
# PlanStepRecord contracts
# ---------------------------------------------------------------------------


class TestPlanStepRecordContract:
    """Contract tests for PlanStepRecord serialization and lifecycle."""

    def test_to_dict_produces_serializable_payload(self) -> None:
        """to_dict should produce a JSON-serializable dict with all fields."""
        step = PlanStepRecord(
            index=1,
            text="Do something",
            done=False,
            evidence=None,
            completed_at=None,
        )
        d = step.to_dict()
        assert d["index"] == 1
        assert d["text"] == "Do something"
        assert d["done"] is False
        assert d["evidence"] is None
        assert d["completed_at"] is None

    def test_from_dict_roundtrip(self) -> None:
        """PlanStepRecord should round-trip through dict serialization."""
        original = PlanStepRecord(
            index=2,
            text="Step two",
            done=True,
            evidence="proof",
            completed_at="2024-01-01T00:00:00",
        )
        payload = original.to_dict()
        restored = PlanStepRecord.from_dict(payload)
        assert restored.index == original.index
        assert restored.text == original.text
        assert restored.done == original.done
        assert restored.evidence == original.evidence
        assert restored.completed_at == original.completed_at

    def test_from_dict_handles_missing_optional_fields(self) -> None:
        """from_dict should handle missing optional fields gracefully."""
        payload = {"index": 1, "text": "minimal", "done": False}
        step = PlanStepRecord.from_dict(payload)
        assert step.index == 1
        assert step.text == "minimal"
        assert step.done is False
        assert step.evidence is None
        assert step.completed_at is None

    def test_from_dict_coerces_index_types(self) -> None:
        """from_dict should coerce index from string to int."""
        payload = {"index": "3", "text": "coerced", "done": False}
        step = PlanStepRecord.from_dict(payload)
        assert step.index == 3

    def test_frozen_dataclass(self) -> None:
        """PlanStepRecord should be immutable."""
        step = PlanStepRecord(index=1, text="test", done=False, evidence=None, completed_at=None)
        with pytest.raises(FrozenInstanceError):
            step.done = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PlanRecord contracts
# ---------------------------------------------------------------------------


class TestPlanRecordContract:
    """Contract tests for PlanRecord serialization and lifecycle."""

    def test_to_dict_serializes_all_fields(self) -> None:
        """to_dict should produce a complete JSON-serializable payload."""
        record = PlanRecord(
            plan_id="plan-abc123",
            title="Test Plan",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
            steps=(),
        )
        d = record.to_dict()
        assert d["plan_id"] == "plan-abc123"
        assert d["title"] == "Test Plan"
        assert isinstance(d["steps"], list)

    def test_from_dict_roundtrip(self) -> None:
        """PlanRecord should round-trip through dict serialization."""
        original = PlanRecord(
            plan_id="plan-xyz",
            title="Round Trip",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-02T00:00:00",
            steps=(
                PlanStepRecord(index=1, text="Step 1", done=False, evidence=None, completed_at=None),
                PlanStepRecord(index=2, text="Step 2", done=True, evidence="done", completed_at="2024-01-02T00:00:00"),
            ),
        )
        payload = original.to_dict()
        restored = PlanRecord.from_dict(payload)
        assert restored.plan_id == original.plan_id
        assert restored.title == original.title
        assert len(restored.steps) == len(original.steps)
        assert restored.steps[0].text == original.steps[0].text

    def test_from_dict_handles_empty_steps(self) -> None:
        """from_dict should handle missing or empty steps."""
        payload = {"plan_id": "p1", "title": "no steps"}
        record = PlanRecord.from_dict(payload)
        assert record.plan_id == "p1"
        assert record.steps == ()

    def test_from_dict_ignores_non_dict_steps(self) -> None:
        """from_dict should skip non-dict entries in steps list."""
        payload = {"plan_id": "p1", "title": "bad steps", "steps": ["not a dict", 123]}
        record = PlanRecord.from_dict(payload)
        assert record.steps == ()


# ---------------------------------------------------------------------------
# _normalize_steps contracts
# ---------------------------------------------------------------------------


class TestNormalizeStepsContract:
    """Contract tests for step normalization."""

    def test_passes_through_list(self) -> None:
        """A list of non-empty strings should be normalized to a tuple."""
        result = _normalize_steps(["Step 1", "Step 2"])
        assert result == ("Step 1", "Step 2")

    def test_passes_through_tuple(self) -> None:
        """A tuple should be normalized to a clean tuple."""
        result = _normalize_steps(("A", "B"))
        assert result == ("A", "B")

    def test_strips_whitespace(self) -> None:
        """Steps with leading/trailing whitespace should be stripped."""
        result = _normalize_steps(["  Step 1  ", "  Step 2  "])
        assert result == ("Step 1", "Step 2")

    def test_filters_empty_strings(self) -> None:
        """Empty strings should be filtered out."""
        result = _normalize_steps(["Step 1", "", "  ", "Step 2"])
        assert result == ("Step 1", "Step 2")

    def test_returns_empty_for_none(self) -> None:
        """None input should produce empty tuple."""
        assert _normalize_steps(None) == ()

    def test_returns_empty_for_empty_list(self) -> None:
        """Empty list should produce empty tuple."""
        assert _normalize_steps([]) == ()

    def test_parses_markdown_bullets_from_plan_string(self) -> None:
        """Markdown bullet prefixes should be stripped when parsing from plan string."""
        result = _normalize_steps(None, plan="- Step 1\n* Step 2\n  - Step 3")
        assert result == ("Step 1", "Step 2", "Step 3")

    def test_parses_numbered_list_from_plan_string(self) -> None:
        """Numbered list prefixes should be stripped when parsing from plan string."""
        result = _normalize_steps(None, plan="1. Step 1\n2) Step 2\n3.  Step 3")
        assert result == ("Step 1", "Step 2", "Step 3")

    def test_parses_multiline_plan_string(self) -> None:
        """A multiline plan string should be parsed into steps."""
        plan = "- Step one\n- Step two\n- Step three"
        result = _normalize_steps(None, plan=plan)
        assert result == ("Step one", "Step two", "Step three")

    def test_steps_takes_precedence_over_plan(self) -> None:
        """When both steps and plan are provided, steps takes precedence."""
        result = _normalize_steps(["Step A", "Step B"], plan="- Ignored")
        assert result == ("Step A", "Step B")


# ---------------------------------------------------------------------------
# PlanExecutionService contracts
# ---------------------------------------------------------------------------


class TestPlanExecutionServiceContract:
    """Contract tests for PlanExecutionService behavioral contracts."""

    @pytest.fixture
    def tmp_project(self) -> Path:
        """Create a temporary project root."""
        tmp = Path(tempfile.mkdtemp())
        yield tmp
        # Cleanup
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    def test_create_plan_requires_steps(self, tmp_project: Path) -> None:
        """create_plan should raise ValueError when no steps provided."""
        service = PlanExecutionService(project_root=tmp_project)
        with pytest.raises(ValueError, match="At least one plan step is required"):
            service.create_plan()

    def test_create_plan_with_steps(self, tmp_project: Path) -> None:
        """create_plan should create a record with normalized steps."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(title="My Plan", steps=["Do X", "Do Y"])
        assert record.plan_id.startswith("plan-")
        assert record.title == "My Plan"
        assert len(record.steps) == 2
        assert record.steps[0].text == "Do X"
        assert record.steps[0].done is False
        assert record.steps[1].text == "Do Y"

    def test_create_plan_with_markdown_plan(self, tmp_project: Path) -> None:
        """create_plan should parse a markdown plan string."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(plan="- Step A\n- Step B\n- Step C")
        assert len(record.steps) == 3
        assert record.steps[0].text == "Step A"

    def test_create_plan_default_title(self, tmp_project: Path) -> None:
        """create_plan should use 'plan' as default title."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["Step"])
        assert record.title == "plan"

    def test_create_plan_empty_title(self, tmp_project: Path) -> None:
        """create_plan should use 'plan' when title is empty/whitespace."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(title="   ", steps=["Step"])
        assert record.title == "plan"

    def test_list_plans_empty(self, tmp_project: Path) -> None:
        """list_plans should return empty list when no plans exist."""
        service = PlanExecutionService(project_root=tmp_project)
        plans = service.list_plans()
        assert plans == []

    def test_list_plans_sorted_by_created_at(self, tmp_project: Path) -> None:
        """list_plans should return plans sorted by creation time."""
        service = PlanExecutionService(project_root=tmp_project)
        service.create_plan(steps=["A"])
        service.create_plan(steps=["B"])
        plans = service.list_plans()
        assert len(plans) == 2
        assert plans[0].created_at <= plans[1].created_at

    def test_get_plan_returns_record(self, tmp_project: Path) -> None:
        """get_plan should return the record for a known plan_id."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["Step"])
        retrieved = service.get_plan(record.plan_id)
        assert retrieved is not None
        assert retrieved.plan_id == record.plan_id

    def test_get_plan_returns_none_for_unknown(self, tmp_project: Path) -> None:
        """get_plan should return None for an unknown plan_id."""
        service = PlanExecutionService(project_root=tmp_project)
        assert service.get_plan("nonexistent") is None

    def test_next_step_returns_first_pending(self, tmp_project: Path) -> None:
        """next_step should return the first incomplete step."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["A", "B", "C"])
        step = service.next_step(record.plan_id)
        assert step is not None
        assert step.index == 1

    def test_next_step_returns_none_when_all_done(self, tmp_project: Path) -> None:
        """next_step should return None when all steps are complete."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["A"])
        service.complete_step(record.plan_id, step=1, evidence="done")
        assert service.next_step(record.plan_id) is None

    def test_complete_step_must_be_in_order(self, tmp_project: Path) -> None:
        """complete_step should raise when completing out of order."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["A", "B", "C"])
        with pytest.raises(ValueError, match="out of order"):
            service.complete_step(record.plan_id, step=2)

    def test_complete_step_updates_record(self, tmp_project: Path) -> None:
        """complete_step should mark the step done and update timestamps."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["A", "B"])
        updated = service.complete_step(record.plan_id, step=1, evidence="proof")
        assert updated.steps[0].done is True
        assert updated.steps[0].evidence == "proof"
        assert updated.steps[0].completed_at is not None
        assert updated.updated_at != record.updated_at

    def test_complete_step_strips_evidence(self, tmp_project: Path) -> None:
        """complete_step should strip whitespace from evidence."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["A"])
        updated = service.complete_step(record.plan_id, step=1, evidence="  proof  ")
        assert updated.steps[0].evidence == "proof"

    def test_complete_step_empty_evidence_is_none(self, tmp_project: Path) -> None:
        """complete_step should set evidence to None when empty/whitespace."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["A"])
        updated = service.complete_step(record.plan_id, step=1, evidence="   ")
        assert updated.steps[0].evidence is None

    def test_render_status(self, tmp_project: Path) -> None:
        """render_status should produce a readable status report."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(steps=["A", "B"])
        service.complete_step(record.plan_id, step=1)
        status = service.render_status(record.plan_id)
        assert "[done] 1. A" in status
        assert "[pending] 2. B" in status

    def test_require_plan_raises_key_error(self, tmp_project: Path) -> None:
        """Accessing a nonexistent plan should raise KeyError."""
        service = PlanExecutionService(project_root=tmp_project)
        with pytest.raises(KeyError, match="not found"):
            service.next_step("nonexistent")

    def test_persistence_roundtrip(self, tmp_project: Path) -> None:
        """Plans should survive service restart (reload from disk)."""
        service = PlanExecutionService(project_root=tmp_project)
        record = service.create_plan(title="Persisted", steps=["A", "B"])
        service.complete_step(record.plan_id, step=1, evidence="done")

        # Create a new service instance (simulates restart)
        service2 = PlanExecutionService(project_root=tmp_project)
        restored = service2.get_plan(record.plan_id)
        assert restored is not None
        assert restored.title == "Persisted"
        assert restored.steps[0].done is True
        assert restored.steps[0].evidence == "done"
        assert restored.steps[1].done is False
