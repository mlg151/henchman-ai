"""Knowledge graph query tool for agents.

Provides a READ tool that searches the project knowledge graph by
entity name/type, relations, full-text search, and importance ranking.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from henchman.knowledge.scanner import scan_repository
from henchman.knowledge.store import KnowledgeStore
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.kg_update import VALID_ENTITY_TYPES


def _find_git_root() -> Path | None:
    """Locate the git repository root from cwd."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


class KgQueryTool(Tool):
    """Query the project knowledge graph.

    Supports multiple actions: search, get, neighbors, relations,
    important, and stats.

    The graph is lazily initialised on first query — auto-scanning the
    repository if the graph is empty.
    """

    def __init__(self, store: KnowledgeStore | None = None) -> None:
        """Initialise the knowledge graph query tool.

        Args:
            store: Optional pre-built store.  When ``None`` the tool
                will auto-discover the git root and create one.
        """
        self._store = store
        self._initialised = store is not None

    @property
    def name(self) -> str:
        """Tool name."""
        return "kg_query"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Query the project knowledge graph. Supports actions: "
            "'search' (full-text), 'get' (by id), 'neighbors' (graph traversal), "
            "'relations' (edges), 'important' (PageRank), 'stats' (summary)."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for tool parameters."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "search",
                        "get",
                        "neighbors",
                        "relations",
                        "important",
                        "stats",
                    ],
                    "description": "The query action to perform.",
                },
                "query": {
                    "type": "string",
                    "description": (
                        "Search term for 'search' action, or entity id "
                        "for 'get'/'neighbors'/'relations'."
                    ),
                },
                "entity_type": {
                    "type": "string",
                    "enum": sorted(VALID_ENTITY_TYPES),
                    "description": "Filter by entity type.",
                },
                "depth": {
                    "type": "integer",
                    "description": "Hop depth for 'neighbors' (default 1).",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of results for 'important' (default 10).",
                },
            },
            "required": ["action"],
        }

    @property
    def kind(self) -> ToolKind:
        """Read-only tool — auto-approved."""
        return ToolKind.READ

    def _ensure_initialised(self) -> KnowledgeStore | None:
        """Lazy init: discover git root, create store, auto-scan if empty."""
        if self._initialised:
            return self._store

        git_root = _find_git_root()
        if git_root is None:
            return None

        self._store = KnowledgeStore(git_root=git_root)
        self._store.load()

        if self._store.entity_count() == 0:
            scan_repository(self._store, git_root, incremental=True)
            self._store.save()

        self._initialised = True
        return self._store

    async def execute(self, **params: object) -> ToolResult:
        """Execute a knowledge graph query.

        Args:
            **params: Tool parameters (action, query, etc.).

        Returns:
            Formatted query results.
        """
        store = self._ensure_initialised()
        if store is None:
            return ToolResult(content="Not in a git repository — knowledge graph unavailable.")

        action = str(params.get("action", "search"))
        query = str(params.get("query", ""))
        entity_type = params.get("entity_type")

        # Safely convert depth and top_k to int
        depth_val = params.get("depth", 1)
        depth = int(depth_val) if isinstance(depth_val, (int, str)) and str(depth_val).isdigit() else 1

        top_k_val = params.get("top_k", 10)
        top_k = int(top_k_val) if isinstance(top_k_val, (int, str)) and str(top_k_val).isdigit() else 10

        if action == "search":
            if not query:
                return ToolResult(content="'query' is required for search action.")
            entities = store.search_entities(query)
            if entity_type:
                entities = [e for e in entities if e.entity_type == str(entity_type)]
            if not entities:
                return ToolResult(content=f"No entities found matching '{query}'.")
            return ToolResult(content=store.format_for_llm(entities))

        elif action == "get":
            if not query:
                return ToolResult(content="'query' (entity id) is required for get action.")
            entity = store.get_entity(query)
            if entity is None:
                return ToolResult(content=f"Entity '{query}' not found.")
            return ToolResult(content=store.format_entity_for_llm(entity))

        elif action == "neighbors":
            if not query:
                return ToolResult(content="'query' (entity id) is required for neighbors action.")
            neighbors = store.get_neighbors(query, depth=depth)
            if not neighbors:
                return ToolResult(content=f"No neighbors found for '{query}'.")
            return ToolResult(content=store.format_for_llm(neighbors))

        elif action == "relations":
            if not query:
                return ToolResult(content="'query' (entity id) is required for relations action.")
            relations = store.get_relations(query)
            if not relations:
                return ToolResult(content=f"No relations found for '{query}'.")
            lines = [f"# Relations for `{query}`\n"]
            for rel in relations:
                arrow = "→" if rel.source == query else "←"
                other = rel.target if rel.source == query else rel.source
                desc = f" ({rel.description})" if rel.description else ""
                lines.append(f"- {arrow} **{rel.relation_type}**: `{other}`{desc}")
            return ToolResult(content="\n".join(lines))

        elif action == "important":
            ranked = store.get_important_entities(top_k=top_k)
            if not ranked:
                return ToolResult(content="Knowledge graph is empty.")
            lines = ["# Most Important Entities (by PageRank)\n"]
            for entity, score in ranked:
                lines.append(
                    f"- **{entity.name}** ({entity.entity_type}) — "
                    f"score: {score:.4f}"
                )
            return ToolResult(content="\n".join(lines))

        elif action == "stats":
            components = store.get_connected_components()
            return ToolResult(
                content=(
                    f"# Knowledge Graph Stats\n\n"
                    f"- **Entities:** {store.entity_count()}\n"
                    f"- **Relations:** {store.relation_count()}\n"
                    f"- **Connected components:** {len(components)}\n"
                    f"- **Last indexed:** {store.meta.last_indexed or 'never'}"
                )
            )

        return ToolResult(content=f"Unknown action: '{action}'.")
