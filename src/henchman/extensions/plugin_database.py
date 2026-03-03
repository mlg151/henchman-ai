"""Database operations for plugin management."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import ValidationError

from henchman.extensions.constants import PluginConstants
from henchman.extensions.models import PluginInstallation, PluginMetadata

if TYPE_CHECKING:
    from pathlib import Path


class PluginDatabase:
    """Database operations for plugin installations.

    This class handles all SQLite database operations for tracking
    installed plugins, their metadata, and installation status.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize plugin database.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path

    async def initialize(self) -> None:
        """Initialize the plugin database.

        Creates necessary tables and indexes if they don't exist.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()

            # Create installations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plugin_installations (
                    name TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    installed_at TEXT NOT NULL,
                    installed_version TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    installation_path TEXT,
                    last_used TEXT
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_installed_at ON plugin_installations(installed_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_enabled ON plugin_installations(enabled)")

            conn.commit()
        finally:
            conn.close()

    async def load_installations(self) -> dict[str, PluginInstallation]:
        """Load all installed plugins from database.

        Returns:
            Dictionary mapping plugin names to installation records.
        """
        installations: dict[str, PluginInstallation] = {}
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM plugin_installations")

            for row in cursor.fetchall():
                try:
                    installation = self._row_to_installation(row)
                    installations[installation.metadata.name] = installation
                except (json.JSONDecodeError, ValidationError) as e:
                    # Log warning but continue loading other plugins
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning("Failed to load plugin installation from database: %s", e)
        finally:
            conn.close()

        return installations

    def _row_to_installation(self, row: tuple) -> PluginInstallation:
        """Convert database row to PluginInstallation object.

        Args:
            row: Database row tuple.

        Returns:
            PluginInstallation object.

        Raises:
            json.JSONDecodeError: If metadata JSON is invalid.
            ValidationError: If metadata validation fails.
        """
        metadata_json = row[PluginConstants.DB_COL_METADATA_JSON]
        metadata_dict = json.loads(metadata_json)
        metadata = PluginMetadata(**metadata_dict)

        return PluginInstallation(
            metadata=metadata,
            installed_at=datetime.fromisoformat(row[PluginConstants.DB_COL_INSTALLED_AT]),
            installed_version=row[PluginConstants.DB_COL_INSTALLED_VERSION],
            enabled=bool(row[PluginConstants.DB_COL_ENABLED]),
            installation_path=row[PluginConstants.DB_COL_INSTALLATION_PATH],
            last_used=datetime.fromisoformat(row[PluginConstants.DB_COL_LAST_USED]) if row[PluginConstants.DB_COL_LAST_USED] else None,
        )

    async def save_installation(self, installation: PluginInstallation) -> None:
        """Save plugin installation to database.

        Args:
            installation: Plugin installation record.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            params = self._build_installation_params(installation)
            cursor.execute("""
                INSERT OR REPLACE INTO plugin_installations
                (name, metadata_json, installed_at, installed_version, enabled, installation_path, last_used)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, params)
            conn.commit()
        finally:
            conn.close()

    def _build_installation_params(self, installation: PluginInstallation) -> tuple:
        """Build database parameters for plugin installation.

        Args:
            installation: Plugin installation record.

        Returns:
            Tuple of parameters for database insertion.
        """
        metadata_json = installation.metadata.model_dump_json()
        return (
            installation.metadata.name,
            metadata_json,
            installation.installed_at.isoformat(),
            installation.installed_version,
            int(installation.enabled),
            installation.installation_path,
            installation.last_used.isoformat() if installation.last_used else None,
        )

    async def delete_installation(self, plugin_name: str) -> None:
        """Delete plugin installation from database.

        Args:
            plugin_name: Name of plugin to delete.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM plugin_installations WHERE name = ?", (plugin_name,))
            conn.commit()
        finally:
            conn.close()
