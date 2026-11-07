"""Interactive session evidence uses runtime credentials without changing execution."""

from pathlib import Path
from unittest.mock import patch

import pytest

from henchman.cli.core_init import create_core_context
from henchman.cli.provider_switch import switch_runtime_provider
from henchman.cli.repl import Repl
from henchman.config.schema import ProviderSettings, Settings
from henchman.core.session import SessionMessage
from henchman.providers.ollama import OllamaProvider


@pytest.mark.parametrize("frontend", ["repl", "core"])
def test_configured_keys_and_provider_rotation_redact_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, frontend: str,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    original_key = "active-provider-key-canary"
    configured_key = "saved-provider-key-canary"
    rotated_key = "rotated-provider-key-canary"
    settings = Settings(providers=ProviderSettings(openrouter={"api_key": configured_key}))
    provider = OllamaProvider()
    provider.api_key = original_key
    with patch("henchman.cli.input.PromptSession"):
        runtime = Repl(provider=provider, settings=settings) if frontend == "repl" else (
            create_core_context(provider, settings=settings)
        )
    manager = runtime.session_manager.session_manager
    manager.data_dir = tmp_path / "sessions"
    session = manager.create_session("project")
    runtime.session_manager.set_session(session)
    replacement = OllamaProvider()
    replacement.api_key = rotated_key
    switch_runtime_provider(runtime, replacement)
    content = f"{original_key} {configured_key} {rotated_key}"
    session.messages.append(SessionMessage(role="user", content=content))
    path = manager.save(session)
    for secret in (original_key, configured_key, rotated_key):
        assert secret not in path.read_text()
    assert session.messages[-1].content == content
    assert runtime.provider.api_key == rotated_key
    assert settings.providers.openrouter["api_key"] == configured_key
