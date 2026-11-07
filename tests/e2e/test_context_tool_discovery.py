"""Real adapters discover a test tool, repair Python and verify at 8K context."""

import json
import socket
from importlib import import_module
from typing import Any, NoReturn

import pytest
from tests.e2e.test_coding_loop import anthropic_response, compatible_response

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.tool_manager import ToolManager
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.events import EventType
from henchman.providers.factory import create_configured_provider
from henchman.providers.request_budget import estimate_serialized_input


async def _stream_body(call: tuple[str, str, dict[str, Any]] | None, *, native: bool) -> bytes:
    """Encode fixture events for the real SDK's HTTP stream parser."""
    if native:
        events = [{
            "type": "message_start", "message": {
                "id": "message-1", "type": "message", "role": "assistant",
                "model": "coding-test", "content": [], "stop_reason": None,
                "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 0},
            },
        }]
        async with anthropic_response(call) as chunks:
            events.extend([chunk.model_dump() async for chunk in chunks])
        return "".join(
            f"event: {event['type']}\ndata: {json.dumps(event)}\n\n" for event in events
        ).encode()
    response = compatible_response(call)
    try:
        chunks = [chunk.model_dump() async for chunk in response]
    finally:
        await response.close()
    chunks.append({
        "id": "completion", "object": "chat.completion.chunk", "created": 1,
        "model": "coding-test", "choices": [],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    })
    return ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks)
            + "data: [DONE]\n\n").encode()


@pytest.mark.parametrize("provider_name", ["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"])
async def test_engineer_discovers_verification_tool_and_recovers_at_8k(
    tmp_path, monkeypatch, provider_name,
):
    network_attempts = []

    def forbid_network(*_args: object, **_kwargs: object) -> NoReturn:
        network_attempts.append(True)
        raise AssertionError("Offline model fixture attempted real network I/O")

    monkeypatch.setattr(socket, "getaddrinfo", forbid_network)
    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbid_network)
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

    # Match the installed SDK's HTTP family (fresh Anthropic versions use httpx2).
    http_name = next(
        cls.__module__.partition(".")[0] for cls in type(provider._client._client).__mro__
        if cls.__module__.partition(".")[0] in {"httpx", "httpx2"}
    )
    http = import_module(http_name)

    async def next_response(request: Any) -> Any:
        assert request.url.host == "offline.invalid"
        kwargs = json.loads(request.content)
        requests.append(kwargs)
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
        return http.Response(
            200, content=await _stream_body(call, native=provider_name == "anthropic"),
            headers={"content-type": "text/event-stream"},
        )

    # SDK with_options copies retain this transport, unlike resource-method mocks.
    client_class = type(provider._client)
    await provider._client.close()
    provider._client = client_class(
        api_key="offline-test", base_url="https://offline.invalid/v1",
        http_client=http.AsyncClient(transport=http.MockTransport(next_response)),
    )
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
        await orch.aclose()
        await provider._client.close()
    errors = [event.data for event in events if event.type == EventType.ERROR]
    assert not errors, errors
    assert len(requests) == len(script)
    snapshot = orch.last_budget_scope.ledger.snapshot()
    assert snapshot.consumed_requests == len(script)
    assert snapshot.unknown_dispatched_requests == 0
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
    # The repeated identical pytest run reuses the first approval grant.
    assert confirmations == ["pytest_run", "edit_file"]
    assert events[-1].data["status"] == "completed"
    assert not network_attempts
