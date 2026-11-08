"""Tests for the core doctor diagnostics command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.system_info import HealthSignal, InstallContext, SystemInfo
from henchman.config.repository import SettingsRepository


def _make_system_info(
    *,
    python_status: str = "pass",
    install_status: str = "pass",
    package_manager_status: str = "pass",
) -> SystemInfo:
    return SystemInfo(
        package_name="henchman-ai",
        version="1.2.3",
        install_context=InstallContext(
            install_method="pip" if install_status == "pass" else "unknown",
            package_manager="pip" if package_manager_status == "pass" else "unknown",
            executable_path="/workspace/.venv/bin/henchman",
            python_executable="/workspace/.venv/bin/python",
            detected_with=("python environment",),
            is_ambiguous=install_status == "warn",
        ),
        health_signals=(
            HealthSignal(
                name="python-executable",
                status=python_status,
                summary="Python interpreter detected.",
            ),
            HealthSignal(
                name="install-detection",
                status=install_status,
                summary=(
                    "Detected pip install method."
                    if install_status == "pass"
                    else "Install method could not be determined."
                ),
            ),
            HealthSignal(
                name="package-manager",
                status=package_manager_status,
                summary=(
                    "Python can invoke pip via -m pip."
                    if package_manager_status == "pass"
                    else "Package manager is unknown; self-upgrade should stay manual."
                ),
            ),
        ),
    )


class _FakeSettingsRepository:
    """Minimal settings repository stub for doctor tests."""

    def __init__(self, *, payload: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.payload = payload or {}
        self.error = error
        self.view_calls = 0

    def view(self, *, scope: object) -> dict[str, object]:
        self.view_calls += 1
        if self.error is not None:
            raise self.error
        return self.payload


def test_collect_doctor_core_report_surfaces_invalid_configuration(
    monkeypatch, tmp_path: Path
) -> None:
    """Doctor should report invalid settings without mutating config files."""
    from henchman.cli.commands.doctor_core_command import collect_doctor_core_report

    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    settings_dir = home_dir / ".henchman"
    settings_dir.mkdir()
    settings_file = settings_dir / "settings.yaml"
    settings_file.write_text("ui:\n  theme: invalid-theme\n", encoding="utf-8")
    original_text = settings_file.read_text(encoding="utf-8")

    report = collect_doctor_core_report(
        system_info=_make_system_info(),
        settings_repository=SettingsRepository(project_root=project_root),
        dependency_probe=lambda _: True,
    )

    checks = {check.name: check for check in report.checks}

    assert report.status == "fail"
    assert checks["configuration"].status == "fail"
    assert "Invalid settings" in checks["configuration"].detail
    assert "ui.theme" in checks["configuration"].detail
    assert "fix the invalid settings" in checks["configuration"].remediation.lower()
    assert settings_file.read_text(encoding="utf-8") == original_text


def test_collect_doctor_core_report_fails_for_missing_runtime_dependency() -> None:
    """Doctor should fail when a required runtime dependency is unavailable."""
    from henchman.cli.commands.doctor_core_command import collect_doctor_core_report

    report = collect_doctor_core_report(
        system_info=_make_system_info(),
        settings_repository=_FakeSettingsRepository(payload={"ui": {"output_style": "compact"}}),
        dependency_probe=lambda module_name: module_name != "yaml",
    )

    checks = {check.name: check for check in report.checks}

    assert report.status == "fail"
    assert checks["runtime-dependencies"].status == "fail"
    assert "yaml" in checks["runtime-dependencies"].detail
    assert "install the missing runtime dependencies" in checks["runtime-dependencies"].remediation.lower()


def test_doctor_core_command_renders_structured_json() -> None:
    """The command should expose structured diagnostics for JSON consumers."""
    from henchman.cli.commands.doctor_core_command import create_doctor_core_command

    runner = CliRunner()
    settings_repository = _FakeSettingsRepository(payload={"ui": {"output_style": "json"}})
    command = create_doctor_core_command(
        system_info_provider=lambda: _make_system_info(install_status="warn"),
        settings_repository_factory=lambda: settings_repository,
        dependency_probe=lambda _: True,
    )

    result = runner.invoke(command, ["--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)

    assert payload["status"] == "warn"
    assert payload["checks"][0]["name"] == "runtime-environment"
    assert payload["checks"][1]["name"] == "install-method"
    assert payload["checks"][2]["name"] == "package-manager"
    assert payload["checks"][3]["name"] == "runtime-dependencies"
    assert payload["checks"][4]["name"] == "configuration"
    assert payload["checks"][1]["status"] == "warn"
    assert payload["checks"][1]["remediation"]
    assert settings_repository.view_calls == 1


def test_doctor_core_command_renders_text_with_remediation() -> None:
    """The command should render human-readable remediation guidance."""
    from henchman.cli.commands.doctor_core_command import create_doctor_core_command

    runner = CliRunner()
    command = create_doctor_core_command(
        system_info_provider=lambda: _make_system_info(package_manager_status="warn"),
        settings_repository_factory=lambda: _FakeSettingsRepository(payload={"ui": {"output_style": "compact"}}),
        dependency_probe=lambda _: True,
    )

    result = runner.invoke(command)

    assert result.exit_code == 0
    assert "Doctor status: WARN" in result.output
    assert "[warn] package-manager" in result.output
    assert "Use manual guidance" in result.output


def _effective_controls(repository: SettingsRepository) -> dict[str, object]:
    from henchman.cli.commands.doctor_core_command import collect_doctor_core_report

    report = collect_doctor_core_report(
        system_info=_make_system_info(), settings_repository=repository,
        dependency_probe=lambda _: True,
    )
    configuration = next(check for check in report.checks if check.name == "configuration")
    assert configuration.status == "pass"
    return json.loads(configuration.detail.removeprefix("Effective settings: "))


def test_doctor_runtime_controls_keep_one_snapshot_and_exact_origins(tmp_path, monkeypatch) -> None:
    """Inspect held controls, including price provenance, without reloading files."""
    from henchman.config.runtime import RuntimeSettingsState
    from henchman.config.settings import load_settings_snapshot

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    global_file = home / ".henchman" / "settings.yaml"
    global_file.parent.mkdir()
    price = {"provider": "ollama", "model": "local-fixture", "input_per_1k": "0.125",
             "output_per_1k": "0", "currency": "USD", "source": "local price catalog",
             "as_of": "2026-11-07"}
    global_file.write_text(yaml.safe_dump({"usage": {"prices": [price]}}))
    project = tmp_path / "project"
    project_file = project / ".henchman" / "settings.yaml"
    project_file.parent.mkdir(parents=True)
    project_file.write_text("operations: {persistence: durable}\n")
    state = RuntimeSettingsState(load_settings_snapshot(project_root=project))
    checks = [{"kind": "file_contains", "path": "result.txt", "text": "expected evidence"}]
    state.update({"verification": {"checks": checks}})
    before = state.snapshot()
    held_usage = state.settings.usage
    # Later file edits are independent of the active runtime snapshot.
    project_file.write_text("operations: {persistence: process}\n")
    reads = 0

    def snapshot():
        nonlocal reads
        reads += 1
        return state.snapshot()

    controls = _effective_controls(SettingsRepository(project, snapshot_provider=snapshot))

    assert controls["usage.persistence"] == {"value": "process", "resolved_scope": "default"}
    prices = controls["usage.prices"]
    assert prices["resolved_scope"] == "global"
    assert prices["value"] == [before.settings.usage.prices[0].model_dump(mode="python")]
    assert controls["operations.persistence"] == {"value": "durable", "resolved_scope": "project"}
    assert controls["verification.checks"] == {"value": checks, "resolved_scope": "session"}
    assert reads == 1
    assert state.settings.usage is held_usage and state.snapshot() == before
    assert yaml.safe_load(global_file.read_text()) == {"usage": {"prices": [price]}}
    assert project_file.read_text() == "operations: {persistence: process}\n"


def test_doctor_reports_default_empty_controls_explicitly(tmp_path) -> None:
    from henchman.config.runtime import RuntimeSettingsState
    from henchman.config.schema import Settings

    state = RuntimeSettingsState.from_settings(Settings())
    controls = _effective_controls(SettingsRepository(tmp_path, snapshot_provider=state.snapshot))
    for key, value in {"usage.persistence": "process", "usage.prices": [],
                       "operations.persistence": "process", "verification.checks": []}.items():
        assert controls[key] == {"value": value, "resolved_scope": "default"}


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_doctor_projects_control_evidence_without_changing_execution_values(tmp_path, output_format) -> None:
    from henchman.cli.commands.doctor_core_command import create_doctor_core_command
    from henchman.config.runtime import RuntimeSettingsState
    from henchman.config.schema import Settings

    secret = "doctor-runtime-credential-canary"
    header_secret = "doctor-unknown-header-canary"
    settings = Settings.model_validate({
        "providers": {"deepseek": {"api_key": secret}},
        "usage": {"prices": [{"provider": "deepseek", "model": secret,
                              "source": f"price source {secret}", "input_per_1k": "0.125",
                              "as_of": "2026-11-07"}], "persistence": "durable"},
        "operations": {"persistence": "durable"},
        "verification": {"checks": [{"kind": "file_contains", "path": f"{secret}.txt",
                                     "text": f"{secret}\nAuthorization: {header_secret}"}]},
    })
    state = RuntimeSettingsState.from_settings(settings)
    before = state.snapshot()
    command = create_doctor_core_command(
        system_info_provider=_make_system_info,
        settings_repository_factory=lambda: SettingsRepository(tmp_path, snapshot_provider=state.snapshot),
        dependency_probe=lambda _: True,
    )

    result = CliRunner().invoke(command, ["--format", output_format])

    assert result.exit_code == 0, result.output
    assert "usage.prices" in result.output and "verification.checks" in result.output
    assert "usage.persistence" in result.output and "operations.persistence" in result.output
    assert secret not in result.output and header_secret not in result.output
    assert "[REDACTED]" in result.output
    assert "2026-11-07" in result.output and "0.125" in result.output
    assert "price source" in result.output and "session" in result.output
    assert state.settings is settings and state.snapshot() == before
    assert settings.usage.prices[0].model == secret
    assert settings.verification.checks[0]["text"] == f"{secret}\nAuthorization: {header_secret}"
