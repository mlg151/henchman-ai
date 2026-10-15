"""Tests for Tier 7 integration settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.config import load_settings


def test_load_settings_supports_tier7_integration_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier 7 integration settings should validate through the strict schema."""

    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    config_dir = project_root / ".henchman"
    config_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    (config_dir / "settings.yaml").write_text(
        "chat:\n"
        "  discord:\n"
        "    mention_only: false\n"
        "    allowed_channel_ids:\n"
        "      - '1234'\n"
        "  slack:\n"
        "    enabled: true\n"
        "    signing_secret: test-secret\n"
        "voice:\n"
        "  preferred_voice: Alloy\n"
        "  tts_command:\n"
        "    - fake-tts\n"
        "    - '{text}'\n"
        "  stt_command:\n"
        "    - fake-stt\n"
        "    - '{input}'\n",
        encoding="utf-8",
    )

    settings = load_settings(project_root=project_root)

    assert settings.chat.discord.mention_only is False
    assert settings.chat.discord.allowed_channel_ids == ["1234"]
    assert settings.chat.slack.enabled is True
    assert settings.chat.slack.signing_secret == "test-secret"
    assert settings.voice.preferred_voice == "Alloy"
    assert settings.voice.tts_command == ["fake-tts", "{text}"]
    assert settings.voice.stt_command == ["fake-stt", "{input}"]
