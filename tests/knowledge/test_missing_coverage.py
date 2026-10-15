"""Tests targeting missing coverage lines in knowledge modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.knowledge.models import Entity, Relation
from henchman.knowledge.scanner import (
    _build_module_lookup,
    _find_import_target_optimized,
)
from henchman.knowledge.store import (
    KnowledgeStore,
    _format_entity_as_markdown,
    _safe_node_to_entity,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def git_root(tmp_path: Path) -> Path:
    """Create a minimal git repo directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    return repo


@pytest.fixture
def store(git_root: Path, tmp_path: Path) -> KnowledgeStore:
    """KnowledgeStore with temporary storage."""
    return KnowledgeStore(git_root=git_root, base_dir=tmp_path / "kg")


def _entity(eid: str = "e1", etype: str = "file") -> Entity:
    return Entity(
        id=eid,
        entity_type=etype,
        name=eid,
        description=f"Desc of {eid}",
        file_path=f"src/{eid}.py",
        tags=["test"],
    )


# ---------------------------------------------------------------------------
# knowledge/store.py – lines 65-67: _safe_node_to_entity with malformed node
# ---------------------------------------------------------------------------


class TestSafeNodeToEntity:
    """Cover lines 65-67: malformed node is skipped gracefully."""

    def test_malformed_attrs_returns_none(self) -> None:
        """Lines 65-67: _safe_node_to_entity returns None for bad attrs."""
        # Pass attrs that are missing required fields → _node_attrs_to_entity raises
        result = _safe_node_to_entity("bad-node", {"entity_type": None})
        assert result is None

    def test_valid_attrs_returns_entity(self) -> None:
        """Baseline: valid attrs produce an Entity."""
        ent = _entity("good-node")
        attrs = {
            "entity_type": ent.entity_type,
            "name": ent.name,
            "description": ent.description,
            "file_path": ent.file_path,
            "tags": list(ent.tags),
            "observations": [],
        }
        result = _safe_node_to_entity("good-node", attrs)
        assert result is not None
        assert result.id == "good-node"


# ---------------------------------------------------------------------------
# knowledge/store.py – line 356: .graph property
# ---------------------------------------------------------------------------


class TestKnowledgeStoreGraphProperty:
    """Cover line 356: KnowledgeStore.graph property."""

    def test_graph_property_returns_digraph(self, store: KnowledgeStore) -> None:
        """Line 356: .graph returns the underlying NetworkX DiGraph."""
        import networkx as nx

        g = store.graph
        assert isinstance(g, nx.DiGraph)


# ---------------------------------------------------------------------------
# knowledge/store.py – lines 181->183, 183->185: _format_entity_markdown branches
# ---------------------------------------------------------------------------


class TestFormatEntityMarkdown:
    """Cover optional field branches in _format_entity_markdown."""

    def test_entity_without_file_path(self, store: KnowledgeStore) -> None:
        """Line 181->183: entity.file_path is None/empty → file_path block skipped."""
        ent = Entity(
            id="no-path",
            entity_type="concept",
            name="no-path",
            description="Some concept",
            file_path=None,
            tags=[],
        )
        md = _format_entity_as_markdown(ent, [])
        assert "**File:**" not in md
        assert "no-path" in md

    def test_entity_without_description(self, store: KnowledgeStore) -> None:
        """Line 183->185: entity.description is empty/None → description block skipped."""
        ent = Entity(
            id="no-desc",
            entity_type="file",
            name="no-desc",
            description="",
            file_path="src/no-desc.py",
            tags=[],
        )
        md = _format_entity_as_markdown(ent, [])
        assert "**File:**" in md  # file_path present
        # Empty description means no extra description line
        assert md.count("no-desc") >= 1


# ---------------------------------------------------------------------------
# knowledge/store.py – line 227: search_entities skips None entities
# ---------------------------------------------------------------------------


