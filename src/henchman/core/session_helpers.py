"""Shared helper functions for session management.

Provides utility functions used by :mod:`session_manager_base` and
:mod:`session_manager` for ID generation, timestamps, persistence,
and project hashing.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .session_data import Session, session_from_json

if TYPE_CHECKING:
    from .session_models import SessionMetadata


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PROJECT_HASH_LENGTH = 16


# ---------------------------------------------------------------------------
# Timestamp and ID generation
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Get current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _generate_id() -> str:
    """Generate a unique session identifier."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Project hashing
# ---------------------------------------------------------------------------


def compute_project_hash(directory: Path) -> str:
    """Compute a deterministic hash for a project directory.

    Args:
        directory: Project directory.

    Returns:
        16-character hex hash string.
    """
    encoded = str(directory.resolve()).encode()
    return hashlib.sha256(encoded).hexdigest()[:_PROJECT_HASH_LENGTH]


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _persist_session(data_dir: Path, session: Session) -> Path:
    """Write *session* to disk, updating its ``last_updated`` timestamp.

    Args:
        data_dir: Directory for session files.
        session: Session to persist.

    Returns:
        Path to the written file.
    """
    session.last_updated = _now_iso()
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / f"{session.id}.json"
    path.write_text(session.to_json())
    return path


def _try_load_metadata(
    path: Path,
    project_hash: str | None,
) -> SessionMetadata | None:
    """Try to read session metadata from *path*.

    Returns:
        :class:`SessionMetadata` or ``None`` if the file is
        invalid or does not match *project_hash*.
    """
    try:
        session = session_from_json(path.read_text())
    except (json.JSONDecodeError, KeyError):
        return None
    if project_hash is not None and session.project_hash != project_hash:
        return None
    return session.get_metadata()
