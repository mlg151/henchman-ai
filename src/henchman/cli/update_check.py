"""Update guidance helpers built on shared system introspection."""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from henchman.cli.system_info import SystemInfo
from henchman.tools.security import sanitize_command


@dataclass(frozen=True, slots=True)
class UpdatePlan:
    """Structured update guidance for the Tier 1 CLI."""

    can_self_update: bool
    package_manager: str
    install_method: str
    command: tuple[str, ...]
    rendered_command: str
    summary: str
    failure_code: str | None


def render_update_command(command: tuple[str, ...]) -> str:
    """Render argv-style upgrade commands through the shared sanitization layer."""

    if not command:
        return ""
    return sanitize_command(shlex.join(command))


def _build_manual_update_plan(
    *,
    package_manager: str,
    install_method: str,
    summary: str,
    failure_code: str | None,
) -> UpdatePlan:
    """Build a manual-only update plan without a runnable command."""

    return UpdatePlan(
        can_self_update=False,
        package_manager=package_manager,
        install_method=install_method,
        command=(),
        rendered_command="",
        summary=summary,
        failure_code=failure_code,
    )


def _has_available_wrapper_manager(system_info: SystemInfo, install_method: str) -> bool:
    """Return whether the detected uv/pipx executable is available on PATH."""

    package_manager_signal = next(
        (signal for signal in system_info.health_signals if signal.name == "package-manager"),
        None,
    )
    if package_manager_signal is None:
        return True
    if system_info.install_context.install_method != install_method:
        return True
    return package_manager_signal.status == "pass"


def build_update_plan(system_info: SystemInfo) -> UpdatePlan:
    """Build deterministic update guidance for a detected install.

    Args:
        system_info: Shared system introspection payload.

    Returns:
        UpdatePlan: Structured, non-executing update guidance.
    """

    install_context = system_info.install_context
    package_name = system_info.package_name

    if install_context.install_method == "pip":
        command: tuple[str, ...] = (
            install_context.python_executable,
            "-m",
            "pip",
            "install",
            "--upgrade",
            package_name,
        )
        return UpdatePlan(
            can_self_update=True,
            package_manager="pip",
            install_method="pip",
            command=command,
            rendered_command=render_update_command(command),
            summary="Upgrade with the current Python interpreter and pip.",
            failure_code=None,
        )
    if install_context.install_method == "uv":
        if not _has_available_wrapper_manager(system_info, "uv"):
            return _build_manual_update_plan(
                package_manager="uv",
                install_method="uv",
                summary="Detected uv install, but the uv executable is unavailable; use manual upgrade guidance.",
                failure_code=None,
            )
        command = ("uv", "tool", "upgrade", package_name)
        return UpdatePlan(
            can_self_update=True,
            package_manager="uv",
            install_method="uv",
            command=command,
            rendered_command=render_update_command(command),
            summary="Upgrade the uv-managed tool install.",
            failure_code=None,
        )
    if install_context.install_method == "pipx":
        if not _has_available_wrapper_manager(system_info, "pipx"):
            return _build_manual_update_plan(
                package_manager="pipx",
                install_method="pipx",
                summary="Detected pipx install, but the pipx executable is unavailable; use manual upgrade guidance.",
                failure_code=None,
            )
        command = ("pipx", "upgrade", package_name)
        return UpdatePlan(
            can_self_update=True,
            package_manager="pipx",
            install_method="pipx",
            command=command,
            rendered_command=render_update_command(command),
            summary="Upgrade the pipx-managed app install.",
            failure_code=None,
        )
    return _build_manual_update_plan(
        package_manager="unknown",
        install_method="unknown",
        summary="Install method is unknown or ambiguous; use manual upgrade guidance.",
        failure_code="HMN_UPGRADE_INSTALL_METHOD_UNKNOWN",
    )
