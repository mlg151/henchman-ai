"""Real adapters discover a test tool, repair Python and verify at 8K context."""

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from tests.e2e.test_coding_loop import anthropic_response, compatible_response

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.tool_manager import ToolManager
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.events import EventType
from henchman.providers.factory import create_configured_provider
from henchman.providers.request_budget import estimate_serialized_input


@pytest.mark.parametrize("provider_name", ["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"])
async def test_engineer_discovers_verification_tool_and_recovers_at_8k(
    tmp_path, monkeypatch, provider_name,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    source = tmp_path / "arithmetic.py"
    source.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    tests = tmp_path / "test_arithmetic.py"
    tests.write_text("from arithmetic import add\n\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")
    script = [
        ("discover", "tool_search", {"query": "pytest_run"}),
        ("inspect", "read_file", {"path": str(source)}),
        ("before", "pytest_run", {"path": str(tests), "timeout": 20}),
        ("fix", "edit_file", {"path": str(source), "old_str": "return a - b", "new_str": "return a + b"}),
        ("after", "pytest_run", {"path": str(tests), "timeout": 20}),
        None,
    ]
    saved = {"api_key": "offline-test", "model": "coding-test", "max_tokens": 1024}
    if provider_name == "anthropic":
        saved["tokens_per_minute"] = 1_000_000_000
    if provider_name == "openai_compat":
        saved["base_url"] = "https://offline.invalid/v1"
    if provider_name == "ollama":
        saved.pop("api_key")
    providers = ProviderSettings(default=provider_name, **{provider_name: saved})
    provider = create_configured_provider(providers)
    requests = []

    def next_response(**kwargs):
        requests.append(deepcopy(kwargs))
        assert len(requests) <= len(script)
        call = script[len(requests) - 1]
        names = {
            tool["name"] if provider_name == "anthropic" else tool["function"]["name"]
            for tool in kwargs["tools"]
        }
        if call:
            assert call[1] in names, f"Model call {call[1]} lacked a declared schema"
        payload = {key: kwargs[key] for key in ("messages", "tools", "system") if key in kwargs}
        assert kwargs["max_tokens"] == 1024
        assert estimate_serialized_input(payload, model="coding-test") + 1024 <= 8000
        return anthropic_response(call) if provider_name == "anthropic" else compatible_response(call)

    if provider_name == "anthropic":
        monkeypatch.setattr(provider._client.messages, "stream", next_response)
    else:
        monkeypatch.setattr(provider._client.chat.completions, "create", AsyncMock(side_effect=next_response))
    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()
    confirmations = []

    async def approve(request):
        confirmations.append(request.tool_name)
        return True

    manager.registry.set_confirmation_handler(approve)
    orch = Orchestrator(default_provider=provider, tool_registry=manager.registry,
                        settings=Settings(providers=providers))
    try:
        events = [event async for event in orch.run_direct("engineer", "Fix addition; inspect and test before and after.")]
    finally:
        await provider._client.close()
    errors = [event.data for event in events if event.type == EventType.ERROR]
    assert not errors, errors
    assert len(requests) == len(script)
    first_names = {
        tool["name"] if provider_name == "anthropic" else tool["function"]["name"]
        for tool in requests[0]["tools"]
    }
    second_names = {
        tool["name"] if provider_name == "anthropic" else tool["function"]["name"]
        for tool in requests[1]["tools"]
    }
    assert "pytest_run" not in first_names
    assert "pytest_run" in second_names
    assert source.read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"
    results = [event.data for event in events if event.type == EventType.TOOL_CALL_RESULT]
    assert [result["success"] for result in results] == [True, True, False, True, True]
    assert "1 failed" in results[2]["result"]
    assert "1 passed" in results[4]["result"]
    assert confirmations == ["pytest_run", "edit_file", "pytest_run"]
    assert events[-1].data["status"] == "completed"
