"""Local team collaboration services for Tier 5."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from henchman.config.paths import resolve_project_settings_path
from henchman.core.session import Session
from henchman.core.session_memory import SessionMemoryService

_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
_DEFAULT_CHANNEL = "general"


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""

    return datetime.now(UTC).isoformat()


def _generate_id() -> str:
    """Return a unique record identifier."""

    return str(uuid4())


def _slugify(value: str) -> str:
    """Normalize a user-provided name into a filesystem-safe slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "workspace"


def _coerce_string_list(value: object) -> tuple[str, ...]:
    """Normalize a list-like value into a tuple of non-empty strings."""

    if not isinstance(value, list | tuple):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _coerce_string_mapping(value: object) -> dict[str, str]:
    """Normalize a mapping-like value into a string-to-string dictionary."""

    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _read_json(path: Path, *, default: object) -> object:
    """Read one JSON file or return *default* when it is absent."""

    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def _write_json(path: Path, payload: object) -> None:
    """Persist one JSON payload with stable formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")


def _read_json_lines(path: Path) -> list[dict[str, object]]:
    """Read newline-delimited JSON records from *path*."""

    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _append_json_line(path: Path, payload: dict[str, object]) -> None:
    """Append one JSON record to a newline-delimited JSON file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")


def _render_step(step: str, inputs: dict[str, str]) -> str:
    """Render one workflow step with simple ``{{key}}`` placeholders."""

    return _PLACEHOLDER_RE.sub(lambda match: inputs.get(match.group(1), match.group(0)), step)


@dataclass(frozen=True, slots=True)
class TeamWorkspaceRecord:
    """Persisted metadata for one team workspace."""

    workspace_id: str
    name: str
    description: str | None
    members: tuple[str, ...]
    created_at: str
    workspace_path: Path

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "description": self.description,
            "members": list(self.members),
            "created_at": self.created_at,
            "workspace_path": str(self.workspace_path),
        }


@dataclass(frozen=True, slots=True)
class TeamMessageRecord:
    """Persisted channel message in one team workspace."""

    message_id: str
    workspace_id: str
    channel: str
    sender: str
    body: str
    recipients: tuple[str, ...]
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "message_id": self.message_id,
            "workspace_id": self.workspace_id,
            "channel": self.channel,
            "sender": self.sender,
            "body": self.body,
            "recipients": list(self.recipients),
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class SharedFileRecord:
    """Persisted file share in one team workspace."""

    file_id: str
    workspace_id: str
    sender: str
    original_path: str
    shared_path: Path
    recipient: str | None
    note: str | None
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "file_id": self.file_id,
            "workspace_id": self.workspace_id,
            "sender": self.sender,
            "original_path": self.original_path,
            "shared_path": str(self.shared_path),
            "recipient": self.recipient,
            "note": self.note,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class TeamMemoryRecord:
    """Persisted shared memory captured for a team workspace."""

    memory_id: str
    workspace_id: str
    content: str
    kind: str
    source: str
    source_session_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "memory_id": self.memory_id,
            "workspace_id": self.workspace_id,
            "content": self.content,
            "kind": self.kind,
            "source": self.source,
            "source_session_id": self.source_session_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class PushNotificationRecord:
    """Persisted notification entry for a workspace event."""

    notification_id: str
    workspace_id: str
    recipient: str | None
    event: str
    message: str
    related_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "notification_id": self.notification_id,
            "workspace_id": self.workspace_id,
            "recipient": self.recipient,
            "event": self.event,
            "message": self.message,
            "related_id": self.related_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class WorkflowDefinitionRecord:
    """Persisted workflow definition for a team workspace."""

    workflow_id: str
    workspace_id: str
    workflow_name: str
    steps: tuple[str, ...]
    created_by: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "workflow_name": self.workflow_name,
            "steps": list(self.steps),
            "created_by": self.created_by,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class WorkflowRunRecord:
    """Persisted workflow request, retaining legacy execution claims when loaded."""

    run_id: str
    workspace_id: str
    workflow_name: str
    status: str
    requested_by: str
    inputs: dict[str, str]
    executed_steps: tuple[str, ...]
    trigger_name: str | None
    bridge_session_id: str | None
    created_at: str
    rendered_steps: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "run_id": self.run_id,
            "workspace_id": self.workspace_id,
            "workflow_name": self.workflow_name,
            "status": self.status,
            "requested_by": self.requested_by,
            "inputs": self.inputs,
            "executed_steps": list(self.executed_steps),
            "rendered_steps": list(self.rendered_steps),
            "trigger_name": self.trigger_name,
            "bridge_session_id": self.bridge_session_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class BridgeSessionRecord:
    """Persisted local bridge session for a remote collaboration surface."""

    bridge_id: str
    workspace_id: str
    remote_session: str
    created_by: str
    status: str
    created_at: str
    closed_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "bridge_id": self.bridge_id,
            "workspace_id": self.workspace_id,
            "remote_session": self.remote_session,
            "created_by": self.created_by,
            "status": self.status,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
        }


