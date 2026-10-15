"""Voice runtime helpers for Tier 7 integrations."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from henchman.config.schema import VoiceSettings


class VoiceCommandError(RuntimeError):
    """Raised when a voice command cannot be resolved or executed."""


def _expand_command(
    template: list[str],
    *,
    text: str = "",
    input_path: Path | None = None,
    voice: str | None = None,
) -> list[str]:
    """Expand one command template using voice placeholders."""

    values = {
        "input": str(input_path) if input_path is not None else "",
        "text": text,
        "voice": voice or "",
    }
    return [expanded for part in template if (expanded := part.format(**values))]


def resolve_tts_command(settings: VoiceSettings) -> list[str] | None:
    """Resolve the active text-to-speech command template."""

    if settings.tts_command:
        return list(settings.tts_command)

    for executable in ("say", "espeak", "spd-say"):
        if shutil.which(executable):
            return [executable, "{text}"]
    return None


def resolve_stt_command(settings: VoiceSettings) -> list[str] | None:
    """Resolve the active speech-to-text command template."""

    if settings.stt_command:
        return list(settings.stt_command)
    return None


def describe_voice_runtime(settings: VoiceSettings) -> dict[str, object]:
    """Describe the currently configured or detected voice runtime."""

    return {
        "preferred_voice": settings.preferred_voice,
        "tts_command": resolve_tts_command(settings),
        "stt_command": resolve_stt_command(settings),
    }


def speak_text(text: str, settings: VoiceSettings) -> list[str]:
    """Speak text using the configured or auto-detected TTS runtime."""

    template = resolve_tts_command(settings)
    if template is None:
        msg = "No voice output command configured or detected."
        raise VoiceCommandError(msg)

    command = _expand_command(
        template,
        text=text,
        voice=settings.preferred_voice,
    )
    subprocess.run(command, check=True, capture_output=True, text=True)
    return command


def transcribe_audio(audio_path: Path, settings: VoiceSettings) -> str:
    """Transcribe one audio file using the configured STT runtime."""

    template = resolve_stt_command(settings)
    if template is None:
        msg = "No voice input command configured."
        raise VoiceCommandError(msg)

    command = _expand_command(
        template,
        input_path=audio_path,
        voice=settings.preferred_voice,
    )
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


__all__ = [
    "VoiceCommandError",
    "describe_voice_runtime",
    "resolve_stt_command",
    "resolve_tts_command",
    "speak_text",
    "transcribe_audio",
]
