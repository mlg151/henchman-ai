"""Tests for the agent platform marketplace manager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from henchman.agents.models import AgentDefinition
from henchman.agents.platform_manager import AgentPlatformManager


def _write(path: Path, content: str) -> None:
    """Write a file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _reviewer_definition(version: str = "1.0.0") -> AgentDefinition:
    """Build a test agent definition."""

    return AgentDefinition.from_payload(
        {
            "name": "Reviewer",
            "role": "reviewer",
            "description": "Reviews code changes",
            "version": version,
            "tools": ["read_file", "grep"],
            "system_prompt": "Review pull requests carefully.",
        },
        source_kind="registry",
        source_path=Path("/tmp/registry/reviewer.yaml"),
    )


@pytest.mark.asyncio
async def test_install_agent_writes_definition_file(tmp_path: Path) -> None:
    """Installing an agent should persist a YAML definition into the project data dir."""

    manager = AgentPlatformManager(data_dir=tmp_path / ".henchman" / "agents")
    await manager.initialize()

    with patch.object(manager, "get_agent_info", return_value=_reviewer_definition()):
        installation = await manager.install_agent("reviewer")

    installation_path = Path(installation.installation_path)
    assert installation.definition.role == "reviewer"
    assert installation.installed_version == "1.0.0"
    assert installation_path.exists()
    assert installation_path.read_text(encoding="utf-8")

    await manager.close()


@pytest.mark.asyncio
async def test_publish_agent_creates_local_publication_bundle(tmp_path: Path) -> None:
    """Publishing an agent should snapshot a definition into the local publication store."""

    spec_path = tmp_path / "reviewer.yaml"
    _write(
        spec_path,
        """
name: Reviewer
role: reviewer
description: Reviews code changes
version: 1.3.0
tools:
  - read_file
  - grep
""".strip(),
    )

    manager = AgentPlatformManager(data_dir=tmp_path / ".henchman" / "agents")
    await manager.initialize()

    publication = await manager.publish_agent(spec_path)

    assert publication.definition.role == "reviewer"
    assert publication.version == "1.3.0"
    assert Path(publication.publication_path).exists()

    await manager.close()
