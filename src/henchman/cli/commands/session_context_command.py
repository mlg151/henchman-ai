"""Root Tier 2 session/context management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from henchman.core.session import Session, SessionManager
from henchman.core.session_context import SessionContextService
from henchman.core.session_memory import SessionMemoryService
from henchman.core.session_vcr import SessionVcrService


def _resolve_project_root(project_root: Path | None = None) -> Path:
    """Resolve the project root, falling back to cwd at invocation time.

    Args:
        project_root: Optional explicit project root.

    Returns:
        Resolved project root path.
    """
    return project_root or Path.cwd()


def _resolve_session(*, project_root: Path) -> tuple[SessionManager, str, Session]:
    """Resolve the active project session or raise a Click error."""

    manager = SessionManager()
    service = SessionContextService(manager)
    try:
        project_hash, session = service.resolve_active_session(project_root)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    return manager, project_hash, session


def _render_json(payload: dict[str, Any]) -> str:
    """Render a payload as deterministic JSON."""

    return json.dumps(payload, sort_keys=True)


def _render_context_snapshot(payload: dict[str, Any]) -> str:
    """Render a context snapshot in plain text."""

    tool_usage = payload["tool_usage"]
    lines = [
        f"Session: {payload['session_id']}",
        f"Tag: {payload['tag'] or '(untagged)'}",
        f"Turns: {payload['turn_count']}",
        f"Messages: {payload['message_count']}",
        f"Summaries: {payload['turn_summary_count']}",
        f"Memories: {payload['memory_count']}",
        f"Estimated tokens: {payload['token_estimate']}",
        f"Plan mode: {'on' if payload['plan_mode'] else 'off'}",
        (
            "Tool usage: "
            f"{tool_usage['total_calls']} call(s), {tool_usage['total_results']} result(s)"
        ),
    ]
    return "\n".join(lines) + "\n"


def _render_compaction(payload: dict[str, Any]) -> str:
    """Render a compaction or rewind operation payload in plain text."""

    if payload.get("operation") == "rewind":
        return (
            "Rewound session "
            f"{payload['session_id']}: removed {payload['removed_turns']} turn(s), "
            f"{payload['remaining_turns']} turn(s) remain.\n"
        )
    if payload.get("operation") == "teleport":
        return (
            f"Teleported to turn {payload['turn_number']} via session {payload['session_id']}.\n"
        )
    if not payload.get("changed", True):
        return f"Session {payload['session_id']} already fits within the preserved-turn window.\n"
    return (
        f"Compacted session {payload['session_id']}: removed {payload['removed_turns']} "
        f"turn(s) and preserved {payload['preserved_turns']} turn(s).\n"
    )


def _render_memory_payload(payload: dict[str, Any]) -> str:
    """Render a memory payload in plain text."""

    memories = payload.get("memories", [])
    operation = payload.get("operation", "list")
    if operation == "delete":
        return (
            f"{'Deleted' if payload.get('deleted') else 'Did not find'} memory "
            f"{payload['memory_id']}.\n"
        )
    if not memories:
        return "No session memories.\n"
    lines = [f"Session memories ({len(memories)}):"]
    for memory in memories:
        lines.append(f"- {memory['id']}: {memory['content']}")
    return "\n".join(lines) + "\n"


def _render_transcript(payload: dict[str, Any]) -> str:
    """Render a transcript payload in plain text."""

    return f"{payload['transcript']}\n"


def _render_playback(payload: dict[str, Any]) -> str:
    """Render a playback payload in plain text."""

    lines = [f"Playback for session {payload['session_id']}:"]
    for event in payload["events"]:
        if event["type"] == "summary":
            lines.append(f"- [summary] {event['summary']}")
        else:
            role = event["role"]
            content = event.get("content") or ""
            lines.append(f"- [{role}] {content}")
    return "\n".join(lines) + "\n"


def create_context_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root ``context`` command group."""

    @click.group(
        name="context",
        help="View and manage the current session context.",
        invoke_without_command=True,
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the context snapshot as text or JSON.",
    )
    @click.pass_context
    def context_command(ctx: click.Context, output_format: str) -> None:
        if ctx.invoked_subcommand is not None:
            return
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        snapshot = SessionContextService(manager).build_snapshot(session).to_dict()
        click.echo(
            _render_json(snapshot) if output_format == "json" else _render_context_snapshot(snapshot),
            nl=False,
        )

    @context_command.command(name="transcript", help="Render the current session transcript.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the transcript as text or JSON.",
    )
    def transcript_command(output_format: str) -> None:
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        transcript = SessionContextService(manager).render_transcript(session)
        payload = {"session_id": session.id, "transcript": transcript}
        click.echo(
            _render_json(payload) if output_format == "json" else _render_transcript(payload),
            nl=False,
        )

    @context_command.command(name="playback", help="Render a playback/VCR view of the session.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render playback events as text or JSON.",
    )
    def playback_command(output_format: str) -> None:
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        payload = SessionVcrService().build_playback(session)
        click.echo(
            _render_json(payload) if output_format == "json" else _render_playback(payload),
            nl=False,
        )

    return context_command


def create_compact_command(*, project_root: Path | None = None) -> click.Command:
    """Create the root ``compact`` command."""

    @click.command(name="compact", help="Compact older session context into summaries.")
    @click.option("--preserve-turns", type=int, default=2, show_default=True)
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
    )
    def compact_command(preserve_turns: int, output_format: str) -> None:
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        result = SessionContextService(manager).compact_session(session, preserve_turns=preserve_turns)
        manager.save(session)
        payload = {
            "operation": "compact",
            "session_id": session.id,
            **result.to_dict(),
        }
        click.echo(
            _render_json(payload) if output_format == "json" else _render_compaction(payload),
            nl=False,
        )

    return compact_command


