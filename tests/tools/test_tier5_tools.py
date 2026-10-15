"""Tests for Tier 5 team collaboration builtin tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_manager import ToolManager
from henchman.core.session import SessionManager, SessionMessage
from henchman.team import (
    BridgeSessionService,
    TeamMemorySyncService,
    TeamWorkspaceService,
    WorkflowService,
)


def test_builtin_surface_includes_tier5_tools() -> None:
    """The builtin export surface should expose the Tier 5 collaboration tools."""

    import henchman.tools.builtins as builtins_mod

    assert {
        "TeamCreateTool",
        "TeamDeleteTool",
        "SendMessageTool",
        "SendUserFileTool",
        "WorkflowTool",
    } <= set(builtins_mod.__all__)

    def _instantiate(tool_class: object) -> object:
        if tool_class is builtins_mod.ShellTool:
            return builtins_mod.ShellTool(default_timeout=60)
        if tool_class is builtins_mod.RagSearchTool:
            from unittest.mock import MagicMock

            return builtins_mod.RagSearchTool(store=MagicMock())
        return tool_class()

    names = {_instantiate(tool_class).name for tool_class in builtins_mod.iter_available_builtin_tool_classes()}

    assert {"team_create", "team_delete", "send_message", "send_user_file", "workflow"} <= names


@pytest.mark.anyio
async def test_team_tools_manage_workspace_messages_files_and_memory(tmp_path: Path) -> None:
    """Tier 5 tools should persist collaboration data through the builtin registry."""

    manager = ToolManager()

    backing_manager = SessionManager(data_dir=tmp_path / "sessions")
    wrapper = ReplSessionManager(session_manager=backing_manager, auto_save=False)
    session = backing_manager.create_session(project_hash="abc123", tag="tier5")
    session.messages = [SessionMessage(role="user", content="Prefer compact output.")]
    wrapper.set_session(session)
    manager.bind_runtime(session_manager=wrapper, project_root=tmp_path)
    manager.register_builtin_tools()

    source_file = tmp_path / "brief.txt"
    source_file.write_text("handoff details", encoding="utf-8")

    created = await manager.registry.execute(
        "team_create",
        {
            "workspace": "Release Squad",
            "members": ["alice", "bob"],
            "description": "Cross-functional release coordination.",
        },
    )
    messaged = await manager.registry.execute(
        "send_message",
        {
            "workspace": "release-squad",
            "sender": "alice",
            "message": "Ready for handoff.",
            "recipients": ["bob"],
        },
    )
    shared = await manager.registry.execute(
        "send_user_file",
        {
            "workspace": "release-squad",
            "sender": "alice",
            "path": str(source_file),
            "recipient": "bob",
            "note": "Latest handoff brief.",
        },
    )

    workspace_service = TeamWorkspaceService(project_root=tmp_path)
    memory_service = TeamMemorySyncService(project_root=tmp_path)

    assert created.success is True
    assert messaged.success is True
    assert shared.success is True
    assert workspace_service.get_workspace("release-squad").members == ("alice", "bob")
    assert len(workspace_service.list_messages(workspace_id="release-squad")) == 1
    assert len(workspace_service.list_shared_files(workspace_id="release-squad")) == 1
    assert [record.content for record in memory_service.list_memories(workspace_id="release-squad")] == [
        "Prefer compact output."
    ]

    deleted = await manager.registry.execute("team_delete", {"workspace": "release-squad"})

    assert deleted.success is True
    assert workspace_service.workspace_exists("release-squad") is False


@pytest.mark.anyio
async def test_workflow_tool_supports_define_run_trigger_and_bridge_actions(
    tmp_path: Path,
) -> None:
    """WorkflowTool should orchestrate local workflow, bridge, and trigger services."""

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()

    created = await manager.registry.execute(
        "team_create",
        {"workspace": "Platform Ops", "members": ["alice", "ci-bot"]},
    )
    defined = await manager.registry.execute(
        "workflow",
        {
            "action": "define",
            "workspace": "platform-ops",
            "workflow": "release-checklist",
            "steps": ["review {{ticket}}", "ship {{ticket}}"],
            "actor": "alice",
        },
    )
    ran = await manager.registry.execute(
        "workflow",
        {
            "action": "run",
            "workspace": "platform-ops",
            "workflow": "release-checklist",
            "actor": "alice",
            "inputs": {"ticket": "REL-7"},
        },
    )
    opened = await manager.registry.execute(
        "workflow",
        {
            "action": "open_bridge",
            "workspace": "platform-ops",
            "remote_session": "discord://release-room",
            "actor": "alice",
        },
    )

    bridge_service = BridgeSessionService(project_root=tmp_path)
    bridge_id = bridge_service.list_bridges(workspace_id="platform-ops")[0].bridge_id

    created_trigger = await manager.registry.execute(
        "workflow",
        {
            "action": "create_trigger",
            "workspace": "platform-ops",
            "trigger": "nightly-release",
            "workflow": "release-checklist",
            "actor": "alice",
            "bridge_id": bridge_id,
        },
    )
    triggered = await manager.registry.execute(
        "workflow",
        {
            "action": "trigger",
            "workspace": "platform-ops",
            "trigger": "nightly-release",
            "actor": "ci-bot",
            "inputs": {"ticket": "REL-8"},
        },
    )
    closed = await manager.registry.execute(
        "workflow",
        {
            "action": "close_bridge",
            "workspace": "platform-ops",
            "bridge_id": bridge_id,
            "actor": "alice",
        },
    )

    workflow_service = WorkflowService(project_root=tmp_path)

    assert created.success is True
    assert defined.success is True
    assert ran.success is False
    assert opened.success is True
    assert created_trigger.success is True
    assert triggered.success is False
    assert closed.success is True
    assert "release-checklist" in defined.content
    assert "REL-7" in ran.content
    assert "nightly-release" in created_trigger.content
    assert "REL-8" in triggered.content
    assert workflow_service.list_runs(
        workspace_id="platform-ops", workflow_name="release-checklist"
    )[-1].rendered_steps == ("review REL-8", "ship REL-8")
