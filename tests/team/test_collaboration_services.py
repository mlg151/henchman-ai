"""Tests for Tier 5 team collaboration services."""

from __future__ import annotations

from pathlib import Path

from henchman.core.session import SessionManager, SessionMessage
from henchman.core.session_memory import SessionMemoryService
from henchman.team import (
    BridgeSessionService,
    PushNotificationService,
    RemoteTriggerService,
    TeamMemorySyncService,
    TeamWorkspaceService,
    WorkflowService,
)


def test_workspace_service_round_trips_messages_files_and_notifications(
    tmp_path: Path,
) -> None:
    """Team workspaces should persist shared messages and files locally."""

    notifications = PushNotificationService(project_root=tmp_path)
    service = TeamWorkspaceService(project_root=tmp_path, notification_service=notifications)

    workspace = service.create_workspace(
        name="Platform Ops",
        members=["alice", "bob"],
        description="Operational coordination workspace.",
    )
    source_file = tmp_path / "runbook.txt"
    source_file.write_text("Escalation flow", encoding="utf-8")

    message = service.post_message(
        workspace_id=workspace.workspace_id,
        sender="alice",
        body="Need a release checkpoint.",
        recipients=["bob"],
    )
    shared_file = service.share_file(
        workspace_id=workspace.workspace_id,
        sender="alice",
        path=source_file,
        recipient="bob",
        note="Latest runbook snapshot.",
    )

    workspace_path = (
        tmp_path
        / ".henchman"
        / "team"
        / "workspaces"
        / workspace.workspace_id
        / "workspace.json"
    )

    assert workspace.workspace_id == "platform-ops"
    assert workspace_path.exists()
    assert service.get_workspace(workspace.workspace_id).members == ("alice", "bob")
    assert service.list_messages(workspace_id=workspace.workspace_id)[0].message_id == message.message_id
    assert service.list_shared_files(workspace_id=workspace.workspace_id)[0].file_id == shared_file.file_id
    assert shared_file.shared_path.exists()
    assert len(notifications.list_notifications(workspace_id=workspace.workspace_id, recipient="bob")) == 2
    assert service.delete_workspace(workspace.workspace_id) is True
    assert workspace_path.exists() is False


def test_team_memory_sync_service_deduplicates_session_preferences(tmp_path: Path) -> None:
    """Session memories should sync into the workspace store exactly once."""

    workspace_service = TeamWorkspaceService(project_root=tmp_path)
    workspace = workspace_service.create_workspace(name="Release Squad", members=["alice"])

    manager = SessionManager(data_dir=tmp_path / "sessions")
    session = manager.create_session(project_hash="abc123", tag="tier5")
    session.messages = [
        SessionMessage(role="user", content="Prefer compact output."),
        SessionMessage(role="user", content="Use .henchman for project config."),
    ]

    service = TeamMemorySyncService(project_root=tmp_path)
    memory_service = SessionMemoryService()
    extracted = memory_service.extract_memories(session)
    assert len(extracted) == 2

    created = service.sync_session(workspace_id=workspace.workspace_id, session=session)
    repeated = service.sync_session(workspace_id=workspace.workspace_id, session=session)

    assert len(created) == 2
    assert repeated == ()
    assert [record.content for record in service.list_memories(workspace_id=workspace.workspace_id)] == [
        "Prefer compact output.",
        "Use .henchman for project config.",
    ]


def _extracted_session(
    manager: SessionManager, tag: str
) -> tuple[object, SessionMemoryService]:
    """Persist a session with both extraction candidates stored on the session."""

    session = manager.create_session(project_hash="abc123", tag=tag)
    session.messages = [
        SessionMessage(role="user", content="Prefer compact output."),
        SessionMessage(role="user", content="Use .henchman for project config."),
    ]
    manager.save(session)
    memory_service = SessionMemoryService()
    loaded = manager.load(session.id)
    extracted = memory_service.extract_memories(loaded)
    assert len(extracted) == 2
    manager.save(loaded)
    return loaded, memory_service


def test_sync_session_propagates_session_memory_deletion(tmp_path: Path) -> None:
    """Deleting a session memory must remove its synced workspace copy on next sync."""

    workspace_service = TeamWorkspaceService(project_root=tmp_path)
    workspace = workspace_service.create_workspace(name="Release Squad", members=["alice"])
    manager = SessionManager(data_dir=tmp_path / "sessions")
    session, memory_service = _extracted_session(manager, "tier5-del")

    service = TeamMemorySyncService(project_root=tmp_path)
    service.sync_session(workspace_id=workspace.workspace_id, session=session)

    memories = service.list_memories(workspace_id=workspace.workspace_id)
    assert len(memories) == 2

    loaded = manager.load(session.id)
    stored = memory_service.list_memories(loaded)
    memory_service.delete_memory(loaded, stored[0].id)
    manager.save(loaded)

    service.sync_session(workspace_id=workspace.workspace_id, session=manager.load(session.id))

    remaining = service.list_memories(workspace_id=workspace.workspace_id)
    assert [record.content for record in remaining] == ["Use .henchman for project config."]


