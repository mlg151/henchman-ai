"""CLI command for Tier 7 voice integrations."""

from __future__ import annotations

import json
from pathlib import Path

import click

from henchman.config import load_settings
from henchman.integrations.voice import (
    VoiceCommandError,
    describe_voice_runtime,
    speak_text,
    transcribe_audio,
)


def _resolve_project_root(project_root: Path | None = None) -> Path:
    """Resolve the project root, falling back to cwd at invocation time.

    Args:
        project_root: Optional explicit project root.

    Returns:
        Resolved project root path.
    """
    return project_root or Path.cwd()


def create_voice_command(*, project_root: Path | None = None) -> click.Group:
    """Create the root `voice` command group."""

    @click.group(
        name="voice",
        help="Inspect and run local voice input/output integrations.",
        invoke_without_command=True,
    )
    @click.pass_context
    def voice_command(ctx: click.Context) -> None:
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @voice_command.command(name="doctor", help="Show configured and detected voice runtimes.")
    @click.option(
        "--format",
        "output_format",
        type=click.Choice(("text", "json"), case_sensitive=False),
        default="text",
        show_default=True,
        help="Render voice runtime details as text or JSON.",
    )
    def doctor_command(output_format: str) -> None:
        settings = load_settings(project_root=_resolve_project_root(project_root))
        payload = describe_voice_runtime(settings.voice)
        if output_format == "json":
            click.echo(json.dumps(payload, sort_keys=True))
            return

        click.echo(
            "\n".join(
                [
                    "Voice runtime:",
                    f"- preferred_voice: {payload['preferred_voice'] or 'unset'}",
                    f"- tts_command: {payload['tts_command'] or 'unconfigured'}",
                    f"- stt_command: {payload['stt_command'] or 'unconfigured'}",
                ],
            ),
        )

    @voice_command.command(name="speak", help="Speak one line of text.")
    @click.argument("text")
    def speak_command(text: str) -> None:
        settings = load_settings(project_root=_resolve_project_root(project_root))
        try:
            command = speak_text(text, settings.voice)
        except VoiceCommandError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(f"Executed {' '.join(command)}")

    @voice_command.command(name="transcribe", help="Transcribe one audio file.")
    @click.argument(
        "audio_path",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
    )
    def transcribe_command(audio_path: Path) -> None:
        settings = load_settings(project_root=_resolve_project_root(project_root))
        try:
            transcript = transcribe_audio(audio_path, settings.voice)
        except VoiceCommandError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(transcript)

    return voice_command


def register_voice_command(
    cli: click.Group,
    *,
    project_root: Path | None = None,
) -> click.Group:
    """Register the voice command group on a root click group.

    Args:
        cli: Root click group that should expose the voice command.
        project_root: Optional project root for deterministic tests.

    Returns:
        The command group instance added to ``cli``.
    """
    command = create_voice_command(project_root=project_root)
    cli.add_command(command)
    return command
