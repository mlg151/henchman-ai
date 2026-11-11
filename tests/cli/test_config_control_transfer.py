"""Explicit file transfer of operational controls through the actual Click surface."""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_command import create_config_command
from tests.config.test_settings_control_transfer import CONTROLS, write


@pytest.mark.parametrize("suffix", [".json", ".yaml", ".yml"])
def test_cli_control_export_import_roundtrip_requires_product_flags(
    tmp_path: Path, suffix: str
) -> None:
    source, destination = tmp_path / "source", tmp_path / "destination"
    write(source, {**CONTROLS, "ui": {"theme": "light"}})
    path = tmp_path / f"transfer{suffix}"
    runner = CliRunner()
    exported = runner.invoke(
        create_config_command(project_root=source),
        ["export", str(path), "--scope", "project", "--include-controls", "--format", "json"],
    )
    assert exported.exit_code == 0, exported.output
    assert json.loads(exported.output)["payload"]["usage"] == CONTROLS["usage"]
    denied = runner.invoke(
        create_config_command(project_root=destination), ["import", str(path), "--scope", "project"]
    )
    assert denied.exit_code != 0 and "accept-control-changes" in denied.output
    assert not (destination / ".henchman").exists()
    imported = runner.invoke(
        create_config_command(project_root=destination),
        ["import", str(path), "--scope", "project", "--accept-control-changes", "--format", "json"],
    )
    assert imported.exit_code == 0, imported.output
    assert (
        yaml.safe_load((destination / ".henchman" / "settings.yaml").read_text())["usage"]
        == CONTROLS["usage"]
    )


@pytest.mark.parametrize("operation", ["import", "export"])
def test_cli_rejects_sensitive_controls_without_touching_destination(tmp_path, operation) -> None:
    secret = "runtime-sensitive-canary"
    write(
        tmp_path,
        {
            "providers": {"deepseek": {"api_key": secret}},
            "usage": {"prices": [{"provider": "local", "model": "fixture", "source": secret}]},
        },
    )
    transfer = tmp_path / "transfer.json"
    transfer.write_text(
        json.dumps({"verification": {"checks": [{"kind": "command", "argv": ["python", secret]}]}})
    )
    original_transfer = transfer.read_bytes()
    settings = tmp_path / ".henchman" / "settings.yaml"
    original_settings = settings.read_bytes()
    flag = "--include-controls" if operation == "export" else "--accept-control-changes"
    result = CliRunner().invoke(
        create_config_command(project_root=tmp_path),
        [operation, str(transfer), "--scope", "project", flag],
    )
    assert result.exit_code != 0 and "credential" in result.output
    assert secret not in result.output
    assert transfer.read_bytes() == original_transfer
    assert settings.read_bytes() == original_settings


def test_ui_only_cli_shape_does_not_gain_control_defaults(tmp_path) -> None:
    write(tmp_path, {**CONTROLS, "ui": {"theme": "light"}})
    output = tmp_path / "ui.json"
    result = CliRunner().invoke(
        create_config_command(project_root=tmp_path), ["export", str(output), "--scope", "project"]
    )
    assert result.exit_code == 0
    assert json.loads(output.read_text()) == {"ui": {"theme": "light"}}


def test_export_reports_real_writer_failure(tmp_path, monkeypatch) -> None:
    from henchman.cli.commands import config_write_command

    write(tmp_path, CONTROLS)
    failure = OSError("owned export writer failure")

    def refuse(*_args):
        raise failure

    monkeypatch.setattr(config_write_command, "_write_serialized_payload", refuse)
    result = CliRunner().invoke(
        create_config_command(project_root=tmp_path),
        ["export", str(tmp_path / "output.json"), "--scope", "project", "--include-controls"],
    )
    assert result.exit_code != 0
    assert "owned export writer failure" in result.output
    assert not (tmp_path / "output.json").exists()
