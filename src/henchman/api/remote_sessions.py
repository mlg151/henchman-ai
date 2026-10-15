"""Remote session management for Tier 8 API workflows."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import uuid4

from henchman.api.oauth import OAuthService
from henchman.ops.store import OpsStore


class RemoteSessionManager:
    """Create and track remote sessions backed by the shared ops store."""

    def __init__(
        self,
        *,
        store: OpsStore,
        oauth_service: OAuthService | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Initialize the remote session manager.

        Args:
            store: Shared operations store.
            oauth_service: Optional OAuth service instance.
            id_factory: Optional session ID factory for tests.
        """
        self._store = store
        self.oauth_service = oauth_service or OAuthService(store=store)
        self._id_factory = id_factory or (lambda: uuid4().hex)

    def create_session(self, *, client_id: str, title: str) -> dict[str, Any]:
        """Create and persist a new remote session.

        Args:
            client_id: Remote client identifier.
            title: Human-readable session title.

        Returns:
            Persisted session record.
        """
        session_id = self._id_factory()
        self._store.upsert_remote_session(
            session_id,
            {
                "session_id": session_id,
                "client_id": client_id,
                "title": title,
                "status": "active",
                "last_event": None,
            },
        )
        session = self.get_session(session_id)
        if session is None:
            msg = f"Failed to create session {session_id}"
            raise RuntimeError(msg)
        return session

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Load one remote session."""
        return self._store.get_remote_session(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all known remote sessions."""
        return self._store.list_remote_sessions()

    def publish_event(self, session_id: str, event: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist and return a remote session event.

        Args:
            session_id: Remote session identifier.
            event: Event name.
            payload: Event payload.

        Returns:
            Persisted event record.

        Raises:
            KeyError: If the session does not exist.
        """
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)

        event_record = self._store.append_remote_event(
            session_id,
            {
                "event": event,
                "payload": payload,
            },
        )
        session["last_event"] = event_record
        self._store.upsert_remote_session(session_id, session)
        return event_record

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        """List all persisted events for one session."""
        return self._store.list_remote_events(session_id)
