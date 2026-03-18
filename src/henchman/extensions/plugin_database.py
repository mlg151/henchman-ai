"""Database operations for plugin management."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from henchman.extensions.constants import PluginConstants
from henchman.extensions.models import PluginInstallation, PluginMetadata

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_INSERT_SQL = """
    INSERT OR REPLACE INTO plugin_installations
    (name, metadata_json, installed_at, installed_version,
     enabled, installation_path, last_used)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""


# ---------------------------------------------------------------------------
# Module-level helpers (extracted to eliminate Feature Envy in class methods)
# ---------------------------------------------------------------------------


def _parse_row_to_installation(row: tuple[Any, ...]) -> PluginInstallation:
    """Convert a database row tuple to a PluginInstallation object.

    Raises:
        json.JSONDecodeError: If metadata JSON is invalid.
        ValidationError: If metadata validation fails.
    """
    PC = PluginConstants
    last_used_str = row[PC.DB_COL_LAST_USED]
    metadata = PluginMetadata(**json.loads(row[PC.DB_COL_METADATA_JSON]))
    return PluginInstallation(
        metadata=metadata,
        installed_at=datetime.fromisoformat(row[PC.DB_COL_INSTALLED_AT]),
        installed_version=row[PC.DB_COL_INSTALLED_VERSION],
        enabled=bool(row[PC.DB_COL_ENABLED]),
        installation_path=row[PC.DB_COL_INSTALLATION_PATH],
        last_used=datetime.fromisoformat(last_used_str) if last_used_str else None,
    )


def _try_parse_installation_row(row: tuple[Any, ...]) -> PluginInstallation | None:
    """Parse a database row, returning None and logging a warning on failure."""
    try:
        return _parse_row_to_installation(row)
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning("Failed to load plugin installation from database: %s", e)
        return None


def _build_installation_db_params(installation: PluginInstallation) -> tuple[Any, ...]:
    """Build the SQL parameters tuple for a PluginInstallation record."""
    metadata = installation.metadata
    last_used = installation.last_used
    return (
        metadata.name,
        metadata.model_dump_json(),
        installation.installed_at.isoformat(),
        installation.installed_version,
        int(installation.enabled),
        installation.installation_path,
        last_used.isoformat() if last_used else None,
    )


def _initialize_plugin_db(db_path: Path) -> None:
    """Create plugin_installations table and indexes if they don't exist."""
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
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
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_installed_at ON plugin_installations(installed_at)",
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_enabled ON plugin_installations(enabled)",
        )
        conn.commit()
    finally:
        conn.close()


def _save_installation_to_db(db_path: Path, installation: PluginInstallation) -> None:
    """Persist a plugin installation record to the database."""
    conn = sqlite3.connect(db_path)
    try:
        conn.cursor().execute(_INSERT_SQL, _build_installation_db_params(installation))
        conn.commit()
    finally:
        conn.close()


def _delete_installation_from_db(db_path: Path, plugin_name: str) -> None:
    """Remove a plugin installation record from the database."""
    conn = sqlite3.connect(db_path)
    try:
        conn.cursor().execute(
            "DELETE FROM plugin_installations WHERE name = ?",
            (plugin_name,),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public class - thin delegates to module-level helpers
# ---------------------------------------------------------------------------


class PluginDatabase:
    """Database operations for plugin installations.

    This class handles all SQLite database operations for tracking
    installed plugins, their metadata, and installation status.
    """

    def __init__(self: PluginDatabase, db_path: Path) -> None:
        """Initialize plugin database.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = db_path

    async def initialize(self: PluginDatabase) -> None:
        """Create necessary tables and indexes if they don't exist.

        Returns:
            None
        """
        _initialize_plugin_db(self.db_path)

    async def load_installations(self: PluginDatabase) -> dict[str, PluginInstallation]:
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
                installation = _try_parse_installation_row(row)
                if installation is not None:
                    installations[installation.metadata.name] = installation
        finally:
            conn.close()
        return installations

    async def save_installation(self: PluginDatabase, installation: PluginInstallation) -> None:
        """Save plugin installation to database.

        Args:
            installation: Plugin installation record.

        Returns:
            None
        """
        db_path = self.db_path
        _save_installation_to_db(db_path, installation)

    async def delete_installation(self: PluginDatabase, plugin_name: str) -> None:
        """Delete plugin installation from database.

        Args:
            plugin_name: Name of plugin to delete.

        Returns:
            None
        """
        _delete_installation_from_db(self.db_path, plugin_name)

    # One-liner delegates that preserve the private API
    def _row_to_installation(self: PluginDatabase, row: tuple[Any, ...]) -> PluginInstallation:
        return _parse_row_to_installation(row)

    def _build_installation_params(
        self: PluginDatabase,
        installation: PluginInstallation,
    ) -> tuple[Any, ...]:
        return _build_installation_db_params(installation)
