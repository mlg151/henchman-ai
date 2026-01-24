"""Session management for conversation persistence.

This module provides session data models and the SessionManager
for saving and restoring conversation history.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionMessage:
    """A message in a session.

    Attributes:
        role: The role (user, assistant, tool, system).
        content: The message content.
        tool_calls: Tool calls made by the assistant.
        tool_call_id: ID of the tool call this message responds to.
    """

    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        data: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            data["content"] = self.content
        if self.tool_calls is not None:
            data["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            data["tool_call_id"] = self.tool_call_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMessage:
        """Create from dictionary.

        Args:
            data: Dictionary with message data.

        Returns:
            SessionMessage instance.
        """
        return cls(
            role=data["role"],
            content=data.get("content"),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
        )


@dataclass
class SessionMetadata:
    """Metadata about a session (without messages).

    Attributes:
        id: Unique session identifier.
        tag: Optional human-readable tag.
        project_hash: Hash identifying the project.
        started: ISO timestamp when session started.
        last_updated: ISO timestamp of last update.
        message_count: Number of messages in session.
    """

    id: str
    project_hash: str
    started: str
    last_updated: str
    message_count: int
    tag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "tag": self.tag,
            "project_hash": self.project_hash,
            "started": self.started,
            "last_updated": self.last_updated,
            "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMetadata:
        """Create from dictionary.

        Args:
            data: Dictionary with metadata.

        Returns:
            SessionMetadata instance.
        """
        return cls(
            id=data["id"],
            tag=data.get("tag"),
            project_hash=data["project_hash"],
            started=data["started"],
            last_updated=data["last_updated"],
            message_count=data["message_count"],
        )


@dataclass
class Session:
    """A conversation session.

    Attributes:
        id: Unique session identifier.
        project_hash: Hash identifying the project.
        started: ISO timestamp when session started.
        last_updated: ISO timestamp of last update.
        messages: List of session messages.
        tag: Optional human-readable tag.
    """

    id: str
    project_hash: str
    started: str
    last_updated: str
    messages: list[SessionMessage] = field(default_factory=list)
    tag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "tag": self.tag,
            "project_hash": self.project_hash,
            "started": self.started,
            "last_updated": self.last_updated,
            "messages": [msg.to_dict() for msg in self.messages],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """Create from dictionary.

        Args:
            data: Dictionary with session data.

        Returns:
            Session instance.
        """
        return cls(
            id=data["id"],
            tag=data.get("tag"),
            project_hash=data["project_hash"],
            started=data["started"],
            last_updated=data["last_updated"],
            messages=[SessionMessage.from_dict(m) for m in data.get("messages", [])],
        )

    def to_json(self) -> str:
        """Serialize to JSON string.

        Returns:
            JSON string.
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> Session:
        """Deserialize from JSON string.

        Args:
            json_str: JSON string.

        Returns:
            Session instance.
        """
        return cls.from_dict(json.loads(json_str))

    def get_metadata(self) -> SessionMetadata:
        """Get session metadata.

        Returns:
            SessionMetadata for this session.
        """
        return SessionMetadata(
            id=self.id,
            tag=self.tag,
            project_hash=self.project_hash,
            started=self.started,
            last_updated=self.last_updated,
            message_count=len(self.messages),
        )


class SessionManager:
    """Manages session persistence and retrieval.

    Attributes:
        data_dir: Directory for storing session files.
        current: The currently active session.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize the session manager.

        Args:
            data_dir: Directory for session files. Defaults to ~/.henchman/sessions.
        """
        self.data_dir = data_dir or (Path.home() / ".henchman" / "sessions")
        self._current: Session | None = None

    @property
    def current(self) -> Session | None:
        """Get the current session."""
        return self._current

    def set_current(self, session: Session) -> None:
        """Set the current session.

        Args:
            session: Session to set as current.
        """
        self._current = session

    def clear_current(self) -> None:
        """Clear the current session."""
        self._current = None

    def _now_iso(self) -> str:
        """Get current time as ISO string."""
        return datetime.now(UTC).isoformat()

    def _generate_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def create_session(
        self,
        project_hash: str,
        tag: str | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            project_hash: Hash identifying the project.
            tag: Optional human-readable tag.

        Returns:
            New Session instance.
        """
        now = self._now_iso()
        return Session(
            id=self._generate_id(),
            project_hash=project_hash,
            started=now,
            last_updated=now,
            messages=[],
            tag=tag,
        )

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.data_dir / f"{session_id}.json"

    def save(self, session: Session) -> Path:
        """Save a session to disk.

        Args:
            session: Session to save.

        Returns:
            Path to saved file.
        """
        # Update last_updated timestamp
        session.last_updated = self._now_iso()

        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        path = self._get_session_path(session.id)
        path.write_text(session.to_json())
        return path

    def load(self, session_id: str) -> Session:
        """Load a session from disk.

        Args:
            session_id: ID of session to load.

        Returns:
            Loaded Session instance.

        Raises:
            FileNotFoundError: If session doesn't exist.
        """
        path = self._get_session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        return Session.from_json(path.read_text())

    def load_by_tag(
        self,
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

    def list_sessions(
        self,
        project_hash: str | None = None,
    ) -> list[SessionMetadata]:
        """List saved sessions.

        Args:
            project_hash: Optional project hash to filter by.

        Returns:
            List of session metadata.
        """
        if not self.data_dir.exists():
            return []

        sessions: list[SessionMetadata] = []
        for path in self.data_dir.glob("*.json"):
            try:
                session = Session.from_json(path.read_text())
                if project_hash is None or session.project_hash == project_hash:
                    sessions.append(session.get_metadata())
            except (json.JSONDecodeError, KeyError):
                # Skip invalid session files
                continue

        # Sort by last_updated, most recent first
        sessions.sort(key=lambda s: s.last_updated, reverse=True)
        return sessions

    def delete(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: ID of session to delete.

        Raises:
            FileNotFoundError: If session doesn't exist.
        """
        path = self._get_session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        path.unlink()

    def compute_project_hash(self, directory: Path) -> str:
        """Compute a hash for a project directory.

        Args:
            directory: Project directory.

        Returns:
            Hash string identifying the project.
        """
        # Use absolute path for consistency
        abs_path = directory.resolve()
        return hashlib.sha256(str(abs_path).encode()).hexdigest()[:16]
