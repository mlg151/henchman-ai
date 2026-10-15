"""Tests for the root agents-platform command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from henchman.cli.app import cli


def _write(path: Path, content: str) -> None:
    """Write a test file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_agents_platform_list_discovers_local_agent_specs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`henchman agents-platform list` should show discovered agent specs."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)

    _write(
        project_root / ".henchman" / "agents" / "reviewer.yaml",
        """
name: Reviewer
role: reviewer
description: Reviews code changes
version: 1.0.0
tools:
  - read_file
  - grep
""".strip(),
    )

    result = runner.invoke(cli, ["agents-platform", "list"])

    assert result.exit_code == 0
    assert "reviewer" in result.output
    assert "Reviews code changes" in result.output


def test_agents_platform_install_calls_manager(monkeypatch) -> None:
    """`agents-platform install` should delegate to the marketplace manager."""

    installed: list[tuple[str, str | None]] = []

    class FakeInstallation:
        def __init__(self) -> None:
            self.definition = type(
                "Definition",
                (),
                {"role": "reviewer", "description": "Reviews code changes"},
            )()
            self.installed_version = "1.0.0"

    class FakeAgentPlatformManager:
        def __init__(self, data_dir=None) -> None:
            self.data_dir = data_dir

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def install_agent(
            self,
            role: str,
            version: str | None = None,
        ) -> FakeInstallation:
            installed.append((role, version))
            return FakeInstallation()

    monkeypatch.setattr(
        "henchman.cli.commands.agents_platform_command.AgentPlatformManager",
        FakeAgentPlatformManager,
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["agents-platform", "install", "reviewer"])

    assert result.exit_code == 0
    assert installed == [("reviewer", None)]
    assert "Installed agent reviewer 1.0.0" in result.output


def test_agents_platform_install_gracefully_reports_unsupported_registry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`agents-platform install` should return truthful guidance when registry installs are unavailable."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)

    result = runner.invoke(cli, ["agents-platform", "install", "reviewer"])

    assert result.exit_code == 1
    assert "Registry-backed agent installs are not available" in result.output
    assert "agents-platform list" in result.output
    assert "agents-platform show" in result.output
    assert "agents-platform publish" in result.output


def test_agents_platform_show_renders_local_agent_definition(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`henchman agents-platform show` should render one local agent definition."""

    runner = CliRunner()
    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.chdir(project_root)

    _write(
        project_root / ".henchman" / "agents" / "reviewer.yaml",
        """
name: Reviewer
role: reviewer
description: Reviews code changes
version: 1.0.0
tools:
  - read_file
  - grep
system_prompt: Review carefully.
""".strip(),
    )

    result = runner.invoke(cli, ["agents-platform", "show", "reviewer"])

    assert result.exit_code == 0
    assert "Role: reviewer" in result.output
    assert "Source: henchman-project" in result.output
    assert "System prompt:" in result.output


def test_agents_platform_publish_calls_manager(monkeypatch, tmp_path: Path) -> None:
    """`agents-platform publish` should delegate to the marketplace manager."""

    published: list[Path] = []
    spec_path = tmp_path / "reviewer.yaml"
    _write(
        spec_path,
        """
name: Reviewer
role: reviewer
description: Reviews code changes
version: 1.0.0
tools:
  - read_file
""".strip(),
    )

    class FakePublication:
        def __init__(self) -> None:
            self.definition = type("Definition", (), {"role": "reviewer"})()
            self.version = "1.0.0"
            self.publication_path = ".henchman/agents/published/reviewer-1.0.0.yaml"

    class FakeAgentPlatformManager:
        def __init__(self, data_dir=None) -> None:
            self.data_dir = data_dir

        async def initialize(self) -> None:
            return None

        async def close(self) -> None:
            return None

        async def publish_agent(self, incoming_spec_path: Path) -> FakePublication:
            published.append(incoming_spec_path)
            return FakePublication()

    monkeypatch.setattr(
        "henchman.cli.commands.agents_platform_command.AgentPlatformManager",
        FakeAgentPlatformManager,
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["agents-platform", "publish", str(spec_path)])

    assert result.exit_code == 0
    assert published == [spec_path]
    assert "Published agent reviewer 1.0.0" in result.output
