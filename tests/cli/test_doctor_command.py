"""Tests for the composed Tier 1 doctor command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from henchman.cli.system_info import HealthSignal, HealthStatus, InstallContext, SystemInfo


def _make_system_info(
    *,
    python_status: HealthStatus = "pass",
    install_status: HealthStatus = "pass",
    package_manager_status: HealthStatus = "pass",
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

    def __init__(self, *, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or {}
        self.view_calls = 0

    def view(self, *, scope: object) -> dict[str, object]:
        self.view_calls += 1
        return self.payload


def test_collect_doctor_report_combines_core_and_tool_health() -> None:
    """Doctor should surface both slice reports in one deterministic structure."""
    from henchman.cli.commands.doctor_command import collect_doctor_report

    settings_repository = _FakeSettingsRepository(payload={"ui": {"output_style": "compact"}})

    report = collect_doctor_report(
        system_info=_make_system_info(install_status="warn"),
        settings_repository=settings_repository,
        dependency_probe=lambda _: True,
        registered_tool_names=("tool_search",),
    )

    assert report.status == "fail"
    assert report.core.status == "warn"
    assert report.tool_health.status == "fail"
    assert report.core.checks[1].name == "install-method"
    assert report.tool_health.checks[0].name == "tier1-tools"
    assert settings_repository.view_calls == 1


def test_doctor_command_renders_structured_json() -> None:
    """The command should render both doctor slices in one JSON payload."""
    from henchman.cli.commands.doctor_command import create_doctor_command

    runner = CliRunner()
    system_info_calls = 0
    settings_repository = _FakeSettingsRepository(payload={"ui": {"output_style": "json"}})
    tool_provider_calls = 0

    def _system_info_provider() -> SystemInfo:
        nonlocal system_info_calls
        system_info_calls += 1
        return _make_system_info()

    def _registered_tool_names() -> tuple[str, ...]:
        nonlocal tool_provider_calls
        tool_provider_calls += 1
        return ("web_search", "sleep", "skill", "tool_search")

    command = create_doctor_command(
        system_info_provider=_system_info_provider,
        settings_repository_factory=lambda: settings_repository,
        dependency_probe=lambda _: True,
        registered_tool_names_provider=_registered_tool_names,
    )

    result = runner.invoke(command, ["--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)

    assert payload["status"] == "pass"
    assert payload["core"]["status"] == "pass"
    assert payload["tool_health"]["status"] == "pass"
    assert payload["core"]["checks"][0]["name"] == "runtime-environment"
    assert payload["tool_health"]["checks"][0]["name"] == "tier1-tools"
    capabilities = {entry["name"]: entry for entry in payload["tool_health"]["capabilities"]}
    assert capabilities["web_search"]["classification"] == "runtime-wired"
    assert capabilities["plugin marketplace install"]["classification"] == "unavailable"
    assert system_info_calls == 1
    assert settings_repository.view_calls == 1
    assert tool_provider_calls == 1


def test_doctor_command_renders_text_with_both_sections() -> None:
    """The command should preserve both slice outputs in text mode."""
    from henchman.cli.commands.doctor_command import create_doctor_command

    runner = CliRunner()
    command = create_doctor_command(
        system_info_provider=lambda: _make_system_info(package_manager_status="warn"),
        settings_repository_factory=lambda: _FakeSettingsRepository(
            payload={"ui": {"output_style": "compact"}}
        ),
        dependency_probe=lambda _: True,
        registered_tool_names_provider=lambda: ("tool_search",),
    )

    result = runner.invoke(command)

    assert result.exit_code == 0
    assert "Doctor status: FAIL" in result.output
    assert "Core diagnostics:" in result.output
    assert "Doctor status: WARN" in result.output
    assert "[warn] package-manager" in result.output
    assert "Tool health:" in result.output
    assert "Doctor tool status: FAIL" in result.output
    assert "Missing tools: skill, sleep, web_search." in result.output
    assert "- GitHub webhook-helper [docs-only]:" in result.output
