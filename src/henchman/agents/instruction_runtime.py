"""Connect conversation-local instruction refresh to delegation and session evidence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.config.context import ContextSnapshot
from henchman.core.agent import Agent
from henchman.core.instruction_context import InstructionContext
from henchman.core.instruction_provenance import InstructionProvenanceService

if TYPE_CHECKING:
    from henchman.agents.orchestrator import Orchestrator
    from henchman.cli.session_manager import ReplSessionManager


def bind_instruction_runtime(
    orchestrator: Orchestrator, sessions: ReplSessionManager,
    snapshot: ContextSnapshot | None,
) -> None:
    """Bind the primary conversation and lazy specialists to the loaded context."""
    if not isinstance(snapshot, ContextSnapshot) or not isinstance(orchestrator.tech_lead, Agent):
        return

    def capture(updated: ContextSnapshot) -> None:
        if sessions.session is not None:
            InstructionProvenanceService().capture(sessions.session, updated)

    def primary_updated(updated: ContextSnapshot) -> None:
        capture(updated)
        orchestrator.instruction_snapshot = updated
        orchestrator.delegation_runner.instruction_snapshot = updated
        orchestrator.pool.instruction_snapshot = updated
        sessions.instruction_snapshot = updated

    orchestrator.pool.instruction_snapshot = snapshot
    orchestrator.pool.instruction_observer = capture
    InstructionContext.attach(orchestrator.tech_lead, snapshot, primary_updated)
