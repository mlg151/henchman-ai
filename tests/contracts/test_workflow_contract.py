"""Portable workflow references retain identity without dispatch permission."""

from copy import deepcopy

import pytest

from henchman.core.session_data import Session, session_from_dict
from henchman.core.workflow_state import WorkflowReference
from tests.contracts.helpers import assert_contract_matches, load_contract_schema


def test_workflow_reference_contract_and_strict_roundtrip(contract_suite):
    session = Session("session", "project", "now", "now")
    session.workflow = WorkflowReference(store_id="store", project_hash="project", session_id="session")
    payload = session.to_dict()
    assert_contract_matches(payload=payload, schema_name="runtime/session", contract_suite=contract_suite)
    assert session_from_dict(payload).workflow == session.workflow
    assert session_from_dict(payload).workflow_runtime is None
    invalid = deepcopy(payload)
    invalid["workflow"]["dispatch_authorized"] = True
    assert contract_suite.validate_json_schema(invalid, load_contract_schema("runtime/session"))
    with pytest.raises(ValueError):
        session_from_dict(invalid)
