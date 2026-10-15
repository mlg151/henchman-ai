"""Contract tests for knowledge graph payloads."""

from __future__ import annotations

from henchman.knowledge.models import Entity, Observation, Relation
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def test_knowledge_payloads_match_contracts(contract_suite) -> None:
    """Serialized knowledge payloads should satisfy their contracts."""
    observation = Observation(
        content="This is a test observation",
        source="test-source",
        author="agent"
    )
    relation = Relation(
        source="entity-a",
        target="entity-b",
        relation_type="depends_on",
        description="A depends on B"
    )
    entity = Entity(
        id="test-entity",
        entity_type="file",
        name="Test Entity",
        description="A test entity",
        file_path="src/test.py",
        tags=["test"],
        observations=[observation]
    )

    assert_contract_matches(
        payload=serialize_contract_value(observation),
        schema_name="knowledge/observation",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(relation),
        schema_name="knowledge/relation",
        contract_suite=contract_suite,
    )
    assert_contract_matches(
        payload=serialize_contract_value(entity),
        schema_name="knowledge/entity",
        contract_suite=contract_suite,
    )
