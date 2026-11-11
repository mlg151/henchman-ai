"""Task launch intent and operation links have an explicit public shape."""

from tests.advanced.test_task_store import record
from tests.contracts.helpers import assert_contract_matches


def test_queued_task_contract_has_nullable_start_and_explicit_identity(contract_suite):
    payload = record()
    payload["operation_context"] = {
        "operation_id": "operation", "project_hash": "project", "session_id": "session",
        "run_id": "run", "turn_id": "turn", "agent_id": "agent", "tool_call_id": "call",
    }
    assert_contract_matches(contract_suite=contract_suite, payload=payload, schema_name="advanced/task_record")
