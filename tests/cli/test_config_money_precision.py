"""Actual six-verb commands preserve accepted decimal control values."""

from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_command import create_config_command
from henchman.config.repository import SettingsRepository, SettingsScope
from tests.config.test_settings_numeric_parsing import AMOUNT, RATE, document


@pytest.mark.parametrize(
    "key,value",
    [
        ("usage.limits.max_cost", AMOUNT),
        (" usage.limits.max_cost", AMOUNT),
        ("usage . limits . max_cost", AMOUNT),
        ("usage.limits.max_cost ", AMOUNT),
        ("usage.limits", '{"max_cost":' + AMOUNT + "}"),
        ("usage", '{"limits":{"max_cost":' + AMOUNT + "}}"),
    ],
)
def test_set_view_get_unset_exact_cap_and_lower_scope(tmp_path: Path, key: str, value: str):
    repository = SettingsRepository(tmp_path)
    repository.set("usage.limits.max_cost", "1", scope=SettingsScope.GLOBAL)
    runner, command = CliRunner(), create_config_command(project_root=tmp_path)
    result = runner.invoke(command, ["set", key, value, "--scope", "project"])
    assert result.exit_code == 0, result.output
    for verb in ("get", "view"):
        result = runner.invoke(command, [verb, "usage.limits.max_cost"])
        assert result.exit_code == 0, result.output
        payload = yaml.safe_load(result.output)
        assert Decimal(payload["value"]) == Decimal(AMOUNT)
        assert payload["resolved_scope"] == "project"
    result = runner.invoke(command, ["unset", "usage.limits.max_cost", "--scope", "project"])
    assert result.exit_code == 0, result.output
    assert repository.get("usage.limits.max_cost") == "1"


@pytest.mark.parametrize("suffix", ["json", "yaml", "yml"])
def test_import_export_money_numbers_roundtrip_losslessly(tmp_path: Path, suffix: str):
    transfer = tmp_path / f"source.{suffix}"
    # Transfer deliberately excludes provider/context groups, whose existing
    # allowlist remains separate from numerical parsing.
    raw = document(suffix)
    raw = raw[: raw.index(',"context"')] + "}" if suffix == "json" else raw.split("context:", 1)[0]
    transfer.write_text(raw)
    command, runner = create_config_command(project_root=tmp_path), CliRunner()
    result = runner.invoke(
        command, ["import", str(transfer), "--scope", "project", "--accept-control-changes"]
    )
    assert result.exit_code == 0, result.output
    output = tmp_path / "export.json"
    result = runner.invoke(
        command, ["export", str(output), "--scope", "project", "--include-controls"]
    )
    assert result.exit_code == 0, result.output
    payload = yaml.safe_load(output.read_text())
    assert Decimal(payload["usage"]["limits"]["max_cost"]) == Decimal(AMOUNT)
    assert Decimal(payload["usage"]["prices"][0]["input_per_1k"]) == Decimal(RATE)


@pytest.mark.parametrize(
    "field", ["input_per_1k", "output_per_1k", "cache_read_per_1k", "cache_write_per_1k"]
)
@pytest.mark.parametrize("key", ["usage.prices", " usage . prices "])
def test_set_nested_price_preserves_positive_underflow(tmp_path: Path, field: str, key: str):
    value = '[{"provider":"ollama","model":"fixture","' + field + '":' + RATE + "}]"
    result = CliRunner().invoke(
        create_config_command(project_root=tmp_path),
        ["set", key, value, "--scope", "project"],
    )
    assert result.exit_code == 0, result.output
    assert Decimal(SettingsRepository(tmp_path).get("usage.prices")[0][field]) == Decimal(RATE)


@pytest.mark.parametrize("value", ["true", "-1.0e-1000", ".nan", ".inf"])
def test_invalid_money_is_rejected_atomically(tmp_path: Path, value: str):
    repository = SettingsRepository(tmp_path)
    repository.set("usage.limits.max_cost", "1", scope=SettingsScope.PROJECT)
    path = tmp_path / ".henchman" / "settings.yaml"
    before = path.read_bytes()
    result = CliRunner().invoke(
        create_config_command(project_root=tmp_path),
        ["set", "usage.limits.max_cost", value, "--scope", "project"],
    )
    assert result.exit_code != 0
    assert path.read_bytes() == before


def test_set_opaque_provider_options_retains_float_types_and_schema_path_boundary(tmp_path: Path):
    value = '{"temperature":0.125,"usage":{"limits":{"max_cost":0.099999999999999999999999999999}}}'
    result = CliRunner().invoke(
        create_config_command(project_root=tmp_path),
        ["set", "providers.ollama", value, "--scope", "project"],
    )
    assert result.exit_code == 0, result.output
    values = SettingsRepository(tmp_path).get("providers.ollama")
    assert type(values["temperature"]) is float
    assert values["usage"]["limits"]["max_cost"] == 0.1
