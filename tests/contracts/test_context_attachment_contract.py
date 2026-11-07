"""Canonical message contracts include validated attached context evidence."""

from dataclasses import asdict

import pytest

from henchman.core.session import SessionManager, SessionMessage
from tests.contracts.helpers import assert_contract_matches
from tests.core.test_context_attachments import attachment_message


@pytest.mark.parametrize("schema", ["providers/message", "runtime/message", "runtime/session_message"])
def test_message_attachment_contract(contract_suite, schema):
    message = attachment_message()
    payload = asdict(message) if schema != "runtime/session_message" else SessionMessage(**asdict(message)).to_dict()
    assert_contract_matches(payload=payload, schema_name=schema, contract_suite=contract_suite)


def test_session_attachment_contract(contract_suite):
    manager = SessionManager()
    session = manager.create_session("project")
    session.messages = [SessionMessage(**asdict(attachment_message()))]
    assert_contract_matches(payload=session.to_dict(), schema_name="runtime/session", contract_suite=contract_suite)
