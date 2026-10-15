"""Contract tests for Session, SessionMessage, and related models.

These tests validate that serialised session payloads conform to their
published JSON Schema contracts. The session format is the persisted
representation of all REPL conversations and must remain stable across
software versions.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from henchman.core.session_data import Session
from henchman.core.session_models import (
    SessionMessage,
    TurnSummaryRecord,
)
from tests.contracts.helpers import assert_contract_matches

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def text_message() -> SessionMessage:
    """A plain text user message."""
    return SessionMessage(role="user", content="Hello, can you help me write a parser?")


@pytest.fixture
def tool_call_message() -> SessionMessage:
    """An assistant message with a tool call."""
    return SessionMessage(
        role="assistant",
        content="Let me check that file.",
        tool_calls=[{"name": "read", "arguments": {"path": "/src/main.py"}}],
        tool_call_id="call-abc",
        agent_id="coder",
    )


@pytest.fixture
def tool_result_message() -> SessionMessage:
    """A tool result message."""
    return SessionMessage(
        role="tool",
        content="File contents: def main(): pass",
        tool_call_id="call-abc",
        agent_id="coder",
    )


@pytest.fixture
def populated_session(
    text_message: SessionMessage,
    tool_call_message: SessionMessage,
    tool_result_message: SessionMessage,
) -> Session:
    """A fully-populated Session."""
    return Session(
        id="sess-abc-123",
        project_hash="a1b2c3d4",
        started="2025-01-01T00:00:00Z",
        last_updated="2025-01-01T01:00:00Z",
        messages=[text_message, tool_call_message, tool_result_message],
        tag="feature-x-parser",
        plan_mode=False,
        turn_summaries=[TurnSummaryRecord(turn_number=1, summary_text="User asked for help with parser")],
        active_agents=["coder", "reviewer"],
        delegation_log=[{"from": "tech_lead", "to": "coder", "task": "Write parser"}],
        template_parameters={"language": "python"},
        export_metadata={"exported_at": "2025-01-02T00:00:00Z"},
    )


@pytest.fixture
def minimal_session() -> Session:
    """A Session with only required fields."""
    return Session(
        id="sess-min-001",
        project_hash="deadbeef",
        started="2025-06-01T00:00:00Z",
        last_updated="2025-06-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# SessionMessage contracts
# ---------------------------------------------------------------------------


class TestSessionMessageContract:
    """SessionMessage.to_dict() must satisfy the message contract."""

    def test_text_message_matches_contract(
        self, contract_suite: object, text_message: SessionMessage
    ) -> None:
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=text_message.to_dict(),
            schema_name="runtime/session_message",
        )

    def test_tool_call_message_matches_contract(
        self, contract_suite: object, tool_call_message: SessionMessage
    ) -> None:
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=tool_call_message.to_dict(),
            schema_name="runtime/session_message",
        )

    def test_tool_result_message_matches_contract(
        self, contract_suite: object, tool_result_message: SessionMessage
    ) -> None:
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=tool_result_message.to_dict(),
            schema_name="runtime/session_message",
        )

    def test_message_yaml_roundtrip_preserves_contract(
        self, contract_suite: object, text_message: SessionMessage, tmp_path: Path
    ) -> None:
        yaml_path = tmp_path / "message.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(text_message.to_dict(), f, default_flow_style=False)
        with open(yaml_path) as f:
            reloaded = yaml.safe_load(f)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=reloaded,
            schema_name="runtime/session_message",
        )


# ---------------------------------------------------------------------------
# SessionMetadata contract
# ---------------------------------------------------------------------------


class TestSessionMetadataContract:
    """SessionMetadata must satisfy its contract."""

    def test_metadata_matches_contract(
        self, contract_suite: object, populated_session: Session
    ) -> None:
        meta = populated_session.get_metadata()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(meta),
            schema_name="runtime/session_metadata",
        )

    def test_minimal_metadata_matches_contract(
        self, contract_suite: object, minimal_session: Session
    ) -> None:
        meta = minimal_session.get_metadata()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(meta),
            schema_name="runtime/session_metadata",
        )


# ---------------------------------------------------------------------------
# TurnSummaryRecord contract
# ---------------------------------------------------------------------------


class TestTurnSummaryRecordContract:
    """TurnSummaryRecord.to_dict() must satisfy its contract."""

    def test_turn_summary_matches_contract(
        self, contract_suite: object
    ) -> None:
        record = TurnSummaryRecord(turn_number=1, summary_text="User requested code review")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=record.to_dict(),
            schema_name="runtime/turn_summary_record",
        )

    def test_empty_summary_matches_contract(
        self, contract_suite: object
    ) -> None:
        record = TurnSummaryRecord(turn_number=1, summary_text="")
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=record.to_dict(),
            schema_name="runtime/turn_summary_record",
        )


# ---------------------------------------------------------------------------
# Session contracts
# ---------------------------------------------------------------------------


class TestSessionContract:
    """Session.to_dict() must satisfy the session contract."""

    def test_populated_session_matches_contract(
        self, contract_suite: object, populated_session: Session
    ) -> None:
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=populated_session.to_dict(),
            schema_name="runtime/session",
        )

    def test_minimal_session_matches_contract(
        self, contract_suite: object, minimal_session: Session
    ) -> None:
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=minimal_session.to_dict(),
            schema_name="runtime/session",
        )

    def test_session_json_roundtrip_preserves_contract(
        self, contract_suite: object, populated_session: Session, tmp_path: Path
    ) -> None:
        import json

        json_str = populated_session.to_json()
        reloaded = json.loads(json_str)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=reloaded,
            schema_name="runtime/session",
        )

    def test_session_export_metadata_accepted(
        self, contract_suite: object, populated_session: Session
    ) -> None:
        """Session with export_metadata must still pass the contract."""
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=populated_session.to_dict(),
            schema_name="runtime/session",
        )
