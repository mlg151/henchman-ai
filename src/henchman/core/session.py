"""Session management for conversation persistence.

This module provides session data models and the SessionManager
for saving and restoring conversation history.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SessionMessage:
    """A message in a session.

    Attributes:
        role: The role (user, assistant, tool, system).
        content: The message content.
        tool_calls: Tool calls made by the assistant.
        tool_call_id: ID of the tool call this message responds to.
    """

    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    agent_id: str | None = None
    agent_role: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        data: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            data["content"] = self.content
        if self.tool_calls is not None:
            data["tool_calls"] = self.tool_calls
        if self.tool_call_id is not None:
            data["tool_call_id"] = self.tool_call_id
        if self.agent_id is not None:
            data["agent_id"] = self.agent_id
        if self.agent_role is not None:
            data["agent_role"] = self.agent_role
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMessage:
        """Create from dictionary.

        Args:
            data: Dictionary with message data.

        Returns:
            SessionMessage instance.
        """
        return cls(
            role=data["role"],
            content=data.get("content"),
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
            agent_id=data.get("agent_id"),
            agent_role=data.get("agent_role"),
        )


@dataclass
class SessionMetadata:
    """Metadata about a session (without messages).

    Attributes:
        id: Unique session identifier.
        tag: Optional human-readable tag.
        project_hash: Hash identifying the project.
        started: ISO timestamp when session started.
        last_updated: ISO timestamp of last update.
        message_count: Number of messages in session.
    """

    id: str
    project_hash: str
    started: str
    last_updated: str
    message_count: int
    tag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "tag": self.tag,
            "project_hash": self.project_hash,
            "started": self.started,
            "last_updated": self.last_updated,
            "message_count": self.message_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMetadata:
        """Create from dictionary.

        Args:
            data: Dictionary with metadata.

        Returns:
            SessionMetadata instance.
        """
        return cls(
            id=data["id"],
            tag=data.get("tag"),
            project_hash=data["project_hash"],
            started=data["started"],
            last_updated=data["last_updated"],
            message_count=data["message_count"],
        )


@dataclass
class TurnSummaryRecord:
    """Summary of a completed turn for persistence.

    Attributes:
        turn_number: Sequential turn number in session.
        summary_text: LLM-generated summary of the turn.
        files_modified: List of files modified during the turn.
        tool_count: Number of tool calls made.
        timestamp: ISO timestamp when turn completed.
    """

    turn_number: int
    summary_text: str
    files_modified: list[str]
    tool_count: int
    timestamp: str

    def __hash__(self) -> int:
        """Make TurnSummaryRecord hashable for deduplication."""
        return hash((
            self.turn_number,
            self.summary_text,
            tuple(self.files_modified),
            self.tool_count,
            self.timestamp,
        ))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "turn_number": self.turn_number,
            "summary_text": self.summary_text,
            "files_modified": self.files_modified,
            "tool_count": self.tool_count,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnSummaryRecord:
        """Create from dictionary."""
        return cls(
            turn_number=data["turn_number"],
            summary_text=data["summary_text"],
            files_modified=data.get("files_modified", []),
            tool_count=data.get("tool_count", 0),
            timestamp=data["timestamp"],
        )


@dataclass
class Session:
    """A conversation session.

    Attributes:
        id: Unique session identifier.
        project_hash: Hash identifying the project.
        started: ISO timestamp when session started.
        last_updated: ISO timestamp of last update.
        messages: List of session messages.
        tag: Optional human-readable tag.
        plan_mode: Whether the session is in Plan Mode (read-only).
        turn_summaries: Summaries of completed turns.
        parent_id: ID of parent session if this is a branch.
        branch_point: Message index where branch occurred (0-based).
        template_id: ID of template this session was created from.
        template_parameters: Parameters used to instantiate template.
        export_metadata: Metadata for export/import operations.
    """

    id: str
    project_hash: str
    started: str
    last_updated: str
    messages: list[SessionMessage] = field(default_factory=list)
    tag: str | None = None
    plan_mode: bool = False
    turn_summaries: list[TurnSummaryRecord] = field(default_factory=list)
    active_agents: list[str] = field(default_factory=list)
    delegation_log: list[dict[str, Any]] = field(default_factory=list)
    parent_id: str | None = None
    branch_point: int | None = None
    template_id: str | None = None
    template_parameters: dict[str, Any] = field(default_factory=dict)
    export_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "tag": self.tag,
            "project_hash": self.project_hash,
            "started": self.started,
            "last_updated": self.last_updated,
            "plan_mode": self.plan_mode,
            "messages": [msg.to_dict() for msg in self.messages],
            "turn_summaries": [ts.to_dict() for ts in self.turn_summaries],
            "active_agents": self.active_agents,
            "delegation_log": self.delegation_log,
            "parent_id": self.parent_id,
            "branch_point": self.branch_point,
            "template_id": self.template_id,
            "template_parameters": self.template_parameters,
            "export_metadata": self.export_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """Create from dictionary.

        Args:
            data: Dictionary with session data.

        Returns:
            Session instance.
        """
        return cls(
            id=data["id"],
            tag=data.get("tag"),
            project_hash=data["project_hash"],
            started=data["started"],
            last_updated=data["last_updated"],
            plan_mode=data.get("plan_mode", False),
            messages=[SessionMessage.from_dict(m) for m in data.get("messages", [])],
            turn_summaries=[
                TurnSummaryRecord.from_dict(ts) for ts in data.get("turn_summaries", [])
            ],
            active_agents=data.get("active_agents", []),
            delegation_log=data.get("delegation_log", []),
            parent_id=data.get("parent_id"),
            branch_point=data.get("branch_point"),
            template_id=data.get("template_id"),
            template_parameters=data.get("template_parameters", {}),
            export_metadata=data.get("export_metadata", {}),
        )

    def to_json(self) -> str:
        """Serialize to JSON string.

        Returns:
            JSON string.
        """
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> Session:
        """Deserialize from JSON string.

        Args:
            json_str: JSON string.

        Returns:
            Session instance.
        """
        return cls.from_dict(json.loads(json_str))

    def get_metadata(self) -> SessionMetadata:
        """Get session metadata.

        Returns:
            SessionMetadata for this session.
        """
        return SessionMetadata(
            id=self.id,
            tag=self.tag,
            project_hash=self.project_hash,
            started=self.started,
            last_updated=self.last_updated,
            message_count=len(self.messages),
        )


class SessionManager:
    """Manages session persistence and retrieval.

    Attributes:
        data_dir: Directory for storing session files.
        current: The currently active session.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize the session manager.

        Args:
            data_dir: Directory for session files. Defaults to ~/.henchman/sessions.
        """
        self.data_dir = data_dir or (Path.home() / ".henchman" / "sessions")
        self._current: Session | None = None

    @property
    def current(self) -> Session | None:
        """Get the current session."""
        return self._current

    def set_current(self, session: Session) -> None:
        """Set the current session.

        Args:
            session: Session to set as current.
        """
        self._current = session

    def clear_current(self) -> None:
        """Clear the current session."""
        self._current = None

    def _now_iso(self) -> str:
        """Get current time as ISO string."""
        return datetime.now(timezone.utc).isoformat()

    def _generate_id(self) -> str:
        """Generate a unique session ID."""
        return str(uuid.uuid4())

    def create_session(
        self,
        project_hash: str,
        tag: str | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            project_hash: Hash identifying the project.
            tag: Optional human-readable tag.

        Returns:
            New Session instance.
        """
        now = self._now_iso()
        return Session(
            id=self._generate_id(),
            project_hash=project_hash,
            started=now,
            last_updated=now,
            messages=[],
            tag=tag,
        )

    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.data_dir / f"{session_id}.json"

    def save(self, session: Session) -> Path:
        """Save a session to disk.

        Args:
            session: Session to save.

        Returns:
            Path to saved file.
        """
        # Update last_updated timestamp
        session.last_updated = self._now_iso()

        # Ensure directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        path = self._get_session_path(session.id)
        path.write_text(session.to_json())
        return path

    def load(self, session_id: str) -> Session:
        """Load a session from disk.

        Args:
            session_id: ID or ID prefix of session to load.

        Returns:
            Loaded Session instance.

        Raises:
            FileNotFoundError: If session doesn't exist or is ambiguous.
        """
        path = self._get_session_path(session_id)
        if path.exists():
            return Session.from_json(path.read_text())

        # If not found by exact ID, try as prefix
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        matches = list(self.data_dir.glob(f"{session_id}*.json"))
        if not matches:
            raise FileNotFoundError(f"Session not found: {session_id}")

        if len(matches) > 1:
            # Prefer exact match if somehow multiple match prefix but one is exact
            # (though glob already failed exact match if we are here)
            raise ValueError(f"Ambiguous session ID prefix: {session_id}")

        return Session.from_json(matches[0].read_text())

    def load_by_tag(
        self,
        tag: str,
        project_hash: str | None = None,
    ) -> Session | None:
        """Load a session by tag.

        Args:
            tag: Tag to search for.
            project_hash: Optional project hash to filter by.

        Returns:
            Session if found, None otherwise.
        """
        for meta in self.list_sessions(project_hash):
            if meta.tag == tag:
                return self.load(meta.id)
        return None

    def list_sessions(
        self,
        project_hash: str | None = None,
    ) -> list[SessionMetadata]:
        """List saved sessions.

        Args:
            project_hash: Optional project hash to filter by.

        Returns:
            List of session metadata.
        """
        if not self.data_dir.exists():
            return []

        sessions: list[SessionMetadata] = []
        for path in self.data_dir.glob("*.json"):
            try:
                session = Session.from_json(path.read_text())
                if project_hash is None or session.project_hash == project_hash:
                    sessions.append(session.get_metadata())
            except (json.JSONDecodeError, KeyError):
                # Skip invalid session files
                continue

        # Sort by last_updated, most recent first
        sessions.sort(key=lambda s: s.last_updated, reverse=True)
        return sessions

    def delete(self, session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: ID of session to delete.

        Raises:
            FileNotFoundError: If session doesn't exist.
        """
        path = self._get_session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        path.unlink()

    def compute_project_hash(self, directory: Path) -> str:
        """Compute a hash for a project directory.

        Args:
            directory: Project directory.

        Returns:
            Hash string identifying the project.
        """
        # Use absolute path for consistency
        abs_path = directory.resolve()
        return hashlib.sha256(str(abs_path).encode()).hexdigest()[:16]

    # Enhanced session management methods

    def branch_session(self, session_id: str, branch_point: int, tag: str | None = None) -> Session:
        """Create a new session branched from an existing session.

        Args:
            session_id: ID of session to branch from.
            branch_point: Message index (0-based) where branch occurs.
            tag: Optional tag for the new session.

        Returns:
            New branched Session instance.

        Raises:
            ValueError: If branch_point is out of range.
        """
        parent = self.load(session_id)

        if branch_point < 0 or branch_point > len(parent.messages):
            raise ValueError(
                f"Branch point {branch_point} out of range (0-{len(parent.messages)})"
            )

        now = self._now_iso()
        branch = Session(
            id=self._generate_id(),
            project_hash=parent.project_hash,
            started=now,
            last_updated=now,
            messages=parent.messages[:branch_point],  # Copy messages up to branch point
            tag=tag,
            plan_mode=parent.plan_mode,
            turn_summaries=parent.turn_summaries[:],  # Copy turn summaries
            active_agents=parent.active_agents[:],  # Copy active agents
            delegation_log=parent.delegation_log[:],  # Copy delegation log
            parent_id=parent.id,
            branch_point=branch_point,
            template_id=parent.template_id,
            template_parameters=parent.template_parameters.copy(),
            export_metadata=parent.export_metadata.copy(),
        )

        return branch

    def merge_sessions(
        self,
        session_ids: list[str],
        strategy: str = "union",
        tag: str | None = None,
    ) -> Session:
        """Merge multiple sessions into a new session.

        Args:
            session_ids: List of session IDs to merge.
            strategy: Merge strategy: "union", "intersection", or "smart".
            tag: Optional tag for the merged session.

        Returns:
            New merged Session instance.

        Raises:
            ValueError: If less than 2 sessions provided or invalid strategy.
        """
        if len(session_ids) < 2:
            raise ValueError("At least 2 sessions required for merging")

        if strategy not in ("union", "intersection", "smart"):
            raise ValueError(f"Invalid merge strategy: {strategy}")

        # Load all sessions
        sessions = [self.load(sid) for sid in session_ids]

        # Check all sessions have same project hash
        project_hash = sessions[0].project_hash
        for session in sessions[1:]:
            if session.project_hash != project_hash:
                raise ValueError("Cannot merge sessions from different projects")

        now = self._now_iso()
        merged = Session(
            id=self._generate_id(),
            project_hash=project_hash,
            started=now,
            last_updated=now,
            tag=tag,
        )

        if strategy == "union":
            # Combine all messages from all sessions
            all_messages: list[SessionMessage] = []
            for session in sessions:
                all_messages.extend(session.messages)
            merged.messages = all_messages

        elif strategy == "intersection":
            # Find common messages (by content hash)
            if not sessions:
                merged.messages = []
            else:
                # Create content hashes for each message
                message_hashes: list[set[str]] = []
                for session in sessions:
                    hashes = set()
                    for msg in session.messages:
                        # Simple hash of message content
                        msg_str = f"{msg.role}:{msg.content}:{str(msg.tool_calls)}"
                        msg_hash = hashlib.md5(msg_str.encode()).hexdigest()
                        hashes.add(msg_hash)
                    message_hashes.append(hashes)

                # Find intersection of all hash sets
                common_hashes = set.intersection(*message_hashes)

                # Get messages from first session that are in common
                merged.messages = [
                    msg for msg in sessions[0].messages
                    if hashlib.md5(
                        f"{msg.role}:{msg.content}:{str(msg.tool_calls)}".encode()
                    ).hexdigest() in common_hashes
                ]

        elif strategy == "smart":
            # Smart merge: combine unique insights, avoid duplicates
            seen_hashes: set[str] = set()
            merged_messages: list[SessionMessage] = []

            for session in sessions:
                for msg in session.messages:
                    msg_str = f"{msg.role}:{msg.content}:{str(msg.tool_calls)}"
                    msg_hash = hashlib.md5(msg_str.encode()).hexdigest()

                    if msg_hash not in seen_hashes:
                        seen_hashes.add(msg_hash)
                        merged_messages.append(msg)

            merged.messages = merged_messages

        # Merge other metadata
        all_turn_summaries: list[TurnSummaryRecord] = []
        all_active_agents: list[str] = []
        all_delegation_logs: list[dict[str, Any]] = []

        for session in sessions:
            all_turn_summaries.extend(session.turn_summaries)
            all_active_agents.extend(session.active_agents)
            all_delegation_logs.extend(session.delegation_log)

        # Remove duplicates while preserving order
        merged.turn_summaries = list(dict.fromkeys(all_turn_summaries))
        merged.active_agents = list(dict.fromkeys(all_active_agents))
        merged.delegation_log = all_delegation_logs

        # Add merge metadata
        merged.export_metadata = {
            "merged_from": session_ids,
            "merge_strategy": strategy,
            "merge_timestamp": now,
        }

        return merged

    def export_session(
        self,
        session_id: str,
        format: str = "json",
        include_metadata: bool = True,
    ) -> str:
        """Export a session to a string representation.

        Args:
            session_id: ID of session to export.
            format: Export format: "json" or "markdown".
            include_metadata: Whether to include session metadata.

        Returns:
            Exported session as string.

        Raises:
            ValueError: If invalid format specified.
        """
        session = self.load(session_id)

        if format == "json":
            return session.to_json()

        elif format == "markdown":
            # Create human-readable markdown export
            lines: list[str] = []

            if include_metadata:
                lines.append(f"# Session: {session.tag or session.id}")
                lines.append("")
                lines.append("## Metadata")
                lines.append(f"- **ID**: `{session.id}`")
                lines.append(f"- **Project Hash**: `{session.project_hash}`")
                lines.append(f"- **Started**: {session.started}")
                lines.append(f"- **Last Updated**: {session.last_updated}")
                lines.append(f"- **Messages**: {len(session.messages)}")
                if session.tag:
                    lines.append(f"- **Tag**: {session.tag}")
                if session.parent_id:
                    lines.append(f"- **Parent Session**: `{session.parent_id}`")
                if session.template_id:
                    lines.append(f"- **Template**: `{session.template_id}`")
                lines.append("")

            lines.append("## Conversation")
            lines.append("")

            for i, msg in enumerate(session.messages):
                lines.append(f"### Turn {i + 1}: {msg.role}")
                lines.append("")

                if msg.agent_id:
                    lines.append(f"*Agent: {msg.agent_id}*  ")

                if msg.content:
                    # Escape markdown special characters in content
                    content = msg.content.replace("<", "\\<").replace(">", "\\>")
                    lines.append(content)
                    lines.append("")

                if msg.tool_calls:
                    lines.append("**Tool Calls:**")
                    for tc in msg.tool_calls:
                        lines.append(f"- `{tc.get('name', 'unknown')}`: {tc.get('arguments', {})}")
                    lines.append("")

                lines.append("---")
                lines.append("")

            if session.turn_summaries:
                lines.append("## Turn Summaries")
                lines.append("")
                for ts in session.turn_summaries:
                    lines.append(f"### Turn {ts.turn_number}")
                    lines.append(f"*{ts.timestamp}*  ")
                    lines.append("")
                    lines.append(ts.summary_text)
                    lines.append("")

            return "\n".join(lines)

        else:
            raise ValueError(f"Unsupported export format: {format}")

    def import_session(
        self,
        data: str,
        format: str = "json",
        tag: str | None = None,
    ) -> Session:
        """Import a session from string representation.

        Args:
            data: Session data string.
            format: Import format: "json" or "markdown".
            tag: Optional tag for imported session.

        Returns:
            Imported Session instance.

        Raises:
            ValueError: If invalid format or data cannot be parsed.
        """
        if format == "json":
            session = Session.from_json(data)

            # Generate new ID for imported session
            session.id = self._generate_id()
            session.last_updated = self._now_iso()

            if tag:
                session.tag = tag

            # Add import metadata
            session.export_metadata["imported_at"] = session.last_updated
            session.export_metadata["original_id"] = session.id

            return session

        elif format == "markdown":
            # Parse markdown format (simplified - for full fidelity, use JSON)
            raise ValueError(
                "Markdown import not fully implemented. Use JSON for full fidelity import."
            )

        else:
            raise ValueError(f"Unsupported import format: {format}")

    def save_template(
        self,
        session_id: str,
        name: str,
        description: str = "",
        parameters: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Save a session as a template.

        Args:
            session_id: ID of session to save as template.
            name: Template name.
            description: Template description.
            parameters: Template parameters with descriptions.

        Returns:
            Template metadata.
        """
        session = self.load(session_id)

        template_id = f"template_{self._generate_id()}"
        template_data = {
            "id": template_id,
            "name": name,
            "description": description,
            "parameters": parameters or {},
            "session_data": session.to_dict(),
            "created_at": self._now_iso(),
        }

        # Save template to templates directory
        templates_dir = self.data_dir / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        template_path = templates_dir / f"{template_id}.json"
        template_path.write_text(json.dumps(template_data, indent=2))

        # Update session with template reference
        session.template_id = template_id
        self.save(session)

        return template_data

    def create_from_template(
        self,
        template_id: str,
        parameters: dict[str, Any] | None = None,
        tag: str | None = None,
    ) -> Session:
        """Create a new session from a template.

        Args:
            template_id: ID of template to use.
            parameters: Values for template parameters.
            tag: Optional tag for the new session.

        Returns:
            New Session instance created from template.

        Raises:
            FileNotFoundError: If template doesn't exist.
        """
        templates_dir = self.data_dir / "templates"
        template_path = templates_dir / f"{template_id}.json"

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_id}")

        template_data = json.loads(template_path.read_text())
        session_data = template_data["session_data"]

        # Apply parameter substitution
        if parameters:
            session_json = json.dumps(session_data)
            for param_name, param_value in parameters.items():
                placeholder = f"{{{{{param_name}}}}}"
                session_json = session_json.replace(placeholder, str(param_value))
            session_data = json.loads(session_json)

        # Create session from template data
        session = Session.from_dict(session_data)

        # Update session metadata
        session.id = self._generate_id()
        session.started = self._now_iso()
        session.last_updated = session.started
        session.tag = tag
        session.template_id = template_id
        session.template_parameters = parameters or {}

        return session

    def list_templates(self) -> list[dict[str, Any]]:
        """List available templates.

        Returns:
            List of template metadata dictionaries.
        """
        templates_dir = self.data_dir / "templates"

        if not templates_dir.exists():
            return []

        templates: list[dict[str, Any]] = []
        for path in templates_dir.glob("*.json"):
            try:
                template_data = json.loads(path.read_text())
                templates.append({
                    "id": template_data.get("id"),
                    "name": template_data.get("name"),
                    "description": template_data.get("description", ""),
                    "parameters": template_data.get("parameters", {}),
                    "created_at": template_data.get("created_at"),
                })
            except (json.JSONDecodeError, KeyError):
                # Skip invalid template files
                continue

        return templates

    def delete_template(self, template_id: str) -> None:
        """Delete a template.

        Args:
            template_id: ID of template to delete.

        Raises:
            FileNotFoundError: If template doesn't exist.
        """
        templates_dir = self.data_dir / "templates"
        template_path = templates_dir / f"{template_id}.json"

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_id}")

        template_path.unlink()
