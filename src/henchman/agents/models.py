"""Typed models for agent definitions and marketplace workflows."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from henchman.config.schema import AgentConfig

DEFAULT_AGENT_PAGE_SIZE = 20
"""Default page size for agent registry searches."""

_AGENT_METADATA_KEYS = {"version", "author", "tags", "source_kind", "source_path"}


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Normalized agent definition from disk or a registry payload."""

    config: AgentConfig
    version: str
    source_path: Path
    source_kind: str
    author: str | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def role(self) -> str:
        """Return the agent role identifier."""

        return self.config.role

    @property
    def name(self) -> str:
        """Return the display name for the agent."""

        return self.config.name

    @property
    def description(self) -> str:
        """Return the normalized description for the agent."""

        return self.config.description

    def to_payload(self, *, include_source: bool = False) -> dict[str, Any]:
        """Serialize the definition into a YAML/JSON-friendly payload."""

        payload = self.config.model_dump(exclude_none=True)
        payload["version"] = self.version
        if self.author:
            payload["author"] = self.author
        if self.tags:
            payload["tags"] = list(self.tags)
        if include_source:
            payload["source_kind"] = self.source_kind
            payload["source_path"] = str(self.source_path)
        return payload

    @classmethod
    def from_payload(
        cls,
        payload: Mapping[str, Any],
        *,
        source_kind: str | None = None,
        source_path: Path | None = None,
    ) -> AgentDefinition:
        """Build an agent definition from one decoded YAML/JSON payload."""

        metadata_source_kind = source_kind or str(payload.get("source_kind") or "unknown")
        metadata_source_path = source_path or Path(str(payload.get("source_path") or "<memory>"))
        config_payload = {
            key: value for key, value in payload.items() if key not in _AGENT_METADATA_KEYS
        }
        config = AgentConfig(**config_payload)
        version = str(payload.get("version") or "1.0.0")
        author_value = payload.get("author")
        author = str(author_value) if author_value is not None else None
        tags_payload = payload.get("tags", [])
        tags = [str(tag) for tag in tags_payload] if isinstance(tags_payload, list) else []
        return cls(
            config=config,
            version=version,
            source_path=metadata_source_path,
            source_kind=metadata_source_kind,
            author=author,
            tags=tags,
        )


@dataclass(frozen=True, slots=True)
class AgentSearchParams:
    """Structured parameters for agent registry searches."""

    query: str | None = None
    page: int = 1
    page_size: int = DEFAULT_AGENT_PAGE_SIZE


@dataclass(frozen=True, slots=True)
class AgentSearchResult:
    """Search results returned by the agent registry."""

    agents: list[AgentDefinition]
    total: int
    page: int
    page_size: int
    query: str | None = None


@dataclass(frozen=True, slots=True)
class AgentInstallation:
    """Metadata for one installed agent definition."""

    definition: AgentDefinition
    installed_version: str
    installation_path: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class AgentUpdateInfo:
    """Version-difference information for one installed agent."""

    role: str
    current_version: str
    latest_version: str


@dataclass(frozen=True, slots=True)
class AgentPublication:
    """Information about a locally published agent definition bundle."""

    definition: AgentDefinition
    version: str
    publication_path: str


def installation_to_payload(installation: AgentInstallation) -> dict[str, Any]:
    """Serialize one installed agent record for persistence."""

    payload = asdict(installation)
    payload["definition"] = installation.definition.to_payload(include_source=True)
    return payload


def installation_from_payload(payload: Mapping[str, Any]) -> AgentInstallation:
    """Deserialize one installed agent record from persistence."""

    definition_payload = payload["definition"]
    if not isinstance(definition_payload, Mapping):
        msg = "Installation payload is missing a valid definition block"
        raise ValueError(msg)
    definition = AgentDefinition.from_payload(definition_payload)
    return AgentInstallation(
        definition=definition,
        installed_version=str(payload["installed_version"]),
        installation_path=str(payload["installation_path"]),
        enabled=bool(payload.get("enabled", True)),
    )
