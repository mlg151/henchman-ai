"""Session branching logic.

Provides a function to create a new session that diverges from
an existing session at a given message index.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session_data import Session


# ---------------------------------------------------------------------------
# Parameter object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _BranchMeta:
    """Grouped parameters for a branch operation."""

    new_id: str
    now: str
    tag: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def branch_session(
    parent: Session,
    branch_point: int,
    meta: _BranchMeta,
) -> Session:
    """Create a branched copy of *parent* up to *branch_point*.

    Args:
        parent: Session to branch from.
        branch_point: Message index (0-based) where the branch occurs.
        meta: Grouped parameters (new_id, now, tag).

    Returns:
        New Session that shares history up to *branch_point*.

    Raises:
        ValueError: If *branch_point* is out of range.
    """
    from .session_data import Session

    msg_count = len(parent.messages)
    if branch_point < 0 or branch_point > msg_count:
        msg = f"Branch point {branch_point} out of range (0-{msg_count})"
        raise ValueError(msg)

    return Session(
        id=meta.new_id,
        project_hash=parent.project_hash,
        started=meta.now,
        last_updated=meta.now,
        messages=parent.messages[:branch_point],
        tag=meta.tag,
        plan_mode=parent.plan_mode,
        turn_summaries=parent.turn_summaries[:],
        active_agents=parent.active_agents[:],
        delegation_log=parent.delegation_log[:],
        parent_id=parent.id,
        branch_point=branch_point,
        template_id=parent.template_id,
        template_parameters=parent.template_parameters.copy(),
        export_metadata=parent.export_metadata.copy(),
    )
