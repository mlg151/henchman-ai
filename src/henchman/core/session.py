"""Session management for conversation persistence.

Re-exports all public symbols so that existing imports like
``from henchman.core.session import Session`` continue to work.
"""

from __future__ import annotations

from .session_data import Session, session_from_dict, session_from_json
from .session_manager import SessionManager
from .session_models import (
    SessionMessage,
    SessionMetadata,
    TurnSummaryRecord,
    message_from_dict,
    metadata_from_dict,
    turn_summary_from_dict,
)

__all__ = [
    "Session",
    "SessionManager",
    "SessionMessage",
    "SessionMetadata",
    "TurnSummaryRecord",
    "message_from_dict",
    "metadata_from_dict",
    "session_from_dict",
    "session_from_json",
    "turn_summary_from_dict",
]

