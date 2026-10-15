"""Explicit version command with install and update awareness."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Literal

import click
import httpx

from henchman.cli.system_info import SystemInfo, get_system_info
from henchman.cli.update_check import build_update_plan

VersionStatus = Literal["available", "current", "manual", "unknown"]
LatestVersionProvider = Callable[[str], str | None]
SystemInfoProvider = Callable[[], SystemInfo]


@dataclass(frozen=True, slots=True)
class VersionReport:
    """Structured version report for text, compact, and JSON rendering."""

    package_name: str
    version: str
    install_method: str
    package_manager: str
    update_status: VersionStatus
    update_summary: str
    latest_version: str | None
    update_command: str | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the report.

        Returns:
            A mapping containing the serialized report fields.
        """

        return asdict(self)


def create_version_command(
    *,
    system_info_provider: SystemInfoProvider | None = None,
    latest_version_provider: LatestVersionProvider | None = None,
) -> click.Command:
    """Create the explicit version click command.

    Args:
        system_info_provider: Optional provider for deterministic tests.
        latest_version_provider: Optional latest-version lookup for deterministic tests.

    Returns:
        A click command that renders version details.
    """

    @click.command(name="version")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json", "compact"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the version report as text, JSON, or compact text.",
    )
    def _version_command(output_format: str) -> None:
        resolved_system_info = (
            system_info_provider() if system_info_provider is not None else get_system_info()
        )
        report = build_version_report(
            system_info=resolved_system_info,
            latest_version_provider=latest_version_provider or fetch_latest_version,
        )
        if output_format == "json":
            click.echo(json.dumps(report.to_dict(), sort_keys=True))
            return
        if output_format == "compact":
            click.echo(render_version_report_compact(report))
            return
        click.echo(render_version_report_text(report))

    return _version_command


def build_version_report(
    *,
    system_info: SystemInfo,
    latest_version_provider: LatestVersionProvider,
) -> VersionReport:
    """Build a structured version report from shared introspection helpers.

    Args:
        system_info: Shared install and runtime introspection payload.
        latest_version_provider: Callable used to look up the latest released version.

    Returns:
        A structured report suitable for multiple output formats.
    """

    update_plan = build_update_plan(system_info)
    update_command = update_plan.rendered_command or None

    if not update_plan.can_self_update:
        update_status: VersionStatus = (
            "unknown"
            if _should_report_unknown_update_status(system_info=system_info, failure_code=update_plan.failure_code)
            else "manual"
        )
        return VersionReport(
            package_name=system_info.package_name,
            version=system_info.version,
            install_method=system_info.install_context.install_method,
            package_manager=system_info.install_context.package_manager,
            update_status=update_status,
            update_summary=update_plan.summary,
            latest_version=None,
            update_command=update_command,
        )

    latest_version = latest_version_provider(system_info.package_name)
    if latest_version is None:
        return VersionReport(
            package_name=system_info.package_name,
            version=system_info.version,
            install_method=system_info.install_context.install_method,
            package_manager=system_info.install_context.package_manager,
            update_status="unknown",
            update_summary="Unable to determine whether an update is available right now.",
            latest_version=None,
            update_command=update_command,
        )

    if is_newer_version(candidate=latest_version, current=system_info.version):
        return VersionReport(
            package_name=system_info.package_name,
            version=system_info.version,
            install_method=system_info.install_context.install_method,
            package_manager=system_info.install_context.package_manager,
            update_status="available",
            update_summary=f"Update available: {system_info.version} -> {latest_version}.",
            latest_version=latest_version,
            update_command=update_command,
        )

    return VersionReport(
        package_name=system_info.package_name,
        version=system_info.version,
        install_method=system_info.install_context.install_method,
        package_manager=system_info.install_context.package_manager,
        update_status="current",
        update_summary="You are up to date.",
        latest_version=latest_version,
        update_command=update_command,
    )


def _should_report_unknown_update_status(
    *,
    system_info: SystemInfo,
    failure_code: str | None,
) -> bool:
    """Return whether a non-self-update report should stay in the unknown state."""

    return (
        system_info.install_context.install_method == "unknown"
        or system_info.install_context.is_ambiguous
        or failure_code == "HMN_UPGRADE_INSTALL_METHOD_UNKNOWN"
    )


def render_version_report_text(report: VersionReport) -> str:
    """Render a human-readable multiline version report.

    Args:
        report: Structured report to render.

    Returns:
        The rendered text output.
    """

    lines = [
        f"Version: {report.version}",
        f"Install method: {report.install_method}",
        f"Package manager: {report.package_manager}",
        f"Update status: {report.update_status}",
        report.update_summary,
    ]
    if report.latest_version is not None:
        lines.append(f"Latest version: {report.latest_version}")
    if report.update_command is not None:
        lines.append(f"Recommended command: {report.update_command}")
    return "\n".join(lines)


def render_version_report_compact(report: VersionReport) -> str:
    """Render a one-line version summary.

    Args:
        report: Structured report to render.

    Returns:
        The rendered compact output.
    """

    summary = (
        f"henchman {report.version} ({report.install_method}; update {report.update_status})"
    )
    if report.latest_version is None:
        return summary
    return f"{summary} latest={report.latest_version}"


def fetch_latest_version(package_name: str) -> str | None:
    """Look up the latest published package version from PyPI.

    Args:
        package_name: Distribution name to query.

    Returns:
        The latest released version when available, otherwise ``None``.
    """

    try:
        response = httpx.get(
            f"https://pypi.org/pypi/{package_name}/json",
            follow_redirects=True,
            timeout=1.0,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    payload = response.json()
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    version = info.get("version")
    return version if isinstance(version, str) and version else None


def is_newer_version(*, candidate: str, current: str) -> bool:
    """Return whether the candidate release is newer than the current release.

    Args:
        candidate: Candidate released version.
        current: Installed version.

    Returns:
        ``True`` when the candidate is newer than the installed version.
    """

    candidate_parts = _parse_release_parts(candidate)
    current_parts = _parse_release_parts(current)
    if candidate_parts and current_parts:
        return candidate_parts > current_parts
    return candidate != current


def _parse_release_parts(version: str) -> tuple[int, ...]:
    """Parse numeric release components from a version string."""

    parts: list[int] = []
    for segment in version.split("."):
        digits = "".join(character for character in segment if character.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


version_command = create_version_command()


def register_version_command(cli: click.Group) -> click.Command:
    """Register the version command on a root click group.

    Args:
        cli: Root click group that should expose the version command.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_version_command()
    cli.add_command(command)
    return command


__all__ = [
    "VersionReport",
    "build_version_report",
    "create_version_command",
    "fetch_latest_version",
    "is_newer_version",
    "register_version_command",
    "render_version_report_compact",
    "render_version_report_text",
    "version_command",
]
