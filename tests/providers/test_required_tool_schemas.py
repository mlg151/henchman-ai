"""Explicit provider tool choices retain required schemas during catalog reduction."""

from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any

import pytest

from henchman.providers.base import Message, ModelProvider, StreamChunk, ToolDeclaration
from henchman.providers.openai_compat import OpenAICompatibleProvider


class CustomProvider(ModelProvider):
    name = "custom"

    async def chat_completion_stream(
        self,
        messages: list[Message],
        tools: list[ToolDeclaration] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content="unused")


def compatible(**options: Any) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        api_key="not-sent",
        base_url="http://127.0.0.1:18080/v1",
        default_model="local-test",
        **options,
    )


def named(name: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name}}


def test_custom_provider_requires_no_specific_schema() -> None:
    assert CustomProvider().required_tool_names() == []


@pytest.mark.parametrize(
    "options", [{}, {"tool_choice": "auto"}, {"tool_choice": "none"}, {"tool_choice": "required"}]
)
def test_unconstrained_choices_require_no_named_schema(options: dict[str, Any]) -> None:
    assert compatible(**options).required_tool_names() == []


def test_named_choice_retained_without_mutating_request() -> None:
    provider = compatible(tool_choice=named("python_ast"))
    original = deepcopy(provider.request_defaults)
    names = provider.required_tool_names()
    assert names == ["python_ast"]
    names.clear()
    assert provider.required_tool_names() == ["python_ast"]
    params = provider._build_request_params([Message("user", "task")], None, {})
    assert params["tool_choice"] == original["tool_choice"]
    assert provider.request_defaults == original


@pytest.mark.parametrize(
    ("choice", "expected"), [(named("pytest_run"), ["pytest_run"]), ("auto", [])]
)
def test_extra_body_choice_overrides_top_level(choice: Any, expected: list[str]) -> None:
    provider = compatible(tool_choice=named("python_ast"), extra_body={"tool_choice": choice})
    before = deepcopy(provider.request_defaults)
    assert provider.required_tool_names() == expected
    assert provider.request_defaults == before


@pytest.mark.parametrize("mode", ["auto", "required"])
def test_allowed_tools_preserves_every_named_function(mode: str) -> None:
    provider = compatible(
        tool_choice={
            "type": "allowed_tools",
            "allowed_tools": {
                "mode": mode,
                "tools": [named("python_ast"), named("pytest_run"), named("python_ast")],
            },
        }
    )
    before = deepcopy(provider.request_defaults)
    assert provider.required_tool_names() == ["python_ast", "pytest_run"]
    assert provider.request_defaults == before


@pytest.mark.parametrize(
    "choice",
    [
        None,
        True,
        "unsupported",
        [],
        {},
        {"type": "function"},
        {"type": "function", "function": "python_ast"},
        named(""),
        named("   "),
        {"type": "function", "function": {"name": 1}},
        {"type": "custom", "custom": {"name": "python_ast"}},
        {"type": "allowed_tools"},
        {
            "type": "allowed_tools",
            "allowed_tools": {"mode": "none", "tools": [named("python_ast")]},
        },
        {"type": "allowed_tools", "allowed_tools": {"mode": "auto", "tools": []}},
        {"type": "allowed_tools", "allowed_tools": {"mode": "auto", "tools": "python_ast"}},
        {
            "type": "allowed_tools",
            "allowed_tools": {"mode": "required", "tools": [named("python_ast"), {}]},
        },
    ],
)
def test_invalid_or_unsupported_choices_fail_closed_only_when_reducing(choice: Any) -> None:
    provider = compatible(tool_choice=choice)
    before = deepcopy(provider.request_defaults)
    assert (
        provider._build_request_params([Message("user", "task")], None, {})["tool_choice"] == choice
    )
    with pytest.raises(ValueError, match="tool_choice"):
        provider.required_tool_names()
    assert provider.request_defaults == before
