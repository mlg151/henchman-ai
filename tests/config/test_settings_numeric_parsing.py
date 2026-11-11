"""Accepted text money must reach accounting without an intermediate float."""

from decimal import Decimal, Inexact, localcontext
from pathlib import Path

import pytest

from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.settings import load_settings_snapshot
from henchman.config.usage import model_pricing, run_budget_limits
from henchman.core.run_budget import BudgetExceeded, RequestEstimate, RunBudgetLedger

AMOUNT = "0.099999999999999999999999999999"
RATE = "1.0e-1000"


def document(suffix: str) -> str:
    if suffix == "json":
        return (
            '{"usage":{"limits":{"max_cost":' + AMOUNT + '},"prices":[{'
            '"provider":"ollama","model":"fixture","input_per_1k":' + RATE + ","
            '"output_per_1k":0,"cache_read_per_1k":' + AMOUNT + ","
            '"cache_write_per_1k":' + RATE + "}]},"
            '"context":{"compaction_threshold":0.75},'
            '"providers":{"ollama":{"temperature":0.125,"custom":{"rate":1.0e-1000}}}}'
        )
    return f"""usage:
  limits:
    max_cost: {AMOUNT}
  prices:
    - provider: ollama
      model: fixture
      input_per_1k: {RATE}
      output_per_1k: 0
      cache_read_per_1k: {AMOUNT}
      cache_write_per_1k: {RATE}
context:
  compaction_threshold: 0.75
providers:
  ollama:
    temperature: 0.125
    custom:
      rate: 1.0e-1000
"""


@pytest.mark.parametrize("suffix", ["yaml", "yml", "json"])
def test_startup_scoped_reads_and_canonical_roundtrip_keep_money_exact(tmp_path: Path, suffix: str):
    project = tmp_path / "project"
    directory = project / ".henchman"
    directory.mkdir(parents=True)
    (directory / f"settings.{suffix}").write_text(document(suffix))
    repository = SettingsRepository(project)
    with localcontext() as context:
        context.prec = 4
        context.traps[Inexact] = True
        state = load_settings_snapshot(project)
        raw = repository.view(scope=SettingsScope.PROJECT)
        assert Decimal(raw["usage"]["limits"]["max_cost"]) == Decimal(AMOUNT)
        assert state.settings.usage.limits.max_cost == Decimal(AMOUNT)
        price = state.settings.usage.prices[0]
        assert price.input_per_1k == price.cache_write_per_1k == Decimal(RATE)
        assert price.output_per_1k == Decimal(0)
        assert price.cache_read_per_1k == Decimal(AMOUNT)
        assert state.origins["usage.limits.max_cost"].scope == "project"
        assert type(raw["context"]["compaction_threshold"]) is float
        assert type(raw["providers"]["ollama"]["temperature"]) is float
        assert raw["providers"]["ollama"]["custom"]["rate"] == 0.0
        repository.set("ui.theme", "light", scope=SettingsScope.PROJECT)
        restored = load_settings_snapshot(project)
        assert restored.settings.usage == state.settings.usage


def test_positive_underflow_rate_cannot_authorize_a_free_request(tmp_path: Path):
    directory = tmp_path / ".henchman"
    directory.mkdir()
    (directory / "settings.yaml").write_text(document("yaml").replace(AMOUNT, "0"))
    settings = load_settings_snapshot(tmp_path).settings
    ledger = RunBudgetLedger(limits=run_budget_limits(settings))
    price = model_pricing(settings, provider="ollama", model="fixture")
    with pytest.raises(BudgetExceeded):
        ledger.reserve(RequestEstimate(1000, 1, pricing=price, cache_mode="none"))
    assert ledger.snapshot().consumed_requests == 0
    assert ledger.snapshot().records == ()


def test_yaml_aliases_are_normalized_for_each_schema_path(tmp_path: Path):
    directory = tmp_path / ".henchman"
    directory.mkdir()
    (directory / "settings.yaml").write_text(
        f"providers:\n  ollama:\n    temperature: &number {AMOUNT}\n"
        "usage:\n  limits:\n    max_cost: *number\n"
    )
    values = SettingsRepository(tmp_path).view(scope=SettingsScope.PROJECT)
    assert type(values["providers"]["ollama"]["temperature"]) is float
    assert Decimal(values["usage"]["limits"]["max_cost"]) == Decimal(AMOUNT)


@pytest.mark.parametrize(
    "token,expected",
    [
        ("1_000.000_000_000_000_000_001", "1000.000000000000000001"),
        ("1:20.000000000000000001", "80.000000000000000001"),
        ("+.125", "0.125"),
        ("-0.0", "-0.0"),
        ("1.0e+1000", "1.0e+1000"),
    ],
)
def test_existing_yaml_numeric_syntax_keeps_exact_money(tmp_path: Path, token: str, expected: str):
    directory = tmp_path / ".henchman"
    directory.mkdir()
    (directory / "settings.yaml").write_text(f"usage:\n  limits:\n    max_cost: {token}\n")
    assert load_settings_snapshot(tmp_path).settings.usage.limits.max_cost == Decimal(expected)


def test_alias_price_list_preserves_ordinary_provider_numeric_types():
    from henchman.config.parsing import parse_settings_text

    values = parse_settings_text(
        "providers:\n  ollama:\n    custom: &rates\n      - input_per_1k: 1.0e-1000\n"
        "usage:\n  prices: *rates\n",
        format="yaml",
    )
    assert type(values["providers"]["ollama"]["custom"][0]["input_per_1k"]) is float
    assert values["usage"]["prices"][0]["input_per_1k"] == "1.0e-1000"


def test_safe_yaml_structures_do_not_leak_numeric_parser_objects():
    import yaml

    from henchman.config.parsing import parse_settings_text

    text = "providers:\n  ollama:\n    values: !!set {1.5: null}\n    order: !!omap [{k: 0.25}]\n"
    parsed = parse_settings_text(text, format="yaml")
    assert parsed == yaml.safe_load(text)
    assert yaml.safe_load(yaml.safe_dump(parsed)) == yaml.safe_load(
        yaml.safe_dump(yaml.safe_load(text))
    )
