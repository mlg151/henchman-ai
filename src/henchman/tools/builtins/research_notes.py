"""Research notes tool - persistent in-session note-taking scratchpad."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult

_DEFAULT_NOTES_DIR = Path.home() / ".henchman" / "notes"
_VALID_ACTIONS = {"write", "append", "read", "list", "search"}


@dataclass
class ResearchNotesParams:
    """Parameters for research notes action."""
    action: str
    tag: str
    content: str
    query: str
    notes_dir: Path | None = None


def _get_notes_dir(notes_dir: Path | None = None) -> Path:
    """Return the notes directory, creating it if needed.

    Args:
        notes_dir: Custom notes directory path, or None to use default.

    Returns:
        Path to the notes directory (guaranteed to exist).
    """
    directory = notes_dir or _DEFAULT_NOTES_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _note_path(tag: str, notes_dir: Path) -> Path:
    """Return the file path for a note with the given tag.

    Args:
        tag: Note tag (used as the filename base).
        notes_dir: Directory where notes are stored.

    Returns:
        Path object for the note file.
    """
    safe_tag = "".join(c if c.isalnum() or c in "-_." else "_" for c in tag)
    return notes_dir / f"{safe_tag}.json"


def _load_note(tag: str, notes_dir: Path) -> dict[str, str]:
    """Load an existing note as a dict, or return empty dict.

    Args:
        tag: Note tag to load.
        notes_dir: Directory where notes are stored.

    Returns:
        Dict with 'content', 'tag', and 'updated_at' keys, or empty dict.
    """
    path = _note_path(tag, notes_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def _save_note(tag: str, content: str, notes_dir: Path) -> None:
    """Persist a note to disk.

    Args:
        tag: Note tag (used as identifier and filename).
        content: Note content to save.
        notes_dir: Directory where notes are stored.
    """
    path = _note_path(tag, notes_dir)
    data = {
        "tag": tag,
        "content": content,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _action_write(tag: str, content: str, notes_dir: Path) -> ToolResult:
    """Write (create or overwrite) a note.

    Args:
        tag: Note identifier.
        content: Content to write.
        notes_dir: Notes storage directory.

    Returns:
        ToolResult confirming the write.
    """
    _save_note(tag, content, notes_dir)
    return ToolResult(content=f"Note '{tag}' written ({len(content)} chars).", success=True)


def _action_append(tag: str, content: str, notes_dir: Path) -> ToolResult:
    """Append content to an existing note (creates it if absent).

    Args:
        tag: Note identifier.
        content: Content to append.
        notes_dir: Notes storage directory.

    Returns:
        ToolResult confirming the append.
    """
    existing = _load_note(tag, notes_dir)
    existing_content = existing.get("content", "")
    separator = "\n" if existing_content and not existing_content.endswith("\n") else ""
    new_content = existing_content + separator + content
    _save_note(tag, new_content, notes_dir)
    return ToolResult(
        content=f"Appended {len(content)} chars to note '{tag}' (total: {len(new_content)}).",
        success=True,
    )


def _action_read(tag: str, notes_dir: Path) -> ToolResult:
    """Read the content of a note.

    Args:
        tag: Note identifier.
        notes_dir: Notes storage directory.

    Returns:
        ToolResult with the note content, or error if not found.
    """
    note = _load_note(tag, notes_dir)
    if not note:
        return ToolResult(
            content=f"Note '{tag}' not found.",
            success=False,
            error=f"Note not found: {tag}",
        )
    updated = note.get("updated_at", "unknown")
    return ToolResult(
        content=f"# Note: {tag}\n_Last updated: {updated}_\n\n{note.get('content', '')}",
        success=True,
    )


def _action_list(notes_dir: Path) -> ToolResult:
    """List all notes in the notes directory.

    Args:
        notes_dir: Notes storage directory.

    Returns:
        ToolResult with a formatted list of all notes.
    """
    note_files = sorted(notes_dir.glob("*.json"))
    if not note_files:
        return ToolResult(content="No notes found.", success=True)

    rows: list[str] = ["# Notes\n", "| Tag | Updated | Size |", "| --- | --- | --- |"]
    for nf in note_files:
        try:
            data = json.loads(nf.read_text(encoding="utf-8"))
            tag = data.get("tag", nf.stem)
            updated = data.get("updated_at", "?")[:19]
            size = len(data.get("content", ""))
            rows.append(f"| {tag} | {updated} | {size} chars |")
        except (json.JSONDecodeError, OSError):
            rows.append(f"| {nf.stem} | ? | ? |")

    return ToolResult(content="\n".join(rows), success=True)


def _action_search(query: str, notes_dir: Path) -> ToolResult:
    """Search note contents for a query string.

    Args:
        query: Search string to look for in note contents.
        notes_dir: Notes storage directory.

    Returns:
        ToolResult with matching notes and excerpt context.
    """
    query_lower = query.lower()
    note_files = sorted(notes_dir.glob("*.json"))
    matches: list[str] = []

    for nf in note_files:
        try:
            data = json.loads(nf.read_text(encoding="utf-8"))
            content = data.get("content", "")
            if query_lower in content.lower():
                tag = data.get("tag", nf.stem)
                # Find first matching line as excerpt
                for line in content.splitlines():
                    if query_lower in line.lower():
                        excerpt = line.strip()[:100]
                        matches.append(f"- **{tag}**: `{excerpt}`")
                        break
        except (json.JSONDecodeError, OSError):
            continue

    if not matches:
        return ToolResult(content=f"No notes contain '{query}'.", success=True)

    return ToolResult(
        content=f"# Search results for '{query}'\n\n" + "\n".join(matches),
        success=True,
    )


def _execute_research_notes(params: ResearchNotesParams) -> ToolResult:
    """Dispatch a research notes action.

    Args:
        params: ResearchNotesParams containing action, tag, content, query, notes_dir.

    Returns:
        ToolResult appropriate to the action.
    """
    if params.action not in _VALID_ACTIONS:
        return ToolResult(
            content=f"Error: invalid action '{params.action}'. Valid: {sorted(_VALID_ACTIONS)}",
            success=False,
            error=f"Invalid action: {params.action}",
        )

    nd = _get_notes_dir(params.notes_dir)

    # Validate parameters based on action
    error_msg = None
    if params.action == "search" and not params.query:
        error_msg = "query is required for search action"
    elif params.action in {"read", "write", "append"} and not params.tag:
        error_msg = f"tag is required for action '{params.action}'"
    elif params.action in {"write", "append"} and not params.content:
        error_msg = f"content is required for action '{params.action}'"

    if error_msg:
        return ToolResult(content=f"Error: {error_msg}", success=False, error=error_msg)

    # Dispatch to appropriate action handler
    if params.action == "list":
        return _action_list(nd)
    if params.action == "search":
        return _action_search(params.query, nd)

    # Note-specific actions (read, write, append)
    if params.action == "read":
        return _action_read(params.tag, nd)

    action_func = _action_write if params.action == "write" else _action_append
    return action_func(params.tag, params.content, nd)


class ResearchNotesTool(Tool):
    """Persistent in-session note-taking scratchpad for research findings.

    Provides a simple key-value note store persisted to disk at
    ~/.henchman/notes/. Useful for accumulating research findings,
    hypotheses, and decisions across multiple agent turns. Notes
    persist for the life of the notes directory.

    Actions:
        write:  Create or overwrite a note by tag.
        append: Append content to an existing note (creates if absent).
        read:   Read the content of a note by tag.
        list:   List all stored notes with timestamps and sizes.
        search: Search note contents for a query string.
    """

    _parameters: ClassVar[dict[str, object]] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Action: 'write', 'append', 'read', 'list', or 'search'",
                "enum": ["write", "append", "read", "list", "search"],
            },
            "tag": {
                "type": "string",
                "description": "Note identifier/name (required for write/append/read)",
            },
            "content": {
                "type": "string",
                "description": "Note content (required for write/append)",
            },
            "query": {
                "type": "string",
                "description": "Search query (required for search)",
            },
        },
        "required": ["action"],
    }

    @property
    def name(self: ResearchNotesTool) -> str:
        """Tool name."""
        return "research_notes"

    @property
    def description(self: ResearchNotesTool) -> str:
        """Tool description."""
        return (
            "Persistent in-session note-taking scratchpad. Write, append, read, list, "
            "or search named notes stored in ~/.henchman/notes/. Use to accumulate "
            "research findings and decisions across multiple agent turns."
        )

    @property
    def kind(self: ResearchNotesTool) -> ToolKind:
        """Tool kind - WRITE (note persistence modifies files on disk)."""
        return ToolKind.WRITE

    def needs_confirmation(
        self: ResearchNotesTool,
        params: dict[str, object],
    ) -> ConfirmationRequest | None:
        """Only write/append actions need confirmation; reads are auto-approved.

        Args:
            params: Tool parameters including 'action'.

        Returns:
            ConfirmationRequest for write/append, None for read/list/search.
        """
        if params.get("action") in {"write", "append"}:
            return super().needs_confirmation(params)
        return None

    async def execute(  # type: ignore[override]
        self: ResearchNotesTool,
        action: str = "",
        tag: str = "",
        content: str = "",
        query: str = "",
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Execute a research notes action.

        Args:
            action: Action to perform ('write', 'append', 'read', 'list', 'search').
            tag: Note identifier (required for write/append/read).
            content: Content for write/append actions.
            query: Search query for search action.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult appropriate to the action.
        """
        return _execute_research_notes(
            ResearchNotesParams(
                action=action,
                tag=tag,
                content=content,
                query=query,
                notes_dir=None
            )
        )
