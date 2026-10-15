"""Tests for project-local config path resolution."""

from __future__ import annotations

from pathlib import Path

from henchman.config.paths import (
    resolve_legacy_project_settings_path,
    resolve_project_settings_path,
)


def test_resolve_project_settings_path_uses_canonical_directory(
    tmp_path: Path,
) -> None:
    """The canonical project settings directory should always be .henchman."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    assert resolve_project_settings_path(project_root) == project_root.resolve() / ".henchman"


def test_resolve_project_settings_path_defaults_to_current_working_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """The resolver should default to the current working directory."""
    monkeypatch.chdir(tmp_path)

    assert resolve_project_settings_path() == tmp_path.resolve() / ".henchman"


def test_resolve_legacy_project_settings_path_reads_historical_directory(
    tmp_path: Path,
) -> None:
    """The legacy resolver should return an existing historical casing directory."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    legacy_path = project_root / ".hENCHMAN"
    legacy_path.mkdir()

    assert resolve_legacy_project_settings_path(project_root) == legacy_path.resolve()


def test_resolve_legacy_project_settings_path_prefers_canonical_directory(
    tmp_path: Path,
) -> None:
    """Legacy fallback should be disabled once the canonical directory exists."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    (project_root / ".henchman").mkdir()
    (project_root / ".hENCHMAN").mkdir()

    assert resolve_legacy_project_settings_path(project_root) is None


def test_resolvers_do_not_create_project_directories(tmp_path: Path) -> None:
    """Path resolution should not create canonical or legacy directories."""
    project_root = tmp_path / "workspace"
    project_root.mkdir()

    resolve_project_settings_path(project_root)
    resolve_legacy_project_settings_path(project_root)

    assert not (project_root / ".henchman").exists()
    assert not (project_root / ".hENCHMAN").exists()
