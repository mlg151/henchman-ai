"""Startup must configure provider and runtime from the same settings."""

from types import SimpleNamespace

import pytest

import henchman.config as config_module
import henchman.config.environment
import henchman.providers.factory
from henchman.config.context import ContextLoader
from henchman.config.schema import ProviderSettings, Settings


def test_prepare_runtime_context_loads_settings_once(monkeypatch: pytest.MonkeyPatch) -> None:

    load_count = 0
    first_settings = Settings(providers=ProviderSettings(deepseek={"model": "first-model"}))
    later_settings = Settings(providers=ProviderSettings(deepseek={"model": "later-model"}))

    def mock_load_settings() -> Settings:
        nonlocal load_count
        load_count += 1
        return first_settings if load_count == 1 else later_settings

    fake_provider = SimpleNamespace(name="deepseek", model="first-model")
    captured_provider_settings: ProviderSettings | None = None

    def mock_create_configured_provider(
        provider_settings: ProviderSettings, **_kwargs: object
    ) -> SimpleNamespace:
        nonlocal captured_provider_settings
        captured_provider_settings = provider_settings
        return fake_provider

    monkeypatch.setattr(config_module, "load_settings", mock_load_settings)
    monkeypatch.setattr(
        henchman.providers.factory, "create_configured_provider", mock_create_configured_provider
    )

    monkeypatch.setattr(ContextLoader, "load", lambda _self: "prompt")

    monkeypatch.setattr(henchman.config.environment, "gather_environment", lambda: {})
    monkeypatch.setattr(henchman.config.environment, "format_environment_block", lambda _env: "env")

    from henchman.cli.app import _prepare_runtime_context

    ctx = _prepare_runtime_context()

    assert load_count == 1, f"Expected 1 load, got {load_count}"
    assert ctx.settings is first_settings
    assert captured_provider_settings is first_settings.providers
    assert ctx.provider is fake_provider