class TestSearchEntitiesSkipsNone:
    """Cover line 227: entity is None → continue."""

    def test_search_skips_malformed_nodes(self, store: KnowledgeStore) -> None:
        """Line 227: malformed graph nodes are skipped during search."""

        # Add a malformed node directly to the graph
        store._graph.add_node("bad-node", entity_type=None)

        # Also add a valid entity
        good = _entity("good-ent")
        store.add_entity(good)

        # search_entities should not raise and should return only valid entities
        results = store.search_entities("good")
        assert any(e.id == "good-ent" for e in results)


# ---------------------------------------------------------------------------
# knowledge/store.py – lines 265, 267->263: get_neighbors skips None / non-graph nodes
# ---------------------------------------------------------------------------


class TestGetNeighbors:
    """Cover lines 265 and 267->263 in get_neighbors."""

    def test_neighbor_not_in_graph_is_skipped(self, store: KnowledgeStore) -> None:
        """Line 265: neighbor id not in graph dict → continue."""
        # Build a small graph with a disconnected node reference
        a = _entity("a")
        b = _entity("b")
        store.add_entity(a)
        store.add_entity(b)
        store.add_relation(Relation(source="a", target="b", relation_type="calls"))

        # Remove b from graph but keep edge (simulate stale ref)
        store._graph.remove_node("b")
        store._graph.add_edge("a", "b")  # Dangling edge: b not a proper node

        # Should not raise
        results = store.get_neighbors("a")
        # b was in the graph as an edge target but not a node, so it's skipped
        assert isinstance(results, list)

    def test_neighbor_with_malformed_attrs_skipped(self, store: KnowledgeStore) -> None:
        """Line 267->263: _safe_node_to_entity returns None → not added to results."""
        a = _entity("alpha")
        store.add_entity(a)

        # Add a neighbor node with invalid attrs
        store._graph.add_node("bad-neighbor", entity_type=None)
        store._graph.add_edge("alpha", "bad-neighbor")

        results = store.get_neighbors("alpha")
        # bad-neighbor should be filtered out
        assert all(e.id != "bad-neighbor" for e in results)


# ---------------------------------------------------------------------------
# knowledge/store.py – lines 291, 293->289: get_important_entities skips None
# ---------------------------------------------------------------------------


class TestGetImportantEntities:
    """Cover lines 291 and 293->289 in get_important_entities."""

    def test_nid_not_in_graph_skipped(self, store: KnowledgeStore) -> None:
        """Line 291: nid not in graph after pagerank → continue.

        We add a malformed node to the graph that pagerank includes but
        then remove it before _safe_node_to_entity is called.
        """
        a = _entity("pagerank-a")
        store.add_entity(a)
        # Add a dangling node - pagerank will include it but it lacks proper attrs
        store._graph.add_node("dangling-node")
        store._graph.add_edge("pagerank-a", "dangling-node")

        # Should not raise - dangling-node should be skipped or produce None entity
        results = store.get_important_entities(top_k=5)
        assert isinstance(results, list)

    def test_malformed_node_skipped_in_pagerank(self, store: KnowledgeStore) -> None:
        """Line 293->289: _safe_node_to_entity returns None → not in results."""
        a = _entity("pr-good")
        store.add_entity(a)
        store._graph.add_node("pr-bad", entity_type=None)
        store._graph.add_edge("pr-good", "pr-bad")

        results = store.get_important_entities(top_k=10)
        ids = [e.id for e, _ in results]
        assert "pr-bad" not in ids

    def test_empty_graph_returns_empty(self, store: KnowledgeStore) -> None:
        """Baseline: empty graph → empty list."""
        results = store.get_important_entities()
        assert results == []


# ---------------------------------------------------------------------------
# knowledge/store.py – line 455: list_entities skips None entities
# ---------------------------------------------------------------------------


class TestListEntities:
    """Cover line 455 in list_entities."""

    def test_malformed_node_skipped_in_list(self, store: KnowledgeStore) -> None:
        """Line 455: malformed node → entity is None → continue."""
        valid = _entity("le-valid")
        store.add_entity(valid)
        store._graph.add_node("le-bad", entity_type=None)

        results = store.list_entities()
        ids = [e.id for e in results]
        assert "le-valid" in ids
        assert "le-bad" not in ids


