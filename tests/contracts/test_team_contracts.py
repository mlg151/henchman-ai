"""Contract tests for team collaboration records.

These tests validate that TeamWorkspaceRecord, TeamMessageRecord,
SharedFileRecord, WorkflowDefinitionRecord, and WorkflowRunRecord
payloads conform to their published JSON Schema contracts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.team.collaboration import (
    SharedFileRecord,
    TeamMessageRecord,
    TeamWorkspaceRecord,
    WorkflowDefinitionRecord,
    WorkflowRunRecord,
)
from tests.contracts.helpers import assert_contract_matches

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_workspace_record() -> TeamWorkspaceRecord:
    """A representative TeamWorkspaceRecord."""
    return TeamWorkspaceRecord(
        workspace_id="test-workspace",
        name="Test Workspace",
        description="A workspace for testing contracts.",
        members=("alice", "bob"),
        created_at="2026-04-24T12:00:00Z",
        workspace_path=Path("/tmp/test-workspace"),
    )


@pytest.fixture
def sample_message_record() -> TeamMessageRecord:
    """A representative TeamMessageRecord."""
    return TeamMessageRecord(
        message_id="msg-123",
        workspace_id="test-workspace",
        channel="general",
        sender="alice",
        body="Hello, team!",
        recipients=("bob",),
        created_at="2026-04-24T12:05:00Z",
    )


@pytest.fixture
def sample_shared_file_record() -> SharedFileRecord:
    """A representative SharedFileRecord."""
    return SharedFileRecord(
        file_id="file-456",
        workspace_id="test-workspace",
        sender="alice",
        original_path="/home/alice/data.csv",
        shared_path=Path("/tmp/test-workspace/shared/data.csv"),
        recipient="bob",
        note="Check this data.",
        created_at="2026-04-24T12:10:00Z",
    )


@pytest.fixture
def sample_workflow_definition() -> WorkflowDefinitionRecord:
    """A representative WorkflowDefinitionRecord."""
    return WorkflowDefinitionRecord(
        workflow_id="wf-789",
        workspace_id="test-workspace",
        workflow_name="CI/CD",
        steps=("build", "test", "deploy"),
        created_by="alice",
        created_at="2026-04-24T12:15:00Z",
    )


@pytest.fixture
def sample_workflow_run() -> WorkflowRunRecord:
    """A representative WorkflowRunRecord."""
    return WorkflowRunRecord(
        run_id="run-101",
        workspace_id="test-workspace",
        workflow_name="CI/CD",
        status="completed",
        requested_by="bob",
        inputs={"branch": "main", "env": "prod"},
        executed_steps=("build", "test", "deploy"),
        trigger_name="git-push",
        bridge_session_id="session-xyz",
        created_at="2026-04-24T12:20:00Z",
    )


# ---------------------------------------------------------------------------
# Team Record Contracts
# ---------------------------------------------------------------------------


class TestTeamRecordContracts:
    """Team records must satisfy their JSON Schema contracts."""

    def test_workspace_record_matches_contract(
        self, contract_suite: object, sample_workspace_record: TeamWorkspaceRecord
    ) -> None:
        payload = sample_workspace_record.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="team/team_workspace_record",
        )

    def test_message_record_matches_contract(
        self, contract_suite: object, sample_message_record: TeamMessageRecord
    ) -> None:
        payload = sample_message_record.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="team/team_message_record",
        )

    def test_shared_file_record_matches_contract(
        self, contract_suite: object, sample_shared_file_record: SharedFileRecord
    ) -> None:
        payload = sample_shared_file_record.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="team/shared_file_record",
        )

    def test_workflow_definition_record_matches_contract(
        self, contract_suite: object, sample_workflow_definition: WorkflowDefinitionRecord
    ) -> None:
        payload = sample_workflow_definition.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="team/workflow_definition_record",
        )

    def test_workflow_run_record_matches_contract(
        self, contract_suite: object, sample_workflow_run: WorkflowRunRecord
    ) -> None:
        payload = sample_workflow_run.to_dict()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="team/workflow_run_record",
        )
