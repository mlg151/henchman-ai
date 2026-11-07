from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import henchman.config as config_module
import henchman.providers.factory
from henchman.cli.textual_mixins import _ProviderMixin
from henchman.config.schema import ProviderSettings, Settings
from henchman.config.settings import ConfigError, SettingOrigin, SettingsSnapshot


def test_direct_tui_loads_one_settings_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    load_count = 0
    first_settings = Settings(providers=ProviderSettings(deepseek={"model": "first-model"}))
    later_settings = Settings(providers=ProviderSettings(deepseek={"model": "later-model"}))

    def mock_load_settings() -> SettingsSnapshot:
        nonlocal load_count
        load_count += 1
        return SettingsSnapshot(
            first_settings if load_count == 1 else later_settings,
            {"providers.deepseek.model": SettingOrigin("project", "startup/settings.yaml")},
        )

    fake_provider = SimpleNamespace(name="deepseek", model="first-model")
    captured_provider_settings: ProviderSettings | None = None

    def mock_create_configured_provider(
        provider_settings: ProviderSettings, **_kwargs: object
    ) -> SimpleNamespace:
        nonlocal captured_provider_settings
        captured_provider_settings = provider_settings
        return fake_provider

    monkeypatch.setattr(config_module, "load_settings_snapshot", mock_load_settings)
    monkeypatch.setattr(
        henchman.providers.factory, "create_configured_provider", mock_create_configured_provider
    )

    monkeypatch.setattr(_ProviderMixin, "_create_config_safe", staticmethod(lambda: object()))
    monkeypatch.setattr(_ProviderMixin, "_gather_env_safe", staticmethod(lambda: "env"))

    runtime = _ProviderMixin()
    runtime._resolve_provider_from_env()

    assert load_count == 1, f"Expected 1 load, got {load_count}"
    assert runtime.settings is first_settings
    assert captured_provider_settings is first_settings.providers
    assert runtime.provider is fake_provider
    assert runtime.settings_state.snapshot().origins["providers.deepseek.model"].scope == "project"


def test_resolve_provider_from_env_raises_config_error_on_invalid_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = Mock()
    factory = Mock()

    monkeypatch.setattr(config_module, "load_settings_snapshot", loader)
    monkeypatch.setattr(henchman.providers.factory, "create_configured_provider", factory)

    loader.side_effect = ConfigError("invalid test settings")

    monkeypatch.setattr(_ProviderMixin, "_create_config_safe", staticmethod(lambda: object()))
    monkeypatch.setattr(_ProviderMixin, "_gather_env_safe", staticmethod(lambda: "env"))

    with pytest.raises(ConfigError, match="invalid test settings"):
        _ProviderMixin()._resolve_provider_from_env()

    loader.assert_called_once_with()
    factory.assert_not_called()