@dataclass(frozen=True, slots=True)
class RemoteTriggerRecord:
    """Persisted trigger that can invoke a workflow."""

    trigger_id: str
    workspace_id: str
    trigger_name: str
    workflow_name: str
    created_by: str
    bridge_session_id: str | None
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "trigger_id": self.trigger_id,
            "workspace_id": self.workspace_id,
            "trigger_name": self.trigger_name,
            "workflow_name": self.workflow_name,
            "created_by": self.created_by,
            "bridge_session_id": self.bridge_session_id,
            "created_at": self.created_at,
        }


def _workspace_from_dict(data: dict[str, object], *, workspace_path: Path) -> TeamWorkspaceRecord:
    """Deserialize one persisted workspace record."""

    return TeamWorkspaceRecord(
        workspace_id=str(data["workspace_id"]),
        name=str(data["name"]),
        description=str(data["description"]) if data.get("description") is not None else None,
        members=_coerce_string_list(data.get("members")),
        created_at=str(data["created_at"]),
        workspace_path=workspace_path,
    )


def _message_from_dict(data: dict[str, object]) -> TeamMessageRecord:
    """Deserialize one persisted team message."""

    return TeamMessageRecord(
        message_id=str(data["message_id"]),
        workspace_id=str(data["workspace_id"]),
        channel=str(data["channel"]),
        sender=str(data["sender"]),
        body=str(data["body"]),
        recipients=_coerce_string_list(data.get("recipients")),
        created_at=str(data["created_at"]),
    )


def _shared_file_from_dict(data: dict[str, object]) -> SharedFileRecord:
    """Deserialize one persisted shared file record."""

    recipient_value = data.get("recipient")
    note_value = data.get("note")
    return SharedFileRecord(
        file_id=str(data["file_id"]),
        workspace_id=str(data["workspace_id"]),
        sender=str(data["sender"]),
        original_path=str(data["original_path"]),
        shared_path=Path(str(data["shared_path"])),
        recipient=str(recipient_value) if recipient_value is not None else None,
        note=str(note_value) if note_value is not None else None,
        created_at=str(data["created_at"]),
    )


def _memory_from_dict(data: dict[str, object]) -> TeamMemoryRecord:
    """Deserialize one persisted team memory."""

    session_id = data.get("source_session_id")
    return TeamMemoryRecord(
        memory_id=str(data["memory_id"]),
        workspace_id=str(data["workspace_id"]),
        content=str(data["content"]),
        kind=str(data["kind"]),
        source=str(data["source"]),
        source_session_id=str(session_id) if session_id is not None else None,
        created_at=str(data["created_at"]),
    )


def _notification_from_dict(data: dict[str, object]) -> PushNotificationRecord:
    """Deserialize one persisted notification."""

    recipient_value = data.get("recipient")
    related_id = data.get("related_id")
    return PushNotificationRecord(
        notification_id=str(data["notification_id"]),
        workspace_id=str(data["workspace_id"]),
        recipient=str(recipient_value) if recipient_value is not None else None,
        event=str(data["event"]),
        message=str(data["message"]),
        related_id=str(related_id) if related_id is not None else None,
        created_at=str(data["created_at"]),
    )


