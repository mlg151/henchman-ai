"""Session references preserve identity but never contain budget balances."""

import pytest

from henchman.core.session_data import Session, SessionAccountingReference, session_from_dict


def test_reference_roundtrips_without_redacting_protocol_identifiers() -> None:
    session = Session("session", "project", "now", "now")
    session.accounting = SessionAccountingReference("store", "active", ("old", "active"))
    for identity in ("store", "active", "old"):
        session.evidence_redactor.register_secret(identity)
    payload = session.to_dict()
    assert payload["accounting"] == {"store_id": "store", "active_run_id": "active", "run_ids": ["old", "active"], "active_owner_key": None}
    assert session_from_dict(payload).accounting == session.accounting
    assert session_from_dict({k: v for k, v in payload.items() if k != "accounting"}).accounting is None


@pytest.mark.parametrize("raw", [
    {"store_id": "", "active_run_id": None, "run_ids": []},
    {"store_id": "store", "active_run_id": "missing", "run_ids": []},
    {"store_id": "store", "active_run_id": None, "run_ids": ["r", "r"]},
    {"store_id": "store", "active_run_id": None, "run_ids": [3]},
    {"store_id": "store", "active_run_id": None, "run_ids": [], "remaining_tokens": 100},
])
def test_invalid_reference_fails_instead_of_becoming_an_unaccounted_session(raw) -> None:
    with pytest.raises(ValueError):
        session_from_dict({"id": "s", "project_hash": "p", "started": "now", "last_updated": "now", "accounting": raw})
