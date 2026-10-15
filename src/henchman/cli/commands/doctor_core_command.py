"""Core doctor diagnostics for environment and configuration health."""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass

import click

from henchman.cli.system_info import HealthSignal, HealthStatus, SystemInfo, get_system_info
from henchman.config.repository import SettingsRepository, SettingsScope

DependencyProbe = Callable[[str], bool]
SystemInfoProvider = Callable[[], SystemInfo]
SettingsRepositoryFactory = Callable[[], SettingsRepository]
_DEFAULT_RUNTIME_DEPENDENCIES = ("click", "yaml", "pydantic")


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    """Structured doctor check suitable for text and JSON rendering."""

    name: str
    status: HealthStatus
    summary: str
    detail: str
    remediation: str


@dataclass(frozen=True, slots=True)
class DoctorCoreReport:
    """Structured core doctor report."""

    status: HealthStatus
    checks: tuple[DoctorCheck, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation of the report.

        Returns:
            A dictionary containing the top-level status and serialized checks.
        """
        return {
            "status": self.status,
            "checks": [asdict(check) for check in self.checks],
        }


def collect_doctor_core_report(
    *,
    system_info: SystemInfo | None = None,
    settings_repository: SettingsRepository | None = None,
    dependency_probe: DependencyProbe | None = None,
) -> DoctorCoreReport:
    """Collect the read-only core doctor diagnostics.

    Args:
        system_info: Optional injected system info for deterministic tests.
        settings_repository: Optional injected settings repository.
        dependency_probe: Optional dependency availability predicate.

    Returns:
        The structured core doctor report.
    """
    resolved_system_info = system_info or get_system_info()
    repository = settings_repository or SettingsRepository()
    probe = dependency_probe or _is_dependency_available

    checks = (
        _build_runtime_environment_check(resolved_system_info),
        _build_install_method_check(resolved_system_info),
        _build_package_manager_check(resolved_system_info),
        _build_runtime_dependencies_check(probe),
        _build_configuration_check(repository),
    )
    return DoctorCoreReport(status=_summarize_status(checks), checks=checks)


def render_doctor_core_text(report: DoctorCoreReport) -> str:
    """Render the doctor report as human-readable text.

    Args:
        report: Structured doctor report to render.

    Returns:
        The rendered text output.
    """
    lines = [f"Doctor status: {report.status.upper()}"]
    for check in report.checks:
        lines.extend(
            [
                f"[{check.status}] {check.name}: {check.summary}",
                f"  detail: {check.detail}",
                f"  remediation: {check.remediation}",
            ]
        )
    return "\n".join(lines)


def create_doctor_core_command(
    *,
    system_info_provider: SystemInfoProvider | None = None,
    settings_repository_factory: SettingsRepositoryFactory | None = None,
    dependency_probe: DependencyProbe | None = None,
) -> click.Command:
    """Create the core doctor click command.

    Args:
        system_info_provider: Optional system info provider for tests.
        settings_repository_factory: Optional settings repository factory.
        dependency_probe: Optional dependency availability predicate.

    Returns:
        A click command for the core doctor diagnostics.
    """
    resolved_system_info_provider = system_info_provider or get_system_info
    resolved_repository_factory = settings_repository_factory or SettingsRepository

    @click.command(name="doctor-core")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render diagnostics as text or JSON.",
    )
    def _doctor_core_command(output_format: str) -> None:
        report = collect_doctor_core_report(
            system_info=resolved_system_info_provider(),
            settings_repository=resolved_repository_factory(),
            dependency_probe=dependency_probe,
        )
        if output_format == "json":
            click.echo(json.dumps(report.to_dict(), sort_keys=True))
            return
        click.echo(render_doctor_core_text(report))

    return _doctor_core_command


doctor_core_command = create_doctor_core_command()


def _build_runtime_environment_check(system_info: SystemInfo) -> DoctorCheck:
    signal = _get_health_signal(system_info, "python-executable")
    detail = (
        "Executable: "
        f"{system_info.install_context.executable_path or '<unavailable>'}; "
        f"Python: {system_info.install_context.python_executable or '<unavailable>'}"
    )
    remediation = (
        "No action required."
        if signal.status == "pass"
        else "Ensure the Henchman executable is launched from a valid Python installation."
    )
    return DoctorCheck(
        name="runtime-environment",
        status=signal.status,
        summary=signal.summary,
        detail=detail,
        remediation=remediation,
    )


def _build_install_method_check(system_info: SystemInfo) -> DoctorCheck:
    signal = _get_health_signal(system_info, "install-detection")
    install_context = system_info.install_context
    detected_with = ", ".join(install_context.detected_with) or "no install markers"
    detail = f"Install method: {install_context.install_method}; detected with: {detected_with}."
    remediation = (
        "No action required."
        if signal.status == "pass"
        else "Use manual guidance until the installation method can be confirmed."
    )
    return DoctorCheck(
        name="install-method",
        status=signal.status,
        summary=signal.summary,
        detail=detail,
        remediation=remediation,
    )


def _build_package_manager_check(system_info: SystemInfo) -> DoctorCheck:
    signal = _get_health_signal(system_info, "package-manager")
    detail = (
        "Install method: "
        f"{system_info.install_context.install_method}; package manager: "
        f"{system_info.install_context.package_manager}."
    )
    remediation = (
        "No action required."
        if signal.status == "pass"
        else "Use manual guidance until the package manager becomes available on PATH."
    )
    return DoctorCheck(
        name="package-manager",
        status=signal.status,
        summary=signal.summary,
        detail=detail,
        remediation=remediation,
    )


def _build_runtime_dependencies_check(probe: DependencyProbe) -> DoctorCheck:
    available_modules = tuple(
        module_name
        for module_name in _DEFAULT_RUNTIME_DEPENDENCIES
        if probe(module_name)
    )
    missing_modules = tuple(
        module_name
        for module_name in _DEFAULT_RUNTIME_DEPENDENCIES
        if module_name not in available_modules
    )
    if missing_modules:
        return DoctorCheck(
            name="runtime-dependencies",
            status="fail",
            summary="Required runtime dependencies are missing.",
            detail=f"Missing modules: {', '.join(missing_modules)}.",
            remediation="Install the missing runtime dependencies and rerun henchman doctor.",
        )
    return DoctorCheck(
        name="runtime-dependencies",
        status="pass",
        summary="Required runtime dependencies are available.",
        detail=f"Available modules: {', '.join(available_modules)}.",
        remediation="No action required.",
    )


def _build_configuration_check(settings_repository: SettingsRepository) -> DoctorCheck:
    try:
        settings_payload = settings_repository.view(scope=SettingsScope.MERGED)
    except ValueError as exc:
        return DoctorCheck(
            name="configuration",
            status="fail",
            summary="Configuration is invalid.",
            detail=str(exc),
            remediation="Fix the invalid settings values or remove the broken settings override.",
        )

    top_level_keys = ", ".join(sorted(settings_payload)) or "defaults only"
    return DoctorCheck(
        name="configuration",
        status="pass",
        summary="Configuration is valid.",
        detail=f"Merged settings loaded successfully from: {top_level_keys}.",
        remediation="No action required.",
    )


def _get_health_signal(system_info: SystemInfo, name: str) -> HealthSignal:
    for signal in system_info.health_signals:
        if signal.name == name:
            return signal
    return HealthSignal(name=name, status="warn", summary=f"{name} signal is unavailable.")


def _summarize_status(checks: tuple[DoctorCheck, ...]) -> HealthStatus:
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _is_dependency_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None
