"""Configured leaders send their own model and prompt through real adapters."""

import copy
from typing import Any

import pytest
from tests.e2e.provider_transport import ScriptedCall, bind_scripted_transport

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.events import EventType
from henchman.providers.anthropic import AnthropicProvider
from henchman.providers.factory import create_configured_provider
from henchman.providers.ollama import OllamaProvider
from henchman.providers.openai_compat import OpenAICompatibleProvider
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.registry import ToolRegistry


@pytest.mark.parametrize("name", ["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"])
@pytest.mark.parametrize("explicit_provider", [True, False], ids=["saved-provider", "live-model-only"])
async def test_actual_leader_request_honors_role_configuration(
    name: str, explicit_provider: bool,
) -> None:
    options: dict[str, Any] = {"model": "default-model", "max_tokens": 1024}
    if name != "ollama":
        options["api_key"] = "offline-test-key"
    if name != "anthropic":
        options.update(base_url="https://offline.invalid/v1", temperature=0.25)
    else:
        options["tokens_per_minute"] = 1000000
    providers = ProviderSettings(**{name: options})
    default = OllamaProvider(model="unrelated-default") if explicit_provider else (
        create_configured_provider(providers, provider_name=name)
    )
    role: dict[str, Any] = {
        "model": "configured-leader-model", "system_prompt": "Configured leader instruction.",
        "tools": ["read_file"],
    }
    if explicit_provider:
        role["provider"] = name
    # This is the documented partial settings shape, not a prebuilt role object.
    settings = Settings.model_validate({
        "providers": providers if explicit_provider else ProviderSettings(),
        "agents": {"agents": {"tech_lead": role}},
    })
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    orch = Orchestrator(default, settings=settings, tool_registry=registry)
    leader = orch.tech_lead
    provider = leader.provider
    assert isinstance(provider, AnthropicProvider | OpenAICompatibleProvider)
    assert isinstance(default, AnthropicProvider | OpenAICompatibleProvider)
    requests: list[dict[str, Any]] = []

    def respond(**kwargs: Any) -> ScriptedCall:
        requests.append(copy.deepcopy(kwargs))
        assert len(requests) == 1, "Unexpected extra leader request"
        return None

    await bind_scripted_transport(provider, respond)
    try:
        events = [event async for event in orch.run("Describe the current status.")]
    finally:
        await orch.aclose()
        await provider._client.close()
        await default._client.close()

    assert not any(event.type == EventType.ERROR for event in events), events
    assert any(event.type == EventType.CONTENT for event in events)
    assert len(requests) == 1
    snapshot = orch.last_budget_scope.ledger.snapshot()
    assert snapshot.consumed_requests == 1
    assert snapshot.unknown_dispatched_requests == 0
    request = requests[0]
    assert request["model"] == "configured-leader-model"
    assert request["max_tokens"] == 1024
    assert request["messages"][-1]["content"] == "Describe the current status."
    if isinstance(provider, AnthropicProvider):
        system_prompt = request["system"]
        assert [tool["name"] for tool in request["tools"]] == ["read_file"]
    else:
        assert request["messages"][0]["role"] == "system"
        system_prompt = request["messages"][0]["content"]
        assert request["temperature"] == 0.25
        assert [tool["function"]["name"] for tool in request["tools"]] == ["read_file"]
        assert provider.base_url == "https://offline.invalid/v1"
    assert system_prompt.startswith("Configured leader instruction.\n\n")
    assert "Delegation is disabled." in system_prompt
    assert not orch.delegation_runner.admission.allowed
    assert orch.pool.get_agent("tech_lead") is leader
    assert provider is not default
    assert orch.default_provider is orch.pool.default_provider is default
    assert default.default_model == ("unrelated-default" if explicit_provider else "default-model")
