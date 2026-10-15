"""Contract tests for delegation parameter types.

These tests validate that the serialised shapes of DelegationParams,
AgentLoopParams, DelegationExecutionParams, and CompletionStatus conform
to their published JSON Schema contracts.
"""

from __future__ import annotations

from dataclasses import asdict

from henchman.agents.orchestrator_types import (
    AgentLoopParams,
    CompletionStatus,
    DelegationExecutionParams,
    DelegationParams,
)
from tests.contracts.helpers import assert_contract_matches

# ---------------------------------------------------------------------------
# DelegationParams contracts
# ---------------------------------------------------------------------------


class TestDelegationParamsContract:
    """DelegationParams must satisfy its contract."""

    def test_full_params_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = DelegationParams(
            target_role="coder",
            task="Write a CSV parser module",
            brief={"files": ["/src/parser.py"], "context": "Uses pandas"},
            depth=1,
            target_agent="agent_ref_123",
            full_task="Full: Write a CSV parser module with tests",
            msg_start=5,
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/delegation_params",
        )

    def test_minimal_params_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = DelegationParams(
            target_role="reviewer",
            task="Review PR #42",
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/delegation_params",
        )

    def test_params_without_brief_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = DelegationParams(
            target_role="tech_lead",
            task="Architect the solution",
            depth=2,
            full_task="Architect the solution for feature X",
            msg_start=10,
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/delegation_params",
        )


# ---------------------------------------------------------------------------
# AgentLoopParams contracts
# ---------------------------------------------------------------------------


class TestAgentLoopParamsContract:
    """AgentLoopParams must satisfy its contract."""

    def test_full_loop_params_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = AgentLoopParams(
            agent="agent_instance",
            target_role="coder",
            input_text="Write a parser for CSV files",
            depth=1,
            max_turns=50,
            prior_tool_rounds=2,
            prior_tool_calls=7,
            msg_start_index=0,
            brief={"task": "Write parser", "files": ["/src/parser.py"]},
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/agent_loop_params",
        )

    def test_minimal_loop_params_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = AgentLoopParams(
            input_text="Hello",
            depth=0,
            max_turns=150,
            msg_start_index=0,
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/agent_loop_params",
        )


# ---------------------------------------------------------------------------
# DelegationExecutionParams contracts
# ---------------------------------------------------------------------------


class TestDelegationExecutionParamsContract:
    """DelegationExecutionParams must satisfy its contract."""

    def test_execution_params_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = DelegationExecutionParams(
            target="coder",
            task="Write tests for parser",
            depth=2,
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/delegation_execution_params",
        )

    def test_execution_params_with_optionals_matches_contract(
        self, contract_suite: object
    ) -> None:
        payload = DelegationExecutionParams(
            target="reviewer",
            task="Review code changes",
            depth=3,
            tool_call="tool_call_ref",
            agent="agent_ref",
            ledger_record="ledger_ref",
        )
        assert_contract_matches(
            contract_suite=contract_suite,  # type: ignore[arg-type]
            payload=asdict(payload),
            schema_name="agents/delegation_execution_params",
        )


# ---------------------------------------------------------------------------
# CompletionStatus enum contract
# ---------------------------------------------------------------------------


class TestCompletionStatusContract:
    """CompletionStatus values must match the published enum contract."""

    def test_all_completion_status_values_match_contract(
        self, contract_suite: object
    ) -> None:
        for status in CompletionStatus:
            assert_contract_matches(
                contract_suite=contract_suite,  # type: ignore[arg-type]
                payload=status.value,
                schema_name="agents/completion_status",
            )