def _workflow_definition_from_dict(data: dict[str, object]) -> WorkflowDefinitionRecord:
    """Deserialize one workflow definition."""

    return WorkflowDefinitionRecord(
        workflow_id=str(data["workflow_id"]),
        workspace_id=str(data["workspace_id"]),
        workflow_name=str(data["workflow_name"]),
        steps=_coerce_string_list(data.get("steps")),
        created_by=str(data["created_by"]),
        created_at=str(data["created_at"]),
    )


def _workflow_run_from_dict(data: dict[str, object]) -> WorkflowRunRecord:
    """Deserialize one workflow run."""

    trigger_value = data.get("trigger_name")
    bridge_value = data.get("bridge_session_id")
    return WorkflowRunRecord(
        run_id=str(data["run_id"]),
        workspace_id=str(data["workspace_id"]),
        workflow_name=str(data["workflow_name"]),
        status=str(data["status"]),
        requested_by=str(data["requested_by"]),
        inputs=_coerce_string_mapping(data.get("inputs")),
        executed_steps=_coerce_string_list(data.get("executed_steps")),
        rendered_steps=_coerce_string_list(data.get("rendered_steps")),
        trigger_name=str(trigger_value) if trigger_value is not None else None,
        bridge_session_id=str(bridge_value) if bridge_value is not None else None,
        created_at=str(data["created_at"]),
    )


def _bridge_from_dict(data: dict[str, object]) -> BridgeSessionRecord:
    """Deserialize one bridge session."""

    closed_at = data.get("closed_at")
    return BridgeSessionRecord(
        bridge_id=str(data["bridge_id"]),
        workspace_id=str(data["workspace_id"]),
        remote_session=str(data["remote_session"]),
        created_by=str(data["created_by"]),
        status=str(data["status"]),
        created_at=str(data["created_at"]),
        closed_at=str(closed_at) if closed_at is not None else None,
    )


def _trigger_from_dict(data: dict[str, object]) -> RemoteTriggerRecord:
    """Deserialize one remote trigger record."""

    bridge_value = data.get("bridge_session_id")
    return RemoteTriggerRecord(
        trigger_id=str(data["trigger_id"]),
        workspace_id=str(data["workspace_id"]),
        trigger_name=str(data["trigger_name"]),
        workflow_name=str(data["workflow_name"]),
        created_by=str(data["created_by"]),
        bridge_session_id=str(bridge_value) if bridge_value is not None else None,
        created_at=str(data["created_at"]),
    )


