"""Tool display names are evidence; exact call identities retain correlation."""

import json
from copy import deepcopy

import pytest

from henchman.core.event_evidence import EventEvidenceRedactor
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import ToolCall
from henchman.utils.evidence_redaction import EvidenceRedactor


@pytest.mark.parametrize("secret", ["private-canary", "x", "name", "read_file", 'quoted"\\\nΩ'])
def test_tool_request_name_is_projected_without_changing_executable_call(secret):
    policy = EvidenceRedactor([secret, "call-id", "agent-id"])
    name = f"unknown_{secret}"
    call = ToolCall("call-id", name, {"payload": secret})
    event = AgentEvent(EventType.TOOL_CALL_REQUEST, call, "agent-id")
    projected = EventEvidenceRedactor(policy).project(event)[0]
    assert projected.data["id"] == "call-id"
    assert projected.source_agent == "agent-id"
    assert projected.data["name"] == "unknown_[REDACTED]"
    assert projected.data["arguments"]["payload"] == "[REDACTED]"
    assert call.name == name and call.arguments == {"payload": secret}
    assert event.data is call


@pytest.mark.parametrize("secret", ["private-canary", "x", "tool_name", "read_file", 'quoted"\\\nΩ'])
def test_tool_result_display_names_are_projected_but_ids_are_unchanged(secret):
    policy = EvidenceRedactor([secret, "call-id", "agent-id"])
    data = {"id": "call-id", "tool_call_id": "call-id", "name": secret, "tool_name": secret,
            "result": f"Tool {secret} unavailable", "success": False}
    original = deepcopy(data)
    projected = EventEvidenceRedactor(policy).project(AgentEvent(EventType.TOOL_CALL_RESULT, data, "agent-id"))[0]
    assert projected.data["id"] == projected.data["tool_call_id"] == "call-id"
    assert projected.source_agent == "agent-id"
    assert projected.data["name"] == projected.data["tool_name"] == "[REDACTED]"
    assert projected.data["result"] == "Tool [REDACTED] unavailable"
    assert projected.data["success"] is False
    assert data == original


@pytest.mark.parametrize("escaped", [False, True])
def test_nested_typed_results_do_not_exempt_names_or_change_raw_evidence(escaped):
    secret = 'nested"\\\nprivate-canary'
    value = json.dumps(secret)[1:-1] if escaped else secret
    data = {"tool_call_id": "call", "tool_name": value, "result": "failure", "success": False,
            "tool_result": {"success": False, "error": value, "structured_content_present": True,
                "structured_content": {"name": value, "tool_name": value},
                "content_blocks": [{"type": "resource_link", "name": value, "uri": value}],
                "metadata": {"api_key": secret, "name": value, "tool_name": value}}}
    original = deepcopy(data)
    # The marked nested credential must also protect the earlier outer name.
    shown = EventEvidenceRedactor(EvidenceRedactor()).project(AgentEvent(EventType.TOOL_CALL_RESULT, data))[0].data
    assert shown["tool_name"] == "[REDACTED]"
    typed = shown["tool_result"]
    assert typed["structured_content"] == {"name": "[REDACTED]", "tool_name": "[REDACTED]"}
    assert typed["content_blocks"] == [{"type": "resource_link", "name": "[REDACTED]", "uri": "[REDACTED]"}]
    assert typed["metadata"] == {"api_key": "[REDACTED]", "name": "[REDACTED]", "tool_name": "[REDACTED]"}
    assert typed["success"] is False and typed["structured_content_present"] is True
    assert data == original


def test_ordinary_names_and_reused_call_ids_retain_exact_agent_correlation():
    projector = EventEvidenceRedactor(EvidenceRedactor(["call", "one", "two"]))
    for actor in ("one", "two"):
        request = projector.project(AgentEvent(EventType.TOOL_CALL_REQUEST, ToolCall("call", "read_file", {}), actor))[0]
        result = projector.project(AgentEvent(EventType.TOOL_CALL_RESULT, {"tool_call_id": "call", "tool_name": "read_file", "result": "ok"}, actor))[0]
        assert request.source_agent == result.source_agent == actor
        assert request.data["id"] == result.data["tool_call_id"] == "call"
        assert request.data["name"] == result.data["tool_name"] == "read_file"
