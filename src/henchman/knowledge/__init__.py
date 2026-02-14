"""Knowledge graph system for persistent project understanding.

Provides a graph-based knowledge store backed by NetworkX for structure
and ChromaDB for semantic search over entity descriptions.
"""

from henchman.knowledge.models import Entity, GraphMeta, Observation, Relation
from henchman.knowledge.store import KnowledgeStore

__all__ = [
    "Entity",
    "GraphMeta",
    "KnowledgeStore",
    "Observation",
    "Relation",
]
