"""Tests for the tool-health doctor diagnostics command."""

from __future__ import annotations

import json

from click.testing import CliRunner


def test_collect_doctor_tool_report_reports_missing_tier1_tools() -> None:
    """Doctor should fail when a required Tier 1 tool is missing."""
    from henchman.cli.commands.doctor_tool_command import collect_doctor_tool_report

    report = collect_doctor_tool_report(
        registered_tool_names=("sleep", "tool_search", "web_search")
    )
    checks = {check.name: check for check in report.checks}

    assert report.status == "fail"
    assert checks["tier1-tools"].status == "fail"
    assert checks["tier1-tools"].summary == "Required Tier 1 tools are missing from the registry."
    assert "Missing tools: skill." in checks["tier1-tools"].detail
    assert "Registered tools: sleep, tool_search, web_search." in checks["tier1-tools"].detail
    assert "register the missing tier 1 builtin tools" in checks["tier1-tools"].remediation.lower()


def test_collect_doctor_tool_report_reads_live_registry_defaults() -> None:
    """Doctor should inspect the live builtin registry by default."""
    from henchman.cli.commands.doctor_tool_command import collect_doctor_tool_report

    report = collect_doctor_tool_report()
    checks = {check.name: check for check in report.checks}

    assert report.status == "pass"
    assert checks["tier1-tools"].status == "pass"
    assert checks["tier1-tools"].summary == "Required Tier 1 tools are registered."
    for tool_name in ("skill", "sleep", "tool_search", "web_search"):
        assert tool_name in checks["tier1-tools"].detail


def test_doctor_tool_command_renders_structured_json() -> None:
    """The command should expose structured JSON for tool-health consumers."""
    from henchman.cli.commands.doctor_tool_command import create_doctor_tool_command

    runner = CliRunner()
    provider_calls = 0

    def _registered_tool_names() -> tuple[str, ...]:
        nonlocal provider_calls
        provider_calls += 1
        return ("web_search", "sleep", "skill", "tool_search")

    command = create_doctor_tool_command(registered_tool_names_provider=_registered_tool_names)

    result = runner.invoke(command, ["--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)

    assert payload["status"] == "pass"
    assert payload["checks"][0]["name"] == "tier1-tools"
    assert payload["checks"][0]["status"] == "pass"
    assert "skill" in payload["checks"][0]["detail"]
    capabilities = {entry["name"]: entry for entry in payload["capabilities"]}
    assert capabilities["web_search"]["classification"] == "runtime-wired"
    assert capabilities["plugin marketplace install"]["classification"] == "unavailable"
    assert capabilities["GitHub webhook-helper"]["classification"] == "docs-only"
    assert capabilities["Tier 10 dialogs"]["classification"] == "undiscoverable"
    assert provider_calls == 1


def test_doctor_tool_command_renders_text_with_missing_tools_guidance() -> None:
    """The command should render actionable guidance when tools are missing."""
    from henchman.cli.commands.doctor_tool_command import create_doctor_tool_command

    runner = CliRunner()
    command = create_doctor_tool_command(
        registered_tool_names_provider=lambda: ("tool_search",),
    )

    result = runner.invoke(command)

    assert result.exit_code == 0
    assert "Doctor tool status: FAIL" in result.output
    assert "[fail] tier1-tools" in result.output
    assert "Missing tools: skill, sleep, web_search." in result.output
    assert "Register the missing Tier 1 builtin tools" in result.output
    assert "Capabilities:" in result.output
    assert "- skill [local-only]:" in result.output
    assert "- GitHub webhook-helper [docs-only]:" in result.output


def test_collect_doctor_tool_report_includes_capability_classifications() -> None:
    """Doctor tool report should expose the shared discovery-truth matrix."""
    from henchman.cli.commands.doctor_tool_command import collect_doctor_tool_report

    report = collect_doctor_tool_report(
        registered_tool_names=(
            "mcp",
            "mcp_auth",
            "schedule_cron",
            "skill",
            "sleep",
            "tool_search",
            "web_search",
        )
    )
    capabilities = {capability.name: capability for capability in report.capabilities}

    assert capabilities["mcp"].classification == "runtime-wired"
    assert capabilities["skill"].classification == "local-only"
    assert capabilities["schedule_cron"].classification == "metadata-only"
    assert capabilities["agents-platform install"].classification == "unavailable"
