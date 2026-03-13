"""Merge logic for combining multiple sessions.

Provides strategy-based session merging: union, intersection, and
smart (deduplicated union).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .session_data import Session, SessionMessage
    from .session_models import TurnSummaryRecord

# Minimum number of sessions required for a merge operation.
_MIN_SESSIONS_FOR_MERGE = 2

_VALID_STRATEGIES = ("union", "intersection", "smart")


# ---------------------------------------------------------------------------
# Merge strategy helpers
# ---------------------------------------------------------------------------


def _message_hash(msg: SessionMessage) -> str:
    """Compute a content hash for deduplication."""
    raw = f"{msg.role}:{msg.content}:{msg.tool_calls!s}"
    return hashlib.md5(raw.encode()).hexdigest()


def _merge_union(sessions: list[Session]) -> list[SessionMessage]:
    """Union strategy: combine all messages from all sessions."""
    result: list[SessionMessage] = []
    for session in sessions:
        result.extend(session.messages)
    return result


def _merge_intersection(sessions: list[Session]) -> list[SessionMessage]:
    """Intersection strategy: keep only messages common to all sessions."""
    if not sessions:
        return []
    hash_sets = [{_message_hash(m) for m in s.messages} for s in sessions]
    common = set.intersection(*hash_sets)
    return [m for m in sessions[0].messages if _message_hash(m) in common]


def _merge_smart(sessions: list[Session]) -> list[SessionMessage]:
    """Smart strategy: deduplicated union preserving order."""
    seen: set[str] = set()
    result: list[SessionMessage] = []
    for session in sessions:
        for msg in session.messages:
            h = _message_hash(msg)
            if h not in seen:
                seen.add(h)
                result.append(msg)
    return result


_STRATEGY_MAP = {
    "union": _merge_union,
    "intersection": _merge_intersection,
    "smart": _merge_smart,
}


# ---------------------------------------------------------------------------
# Metadata merging
# ---------------------------------------------------------------------------


def _merge_metadata(
    merged: Session,
    sessions: list[Session],
    session_ids: list[str],
    strategy: str,
    now: str,
) -> None:
    """Merge turn summaries, agents, logs, and export metadata."""
    all_summaries: list[TurnSummaryRecord] = []
    all_agents: list[str] = []
    all_logs: list[dict[str, Any]] = []
    for session in sessions:
        all_summaries.extend(session.turn_summaries)
        all_agents.extend(session.active_agents)
        all_logs.extend(session.delegation_log)
    merged.turn_summaries = list(dict.fromkeys(all_summaries))
    merged.active_agents = list(dict.fromkeys(all_agents))
    merged.delegation_log = all_logs
    merged.export_metadata = {
        "merged_from": session_ids,
        "merge_strategy": strategy,
        "merge_timestamp": now,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def merge_sessions(
    sessions: list[Session],
    session_ids: list[str],
    strategy: str,
    merged: Session,
    now: str,
) -> None:
    """Merge multiple sessions into *merged* using the given strategy.

    Args:
        sessions: Loaded session objects to merge.
        session_ids: Original session IDs (for metadata).
        strategy: One of ``"union"``, ``"intersection"``, or ``"smart"``.
        merged: Pre-created target session to populate.
        now: ISO timestamp for metadata.

    Raises:
        ValueError: If fewer than 2 sessions or invalid strategy.

    Returns:
        None
    """
    if len(session_ids) < _MIN_SESSIONS_FOR_MERGE:
        msg = "At least 2 sessions required for merging"
        raise ValueError(msg)
    if strategy not in _VALID_STRATEGIES:
        msg = f"Invalid merge strategy: {strategy}"
        raise ValueError(msg)

    project_hash = sessions[0].project_hash
    for session in sessions[1:]:
        if session.project_hash != project_hash:
            msg = "Cannot merge sessions from different projects"
            raise ValueError(msg)

    merged.messages = _STRATEGY_MAP[strategy](sessions)
    _merge_metadata(merged, sessions, session_ids, strategy, now)
