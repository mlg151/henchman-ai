"""Contract tests for the Agent Catalog and Platform Manager.

These tests validate that agent definitions loaded from files satisfy
the agent definition schema contract, and that the platform manager's
installation lifecycle is contract-compliant.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from henchman.agents.catalog import AgentCatalog, load_agent_definition_file
from henchman.agents.models import AgentDefinition
from henchman.agents.platform_manager import AgentPlatformManager
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value


class TestAgentCatalogContract:
    """AgentCatalog must produce contract-compliant definitions from files."""

    def test_catalog_yaml_file_matches_definition_contract(
        self, contract_suite: object, tmp_path: Path
    ) -> None:
        """Agent definitions loaded from YAML must satisfy the definition schema."""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        (agent_dir / "coder.yaml").write_text(yaml.safe_dump({
            "name": "Coder",
            "role": "coder",
            "description": "Writes production code",
            "version": "1.0.0",
            "system_prompt": "You are a senior software engineer.",
        }))

        catalog = AgentCatalog(project_root=tmp_path)
        definitions = catalog.list_agents()
        assert len(definitions) >= 1

        for defn in definitions:
            payload = serialize_contract_value(defn.to_payload())
            assert_contract_matches(
                contract_suite=contract_suite,
                payload=payload,
                schema_name="agents/agent_definition",
            )

    def test_catalog_json_file_matches_definition_contract(
        self, contract_suite: object, tmp_path: Path
    ) -> None:
        """Agent definitions loaded from JSON must satisfy the definition schema."""
        import json

        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()
        (agent_dir / "tester.json").write_text(json.dumps({
            "name": "Tester",
            "role": "tester",
            "description": "Writes and runs tests",
            "version": "1.0.0",
            "system_prompt": "You are a QA engineer.",
            "tools": ["pytest", "read", "write"],
        }))

        catalog = AgentCatalog(project_root=tmp_path)
        definitions = catalog.list_agents()
        assert len(definitions) >= 1

        for defn in definitions:
            payload = serialize_contract_value(defn.to_payload())
            assert_contract_matches(
                contract_suite=contract_suite,
                payload=payload,
                schema_name="agents/agent_definition",
            )

    def test_catalog_multiple_agents_all_match_contract(
        self, contract_suite: object, tmp_path: Path
    ) -> None:
        """Multiple agent definitions should all satisfy the contract."""
        agent_dir = tmp_path / "agents"
        agent_dir.mkdir()

        (agent_dir / "architect.yaml").write_text(yaml.safe_dump({
            "name": "Architect",
            "role": "architect",
            "description": "Designs system architecture",
            "version": "1.0.0",
        }))
        (agent_dir / "reviewer.yaml").write_text(yaml.safe_dump({
            "name": "Reviewer",
            "role": "reviewer",
            "description": "Reviews code changes",
            "version": "1.0.0",
            "tools": ["read", "diff"],
        }))

        catalog = AgentCatalog(project_root=tmp_path)
        definitions = catalog.list_agents()
        assert len(definitions) >= 2

        for defn in definitions:
            payload = serialize_contract_value(defn.to_payload())
            assert_contract_matches(
                contract_suite=contract_suite,
                payload=payload,
                schema_name="agents/agent_definition",
            )

    def test_load_agent_definition_file_matches_contract(
        self, contract_suite: object, tmp_path: Path
    ) -> None:
        """load_agent_definition_file() must produce contract-compliant payloads."""
        agent_file = tmp_path / "custom_agent.yaml"
        agent_file.write_text(yaml.safe_dump({
            "name": "Custom Agent",
            "role": "custom",
            "description": "A custom agent definition",
            "version": "2.0.0",
            "system_prompt": "You are a custom agent with special capabilities.",
            "tools": ["search", "read", "write"],
        }))

        definition = load_agent_definition_file(agent_file, source_kind="local")
        payload = serialize_contract_value(definition.to_payload())
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="agents/agent_definition",
        )


class TestAgentPlatformManagerContract:
    """AgentPlatformManager must satisfy installation lifecycle contracts."""

    @pytest.mark.anyio
    async def test_platform_manager_initialization_contract(
        self, tmp_path: Path
    ) -> None:
        """Platform manager initialization should create persistent state."""
        manager = AgentPlatformManager(
            data_dir=tmp_path / "platform_data",
            registry_url="https://test-registry.local",
        )
        assert manager._initialized is False

        await manager.initialize()
        assert manager._initialized is True
        assert manager.data_dir.exists()

        await manager.close()
        assert manager._initialized is False

    @pytest.mark.anyio
    async def test_platform_manager_initialized_check(self, tmp_path: Path) -> None:
        """Operations before initialization should raise RuntimeError."""
        manager = AgentPlatformManager(
            data_dir=tmp_path / "platform_data",
        )
        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.search_agents(query="test")

        with pytest.raises(RuntimeError, match="not initialized"):
            await manager.get_agent_info("coder")

    @pytest.mark.anyio
    async def test_platform_manager_double_init_is_safe(
        self, tmp_path: Path
    ) -> None:
        """Calling initialize() twice should be safe."""
        manager = AgentPlatformManager(data_dir=tmp_path / "data")
        await manager.initialize()
        await manager.initialize()  # Should not raise
        assert manager._initialized is True
        await manager.close()

    def test_load_agent_definition_yaml_matches_contract(
        self, contract_suite: object, tmp_path: Path
    ) -> None:
        """Agent definition file loaded with source_kind matches schema."""
        agent_file = tmp_path / "engineer.yaml"
        agent_file.write_text(yaml.safe_dump({
            "name": "Engineer",
            "role": "engineer",
            "description": "Implements features",
            "version": "1.5.0",
            "tools": ["read", "write", "edit", "shell", "git"],
        }))

        definition = load_agent_definition_file(agent_file, source_kind="henchman-user")
        payload = serialize_contract_value(definition.to_payload())
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="agents/agent_definition",
        )
        assert isinstance(definition, AgentDefinition)
