"""Provider budget hooks match serialized requests without network activity."""

import json
from collections.abc import AsyncIterator
from copy import deepcopy
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.base import Message, ModelProvider, StreamChunk, ToolCall, ToolDeclaration
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.utils.tokens import TokenCounter


class CustomProvider(ModelProvider):
    @property
    def name(self) -> str:
        return "custom"

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="unused")


def compatible(**options: Any) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        api_key="private-key",
        base_url="http://127.0.0.1:18080/v1",
        default_model="unknown-local-model",
        **options,
    )


def test_custom_provider_has_portable_default_and_frozen_budget() -> None:
    from henchman.providers.request_budget import OutputBudget

    budget = CustomProvider().prepare_output_budget(512)
    assert isinstance(budget, OutputBudget)
    assert budget.output_tokens == 512
    assert budget.request_options == {"max_tokens": 512}
    with pytest.raises(FrozenInstanceError):
        budget.output_tokens = 1  # type: ignore[misc]


@pytest.mark.parametrize("value", [None, True, False, 0, -1, 1.5, "512", float("inf")])
def test_invalid_default_caps_are_rejected(value: Any) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        CustomProvider().prepare_output_budget(value)


@pytest.mark.parametrize(
    ("options", "field", "expected"),
    [
        ({}, "max_tokens", 512),
        ({"max_tokens": 300}, "max_tokens", 300),
        ({"max_completion_tokens": 400}, "max_completion_tokens", 400),
        ({"extra_body": {"max_tokens": 200}}, "max_tokens", 200),
        ({"max_tokens": 300, "extra_body": {"max_tokens": 200}}, "max_tokens", 200),
        (
            {"max_completion_tokens": 400, "extra_body": {"max_completion_tokens": 100}},
            "max_completion_tokens",
            100,
        ),
    ],
)
def test_compatible_cap_matches_effective_wire_body(
    options: dict[str, Any],
    field: str,
    expected: int,
) -> None:
    provider = compatible(**options)
    before = deepcopy(provider.request_defaults)
    budget = provider.prepare_output_budget(512)
    params = provider._build_request_params(
        [Message("user", "hello")], None, budget.request_options
    )
    wire = {**params, **(params.get("extra_body") or {})}
    assert budget.output_tokens == wire[field] == expected
    assert provider.request_defaults == before
    assert budget.request_options == {field: expected}
    assert "private-key" not in str(budget)


@pytest.mark.parametrize(
    "options",
    [
        {"max_tokens": 10, "max_completion_tokens": 10},
        {"max_tokens": 10, "extra_body": {"max_completion_tokens": 20}},
        {"max_tokens": None},
        {"max_tokens": False},
        {"max_completion_tokens": 0},
        {"extra_body": {"max_tokens": -1}},
        {"extra_body": {"max_completion_tokens": "10"}},
        {"extra_body": []},
        {"extra_body": {"messages": []}},
        {"extra_body": {"tools": []}},
    ],
)
def test_compatible_rejects_ambiguous_or_unaccountable_options(options: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        compatible(**options).prepare_output_budget(512)


def test_anthropic_reserves_configured_cap_actually_sent() -> None:
    provider = AnthropicProvider(api_key="private-key", max_tokens=777)
    budget = provider.prepare_output_budget(128)
    system, messages = provider._format_messages(
        [Message("system", "rules"), Message("user", "hello")]
    )
    params = provider._prepare_request_params(system, messages, None, dict(budget.request_options))
    assert budget.output_tokens == params["max_tokens"] == 777
    assert provider.max_tokens == 777


@pytest.mark.parametrize("value", [0, -1, True, "100", None])
def test_anthropic_rejects_invalid_configured_cap(value: Any) -> None:
    with pytest.raises(ValueError):
        AnthropicProvider(api_key="key", max_tokens=value).prepare_output_budget(100)


@pytest.mark.parametrize("kind", ["custom", "compatible", "anthropic"])
def test_estimate_counts_input_wire_fields_without_provider_secrets(
    kind: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider: ModelProvider = {
        "custom": CustomProvider(),
        "compatible": compatible(extra_headers={"Secret": "hidden-header"}),
        "anthropic": AnthropicProvider(api_key="private-key"),
    }[kind]
    captured: list[str] = []

    def count(text: str, model: str | None = None) -> int:
        assert model is None or isinstance(model, str)
        captured.append(text)
        return len(text)

    monkeypatch.setattr(TokenCounter, "count_text", count)
    messages = [
        Message("system", "system-marker"),
        Message("user", "request-marker"),
        Message(
            "assistant",
            "answer-marker",
            [ToolCall("call-1", "edit", {"source": "argument-marker"})],
            reasoning_content="reasoning-marker",
        ),
        Message("tool", "result-marker", tool_call_id="call-1"),
    ]
    tools = [
        ToolDeclaration(
            "edit",
            "tool-description",
            {
                "type": "object",
                "properties": {"source": {"type": "string", "description": "schema-marker"}},
            },
        )
    ]
    before = deepcopy((messages, tools))
    estimate = provider.estimate_input_tokens(messages, tools)
    assert len(captured) == 1
    payload = json.loads(captured[0])
    assert estimate >= len(captured[0])
    for marker in (
        "system-marker",
        "request-marker",
        "argument-marker",
        "result-marker",
        "tool-description",
        "schema-marker",
    ):
        assert marker in captured[0]
    assert "private-key" not in captured[0] and "hidden-header" not in captured[0]
    assert "127.0.0.1" not in captured[0]
    if kind == "anthropic":
        assert payload["system"] == "system-marker"
        assert payload["tools"][0]["input_schema"] == tools[0].parameters
        # This adapter does not send reasoning_content on its wire format.
        assert "reasoning-marker" not in captured[0]
    else:
        assert "reasoning-marker" in captured[0]
    assert (messages, tools) == before


def test_large_tools_and_reasoning_increase_estimate() -> None:
    provider = compatible()
    plain = [Message("user", "hello")]
    base = provider.estimate_input_tokens(plain, None)
    tools = [
        ToolDeclaration(f"tool_{index}", "description " * 50, {"type": "object"})
        for index in range(8)
    ]
    assert provider.estimate_input_tokens(plain, tools) > base + 100
    assert (
        provider.estimate_input_tokens(
            [*plain, Message("assistant", "answer", reasoning_content="reason " * 300)], None
        )
        > base + 100
    )


def test_known_schema_options_use_effective_extra_body_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    def count(text: str, model: str | None = None) -> int:
        assert model is None or isinstance(model, str)
        captured.append(text)
        return len(text)

    monkeypatch.setattr(TokenCounter, "count_text", count)
    provider = compatible(
        response_format={"type": "json_schema", "json_schema": {"name": "old-schema"}},
        tool_choice="auto",
        extra_body={
            "response_format": {"type": "json_schema", "json_schema": {"name": "effective-schema"}},
            "tool_choice": {"type": "function", "function": {"name": "chosen-tool"}},
            "opaque_extension": "not-counted",
        },
    )
    provider.estimate_input_tokens([Message("user", "hello")], None)
    payload = json.loads(captured[0])
    assert payload["response_format"]["json_schema"]["name"] == "effective-schema"
    assert payload["tool_choice"]["function"]["name"] == "chosen-tool"
    assert "old-schema" not in captured[0]
    assert "not-counted" not in captured[0]