def create_rewind_command(*, project_root: Path | None = None) -> click.Command:
    """Create the root ``rewind`` command."""


    @click.command(name="rewind", help="Undo the last N turns in the active session.")
    @click.argument("turns", type=int)
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
    )
    def rewind_command(turns: int, output_format: str) -> None:
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        try:
            result = SessionContextService(manager).rewind_session(session, turns=turns)
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        manager.save(session)
        payload = {
            "operation": "rewind",
            "session_id": session.id,
            **result.to_dict(),
        }
        click.echo(
            _render_json(payload) if output_format == "json" else _render_compaction(payload),
            nl=False,
        )

    return rewind_command


def create_memory_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root ``memory`` command group."""

    memory_service = SessionMemoryService()

    @click.group(
        name="memory",
        help="View and manage per-session memories.",
        invoke_without_command=True,
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render the memory list as text or JSON.",
    )
    @click.pass_context
    def memory_command(ctx: click.Context, output_format: str) -> None:
        if ctx.invoked_subcommand is not None:
            return
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        payload = {
            "operation": "list",
            "session_id": session.id,
            "memories": [memory.to_dict() for memory in memory_service.list_memories(session)],
        }
        click.echo(
            _render_json(payload) if output_format == "json" else _render_memory_payload(payload),
            nl=False,
        )

    @memory_command.command(name="list", help="List stored memories for the active session.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
    )
    def list_command(output_format: str) -> None:
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        payload = {
            "operation": "list",
            "session_id": session.id,
            "memories": [memory.to_dict() for memory in memory_service.list_memories(session)],
        }
        click.echo(
            _render_json(payload) if output_format == "json" else _render_memory_payload(payload),
            nl=False,
        )

    @memory_command.command(name="add", help="Add one memory to the active session.")
    @click.argument("content", nargs=-1, required=True)
    @click.option(
        "--kind",
        type=click.Choice(("note", "preference"), case_sensitive=False),
        default="note",
        show_default=True,
    )
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
    )
    def add_command(content: tuple[str, ...], kind: str, output_format: str) -> None:
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        record = memory_service.add_memory(session, content=" ".join(content), kind=kind, source="manual")
        manager.save(session)
        payload = {"operation": "add", "session_id": session.id, "memories": [record.to_dict()]}
        click.echo(
            _render_json(payload) if output_format == "json" else _render_memory_payload(payload),
            nl=False,
        )

    @memory_command.command(name="delete", help="Delete one memory from the active session.")
    @click.argument("memory_id")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
    )
    def delete_command(memory_id: str, output_format: str) -> None:
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        deleted = memory_service.delete_memory(session, memory_id)
        manager.save(session)
        payload = {
            "operation": "delete",
            "session_id": session.id,
            "memory_id": memory_id,
            "deleted": deleted,
        }
        click.echo(
            _render_json(payload) if output_format == "json" else _render_memory_payload(payload),
            nl=False,
        )

    @memory_command.command(name="extract", help="Extract memory candidates from session history.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
    )
    def extract_command(output_format: str) -> None:
        manager, _project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        created = memory_service.extract_memories(session)
        manager.save(session)
        payload = {
            "operation": "extract",
            "session_id": session.id,
            "memories": [memory.to_dict() for memory in created],
        }
        click.echo(
            _render_json(payload) if output_format == "json" else _render_memory_payload(payload),
            nl=False,
        )

    return memory_command


def create_teleport_command(*, project_root: Path | None = None) -> click.Command:
    """Create the root ``teleport`` command."""


    @click.command(name="teleport", help="Jump to a turn by branching the active session.")
    @click.argument("turn_number", type=int)
    @click.option("--tag", default=None, help="Optional tag for the new teleported session.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
    )
    def teleport_command(turn_number: int, tag: str | None, output_format: str) -> None:
        manager, project_hash, session = _resolve_session(project_root=_resolve_project_root(project_root))
        service = SessionContextService(manager)
        try:
            branch = service.branch_for_turn(
                session,
                turn_number=turn_number,
                tag=tag or f"teleport-turn-{turn_number}",
            )
        except ValueError as error:
            raise click.ClickException(str(error)) from error
        manager.save(branch)
        manager.set_project_current(project_hash, branch.id)
        payload = {
            "operation": "teleport",
            "session_id": branch.id,
            "source_session_id": session.id,
            "turn_number": turn_number,
            "tag": branch.tag,
        }
        click.echo(
            _render_json(payload) if output_format == "json" else _render_compaction(payload),
            nl=False,
        )

    return teleport_command


__all__ = [
    "create_compact_command",
    "create_context_command",
    "create_memory_command",
    "create_rewind_command",
    "create_teleport_command",
    "register_session_context_commands",
]


def register_session_context_commands(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> None:
    """Register session context commands on a root click group.

    Args:
        cli: Root click group that should expose the session context commands.
        project_root: Optional project root for deterministic tests.
    """
    cli.add_command(create_context_command(project_root=project_root))
    cli.add_command(create_compact_command(project_root=project_root))
    cli.add_command(create_rewind_command(project_root=project_root))
    cli.add_command(create_memory_command(project_root=project_root))
    cli.add_command(create_teleport_command(project_root=project_root))
