"""Five offline adapter payloads preserve canonical optional/null semantics."""

from copy import deepcopy

import pytest

from henchman.providers import (
    AnthropicProvider,
    DeepSeekProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenRouterProvider,
)
from henchman.providers.anthropic import _format_tool_for_anthropic
from henchman.providers.base import Message, ToolDeclaration
from henchman.providers.schema_projections import SchemaProjectionError, project_tool_parameters
from henchman.tools.contracts import SchemaContract

PROVIDERS = ("anthropic", "deepseek", "ollama", "openrouter", "openai_compat")


def schema():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": {"maybe": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
            "type": "object", "properties": {"optional": {"$ref": "#/$defs/maybe"},
                                               "required": {"type": "integer", "minimum": 1}},
            "required": ["required"], "additionalProperties": False}


@pytest.mark.parametrize("provider", PROVIDERS)
def test_projection_preserves_omission_null_and_local_constraints(provider):
    original = schema()
    before = deepcopy(original)
    projected = project_tool_parameters(original, provider)
    assert original == before
    assert projected["required"] == ["required"]
    assert "$defs" not in projected and "$schema" not in projected
    assert "$ref" not in projected["properties"]["optional"]
    for value, valid in [({"required": 1}, True), ({"required": 1, "optional": None}, True),
                         ({"required": 2, "optional": "x"}, True), ({"required": 0}, False),
                         ({"optional": None}, False), ({"required": 1, "optional": 1}, False)]:
        for candidate in (original, projected):
            if valid:
                SchemaContract(candidate).validate(value)
            else:
                with pytest.raises(ValueError):
                    SchemaContract(candidate).validate(value)


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("unsupported", [
    {"if": {"required": ["x"]}, "then": {"required": ["y"]}},
    {"unevaluatedProperties": False},
    {"properties": {"value": {"$ref": "#"}}},
    {"properties": {"x": {"$dynamicRef": "#"}}},
    {"x-unrecognized-assertion": True},
])
def test_unsupported_projections_are_explicit_without_schema_values(provider, unsupported):
    with pytest.raises(SchemaProjectionError, match=provider) as error:
        project_tool_parameters({"type": "object", "description": "private-canary", **unsupported}, provider)
    assert "private-canary" not in str(error.value)


def test_ref_siblings_never_merge_assertions_with_changed_meaning():
    original = {"$defs": {"object": {"type": "object", "properties": {"x": {"type": "integer"}}}},
                "$ref": "#/$defs/object", "additionalProperties": False}
    with pytest.raises(SchemaProjectionError, match="reference_siblings"):
        project_tool_parameters(original, "openai_compat")


def test_projection_expansion_has_an_independent_budget():
    definitions = {"n0": {"type": "string"}}
    for index in range(1, 15):
        definitions[f"n{index}"] = {"type": "object", "properties": {
            "left": {"$ref": f"#/$defs/n{index-1}"}, "right": {"$ref": f"#/$defs/n{index-1}"}}}
    with pytest.raises(SchemaProjectionError, match="projection_limit"):
        project_tool_parameters({"$defs": definitions, "$ref": "#/$defs/n14"}, "anthropic")


def make_adapter(provider):
    classes = {"anthropic": AnthropicProvider, "deepseek": DeepSeekProvider,
               "ollama": OllamaProvider, "openrouter": OpenRouterProvider}
    if provider == "openai_compat":
        adapter = OpenAICompatibleProvider(api_key="offline-test", base_url="http://127.0.0.1:18080/v1", default_model="fixture")
    elif provider == "ollama":
        adapter = OllamaProvider(base_url="http://127.0.0.1:18080/v1", model="fixture")
    else:
        adapter = classes[provider](api_key="offline-test", model="fixture")
    return adapter


@pytest.mark.parametrize("provider", PROVIDERS)
def test_actual_adapter_payload_and_estimate_use_the_same_projection(provider):
    adapter = make_adapter(provider)
    declaration = ToolDeclaration("inspect", "Inspect", schema())
    expected = project_tool_parameters(declaration.parameters, provider)
    if provider == "anthropic":
        assert _format_tool_for_anthropic(declaration)["input_schema"] == expected
    else:
        wire = adapter._build_request_params([Message("user", "task")], [declaration], {})
        assert wire["tools"][0]["function"]["parameters"] == expected
        assert adapter._format_tool(declaration)["function"]["parameters"] == expected
    assert adapter.estimate_input_tokens([Message("user", "task")], [declaration]) > 0
    unsupported = ToolDeclaration("inspect", "Inspect", {"type": "object", "not": {"required": ["x"]}})
    with pytest.raises(SchemaProjectionError):
        adapter.estimate_input_tokens([Message("user", "task")], [unsupported])


@pytest.mark.parametrize("provider", PROVIDERS)
async def test_unsupported_contract_rejected_before_touching_transport(provider):
    adapter = make_adapter(provider)
    original = adapter._client

    class ForbiddenTransport:
        def __getattr__(self, _name):
            raise AssertionError("Unsupported schema reached SDK transport")

    adapter._client = ForbiddenTransport()
    try:
        declaration = ToolDeclaration("inspect", "Inspect", {"type": "object", "unevaluatedProperties": False})
        with pytest.raises(SchemaProjectionError):
            async for _chunk in adapter.chat_completion_stream([Message("user", "task")], [declaration]):
                pass
    finally:
        await original.close()