class _WorkspaceScopedService:
    """Shared helpers for project-local team storage."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the service with a project-local storage root."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._team_root = resolve_project_settings_path(self._project_root) / "team"

    def _workspace_id(self, workspace: str) -> str:
        """Return the normalized workspace identifier."""

        normalized = str(workspace).strip()
        if not normalized:
            raise ValueError("A workspace name is required.")
        return _slugify(normalized)

    def _workspace_dir(self, workspace: str) -> Path:
        """Return the directory for one workspace."""

        return self._team_root / "workspaces" / self._workspace_id(workspace)

    def _workspace_metadata_path(self, workspace: str) -> Path:
        """Return the workspace metadata path for one workspace."""

        return self._workspace_dir(workspace) / "workspace.json"

    def _require_workspace(self, workspace: str) -> str:
        """Validate that the workspace exists and return its normalized id."""

        workspace_id = self._workspace_id(workspace)
        if not self._workspace_metadata_path(workspace_id).exists():
            raise ValueError(f'Unknown team workspace "{workspace_id}".')
        return workspace_id


class PushNotificationService(_WorkspaceScopedService):
    """Persist local notifications for workspace activity."""

    def send(
        self,
        *,
        workspace_id: str,
        recipient: str | None,
        event: str,
        message: str,
        related_id: str | None = None,
    ) -> PushNotificationRecord:
        """Persist one notification for a workspace event."""

        normalized_workspace = self._require_workspace(workspace_id)
        record = PushNotificationRecord(
            notification_id=_generate_id(),
            workspace_id=normalized_workspace,
            recipient=recipient,
            event=event,
            message=message.strip(),
            related_id=related_id,
            created_at=_now_iso(),
        )
        _append_json_line(self._workspace_dir(normalized_workspace) / "notifications.jsonl", record.to_dict())
        return record

    def list_notifications(
        self,
        *,
        workspace_id: str,
        recipient: str | None = None,
    ) -> list[PushNotificationRecord]:
        """List persisted notifications for one workspace."""

        normalized_workspace = self._require_workspace(workspace_id)
        notifications = [
            _notification_from_dict(record)
            for record in _read_json_lines(self._workspace_dir(normalized_workspace) / "notifications.jsonl")
        ]
        if recipient is None:
            return notifications
        return [record for record in notifications if record.recipient == recipient]


class TeamWorkspaceService(_WorkspaceScopedService):
    """Manage team workspaces, messages, and shared files."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        notification_service: PushNotificationService | None = None,
    ) -> None:
        """Initialize the workspace service."""

        super().__init__(project_root)
        self._notifications = notification_service

    def create_workspace(
        self,
        *,
        name: str,
        members: list[str] | tuple[str, ...] | None = None,
        description: str | None = None,
    ) -> TeamWorkspaceRecord:
        """Create and persist one team workspace."""

        workspace_id = self._workspace_id(name)
        metadata_path = self._workspace_metadata_path(workspace_id)
        if metadata_path.exists():
            raise ValueError(f'Team workspace "{workspace_id}" already exists.')
        workspace_dir = self._workspace_dir(workspace_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        record = TeamWorkspaceRecord(
            workspace_id=workspace_id,
            name=name.strip(),
            description=description.strip() if isinstance(description, str) and description.strip() else None,
            members=_coerce_string_list(members),
            created_at=_now_iso(),
            workspace_path=workspace_dir,
        )
        _write_json(metadata_path, record.to_dict())
        return record

    def get_workspace(self, workspace_id: str) -> TeamWorkspaceRecord:
        """Load one persisted workspace record."""

        normalized_workspace = self._require_workspace(workspace_id)
        workspace_dir = self._workspace_dir(normalized_workspace)
        data = _read_json(self._workspace_metadata_path(normalized_workspace), default={})
        if not isinstance(data, dict):
            raise ValueError("Workspace metadata is invalid.")
        return _workspace_from_dict(data, workspace_path=workspace_dir)

    def list_workspaces(self) -> list[TeamWorkspaceRecord]:
        """List all persisted team workspaces."""

        workspaces_root = self._team_root / "workspaces"
        if not workspaces_root.exists():
            return []
        records: list[TeamWorkspaceRecord] = []
        for workspace_dir in sorted(path for path in workspaces_root.iterdir() if path.is_dir()):
            metadata_path = workspace_dir / "workspace.json"
            if not metadata_path.exists():
                continue
            data = _read_json(metadata_path, default={})
            if isinstance(data, dict):
                records.append(_workspace_from_dict(data, workspace_path=workspace_dir))
        return records

    def workspace_exists(self, workspace_id: str) -> bool:
        """Return whether a workspace exists."""

        return self._workspace_metadata_path(self._workspace_id(workspace_id)).exists()

    def delete_workspace(self, workspace_id: str) -> bool:
        """Delete one workspace and all of its persisted state."""

        normalized_workspace = self._workspace_id(workspace_id)
        workspace_dir = self._workspace_dir(normalized_workspace)
        if not workspace_dir.exists():
            return False
        shutil.rmtree(workspace_dir)
        return True

    def post_message(
        self,
        *,
        workspace_id: str,
        sender: str,
        body: str,
        channel: str = _DEFAULT_CHANNEL,
        recipients: list[str] | tuple[str, ...] | None = None,
    ) -> TeamMessageRecord:
        """Append one channel message to a workspace."""

        normalized_workspace = self._require_workspace(workspace_id)
        cleaned_sender = sender.strip()
        cleaned_body = body.strip()
        if not cleaned_sender:
            raise ValueError("A sender is required.")
        if not cleaned_body:
            raise ValueError("A message body is required.")
        record = TeamMessageRecord(
            message_id=_generate_id(),
            workspace_id=normalized_workspace,
            channel=_slugify(channel or _DEFAULT_CHANNEL),
            sender=cleaned_sender,
            body=cleaned_body,
            recipients=_coerce_string_list(recipients),
            created_at=_now_iso(),
        )
        messages_path = self._workspace_dir(normalized_workspace) / "channels" / f"{record.channel}.jsonl"
        _append_json_line(messages_path, record.to_dict())
        if self._notifications is not None:
            for recipient in record.recipients:
                self._notifications.send(
                    workspace_id=normalized_workspace,
                    recipient=recipient,
                    event="message",
                    message=f"New message from {record.sender}: {record.body}",
                    related_id=record.message_id,
                )
        return record

    def list_messages(
        self,
        *,
        workspace_id: str,
        channel: str = _DEFAULT_CHANNEL,
    ) -> list[TeamMessageRecord]:
        """List messages from one workspace channel."""

        normalized_workspace = self._require_workspace(workspace_id)
        messages_path = self._workspace_dir(normalized_workspace) / "channels" / f"{_slugify(channel)}.jsonl"
        return [_message_from_dict(record) for record in _read_json_lines(messages_path)]

    def share_file(
        self,
        *,
        workspace_id: str,
        sender: str,
        path: Path | str,
        recipient: str | None = None,
        note: str | None = None,
    ) -> SharedFileRecord:
        """Copy one file into a workspace share directory and persist metadata."""

        normalized_workspace = self._require_workspace(workspace_id)
        source_path = Path(path).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"Shared file does not exist: {source_path}")
        cleaned_sender = sender.strip()
        if not cleaned_sender:
            raise ValueError("A sender is required.")
        record = SharedFileRecord(
            file_id=_generate_id(),
            workspace_id=normalized_workspace,
            sender=cleaned_sender,
            original_path=str(source_path),
            shared_path=self._workspace_dir(normalized_workspace)
            / "shared"
            / f"{_generate_id()}__{source_path.name}",
            recipient=recipient.strip() if isinstance(recipient, str) and recipient.strip() else None,
            note=note.strip() if isinstance(note, str) and note.strip() else None,
            created_at=_now_iso(),
        )
        record.shared_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, record.shared_path)
        files_path = self._workspace_dir(normalized_workspace) / "shared" / "files.json"
        existing_payload = _read_json(files_path, default=[])
        existing = list(existing_payload) if isinstance(existing_payload, list) else []
        existing.append(record.to_dict())
        _write_json(files_path, existing)
        if self._notifications is not None and record.recipient is not None:
            self._notifications.send(
                workspace_id=normalized_workspace,
                recipient=record.recipient,
                event="file_share",
                message=f'{record.sender} shared "{source_path.name}".',
                related_id=record.file_id,
            )
        return record

    def list_shared_files(self, *, workspace_id: str) -> list[SharedFileRecord]:
        """List files shared into one workspace."""

        normalized_workspace = self._require_workspace(workspace_id)
        files_path = self._workspace_dir(normalized_workspace) / "shared" / "files.json"
        payload = _read_json(files_path, default=[])
        if not isinstance(payload, list):
            return []
        return [_shared_file_from_dict(record) for record in payload if isinstance(record, dict)]


