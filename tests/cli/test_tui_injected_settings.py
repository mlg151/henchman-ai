from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from henchman.cli.textual_mixins import _InitMixin, _ProviderMixin
from henchman.config.schema import ProviderSettings, Settings


class _Runtime(_InitMixin, _ProviderMixin):
    pass


@pytest.mark.parametrize(
    "has_provider, has_settings",
    [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ],
)
def test_tui_injected_settings(
    monkeypatch: pytest.MonkeyPatch,
    has_provider: bool,
    has_settings: bool,
) -> None:
    # Setup
    supplied = Settings(providers=ProviderSettings(deepseek={"model": "supplied"}))
    ambient = Settings(providers=ProviderSettings(deepseek={"model": "ambient"}))

    loader = Mock(return_value=ambient)
    configured = SimpleNamespace(name="deepseek")
    factory = Mock(return_value=configured)
    injected = SimpleNamespace(name="injected")

    # Monkeypatch actual config_module.load_settings
    monkeypatch.setattr("henchman.config.load_settings", loader)
    # Monkeypatch henchman.providers.factory.create_configured_provider
    monkeypatch.setattr("henchman.providers.factory.create_configured_provider", factory)

    # Stub only presentation _ProviderMixin._create_config_safe=staticmethod(lambda:object()), _gather_env_safe=staticmethod(lambda:"env")
    monkeypatch.setattr(_ProviderMixin, "_create_config_safe", staticmethod(lambda: object()))
    monkeypatch.setattr(_ProviderMixin, "_gather_env_safe", staticmethod(lambda: "env"))

    runtime = _Runtime()
    runtime._init_provider_and_settings(
        provider=injected if has_provider else None,
        config=SimpleNamespace(),
        settings=supplied if has_settings else None,
        env_ctx="env",
    )

    expected = supplied if has_settings else ambient
    assert runtime.settings is expected

    if has_settings:
        loader.assert_not_called()
    else:
        loader.assert_called_once_with()

    if has_provider:
        factory.assert_not_called()
        assert runtime.provider is injected
    else:
        factory.assert_called_once_with(expected.providers)
        assert runtime.provider is configured
