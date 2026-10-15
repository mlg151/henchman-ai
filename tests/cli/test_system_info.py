"""Tests for Tier 1 system introspection helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.version import VERSION


def _make_snapshot(
    executable_path: Path,
    python_executable: Path,
    *,
    environment: dict[str, str] | None = None,
):
    from henchman.cli.system_info import RuntimeSnapshot

    return RuntimeSnapshot(
        executable_path=str(executable_path),
        python_executable=str(python_executable),
        environment=environment or {},
    )


def test_get_system_info_detects_pip_install(tmp_path: Path) -> None:
    """System introspection should classify regular virtualenv installs as pip."""
    from henchman.cli.system_info import get_system_info

    bin_dir = tmp_path / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    python_executable = bin_dir / "python"
    executable_path = bin_dir / "henchman"

    system_info = get_system_info(
        snapshot=_make_snapshot(executable_path, python_executable),
    )

    health = {signal.name: signal.status for signal in system_info.health_signals}

    assert system_info.version == VERSION
    assert system_info.package_name == "henchman-ai"
    assert system_info.install_context.install_method == "pip"
    assert system_info.install_context.package_manager == "pip"
    assert system_info.install_context.is_ambiguous is False
    assert health["install-detection"] == "pass"
    assert health["python-executable"] == "pass"
    assert health["package-manager"] == "pass"


def test_get_system_info_keeps_manual_install_unknown(tmp_path: Path) -> None:
    """Manual wrappers should stay unknown instead of defaulting to pip."""
    from henchman.cli.system_info import get_system_info
    from henchman.cli.update_check import build_update_plan

    executable_path = tmp_path / "henchman"
    python_executable = Path("/usr/bin/python3")

    system_info = get_system_info(
        snapshot=_make_snapshot(executable_path, python_executable),
    )
    update_plan = build_update_plan(system_info)

    assert system_info.install_context.install_method == "unknown"
    assert system_info.install_context.package_manager == "unknown"
    assert system_info.install_context.is_ambiguous is False
    assert update_plan.can_self_update is False
    assert update_plan.command == ()
    assert update_plan.failure_code == "HMN_UPGRADE_INSTALL_METHOD_UNKNOWN"
    assert "manual" in update_plan.summary.lower()


def test_get_system_info_detects_uv_install(tmp_path: Path) -> None:
    """System introspection should recognize uv-managed tool installs."""
    from henchman.cli.system_info import get_system_info

    tool_python = tmp_path / ".local" / "share" / "uv" / "tools" / "henchman-ai" / "bin" / "python"
    tool_python.parent.mkdir(parents=True)
    executable_path = tmp_path / ".local" / "bin" / "henchman"
    executable_path.parent.mkdir(parents=True, exist_ok=True)

    system_info = get_system_info(
        snapshot=_make_snapshot(
            executable_path,
            tool_python,
            environment={"UV_TOOL_BIN_DIR": str(executable_path.parent)},
        ),
        command_resolver=lambda command: f"/usr/bin/{command}" if command == "uv" else None,
    )

    health = {signal.name: signal.status for signal in system_info.health_signals}

    assert system_info.install_context.install_method == "uv"
    assert system_info.install_context.package_manager == "uv"
    assert system_info.install_context.is_ambiguous is False
    assert health["package-manager"] == "pass"


def test_get_system_info_detects_pipx_install(tmp_path: Path) -> None:
    """System introspection should recognize pipx-managed installs."""
    from henchman.cli.system_info import get_system_info

    pipx_root = tmp_path / ".local" / "pipx"
    python_executable = pipx_root / "venvs" / "henchman-ai" / "bin" / "python"
    python_executable.parent.mkdir(parents=True)
    executable_path = python_executable.parent / "henchman"

    system_info = get_system_info(
        snapshot=_make_snapshot(
            executable_path,
            python_executable,
            environment={"PIPX_HOME": str(pipx_root)},
        ),
        command_resolver=lambda command: f"/usr/bin/{command}" if command == "pipx" else None,
    )

    assert system_info.install_context.install_method == "pipx"
    assert system_info.install_context.package_manager == "pipx"
    assert system_info.install_context.is_ambiguous is False


def test_get_system_info_marks_ambiguous_install_detection(tmp_path: Path) -> None:
    """Conflicting markers should degrade to manual guidance instead of guessing."""
    from henchman.cli.system_info import get_system_info
    from henchman.cli.update_check import build_update_plan

    python_executable = tmp_path / ".local" / "share" / "uv" / "tools" / "henchman-ai" / "bin" / "python"
    python_executable.parent.mkdir(parents=True)
    executable_path = tmp_path / ".local" / "pipx" / "venvs" / "henchman-ai" / "bin" / "henchman"
    executable_path.parent.mkdir(parents=True)

    system_info = get_system_info(
        snapshot=_make_snapshot(
            executable_path,
            python_executable,
            environment={
                "PIPX_HOME": str(tmp_path / ".local" / "pipx"),
                "UV_TOOL_BIN_DIR": str(tmp_path / ".local" / "bin"),
            },
        ),
        command_resolver=lambda command: f"/usr/bin/{command}",
    )

    update_plan = build_update_plan(system_info)
    install_detection = next(
        signal for signal in system_info.health_signals if signal.name == "install-detection"
    )

    assert system_info.install_context.install_method == "unknown"
    assert system_info.install_context.package_manager == "unknown"
    assert system_info.install_context.is_ambiguous is True
    assert install_detection.status == "warn"
    assert update_plan.can_self_update is False
    assert update_plan.command == ()
    assert update_plan.failure_code == "HMN_UPGRADE_INSTALL_METHOD_UNKNOWN"
    assert "manual" in update_plan.summary.lower()


@pytest.mark.parametrize(
    ("install_method", "expected_command"),
    [
        ("pip", ("/workspace/.venv/bin/python", "-m", "pip", "install", "--upgrade", "henchman-ai")),
        ("uv", ("uv", "tool", "upgrade", "henchman-ai")),
        ("pipx", ("pipx", "upgrade", "henchman-ai")),
    ],
)
def test_build_update_plan_uses_manager_specific_commands(
    install_method: str,
    expected_command: tuple[str, ...],
) -> None:
    """Update plans should render deterministic commands for supported installs."""
    from henchman.cli.system_info import RuntimeSnapshot, get_system_info
    from henchman.cli.update_check import build_update_plan

    snapshot = RuntimeSnapshot(
        executable_path="/workspace/.venv/bin/henchman",
        python_executable="/workspace/.venv/bin/python",
        environment={},
    )
    if install_method == "uv":
        snapshot = RuntimeSnapshot(
            executable_path="/home/test/.local/bin/henchman",
            python_executable="/home/test/.local/share/uv/tools/henchman-ai/bin/python",
            environment={"UV_TOOL_BIN_DIR": "/home/test/.local/bin"},
        )
    if install_method == "pipx":
        snapshot = RuntimeSnapshot(
            executable_path="/home/test/.local/pipx/venvs/henchman-ai/bin/henchman",
            python_executable="/home/test/.local/pipx/venvs/henchman-ai/bin/python",
            environment={"PIPX_HOME": "/home/test/.local/pipx"},
        )

    system_info = get_system_info(
        snapshot=snapshot,
        command_resolver=lambda command: f"/usr/bin/{command}" if command != "pip" else None,
    )
    update_plan = build_update_plan(system_info)

    assert update_plan.can_self_update is True
    assert update_plan.command == expected_command
    assert update_plan.failure_code is None


def test_get_system_info_warns_when_wrapper_manager_is_missing(tmp_path: Path) -> None:
    """Health signals should surface when uv or pipx wrappers are unavailable."""
    from henchman.cli.system_info import get_system_info
    from henchman.cli.update_check import build_update_plan

    def _missing_command(_: str) -> str | None:
        return None

    tool_python = tmp_path / ".local" / "share" / "uv" / "tools" / "henchman-ai" / "bin" / "python"
    tool_python.parent.mkdir(parents=True)
    executable_path = tmp_path / ".local" / "bin" / "henchman"
    executable_path.parent.mkdir(parents=True, exist_ok=True)

    system_info = get_system_info(
        snapshot=_make_snapshot(
            executable_path,
            tool_python,
            environment={"UV_TOOL_BIN_DIR": str(executable_path.parent)},
        ),
        command_resolver=_missing_command,
    )

    package_manager_signal = next(
        signal for signal in system_info.health_signals if signal.name == "package-manager"
    )
    update_plan = build_update_plan(system_info)

    assert system_info.install_context.install_method == "uv"
    assert package_manager_signal.status == "warn"
    assert update_plan.can_self_update is False
    assert update_plan.command == ()
    assert update_plan.rendered_command == ""
    assert update_plan.failure_code is None
    assert "manual" in update_plan.summary.lower()
    assert "unavailable" in update_plan.summary.lower()


@pytest.mark.parametrize("separator", ["\\", "/", "mixed"])
@pytest.mark.parametrize("manager", ["uv", "pipx", "pip"])
def test_windows_install_paths_select_correct_upgrade_argv(manager: str, separator: str) -> None:
    """Manager markers work without environment hints and preserve executable argv."""
    from henchman.cli.system_info import RuntimeSnapshot, get_system_info
    from henchman.cli.update_check import build_update_plan

    roots = {
        "uv": "C:/Users/Test User/AppData/Roaming/UV/Tools/henchman-ai/Scripts",
        "pipx": "C:/Users/Test User/PIPX/Venvs/henchman-ai/Scripts",
        "pip": "C:/Workspace/Project Name/.venv/Scripts",
    }
    root = roots[manager]
    if separator == "mixed":
        root = root.replace("C:/Users/", "C:\\Users\\").replace("/Scripts", "\\Scripts")
    else:
        root = root.replace("/", separator)
    executable = f"{root}\\henchman.exe"
    python = f"{root}\\python.exe"
    info = get_system_info(
        snapshot=RuntimeSnapshot(executable_path=executable, python_executable=python),
        command_resolver=lambda command: f"C:\\Tools\\{command}.exe",
    )
    plan = build_update_plan(info)
    assert info.install_context.install_method == manager
    assert info.install_context.is_ambiguous is False
    assert info.install_context.python_executable == python
    assert info.install_context.executable_path == executable
    assert plan.can_self_update is True
    expected = {
        "uv": ("uv", "tool", "upgrade", "henchman-ai"),
        "pipx": ("pipx", "upgrade", "henchman-ai"),
        "pip": (python, "-m", "pip", "install", "--upgrade", "henchman-ai"),
    }
    assert plan.command == expected[manager]


def test_conflicting_windows_install_paths_require_manual_upgrade() -> None:
    """Mixed manager markers must stay ambiguous regardless of separator direction."""
    from henchman.cli.system_info import RuntimeSnapshot, get_system_info
    from henchman.cli.update_check import build_update_plan

    info = get_system_info(
        snapshot=RuntimeSnapshot(
            executable_path=r"C:\Users\Test\pipx\venvs\henchman-ai\Scripts\henchman.exe",
            python_executable=r"C:\Users\Test\uv\tools\henchman-ai\Scripts\python.exe",
        ),
        command_resolver=lambda command: f"C:\\Tools\\{command}.exe",
    )
    assert info.install_context.install_method == "unknown"
    assert info.install_context.is_ambiguous is True
    plan = build_update_plan(info)
    assert plan.can_self_update is False
    assert plan.command == ()
    assert plan.failure_code == "HMN_UPGRADE_INSTALL_METHOD_UNKNOWN"


@pytest.mark.parametrize("marker", ["uv\\tools", "pipx\\venvs"])
def test_windows_manager_missing_from_path_requires_manual_upgrade(marker: str) -> None:
    from henchman.cli.system_info import RuntimeSnapshot, get_system_info
    from henchman.cli.update_check import build_update_plan

    root = f"C:\\Users\\Test\\{marker}\\henchman-ai\\Scripts"
    info = get_system_info(
        snapshot=RuntimeSnapshot(
            executable_path=f"{root}\\henchman.exe", python_executable=f"{root}\\python.exe",
        ),
        command_resolver=lambda _: None,
    )
    plan = build_update_plan(info)
    assert info.install_context.install_method == marker.split("\\")[0]
    assert plan.can_self_update is False
    assert plan.command == ()
    assert "unavailable" in plan.summary.lower()
