"""Base class for session management.

Provides core CRUD operations used by :class:`SessionManager`
in :mod:`session_manager`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .session_data import Session, session_from_json
from .session_helpers import (
    _generate_id,
    _now_iso,
    _persist_session,
    _try_load_metadata,
    compute_project_hash,
)

if TYPE_CHECKING:
    from .session_models import SessionMetadata


# ---------------------------------------------------------------------------
# Base session manager
# ---------------------------------------------------------------------------


class _SessionManagerBase:
    """Base class providing core CRUD session operations.

    Attributes:
        data_dir: Directory for storing session files.
    """

    def __init__(
        self: _SessionManagerBase,
        data_dir: Path | None = None,
    ) -> None:
        """Initialise the session manager.

        Args:
            data_dir: Directory for session files.
                Defaults to ``~/.henchman/sessions``.
        """
        self.data_dir = data_dir or (Path.home() / ".henchman" / "sessions")
        self._current: Session | None = None

    # ------------------------------------------------------------------
    # Current session tracking
    # ------------------------------------------------------------------

    @property
    def current(self: _SessionManagerBase) -> Session | None:
        """Get the current session."""
        return self._current

    def set_current(self: _SessionManagerBase, session: Session) -> None:
        """Set the current session."""
        self._current = session

    def clear_current(self: _SessionManagerBase) -> None:
        """Clear the current session."""
        self._current = None

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def _get_session_path(
        self: _SessionManagerBase,
        session_id: str,
    ) -> Path:
        """Get the file path for a session."""
        return self.data_dir / f"{session_id}.json"

    def create_session(
        self: _SessionManagerBase,
        project_hash: str,
        tag: str | None = None,
    ) -> Session:
        """Create a new empty session.

        Args:
            project_hash: Hash identifying the project.
            tag: Optional human-readable tag.

        Returns:
            New Session instance.
        """
        now = _now_iso()
        return Session(
            id=_generate_id(),
            project_hash=project_hash,
            started=now,
            last_updated=now,
            messages=[],
            tag=tag,
        )

    def save(self: _SessionManagerBase, session: Session) -> Path:
        """Save a session to disk.

        Args:
            session: Session to save.

        Returns:
            Path to saved file.
        """
        return _persist_session(self.data_dir, session)

    # ------------------------------------------------------------------
    # Load and lookup
    # ------------------------------------------------------------------

    def load(self: _SessionManagerBase, session_id: str) -> Session:
        """Load a session from disk.

        Args:
            session_id: ID or ID prefix of session to load.

        Returns:
            Loaded Session instance.

        Raises:
            FileNotFoundError: If session doesn't exist.
            ValueError: If session ID prefix is ambiguous.
        """
        path = self._get_session_path(session_id)
        if path.exists():
            return session_from_json(path.read_text())
        if not self.data_dir.exists():
            msg = f"Session not found: {session_id}"
            raise FileNotFoundError(msg)
        matches = list(self.data_dir.glob(f"{session_id}*.json"))
        if not matches:
            msg = f"Session not found: {session_id}"
            raise FileNotFoundError(msg)
        if len(matches) > 1:
            msg = f"Ambiguous session ID prefix: {session_id}"
            raise ValueError(msg)
        return session_from_json(matches[0].read_text())

    def load_by_tag(
        self: _SessionManagerBase,
        tag: str,
        project_hash: str | None = None,
    ) -> Session | None:
        """Load a session by tag.

        Args:
            tag: Tag to search for.
            project_hash: Optional project hash to filter by.

        Returns:
            Session if found, None otherwise.
        """
        for meta in self.list_sessions(project_hash):
            if meta.tag == tag:
                return self.load(meta.id)
        return None

    # ------------------------------------------------------------------
    # Listing and deletion
    # ------------------------------------------------------------------

    def list_sessions(
        self: _SessionManagerBase,
        project_hash: str | None = None,
    ) -> list[SessionMetadata]:
        """List saved sessions, most recent first.

        Args:
            project_hash: Optional project hash to filter by.

        Returns:
            List of session metadata.
        """
        if not self.data_dir.exists():
            return []
        loaded = [_try_load_metadata(p, project_hash) for p in self.data_dir.glob("*.json")]
        sessions: list[Any] = [m for m in loaded if m is not None]
        sessions.sort(key=lambda s: s.last_updated, reverse=True)
        return sessions

    def delete(self: _SessionManagerBase, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: ID of session to delete.

        Raises:
            FileNotFoundError: If session doesn't exist.
        """
        path = self._get_session_path(session_id)
        if not path.exists():
            msg = f"Session not found: {session_id}"
            raise FileNotFoundError(msg)
        path.unlink()

    def compute_project_hash(
        self: _SessionManagerBase,
        directory: Path,
    ) -> str:
        """Compute a hash for a project directory.

        Args:
            directory: Project directory.

        Returns:
            Hash string identifying the project.
        """
        return compute_project_hash(directory)
