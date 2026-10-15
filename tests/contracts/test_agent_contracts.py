"""Contract tests for agent definition, search, and marketplace models.

These tests validate that serialised AgentDefinition, AgentSearchResult,
AgentInstallation, AgentUpdateInfo, and AgentPublication payloads conform
to their published JSON Schema contracts.

Consumers include the agent catalog, registry marketplace queries, and
the installation/persistence layer.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from henchman.agents.models import (
    AgentDefinition,
    AgentInstallation,
    AgentPublication,
    AgentSearchParams,
    AgentSearchResult,
    AgentUpdateInfo,
    installation_to_payload,
)
from henchman.config.schema import AgentConfig
from tests.contracts.helpers import assert_contract_matches

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_agent_config() -> AgentConfig:
    """A representative AgentConfig for use in definition fixtures."""
    return AgentConfig(
        name="Coder",
        role="coder",
        description="Writes production code",
        system_prompt="You are a senior engineer.",
        tools=["read", "write", "shell"],
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        auto_approve=["read"],
        can_delegate_to=["reviewer"],
        enabled=True,
    )


@pytest.fixture
def sample_definition(sample_agent_config: AgentConfig) -> AgentDefinition:
    """A fully-populated AgentDefinition with source metadata."""
    return AgentDefinition(
        config=sample_agent_config,
        version="1.2.0",
        source_path=Path("/home/user/.henchman/agents/coder.yaml"),
        source_kind="local",
        author="dev-team",
        tags=["code", "python"],
    )


@pytest.fixture
def minimal_definition() -> AgentDefinition:
    """An AgentDefinition with only required fields."""
    return AgentDefinition(
        config=AgentConfig(
            name="Reviewer",
            role="reviewer",
            description="Reviews pull requests",
            tools=["read"],
        ),
        version="1.0.0",
        source_path=Path("<memory>"),
        source_kind="unknown",
    )


# ---------------------------------------------------------------------------
# AgentDefinition contracts
# ---------------------------------------------------------------------------


class TestAgentDefinitionContract:
    """AgentDefinition.to_payload() must satisfy the definition contract."""

    def test_full_payload_matches_contract(
        self, contract_suite: object, sample_definition: AgentDefinition
    ) -> None:
        payload = sample_definition.to_payload(include_source=True)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="agents/agent_definition",
        )

    def test_payload_without_source_matches_contract(
        self, contract_suite: object, sample_definition: AgentDefinition
    ) -> None:
        payload = sample_definition.to_payload()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="agents/agent_definition",
        )

    def test_minimal_payload_matches_contract(
        self, contract_suite: object, minimal_definition: AgentDefinition
    ) -> None:
        payload = minimal_definition.to_payload()
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="agents/agent_definition",
        )

    def test_payload_yaml_roundtrip_preserves_contract(
        self, contract_suite: object, sample_definition: AgentDefinition, tmp_path: Path
    ) -> None:
        payload = sample_definition.to_payload(include_source=True)
        yaml_path = tmp_path / "agent.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(payload, f, default_flow_style=False)
        with open(yaml_path) as f:
            reloaded = yaml.safe_load(f)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=reloaded,
            schema_name="agents/agent_definition",
        )


# ---------------------------------------------------------------------------
# AgentSearchParams & AgentSearchResult contracts
# ---------------------------------------------------------------------------


class TestAgentSearchParamsContract:
    """AgentSearchParams must satisfy its contract."""

    def test_search_params_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = AgentSearchParams(query="code review", page=1, page_size=20)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/agent_search_params",
        )

    def test_search_params_defaults_match_contract(
        self, contract_suite: object
    ) -> None:
        payload = AgentSearchParams(query=None)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/agent_search_params",
        )


class TestAgentSearchResultContract:
    """AgentSearchResult must satisfy its contract."""

    def test_search_result_matches_contract(
        self, contract_suite: object, sample_definition: AgentDefinition
    ) -> None:
        result = AgentSearchResult(
            agents=[sample_definition],
            total=1,
            page=1,
            page_size=20,
            query="code review",
        )
        payload = asdict(result)
        payload["agents"] = [a.to_payload(include_source=True) for a in result.agents]
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="agents/agent_search_result",
        )

    def test_search_result_empty_matches_contract(
        self, contract_suite: object
    ) -> None:
        result = AgentSearchResult(agents=[], total=0, page=1, page_size=20)
        payload = asdict(result)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="agents/agent_search_result",
        )


# ---------------------------------------------------------------------------
# AgentInstallation contract
# ---------------------------------------------------------------------------


class TestAgentInstallationContract:
    """AgentInstallation (via installation_to_payload) must satisfy its contract."""

    def test_installation_matches_contract(
        self, contract_suite: object, sample_definition: AgentDefinition
    ) -> None:
        installation = AgentInstallation(
            definition=sample_definition,
            installed_version="1.2.0",
            installation_path="/home/user/.henchman/installed/coder",
            enabled=True,
        )
        payload = installation_to_payload(installation)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="agents/agent_installation",
        )

    def test_installation_disabled_matches_contract(
        self, contract_suite: object, sample_definition: AgentDefinition
    ) -> None:
        installation = AgentInstallation(
            definition=sample_definition,
            installed_version="1.0.0",
            installation_path="/tmp/test/install",
            enabled=False,
        )
        payload = installation_to_payload(installation)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="agents/agent_installation",
        )


# ---------------------------------------------------------------------------
# AgentUpdateInfo contract
# ---------------------------------------------------------------------------


class TestAgentUpdateInfoContract:
    """AgentUpdateInfo must satisfy its contract."""

    def test_update_info_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = AgentUpdateInfo(
            role="coder",
            current_version="1.2.0",
            latest_version="1.3.0",
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/agent_update_info",
        )

    def test_update_info_no_update_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = AgentUpdateInfo(
            role="reviewer",
            current_version="1.0.0",
            latest_version="1.0.0",
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/agent_update_info",
        )


# ---------------------------------------------------------------------------
# AgentPublication contract
# ---------------------------------------------------------------------------


class TestAgentPublicationContract:
    """AgentPublication must satisfy its contract."""

    def test_publication_matches_contract(
        self, contract_suite: object, sample_definition: AgentDefinition
    ) -> None:
        pub = AgentPublication(
            definition=sample_definition,
            version="1.2.0",
            publication_path="/tmp/publish/coder-v1.2.0",
        )
        payload = asdict(pub)
        payload["definition"] = pub.definition.to_payload(include_source=True)
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=payload,
            schema_name="agents/agent_publication",
        )
