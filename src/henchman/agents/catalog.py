"""Discover YAML/JSON agent definitions from project and user directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from henchman.agents.models import AgentDefinition
from henchman.config.paths import resolve_project_settings_path
from henchman.config.schema import AgentConfig

_IGNORED_DISCOVERY_BASENAMES = frozenset({"agents.json"})


class AgentCatalog:
    """Discover and resolve on-disk agent definitions."""

    def __init__(
        self,
        *,
        project_root: Path | None = None,
        home_dir: Path | None = None,
    ) -> None:
        """Initialize the catalog for one project and one home directory."""

        self._project_root = (project_root or Path.cwd()).resolve()
        self._home_dir = (home_dir or Path.home()).resolve()

    def list_agents(self) -> list[AgentDefinition]:
        """Return all discovered agent definitions sorted by role."""

        definitions = self._discover_agents()
        return sorted(definitions.values(), key=lambda definition: definition.role)

    def get(self, role: str) -> AgentDefinition | None:
        """Resolve one agent definition by role, case-insensitively."""

        return self._discover_agents().get(role.casefold())

    def as_config_map(self) -> dict[str, AgentConfig]:
        """Return discovered definitions as a runtime config map."""

        return {
            definition.role: definition.config
            for definition in self.list_agents()
        }

    def _discover_agents(self) -> dict[str, AgentDefinition]:
        """Discover all supported agent definitions with project-local precedence."""

        definitions: dict[str, AgentDefinition] = {}
        for definition in self._iter_discovered_agents():
            definitions[definition.role.casefold()] = definition
        return definitions

    def _iter_discovered_agents(self) -> list[AgentDefinition]:
        """Return discovered definitions from lowest to highest precedence."""

        discovered: list[AgentDefinition] = []
        discovered.extend(
            self._discover_directory(
                self._home_dir / ".henchman" / "agents",
                source_kind="henchman-user",
            ),
        )
        discovered.extend(
            self._discover_directory(
                self._project_root / "agents",
                source_kind="henchman-bundled",
            ),
        )
        discovered.extend(
            self._discover_directory(
                resolve_project_settings_path(self._project_root) / "agents",
                source_kind="henchman-project",
            ),
        )
        return discovered

    def _discover_directory(self, directory: Path, *, source_kind: str) -> list[AgentDefinition]:
        """Load all YAML/JSON agent definitions from one directory tree."""

        if not directory.is_dir():
            return []

        definitions: list[AgentDefinition] = []
        patterns = ("*.yaml", "*.yml", "*.json")
        files = sorted(
            file_path
            for pattern in patterns
            for file_path in directory.rglob(pattern)
        )
        for definition_file in files:
            if _should_skip_discovered_file(definition_file, root_directory=directory):
                continue
            definitions.append(
                load_agent_definition_file(
                    definition_file,
                    source_kind=source_kind,
                ),
            )
        return definitions


def merge_discovered_agent_configs(
    base_configs: dict[str, AgentConfig],
    *,
    project_root: Path | None = None,
    home_dir: Path | None = None,
) -> dict[str, AgentConfig]:
    """Overlay discovered agent definitions onto one base config mapping."""

    merged = dict(base_configs)
    for role, config in AgentCatalog(project_root=project_root, home_dir=home_dir).as_config_map().items():
        merged[role] = config
    return merged


def load_agent_definition_file(
    path: Path,
    *,
    source_kind: str,
) -> AgentDefinition:
    """Load one agent definition file from YAML or JSON."""

    raw_payload = _load_payload(path)
    if not isinstance(raw_payload, dict):
        msg = f"Agent definition at {path} must decode to an object payload"
        raise ValueError(msg)
    return AgentDefinition.from_payload(
        raw_payload,
        source_kind=source_kind,
        source_path=path,
    )


def _should_skip_discovered_file(path: Path, *, root_directory: Path) -> bool:
    """Return whether discovery should ignore one known non-definition file."""

    return path.parent == root_directory and path.name in _IGNORED_DISCOVERY_BASENAMES


def _load_payload(path: Path) -> dict[str, Any]:
    """Decode one YAML or JSON agent definition file."""

    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(raw_text)
    else:
        payload = yaml.safe_load(raw_text) or {}
    if not isinstance(payload, dict):
        msg = f"Agent definition at {path} must decode to an object payload"
        raise ValueError(msg)
    return payload
