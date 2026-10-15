"""Tests for Tier 7 integration commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from henchman.cli.app import cli


def _write(path: Path, content: str) -> None:
    """Write a test file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_ide_list_shows_supported_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`henchman ide list` should advertise the bundled IDE integrations."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)

    result = runner.invoke(cli, ["ide", "list"])

    assert result.exit_code == 0
    assert "vscode" in result.output
    assert "jetbrains" in result.output
    assert "export-only scaffolds" in result.output.lower()


@pytest.mark.parametrize(
    ("command_name", "target", "expected_file"),
    [
        ("desktop", "electron", "main.js"),
        ("mobile", "react-native", "App.js"),
        ("chrome", "chrome-extension", "manifest.json"),
    ],
)
def test_export_commands_write_expected_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command_name: str,
    target: str,
    expected_file: str,
) -> None:
    """Each Tier 7 export command should materialize its bundled scaffold."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)

    output_dir = project_root / "exports" / target
    result = runner.invoke(cli, [command_name, "export", target, str(output_dir)])

    assert result.exit_code == 0
    assert (output_dir / expected_file).is_file()
    assert "export-only" in result.output.lower()
    assert "does not launch" in result.output.lower()


@pytest.mark.parametrize("command_name", ["ide", "desktop", "mobile", "chrome"])
def test_integration_help_describes_export_only_surface(command_name: str) -> None:
    """Integration command help should describe scaffold export rather than runtime setup."""

    runner = CliRunner()

    result = runner.invoke(cli, [command_name, "--help"])

    assert result.exit_code == 0
    assert "export-only" in result.output.lower()
    assert "does not launch" in result.output.lower()


def test_voice_speak_uses_configured_tts_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`henchman voice speak` should execute the configured TTS command template."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)
    _write(
        project_root / ".henchman" / "settings.yaml",
        "voice:\n"
        "  tts_command:\n"
        "    - fake-tts\n"
        "    - '{text}'\n",
    )

    calls: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("henchman.integrations.voice.subprocess.run", fake_run)

    result = runner.invoke(cli, ["voice", "speak", "hello from tests"])

    assert result.exit_code == 0
    assert calls == [["fake-tts", "hello from tests"]]


def test_voice_transcribe_prints_stdout_from_configured_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`henchman voice transcribe` should print the configured STT command output."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)
    _write(
        project_root / ".henchman" / "settings.yaml",
        "voice:\n"
        "  stt_command:\n"
        "    - fake-stt\n"
        "    - '{input}'\n",
    )
    audio_path = project_root / "sample.wav"
    audio_path.write_bytes(b"RIFF-test")

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        assert command == ["fake-stt", str(audio_path)]
        return subprocess.CompletedProcess(command, 0, stdout="transcribed text\n", stderr="")

    monkeypatch.setattr("henchman.integrations.voice.subprocess.run", fake_run)

    result = runner.invoke(cli, ["voice", "transcribe", str(audio_path)])

    assert result.exit_code == 0
    assert result.output.strip() == "transcribed text"
