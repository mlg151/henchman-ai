"""File-based settings sync helpers for Tier 8."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from henchman.config.repository import SettingsRepository, SettingsScope


class SettingsSyncBackend:
    """Wrap existing settings import/export for Tier 8 sync workflows."""

    def export_project_settings(self, *, project_root: Path) -> dict[str, Any]:
        """Export project-local settings.

        Args:
            project_root: Project root whose canonical ``.henchman`` settings are read.

        Returns:
            Exported settings payload.
        """
        repository = SettingsRepository(project_root=project_root)
        return repository.export_settings(scope=SettingsScope.PROJECT)

    def import_project_settings(self, *, project_root: Path, payload: Mapping[str, Any]) -> None:
        """Import project-local settings from a file-backed payload.

        Args:
            project_root: Project root whose canonical ``.henchman`` settings are written.
            payload: Previously exported settings payload.
        """
        repository = SettingsRepository(project_root=project_root)
        repository.import_settings(payload, scope=SettingsScope.PROJECT)
