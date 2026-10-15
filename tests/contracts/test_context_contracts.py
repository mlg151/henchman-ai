"""Contract tests for Intelligent Context compaction results."""

from __future__ import annotations

from henchman.providers.base import Message
from henchman.utils.intelligent_context import IntelligentContextManager
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def test_compaction_result_matches_contract(contract_suite) -> None:
    """IntelligentContextManager should produce results that satisfy the contract."""
    manager = IntelligentContextManager()
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Hello " * 100),
    ]

    # Force a result
    result = manager.compact_with_result(messages)

    assert_contract_matches(
        payload=serialize_contract_value(result),
        schema_name="context/compaction_result",
        contract_suite=contract_suite,
    )
