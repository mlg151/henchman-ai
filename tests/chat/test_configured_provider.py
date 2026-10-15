"""Chat integrations share configured provider construction."""

import pytest

from henchman.chat.manager import ChatManager
from henchman.config.schema import ProviderSettings, Settings


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["openrouter", "openai_compat", "ollama"])
async def test_chat_uses_selected_provider_settings(
    monkeypatch: pytest.MonkeyPatch, provider_name: str,
) -> None:
    monkeypatch.setenv("HENCHMAN_API_KEY", "generic-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = ProviderSettings(default=provider_name)
    setattr(providers, provider_name, {"model": "test-model", "base_url": "http://localhost:12345/v1"})
    # Tool discovery is independent of provider selection and can load optional integrations.
    monkeypatch.setattr("henchman.cli.tool_manager.ToolManager.register_builtin_tools", lambda _self: None)
    manager = ChatManager(Settings(providers=providers))
    agent = await manager._get_or_create_agent("test-user")
    assert agent.provider.default_model == "test-model"
    assert agent.provider.base_url == "http://localhost:12345/v1"
    if provider_name != "ollama":
        assert agent.provider.api_key == "generic-key"
    assert await manager._get_or_create_agent("test-user") is agent
