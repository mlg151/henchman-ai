"""Tests for knowledge graph data models."""

from henchman.knowledge.models import Entity, GraphMeta, Observation, Relation


def test_observation_defaults() -> None:
    """Observation gets auto-timestamp and default author."""
    obs = Observation(content="fact", source="file.py:10")
    assert obs.content == "fact"
    assert obs.source == "file.py:10"
    assert obs.author == "agent"
    assert obs.timestamp  # non-empty


def test_observation_custom_author() -> None:
    """Auto-scanner observations use author='auto'."""
    obs = Observation(content="has 3 imports", source="scanner", author="auto")
    assert obs.author == "auto"


def test_relation_fields() -> None:
    """Relation captures source, target, type."""
    rel = Relation(source="a", target="b", relation_type="imports")
    assert rel.source == "a"
    assert rel.target == "b"
    assert rel.relation_type == "imports"
    assert rel.description == ""


def test_relation_with_description() -> None:
    """Relation description is optional."""
    rel = Relation(
        source="a",
        target="b",
        relation_type="depends_on",
        description="runtime dep",
    )
    assert rel.description == "runtime dep"


def test_entity_minimal() -> None:
    """Entity with required fields only."""
    e = Entity(id="foo", entity_type="file", name="foo.py")
    assert e.id == "foo"
    assert e.entity_type == "file"
    assert e.name == "foo.py"
    assert e.description == ""
    assert e.file_path is None
    assert e.tags == []
    assert e.observations == []


def test_entity_full() -> None:
    """Entity with all fields populated."""
    obs = Observation(content="handles auth", source="review")
    e = Entity(
        id="auth-module",
        entity_type="module",
        name="Auth Module",
        description="Handles authentication",
        file_path="src/auth.py",
        tags=["security", "core"],
        observations=[obs],
    )
    assert e.file_path == "src/auth.py"
    assert len(e.observations) == 1
    assert "security" in e.tags


def test_entity_serialization_roundtrip() -> None:
    """Entity survives JSON roundtrip via Pydantic."""
    e = Entity(
        id="x",
        entity_type="class",
        name="X",
        description="desc",
        observations=[Observation(content="note", source="test")],
    )
    data = e.model_dump(mode="json")
    restored = Entity.model_validate(data)
    assert restored.id == "x"
    assert len(restored.observations) == 1
    assert restored.observations[0].content == "note"


def test_graph_meta_defaults() -> None:
    """GraphMeta has sensible defaults."""
    meta = GraphMeta(repo_path="/tmp/repo", repo_hash="abc123")
    assert meta.schema_version == 1
    assert meta.last_indexed == ""
    assert meta.file_hashes == {}


def test_graph_meta_with_hashes() -> None:
    """GraphMeta stores file hashes for incremental indexing."""
    meta = GraphMeta(
        repo_path="/tmp/repo",
        repo_hash="abc123",
        file_hashes={"a.py": "hash1", "b.py": "hash2"},
    )
    assert len(meta.file_hashes) == 2
