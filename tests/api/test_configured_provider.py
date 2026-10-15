"""API startup honors the same provider settings as interactive clients."""

import pytest

from henchman.api import server
from henchman.api.state import State
from henchman.config.schema import ProviderSettings, Settings


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_name", ["openrouter", "openai_compat", "ollama"])
async def test_lifespan_uses_selected_provider_settings(
    monkeypatch: pytest.MonkeyPatch, provider_name: str,
) -> None:
    monkeypatch.setenv("HENCHMAN_API_KEY", "generic-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    providers = ProviderSettings(default=provider_name)
    setattr(providers, provider_name, {"model": "test-model", "base_url": "http://localhost:12345/v1"})
    monkeypatch.setattr(server, "load_settings", lambda: Settings(providers=providers))
    state = State()
    monkeypatch.setattr(server, "state", state)
    async with server.lifespan(server.app):
        assert state.agent is not None
        assert state.agent.provider.default_model == "test-model"
        assert state.agent.provider.base_url == "http://localhost:12345/v1"
        if provider_name != "ollama":
            assert state.agent.provider.api_key == "generic-key"
