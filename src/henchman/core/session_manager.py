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
    ) -> Session:
        """Create a branch from an existing session.

        See :func:`session_branch.branch_session` for details.
        """
        parent = self.load(session_id)
        meta = _BranchMeta(
            new_id=_generate_id(), now=_now_iso(), tag=tag,
        )
        return branch_session(parent, branch_point, meta)

    def merge_sessions(
        self: SessionManager,
        session_ids: list[str],
        strategy: str = "union",
        tag: TagStr = None,
    ) -> Session:
        """Merge multiple sessions.

        See :func:`session_merge.merge_sessions` for details.
        """
        if len(session_ids) < _MIN_SESSIONS_FOR_MERGE:
            msg = "At least 2 sessions required for merging"
            raise ValueError(msg)
        sessions = [self.load(sid) for sid in session_ids]
        now = _now_iso()
        merged = Session(
            id=_generate_id(),
            project_hash=sessions[0].project_hash,
            started=now,
            last_updated=now,
            tag=tag,
        )
        merge_sessions(sessions, session_ids, strategy, merged, now)
        return merged

    def export_session(
        self: SessionManager,
        session_id: SessionId,
        format: FormatStr = "json",  # noqa: A002
        *,
        include_metadata: bool = True,
    ) -> str:
        """Export a session to string.

        See :func:`session_export.export_as_markdown` for details.
        """
        session = self.load(session_id)
        if format == "json":
            return session.to_json()
        if format == "markdown":
            return export_as_markdown(
                session, include_metadata=include_metadata,
            )
        msg = f"Unsupported export format: {format}"
        raise ValueError(msg)

    def import_session(
        self: SessionManager,
        data: str,
        format: FormatStr = "json",  # noqa: A002
        tag: TagStr = None,
    ) -> Session:
        """Import a session from string.

        See :func:`session_export.import_json_session` for details.
        """
        if format == "json":
            session = session_from_json(data)
            import_json_session(session, tag, _generate_id(), _now_iso())
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
    ) -> dict[str, Any]:
        """Save a session as a template.

        See :func:`session_templates.save_template` for details.
        """
        session = self.load(session_id)
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
    ) -> Session:
        """Create a session from a template.

        See :func:`session_templates.create_from_template` for details.
        """
        io = _TemplateIO(
            self.data_dir / "templates", _generate_id(), _now_iso(),
        )
        return create_from_template(template_id, io, parameters, tag)

    def list_templates(self: SessionManager) -> list[dict[str, Any]]:
        """List available templates.

        See :func:`session_templates.list_templates` for details.
        """
        return list_templates(self.data_dir / "templates")

    def delete_template(
        self: SessionManager,
        template_id: SessionId,
    ) -> None:
        """Delete a template.

        See :func:`session_templates.delete_template` for details.
        """
        delete_template(self.data_dir / "templates", template_id)


__all__ = [
    "SessionManager",
    "compute_project_hash",
]