class TeamMemorySyncService(_WorkspaceScopedService):
    """Sync extracted session memories into the workspace memory store."""

    def __init__(self, project_root: Path | None = None) -> None:
        """Initialize the memory sync service."""

        super().__init__(project_root)
        self._session_memories = SessionMemoryService()

    def sync_session(self, *, workspace_id: str, session: Session) -> tuple[TeamMemoryRecord, ...]:
        """Sync extracted session memories into a workspace-level store."""

        normalized_workspace = self._require_workspace(workspace_id)
        self._session_memories.extract_memories(session)
        session_records = self._session_memories.list_memories(session)
        existing = self.list_memories(workspace_id=normalized_workspace)
        existing_content = {record.content.casefold() for record in existing}
        created: list[TeamMemoryRecord] = []
        for session_record in session_records:
            normalized_content = session_record.content.casefold()
            if normalized_content in existing_content:
                continue
            created_record = TeamMemoryRecord(
                memory_id=_generate_id(),
                workspace_id=normalized_workspace,
                content=session_record.content,
                kind=session_record.kind,
                source=session_record.source,
                source_session_id=session.id,
                created_at=_now_iso(),
            )
            existing.append(created_record)
            created.append(created_record)
            existing_content.add(normalized_content)
        memories_path = self._workspace_dir(normalized_workspace) / "memories.json"
        _write_json(memories_path, [record.to_dict() for record in existing])
        return tuple(created)

    def list_memories(self, *, workspace_id: str) -> list[TeamMemoryRecord]:
        """List stored shared memories for one workspace."""

        normalized_workspace = self._require_workspace(workspace_id)
        payload = _read_json(self._workspace_dir(normalized_workspace) / "memories.json", default=[])
        if not isinstance(payload, list):
            return []
        return [_memory_from_dict(record) for record in payload if isinstance(record, dict)]


