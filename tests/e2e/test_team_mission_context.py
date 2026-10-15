"""All provider transports receive requirements beyond the ledger preview."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock

import pytest
from tests.e2e.test_coding_loop import anthropic_response, compatible_response

from henchman.agents.orchestrator import Orchestrator
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.events import EventType
from henchman.providers.factory import create_configured_provider


@pytest.mark.parametrize(
    "provider_name", ["openrouter", "openai_compat", "deepseek", "ollama", "anthropic"]
)
async def test_specialist_sdk_request_preserves_full_mission_and_narrow_assignment(
    monkeypatch: pytest.MonkeyPatch, provider_name: str
) -> None:
    mission = (
        "Coordinate the library and CLI changes. "
        + "Keep compatibility with all supported Python versions. " * 15
        + "The CLI must work from another working directory; unsupported options exit 2. "
        "Run the named tests after the final edit and obtain independent review."
    )
    assignment = "Explain the existing normalizer; do not implement either file."
    done_when = "Return the helper symbol and reuse recommendation."
    script = [
        (
            "inspect-helper",
            "delegate_task",
            {
                "agent": "explorer",
                "task": assignment,
                "done_when": done_when,
                "completion_requirement": "response",
            },
        ),
        None,
        None,
    ]
    saved: dict[str, Any] = {"model": "coding-test", "max_tokens": 1024}
    if provider_name != "ollama":
        saved["api_key"] = "offline-test"
    if provider_name == "openai_compat":
        saved["base_url"] = "https://offline.invalid/v1"
    if provider_name == "anthropic":
        saved["tokens_per_minute"] = 1_000_000_000
    providers = ProviderSettings(default=provider_name, **{provider_name: saved})
    provider: Any = create_configured_provider(providers)
    requests: list[dict[str, Any]] = []
    compatible_stream: Callable[[Any], Any] = compatible_response

    def respond(**kwargs: Any) -> Any:
        requests.append(deepcopy(kwargs))
        assert len(requests) <= len(script), "Unexpected provider request"
        call = script[len(requests) - 1]
        return anthropic_response(call) if provider_name == "anthropic" else compatible_stream(call)

    if provider_name == "anthropic":
        monkeypatch.setattr(provider._client.messages, "stream", respond)
    else:
        monkeypatch.setattr(
            provider._client.chat.completions, "create", AsyncMock(side_effect=respond)
        )
    settings = Settings(providers=providers, context={"max_tokens": 32768})
    settings.agents.max_delegation_retries = 0
    orch = Orchestrator(default_provider=provider, settings=settings)
    try:
        events = [event async for event in orch.run(mission)]
    finally:
        await provider._client.close()

    assert len(requests) == 3
    texts: list[str] = []
    for message in requests[1]["messages"]:
        if message["role"] != "user":
            continue
        content = message["content"]
        if isinstance(content, str):
            texts.append(content)
        else:
            texts.extend(block["text"] for block in content if block.get("type") == "text")
    delegated_input = "\n".join(texts)
    assert f"## Mission\n{mission}" in delegated_input
    assert f"## Task\n{assignment}" in delegated_input
    assert f"## Done When\n{done_when}" in delegated_input
    assert orch.ledger is not None and orch.ledger.goal == mission
    result = next(
        event
        for event in events
        if event.type == EventType.TOOL_CALL_RESULT
        and event.data["tool_call_id"] == "inspect-helper"
    )
    assert result.data["success"]
