"""SQLite-backed storage for Tier 8 infrastructure services."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _utcnow() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(tz=UTC).isoformat()


class OpsStore:
    """Persist Tier 8 operational data in a small SQLite database."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the operations store.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection with dictionary-like rows."""
        connection = sqlite3.connect(self._db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        """Create the tables required by Tier 8 services."""
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS schema_versions (
                    namespace TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS remote_sessions (
                    session_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS remote_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ops_events (
                    event_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feature_flags (
                    name TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_requests (
                    state TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def put_state(self, key: str, value: Any) -> None:
        """Persist an app-state value.

        Args:
            key: Dotted state key.
            value: JSON-serializable value to store.
        """
        updated_at = _utcnow()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO app_state(key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value), updated_at),
            )

    def get_state(self, key: str, default: Any | None = None) -> Any | None:
        """Load one app-state value.

        Args:
            key: Dotted state key.
            default: Value returned when the key is missing.

        Returns:
            The stored value or the provided default.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM app_state WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        return json.loads(str(row["value_json"]))

    def select_state(self, prefix: str | None = None) -> dict[str, Any]:
        """Select all app-state entries, optionally filtered by prefix.

        Args:
            prefix: Optional key prefix such as ``ui.``.

        Returns:
            Mapping of keys to stored values.
        """
        query = "SELECT key, value_json FROM app_state"
        parameters: tuple[str, ...] = ()
        if prefix:
            query += " WHERE key LIKE ?"
            parameters = (f"{prefix}%",)
        query += " ORDER BY key"

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return {str(row["key"]): json.loads(str(row["value_json"])) for row in rows}

    def get_schema_version(self, namespace: str) -> int:
        """Return the stored schema version for a namespace.

        Args:
            namespace: Logical schema namespace.

        Returns:
            Current schema version, defaulting to ``0``.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT version FROM schema_versions WHERE namespace = ?",
                (namespace,),
            ).fetchone()
        if row is None:
            return 0
        return int(row["version"])

    def set_schema_version(self, namespace: str, version: int) -> None:
        """Persist the schema version for a namespace.

        Args:
            namespace: Logical schema namespace.
            version: Applied version number.
        """
        updated_at = _utcnow()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO schema_versions(namespace, version, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(namespace) DO UPDATE SET
                    version = excluded.version,
                    updated_at = excluded.updated_at
                """,
                (namespace, version, updated_at),
            )

    def upsert_remote_session(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Insert or update a remote session record.

        Args:
            session_id: Remote session identifier.
            payload: Session data to persist.

        Returns:
            The normalized session payload after persistence.
        """
        existing = self.get_remote_session(session_id) or {}
        created_at = str(payload.get("created_at") or existing.get("created_at") or _utcnow())
        updated_at = str(payload.get("updated_at") or _utcnow())
        normalized = {
            **existing,
            **payload,
            "session_id": session_id,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO remote_sessions(session_id, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (session_id, json.dumps(normalized), created_at, updated_at),
            )
        return normalized

    def get_remote_session(self, session_id: str) -> dict[str, Any] | None:
        """Load a persisted remote session.

        Args:
            session_id: Remote session identifier.

        Returns:
            Stored session payload or ``None`` when missing.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM remote_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        return payload if isinstance(payload, dict) else None

    def list_remote_sessions(self) -> list[dict[str, Any]]:
        """List all remote sessions in creation order."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM remote_sessions ORDER BY created_at ASC",
            ).fetchall()
        sessions: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(str(row["payload_json"]))
            if isinstance(payload, dict):
                sessions.append(payload)
        return sessions

    def append_remote_event(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Append an event to a remote session.

        Args:
            session_id: Remote session identifier.
            payload: Event payload to persist.

        Returns:
            The normalized event payload after persistence.
        """
        created_at = str(payload.get("created_at") or _utcnow())
        event_id = str(payload.get("event_id") or uuid4().hex)
        normalized = {
            **payload,
            "event_id": event_id,
            "session_id": session_id,
            "created_at": created_at,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO remote_events(event_id, session_id, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, session_id, json.dumps(normalized), created_at),
            )
        return normalized

    def list_remote_events(self, session_id: str) -> list[dict[str, Any]]:
        """List all events for one remote session.

        Args:
            session_id: Remote session identifier.

        Returns:
            Persisted event payloads in chronological order.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM remote_events
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,),
            ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            payload = json.loads(str(row["payload_json"]))
            if isinstance(payload, dict):
                events.append(payload)
        return events

    def record_ops_event(
        self,
        *,
        category: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist a structured operational event.

        Args:
            category: Event category such as ``analytics``.
            event_type: Specific event name.
            payload: JSON-serializable event details.

        Returns:
            Normalized event record.
        """
        created_at = _utcnow()
        event_id = uuid4().hex
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO ops_events(event_id, category, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (event_id, category, event_type, json.dumps(payload), created_at),
            )
        return {
            "event_id": event_id,
            "category": category,
            "event_type": event_type,
            "payload": payload,
            "created_at": created_at,
        }

    def list_ops_events(self, category: str | None = None) -> list[dict[str, Any]]:
        """List stored operational events.

        Args:
            category: Optional category filter.

        Returns:
            Event records in chronological order.
        """
        query = "SELECT event_id, category, event_type, payload_json, created_at FROM ops_events"
        parameters: tuple[str, ...] = ()
        if category:
            query += " WHERE category = ?"
            parameters = (category,)
        query += " ORDER BY created_at ASC"

        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            {
                "event_id": str(row["event_id"]),
                "category": str(row["category"]),
                "event_type": str(row["event_type"]),
                "payload": json.loads(str(row["payload_json"])),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def set_feature_flag(self, name: str, enabled: bool, *, source: str) -> None:
        """Persist a feature flag override.

        Args:
            name: Canonical feature flag name.
            enabled: Whether the flag is enabled.
            source: Source label such as ``runtime`` or ``config``.
        """
        updated_at = _utcnow()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO feature_flags(name, enabled, source, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    enabled = excluded.enabled,
                    source = excluded.source,
                    updated_at = excluded.updated_at
                """,
                (name, int(enabled), source, updated_at),
            )

    def get_feature_flag(self, name: str) -> dict[str, Any] | None:
        """Load a feature flag override.

        Args:
            name: Canonical feature flag name.

        Returns:
            Stored flag metadata or ``None``.
        """
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT name, enabled, source, updated_at
                FROM feature_flags
                WHERE name = ?
                """,
                (name,),
            ).fetchone()
        if row is None:
            return None
        return {
            "name": str(row["name"]),
            "enabled": bool(row["enabled"]),
            "source": str(row["source"]),
            "updated_at": str(row["updated_at"]),
        }

    def put_oauth_request(self, state: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist an OAuth authorization request payload.

        Args:
            state: OAuth state token.
            payload: Request or token exchange payload.

        Returns:
            Normalized payload after persistence.
        """
        existing = self.get_oauth_request(state) or {}
        created_at = str(payload.get("created_at") or existing.get("created_at") or _utcnow())
        updated_at = str(payload.get("updated_at") or _utcnow())
        normalized = {
            **existing,
            **payload,
            "state": state,
            "created_at": created_at,
            "updated_at": updated_at,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO oauth_requests(state, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(state) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (state, json.dumps(normalized), created_at, updated_at),
            )
        return normalized

    def get_oauth_request(self, state: str) -> dict[str, Any] | None:
        """Load a persisted OAuth authorization request.

        Args:
            state: OAuth state token.

        Returns:
            Stored request payload or ``None``.
        """
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM oauth_requests WHERE state = ?",
                (state,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        return payload if isinstance(payload, dict) else None
