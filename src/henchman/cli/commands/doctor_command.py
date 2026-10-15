"""User-facing Tier 1 doctor command composed from split diagnostic slices."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol, cast

import click

from henchman.cli.commands.doctor_core_command import (
    DependencyProbe,
    DoctorCoreReport,
    SystemInfoProvider,
    collect_doctor_core_report,
    render_doctor_core_text,
)
from henchman.cli.commands.doctor_tool_command import (
    DoctorToolReport,
    RegisteredToolNamesProvider,
    collect_doctor_tool_report,
    render_doctor_tool_text,
)
from henchman.cli.system_info import HealthStatus, SystemInfo
from henchman.config.repository import SettingsRepository

RequiredToolNames = Iterable[str]
SettingsPayload = dict[str, object]


class SettingsRepositoryLike(Protocol):
    """Protocol for the read-only repository behavior used by doctor."""

    def view(self, *, scope: object) -> SettingsPayload:
        """Return settings for a selected scope."""


SettingsRepositoryLikeFactory = Callable[[], SettingsRepositoryLike]
_DEFAULT_REQUIRED_TOOL_NAMES = ("skill", "sleep", "tool_search", "web_search")


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """Structured Tier 1 doctor report."""

    status: HealthStatus
    core: DoctorCoreReport
    tool_health: DoctorToolReport

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the report.

        Returns:
            A dictionary containing the overall status and both doctor slices.
        """
        return {
            "status": self.status,
            "core": self.core.to_dict(),
            "tool_health": self.tool_health.to_dict(),
        }


def collect_doctor_report(
    *,
    system_info: SystemInfo | None = None,
    settings_repository: SettingsRepositoryLike | None = None,
    dependency_probe: DependencyProbe | None = None,
    registered_tool_names: Iterable[str] | None = None,
    required_tool_names: RequiredToolNames | None = None,
) -> DoctorReport:
    """Collect the read-only Tier 1 doctor diagnostics.

    Args:
        system_info: Optional injected system info for deterministic tests.
        settings_repository: Optional injected settings repository.
        dependency_probe: Optional dependency availability predicate.
        registered_tool_names: Optional injected registered tool names for tests.
        required_tool_names: Optional required Tier 1 tool names override.

    Returns:
        The composed doctor report containing both split slices.
    """
    core_report = collect_doctor_core_report(
        system_info=system_info,
        settings_repository=cast("SettingsRepository | None", settings_repository),
        dependency_probe=dependency_probe,
    )
    tool_report = collect_doctor_tool_report(
        registered_tool_names=registered_tool_names,
        required_tool_names=required_tool_names
        if required_tool_names is not None
        else _DEFAULT_REQUIRED_TOOL_NAMES,
    )
    return DoctorReport(
        status=_summarize_status((core_report.status, tool_report.status)),
        core=core_report,
        tool_health=tool_report,
    )


def render_doctor_text(report: DoctorReport) -> str:
    """Render the composed doctor report as human-readable text.

    Args:
        report: Structured doctor report to render.

    Returns:
        The rendered text output.
    """
    sections = (
        ("Core diagnostics:", render_doctor_core_text(report.core)),
        ("Tool health:", render_doctor_tool_text(report.tool_health)),
    )
    lines = [f"Doctor status: {report.status.upper()}"]
    for heading, body in sections:
        lines.extend(("", heading, _indent_block(body)))
    return "\n".join(lines)


def create_doctor_command(
    *,
    system_info_provider: SystemInfoProvider | None = None,
    settings_repository_factory: SettingsRepositoryLikeFactory | None = None,
    dependency_probe: DependencyProbe | None = None,
    registered_tool_names_provider: RegisteredToolNamesProvider | None = None,
    required_tool_names: RequiredToolNames | None = None,
) -> click.Command:
    """Create the user-facing Tier 1 doctor click command.

    Args:
        system_info_provider: Optional system info provider for tests.
        settings_repository_factory: Optional settings repository factory.
        dependency_probe: Optional dependency availability predicate.
        registered_tool_names_provider: Optional tool registry provider for tests.
        required_tool_names: Optional required Tier 1 tool names override.

    Returns:
        A click command for the composed doctor diagnostics.
    """

    @click.command(name="doctor", help="Inspect environment, configuration, and tool health.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render diagnostics as text or JSON.",
    )
    def _doctor_command(output_format: str) -> None:
        report = collect_doctor_report(
            system_info=system_info_provider() if system_info_provider is not None else None,
            settings_repository=(
                settings_repository_factory()
                if settings_repository_factory is not None
                else None
            ),
            dependency_probe=dependency_probe,
            registered_tool_names=(
                registered_tool_names_provider()
                if registered_tool_names_provider is not None
                else None
            ),
            required_tool_names=required_tool_names,
        )
        if output_format == "json":
            click.echo(json.dumps(report.to_dict(), sort_keys=True))
            return
        click.echo(render_doctor_text(report))

    return _doctor_command


def register_doctor_command(cli: click.Group) -> click.Command:
    """Register the Tier 1 doctor command on a root click group.

    Args:
        cli: Root click group that should expose the doctor command.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_doctor_command()
    cli.add_command(command)
    return command


def _indent_block(text: str) -> str:
    return "\n".join(f"  {line}" for line in text.splitlines())


def _summarize_status(statuses: tuple[HealthStatus, ...]) -> HealthStatus:
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


doctor_command = create_doctor_command()


__all__ = [
    "DoctorReport",
    "collect_doctor_report",
    "create_doctor_command",
    "doctor_command",
    "register_doctor_command",
    "render_doctor_text",
]
