"""Contract tests for Session VCR cassettes."""

from __future__ import annotations

from henchman.core.session_data import Session, SessionMessage
from henchman.core.session_vcr import SessionVcrService
from tests.contracts.helpers import assert_contract_matches


def test_vcr_cassette_matches_contract(contract_suite) -> None:
    """SessionVcrService should produce cassettes that satisfy the contract."""
    service = SessionVcrService()
    session = Session(
        id="test-session",
        project_hash="abc",
        started="2026-04-24T12:00:00Z",
        last_updated="2026-04-24T12:00:00Z",
        messages=[
            SessionMessage(role="user", content="hello"),
            SessionMessage(role="assistant", content="hi", tool_calls=[{"id": "1", "type": "function", "function": {"name": "test", "arguments": "{}"}}]),
        ]
    )

    payload = service.build_playback(session)

    assert_contract_matches(
        payload=payload,
        schema_name="vcr/cassette",
        contract_suite=contract_suite,
    )
