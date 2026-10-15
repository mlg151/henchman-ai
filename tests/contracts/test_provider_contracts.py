"""Contract tests for model providers."""

from __future__ import annotations

import pytest

from henchman.providers.base import (
    FinishReason,
    Message,
    ModelProvider,
    StreamChunk,
    ToolCall,
    ToolDeclaration,
)
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value
from tests.contracts.verify_provider import verify_provider_contract


def test_model_provider_is_abstract() -> None:
    """ModelProvider should be an abstract base class that cannot be instantiated directly."""
    try:
        ModelProvider()
    except TypeError as e:
        assert "Can't instantiate abstract class" in str(e)
    else:
        pytest.fail(f"Did not raise! abstractmethods: {getattr(ModelProvider, '__abstractmethods__', 'None')}")


def test_model_provider_contract_methods() -> None:
    """Concrete implementations must provide required methods and properties."""

    class IncompleteProvider(ModelProvider):
        pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompleteProvider"):
        IncompleteProvider()


@pytest.mark.asyncio
async def test_valid_provider_satisfies_contract() -> None:
    """A valid provider should pass the verification suite."""

    class ValidProvider(ModelProvider):
        @property
        def name(self) -> str:
            return "valid"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            yield StreamChunk(content="ok", finish_reason=FinishReason.STOP)

    provider = ValidProvider()
    await verify_provider_contract(provider)


@pytest.mark.asyncio
async def test_invalid_provider_fails_contract() -> None:
    """A provider that misses finish_reason should fail the verification suite."""

    class InvalidProvider(ModelProvider):
        @property
        def name(self) -> str:
            return "invalid"

        async def chat_completion_stream(self, messages, tools=None, **kwargs):
            yield StreamChunk(content="no finish reason here")

    provider = InvalidProvider()
    with pytest.raises(AssertionError, match="No chunk contained a finish_reason"):
        await verify_provider_contract(provider)


def test_provider_models_match_contracts(contract_suite) -> None:
    """Serialized provider models should satisfy their contracts."""
    message = Message(role="assistant", content="hello", reasoning_content="thinking...")
    tool_call = ToolCall(id="1", name="test", arguments={"a": 1})
    tool_decl = ToolDeclaration(name="test", description="desc", parameters={"type": "object"})
    chunk = StreamChunk(content="hi", finish_reason=FinishReason.STOP)

    assert_contract_matches(
        payload=serialize_contract_value(message),
        schema_name="providers/message",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(tool_call),
        schema_name="providers/tool_call",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(tool_decl),
        schema_name="providers/tool_declaration",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(chunk),
        schema_name="providers/stream_chunk",
        contract_suite=contract_suite,
    )
