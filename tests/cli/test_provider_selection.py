"""Provider startup honors the selected configuration instead of key presence."""

from pathlib import Path
from unittest.mock import patch

import click
import pytest

from henchman.cli.app import _get_provider
from henchman.config.schema import ProviderSettings, Settings


def test_cli_respects_openrouter_selection_with_deepseek_key() -> None:
    settings = Settings(
        providers=ProviderSettings(
            default="openrouter", openrouter={"api_key": "router", "model": "vendor/coder"}
        )
    )
    with (
        patch("henchman.config.load_settings", return_value=settings),
        patch.dict("os.environ", {"DEEPSEEK_API_KEY": "deepseek"}, clear=True),
    ):
        provider = _get_provider()
    assert provider.name == "openrouter"
    assert provider.default_model == "vendor/coder"


def test_cli_invalid_selection_never_falls_back_to_deepseek() -> None:
    settings = Settings(providers=ProviderSettings(default="unknown"))
    with (
        patch("henchman.config.load_settings", return_value=settings),
        patch.dict("os.environ", {"DEEPSEEK_API_KEY": "deepseek"}, clear=True),
        pytest.raises(click.ClickException, match="not registered"),
    ):
        _get_provider()


def test_cli_settings_error_is_visible_even_with_credentials() -> None:
    with (
        patch(
            "henchman.config.load_settings", side_effect=ValueError("Invalid settings: providers")
        ),
        patch.dict("os.environ", {"DEEPSEEK_API_KEY": "deepseek"}, clear=True),
        pytest.raises(click.ClickException, match="Invalid settings"),
    ):
        _get_provider()


def test_environment_provider_and_model_overrides_use_real_settings_loader(tmp_path: Path) -> None:
    config = tmp_path / "settings.yaml"
    config.write_text(
        "providers:\n  default: deepseek\n  openrouter:\n    model: saved/model\n", encoding="utf-8"
    )
    with patch.dict(
        "os.environ",
        {
            "HENCHMAN_SETTINGS_PATH": str(config),
            "HENCHMAN_PROVIDER": "openrouter",
            "HENCHMAN_MODEL": "selected/model",
            "OPENROUTER_API_KEY": "router",
            "DEEPSEEK_API_KEY": "unrelated",
        },
        clear=True,
    ):
        provider = _get_provider()
    assert provider.name == "openrouter"
    assert provider.default_model == "selected/model"
    assert provider.api_key == "router"
