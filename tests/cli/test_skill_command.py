"""Tests for the root skill command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from henchman.cli.app import cli


def _write(path: Path, content: str) -> None:
    """Write a test file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_skill_list_discovers_compatible_skills(tmp_path: Path, monkeypatch) -> None:
    """`henchman skill list` should show skills from supported ecosystems."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)

    _write(
        project_root / ".github" / "skills" / "linting" / "SKILL.md",
        """---
name: linting
description: Run the linter
---
# Linting
""",
    )
    _write(
        project_root / ".gemini" / "commands" / "release.toml",
        '''description = "Prepare a release"
prompt = """
Draft the release checklist.
"""
''',
    )

    result = runner.invoke(cli, ["skill", "list"])

    assert result.exit_code == 0
    assert "linting" in result.output
    assert "release" in result.output


def test_skill_show_renders_skill_details(tmp_path: Path, monkeypatch) -> None:
    """`henchman skill show` should print the resolved skill instructions."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)

    _write(
        project_root / ".henchman" / "skills" / "deploy.yaml",
        """name: deploy
description: Deploy the service
steps:
  - Run tests
  - Build artifacts
""",
    )

    result = runner.invoke(cli, ["skill", "show", "deploy"])

    assert result.exit_code == 0
    assert "deploy" in result.output.lower()
    assert "Deploy the service" in result.output
    assert "Run tests" in result.output


def test_skill_help_describes_local_discovery_surface() -> None:
    """`henchman skill --help` should describe the local-only discovery surface truthfully."""

    runner = CliRunner()

    result = runner.invoke(cli, ["skill", "--help"])

    assert result.exit_code == 0
    assert "discover and inspect compatible local skills" in result.output.lower()
    assert "list and inspect metadata only" in result.output.lower()


def test_skill_show_mentions_metadata_only_surface(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`henchman skill show` should avoid implying an invocation backend exists."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)

    _write(
        project_root / ".henchman" / "skills" / "deploy.yaml",
        """name: deploy
description: Deploy the service
steps:
  - Run tests
  - Build artifacts
""",
    )

    result = runner.invoke(cli, ["skill", "show", "deploy"])

    assert result.exit_code == 0
    assert "metadata only" in result.output.lower()
    assert "does not execute skills" in result.output.lower()