class WorkflowService(_WorkspaceScopedService):
    """Persist local workflow definitions and preparation requests without execution."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        notification_service: PushNotificationService | None = None,
    ) -> None:
        """Initialize the workflow service."""

        super().__init__(project_root)
        self._notifications = notification_service

    def define(
        self,
        *,
        workspace_id: str,
        workflow_name: str,
        steps: list[str] | tuple[str, ...],
        created_by: str,
    ) -> WorkflowDefinitionRecord:
        """Persist one workflow definition."""

        normalized_workspace = self._require_workspace(workspace_id)
        cleaned_steps = _coerce_string_list(steps)
        if not cleaned_steps:
            raise ValueError("A workflow must contain at least one step.")
        workflow_slug = _slugify(workflow_name)
        definition = WorkflowDefinitionRecord(
            workflow_id=_generate_id(),
            workspace_id=normalized_workspace,
            workflow_name=workflow_slug,
            steps=cleaned_steps,
            created_by=created_by.strip(),
            created_at=_now_iso(),
        )
        _write_json(
            self._workspace_dir(normalized_workspace) / "workflows" / f"{workflow_slug}.json",
            definition.to_dict(),
        )
        return definition

    def get_definition(self, *, workspace_id: str, workflow_name: str) -> WorkflowDefinitionRecord:
        """Load one workflow definition."""

        normalized_workspace = self._require_workspace(workspace_id)
        workflow_slug = _slugify(workflow_name)
        payload = _read_json(
            self._workspace_dir(normalized_workspace) / "workflows" / f"{workflow_slug}.json",
            default={},
        )
        if not isinstance(payload, dict) or not payload:
            raise ValueError(f'Unknown workflow "{workflow_slug}".')
        return _workflow_definition_from_dict(payload)

    def run(
        self,
        *,
        workspace_id: str,
        workflow_name: str,
        requested_by: str,
        inputs: dict[str, object] | None = None,
        trigger_name: str | None = None,
        bridge_session_id: str | None = None,
    ) -> WorkflowRunRecord:
        """Render and persist steps, explicitly recording that execution is unavailable."""

        definition = self.get_definition(workspace_id=workspace_id, workflow_name=workflow_name)
        normalized_inputs = _coerce_string_mapping(inputs)
        rendered_steps = tuple(_render_step(step, normalized_inputs) for step in definition.steps)
        record = WorkflowRunRecord(
            run_id=_generate_id(),
            workspace_id=definition.workspace_id,
            workflow_name=definition.workflow_name,
            status="execution_unavailable",
            requested_by=requested_by.strip(),
            inputs=normalized_inputs,
            executed_steps=(),
            rendered_steps=rendered_steps,
            trigger_name=trigger_name,
            bridge_session_id=bridge_session_id,
            created_at=_now_iso(),
        )
        _append_json_line(
            self._workspace_dir(definition.workspace_id)
            / "workflow_runs"
            / f"{definition.workflow_name}.jsonl",
            record.to_dict(),
        )
        if self._notifications is not None:
            self._notifications.send(
                workspace_id=definition.workspace_id,
                recipient=None,
                event="workflow_run",
                message=(
                    f'Workflow "{definition.workflow_name}" prepared only. '
                    "Execution is unavailable. No steps were executed."
                ),
                related_id=record.run_id,
            )
        return record

    def list_runs(self, *, workspace_id: str, workflow_name: str) -> list[WorkflowRunRecord]:
        """List persisted runs for one workflow."""

        normalized_workspace = self._require_workspace(workspace_id)
        workflow_slug = _slugify(workflow_name)
        runs_path = (
            self._workspace_dir(normalized_workspace) / "workflow_runs" / f"{workflow_slug}.jsonl"
        )
        return [_workflow_run_from_dict(record) for record in _read_json_lines(runs_path)]


class BridgeSessionService(_WorkspaceScopedService):
    """Persist local bridge session metadata for remote collaboration links."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        notification_service: PushNotificationService | None = None,
    ) -> None:
        """Initialize the bridge session service."""

        super().__init__(project_root)
        self._notifications = notification_service

    def open_bridge(
        self,
        *,
        workspace_id: str,
        remote_session: str,
        created_by: str,
    ) -> BridgeSessionRecord:
        """Persist one active bridge session."""

        normalized_workspace = self._require_workspace(workspace_id)
        record = BridgeSessionRecord(
            bridge_id=_generate_id(),
            workspace_id=normalized_workspace,
            remote_session=remote_session.strip(),
            created_by=created_by.strip(),
            status="active",
            created_at=_now_iso(),
        )
        records = self.list_bridges(workspace_id=normalized_workspace)
        records.append(record)
        self._write_bridges(normalized_workspace, records)
        if self._notifications is not None:
            self._notifications.send(
                workspace_id=normalized_workspace,
                recipient=None,
                event="bridge_open",
                message=f'Opened bridge for "{record.remote_session}".',
                related_id=record.bridge_id,
            )
        return record

    def close_bridge(self, *, workspace_id: str, bridge_id: str) -> BridgeSessionRecord:
        """Mark one bridge session as closed and persist the update."""

        normalized_workspace = self._require_workspace(workspace_id)
        records = self.list_bridges(workspace_id=normalized_workspace)
        updated: list[BridgeSessionRecord] = []
        closed_record: BridgeSessionRecord | None = None
        for record in records:
            if record.bridge_id != bridge_id:
                updated.append(record)
                continue
            closed_record = BridgeSessionRecord(
                bridge_id=record.bridge_id,
                workspace_id=record.workspace_id,
                remote_session=record.remote_session,
                created_by=record.created_by,
                status="closed",
                created_at=record.created_at,
                closed_at=_now_iso(),
            )
            updated.append(closed_record)
        if closed_record is None:
            raise ValueError(f'Unknown bridge "{bridge_id}".')
        self._write_bridges(normalized_workspace, updated)
        if self._notifications is not None:
            self._notifications.send(
                workspace_id=normalized_workspace,
                recipient=None,
                event="bridge_close",
                message=f'Closed bridge "{bridge_id}".',
                related_id=bridge_id,
            )
        return closed_record

    def list_bridges(self, *, workspace_id: str) -> list[BridgeSessionRecord]:
        """List bridge sessions for one workspace."""

        normalized_workspace = self._require_workspace(workspace_id)
        payload = _read_json(self._workspace_dir(normalized_workspace) / "bridges.json", default=[])
        if not isinstance(payload, list):
            return []
        return [_bridge_from_dict(record) for record in payload if isinstance(record, dict)]

    def get_bridge(self, *, workspace_id: str, bridge_id: str) -> BridgeSessionRecord:
        """Return one bridge session by identifier."""

        for record in self.list_bridges(workspace_id=workspace_id):
            if record.bridge_id == bridge_id:
                return record
        raise ValueError(f'Unknown bridge "{bridge_id}".')

    def _write_bridges(self, workspace_id: str, records: list[BridgeSessionRecord]) -> None:
        """Persist all bridge session records for a workspace."""

        _write_json(
            self._workspace_dir(workspace_id) / "bridges.json",
            [record.to_dict() for record in records],
        )


