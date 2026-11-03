"""Regression tests for message reasoning_details contract."""

from __future__ import annotations

import pytest

from henchman.providers.base import Message
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
    m2 = Message(
        role="assistant", content="hi", tool_calls=[], tool_call_id=None, reasoning_content=None
    )
    assert_contract_matches(
        payload=serialize_contract_value(m2),
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
    m4 = Message(
        role="assistant",
        content="hi",
        tool_calls=[],
        tool_call_id=None,
        reasoning_content=None,
        reasoning_details=123,
    )
    with pytest.raises(AssertionError):
        assert_contract_matches(
            payload=serialize_contract_value(m4),
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
