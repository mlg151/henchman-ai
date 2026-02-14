"""Pydantic data models for the knowledge graph."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Observation(BaseModel):
    """A timestamped fact attached to an entity.

    Attributes:
        content: The observation text.
        source: Where this fact came from (e.g. file:line, conversation).
        timestamp: When the observation was recorded (ISO 8601).
        author: Who created it — "auto" for scanner, "agent" for LLM.
    """

    content: str
    source: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    author: str = "agent"


class Relation(BaseModel):
    """A typed directed edge between two entities.

    Attributes:
        source: Source entity id.
        target: Target entity id.
        relation_type: Edge type (imports, depends_on, contains, etc.).
        description: Optional context about the relationship.
    """

    source: str
    target: str
    relation_type: str
    description: str = ""


class Entity(BaseModel):
    """A node in the knowledge graph.

    Attributes:
        id: Unique slug identifier (e.g. "src-henchman-core-agent").
        entity_type: Category (file, module, package, class, function,
            decision, convention, pattern).
        name: Human-readable name.
        description: What this entity is.
        file_path: Source file path if applicable.
        tags: Free-form tags for categorisation.
        observations: Timestamped facts about this entity.
    """

    id: str
    entity_type: str
    name: str
    description: str = ""
    file_path: str | None = None
    tags: list[str] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)


class GraphMeta(BaseModel):
    """Metadata about a persisted knowledge graph.

    Attributes:
        repo_path: Absolute path to the repository root.
        repo_hash: Repository identifier hash.
        last_indexed: ISO timestamp of last auto-population run.
        schema_version: Data schema version for forward compatibility.
        file_hashes: Per-file content hashes for incremental indexing.
    """

    repo_path: str
    repo_hash: str
    last_indexed: str = ""
    schema_version: int = 1
    file_hashes: dict[str, str] = Field(default_factory=dict)
