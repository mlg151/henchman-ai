"""Real adapters route a named check to a specialist without expanding scope."""

import copy
import json
from unittest.mock import AsyncMock

import pytest
from tests.e2e.test_coding_loop import anthropic_response, compatible_response

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import AgentConfig, ProviderSettings, Settings
from henchman.core.events import EventType
from henchman.providers.factory import create_configured_provider
from henchman.tools.builtins.pytest_run import PytestRunTool
from henchman.tools.builtins.tier1_tools import ToolSearchTool
from henchman.tools.registry import ToolRegistry


def tool_result_text(request, call_id):
    """Read a correlated tool result in compatible or native request format."""
    for message in reversed(request["messages"]):
        if message.get("role") == "tool" and message.get("tool_call_id") == call_id:
            return message["content"]
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_result" and block.get("tool_use_id") == call_id:
                    return json.dumps(block["content"])
    raise AssertionError(f"Missing result for {call_id}")


@pytest.mark.parametrize(
    "provider_name", ["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"]
)
@pytest.mark.parametrize("passing", [True, False], ids=["passing-check", "failing-check"])
async def test_team_discovery_routes_exact_check_and_preserves_observed_result(
    tmp_path,
    monkeypatch,
    provider_name,
    passing,
):
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.chdir(tmp_path)
    tests = tmp_path / "test_total.py"
    tests.write_text(
        "def test_positive():\n    assert 2 + 3 == " + ("5" if passing else "99") + "\n"
        "\ndef test_negative():\n    assert -4 + 2 == -2\n",
        encoding="utf-8",
    )
    script = [
        ("local", "tool_search", {"query": "pytest_run"}),
        ("team", "tool_search", {"scope": "team", "query": "pytest_run"}),
        (
            "delegate-check",
            "delegate_task",
            {
                "agent": "engineer",
                "task": "Run the required test check.",
                "files": [str(tests)],
                "done_when": "pytest_run executes all tests in test_total.py and passes.",
                "requirements": "Use the named pytest_run tool and report its observed result.",
            },
        ),
        ("required-check", "pytest_run", {"path": str(tests), "timeout": 20}),
        None,
        None,
    ]
    saved = {"model": "coding-test", "max_tokens": 1024}
    if provider_name != "ollama":
        saved["api_key"] = "offline-test"
    if provider_name == "openai_compat":
        saved["base_url"] = "https://offline.invalid/v1"
    if provider_name == "anthropic":
        saved["tokens_per_minute"] = 1_000_000_000
    providers = ProviderSettings(default=provider_name, **{provider_name: saved})
    provider = create_configured_provider(providers)
    requests = []

    def respond(**kwargs):
        requests.append(copy.deepcopy(kwargs))
        index = len(requests) - 1
        assert index < len(script), "Unexpected model request"
        if index == 2:
            result = tool_result_text(kwargs, "team")
            assert "engineer" in result and "pytest_run" in result
        if index == 3:
            assert "named pytest_run tool" in json.dumps(kwargs["messages"][-1])
        call = script[index]
        return (
            anthropic_response(call) if provider_name == "anthropic" else compatible_response(call)
        )

    if provider_name == "anthropic":
        monkeypatch.setattr(provider._client.messages, "stream", respond)
    else:
        monkeypatch.setattr(
            provider._client.chat.completions, "create", AsyncMock(side_effect=respond)
        )
    registry = ToolRegistry()
    search = ToolSearchTool()
    search.bind_runtime(tool_registry=registry)
    registry.register(search)
    registry.register(PytestRunTool())
    registry.add_auto_approve_policy("delegate_task")
    registry.add_auto_approve_policy("pytest_run")
    settings = Settings(providers=providers, context={"max_tokens": 32768})
    settings.agents.max_delegation_retries = 0
    # Team discovery is needed when a user explicitly excludes the required local tool.
    settings.agents.agents["tech_lead"] = AgentConfig(
        name="Restricted primary",
        role="tech_lead",
        description="Discover and delegate verification outside its own scope",
        tools=["tool_search", "delegate_task"],
    )
    orch = Orchestrator(default_provider=provider, tool_registry=registry, settings=settings)
    try:
        events = [event async for event in orch.run("Use pytest_run to verify test_total.py.")]
    finally:
        await provider._client.close()

    results = {
        event.data["tool_call_id"]: event
        for event in events
        if event.type == EventType.TOOL_CALL_RESULT
    }
    assert not results["local"].data["success"]
    assert results["team"].data["success"]
    assert len(requests) == len(script)
    observed = results["required-check"]
    assert observed.source_agent == "engineer"
    assert observed.data["success"] is passing
    assert ("2 passed" if passing else "1 failed") in observed.data["result"]
    assert results["delegate-check"].data["success"] is passing
    assert orch.tech_lead.tool_registry.get("pytest_run") is None
    assert orch.tech_lead.tool_registry.discovered_tools == []
    for request in requests[:3] + requests[-1:]:
        names = [
            tool.get("name", tool.get("function", {}).get("name")) for tool in request["tools"]
        ]
        assert "pytest_run" not in names
    assert orch.pool.get_agent("engineer").tool_registry.get("pytest_run") is registry.get(
        "pytest_run"
    )
