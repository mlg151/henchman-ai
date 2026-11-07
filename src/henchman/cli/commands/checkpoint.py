"""Shared user checkpoint review commands for CLI, REPL and Textual."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import click

from henchman.advanced.checkpoint_models import CheckpointReview
from henchman.advanced.checkpoints import CheckpointConflict, CheckpointService
from henchman.cli.commands import Command, CommandContext
from henchman.cli.evidence import runtime_evidence_redactor
from henchman.config.repository import SettingsRepository
from henchman.utils.evidence_redaction import EvidenceRedactor


def _review_payload(review: CheckpointReview) -> dict[str, Any]:
    """Present bounded text hunks; truncation never changes restore authority."""
    remaining = 65536
    remaining_hunks = 256
    files = []
    for item in review.files:
        hunks = []
        for hunk in item.hunks[:remaining_hunks]:
            payload = asdict(hunk)
            truncated = False
            for key in ("before", "after"):
                value = payload[key]
                shown = value[:remaining]
                remaining -= len(shown)
                payload[key] = shown
                truncated |= shown != value
            payload["text_truncated"] = truncated
            hunks.append(payload)
        remaining_hunks -= len(hunks)
        files.append({
            "path": item.path, "decision": item.decision, "restorable": item.restorable,
            "before": {"status": item.before.status, "bytes": len(item.before.content or b"")},
            "after": {"status": item.after.status, "bytes": len(item.after.content or b"")},
            "hunk_status": item.hunk_status, "hunks": hunks,
            "hunks_omitted": len(item.hunks) - len(hunks),
        })
    return {"checkpoint_id": review.checkpoint_id, "revision": review.revision, "files": files, "metadata_policy": review.metadata_policy}


def create_checkpoint_command(
    *, project_root: Path | None = None, redactor: EvidenceRedactor | None = None,
    output: Callable[[str], None] | None = None,
) -> click.Group:
    """Build user actions around the same revision-bound checkpoint service."""
    emit = output or click.echo

    def perform(action: Callable[[CheckpointService], Any]) -> None:
        policy = redactor or EvidenceRedactor()
        try:
            root = project_root or Path.cwd()
            policy.register_policy(SettingsRepository(root).evidence_redactor())
            service = CheckpointService(root, redactor=policy)
            result = action(service)
            # The service exposes only eligible text. Project output again for
            # dynamic credentials in identifiers, actors and diagnostic metadata.
            emit(json.dumps(policy.redact(result), indent=2, ensure_ascii=True))
        except (OSError, ValueError, CheckpointConflict) as error:
            paths = ", ".join(error.paths) if isinstance(error, CheckpointConflict) else ""
            detail = f"{error}: {paths}" if paths else str(error)
            raise click.ClickException(policy.text(detail)) from None

    @click.group(name="checkpoint", help="Review captured file changes and apply a conflict-checked decision.")
    def group() -> None:
        pass

    @group.command(name="list")
    def list_command() -> None:
        """List captures and interrupted restore plans."""
        perform(lambda service: {
            "checkpoints": [asdict(record) for record in service.list_checkpoints()],
            "pending_restores": service.pending_restores(),
        })

    @group.command(name="show")
    @click.argument("checkpoint_id")
    def show_command(checkpoint_id: str) -> None:
        """Show file status and numbered text hunks."""
        perform(lambda service: _review_payload(service.review(checkpoint_id)))

    @group.command(name="preview")
    @click.argument("checkpoint_id")
    @click.argument("decision", type=click.Choice(("accept", "reject")))
    @click.option("--path", "paths", multiple=True, help="Select a captured relative file; repeat for multiple files.")
    @click.option("--hunk", "hunks", multiple=True, type=click.IntRange(min=0), help="Select a numbered hunk in exactly one --path.")
    def preview_command(checkpoint_id: str, decision: str, paths: tuple[str, ...], hunks: tuple[int, ...]) -> None:
        """Record a preview without changing workspace files."""
        if hunks and len(paths) != 1:
            raise click.UsageError("Hunk selection requires exactly one --path.")
        perform(lambda service: asdict(service.preview(
            checkpoint_id, decision=decision, paths=(paths or None) if not hunks else None,
            hunks={paths[0]: hunks} if hunks else None,
        )))

    @group.command(name="apply")
    @click.argument("plan_id")
    def apply_command(plan_id: str) -> None:
        """Apply a preview, reporting conflicts instead of overwriting edits."""
        perform(lambda service: asdict(service.apply(plan_id)))

    @group.command(name="recover")
    @click.argument("plan_id")
    def recover_command(plan_id: str) -> None:
        """Continue a previously interrupted restore after checking its journal."""
        perform(lambda service: asdict(service.recover(plan_id)))

    @group.command(name="discard")
    @click.argument("checkpoint_id")
    def discard_command(checkpoint_id: str) -> None:
        """Delete capture/history and retained originals unless recovery is pending."""
        def discard(service: CheckpointService) -> dict[str, str]:
            service.discard(checkpoint_id)
            return {"discarded": checkpoint_id}
        perform(discard)

    @group.command(name="prune")
    def prune_command() -> None:
        """Apply retention while preserving active captures and pending restores."""
        def prune(service: CheckpointService) -> dict[str, bool]:
            service.prune()
            return {"retention_applied": True}
        perform(prune)

    return group


class CheckpointCommand(Command):
    """Expose the shared review actions through either interactive frontend."""

    @property
    def name(self) -> str:
        return "checkpoint"

    @property
    def description(self) -> str:
        return "Review captured files/hunks and apply or recover a previewed decision"

    @property
    def usage(self) -> str:
        return "/checkpoint list|show|preview|apply|recover|discard|prune"

    async def execute(self, ctx: CommandContext) -> None:
        runtime = ctx.repl if ctx.repl is not None else ctx
        policy = runtime_evidence_redactor(runtime)
        def emit(text: str) -> None:
            ctx.console.print(text, markup=False, highlight=False)
        messages: list[str] = []
        command = create_checkpoint_command(redactor=policy, output=messages.append)
        if not ctx.args or "--help" in ctx.args:
            with click.Context(command) as context:
                target = command.get_command(context, ctx.args[0]) if ctx.args else None
                emit((target or command).get_help(context))
            return
        worker = asyncio.create_task(asyncio.to_thread(
            command.main, args=ctx.args, prog_name="/checkpoint", standalone_mode=False,
        ))
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            # A filesystem transaction already authorized by the user owns its
            # worker until it settles. Never leave it mutating after UI cleanup.
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    continue
                except BaseException:
                    break
            if not worker.cancelled():
                worker.exception()
            raise
        except click.ClickException as error:
            emit(policy.text(f"Checkpoint unavailable: {error.format_message()}"))
        for message in messages:
            emit(message)
