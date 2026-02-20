"""Tests for the kg_query tool."""

from pathlib import Path

import pytest

from henchman.knowledge.models import Entity, Observation, Relation
from henchman.knowledge.store import KnowledgeStore
from henchman.tools.builtins.kg_query import KgQueryTool


@pytest.fixture
def store(tmp_path: Path) -> KnowledgeStore:
    """Create a populated store."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    s = KnowledgeStore(git_root=repo, base_dir=tmp_path / "kg")

    s.add_entity(
        Entity(
            id="auth",
            entity_type="module",
            name="Auth Module",
            description="Handles JWT authentication",
            file_path="src/auth.py",
            tags=["security"],
            observations=[Observation(content="uses bcrypt", source="review")],
        )
    )
    s.add_entity(
        Entity(
            id="db",
            entity_type="module",
            name="Database",
            description="PostgreSQL connection pool",
            file_path="src/db.py",
        )
    )
    s.add_relation(Relation(source="auth", target="db", relation_type="depends_on"))
    return s


@pytest.fixture
def tool(store: KnowledgeStore) -> KgQueryTool:
    """Create a query tool with a pre-populated store."""
    return KgQueryTool(store=store)


@pytest.mark.asyncio
async def test_search(tool: KgQueryTool) -> None:
    """Search finds entities by text."""
    result = await tool.execute(action="search", query="jwt")
    assert "Auth Module" in result.content


@pytest.mark.asyncio
async def test_search_with_type_filter(tool: KgQueryTool) -> None:
    """Search can filter by entity type."""
    result = await tool.execute(action="search", query="module", entity_type="module")
    assert "Auth" in result.content or "Database" in result.content


@pytest.mark.asyncio
async def test_search_no_results(tool: KgQueryTool) -> None:
    """Search returns message when nothing found."""
    result = await tool.execute(action="search", query="nonexistent123")
    assert "No entities found" in result.content


@pytest.mark.asyncio
async def test_search_missing_query(tool: KgQueryTool) -> None:
    """Search without query returns error."""
    result = await tool.execute(action="search")
    assert "required" in result.content


@pytest.mark.asyncio
async def test_get(tool: KgQueryTool) -> None:
    """Get retrieves entity by id."""
    result = await tool.execute(action="get", query="auth")
    assert "Auth Module" in result.content
    assert "src/auth.py" in result.content


@pytest.mark.asyncio
async def test_get_missing(tool: KgQueryTool) -> None:
    """Get returns message for missing entity."""
    result = await tool.execute(action="get", query="nope")
    assert "not found" in result.content


@pytest.mark.asyncio
async def test_get_missing_query(tool: KgQueryTool) -> None:
    """Get without query returns error."""
    result = await tool.execute(action="get")
    assert "required" in result.content


@pytest.mark.asyncio
async def test_neighbors(tool: KgQueryTool) -> None:
    """Neighbors returns connected entities."""
    result = await tool.execute(action="neighbors", query="auth")
    assert "Database" in result.content


@pytest.mark.asyncio
async def test_neighbors_missing(tool: KgQueryTool) -> None:
    """Neighbors of non-existent entity returns message."""
    result = await tool.execute(action="neighbors", query="nope")
    assert "No neighbors" in result.content


@pytest.mark.asyncio
async def test_neighbors_missing_query(tool: KgQueryTool) -> None:
    """Neighbors without query returns error."""
    result = await tool.execute(action="neighbors")
    assert "required" in result.content


@pytest.mark.asyncio
async def test_relations(tool: KgQueryTool) -> None:
    """Relations returns edges for an entity."""
    result = await tool.execute(action="relations", query="auth")
    assert "depends_on" in result.content
    assert "db" in result.content


@pytest.mark.asyncio
async def test_relations_missing(tool: KgQueryTool) -> None:
    """Relations for entity with no edges returns message."""
    result = await tool.execute(action="relations", query="nope")
    assert "No relations" in result.content


@pytest.mark.asyncio
async def test_relations_missing_query(tool: KgQueryTool) -> None:
    """Relations without query returns error."""
    result = await tool.execute(action="relations")
    assert "required" in result.content


@pytest.mark.asyncio
async def test_important(tool: KgQueryTool) -> None:
    """Important returns PageRank-sorted entities."""
    result = await tool.execute(action="important", top_k=5)
    assert "Most Important" in result.content


@pytest.mark.asyncio
async def test_important_empty() -> None:
    """Important on empty graph returns message."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        s = KnowledgeStore(git_root=repo, base_dir=Path(td) / "kg")
        t = KgQueryTool(store=s)
        result = await t.execute(action="important")
        assert "empty" in result.content


@pytest.mark.asyncio
async def test_stats(tool: KgQueryTool) -> None:
    """Stats returns summary."""
    result = await tool.execute(action="stats")
    assert "Entities:" in result.content
    assert "Relations:" in result.content


@pytest.mark.asyncio
async def test_unknown_action(tool: KgQueryTool) -> None:
    """Unknown action returns error."""
    result = await tool.execute(action="bogus")
    assert "Unknown action" in result.content


@pytest.mark.asyncio
async def test_no_git_repo() -> None:
    """Tool without store and no git repo returns error."""
    t = KgQueryTool(store=None)
    # Force initialisation to skip (no git root)
    t._initialised = False
    import unittest.mock as mock

    with mock.patch("henchman.tools.builtins.kg_query._find_git_root", return_value=None):
        result = await t.execute(action="stats")
        assert "Not in a git repository" in result.content


def test_tool_properties() -> None:
    """Tool exposes correct name, kind, parameters."""
    t = KgQueryTool()
    assert t.name == "kg_query"
    assert t.kind.name == "READ"
    assert "action" in t.parameters["properties"]  # type: ignore[index]
