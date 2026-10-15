"""Tests for the explicit Tier 1 version command."""

from __future__ import annotations

import json

from click.testing import CliRunner

from henchman.cli.system_info import HealthSignal, InstallContext, SystemInfo
from henchman.version import VERSION


def _make_system_info(
    *,
    install_method: str = "pip",
    version: str = VERSION,
    health_signals: tuple[HealthSignal, ...] = (),
    is_ambiguous: bool = False,
) -> SystemInfo:
    package_manager = install_method if install_method != "unknown" else "unknown"
    return SystemInfo(
        package_name="henchman-ai",
        version=version,
        install_context=InstallContext(
            install_method=install_method,  # type: ignore[arg-type]
            package_manager=package_manager,  # type: ignore[arg-type]
            executable_path="/workspace/.venv/bin/henchman",
            python_executable="/workspace/.venv/bin/python",
            detected_with=("python environment",),
            is_ambiguous=is_ambiguous,
        ),
        health_signals=health_signals,
    )


def test_version_command_reports_available_update_in_text_output() -> None:
    """The command should surface an available update and its guidance."""
    from henchman.cli.commands.version_command import create_version_command

    runner = CliRunner()
    command = create_version_command(
        system_info_provider=lambda: _make_system_info(version="1.2.3"),
        latest_version_provider=lambda _: "1.3.0",
    )

    result = runner.invoke(command)

    assert result.exit_code == 0
    assert "Version: 1.2.3" in result.output
    assert "Install method: pip" in result.output
    assert "Update status: available" in result.output
    assert "Update available: 1.2.3 -> 1.3.0." in result.output
    assert "Recommended command: /workspace/.venv/bin/python -m pip install --upgrade henchman-ai" in result.output


def test_version_command_reports_current_version_when_no_update_is_needed() -> None:
    """The command should confirm when the install is already current."""
    from henchman.cli.commands.version_command import create_version_command

    runner = CliRunner()
    command = create_version_command(
        system_info_provider=lambda: _make_system_info(version="1.2.3"),
        latest_version_provider=lambda _: "1.2.3",
    )

    result = runner.invoke(command, ["--format", "compact"])

    assert result.exit_code == 0
    assert result.output.strip() == "henchman 1.2.3 (pip; update current) latest=1.2.3"


def test_version_command_degrades_gracefully_for_unknown_install() -> None:
    """Unknown installs should avoid self-update claims and stay manual."""
    from henchman.cli.commands.version_command import create_version_command

    runner = CliRunner()
    latest_version_calls = 0

    def _latest_version(_: str) -> str | None:
        nonlocal latest_version_calls
        latest_version_calls += 1
        return "9.9.9"

    command = create_version_command(
        system_info_provider=lambda: _make_system_info(install_method="unknown"),
        latest_version_provider=_latest_version,
    )

    result = runner.invoke(command)

    assert result.exit_code == 0
    assert latest_version_calls == 0
    assert "Install method: unknown" in result.output
    assert "Update status: unknown" in result.output
    assert "Install method is unknown or ambiguous" in result.output
    assert "Recommended command:" not in result.output


def test_build_version_report_preserves_wrapper_missing_reason() -> None:
    """Known installs should keep wrapper-missing guidance instead of collapsing to generic manual text."""
    from henchman.cli.commands.version_command import build_version_report

    latest_version_calls = 0

    def _latest_version(_: str) -> str | None:
        nonlocal latest_version_calls
        latest_version_calls += 1
        return "9.9.9"

    report = build_version_report(
        system_info=_make_system_info(
            install_method="uv",
            health_signals=(
                HealthSignal(
                    name="package-manager",
                    status="warn",
                    summary="Detected uv install, but the uv executable is unavailable.",
                ),
            ),
        ),
        latest_version_provider=_latest_version,
    )

    assert latest_version_calls == 0
    assert report.update_status == "manual"
    assert (
        report.update_summary
        == "Detected uv install, but the uv executable is unavailable; use manual upgrade guidance."
    )
    assert report.update_command is None


def test_build_version_report_marks_ambiguous_install_as_unknown() -> None:
    """Ambiguous installs should surface the specific unknown-install reason."""
    from henchman.cli.commands.version_command import build_version_report

    latest_version_calls = 0

    def _latest_version(_: str) -> str | None:
        nonlocal latest_version_calls
        latest_version_calls += 1
        return "9.9.9"

    report = build_version_report(
        system_info=_make_system_info(install_method="unknown", is_ambiguous=True),
        latest_version_provider=_latest_version,
    )

    assert latest_version_calls == 0
    assert report.update_status == "unknown"
    assert (
        report.update_summary
        == "Install method is unknown or ambiguous; use manual upgrade guidance."
    )
    assert report.update_command is None


def test_version_command_renders_json_output() -> None:
    """The command should expose a structured JSON payload."""
    from henchman.cli.commands.version_command import create_version_command

    runner = CliRunner()
    command = create_version_command(
        system_info_provider=lambda: _make_system_info(version="1.2.3"),
        latest_version_provider=lambda _: None,
    )

    result = runner.invoke(command, ["--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)

    assert payload["package_name"] == "henchman-ai"
    assert payload["version"] == "1.2.3"
    assert payload["install_method"] == "pip"
    assert payload["package_manager"] == "pip"
    assert payload["update_status"] == "unknown"
    assert payload["latest_version"] is None
    assert payload["update_command"] == "/workspace/.venv/bin/python -m pip install --upgrade henchman-ai"


def test_explicit_version_command_reports_same_version_as_flag(monkeypatch) -> None:
    """The explicit command should agree with the existing --version flag."""
    from henchman.cli.app import cli

    runner = CliRunner()
    monkeypatch.setattr(
        "henchman.cli.commands.version_command.get_system_info",
        lambda: _make_system_info(version=VERSION),
    )
    monkeypatch.setattr(
        "henchman.cli.commands.version_command.fetch_latest_version",
        lambda _: VERSION,
    )

    flag_result = runner.invoke(cli, ["--version"])
    command_result = runner.invoke(cli, ["version"])

    assert flag_result.exit_code == 0
    assert command_result.exit_code == 0
    assert VERSION in flag_result.output
    assert VERSION in command_result.output
