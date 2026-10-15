"""Tool-health doctor diagnostics for Tier 1 builtin registry checks."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass

import click

from henchman.cli.commands.discovery_capabilities import (
    DiscoveryCapability,
    build_discovery_capabilities,
)
from henchman.cli.system_info import HealthStatus
from henchman.cli.tool_manager import ToolManager

RegisteredToolNamesProvider = Callable[[], tuple[str, ...]]
_DEFAULT_REQUIRED_TIER1_TOOLS = ("skill", "sleep", "tool_search", "web_search")


def _normalize_tool_names(tool_names: Iterable[str]) -> tuple[str, ...]:
    """Normalize tool names into a deterministic sorted tuple."""
    return tuple(sorted({tool_name.strip() for tool_name in tool_names if tool_name.strip()}))


@dataclass(frozen=True, slots=True)
class DoctorToolCheck:
    """Structured doctor check for tool-health reporting."""

    name: str
    status: HealthStatus
    summary: str
    detail: str
    remediation: str


@dataclass(frozen=True, slots=True)
class DoctorToolReport:
    """Structured tool-health doctor report."""

    status: HealthStatus
    checks: tuple[DoctorToolCheck, ...]
    capabilities: tuple[DiscoveryCapability, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the report.

        Returns:
            A dictionary containing the top-level status and serialized checks.
        """
        return {
            "status": self.status,
            "checks": [asdict(check) for check in self.checks],
            "capabilities": [asdict(capability) for capability in self.capabilities],
        }


def collect_doctor_tool_report(
    *,
    registered_tool_names: Iterable[str] | None = None,
    required_tool_names: Iterable[str] = _DEFAULT_REQUIRED_TIER1_TOOLS,
) -> DoctorToolReport:
    """Collect the read-only tool-health doctor diagnostics.

    Args:
        registered_tool_names: Optional injected registered tool names for tests.
        required_tool_names: Required Tier 1 tool names that must be present.

    Returns:
        The structured tool-health doctor report.
    """
    resolved_registered_tool_names = (
        _normalize_tool_names(registered_tool_names)
        if registered_tool_names is not None
        else _collect_registered_builtin_tool_names()
    )
    resolved_required_tool_names = _normalize_tool_names(required_tool_names)

    checks = (
        _build_tier1_tool_registry_check(
            registered_tool_names=resolved_registered_tool_names,
            required_tool_names=resolved_required_tool_names,
        ),
    )
    return DoctorToolReport(
        status=_summarize_status(checks),
        checks=checks,
        capabilities=build_discovery_capabilities(
            registered_tool_names=resolved_registered_tool_names,
        ),
    )


def render_doctor_tool_text(report: DoctorToolReport) -> str:
    """Render the tool-health doctor report as human-readable text.

    Args:
        report: Structured tool-health report to render.

    Returns:
        The rendered text output.
    """
    lines = [f"Doctor tool status: {report.status.upper()}"]
    for check in report.checks:
        lines.extend(
            [
                f"[{check.status}] {check.name}: {check.summary}",
                f"  detail: {check.detail}",
                f"  remediation: {check.remediation}",
            ]
        )
    lines.append("Capabilities:")
    for capability in report.capabilities:
        lines.extend(
            [
                f"- {capability.name} [{capability.classification}]: {capability.summary}",
                f"  detail: {capability.detail}",
            ]
        )
    return "\n".join(lines)


def create_doctor_tool_command(
    *,
    registered_tool_names_provider: RegisteredToolNamesProvider | None = None,
    required_tool_names: Iterable[str] = _DEFAULT_REQUIRED_TIER1_TOOLS,
) -> click.Command:
    """Create the tool-health doctor click command.

    Args:
        registered_tool_names_provider: Optional provider for deterministic tests.
        required_tool_names: Required Tier 1 tool names that must be present.

    Returns:
        A click command for the tool-health diagnostics.
    """
    resolved_required_tool_names = _normalize_tool_names(required_tool_names)

    @click.command(name="doctor-tool")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render diagnostics as text or JSON.",
    )
    def _doctor_tool_command(output_format: str) -> None:
        report = collect_doctor_tool_report(
            registered_tool_names=(
                registered_tool_names_provider()
                if registered_tool_names_provider is not None
                else None
            ),
            required_tool_names=resolved_required_tool_names,
        )
        if output_format == "json":
            click.echo(json.dumps(report.to_dict(), sort_keys=True))
            return
        click.echo(render_doctor_tool_text(report))

    return _doctor_tool_command


def _collect_registered_builtin_tool_names() -> tuple[str, ...]:
    """Collect the live registered builtin tool names through the shared registry."""
    tool_manager = ToolManager()
    tool_manager.register_builtin_tools()
    return _normalize_tool_names(tool_manager.registry.list_tools())


def _build_tier1_tool_registry_check(
    *,
    registered_tool_names: tuple[str, ...],
    required_tool_names: tuple[str, ...],
) -> DoctorToolCheck:
    missing_tool_names = tuple(
        tool_name for tool_name in required_tool_names if tool_name not in registered_tool_names
    )
    registered_display = ", ".join(registered_tool_names) or "none"
    if missing_tool_names:
        missing_display = ", ".join(missing_tool_names)
        return DoctorToolCheck(
            name="tier1-tools",
            status="fail",
            summary="Required Tier 1 tools are missing from the registry.",
            detail=(
                f"Missing tools: {missing_display}. "
                f"Registered tools: {registered_display}."
            ),
            remediation=(
                "Register the missing Tier 1 builtin tools and rerun henchman doctor."
            ),
        )
    return DoctorToolCheck(
        name="tier1-tools",
        status="pass",
        summary="Required Tier 1 tools are registered.",
        detail=f"Registered tools: {registered_display}.",
        remediation="No action required.",
    )


def _summarize_status(checks: tuple[DoctorToolCheck, ...]) -> HealthStatus:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


doctor_tool_command = create_doctor_tool_command()
