"""Tests for KnowledgeStore."""

from pathlib import Path

import pytest

from henchman.knowledge.models import Entity, Observation, Relation
from henchman.knowledge.store import KnowledgeStore, _slugify

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_root(tmp_path: Path) -> Path:
    """Create a minimal git repo for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()  # enough for compute_repository_id
    return repo


@pytest.fixture
def store(git_root: Path, tmp_path: Path) -> KnowledgeStore:
    """Create a KnowledgeStore with temporary storage."""
    return KnowledgeStore(git_root=git_root, base_dir=tmp_path / "kg")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(eid: str = "test-entity", etype: str = "file") -> Entity:
    return Entity(
        id=eid,
        entity_type=etype,
        name=eid.replace("-", " ").title(),
        description=f"Description of {eid}",
        file_path=f"src/{eid}.py",
        tags=["test"],
    )


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_path() -> None:
    """Paths get normalised to slugs."""
    assert _slugify("src/henchman/core/agent.py") == "src-henchman-core-agent-py"


def test_slugify_dots_underscores() -> None:
    """Dots and underscores become dashes."""
    assert _slugify("my_module.utils") == "my-module-utils"


# ---------------------------------------------------------------------------
# Entity CRUD
# ---------------------------------------------------------------------------


def test_add_and_get_entity(store: KnowledgeStore) -> None:
    """Entity round-trips through add/get."""
    entity = _make_entity()
    store.add_entity(entity)
    result = store.get_entity("test-entity")
    assert result is not None
    assert result.name == entity.name
    assert result.entity_type == "file"


def test_get_missing_entity(store: KnowledgeStore) -> None:
    """Getting a non-existent entity returns None."""
    assert store.get_entity("nope") is None


def test_remove_entity(store: KnowledgeStore) -> None:
    """Removing an entity also removes its edges."""
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    store.add_relation(Relation(source="a", target="b", relation_type="imports"))

    assert store.remove_entity("a")
    assert store.get_entity("a") is None
    assert store.relation_count() == 0


def test_remove_missing_entity(store: KnowledgeStore) -> None:
    """Removing a non-existent entity returns False."""
    assert not store.remove_entity("nope")


def test_list_entities_all(store: KnowledgeStore) -> None:
    """List all entities without filter."""
    store.add_entity(_make_entity("a", "file"))
    store.add_entity(_make_entity("b", "module"))
    assert len(store.list_entities()) == 2


def test_list_entities_by_type(store: KnowledgeStore) -> None:
    """Filter entities by type."""
    store.add_entity(_make_entity("a", "file"))
    store.add_entity(_make_entity("b", "module"))
    files = store.list_entities(entity_type="file")
    assert len(files) == 1
    assert files[0].entity_type == "file"


def test_list_entities_by_tag(store: KnowledgeStore) -> None:
    """Filter entities by tag."""
    e1 = _make_entity("a")
    e1.tags = ["core"]
    e2 = _make_entity("b")
    e2.tags = ["test"]
    store.add_entity(e1)
    store.add_entity(e2)
    core = store.list_entities(tag="core")
    assert len(core) == 1


def test_search_entities(store: KnowledgeStore) -> None:
    """Full-text search over names and descriptions."""
    store.add_entity(
        Entity(
            id="auth",
            entity_type="module",
            name="Authentication",
            description="Handles JWT tokens",
        )
    )
    store.add_entity(
        Entity(id="db", entity_type="module", name="Database", description="PostgreSQL")
    )
    results = store.search_entities("jwt")
    assert len(results) == 1
    assert results[0].id == "auth"


def test_search_entities_in_observations(store: KnowledgeStore) -> None:
    """Search matches observation content too."""
    e = _make_entity("x")
    e.observations = [Observation(content="uses redis for caching", source="agent")]
    store.add_entity(e)
    assert len(store.search_entities("redis")) == 1


# ---------------------------------------------------------------------------
# Observations
# ---------------------------------------------------------------------------


def test_add_observation(store: KnowledgeStore) -> None:
    """Add observation to existing entity."""
    store.add_entity(_make_entity("a"))
    obs = Observation(content="refactored recently", source="agent")
    assert store.add_observation("a", obs)
    entity = store.get_entity("a")
    assert entity is not None
    assert len(entity.observations) == 1
    assert entity.observations[0].content == "refactored recently"


def test_add_observation_missing_entity(store: KnowledgeStore) -> None:
    """Adding observation to non-existent entity returns False."""
    obs = Observation(content="x", source="y")
    assert not store.add_observation("nope", obs)


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


def test_add_and_get_relations(store: KnowledgeStore) -> None:
    """Relations round-trip through add/get."""
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    rel = Relation(source="a", target="b", relation_type="imports")
    store.add_relation(rel)

    out = store.get_relations("a", direction="out")
    assert len(out) == 1
    assert out[0].target == "b"
    assert out[0].relation_type == "imports"

    inc = store.get_relations("b", direction="in")
    assert len(inc) == 1
    assert inc[0].source == "a"


def test_get_relations_both(store: KnowledgeStore) -> None:
    """direction='both' returns in + out edges."""
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    store.add_entity(_make_entity("c"))
    store.add_relation(Relation(source="a", target="b", relation_type="imports"))
    store.add_relation(Relation(source="c", target="a", relation_type="imports"))

    both = store.get_relations("a", direction="both")
    assert len(both) == 2


def test_remove_relation(store: KnowledgeStore) -> None:
    """Remove a specific edge."""
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    store.add_relation(Relation(source="a", target="b", relation_type="imports"))
    assert store.remove_relation("a", "b")
    assert store.relation_count() == 0


def test_remove_missing_relation(store: KnowledgeStore) -> None:
    """Removing non-existent edge returns False."""
    assert not store.remove_relation("a", "b")


# ---------------------------------------------------------------------------
# Graph queries
# ---------------------------------------------------------------------------


def test_get_neighbors(store: KnowledgeStore) -> None:
    """Neighbors within 1 hop."""
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    store.add_entity(_make_entity("c"))
    store.add_relation(Relation(source="a", target="b", relation_type="imports"))
    store.add_relation(Relation(source="b", target="c", relation_type="imports"))

    neighbors = store.get_neighbors("a", depth=1)
    ids = {e.id for e in neighbors}
    assert "b" in ids
    assert "c" not in ids  # 2 hops away


def test_get_neighbors_depth_2(store: KnowledgeStore) -> None:
    """Neighbors within 2 hops."""
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    store.add_entity(_make_entity("c"))
    store.add_relation(Relation(source="a", target="b", relation_type="imports"))
    store.add_relation(Relation(source="b", target="c", relation_type="imports"))

    neighbors = store.get_neighbors("a", depth=2)
    ids = {e.id for e in neighbors}
    assert "b" in ids
    assert "c" in ids


def test_get_neighbors_missing_entity(store: KnowledgeStore) -> None:
    """Neighbors of non-existent entity returns empty list."""
    assert store.get_neighbors("nope") == []


def test_get_important_entities(store: KnowledgeStore) -> None:
    """PageRank returns entities sorted by importance."""
    for i in range(5):
        store.add_entity(_make_entity(f"n{i}"))
    # n0 is imported by everyone else
    for i in range(1, 5):
        store.add_relation(
            Relation(source=f"n{i}", target="n0", relation_type="imports")
        )
    ranked = store.get_important_entities(top_k=3)
    assert len(ranked) == 3
    assert ranked[0][0].id == "n0"  # most imported


def test_get_important_entities_empty(store: KnowledgeStore) -> None:
    """PageRank on empty graph returns empty list."""
    assert store.get_important_entities() == []


def test_get_connected_components(store: KnowledgeStore) -> None:
    """Connected components identifies clusters."""
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    store.add_entity(_make_entity("c"))
    store.add_relation(Relation(source="a", target="b", relation_type="imports"))
    # c is isolated
    components = store.get_connected_components()
    assert len(components) == 2


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_save_and_load(store: KnowledgeStore, git_root: Path, tmp_path: Path) -> None:
    """Graph survives save/load cycle."""
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    store.add_relation(Relation(source="a", target="b", relation_type="imports"))
    store.add_observation("a", Observation(content="note", source="test"))
    store.save()

    # Create new store instance pointing at same location
    store2 = KnowledgeStore(git_root=git_root, base_dir=tmp_path / "kg")
    store2.load()

    assert store2.entity_count() == 2
    assert store2.relation_count() == 1
    entity_a = store2.get_entity("a")
    assert entity_a is not None
    assert len(entity_a.observations) == 1


def test_load_empty(store: KnowledgeStore) -> None:
    """Loading from non-existent directory yields empty graph."""
    store.load()
    assert store.entity_count() == 0


# ---------------------------------------------------------------------------
# Bulk helpers
# ---------------------------------------------------------------------------


def test_entity_and_relation_count(store: KnowledgeStore) -> None:
    """Count helpers return correct values."""
    assert store.entity_count() == 0
    assert store.relation_count() == 0
    store.add_entity(_make_entity("a"))
    store.add_entity(_make_entity("b"))
    store.add_relation(Relation(source="a", target="b", relation_type="x"))
    assert store.entity_count() == 2
    assert store.relation_count() == 1


def test_clear(store: KnowledgeStore) -> None:
    """Clear removes everything."""
    store.add_entity(_make_entity("a"))
    store.add_relation(Relation(source="a", target="a", relation_type="self"))
    store.clear()
    assert store.entity_count() == 0
    assert store.relation_count() == 0


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def test_format_entity_for_llm(store: KnowledgeStore) -> None:
    """LLM formatting includes key fields."""
    e = Entity(
        id="auth",
        entity_type="module",
        name="Auth",
        description="Handles auth",
        file_path="src/auth.py",
        tags=["security"],
        observations=[Observation(content="uses JWT", source="review")],
    )
    store.add_entity(e)
    text = store.format_entity_for_llm(e)
    assert "Auth" in text
    assert "module" in text
    assert "src/auth.py" in text
    assert "security" in text
    assert "uses JWT" in text


def test_format_for_llm_caps_output(store: KnowledgeStore) -> None:
    """format_for_llm respects max_entities."""
    for i in range(10):
        store.add_entity(_make_entity(f"e{i}"))
    entities = store.list_entities()
    text = store.format_for_llm(entities, max_entities=3)
    assert "3/10" in text
