"""Run accounting settings preserve zero, exact money, and provider isolation."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from pydantic import ValidationError

from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.schema import Settings
from henchman.config.settings import load_settings_snapshot, save_settings
from henchman.providers.factory import create_configured_provider
from henchman.providers.openai_compat import OpenAICompatibleProvider


@pytest.fixture(autouse=True)
def isolate_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    for name in ("HENCHMAN_PROVIDER", "HENCHMAN_MODEL", "HENCHMAN_SETTINGS_PATH"):
        monkeypatch.delenv(name, raising=False)


def price_entry(**overrides: object) -> dict[str, object]:
    return {
        "provider": "ollama", "model": "local.model:v1", "input_per_1k": "0",
        "output_per_1k": "0.12345678901234567890123456789", "cache_read_per_1k": "0",
        "cache_write_per_1k": None, "currency": "USD", "source": "configured local price",
        "as_of": "2026-11-07", **overrides,
    }


def test_default_usage_is_unlimited_and_unknown_pricing() -> None:
    from henchman.config.usage import model_pricing, run_budget_limits

    settings = Settings()
    limits = run_budget_limits(settings)
    assert limits.max_requests is None and limits.max_tokens is None
    assert limits.max_seconds is None and limits.max_cost is None
    assert limits.currency == "USD"
    assert settings.usage.prices == []
    assert model_pricing(settings, provider="ollama", model="local") is None


def test_explicit_zero_limits_and_decimal_amounts_are_preserved() -> None:
    from henchman.config.usage import run_budget_limits

    settings = Settings.model_validate({"usage": {"limits": {
        "max_requests": 0, "max_tokens": 0, "max_seconds": 0, "max_cost": "0", "currency": "EUR",
    }}})
    limits = run_budget_limits(settings)
    assert (limits.max_requests, limits.max_tokens, limits.max_seconds, limits.max_cost) == (0, 0, 0, Decimal(0))
    assert limits.currency == "EUR"
    assert isinstance(settings.usage.limits.max_cost, Decimal)
    assert settings.model_dump()["usage"]["limits"]["max_cost"] == "0"
    assert Settings.model_validate(settings.model_dump()) == settings


@pytest.mark.parametrize("field,value", [
    ("max_requests", -1), ("max_requests", True), ("max_requests", 1.5),
    ("max_tokens", False), ("max_tokens", "2"),
    ("max_seconds", True), ("max_seconds", -1), ("max_seconds", float("inf")),
    ("max_seconds", float("nan")), ("max_cost", True), ("max_cost", "-0.1"),
    ("max_cost", "NaN"), ("max_cost", "Infinity"), ("currency", "usd"),
    ("currency", "US"), ("currency", "USD\n"), ("max_request", 1),
])
def test_invalid_budget_limits_report_the_typed_field(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as failure:
        Settings.model_validate({"usage": {"limits": {field: value}}})
    assert failure.value.errors()[0]["loc"] == ("usage", "limits", field)


@pytest.mark.parametrize("field,value", [
    ("provider", ""), ("provider", " ollama"), ("model", " "),
    ("input_per_1k", True), ("output_per_1k", "-0.01"), ("cache_read_per_1k", "NaN"),
    ("cache_write_per_1k", "Infinity"), ("currency", "usd"),
    ("source", " "), ("as_of", "2026-02-30"), ("output_price", 1),
])
def test_invalid_price_entries_report_the_typed_field(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as failure:
        Settings.model_validate({"usage": {"prices": [price_entry(**{field: value})]}})
    assert failure.value.errors()[0]["loc"] == ("usage", "prices", 0, field)


def test_duplicate_catalog_identity_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Duplicate"):
        Settings.model_validate({"usage": {"prices": [price_entry(), price_entry(output_per_1k="0")]}})


def test_model_pricing_uses_exact_provider_and_model_without_fallback() -> None:
    from henchman.config.usage import model_pricing

    settings = Settings.model_validate({"usage": {"prices": [
        price_entry(), price_entry(provider="openai_compat", output_per_1k="3"),
    ]}})
    pricing = model_pricing(settings, provider="ollama", model="local.model:v1")
    assert pricing is not None
    assert pricing.input_per_1k == Decimal(0)
    assert pricing.output_per_1k == Decimal("0.12345678901234567890123456789")
    assert pricing.cache_read_per_1k == Decimal(0)
    assert pricing.cache_write_per_1k is None
    assert pricing.currency == "USD" and pricing.source == "configured local price"
    assert pricing.as_of == "2026-11-07"
    assert settings.usage.prices[0].as_of == date(2026, 11, 7)
    assert model_pricing(settings, provider="ollama", model="local.model:v2") is None
    assert model_pricing(settings, provider="openai", model="local.model:v1") is None
    assert model_pricing(settings, provider="OLLAMA", model="local.model:v1") is None
    settings.usage.prices[0].output_per_1k = Decimal(9)
    assert pricing.output_per_1k == Decimal("0.12345678901234567890123456789")


def test_snapshot_inspection_and_canonical_writes_round_trip_exact_money(tmp_path: Path) -> None:
    amount = "0.12345678901234567890123456789"
    settings_dir = tmp_path / "project" / ".henchman"
    settings_dir.mkdir(parents=True)
    path = settings_dir / "settings.yaml"
    payload = {"usage": {"limits": {"max_tokens": 0, "max_cost": amount}, "prices": [price_entry()]}}
    path.write_text(yaml.safe_dump(payload))
    snapshot = load_settings_snapshot(project_root=settings_dir.parent)
    assert snapshot.settings.usage.limits.max_cost == Decimal(amount)
    assert snapshot.settings.usage.limits.max_tokens == 0
    assert snapshot.origins["usage.limits.max_cost"].scope == "project"
    assert snapshot.origins["usage.prices"].scope == "project"

    repository = SettingsRepository(project_root=settings_dir.parent)
    inspection = repository.inspect(include_groups=True)
    assert inspection["usage.limits.max_cost"].value == amount
    assert inspection["usage.prices"].value[0]["output_per_1k"] == amount
    json.dumps(repository.view())
    yaml.safe_dump(repository.view())
    repository.set("usage.limits.max_cost", Decimal("0.00000000000000000000000000001"), scope=SettingsScope.PROJECT)
    assert yaml.safe_load(path.read_text())["usage"]["limits"]["max_cost"] == "1E-29"
    restored = load_settings_snapshot(project_root=settings_dir.parent)
    assert restored.settings.usage.limits.max_cost == Decimal("1E-29")
    assert restored.settings.usage.limits.max_tokens == 0
    assert restored.settings.usage.prices[0].output_per_1k == Decimal(amount)
    assert not (settings_dir.parent / ".hENCHMAN").exists()


def test_save_settings_serializes_decimal_and_date_without_precision_loss(tmp_path: Path) -> None:
    settings = Settings.model_validate({"usage": {"limits": {"max_cost": "1E-29"}, "prices": [price_entry()]}})
    for suffix in ("yaml", "json"):
        path = tmp_path / f"settings.{suffix}"
        save_settings(settings, path)
        raw = yaml.safe_load(path.read_text()) if suffix == "yaml" else json.loads(path.read_text())
        assert raw["usage"]["limits"]["max_cost"] == "1E-29"
        assert raw["usage"]["prices"][0]["as_of"] == "2026-11-07"
        assert Settings.model_validate(raw) == settings


def test_accounting_settings_never_reach_provider_factory_kwargs() -> None:
    settings = Settings.model_validate({
        "providers": {"default": "openai_compat", "openai_compat": {
            "base_url": "http://localhost:1234/v1", "model": "local.model:v1", "api_key": "test-only",
        }},
        "usage": {"limits": {"max_requests": 0, "max_cost": "0"}, "prices": [price_entry(provider="openai_compat")]},
    })
    registry = MagicMock()
    registry.get.return_value = OpenAICompatibleProvider

    create_configured_provider(settings.providers, registry=registry)

    registry.create.assert_called_once_with(
        "openai_compat", base_url="http://localhost:1234/v1", default_model="local.model:v1", api_key="test-only",
    )
