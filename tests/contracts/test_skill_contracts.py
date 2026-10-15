"""Contract tests for skill-related payloads."""

from __future__ import annotations

from pathlib import Path

import yaml

from henchman.skills.catalog import SkillDefinition
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


def test_skill_definition_matches_contract(contract_suite) -> None:
    """Serialized SkillDefinition should satisfy its contract."""
    definition = SkillDefinition(
        name="test-skill",
        description="A test skill",
        instructions="Do something",
        source_path=Path("/tmp/test.yml"),
        source_kind="henchman"
    )

    assert_contract_matches(
        payload=serialize_contract_value(definition),
        schema_name="skills/skill_definition",
        contract_suite=contract_suite,
    )


def test_native_skill_yaml_matches_contract(contract_suite) -> None:
    """Native Henchman skill YAML files should satisfy the contract."""
    yaml_content = """
name: test-skill
description: A native test skill
steps:
  - do this
  - do that
parameters:
  - arg1
  - arg2: "with description"
"""
    payload = yaml.safe_load(yaml_content)
    assert_contract_matches(
        payload=payload,
        schema_name="skills/native_yaml",
        contract_suite=contract_suite,
    )
