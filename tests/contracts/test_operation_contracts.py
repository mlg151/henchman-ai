"""Session recovery evidence has a strict public persistence shape."""

from copy import deepcopy

from henchman.core.operation_bindings import (
    OperationBinding,
    OperationContext,
    OperationConversation,
    OperationSessionReference,
    SessionOperationState,
)
from henchman.core.session_data import Session, session_from_dict
from henchman.core.session_models import SessionMessage
from tests.contracts.helpers import assert_contract_matches, load_contract_schema


def test_operation_binding_session_contract_and_roundtrip(contract_suite):
    session = Session("session", "project", "today", "today")
    session.operations = SessionOperationState(
        "durable", OperationSessionReference("store", "project", "session"),
        (OperationBinding("operation", OperationContext("project", "session", "run", "turn", "engineer", "call"), 0, "conversation"),),
        ("operation",),
        (OperationConversation("conversation", (SessionMessage("assistant", tool_calls=[
            {"id": "call", "name": "read_file", "arguments": {"path": "file.py"}},
        ]), SessionMessage("tool", content="contents", tool_call_id="call"))),),
    )
    payload = session.to_dict()
    assert_contract_matches(payload=payload, schema_name="runtime/session", contract_suite=contract_suite)
    assert session_from_dict(payload).operations == session.operations
    invalid = deepcopy(payload)
    invalid["operations"]["bindings"][0]["assistant_index"] = -1
    assert contract_suite.validate_json_schema(invalid, load_contract_schema("runtime/session"))
    invalid = deepcopy(payload)
    invalid["operations"]["reference"]["approval_granted"] = True
    assert contract_suite.validate_json_schema(invalid, load_contract_schema("runtime/session"))
