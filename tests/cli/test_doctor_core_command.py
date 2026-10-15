"""Tests for the core doctor diagnostics command."""

from __future__ import annotations

import json
from pathlib import Path

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
