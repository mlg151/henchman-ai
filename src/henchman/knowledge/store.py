"""Knowledge graph store backed by NetworkX + optional ChromaDB.

Persists the graph as JSON (``nx.node_link_data``).  When ChromaDB is
available, entity descriptions are embedded for semantic search.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import networkx as nx
from networkx import DiGraph

from henchman.knowledge.models import Entity, GraphMeta, Observation, Relation
from henchman.rag.repo_id import compute_repository_id

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GRAPH_FILE = "graph.json"
_META_FILE = "meta.json"


def _entity_to_node_attrs(entity: Entity) -> dict[str, Any]:
    """Serialise an Entity to NetworkX node attributes."""
    return entity.model_dump(mode="json")


def _node_attrs_to_entity(node_id: str, attrs: dict[str, Any]) -> Entity:
    """Deserialise NetworkX node attributes back to an Entity.

    Args:
        node_id: The NetworkX node key (used as entity id).
        attrs: Node attribute dictionary.

    Returns:
        Reconstructed Entity.
    """
    data = {**attrs, "id": node_id}
    return Entity.model_validate(data)


def _safe_node_to_entity(node_id: str, attrs: dict[str, Any]) -> Entity | None:
    """Like ``_node_attrs_to_entity`` but returns ``None`` on bad data.

    Args:
        node_id: The NetworkX node key.
        attrs: Node attribute dictionary.

    Returns:
        Reconstructed Entity, or ``None`` if validation fails.
    """
    try:
        return _node_attrs_to_entity(node_id, attrs)
    except Exception:  # noqa: BLE001
        logger.debug("Skipping malformed node %r", node_id)
        return None


def _slugify(text: str) -> str:
    """Convert a path or name to a graph-safe slug.

    Args:
        text: Arbitrary string to slugify.

    Returns:
        Lowercase slug with separators normalised to ``-``.
    """
    return (
        text.lower()
        .replace("/", "-")
        .replace("\\", "-")
        .replace(".", "-")
        .replace("_", "-")
        .strip("-")
    )


# ---------------------------------------------------------------------------
# KnowledgeStore
# ---------------------------------------------------------------------------


class KnowledgeStore:
    """Persistent project knowledge graph.

    The graph is stored under ``~/.henchman/knowledge/<repo-hash>/``.

    Args:
        git_root: Root of the git repository to track.
        base_dir: Override for the storage base directory
            (defaults to ``~/.henchman/knowledge``).
    """

    def __init__(
        self,
        git_root: Path,
        base_dir: Path | None = None,
    ) -> None:
        """Initialize the knowledge store.

        Args:
            git_root: Root of the git repository to track.
            base_dir: Override for the storage base directory
                (defaults to ``~/.henchman/knowledge``).
        """
        self._git_root = git_root.resolve()
        self._base_dir = base_dir or (Path.home() / ".henchman" / "knowledge")
        self._repo_hash = compute_repository_id(self._git_root)
        self._store_dir = self._base_dir / self._repo_hash
        self._graph: DiGraph[str] = DiGraph()
        self._meta: GraphMeta = GraphMeta(
            repo_path=str(self._git_root),
            repo_hash=self._repo_hash,
        )
        self._dirty = False

    # -- properties ----------------------------------------------------------

    @property
    def store_dir(self) -> Path:
        """Directory where this graph is persisted."""
        return self._store_dir

    @property
    def graph(self) -> DiGraph[str]:
        """The underlying NetworkX directed graph."""
        return self._graph

    @property
    def meta(self) -> GraphMeta:
        """Graph metadata."""
        return self._meta

    # -- persistence ---------------------------------------------------------

    def load(self) -> None:
        """Load graph and metadata from disk.

        If the store directory does not yet exist the graph starts empty.
        """
        graph_path = self._store_dir / _GRAPH_FILE
        meta_path = self._store_dir / _META_FILE

        if meta_path.exists():
            raw = json.loads(meta_path.read_text())
            self._meta = GraphMeta.model_validate(raw)

        if graph_path.exists():
            raw = json.loads(graph_path.read_text())
            self._graph = nx.node_link_graph(raw, directed=True)
        else:
            self._graph = nx.DiGraph()

        self._dirty = False

    def save(self) -> None:
        """Persist the graph and metadata to disk."""
        self._store_dir.mkdir(parents=True, exist_ok=True)

        graph_path = self._store_dir / _GRAPH_FILE
        meta_path = self._store_dir / _META_FILE

        graph_data = nx.node_link_data(self._graph)
        graph_path.write_text(json.dumps(graph_data, indent=2))
        meta_path.write_text(self._meta.model_dump_json(indent=2))

        self._dirty = False

    # -- entity CRUD ---------------------------------------------------------

    def add_entity(self, entity: Entity) -> None:
        """Add or update an entity (node) in the graph.

        Args:
            entity: The entity to upsert.
        """
        self._graph.add_node(entity.id, **_entity_to_node_attrs(entity))
        self._dirty = True

    def get_entity(self, entity_id: str) -> Entity | None:
        """Retrieve a single entity by id.

        Args:
            entity_id: The unique entity slug.

        Returns:
            The entity, or ``None`` if not found.
        """
        if entity_id not in self._graph:
            return None
        return _node_attrs_to_entity(entity_id, dict(self._graph.nodes[entity_id]))

    def remove_entity(self, entity_id: str) -> bool:
        """Remove an entity and all its edges.

        Args:
            entity_id: The entity to remove.

        Returns:
            ``True`` if the entity existed and was removed.
        """
        if entity_id not in self._graph:
            return False
        self._graph.remove_node(entity_id)
        self._dirty = True
        return True

    def list_entities(
        self,
        entity_type: str | None = None,
        tag: str | None = None,
    ) -> list[Entity]:
        """List entities, optionally filtered by type or tag.

        Args:
            entity_type: Filter to this type (e.g. ``"file"``).
            tag: Filter to entities that have this tag.

        Returns:
            Matching entities.
        """
        results: list[Entity] = []
        for nid, attrs in self._graph.nodes(data=True):
            entity = _safe_node_to_entity(nid, dict(attrs))
            if entity is None:
                continue
            if entity_type and entity.entity_type != entity_type:
                continue
            if tag and tag not in entity.tags:
                continue
            results.append(entity)
        return results

    def search_entities(self, query: str) -> list[Entity]:
        """Full-text search over entity names, descriptions, and observations.

        Args:
            query: Case-insensitive search term.

        Returns:
            Entities whose text fields contain the query.
        """
        q = query.lower()
        results: list[Entity] = []
        for nid, attrs in self._graph.nodes(data=True):
            entity = _safe_node_to_entity(nid, dict(attrs))
            if entity is None:
                continue
            haystack = " ".join(
                [
                    entity.name,
                    entity.description,
                    " ".join(o.content for o in entity.observations),
                ],
            ).lower()
            if q in haystack:
                results.append(entity)
        return results

    # -- observations --------------------------------------------------------

    def add_observation(
        self,
        entity_id: str,
        observation: Observation,
    ) -> bool:
        """Attach an observation to an existing entity.

        Args:
            entity_id: Target entity.
            observation: The observation to add.

        Returns:
            ``True`` if the entity exists and the observation was added.
        """
        if entity_id not in self._graph:
            return False
        entity = _node_attrs_to_entity(entity_id, dict(self._graph.nodes[entity_id]))
        entity.observations.append(observation)
        self._graph.nodes[entity_id].update(_entity_to_node_attrs(entity))
        self._dirty = True
        return True

    # -- relation CRUD -------------------------------------------------------

    def add_relation(self, relation: Relation) -> None:
        """Add or update a directed edge between two entities.

        Missing endpoint entities are **not** auto-created; the caller
        should ensure both exist first.

        Args:
            relation: The relation to upsert.
        """
        self._graph.add_edge(
            relation.source,
            relation.target,
            relation_type=relation.relation_type,
            description=relation.description,
        )
        self._dirty = True

    def get_relations(
        self,
        entity_id: str,
        direction: str = "both",
    ) -> list[Relation]:
        """Get relations for an entity.

        Args:
            entity_id: The entity to query.
            direction: ``"out"``, ``"in"``, or ``"both"``.

        Returns:
            Relations involving this entity.
        """
        relations: list[Relation] = []

        if direction in ("out", "both"):
            for _, target, data in self._graph.out_edges(entity_id, data=True):
                relations.append(
                    Relation(
                        source=entity_id,
                        target=target,
                        relation_type=data.get("relation_type", "related_to"),
                        description=data.get("description", ""),
                    ),
                )

        if direction in ("in", "both"):
            for source, _, data in self._graph.in_edges(entity_id, data=True):
                relations.append(
                    Relation(
                        source=source,
                        target=entity_id,
                        relation_type=data.get("relation_type", "related_to"),
                        description=data.get("description", ""),
                    ),
                )

        return relations

    def remove_relation(self, source: str, target: str) -> bool:
        """Remove an edge between two entities.

        Args:
            source: Source entity id.
            target: Target entity id.

        Returns:
            ``True`` if the edge existed and was removed.
        """
        if self._graph.has_edge(source, target):
            self._graph.remove_edge(source, target)
            self._dirty = True
            return True
        return False

    # -- graph queries -------------------------------------------------------

    def get_neighbors(
        self,
        entity_id: str,
        depth: int = 1,
    ) -> list[Entity]:
        """Get entities within *depth* hops of *entity_id*.

        Args:
            entity_id: Starting node.
            depth: Maximum hop distance.

        Returns:
            Neighbouring entities (excluding the start node).
        """
        if entity_id not in self._graph:
            return []

        undirected = self._graph.to_undirected()
        visited: set[str] = set()
        frontier = {entity_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                for neighbor in undirected.neighbors(node):
                    if neighbor not in visited and neighbor != entity_id:
                        next_frontier.add(neighbor)
            visited.update(next_frontier)
            frontier = next_frontier

        results: list[Entity] = []
        for n in visited:
            if n not in self._graph:
                continue
            ent = _safe_node_to_entity(n, dict(self._graph.nodes[n]))
            if ent is not None:
                results.append(ent)
        return results

    def get_important_entities(self, top_k: int = 10) -> list[tuple[Entity, float]]:
        """Return the most important entities by PageRank.

        Args:
            top_k: Number of entities to return.

        Returns:
            List of ``(entity, score)`` pairs sorted by importance.
        """
        if len(self._graph) == 0:
            return []

        scores = nx.pagerank(self._graph)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results: list[tuple[Entity, float]] = []
        for nid, score in ranked:
            if nid not in self._graph:
                continue
            ent = _safe_node_to_entity(nid, dict(self._graph.nodes[nid]))
            if ent is not None:
                results.append((ent, score))
        return results

    def get_connected_components(self) -> list[list[str]]:
        """Return connected components of the graph.

        Returns:
            List of components, each being a list of entity ids.
        """
        undirected = self._graph.to_undirected()
        return [list(c) for c in nx.connected_components(undirected)]

    # -- bulk helpers --------------------------------------------------------

    def entity_count(self) -> int:
        """Number of entities in the graph."""
        return self._graph.number_of_nodes()

    def relation_count(self) -> int:
        """Number of relations in the graph."""
        return self._graph.number_of_edges()

    def clear(self) -> None:
        """Remove all entities and relations."""
        self._graph.clear()
        self._dirty = True

    # -- formatting ----------------------------------------------------------

    def format_entity_for_llm(self, entity: Entity) -> str:
        """Format an entity for LLM consumption.

        Args:
            entity: Entity to format.

        Returns:
            Markdown-formatted string.
        """
        parts = [f"## {entity.name} ({entity.entity_type})"]
        if entity.file_path:
            parts.append(f"**File:** `{entity.file_path}`")
        if entity.description:
            parts.append(entity.description)
        if entity.tags:
            parts.append(f"**Tags:** {', '.join(entity.tags)}")
        if entity.observations:
            parts.append("**Observations:**")
            parts.extend(
                f"- {obs.content} _(source: {obs.source})_"
                for obs in entity.observations
            )

        relations = self.get_relations(entity.id)
        if relations:
            parts.append("**Relations:**")
            for rel in relations:
                arrow = "→" if rel.source == entity.id else "←"
                other = rel.target if rel.source == entity.id else rel.source
                parts.append(f"- {arrow} {rel.relation_type}: `{other}`")

        return "\n".join(parts)

    def format_for_llm(
        self,
        entities: Sequence[Entity],
        max_entities: int = 20,
    ) -> str:
        """Format multiple entities for LLM consumption.

        Args:
            entities: Entities to format.
            max_entities: Cap on output size.

        Returns:
            Markdown-formatted string.
        """
        capped = list(entities)[:max_entities]
        sections = [self.format_entity_for_llm(e) for e in capped]
        header = f"Knowledge Graph Results ({len(capped)}/{len(list(entities))} shown)"
        return f"# {header}\n\n" + "\n\n---\n\n".join(sections)
