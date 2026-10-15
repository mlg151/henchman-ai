"""Shared system introspection helpers for Tier 1 commands."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from henchman.version import VERSION

DEFAULT_PACKAGE_NAME = "henchman-ai"

InstallMethod = Literal["pip", "uv", "pipx", "unknown"]
HealthStatus = Literal["pass", "warn", "fail"]
CommandResolver = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    """Deterministic runtime facts used for install detection.

    Attributes:
        executable_path: The resolved CLI executable path.
        python_executable: The Python interpreter backing the current CLI process.
        package_name: Canonical distribution name used for update guidance.
        version: Installed package version.
        environment: Relevant environment variables.
    """

    executable_path: str
    python_executable: str
    package_name: str = DEFAULT_PACKAGE_NAME
    version: str = VERSION
    environment: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class InstallContext:
    """Normalized install detection result."""

    install_method: InstallMethod
    package_manager: InstallMethod
    executable_path: str
    python_executable: str
    detected_with: tuple[str, ...] = ()
    is_ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class HealthSignal:
    """Structured health signal for doctor, version, and upgrade."""

    name: str
    status: HealthStatus
    summary: str


@dataclass(frozen=True, slots=True)
class SystemInfo:
    """Shared system introspection payload consumed by Tier 1 commands."""

    package_name: str
    version: str
    install_context: InstallContext
    health_signals: tuple[HealthSignal, ...]


def get_runtime_snapshot() -> RuntimeSnapshot:
    """Collect runtime facts for install detection.

    Returns:
        RuntimeSnapshot: Deterministic runtime values for the current process.
    """

    executable_path = str(Path(sys.argv[0]).resolve()) if sys.argv and sys.argv[0] else ""
    python_executable = str(Path(sys.executable).resolve()) if sys.executable else ""
    visible_environment = {
        key: value
        for key, value in os.environ.items()
        if key.startswith("PIPX_") or key.startswith("UV_") or key == "VIRTUAL_ENV"
    }
    return RuntimeSnapshot(
        executable_path=executable_path,
        python_executable=python_executable,
        environment=visible_environment,
    )


def detect_install_context(snapshot: RuntimeSnapshot) -> InstallContext:
    """Detect how the current CLI install was provisioned.

    Args:
        snapshot: Runtime facts to inspect.

    Returns:
        InstallContext: Normalized install metadata.
    """

    # Normalize only detection inputs; retain original paths for execution argv.
    python_path = snapshot.python_executable.replace("\\", "/").lower()
    executable_path = snapshot.executable_path.replace("\\", "/").lower()
    environment = {key.upper(): value for key, value in snapshot.environment.items()}

    matched_methods: list[tuple[InstallMethod, str]] = []

    pipx_detected = _looks_like_pipx_install(
        executable_path=executable_path,
        python_path=python_path,
        environment=environment,
    )
    uv_detected = _looks_like_uv_install(
        executable_path=executable_path,
        python_path=python_path,
        environment=environment,
    )

    if pipx_detected:
        matched_methods.append(("pipx", "pipx markers"))
    if uv_detected:
        matched_methods.append(("uv", "uv markers"))
    if not matched_methods and _looks_like_pip_install(
        executable_path=executable_path,
        python_path=python_path,
        environment=environment,
    ):
        matched_methods.append(("pip", "python environment"))

    distinct_methods = tuple(dict.fromkeys(method for method, _ in matched_methods))
    if len(distinct_methods) > 1:
        return InstallContext(
            install_method="unknown",
            package_manager="unknown",
            executable_path=snapshot.executable_path,
            python_executable=snapshot.python_executable,
            detected_with=tuple(reason for _, reason in matched_methods),
            is_ambiguous=True,
        )
    if distinct_methods:
        detected_method = distinct_methods[0]
        return InstallContext(
            install_method=detected_method,
            package_manager=detected_method,
            executable_path=snapshot.executable_path,
            python_executable=snapshot.python_executable,
            detected_with=tuple(reason for _, reason in matched_methods),
        )
    return InstallContext(
        install_method="unknown",
        package_manager="unknown",
        executable_path=snapshot.executable_path,
        python_executable=snapshot.python_executable,
    )


def get_system_info(
    snapshot: RuntimeSnapshot | None = None,
    *,
    command_resolver: CommandResolver | None = None,
) -> SystemInfo:
    """Build the shared Tier 1 system introspection payload.

    Args:
        snapshot: Optional injected runtime facts for deterministic tests.
        command_resolver: Optional executable lookup helper. Defaults to shutil.which.

    Returns:
        SystemInfo: Structured version, install, and health information.
    """

    runtime_snapshot = snapshot or get_runtime_snapshot()
    install_context = detect_install_context(runtime_snapshot)
    resolver = command_resolver or shutil.which
    health_signals = _build_health_signals(install_context, resolver)
    return SystemInfo(
        package_name=runtime_snapshot.package_name,
        version=runtime_snapshot.version,
        install_context=install_context,
        health_signals=health_signals,
    )


def _looks_like_pipx_install(
    *,
    executable_path: str,
    python_path: str,
    environment: Mapping[str, str],
) -> bool:
    return (
        "/pipx/venvs/" in executable_path
        or "/pipx/venvs/" in python_path
        or "PIPX_HOME" in environment
        or "PIPX_BIN_DIR" in environment
    )


def _looks_like_uv_install(
    *,
    executable_path: str,
    python_path: str,
    environment: Mapping[str, str],
) -> bool:
    return (
        "/uv/tools/" in executable_path
        or "/uv/tools/" in python_path
        or "UV_TOOL_BIN_DIR" in environment
        or "UV_TOOL_DIR" in environment
        or "UV_ACTIVE" in environment
    )


def _looks_like_pip_install(
    *,
    executable_path: str,
    python_path: str,
    environment: Mapping[str, str],
) -> bool:
    if not executable_path or not python_path:
        return False

    executable_parent = Path(executable_path).parent
    python_parent = Path(python_path).parent
    if executable_parent == python_parent and executable_parent.name in {"bin", "scripts"}:
        return True

    virtual_env = environment.get("VIRTUAL_ENV", "").lower().rstrip("/\\")
    if not virtual_env:
        return False

    expected_bin_dirs = {
        Path(virtual_env) / "bin",
        Path(virtual_env) / "scripts",
    }
    return executable_parent in expected_bin_dirs and python_parent in expected_bin_dirs


def _build_health_signals(
    install_context: InstallContext,
    command_resolver: CommandResolver,
) -> tuple[HealthSignal, ...]:
    python_signal = HealthSignal(
        name="python-executable",
        status="pass" if install_context.python_executable else "fail",
        summary=(
            "Python interpreter detected."
            if install_context.python_executable
            else "Python interpreter is unavailable."
        ),
    )

    detection_signal = _build_detection_signal(install_context)
    package_manager_signal = _build_package_manager_signal(install_context, command_resolver)
    return (python_signal, detection_signal, package_manager_signal)


def _build_detection_signal(install_context: InstallContext) -> HealthSignal:
    if install_context.is_ambiguous:
        return HealthSignal(
            name="install-detection",
            status="warn",
            summary="Install markers conflict; use manual upgrade guidance.",
        )
    if install_context.install_method == "unknown":
        return HealthSignal(
            name="install-detection",
            status="warn",
            summary="Install method could not be determined.",
        )
    return HealthSignal(
        name="install-detection",
        status="pass",
        summary=f"Detected {install_context.install_method} install method.",
    )


def _build_package_manager_signal(
    install_context: InstallContext,
    command_resolver: CommandResolver,
) -> HealthSignal:
    install_method = install_context.install_method
    if install_method == "pip":
        return HealthSignal(
            name="package-manager",
            status="pass" if install_context.python_executable else "fail",
            summary=(
                "Python can invoke pip via -m pip."
                if install_context.python_executable
                else "Python interpreter is unavailable for pip upgrades."
            ),
        )
    if install_method in {"uv", "pipx"}:
        available = command_resolver(install_method) is not None
        return HealthSignal(
            name="package-manager",
            status="pass" if available else "warn",
            summary=(
                f"{install_method} executable is available."
                if available
                else f"{install_method} executable is not available on PATH."
            ),
        )
    return HealthSignal(
        name="package-manager",
        status="warn",
        summary="Package manager is unknown; self-upgrade should stay manual.",
    )