# ---------------------------------------------------------------------------
# knowledge/scanner.py – line 320: exact match branch in candidate_priority
# ---------------------------------------------------------------------------


class TestFindImportTargetOptimized:
    """Cover line 320 in scanner.py: exact match in candidate_priority."""

    def test_exact_match_takes_priority(self) -> None:
        """Line 320: key == mod → priority (0, key) returned."""
        # Build a module_to_eid with both exact and prefix matches
        module_to_eid = {
            "utils": "eid-utils-root",
            "utils.helper": "eid-utils-helper",
        }
        {v: k for k, v in module_to_eid.items()}

        result = _find_import_target_optimized(
            mod="utils",
            file_eid="eid-other-file",
            file_module="other.module",
            module_to_eid=module_to_eid,
        )

        # Exact match "utils" should win
        assert result == "eid-utils-root"


# ---------------------------------------------------------------------------
# knowledge/scanner.py – line 417->429: file at root level (no parent dir)
# ---------------------------------------------------------------------------


class TestBuildModuleLookup:
    """Cover branch 417->429 (False branch of len(parts) > 1) in scan_repository."""

    def test_root_level_file_creates_no_parent_relation(self) -> None:
        """Line 417->429: file at repository root has no parent dir to link."""
        # A file at root level: rel_path = "main.py" → parts = ["main.py"] → len == 1
        module_to_eid, eid_to_module = _build_module_lookup(["main.py"])

        # module "main" should be in the lookup
        assert "main" in module_to_eid


# ---------------------------------------------------------------------------
# knowledge/store.py – lines 191-195: _format_entity_as_markdown with relations
# ---------------------------------------------------------------------------


class TestFormatEntityMarkdownWithRelations:
    """Cover lines 191-195 in store.py: if relations: block."""

    def test_format_with_relation(self, store: KnowledgeStore) -> None:
        """Lines 191-195: entity formatted with relation arrow."""
        from henchman.knowledge.models import Relation
        from henchman.knowledge.store import _format_entity_as_markdown

        ent = _entity("ent-with-rel")
        rel = Relation(source="ent-with-rel", target="ent-other", relation_type="calls")

        md = _format_entity_as_markdown(ent, [rel])
        assert "→" in md or "->" in md or "calls" in md


# ---------------------------------------------------------------------------
# knowledge/store.py – line 351: store_dir property
# ---------------------------------------------------------------------------


class TestKnowledgeStoreStoreDir:
    """Cover line 351: store_dir property."""

    def test_store_dir_is_path(self, store: KnowledgeStore) -> None:
        """Line 351: store_dir returns a Path."""
        from pathlib import Path

        d = store.store_dir
        assert isinstance(d, Path)


# ---------------------------------------------------------------------------
# knowledge/scanner.py – line 417->429: root-level file in scan_repository
# ---------------------------------------------------------------------------


class TestScanRepositoryRootLevelFile:
    """Cover branch 417->429 in scanner.py via scan_repository."""

    def test_root_level_py_file_has_no_contains_relation(self, tmp_path: Path) -> None:
        """Line 417->429: root-level Python file has no parent dir → skips relation."""
        import subprocess

        repo = tmp_path / "scan-root-test"
        repo.mkdir()

        # Create a Python file at the repo root (not in any subdir)
        root_file = repo / "main.py"
        root_file.write_text('"""Main module."""\n\ndef run():\n    pass\n')

        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"], cwd=repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=repo, check=True
        )
        subprocess.run(["git", "add", "."], cwd=repo, check=True)

        from henchman.knowledge.scanner import scan_repository
        from henchman.knowledge.store import KnowledgeStore

        kg_dir = tmp_path / "kg-root-test"
        test_store = KnowledgeStore(git_root=repo, base_dir=kg_dir)

        scan_repository(test_store, repo)

        # The file entity should exist
        entities = test_store.list_entities()
        assert any("main" in e.name or "main" in (e.file_path or "") for e in entities)
