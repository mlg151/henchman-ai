"""Startup must configure provider and runtime from the same settings."""

from types import SimpleNamespace
from unittest.mock import Mock

import click
import pytest

import henchman.config as config_module
import henchman.config.environment
import henchman.providers.factory
from henchman.config.context import ContextLoader
from henchman.config.schema import ProviderSettings, Settings
from henchman.config.settings import ConfigError


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


def test_prepare_runtime_context_raises_on_invalid_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from henchman.cli.app import _prepare_runtime_context

    loader = Mock(side_effect=ConfigError("invalid test settings"))
    factory = Mock()

    monkeypatch.setattr(config_module, "load_settings", loader)
    monkeypatch.setattr(henchman.providers.factory, "create_configured_provider", factory)

    with pytest.raises(click.ClickException, match="Unable to configure provider: invalid test settings"):
        _prepare_runtime_context()

    loader.assert_called_once_with()
    factory.assert_not_called()
