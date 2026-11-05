"""Approval grants never carry over across session boundaries (#18).

An in-process session switch (for example ``/chat resume``) shares the same
tool registry, so user approvals recorded for one session must be invalidated
when another session is activated.
"""

from __future__ import annotations

from pathlib import Path

from henchman.cli.session_manager import ReplSessionManager
from henchman.core.session_manager import SessionManager
from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry


class _WriteTool(Tool):
    """Mock WRITE tool requiring confirmation."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.executed: list[dict[str, object]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock {self._name} tool"

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {"path": {"type": "string"}}}

    @property
    def kind(self) -> ToolKind:
        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        self.executed.append(params)
        return ToolResult(content=f"Executed {self._name}")


def _approve_all(record: list[ConfirmationRequest]):
    async def handler(request: ConfirmationRequest) -> bool:
        record.append(request)
        return True

    return handler


async def test_switching_sessions_invalidates_grants(tmp_path: Path) -> None:
    core = SessionManager(data_dir=tmp_path / "sessions")
    manager = ReplSessionManager(session_manager=core, auto_save=False)
    registry = ToolRegistry()
    manager.bind_tool_registry(registry)
    registry.register(_WriteTool("write_x"))
    prompts: list[ConfirmationRequest] = []
    registry.set_confirmation_handler(_approve_all(prompts))

    session_a = core.create_session("project-hash", tag="a")
    session_b = core.create_session("project-hash", tag="b")
    manager.set_session(session_a)
    await registry.authorize("write_x", {"path": "/a"})
    assert len(prompts) == 1
    assert len(registry.list_approval_grants()) == 1

    manager.set_session(session_b)  # Session boundary.
    assert registry.list_approval_grants() == []
    await registry.authorize("write_x", {"path": "/a"})
    assert len(prompts) == 2  # Re-prompted; the grant did not carry over.


async def test_set_session_without_registry_binding_is_safe(tmp_path: Path) -> None:
    core = SessionManager(data_dir=tmp_path / "sessions")
    manager = ReplSessionManager(session_manager=core, auto_save=False)
    session = core.create_session("project-hash")
    # No registry bound: the boundary hook is a no-op.
    manager.set_session(session)
    assert manager.current is session
