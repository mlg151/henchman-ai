"""Regression tests for message reasoning_details contract."""

from __future__ import annotations

import pytest

from henchman.providers.base import FinishReason, Message, StreamChunk
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def test_message_reasoning_details_regressions(contract_suite) -> None:
    """Verify that reasoning_details in message payloads are correctly handled as optional, opaque fields."""
    # Null
    m1 = Message(
        role="assistant",
        content="hi",
        tool_calls=[],
        tool_call_id=None,
        reasoning_content=None,
        reasoning_details=None,
    )
    assert_contract_matches(
        payload=serialize_contract_value(m1),
        schema_name="runtime/message",
        contract_suite=contract_suite,
    )

    # Missing (should not be in required)
    # The current "missing" test was actually another null test because dataclass serialization
    # emits reasoning_details=None when omitted from constructor.
    m2 = Message(
        role="assistant", content="hi", tool_calls=[], tool_call_id=None, reasoning_content=None
    )
    payload_m2 = serialize_contract_value(m2)
    payload_m2.pop("reasoning_details", None)
    assert_contract_matches(
        payload=payload_m2,
        schema_name="runtime/message",
        contract_suite=contract_suite,
    )

    # String
    m3 = Message(
        role="assistant",
        content="hi",
        tool_calls=[],
        tool_call_id=None,
        reasoning_content=None,
        reasoning_details="some details",
    )
    assert_contract_matches(
        payload=serialize_contract_value(m3),
        schema_name="runtime/message",
        contract_suite=contract_suite,
    )

    # Invalid (number, rejected by additionalProperties: false since it's not a string|null)
    # Injecting invalid values into serialized payload dictionaries, NOT into a Message constructor with the wrong type.
    m4 = Message(
        role="assistant",
        content="hi",
        tool_calls=[],
        tool_call_id=None,
        reasoning_content=None,
        reasoning_details="valid",
    )
    payload_m4 = serialize_contract_value(m4)
    payload_m4["reasoning_details"] = 123
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=payload_m4,
            schema_name="runtime/message",
            contract_suite=contract_suite,
        )

    # Invalid (bool)
    payload_m4["reasoning_details"] = True
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=payload_m4,
            schema_name="runtime/message",
            contract_suite=contract_suite,
        )

    # Invalid (list)
    payload_m4["reasoning_details"] = ["list"]
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=payload_m4,
            schema_name="runtime/message",
            contract_suite=contract_suite,
        )

    # Invalid (object)
    payload_m4["reasoning_details"] = {"obj": 1}
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=payload_m4,
            schema_name="runtime/message",
            contract_suite=contract_suite,
        )

    # Keep genuine null and opaque STRING tests, including a JSON-looking opaque string whose bytes remain untouched.
    m5 = Message(
        role="assistant",
        content="hi",
        tool_calls=[],
        tool_call_id=None,
        reasoning_content=None,
        reasoning_details='{"json_looking": "opaque_string"}',
    )
    assert_contract_matches(
        payload=serialize_contract_value(m5),
        schema_name="runtime/message",
        contract_suite=contract_suite,
    )


def test_message_unknown_fields_rejection(contract_suite) -> None:
    """Verify that unknown fields are rejected in the message contract."""
    # Construct a payload that represents a Message with an unknown field
    payload = {
        "role": "assistant",
        "content": "hi",
        "tool_calls": [],
        "tool_call_id": None,
        "reasoning_content": None,
        "reasoning_details": None,
        "unknown_field": "bad",
    }
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=payload, schema_name="runtime/message", contract_suite=contract_suite
        )


def test_stream_chunk_rejection(contract_suite) -> None:
    """Verify that StreamChunk rejects reasoning_details even if injected into payload."""
    # Serialize a real StreamChunk
    sc = StreamChunk(
        content="chunk",
        tool_calls=[],
        finish_reason=FinishReason.STOP,
        thinking=None,
        usage=None,
    )
    payload = serialize_contract_value(sc)

    # Inject reasoning_details into the serialized payload
    payload["reasoning_details"] = "injected"

    # Prove runtime/stream_chunk rejects it (it's not in the schema)
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=payload,
            schema_name="runtime/stream_chunk",
            contract_suite=contract_suite,
        )
