"""Full session manager with delegated operations.

Extends :class:`_SessionManagerBase` with branch, merge, export,
import, and template operations.
"""

from __future__ import annotations

from typing import Any, TypeAlias

from .session_branch import _BranchMeta, branch_session
from .session_data import Session, session_from_json
from .session_export import export_as_markdown, import_json_session
from .session_helpers import (
    _generate_id,
    _now_iso,
    compute_project_hash,
)
from .session_manager_base import _SessionManagerBase
from .session_merge import _MIN_SESSIONS_FOR_MERGE, merge_sessions
from .session_templates import (
    _TemplateInfo,
    _TemplateIO,
    create_from_template,
    delete_template,
    list_templates,
    save_template,
)

# ---------------------------------------------------------------------------
# Semantic type aliases
# ---------------------------------------------------------------------------

SessionId: TypeAlias = str
FormatStr: TypeAlias = str
TagStr: TypeAlias = "str | None"


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------


class SessionManager(_SessionManagerBase):
    """Full session manager with branch/merge/export/template support.

    Inherits core CRUD operations from :class:`_SessionManagerBase`
    and adds higher-level delegated operations.
    """

    def branch_session(
        self: SessionManager,
        session_id: SessionId,
        branch_point: int,
        tag: TagStr = None,
        *,
        project_hash: str | None = None,
    ) -> Session:
        """Create a branch from an existing session.

        Args:
            session_id: ID of the session to branch from.
            branch_point: Message index (0-based) where the branch occurs.
            tag: Optional tag for the new branched session.

        Returns:
            New Session that shares history up to *branch_point*.

        Raises:
            ValueError: If *branch_point* is out of range.
            FileNotFoundError: If *session_id* doesn't exist.
            ValueError: If session ID prefix is ambiguous.

        See :func:`session_branch.branch_session` for details.
        """
        parent = self.load(session_id, project_hash=project_hash)
        meta = _BranchMeta(
            new_id=_generate_id(),
            now=_now_iso(),
            tag=tag,
        )
        branched = branch_session(parent, branch_point, meta)
        branched.evidence_redactor = self.evidence_redactor
        return branched

    def merge_sessions(
        self: SessionManager,
        session_ids: list[str],
        strategy: str = "union",
        tag: TagStr = None,
        *,
        project_hash: str | None = None,
    ) -> Session:
        """Merge multiple sessions.

        Args:
            session_ids: List of session IDs to merge. Must contain at least 2 IDs.
            strategy: Merge strategy. One of "union", "intersection", or "smart".
                Defaults to "union".
            tag: Optional tag for the merged session.

        Returns:
            Session: A new session containing the merged messages.

        Raises:
            ValueError: If fewer than 2 session IDs are provided.

        See :func:`session_merge.merge_sessions` for details.
        """
        if len(session_ids) < _MIN_SESSIONS_FOR_MERGE:
            msg = "At least 2 sessions required for merging"
            raise ValueError(msg)
        sessions = [self.load(sid, project_hash=project_hash) for sid in session_ids]
        now = _now_iso()
        merged = Session(
            id=_generate_id(),
            project_hash=sessions[0].project_hash,
            started=now,
            last_updated=now,
            tag=tag,
        )
        merge_sessions(sessions, session_ids, strategy, merged, now)
        merged.evidence_redactor = self.evidence_redactor
        return merged

    def export_session(
        self: SessionManager,
        session_id: SessionId,
        format: FormatStr = "json",
        *,
        include_metadata: bool = True,
        project_hash: str | None = None,
    ) -> str:
        """Export a session to string.

        Args:
            session_id: The ID of the session to export.
            format: Export format, either "json" or "markdown". Defaults to "json".
            include_metadata: Whether to include session metadata in the export.
                Only applies to markdown format. Defaults to True.

        Returns:
            The session exported as a string in the specified format.

        Raises:
            ValueError: If the format is not supported.

        See :func:`session_export.export_as_markdown` for details.
        """
        session = self.load(session_id, project_hash=project_hash)
        if format == "json":
            return session.to_json()
        if format == "markdown":
            return export_as_markdown(
                session,
                include_metadata=include_metadata,
            )
        msg = f"Unsupported export format: {format}"
        raise ValueError(msg)

    def import_session(
        self: SessionManager,
        data: str,
        format: FormatStr = "json",
        tag: TagStr = None,
        *,
        project_hash: str | None = None,
    ) -> Session:
        """Import a session from string.

        Args:
            data: The session data as a string.
            format: The format of the session data ("json" or "markdown").
            tag: Optional tag to assign to the imported session.
            project_hash: Destination project for an explicitly imported copy.

        Returns:
            The imported Session object.

        See :func:`session_export.import_json_session` for details.
        """
        if format == "json":
            session = session_from_json(data)
            session.evidence_redactor = self.evidence_redactor
            import_json_session(session, tag, _generate_id(), _now_iso())
            if project_hash is not None:
                session.project_hash = project_hash
            return session
        if format == "markdown":
            msg = "Markdown import not fully implemented. Use JSON."
            raise ValueError(msg)
        msg = f"Unsupported import format: {format}"
        raise ValueError(msg)

    def save_template(
        self: SessionManager,
        session_id: SessionId,
        name: str,
        description: str = "",
        parameters: dict[str, str] | None = None,
        *,
        project_hash: str | None = None,
    ) -> dict[str, Any]:
        """Save a session as a template.

        Args:
            session_id: The ID of the session to save as a template.
            name: The name of the template.
            description: Optional description of the template.
            parameters: Optional dictionary of template parameters.

        Returns:
            A dictionary containing template information.

        See :func:`session_templates.save_template` for details.
        """
        session = self.load(session_id, project_hash=project_hash)
        tid = f"template_{_generate_id()}"
        info = _TemplateInfo(name, description, parameters)
        io = _TemplateIO(self.data_dir / "templates", tid, _now_iso())
        result = save_template(session, info, tid, io)
        session.template_id = tid
        self.save(session)
        return result

    def create_from_template(
        self: SessionManager,
        template_id: SessionId,
        parameters: dict[str, Any] | None = None,
        tag: TagStr = None,
        *,
        project_hash: str | None = None,
    ) -> Session:
        """Create a session from a template.

        Args:
            template_id: The ID of the template to use.
            parameters: Optional dictionary of parameters for the template.
            tag: Optional tag to assign to the created session.

        Returns:
            A new Session object created from the template.

        See :func:`session_templates.create_from_template` for details.
        """
        io = _TemplateIO(
            self.data_dir / "templates",
            _generate_id(),
            _now_iso(),
        )
        session = create_from_template(template_id, io, parameters, tag, project_hash=project_hash)
        session.evidence_redactor = self.evidence_redactor
        return session

    def list_templates(
        self: SessionManager, *, project_hash: str | None = None
    ) -> list[dict[str, Any]]:
        """List available templates.

        See :func:`session_templates.list_templates` for details.

        Returns:
            List of template metadata dictionaries.
        """
        return list_templates(self.data_dir / "templates", project_hash=project_hash)

    def delete_template(
        self: SessionManager,
        template_id: SessionId,
        *,
        project_hash: str | None = None,
    ) -> None:
        """Delete a template.

        Args:
            template_id: The ID of the template to delete.

        See :func:`session_templates.delete_template` for details.

        Returns:
            None
        """
        delete_template(self.data_dir / "templates", template_id, project_hash=project_hash)


__all__ = [
    "SessionManager",
    "compute_project_hash",
]
