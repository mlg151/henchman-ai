"""Tests for sandboxed runtime plugin loading."""

from __future__ import annotations

from pathlib import Path

from henchman.extensions.sandbox import PluginSandbox


def _write(path: Path, content: str) -> None:
    """Write a file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_sandbox_blocks_unsafe_plugins(tmp_path: Path) -> None:
    """Sandboxed loading should flag plugins with blocked imports or calls."""

    plugins_dir = tmp_path / "unsafe"
    _write(
        plugins_dir / "extension.py",
        """import subprocess

class UnsafeExtension:
    pass
""",
    )

    sandbox = PluginSandbox(mode="docker")
    report = sandbox.scan_directory(plugins_dir)

    assert report.passed is False
    assert any("subprocess" in finding for finding in report.warnings)


def test_sandbox_loads_unsafe_plugins_without_sandbox(tmp_path: Path) -> None:
    """Unsandboxed scanning should allow unsafe plugins."""

    plugins_dir = tmp_path / "unsafe"
    _write(
        plugins_dir / "extension.py",
        """import subprocess

class UnsafeExtension:
    pass
""",
    )

    sandbox = PluginSandbox(mode="none")
    allowed, report = sandbox.allows_directory(plugins_dir)

    # In mode="none", allows_directory always returns True
    assert allowed is True
    # But the report still flags the unsafe import
    assert report.passed is False
    assert any("subprocess" in warning for warning in report.warnings)
