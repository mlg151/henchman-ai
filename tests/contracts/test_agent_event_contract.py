"""Contract tests for AgentEvent with typed payloads."""

from henchman.core.event_payloads import (
    AgentCompletedPayload,
    AgentStartedPayload,
    FinishedPayload,
    ToolCallRequestPayload,
    ToolCallResultPayload,
)
from henchman.core.events import AgentEvent, EventType
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def test_agent_started_event_contract(contract_suite):
    payload = AgentStartedPayload(agent="tech_lead")
    event = AgentEvent(type=EventType.AGENT_STARTED, data=payload, source_agent="orchestrator")

    assert_contract_matches(
        payload=serialize_contract_value(event),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )

def test_agent_completed_event_contract(contract_suite):
    payload = AgentCompletedPayload(agent="coder", status="completed", summary="Fixed the bug")
    event = AgentEvent(type=EventType.AGENT_COMPLETED, data=payload, source_agent="orchestrator")

    assert_contract_matches(
        payload=serialize_contract_value(event),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )

def test_tool_call_request_event_contract(contract_suite):
    payload = ToolCallRequestPayload(id="call_1", name="read_file", arguments={"path": "test.txt"})
    event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=payload, source_agent="coder")

    assert_contract_matches(
        payload=serialize_contract_value(event),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )

def test_tool_call_result_event_contract(contract_suite):
    payload = ToolCallResultPayload(
        tool_call_id="call_1",
        tool_name="read_file",
        result="file contents",
        success=True
    )
    event = AgentEvent(type=EventType.TOOL_CALL_RESULT, data=payload, source_agent="coder")

    assert_contract_matches(
        payload=serialize_contract_value(event),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )

def test_finished_event_contract(contract_suite):
    payload = FinishedPayload(finish_reason="stop", usage={"total_tokens": 100})
    event = AgentEvent(type=EventType.FINISHED, data=payload, source_agent="coder")

    assert_contract_matches(
        payload=serialize_contract_value(event),
        schema_name="runtime/agent_event",
        contract_suite=contract_suite,
    )
