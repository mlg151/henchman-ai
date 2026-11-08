"""Bind one dynamic child conversation to staged file tools and parent review."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from henchman.advanced.checkpoint_models import ReviewResult
from henchman.agents.proposal_review import ParentProposalReview
from henchman.agents.proposal_runtime import ProposalCoordinator
from henchman.agents.staged_tool_registry import StagedToolRegistry
from henchman.agents.workspace_ownership import WorkspaceBinding
from henchman.core.session_operations import OperationRun
from henchman.tools.registry import ToolRegistry


class StagedConversation:
    """Own one runtime-bound proposal until reviewed or retired."""

    def __init__(self, *, conversation_id: str, paths: list[str], tools: list[str],
                 parent_registry: ToolRegistry, run: OperationRun, generation: int,
                 current_binding: Callable[[], WorkspaceBinding], completed: Callable[[], bool],
                 install: Callable[[Any, ToolRegistry], None]) -> None:
        self._id = conversation_id
        self._tools = tools
        self._parent_registry = parent_registry
        self._child = object()
        self._install = install
        parent = object()
        self._runtime = ProposalCoordinator(
            Path.cwd().resolve(), session=run.session, generation=generation, parent=parent, paths=paths,
            current_binding=current_binding, redactor=run.session.evidence_redactor,
        )
        self._handle = self._runtime.reserve(self._child, paths=paths, completed=completed)
        self._review = ParentProposalReview(self._runtime, self._handle)

    def bind(self, worker: asyncio.Task[Any]) -> None:
        self._runtime.bind(self._handle, worker)

    def activate(self, agent: Any) -> None:
        workspace = self._runtime.workspace(self._handle, self._child)
        registry = StagedToolRegistry(self._parent_registry, workspace, self._tools)
        self._install(agent, registry)

    def abort(self) -> None:
        self._runtime.abort(self._handle)

    def preview(self) -> str:
        value = json.loads(self._review.preview())
        # Preserve the acknowledgement at the end after all review content.
        return json.dumps({"conversation_id": self._id, **value}, ensure_ascii=True, separators=(",", ":"))

    def publish(self, token: str) -> ReviewResult:
        return self._review.publish(token)

    async def close(self) -> None:
        await self._runtime.close()
