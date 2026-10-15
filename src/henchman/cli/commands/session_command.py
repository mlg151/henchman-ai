"""Root CLI commands for saved session management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from henchman.core.session import Session, SessionManager


def _resolve_project_root(project_root: Path | None = None) -> Path:
    """Resolve the project root, falling back to cwd at invocation time.

    Args:
        project_root: Optional explicit project root.

    Returns:
        Resolved project root path.
    """
    return project_root or Path.cwd()


def create_session_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root ``session`` command group."""

    @click.group(
        name="session",
        help="List, switch, and delete saved sessions for the current project.",
        invoke_without_command=True,
    )
    @click.pass_context
    def session_command(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @session_command.command(name="list", help="List saved sessions.")
    @click.option(
        "--all-projects",
        is_flag=True,
        default=False,
        help="List saved sessions across all projects instead of the current project only.",
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the session list as text or JSON.",
    )
    def list_command(*, all_projects: bool, output_format: str) -> None:
        manager = SessionManager()
        resolved = _resolve_project_root(project_root)
        project_hash = None if all_projects else manager.compute_project_hash(resolved)
        current_session_id = None
        if project_hash is not None:
            current_session_id = manager.get_project_current(project_hash)

        payload = {
            "project_hash": project_hash,
            "sessions": [
                {
                    "id": metadata.id,
                    "tag": metadata.tag,
                    "message_count": metadata.message_count,
                    "started": metadata.started,
                    "last_updated": metadata.last_updated,
                    "current": metadata.id == current_session_id,
                }
                for metadata in manager.list_sessions(project_hash=project_hash)
            ],
        }
        click.echo(_render_list_payload(payload, output_format=output_format), nl=False)

    @session_command.command(name="switch", help="Select the current session for this project.")
    @click.argument("selector")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the result as text or JSON.",
    )
    def switch_command(selector: str, output_format: str) -> None:
        manager = SessionManager()
        resolved = _resolve_project_root(project_root)
        project_hash = manager.compute_project_hash(resolved)
        session = _resolve_session(manager=manager, selector=selector, project_hash=project_hash)
        manager.set_project_current(project_hash, session.id)
        payload = {
            "operation": "switch",
            "project_hash": project_hash,
            "session_id": session.id,
            "tag": session.tag,
        }
        click.echo(_render_operation_payload(payload, output_format=output_format), nl=False)

    @session_command.command(name="delete", help="Delete one saved session.")
    @click.argument("selector")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the result as text or JSON.",
    )
    def delete_command(selector: str, output_format: str) -> None:
        manager = SessionManager()
        resolved = _resolve_project_root(project_root)
        project_hash = manager.compute_project_hash(resolved)
        session = _resolve_session(manager=manager, selector=selector, project_hash=project_hash)
        manager.delete(session.id)
        if manager.get_project_current(project_hash) == session.id:
            manager.clear_project_current(project_hash)
        payload = {
            "operation": "delete",
            "project_hash": project_hash,
            "session_id": session.id,
            "tag": session.tag,
        }
        click.echo(_render_operation_payload(payload, output_format=output_format), nl=False)

    return session_command


def create_resume_command(*, project_root: Path | None = None) -> click.Command:
    """Create the root ``resume`` command."""

    @click.command(name="resume", help="Resume a saved session by ID, ID prefix, or tag.")
    @click.argument("selector")
    @click.option("-p", "--prompt", help="Run with a single prompt and exit")
    @click.option("-a", "--agent", help="Target a specific specialist agent")
    @click.option("--team", is_flag=True, help="Show team information and exit")
    @click.option(
        "--output-format",
        type=click.Choice(["text", "json", "stream-json", "json-complete"]),
        default="text",
        help="Output format for responses",
    )
    @click.option(
        "--plan",
        is_flag=True,
        default=False,
        help="Start in plan mode (read-only)",
    )
    @click.option(
        "--debug",
        is_flag=True,
        default=False,
        help="Enable debug output",
    )
    @click.option(
        "-y",
        "--yes",
        is_flag=True,
        default=False,
        help="Auto-approve all tool executions (non-interactive mode)",
    )
    @click.option(
        "--tui",
        is_flag=True,
        default=False,
        help="Use Textual TUI interface (experimental)",
    )
    def resume_command(selector: str, **kwargs: Any) -> None:
        manager = SessionManager()
        resolved = _resolve_project_root(project_root)
        project_hash = manager.compute_project_hash(resolved)
        session = _resolve_session(manager=manager, selector=selector, project_hash=project_hash)
        manager.set_project_current(project_hash, session.id)

        from henchman.cli.app import RunConfig, _execute_chat_command

        config = RunConfig(
            prompt=kwargs.get("prompt"),
            agent_role=kwargs.get("agent"),
            team=kwargs.get("team", False),
            output_format=kwargs.get("output_format", "text"),
            plan_mode=kwargs.get("plan", False),
            yes=kwargs.get("yes", False),
            tui=kwargs.get("tui", False),
            debug=kwargs.get("debug", False),
        )
        _execute_chat_command(config)

    return resume_command


def _resolve_session(
    *,
    manager: SessionManager,
    selector: str,
    project_hash: str,
) -> Session:
    """Resolve a session selector to a saved session."""

    tagged_session = manager.load_by_tag(selector, project_hash=project_hash)
    if tagged_session is not None:
        return tagged_session

    try:
        return manager.load(selector)
    except (FileNotFoundError, ValueError) as error:
        raise click.ClickException(str(error)) from error


def _render_list_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render the list payload in one of the supported formats."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)

    sessions = payload["sessions"]
    if not sessions:
        if payload["project_hash"] is None:
            return "No saved sessions.\n"
        return "No saved sessions for the current project.\n"

    lines = ["Saved sessions:"]
    for session in sessions:
        current_marker = "*" if session["current"] else "-"
        tag_text = session["tag"] or "(untagged)"
        lines.append(
            (
                f"{current_marker} {session['id'][:8]} {tag_text} "
                f"({session['message_count']} messages, updated {session['last_updated'][:10]})"
            ),
        )
    return "\n".join(lines) + "\n"


def _render_operation_payload(payload: dict[str, Any], *, output_format: str) -> str:
    """Render a switch/delete payload in one of the supported formats."""

    if output_format == "json":
        return json.dumps(payload, sort_keys=True)

    tag_text = f" ({payload['tag']})" if payload.get("tag") else ""
    verb = {"switch": "Switched", "delete": "Deleted"}.get(
        str(payload.get("operation")),
        "Updated",
    )
    return f"{verb} session {payload['session_id']}{tag_text}.\n"


__all__ = ["create_resume_command", "create_session_command", "register_session_command"]


def register_session_command(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> click.Command:
    """Register the session command group on a root click group.

    Args:
        cli: Root click group that should expose the session command.
        project_root: Optional project root for deterministic tests.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_session_command(project_root=project_root)
    cli.add_command(command)
    return command


def register_resume_command(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> click.Command:
    """Register the resume command on a root click group.

    Args:
        cli: Root click group that should expose the resume command.
        project_root: Optional project root for deterministic tests.

    Returns:
        The command instance added to ``cli``.
    """
    command = create_resume_command(project_root=project_root)
    cli.add_command(command)
    return command
