"""Team delegations carry bounded instruction provenance to specialists."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from henchman.agents.delegation import _populate_execution_params
from henchman.agents.orchestrator_types import DelegationParams
from henchman.config.context import ContextLoader, ContextSnapshot


def _params(agent: SimpleNamespace) -> DelegationParams:
    return DelegationParams(
        target_role="engineer",
        task="Implement the change",
        brief=None,
        target_agent=agent,
    )


class FakeRunner:
    def __init__(self, snapshot: ContextSnapshot | None) -> None:
        self.instruction_snapshot = snapshot
        self.ledger = None

    def _prepare_delegation_context(
        self, role: str, brief: dict[str, Any] | None, task: str = "",
    ) -> dict[str, Any]:
        return dict(brief or {})

    def _assemble_delegation_input(
        self, task: str, brief: dict[str, Any] | None, mission: str | None = None,
    ) -> str:
        return f"TASK: {task}"


@pytest.fixture
def instruction_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> ContextSnapshot:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    project = (tmp_path / "project").resolve()
    project.mkdir()
    (project / ".git").mkdir()
    (project / "AGENTS.md").write_text("Team provenance instructions", encoding="utf-8")
    return ContextLoader(start_dir=project).load_snapshot()


def test_delegation_input_includes_provenance_appendix(
    instruction_snapshot: ContextSnapshot,
) -> None:
    agent = SimpleNamespace(messages=[])
    params = _params(agent)

    _populate_execution_params(FakeRunner(instruction_snapshot), params, agent)

    assert "Project instruction provenance" in params.full_task
    assert str(instruction_snapshot.sources[0].path) in params.full_task
    assert "Team provenance instructions" not in params.full_task
    assert "tool policy" in params.full_task


def test_delegation_input_without_snapshot_is_unchanged() -> None:
    agent = SimpleNamespace(messages=[])
    params = _params(agent)

    _populate_execution_params(FakeRunner(None), params, agent)

    assert params.full_task == "TASK: Implement the change"
