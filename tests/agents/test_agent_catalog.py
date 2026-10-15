"""Tests for agent definition discovery and runtime loading."""

from __future__ import annotations

import json
from pathlib import Path

from henchman.agents.catalog import AgentCatalog, merge_discovered_agent_configs
from henchman.agents.presets import get_default_team


def _write(path: Path, content: str) -> None:
    """Write a file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_agent_catalog_discovers_yaml_and_json_specs_with_project_precedence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Project-local agent specs should override user-level definitions."""

    home_dir = tmp_path / "home"
    project_root = tmp_path / "workspace"
    project_root.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))

    _write(
        home_dir / ".henchman" / "agents" / "reviewer.yaml",
        """
name: Reviewer
role: reviewer
description: Home reviewer
version: 0.9.0
tools:
  - read_file
""".strip(),
    )
    (project_root / "agents").mkdir()
    (project_root / "agents" / "qa.json").write_text(
        json.dumps(
            {
                "name": "QA",
                "role": "qa",
                "description": "Project QA agent",
                "version": "1.0.0",
                "tools": ["read_file", "grep"],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _write(
        project_root / ".henchman" / "agents" / "reviewer.yaml",
        """
name: Reviewer
role: reviewer
description: Project reviewer
version: 1.2.0
tools:
  - read_file
  - grep
system_prompt: Review pull requests carefully.
""".strip(),
    )

    catalog = AgentCatalog(project_root=project_root)

    definitions = catalog.list_agents()
    roles = [definition.role for definition in definitions]

    assert roles == ["qa", "reviewer"]

    reviewer = catalog.get("reviewer")
    assert reviewer is not None
    assert reviewer.description == "Project reviewer"
    assert reviewer.version == "1.2.0"
    assert reviewer.source_kind == "henchman-project"
    assert reviewer.config.system_prompt == "Review pull requests carefully."

    config_map = catalog.as_config_map()
    assert config_map["reviewer"].tools == ["read_file", "grep"]


def test_runtime_agent_config_merge_loads_project_agent_definitions(
    tmp_path: Path,
) -> None:
    """Discovered project-local agent specs should merge into runtime agent configs."""

    project_root = tmp_path / "workspace"
    project_root.mkdir()

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

    merged_configs = merge_discovered_agent_configs(get_default_team(), project_root=project_root)

    assert "reviewer" in merged_configs
    assert merged_configs["reviewer"].description == "Reviews code changes"


def test_agent_catalog_ignores_platform_persistence_payloads(
    tmp_path: Path,
) -> None:
    """Project-local discovery should skip platform persistence payloads."""

    project_root = tmp_path / "workspace"
    project_root.mkdir()

    _write(project_root / ".henchman" / "agents" / "agents.json", "[]")
    _write(
        project_root / ".henchman" / "agents" / "reviewer.yaml",
        """
name: Reviewer
role: reviewer
description: Reviews code changes
version: 1.0.0
tools:
  - read_file
""".strip(),
    )

    catalog = AgentCatalog(project_root=project_root)

    definitions = catalog.list_agents()

    assert [definition.role for definition in definitions] == ["reviewer"]
    assert catalog.get("reviewer") is not None
