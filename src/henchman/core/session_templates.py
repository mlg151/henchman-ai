"""Template operations for session management.

Provides functions to save sessions as reusable templates,
create sessions from templates, list and delete templates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .session_data import Session, session_from_dict

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Parameter objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _TemplateInfo:
    """Grouped metadata for a template save operation."""

    name: str
    description: str
    parameters: dict[str, str] | None


@dataclass(frozen=True)
class _TemplateIO:
    """Grouped I/O context for template operations."""

    templates_dir: Path
    new_id: str
    now: str


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


def save_template(
    session: Session,
    info: _TemplateInfo,
    template_id: str,
    io: _TemplateIO,
) -> dict[str, Any]:
    """Save a session as a reusable template.

    Args:
        session: Session to save as template.
        info: Template name, description, and parameters.
        template_id: Unique template identifier.
        io: I/O context (directory and timestamp).

    Returns:
        Template metadata dictionary.
    """
    template_data: dict[str, Any] = {
        "id": template_id,
        "name": info.name,
        "description": info.description,
        "parameters": info.parameters or {},
        "session_data": session.to_dict(),
        "created_at": io.now,
    }
    io.templates_dir.mkdir(parents=True, exist_ok=True)
    path = io.templates_dir / f"{template_id}.json"
    path.write_text(json.dumps(template_data, indent=2))
    return template_data


def create_from_template(
    template_id: str,
    io: _TemplateIO,
    parameters: dict[str, Any] | None = None,
    tag: str | None = None,
) -> Session:
    """Create a new session from a saved template.

    Args:
        template_id: ID of template to use.
        io: I/O context (directory, new ID, timestamp).
        parameters: Values for template parameter substitution.
        tag: Optional tag for the new session.

    Returns:
        New Session instance.

    Raises:
        FileNotFoundError: If template doesn't exist.
    """
    path = io.templates_dir / f"{template_id}.json"
    if not path.exists():
        msg = f"Template not found: {template_id}"
        raise FileNotFoundError(msg)

    template_data = json.loads(path.read_text())
    session_data: Any = template_data["session_data"]

    if parameters:
        session_json = json.dumps(session_data)
        for param_name, param_value in parameters.items():
            placeholder = f"{{{{{param_name}}}}}"
            session_json = session_json.replace(placeholder, str(param_value))
        session_data = json.loads(session_json)

    session = session_from_dict(session_data)
    session.id = io.new_id
    session.started = io.now
    session.last_updated = io.now
    session.tag = tag
    session.template_id = template_id
    session.template_parameters = parameters or {}
    return session


# ---------------------------------------------------------------------------
# Listing and deletion
# ---------------------------------------------------------------------------


def _try_load_template(path: Path) -> dict[str, Any] | None:
    """Try to load template metadata from a file, or None on failure."""
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, KeyError):
        return None
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "description": data.get("description", ""),
        "parameters": data.get("parameters", {}),
        "created_at": data.get("created_at"),
    }


def list_templates(templates_dir: Path) -> list[dict[str, Any]]:
    """List available templates.

    Args:
        templates_dir: Directory containing templates.

    Returns:
        List of template metadata dictionaries.
    """
    if not templates_dir.exists():
        return []
    loaded = [_try_load_template(p) for p in templates_dir.glob("*.json")]
    return [t for t in loaded if t is not None]


def delete_template(templates_dir: Path, template_id: str) -> None:
    """Delete a template.

    Args:
        templates_dir: Directory containing templates.
        template_id: ID of template to delete.

    Raises:
        FileNotFoundError: If template doesn't exist.
    """
    path = templates_dir / f"{template_id}.json"
    if not path.exists():
        msg = f"Template not found: {template_id}"
        raise FileNotFoundError(msg)
    path.unlink()
