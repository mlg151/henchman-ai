"""Marketplace-style manager for project-local agent definitions."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from henchman.agents.catalog import load_agent_definition_file
from henchman.agents.models import (
    DEFAULT_AGENT_PAGE_SIZE,
    AgentDefinition,
    AgentInstallation,
    AgentPublication,
    AgentSearchParams,
    AgentSearchResult,
    AgentUpdateInfo,
    installation_from_payload,
    installation_to_payload,
)
from henchman.config.paths import resolve_project_settings_path

_DEFAULT_AGENT_REGISTRY_URL = "https://agents.henchman.ai"


class AgentRegistryInstallError(RuntimeError):
    """Base error for guarded registry-backed agent installs."""


class AgentRegistryUnsupportedError(AgentRegistryInstallError):
    """Raised when registry-backed installs are not available."""

    def __init__(self, *, registry_url: str) -> None:
        super().__init__(
            "Registry-backed agent installs are not available in this build. "
            f"The registry at {registry_url} does not expose install metadata yet. "
            "Use `agents-platform list` or `agents-platform show` for local agent definitions, "
            "or `agents-platform publish <spec-path>` to snapshot a local agent spec.",
        )


class AgentRegistryUnavailableError(AgentRegistryInstallError):
    """Raised when registry-backed installs cannot reach registry metadata."""

    def __init__(self, *, registry_url: str) -> None:
        super().__init__(
            "Registry-backed agent installs are temporarily unavailable. "
            f"Could not reach registry metadata at {registry_url}. "
            "Try again later, or keep using `agents-platform list`, `agents-platform show`, "
            "and `agents-platform publish` for local agent workflows.",
        )


class _AgentRegistryClient:
    """Small registry client abstraction for agent metadata lookups."""

    def __init__(self, registry_url: str) -> None:
        """Initialize the client with one registry base URL."""

        self.registry_url = registry_url

    async def search_agents(self, search_params: AgentSearchParams) -> AgentSearchResult:
        """Return an empty search result until a real registry is configured."""

        return AgentSearchResult(
            agents=[],
            total=0,
            page=search_params.page,
            page_size=search_params.page_size,
            query=search_params.query,
        )

    async def get_agent_info(
        self,
        role: str,
        version: str | None = None,
    ) -> AgentDefinition | None:
        """Return no agent metadata by default."""

        del role, version
        return None


class AgentPlatformManager:
    """Manage agent definition install/remove/publish workflows."""

    def __init__(
        self,
        registry_url: str = _DEFAULT_AGENT_REGISTRY_URL,
        data_dir: Path | None = None,
    ) -> None:
        """Initialize the manager with one registry URL and storage root."""

        self.registry_url = registry_url
        self.data_dir = data_dir or (resolve_project_settings_path() / "agents")
        self.db_path = self.data_dir / "agents.json"
        self.registry_client = _AgentRegistryClient(registry_url)
        self.installed_agents: dict[str, AgentInstallation] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize persistence and load installed agents."""

        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "installed").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "published").mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self.db_path.write_text("[]", encoding="utf-8")
        self._load_database()
        self._initialized = True

    async def close(self) -> None:
        """Flush persistence and close the manager."""

        if self._initialized:
            self._persist_database()
        self._initialized = False

    async def search_agents(
        self,
        query: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_AGENT_PAGE_SIZE,
        search_params: AgentSearchParams | None = None,
    ) -> AgentSearchResult:
        """Search the remote agent registry."""

        self._validate_initialization()
        resolved_params = search_params or AgentSearchParams(
            query=query,
            page=page,
            page_size=page_size,
        )
        return await self.registry_client.search_agents(resolved_params)

    async def get_agent_info(
        self,
        role: str,
        version: str | None = None,
    ) -> AgentDefinition | None:
        """Return metadata for one agent from the registry."""

        self._validate_initialization()
        return await self.registry_client.get_agent_info(role, version)

    async def install_agent(
        self,
        role: str,
        version: str | None = None,
    ) -> AgentInstallation:
        """Install one agent definition from the registry into the project store."""

        self._validate_initialization()
        self._check_already_installed(role)
        definition = await self._get_agent_definition(role, version)
        installation_path = self._write_definition_file(definition)
        installation = AgentInstallation(
            definition=definition,
            installed_version=version or definition.version,
            installation_path=str(installation_path),
            enabled=True,
        )
        self.installed_agents[role] = installation
        self._persist_database()
        return installation

    async def uninstall_agent(self, role: str) -> None:
        """Remove one installed agent definition."""

        self._validate_initialization()
        installation = self._get_installation_or_raise(role)
        self.installed_agents.pop(role, None)
        installation_path = Path(installation.installation_path)
        if installation_path.exists():
            installation_path.unlink()
        self._persist_database()

    async def publish_agent(self, spec_path: Path) -> AgentPublication:
        """Publish one local agent definition into the local publication store."""

        self._validate_initialization()
        definition = load_agent_definition_file(
            spec_path,
            source_kind="henchman-publication",
        )
        publication_path = self.data_dir / "published" / f"{definition.role}-{definition.version}.yaml"
        publication_path.write_text(
            yaml.safe_dump(definition.to_payload(), sort_keys=False),
            encoding="utf-8",
        )
        return AgentPublication(
            definition=definition,
            version=definition.version,
            publication_path=str(publication_path),
        )

    async def check_updates(self) -> dict[str, AgentUpdateInfo]:
        """Return available updates for installed agent definitions."""

        self._validate_initialization()
        updates: dict[str, AgentUpdateInfo] = {}
        for role, installation in self.installed_agents.items():
            latest = await self.get_agent_info(role)
            if latest is None or latest.version == installation.installed_version:
                continue
            updates[role] = AgentUpdateInfo(
                role=role,
                current_version=installation.installed_version,
                latest_version=latest.version,
            )
        return updates

    def _validate_initialization(self) -> None:
        """Ensure manager initialization has run."""

        if not self._initialized:
            raise RuntimeError("Agent platform manager is not initialized")

    def _check_already_installed(self, role: str) -> None:
        """Raise when an agent definition is already installed."""

        if role in self.installed_agents:
            raise ValueError(f"Agent '{role}' is already installed")

    async def _get_agent_definition(
        self,
        role: str,
        version: str | None = None,
    ) -> AgentDefinition:
        """Load one agent definition from the registry or raise."""

        try:
            definition = await self.get_agent_info(role, version)
        except AgentRegistryInstallError:
            raise
        except (ConnectionError, OSError, TimeoutError) as error:
            raise AgentRegistryUnavailableError(registry_url=self.registry_url) from error
        if definition is None:
            raise AgentRegistryUnsupportedError(registry_url=self.registry_url)
        return definition

    def _write_definition_file(self, definition: AgentDefinition) -> Path:
        """Persist one installed agent definition to the project store."""

        installation_path = self.data_dir / "installed" / f"{definition.role}.yaml"
        installation_path.write_text(
            yaml.safe_dump(definition.to_payload(), sort_keys=False),
            encoding="utf-8",
        )
        return installation_path

    def _get_installation_or_raise(self, role: str) -> AgentInstallation:
        """Return one installed agent definition or raise."""

        installation = self.installed_agents.get(role)
        if installation is None:
            raise ValueError(f"Agent '{role}' is not installed")
        return installation

    def _load_database(self) -> None:
        """Load persisted agent installation records."""

        raw_text = self.db_path.read_text(encoding="utf-8")
        payload = json.loads(raw_text) if raw_text.strip() else []
        self.installed_agents = {}
        for entry in payload:
            if isinstance(entry, dict):
                installation = installation_from_payload(entry)
                self.installed_agents[installation.definition.role] = installation

    def _persist_database(self) -> None:
        """Persist installed agent definitions to disk."""

        payload = [
            installation_to_payload(installation)
            for installation in self.installed_agents.values()
        ]
        self.db_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