class RemoteTriggerService(_WorkspaceScopedService):
    """Persist and invoke local workflow triggers."""

    def __init__(
        self,
        project_root: Path | None = None,
        *,
        workflow_service: WorkflowService | None = None,
        bridge_service: BridgeSessionService | None = None,
        notification_service: PushNotificationService | None = None,
    ) -> None:
        """Initialize the remote trigger service."""

        super().__init__(project_root)
        self._notifications = notification_service
        self._workflow_service = workflow_service or WorkflowService(
            project_root=self._project_root,
            notification_service=notification_service,
        )
        self._bridge_service = bridge_service or BridgeSessionService(
            project_root=self._project_root,
            notification_service=notification_service,
        )

    def create_trigger(
        self,
        *,
        workspace_id: str,
        trigger_name: str,
        workflow_name: str,
        created_by: str,
        bridge_session_id: str | None = None,
    ) -> RemoteTriggerRecord:
        """Persist one workflow trigger for later invocation."""

        normalized_workspace = self._require_workspace(workspace_id)
        definition = self._workflow_service.get_definition(
            workspace_id=normalized_workspace,
            workflow_name=workflow_name,
        )
        if bridge_session_id is not None:
            bridge = self._bridge_service.get_bridge(
                workspace_id=normalized_workspace,
                bridge_id=bridge_session_id,
            )
            if bridge.status != "active":
                raise ValueError(f'Bridge "{bridge.bridge_id}" is not active.')
        records = self.list_triggers(workspace_id=normalized_workspace)
        record = RemoteTriggerRecord(
            trigger_id=_generate_id(),
            workspace_id=normalized_workspace,
            trigger_name=_slugify(trigger_name),
            workflow_name=definition.workflow_name,
            created_by=created_by.strip(),
            bridge_session_id=bridge_session_id,
            created_at=_now_iso(),
        )
        records.append(record)
        self._write_triggers(normalized_workspace, records)
        return record

    def invoke_trigger(
        self,
        *,
        workspace_id: str,
        trigger_name: str,
        invoked_by: str,
        inputs: dict[str, object] | None = None,
    ) -> WorkflowRunRecord:
        """Prepare a triggered workflow without executing its steps."""

        normalized_workspace = self._require_workspace(workspace_id)
        trigger = self.get_trigger(workspace_id=normalized_workspace, trigger_name=trigger_name)
        if trigger.bridge_session_id is not None:
            bridge = self._bridge_service.get_bridge(
                workspace_id=normalized_workspace,
                bridge_id=trigger.bridge_session_id,
            )
            if bridge.status != "active":
                raise ValueError(f'Bridge "{bridge.bridge_id}" is not active.')
        run = self._workflow_service.run(
            workspace_id=normalized_workspace,
            workflow_name=trigger.workflow_name,
            requested_by=invoked_by,
            inputs=inputs,
            trigger_name=trigger.trigger_name,
            bridge_session_id=trigger.bridge_session_id,
        )
        if self._notifications is not None:
            self._notifications.send(
                workspace_id=normalized_workspace,
                recipient=None,
                event="remote_trigger",
                message=(
                    f'Trigger "{trigger.trigger_name}" prepared workflow "{trigger.workflow_name}" only. '
                    "Execution is unavailable. No steps were executed."
                ),
                related_id=run.run_id,
            )
        return run

    def list_triggers(self, *, workspace_id: str) -> list[RemoteTriggerRecord]:
        """List all triggers defined for one workspace."""

        normalized_workspace = self._require_workspace(workspace_id)
        payload = _read_json(self._workspace_dir(normalized_workspace) / "triggers.json", default=[])
        if not isinstance(payload, list):
            return []
        return [_trigger_from_dict(record) for record in payload if isinstance(record, dict)]

    def get_trigger(self, *, workspace_id: str, trigger_name: str) -> RemoteTriggerRecord:
        """Return one trigger by name."""

        normalized_trigger = _slugify(trigger_name)
        for record in self.list_triggers(workspace_id=workspace_id):
            if record.trigger_name == normalized_trigger:
                return record
        raise ValueError(f'Unknown trigger "{normalized_trigger}".')

    def _write_triggers(self, workspace_id: str, records: list[RemoteTriggerRecord]) -> None:
        """Persist all trigger definitions for a workspace."""

        _write_json(
            self._workspace_dir(workspace_id) / "triggers.json",
            [record.to_dict() for record in records],
        )


__all__ = [
    "BridgeSessionRecord",
    "BridgeSessionService",
    "PushNotificationRecord",
    "PushNotificationService",
    "RemoteTriggerRecord",
    "RemoteTriggerService",
    "SharedFileRecord",
    "TeamMemoryRecord",
    "TeamMemorySyncService",
    "TeamMessageRecord",
    "TeamWorkspaceRecord",
    "TeamWorkspaceService",
    "WorkflowDefinitionRecord",
    "WorkflowRunRecord",
    "WorkflowService",
]
