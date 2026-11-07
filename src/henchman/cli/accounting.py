"""Bind shared CLI session ownership to task accounting."""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.agents.orchestrator import Orchestrator
from henchman.core.session_operations import SessionRunOperations
from henchman.core.session_run_accounting import SessionRunAccounting

if TYPE_CHECKING:
    from henchman.cli.session_manager import ReplSessionManager
    from henchman.core.session_data import Session


def bind_session_accounting(orchestrator: Orchestrator, sessions: ReplSessionManager) -> None:
    """Use the same controller for interactive, Textual and headless CLI turns."""
    if not isinstance(orchestrator, Orchestrator):
        return

    def save(session: Session) -> None:
        sessions.session_manager.save(session)

    orchestrator.accounting_runtime = SessionRunAccounting(
        orchestrator.settings, lambda: sessions.current, save,
        sessions.session_manager.data_dir.parent / "ops.db",
    )
    orchestrator.operation_runtime = SessionRunOperations(
        orchestrator.settings, lambda: sessions.current, save,
        sessions.session_manager.data_dir.parent / "ops.db",
    )
