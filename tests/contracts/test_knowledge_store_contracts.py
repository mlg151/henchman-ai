"""Contract tests for knowledge-store ranking results."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.knowledge.models import Entity, Relation
from henchman.knowledge.store import KnowledgeStore
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def _make_entity(eid: str) -> Entity:
    """Create a simple entity for ranking tests."""
    return Entity(
        id=eid,
        entity_type="file",
        name=eid.upper(),
        description=f"Description for {eid}",
        file_path=f"src/{eid}.py",
        tags=["contract"],
    )


@pytest.fixture
def contract_store(tmp_path: Path) -> KnowledgeStore:
    """Create an isolated KnowledgeStore for contract checks."""
    git_root = tmp_path / "repo"
    git_root.mkdir()
    (git_root / ".git").mkdir()
    return KnowledgeStore(git_root=git_root, base_dir=tmp_path / "kg")


def test_important_entity_ranks_match_contract(
    contract_suite: object,
    contract_store: KnowledgeStore,
) -> None:
    """get_important_entities should emit contract-compliant rank entries."""
    for entity_id in ("a", "b", "c"):
        contract_store.add_entity(_make_entity(entity_id))
    contract_store.add_relation(Relation(source="b", target="a", relation_type="imports"))
    contract_store.add_relation(Relation(source="c", target="a", relation_type="imports"))

    ranked = contract_store.get_important_entities(top_k=2)

    for entity, score in ranked:
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload={"entity": serialize_contract_value(entity), "score": score},
            schema_name="knowledge/important_entity_rank",
        )
