"""Knowledge graph query tool for agents.

Provides a READ tool that searches the project knowledge graph by
entity name/type, relations, full-text search, and importance ranking.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from henchman.knowledge.scanner import scan_repository
from henchman.knowledge.store import KnowledgeStore
from henchman.tools.base import ToolKind, ToolResult
from henchman.tools.builtins.kg_common import KgToolBase, _find_git_root
from henchman.tools.builtins.kg_update import VALID_ENTITY_TYPES

if TYPE_CHECKING:
    from henchman.knowledge.models import Relation

_DEFAULT_SEARCH_LIMIT = 10
"""Default number of results for the 'important' action."""


def _parse_int_param(value: object, default: int) -> int:
    """Safely coerce a parameter value to int, falling back to *default*."""
    if isinstance(value, (int, str)) and str(value).isdigit():
        return int(value)
    return default


def _format_relation_line(rel: Relation, query: str) -> str:
    """Format a single relation edge as a Markdown list item.

    Args:
        rel: The relation to format.
        query: The entity id that was queried (determines arrow direction).

    Returns:
        A Markdown list item string.
    """
    arrow = "→" if rel.source == query else "←"
    other = rel.target if rel.source == query else rel.source
    desc = f" ({rel.description})" if rel.description else ""
    return f"- {arrow} **{rel.relation_type}**: `{other}`{desc}"


def _format_stats_content(store: KnowledgeStore) -> str:
    """Build a Markdown summary of knowledge-graph statistics.

    Args:
        store: The KnowledgeStore to summarise.

    Returns:
        Formatted Markdown string.
    """
    components = store.get_connected_components()
    return (
        f"# Knowledge Graph Stats\n\n"
        f"- **Entities:** {store.entity_count()}\n"
        f"- **Relations:** {store.relation_count()}\n"
        f"- **Connected components:** {len(components)}\n"
        f"- **Last indexed:** {store.meta.last_indexed or 'never'}"
    )


class KgQueryTool(KgToolBase):
    """Query the project knowledge graph.

    Supports multiple actions: search, get, neighbors, relations,
    important, and stats.

    The graph is lazily initialised on first query — auto-scanning the
    repository if the graph is empty.
    """

    @property
    def name(self: KgQueryTool) -> str:
        """Tool name."""
        return "kg_query"

    @property
    def description(self: KgQueryTool) -> str:
        """Tool description."""
        return (
            "Query the project knowledge graph. Supports actions: "
            "'search' (full-text), 'get' (by id), 'neighbors' (graph traversal), "
            "'relations' (edges), 'important' (PageRank), 'stats' (summary)."
        )

    @property
    def parameters(self: KgQueryTool) -> dict[str, object]:  # noqa
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
                    "description": f"Number of results for 'important' (default {_DEFAULT_SEARCH_LIMIT}).",
                },
            },
            "required": ["action"],
        }

    @property
    def kind(self: KgQueryTool) -> ToolKind:
        """Read-only tool — auto-approved."""
        return ToolKind.READ

    def _ensure_initialised(self: KgQueryTool) -> KnowledgeStore | None:
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

    async def execute(self: KgQueryTool, **params: object) -> ToolResult:  # noqa: PLR0911
        """Execute a knowledge graph query.

        Args:
            params: Tool parameters passed as keyword arguments.
                Expected parameters:
                    action (str): Query action: 'search', 'get', 'neighbors',
                        'relations', 'important', or 'stats'.
                    query (str): Search term for 'search' action, or entity id for
                        'get'/'neighbors'/'relations'.
                    entity_type (str, optional): Filter by entity type: 'class',
                        'config', 'convention', 'decision', 'file', 'function',
                        'module', 'package', 'pattern', or 'service'.
                    depth (int, optional): Hop depth for 'neighbors'. Defaults to 1.
                    top_k (int, optional): Number of results for 'important'.
                        Defaults to 10.

        Returns:
            Formatted query results.
        """
        store = self._ensure_initialised()
        if store is None:
            return ToolResult(content="Not in a git repository — knowledge graph unavailable.")

        action = str(params.get("action", "search"))
        query = str(params.get("query", ""))
        entity_type = params.get("entity_type")

        depth_val = params.get("depth", 1)
        depth = _parse_int_param(depth_val, default=1)

        top_k_val = params.get("top_k", _DEFAULT_SEARCH_LIMIT)
        top_k = _parse_int_param(top_k_val, default=_DEFAULT_SEARCH_LIMIT)

        # Dispatch to appropriate handler method
        if action == "search":
            return self._handle_search(store, query, entity_type)
        if action == "get":
            return self._handle_get(store, query)
        if action == "neighbors":
            return self._handle_neighbors(store, query, depth)
        if action == "relations":
            return self._handle_relations(store, query)
        if action == "important":
            return self._handle_important(store, top_k)
        if action == "stats":
            return self._handle_stats(store)
        return ToolResult(content=f"Unknown action: '{action}'.")

    def _handle_search(
        self: KgQueryTool,
        store: KnowledgeStore,
        query: str,
        entity_type: object | None,
    ) -> ToolResult:
        """Handle search action."""
        if not query:
            return ToolResult(content="'query' is required for search action.")

        entities = store.search_entities(query)
        if entity_type:
            entities = [e for e in entities if e.entity_type == str(entity_type)]
        if not entities:
            return ToolResult(content=f"No entities found matching '{query}'.")

        return ToolResult(content=store.format_for_llm(entities))

    def _handle_get(self: KgQueryTool, store: KnowledgeStore, query: str) -> ToolResult:
        """Handle get action."""
        if not query:
            return ToolResult(content="'query' (entity id) is required for get action.")

        entity = store.get_entity(query)
        if entity is None:
            return ToolResult(content=f"Entity '{query}' not found.")

        return ToolResult(content=store.format_entity_for_llm(entity))

    def _handle_neighbors(
        self: KgQueryTool, store: KnowledgeStore, query: str, depth: int
    ) -> ToolResult:  # noqa: E501
        """Handle neighbors action."""
        if not query:
            return ToolResult(content="'query' (entity id) is required for neighbors action.")

        neighbors = store.get_neighbors(query, depth=depth)
        if not neighbors:
            return ToolResult(content=f"No neighbors found for '{query}'.")

        return ToolResult(content=store.format_for_llm(neighbors))

    def _handle_relations(self: KgQueryTool, store: KnowledgeStore, query: str) -> ToolResult:
        """Handle relations action."""
        if not query:
            return ToolResult(content="'query' (entity id) is required for relations action.")

        relations = store.get_relations(query)
        if not relations:
            return ToolResult(content=f"No relations found for '{query}'.")

        lines = [f"# Relations for `{query}`\n"]
        lines.extend(_format_relation_line(rel, query) for rel in relations)
        return ToolResult(content="\n".join(lines))

    def _handle_important(self: KgQueryTool, store: KnowledgeStore, top_k: int) -> ToolResult:
        """Handle important action."""
        ranked = store.get_important_entities(top_k=top_k)
        if not ranked:
            return ToolResult(content="Knowledge graph is empty.")

        lines = ["# Most Important Entities (by PageRank)\n"]
        for entity, score in ranked:
            lines.append(f"- **{entity.name}** ({entity.entity_type}) — score: {score:.4f}")

        return ToolResult(content="\n".join(lines))

    def _handle_stats(self: KgQueryTool, store: KnowledgeStore) -> ToolResult:
        """Handle stats action."""
        return ToolResult(content=_format_stats_content(store))