def test_sync_session_propagates_session_memory_edit(tmp_path: Path) -> None:
    """Editing a session memory must replace its stale workspace copy on next sync."""

    workspace_service = TeamWorkspaceService(project_root=tmp_path)
    workspace = workspace_service.create_workspace(name="Release Squad", members=["alice"])
    manager = SessionManager(data_dir=tmp_path / "sessions")
    session, memory_service = _extracted_session(manager, "tier5-edit")

    service = TeamMemorySyncService(project_root=tmp_path)
    service.sync_session(workspace_id=workspace.workspace_id, session=session)

    loaded = manager.load(session.id)
    stored = memory_service.list_memories(loaded)
    memory_service.edit_memory(loaded, stored[0].id, content="Prefer table output.")
    manager.save(loaded)

    service.sync_session(workspace_id=workspace.workspace_id, session=manager.load(session.id))

    remaining = service.list_memories(workspace_id=workspace.workspace_id)
    assert sorted(record.content for record in remaining) == [
        "Prefer table output.",
        "Use .henchman for project config.",
    ]
    assert "Prefer compact output." not in [record.content for record in remaining]


def test_sync_session_reconciliation_is_scoped_to_the_source_session(
    tmp_path: Path,
) -> None:
    """Reconciling one session must not touch memories synced by another session."""

    workspace_service = TeamWorkspaceService(project_root=tmp_path)
    workspace = workspace_service.create_workspace(name="Release Squad", members=["alice"])
    manager = SessionManager(data_dir=tmp_path / "sessions")
    session_a, memory_service = _extracted_session(manager, "tier5-a")
    session_b = manager.create_session(project_hash="abc123", tag="tier5-b")
    session_b.messages = [SessionMessage(role="user", content="Remember the deploy channel.")]
    manager.save(session_b)
    loaded_b = manager.load(session_b.id)
    memory_service.extract_memories(loaded_b)
    manager.save(loaded_b)

    service = TeamMemorySyncService(project_root=tmp_path)
    service.sync_session(workspace_id=workspace.workspace_id, session=session_a)
    service.sync_session(workspace_id=workspace.workspace_id, session=loaded_b)

    loaded_a = manager.load(session_a.id)
    stored_a = memory_service.list_memories(loaded_a)
    memory_service.delete_memory(loaded_a, stored_a[0].id)
    manager.save(loaded_a)

    service.sync_session(workspace_id=workspace.workspace_id, session=manager.load(session_a.id))

    remaining = service.list_memories(workspace_id=workspace.workspace_id)
    contents = [record.content for record in remaining]
    assert "Remember the deploy channel." in contents
    assert "Use .henchman for project config." in contents


def test_team_memory_sync_delete_memory_removes_workspace_record(tmp_path: Path) -> None:
    """delete_memory must remove one workspace record by id (and report misses)."""

    workspace_service = TeamWorkspaceService(project_root=tmp_path)
    workspace = workspace_service.create_workspace(name="Release Squad", members=["alice"])
    manager = SessionManager(data_dir=tmp_path / "sessions")
    session, _memory_service = _extracted_session(manager, "tier5-wsdel")

    service = TeamMemorySyncService(project_root=tmp_path)
    service.sync_session(workspace_id=workspace.workspace_id, session=session)
    memories = service.list_memories(workspace_id=workspace.workspace_id)
    assert len(memories) == 2

    assert service.delete_memory(workspace_id=workspace.workspace_id, memory_id=memories[0].memory_id) is True
    assert service.delete_memory(workspace_id=workspace.workspace_id, memory_id="no-such-id") is False
    remaining = service.list_memories(workspace_id=workspace.workspace_id)
    assert [record.memory_id for record in remaining] == [memories[1].memory_id]


def test_workflow_trigger_bridge_and_notifications_round_trip(tmp_path: Path) -> None:
    """Triggers and bridges should prepare workflows and leave persisted records."""

    workspace_service = TeamWorkspaceService(project_root=tmp_path)
    workspace = workspace_service.create_workspace(
        name="Release Squad", members=["alice", "ci-bot"]
    )
    notifications = PushNotificationService(project_root=tmp_path)
    workflow_service = WorkflowService(project_root=tmp_path, notification_service=notifications)
    bridge_service = BridgeSessionService(project_root=tmp_path, notification_service=notifications)
    trigger_service = RemoteTriggerService(
        project_root=tmp_path,
        workflow_service=workflow_service,
        bridge_service=bridge_service,
        notification_service=notifications,
    )

    workflow = workflow_service.define(
        workspace_id=workspace.workspace_id,
        workflow_name="release-checklist",
        steps=["review {{ticket}}", "ship {{ticket}}"],
        created_by="alice",
    )
    bridge = bridge_service.open_bridge(
        workspace_id=workspace.workspace_id,
        remote_session="discord://release-room",
        created_by="alice",
    )
    trigger = trigger_service.create_trigger(
        workspace_id=workspace.workspace_id,
        trigger_name="nightly-release",
        workflow_name=workflow.workflow_name,
        created_by="alice",
        bridge_session_id=bridge.bridge_id,
    )
    run = trigger_service.invoke_trigger(
        workspace_id=workspace.workspace_id,
        trigger_name=trigger.trigger_name,
        invoked_by="ci-bot",
        inputs={"ticket": "REL-42"},
    )
    closed = bridge_service.close_bridge(
        workspace_id=workspace.workspace_id,
        bridge_id=bridge.bridge_id,
    )

    assert run.status == "execution_unavailable"
    assert run.executed_steps == ()
    assert run.rendered_steps == ("review REL-42", "ship REL-42")
    assert trigger.bridge_session_id == bridge.bridge_id
    assert closed.status == "closed"
    assert any(
        notification.event == "remote_trigger"
        for notification in notifications.list_notifications(workspace_id=workspace.workspace_id)
    )
