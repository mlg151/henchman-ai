"""Knowledge graph update tool for agents.

Provides a WRITE tool that adds entities, observations, and relations
to the project knowledge graph.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from henchman.knowledge.models import Entity, Observation, Relation
from henchman.knowledge.store import KnowledgeStore
from henchman.tools.base import Tool, ToolKind, ToolResult

# Allowed values ---------------------------------------------------------------

VALID_ENTITY_TYPES = frozenset(
    {
        "file",
        "module",
        "package",
        "class",
        "function",
        "decision",
        "convention",
        "pattern",
        "config",
        "service",
    }
)

VALID_RELATION_TYPES = frozenset(
    {
        "imports",
        "depends_on",
        "contains",
        "implements",
        "tests",
        "related_to",
        "decided_by",
        "configures",
        "extends",
    }
)


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


def _validate_id(raw: object) -> str | None:
    """Return a cleaned entity id or None if invalid."""
    text = str(raw).strip() if raw else ""
    if not text or text == "None":
        return None
    return text


class KgUpdateTool(Tool):
    """Update the project knowledge graph.

    Supports actions: add_entity, add_observation, add_relation,
    and remove_entity.  Changes are persisted to disk after each call.
    """

    def __init__(self, store: KnowledgeStore | None = None) -> None:
        """Initialise the knowledge graph update tool.

        Args:
            store: Optional pre-built store.  When ``None`` the tool
                will auto-discover the git root and create one.
        """
        self._store = store
        self._initialised = store is not None

    @property
    def name(self) -> str:
        """Tool name."""
        return "kg_update"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Update the project knowledge graph. Supports actions: "
            "'add_entity', 'add_observation', 'add_relation', 'remove_entity'. "
            "Use this to record architectural decisions, conventions, patterns, "
            "and facts learned during investigation."
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
                        "add_entity",
                        "add_observation",
                        "add_relation",
                        "remove_entity",
                    ],
                    "description": "The update action to perform.",
                },
                "entity_id": {
                    "type": "string",
                    "description": "Entity id (slug) for all actions.",
                },
                "entity_type": {
                    "type": "string",
                    "enum": sorted(VALID_ENTITY_TYPES),
                    "description": "Type for add_entity.",
                },
                "name": {
                    "type": "string",
                    "description": "Human-readable name for add_entity.",
                },
                "description": {
                    "type": "string",
                    "description": "Description for add_entity or add_observation content.",
                },
                "file_path": {
                    "type": "string",
                    "description": "Source file path for add_entity.",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for add_entity.",
                },
                "observation": {
                    "type": "string",
                    "description": "Observation text for add_observation.",
                },
                "source": {
                    "type": "string",
                    "description": "Source citation for add_observation.",
                },
                "target_id": {
                    "type": "string",
                    "description": "Target entity id for add_relation.",
                },
                "relation_type": {
                    "type": "string",
                    "enum": sorted(VALID_RELATION_TYPES),
                    "description": "Relation type for add_relation.",
                },
            },
            "required": ["action", "entity_id"],
        }

    @property
    def kind(self) -> ToolKind:
        """Write tool — requires confirmation."""
        return ToolKind.WRITE

    def _ensure_initialised(self) -> KnowledgeStore | None:
        """Lazy init: discover git root, create store, load from disk."""
        if self._initialised:
            return self._store

        git_root = _find_git_root()
        if git_root is None:
            return None

        self._store = KnowledgeStore(git_root=git_root)
        self._store.load()
        self._initialised = True
        return self._store

    async def execute(self, **params: object) -> ToolResult:
        """Execute a knowledge graph update.

        Args:
            **params: Tool parameters (action, entity_id, etc.).

        Returns:
            Confirmation message.
        """
        store = self._ensure_initialised()
        if store is None:
            return ToolResult(content="Not in a git repository — knowledge graph unavailable.")

        action = str(params.get("action", ""))
        entity_id = _validate_id(params.get("entity_id"))

        if not entity_id:
            return ToolResult(content="'entity_id' is required and must be a non-empty string.")

        # Dispatch to appropriate handler method
        if action == "add_entity":
            return self._handle_add_entity(store, entity_id, params)
        elif action == "add_observation":
            return self._handle_add_observation(store, entity_id, params)
        elif action == "add_relation":
            return self._handle_add_relation(store, entity_id, params)
        elif action == "remove_entity":
            return self._handle_remove_entity(store, entity_id)

        return ToolResult(content=f"Unknown action: '{action}'.")

    def _handle_add_entity(
        self, store: KnowledgeStore, entity_id: str, params: dict[str, object]
    ) -> ToolResult:
        """Handle add_entity action."""
        entity_type = str(params.get("entity_type", "convention")).strip()
        if entity_type not in VALID_ENTITY_TYPES:
            return ToolResult(
                content=(
                    f"Invalid entity_type '{entity_type}'. "
                    f"Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}."
                )
            )

        name = str(params.get("name", entity_id)).strip()
        if not name:
            name = entity_id

        description = str(params.get("description") or "")
        file_path = params.get("file_path")
        tags = params.get("tags", [])

        entity = Entity(
            id=entity_id,
            entity_type=entity_type,
            name=name,
            description=description,
            file_path=str(file_path) if file_path and str(file_path) != "None" else None,
            tags=list(tags) if isinstance(tags, (list, tuple)) else [],
        )
        store.add_entity(entity)
        store.save()
        return ToolResult(content=f"Added entity '{entity_id}' ({entity_type}).")

    def _handle_add_observation(
        self, store: KnowledgeStore, entity_id: str, params: dict[str, object]
    ) -> ToolResult:
        """Handle add_observation action."""
        observation_text = str(
            params.get("observation") or params.get("description") or ""
        ).strip()
        source = str(params.get("source") or "agent").strip()

        if not observation_text:
            return ToolResult(content="'observation' or 'description' is required.")

        if store.get_entity(entity_id) is None:
            return ToolResult(
                content=f"Entity '{entity_id}' not found. Add it first with add_entity."
            )

        obs = Observation(content=observation_text, source=source, author="agent")
        store.add_observation(entity_id, obs)
        store.save()
        return ToolResult(content=f"Added observation to '{entity_id}': {observation_text}")

    def _handle_add_relation(
        self, store: KnowledgeStore, entity_id: str, params: dict[str, object]
    ) -> ToolResult:
        """Handle add_relation action."""
        target_id = _validate_id(params.get("target_id"))
        if not target_id:
            return ToolResult(content="'target_id' is required for add_relation.")

        relation_type = str(params.get("relation_type", "related_to")).strip()
        if relation_type not in VALID_RELATION_TYPES:
            return ToolResult(
                content=(
                    f"Invalid relation_type '{relation_type}'. "
                    f"Must be one of: {', '.join(sorted(VALID_RELATION_TYPES))}."
                )
            )

        # Both endpoints must exist
        missing = []
        if store.get_entity(entity_id) is None:
            missing.append(entity_id)
        if store.get_entity(target_id) is None:
            missing.append(target_id)
        if missing:
            return ToolResult(
                content=(
                    f"Cannot add relation — entity not found: "
                    f"{', '.join(repr(m) for m in missing)}. "
                    f"Add them first with add_entity."
                )
            )

        description = str(params.get("description") or "")
        rel = Relation(
            source=entity_id,
            target=target_id,
            relation_type=relation_type,
            description=description,
        )
        store.add_relation(rel)
        store.save()
        return ToolResult(
            content=(f"Added relation: '{entity_id}' —[{relation_type}]→ '{target_id}'.")
        )

    def _handle_remove_entity(
        self, store: KnowledgeStore, entity_id: str
    ) -> ToolResult:
        """Handle remove_entity action."""
        if store.remove_entity(entity_id):
            store.save()
            return ToolResult(content=f"Removed entity '{entity_id}'.")
        return ToolResult(content=f"Entity '{entity_id}' not found.")
