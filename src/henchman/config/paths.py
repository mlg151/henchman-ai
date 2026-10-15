"""Path helpers for project-local config storage."""

from __future__ import annotations

from pathlib import Path

PROJECT_SETTINGS_DIRNAME = ".henchman"
_LEGACY_PROJECT_SETTINGS_DIRNAMES = (".hENCHMAN",)


def resolve_project_settings_path(project_root: Path | None = None) -> Path:
    """Return the canonical project-local settings directory.

    Args:
        project_root: Optional project root to resolve from. When omitted, the
            current working directory is used.

    Returns:
        The canonical ``.henchman`` directory path for the project.
    """

    return _resolve_project_root(project_root) / PROJECT_SETTINGS_DIRNAME


def resolve_legacy_project_settings_path(project_root: Path | None = None) -> Path | None:
    """Return an existing legacy project-local settings directory, if needed.

    Args:
        project_root: Optional project root to resolve from. When omitted, the
            current working directory is used.

    Returns:
        The first existing historical casing variant when the canonical
        ``.henchman`` directory is absent; otherwise ``None``.
    """

    resolved_project_root = _resolve_project_root(project_root)
    canonical_path = resolved_project_root / PROJECT_SETTINGS_DIRNAME
    if canonical_path.exists():
        return None

    for legacy_dirname in _LEGACY_PROJECT_SETTINGS_DIRNAMES:
        legacy_path = resolved_project_root / legacy_dirname
        if legacy_path.exists():
            return legacy_path

    return None


def _resolve_project_root(project_root: Path | None) -> Path:
    """Resolve the project root used by project-local settings helpers."""

    return (project_root or Path.cwd()).resolve()
