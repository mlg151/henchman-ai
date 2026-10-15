"""Contract tests for WorkingMemory and its entry types.

These tests validate that the serialised shape of WorkingMemory, WorkingMemoryEntry,
DecisionEntry, ActionEntry, and ProblemEntry conform to their published JSON Schema
contracts.

Consumers include the YAML persistence layer, agent loop context injectors, and
the delegation handoff pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from henchman.agents.working_memory import (
    ActionEntry,
    DecisionEntry,
    ProblemEntry,
    WorkingMemory,
    WorkingMemoryEntry,
)
from tests.contracts.helpers import assert_contract_matches

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_entry() -> WorkingMemoryEntry:
    """A fully-populated WorkingMemoryEntry."""
    return WorkingMemoryEntry(
        path="/src/main.py",
        purpose="Reading implementation details",
        lines_read="1-50",
        key_insights=["Entry point found", "Uses factory pattern"],
        timestamp="2025-01-01T00:00:00Z",
    )


@pytest.fixture
def minimal_entry() -> WorkingMemoryEntry:
    """A WorkingMemoryEntry with only required fields."""
    return WorkingMemoryEntry(
        path="/src/utils.py",
        purpose="Quick check",
    )


@pytest.fixture
def populated_memory(populated_entry: WorkingMemoryEntry) -> WorkingMemory:
    """A fully-populated WorkingMemory."""
    return WorkingMemory(
        current_task="Implement feature X",
        task_objectives=["Write core logic", "Add tests", "Document API"],
        recent_files=[populated_entry],
        active_context={"branch": "feature-x", "ticket": "PROJ-123"},
        decisions_made=[
            DecisionEntry(
                decision="Use factory pattern",
                rationale="Better extensibility for future providers",
                impact="high",
            ),
        ],
        completed_steps=["Step 1: Setup", "Step 2: Implement"],
        next_actions=[
            ActionEntry(action="Write unit tests", priority="high", estimated_effort="2h"),
        ],
        insights_gained=["Factory pattern fits well"],
        problems_encountered=[
            ProblemEntry(
                problem="Off-by-one error in loop boundary",
                status="open",
                resolution="",
            ),
        ],
    )


@pytest.fixture
def empty_memory() -> WorkingMemory:
    """A WorkingMemory with all defaults."""
    return WorkingMemory()


# ---------------------------------------------------------------------------
# WorkingMemoryEntry contracts
# ---------------------------------------------------------------------------


class TestWorkingMemoryEntryContract:
    """WorkingMemoryEntry serialised shape must match its contract."""

    def test_populated_entry_matches_contract(
        self, contract_suite: object, populated_entry: WorkingMemoryEntry
    ) -> None:
        payload = populated_entry.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="runtime/working_memory_entry",
        )

    def test_minimal_entry_matches_contract(
        self, contract_suite: object, minimal_entry: WorkingMemoryEntry
    ) -> None:
        payload = minimal_entry.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="runtime/working_memory_entry",
        )

    def test_entry_yaml_roundtrip_preserves_contract(
        self, contract_suite: object, populated_entry: WorkingMemoryEntry, tmp_path: Path
    ) -> None:
        payload = populated_entry.to_dict()
        yaml_path = tmp_path / "entry.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(payload, f, default_flow_style=False)
        with open(yaml_path) as f:
            reloaded = yaml.safe_load(f)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=reloaded,
            schema_name="runtime/working_memory_entry",
        )


# ---------------------------------------------------------------------------
# Entry sub-type contracts
# ---------------------------------------------------------------------------


class TestDecisionEntryContract:
    """DecisionEntry serialised shape must match its contract."""

    def test_decision_entry_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = DecisionEntry(
            decision="Refactor module X",
            rationale="Reducing cyclomatic complexity",
            impact="medium",
        ).to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="runtime/decision_entry",
        )


class TestActionEntryContract:
    """ActionEntry serialised shape must match its contract."""

    def test_action_entry_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = ActionEntry(
            action="Fix bug in parser",
            priority="critical",
            estimated_effort="4h",
        ).to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="runtime/action_entry",
        )


class TestProblemEntryContract:
    """ProblemEntry serialised shape must match its contract."""

    def test_problem_entry_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = ProblemEntry(
            problem="Memory leak in event loop",
            status="in_progress",
            resolution="Added cleanup handler",
        ).to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="runtime/problem_entry",
        )


# ---------------------------------------------------------------------------
# WorkingMemory contracts
# ---------------------------------------------------------------------------


class TestWorkingMemoryContract:
    """WorkingMemory serialised shape must match its contract."""

    def test_populated_memory_matches_contract(
        self, contract_suite: object, populated_memory: WorkingMemory
    ) -> None:
        payload = populated_memory.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="runtime/working_memory",
        )

    def test_empty_memory_matches_contract(
        self, contract_suite: object, empty_memory: WorkingMemory
    ) -> None:
        """Default WorkingMemory must also match (all fields as empty lists/strings)."""
        payload = empty_memory.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="runtime/working_memory",
        )

    def test_memory_yaml_roundtrip_preserves_contract(
        self, contract_suite: object, populated_memory: WorkingMemory, tmp_path: Path
    ) -> None:
        payload = populated_memory.to_dict()
        yaml_path = tmp_path / "memory.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(payload, f, default_flow_style=False)
        with open(yaml_path) as f:
            reloaded = yaml.safe_load(f)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=reloaded,
            schema_name="runtime/working_memory",
        )
