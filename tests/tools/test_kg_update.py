"""Tests for the kg_update tool."""

from pathlib import Path

import pytest

from henchman.knowledge.models import Entity
from henchman.knowledge.store import KnowledgeStore
from henchman.tools.builtins.kg_update import KgUpdateTool


@pytest.fixture
def store(tmp_path: Path) -> KnowledgeStore:
    """Create a store with one entity."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    s = KnowledgeStore(git_root=repo, base_dir=tmp_path / "kg")
    s.add_entity(
        Entity(id="existing", entity_type="module", name="Existing", description="A module")
    )
    return s


@pytest.fixture
def tool(store: KnowledgeStore) -> KgUpdateTool:
    """Create an update tool with a pre-populated store."""
    return KgUpdateTool(store=store)


@pytest.mark.asyncio
async def test_add_entity(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """Add a new entity."""
    result = await tool.execute(
        action="add_entity",
        entity_id="new-thing",
        entity_type="decision",
        name="New Decision",
        description="We chose X over Y",
        tags=["architecture"],
    )
    assert "Added entity" in result.content
    assert store.get_entity("new-thing") is not None


@pytest.mark.asyncio
async def test_add_entity_defaults(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """Add entity with minimal params gets defaults."""
    result = await tool.execute(
        action="add_entity",
        entity_id="minimal",
    )
    assert "Added entity" in result.content
    e = store.get_entity("minimal")
    assert e is not None
    assert e.entity_type == "convention"  # default


@pytest.mark.asyncio
async def test_add_entity_with_file_path(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """Add entity with a file_path."""
    result = await tool.execute(
        action="add_entity",
        entity_id="fp",
        entity_type="file",
        name="FP",
        file_path="src/fp.py",
    )
    assert "Added entity" in result.content
    e = store.get_entity("fp")
    assert e is not None
    assert e.file_path == "src/fp.py"


@pytest.mark.asyncio
async def test_add_observation(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """Add observation to existing entity."""
    result = await tool.execute(
        action="add_observation",
        entity_id="existing",
        observation="Refactored in v2",
        source="code review",
    )
    assert "Added observation" in result.content
    e = store.get_entity("existing")
    assert e is not None
    assert len(e.observations) == 1
    assert "Refactored" in e.observations[0].content


@pytest.mark.asyncio
async def test_add_observation_missing_entity(tool: KgUpdateTool) -> None:
    """Adding observation to non-existent entity fails gracefully."""
    result = await tool.execute(
        action="add_observation",
        entity_id="nope",
        observation="something",
    )
    assert "not found" in result.content


@pytest.mark.asyncio
async def test_add_observation_missing_text(tool: KgUpdateTool) -> None:
    """Adding empty observation returns error."""
    result = await tool.execute(
        action="add_observation",
        entity_id="existing",
    )
    assert "required" in result.content


@pytest.mark.asyncio
async def test_add_relation(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """Add relation between entities."""
    store.add_entity(Entity(id="other", entity_type="module", name="Other"))
    result = await tool.execute(
        action="add_relation",
        entity_id="existing",
        target_id="other",
        relation_type="depends_on",
        description="runtime dependency",
    )
    assert "Added relation" in result.content
    assert store.relation_count() == 1


@pytest.mark.asyncio
async def test_add_relation_missing_target(tool: KgUpdateTool) -> None:
    """Adding relation without target returns error."""
    result = await tool.execute(
        action="add_relation",
        entity_id="existing",
    )
    assert "required" in result.content


@pytest.mark.asyncio
async def test_remove_entity(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """Remove an entity."""
    result = await tool.execute(
        action="remove_entity",
        entity_id="existing",
    )
    assert "Removed" in result.content
    assert store.get_entity("existing") is None


@pytest.mark.asyncio
async def test_remove_missing_entity(tool: KgUpdateTool) -> None:
    """Removing non-existent entity returns message."""
    result = await tool.execute(
        action="remove_entity",
        entity_id="nope",
    )
    assert "not found" in result.content


@pytest.mark.asyncio
async def test_missing_entity_id(tool: KgUpdateTool) -> None:
    """Missing entity_id returns error."""
    result = await tool.execute(action="add_entity")
    assert "required" in result.content


@pytest.mark.asyncio
async def test_invalid_entity_type(tool: KgUpdateTool) -> None:
    """Invalid entity_type returns validation error."""
    result = await tool.execute(
        action="add_entity",
        entity_id="bad-type",
        entity_type="widget",
    )
    assert "Invalid entity_type" in result.content
    assert "widget" in result.content


@pytest.mark.asyncio
async def test_invalid_relation_type(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """Invalid relation_type returns validation error."""
    store.add_entity(Entity(id="other", entity_type="module", name="Other"))
    result = await tool.execute(
        action="add_relation",
        entity_id="existing",
        target_id="other",
        relation_type="links_to",
    )
    assert "Invalid relation_type" in result.content


@pytest.mark.asyncio
async def test_add_relation_missing_endpoint(tool: KgUpdateTool) -> None:
    """Relation with non-existent source or target is rejected."""
    result = await tool.execute(
        action="add_relation",
        entity_id="existing",
        target_id="ghost",
        relation_type="depends_on",
    )
    assert "not found" in result.content
    assert "ghost" in result.content


@pytest.mark.asyncio
async def test_unknown_action(tool: KgUpdateTool) -> None:
    """Unknown action returns error."""
    result = await tool.execute(action="bogus", entity_id="x")
    assert "Unknown action" in result.content


@pytest.mark.asyncio
async def test_no_git_repo() -> None:
    """Tool without store and no git repo returns error."""
    import unittest.mock as mock

    t = KgUpdateTool(store=None)
    with mock.patch("henchman.tools.builtins.kg_update._find_git_root", return_value=None):
        result = await t.execute(action="add_entity", entity_id="x")
        assert "Not in a git repository" in result.content


@pytest.mark.asyncio
async def test_saves_after_write(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """Tool persists changes to disk after writes."""
    await tool.execute(
        action="add_entity",
        entity_id="persisted",
        entity_type="decision",
        name="Persisted",
    )
    # Load fresh store from same location
    store2 = KnowledgeStore(
        git_root=Path(store.meta.repo_path),
        base_dir=store.store_dir.parent,
    )
    store2.load()
    assert store2.get_entity("persisted") is not None


def test_tool_properties() -> None:
    """Tool exposes correct name, kind, parameters."""
    t = KgUpdateTool()
    assert t.name == "kg_update"
    assert t.kind.name == "WRITE"
    assert "action" in t.parameters["properties"]  # type: ignore[index]


async def test_no_git_repo_update() -> None:
    """Update without git repo returns error."""
    import unittest.mock as mock

    t = KgUpdateTool(store=None)
    t._initialised = False
    with mock.patch("henchman.tools.builtins.kg_update._find_git_root", return_value=None):
        result = await t.execute(action="add_entity", entity_id="foo", entity_type="module")
        assert "Not in a git repository" in result.content


async def test_add_entity_name_defaults_to_id(tool: KgUpdateTool, store: KnowledgeStore) -> None:
    """add_entity uses entity_id as name when name is empty string (line 226)."""
    result = await tool.execute(
        action="add_entity",
        entity_id="my-thing",
        entity_type="decision",
        description="A decision",
        name="",  # empty string → fallback to entity_id
    )
    assert result.success is True
    entity = store.get_entity("my-thing")
    assert entity is not None
    assert entity.name == "my-thing"


async def test_add_relation_missing_entity(tool: KgUpdateTool) -> None:
    """add_relation fails when entity not found."""
    result = await tool.execute(
        action="add_relation",
        entity_id="nonexistent",
        target_id="also-nonexistent",
        relation_type="depends_on",
    )
    assert "not found" in result.content


def test_kg_update_description() -> None:
    """KgUpdateTool.description property returns non-empty string."""
    from henchman.tools.builtins.kg_update import KgUpdateTool
    tool = KgUpdateTool()
    assert len(tool.description) > 10
    assert "update" in tool.description.lower() or "entity" in tool.description.lower()


async def test_lazy_init_with_real_git_root(tmp_path: Path) -> None:
    """_ensure_initialised creates store when git root is found."""
    import unittest.mock as mock

    from henchman.knowledge.store import KnowledgeStore
    from henchman.tools.builtins.kg_update import KgUpdateTool

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    tool = KgUpdateTool(store=None)
    tool._initialised = False

    with (
        mock.patch(
            "henchman.tools.builtins.kg_update._find_git_root",
            return_value=repo,
        ),
        mock.patch.object(KnowledgeStore, "load", return_value=None),
    ):
        store = tool._ensure_initialised()
        assert store is not None
        assert tool._initialised is True
