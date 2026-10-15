"""Contract tests for metrics payloads.

Covers both the event-based metrics (henchman.metrics.models) and the
agent-runtime metrics (henchman.agents.metrics).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from henchman.agents.metrics import (
    OrchestratorMetrics,
    PerformanceMetrics,
    QualityMetrics,
    ToolMetrics,
)
from henchman.metrics.models import TokenMetric, ToolMetric
from tests.contracts.helpers import assert_contract_matches, serialize_contract_value

# ===========================================================================
# Event-based metrics (henchman.metrics.models)
# ===========================================================================


def test_token_metric_matches_contract(contract_suite) -> None:
    """Serialized TokenMetric should satisfy the token_metric contract."""
    token_metric = TokenMetric(
        model="gpt-4o",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )
    assert_contract_matches(
        contract_suite=contract_suite,
        payload=serialize_contract_value(token_metric),
        schema_name="metrics/token_metric",
    )


def test_tool_performance_metric_matches_contract(contract_suite) -> None:
    """Serialized ToolMetric should satisfy the performance_metric contract."""
    perf_metric = ToolMetric(
        tool_name="read_file",
        execution_time_ms=123.45,
        success=True,
    )
    assert_contract_matches(
        contract_suite=contract_suite,
        payload=serialize_contract_value(perf_metric),
        schema_name="metrics/performance_metric",
    )


# ===========================================================================
# Agent-runtime metrics (henchman.agents.metrics)
# ===========================================================================


# -- Serialization helpers ---------------------------------------------------
# The agent metrics classes do not all have a .to_dict() method. We provide
# explicit serializers here so that the contract tests work from the public
# attribute surface without modifying production code.


def _performance_metrics_to_dict(pm: PerformanceMetrics) -> dict[str, Any]:
    """Serialize PerformanceMetrics to a plain dict.

    Filters out ALL-CAPS constants (DELEGATION_RATE_TARGET, etc.) that are
    ``init=False`` dataclass fields leaked by ``asdict()``. Those are class-level
    implementation targets, not instance metrics data, and are not part of the
    serialization contract.
    """
    return {k: v for k, v in asdict(pm).items() if not k.isupper()}


def _tool_metrics_to_dict(tm: ToolMetrics) -> dict[str, int]:
    """Serialize a ToolMetrics instance to a plain dict matching the contract schema."""
    return {
        "total_tool_calls": tm.total_tool_calls,
        "successful_tool_calls": tm.successful_tool_calls,
        "failed_tool_calls": tm.failed_tool_calls,
        "read_file_calls": tm.read_file_calls,
        "write_file_calls": tm.write_file_calls,
        "edit_file_calls": tm.edit_file_calls,
        "shell_calls": tm.shell_calls,
        "git_ops_calls": tm.git_ops_calls,
        "other_tool_calls": tm.other_tool_calls,
    }


def _orchestrator_metrics_to_dict(om: OrchestratorMetrics) -> dict[str, Any]:
    """Serialize an OrchestratorMetrics instance to a plain dict matching the contract schema."""
    return {
        "thinking_pattern_usage": om.thinking_pattern_usage,
        "delegation_count": om.delegation_count,
        "delegation_by_type": dict(om.delegation_by_type),
        "thinking_quality_score": om.thinking_quality_score,
        "performance": _performance_metrics_to_dict(om.performance),
        "quality": asdict(om.quality),
        "tools": _tool_metrics_to_dict(om.tools),
    }


# -- PerformanceMetrics ------------------------------------------------------


class TestPerformanceMetricsContract:
    """Serialized PerformanceMetrics must satisfy the performance_metrics schema."""

    def test_default_metrics_match_contract(self, contract_suite) -> None:
        """A default-constructed PerformanceMetrics should validate."""
        metrics = PerformanceMetrics()
        payload = _performance_metrics_to_dict(metrics)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/performance_metrics",
        )

    def test_metrics_with_data_match_contract(self, contract_suite) -> None:
        """A populated PerformanceMetrics should validate."""
        metrics = PerformanceMetrics()
        metrics.task_start_time = 1000.0
        metrics.task_end_time = 2000.0
        metrics.task_duration_minutes = 16.67
        metrics.track_file_access("/src/main.py")
        metrics.track_file_access("/src/main.py")
        metrics.track_file_access("/src/utils.py")
        metrics.track_tool_usage("read_file")
        metrics.track_tool_usage("write_file")
        metrics.track_tool_usage("shell")
        metrics.delegation_rate = 25.0
        metrics.calculate_file_re_reads()
        metrics.error_rate = 5.0
        metrics.context_window_usage = 60.0

        payload = _performance_metrics_to_dict(metrics)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/performance_metrics",
        )

    def test_reset_metrics_match_contract(self, contract_suite) -> None:
        """After reset, PerformanceMetrics should return to valid default state."""
        metrics = PerformanceMetrics()
        metrics.track_file_access("/tmp/test.py")
        metrics.track_tool_usage("shell")
        metrics.reset()
        payload = _performance_metrics_to_dict(metrics)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/performance_metrics",
        )


# -- QualityMetrics ----------------------------------------------------------


class TestQualityMetricsContract:
    """Serialized QualityMetrics must satisfy the quality_metrics schema."""

    def test_default_metrics_match_contract(self, contract_suite) -> None:
        """A default-constructed QualityMetrics should validate."""
        metrics = QualityMetrics()
        payload = asdict(metrics)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/quality_metrics",
        )

    def test_metrics_with_data_match_contract(self, contract_suite) -> None:
        """A populated QualityMetrics should validate."""
        metrics = QualityMetrics()
        metrics.test_results["passing"] = 45
        metrics.test_results["total"] = 50
        metrics.calculate_test_percentage()
        metrics.code_coverage = 85.5
        metrics.linting_status["errors"] = 2
        metrics.linting_status["warnings"] = 5
        metrics.documentation_coverage = 72.3

        payload = asdict(metrics)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/quality_metrics",
        )

    def test_reset_metrics_match_contract(self, contract_suite) -> None:
        """After reset, QualityMetrics should return to valid default state."""
        metrics = QualityMetrics()
        metrics.test_results["passing"] = 10
        metrics.test_results["total"] = 10
        metrics.calculate_test_percentage()
        metrics.code_coverage = 95.0
        metrics.reset()
        payload = asdict(metrics)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/quality_metrics",
        )


# -- ToolMetrics -------------------------------------------------------------


class TestToolMetricsContract:
    """Serialized ToolMetrics must satisfy the tool_metrics schema."""

    def test_default_metrics_match_contract(self, contract_suite) -> None:
        """A default-constructed ToolMetrics should validate."""
        tm = ToolMetrics()
        payload = _tool_metrics_to_dict(tm)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/tool_metrics",
        )

    def test_metrics_with_calls_match_contract(self, contract_suite) -> None:
        """A ToolMetrics with tracked calls should validate."""
        tm = ToolMetrics()
        tm.track_tool_call("read_file", success=True)
        tm.track_tool_call("write_file", success=True)
        tm.track_tool_call("shell", success=False)
        tm.track_tool_call("edit_file", success=True)
        tm.track_tool_call("git_ops", success=True)
        tm.track_tool_call("unknown_tool", success=False)

        payload = _tool_metrics_to_dict(tm)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/tool_metrics",
        )

    def test_reset_metrics_match_contract(self, contract_suite) -> None:
        """After reset, ToolMetrics should return to valid default state."""
        tm = ToolMetrics()
        tm.track_tool_call("shell", success=False)
        tm.reset()
        payload = _tool_metrics_to_dict(tm)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/tool_metrics",
        )

    def test_error_rate_calculation_preserves_shape(self, contract_suite) -> None:
        """calculate_error_rate should not change the serialized shape."""
        tm = ToolMetrics()
        tm.track_tool_call("read_file", success=True)
        tm.track_tool_call("shell", success=False)
        _ = tm.calculate_error_rate()
        payload = _tool_metrics_to_dict(tm)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/tool_metrics",
        )


# -- OrchestratorMetrics -----------------------------------------------------


class TestOrchestratorMetricsContract:
    """Serialized OrchestratorMetrics must satisfy the orchestrator_metrics schema.

    This is the most critical cross-subsystem contract — it flows from
    agents/metrics.py -> agents/metrics_reporter.py -> cli/output_handler.py.
    """

    def test_default_metrics_match_contract(self, contract_suite) -> None:
        """A default-constructed OrchestratorMetrics should validate."""
        om = OrchestratorMetrics()
        payload = _orchestrator_metrics_to_dict(om)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/orchestrator_metrics",
        )

    def test_metrics_with_data_match_contract(self, contract_suite) -> None:
        """A populated OrchestratorMetrics should validate."""
        om = OrchestratorMetrics()

        # Populate top-level fields
        om.thinking_pattern_usage = 3
        om.delegation_count = 2
        om.delegation_by_type["planner"] = 1
        om.delegation_by_type["engineer"] = 1
        om.thinking_quality_score = 85

        # Populate performance
        om.performance.task_start_time = 1000.0
        om.performance.task_end_time = 3000.0
        om.performance.track_file_access("/src/main.py")
        om.performance.track_tool_usage("read_file")
        om.performance.track_tool_usage("write_file")

        # Populate quality
        om.quality.test_results["passing"] = 45
        om.quality.test_results["total"] = 50
        om.quality.calculate_test_percentage()
        om.quality.code_coverage = 92.0

        # Populate tools
        om.tools.track_tool_call("read_file", success=True)
        om.tools.track_tool_call("write_file", success=True)
        om.tools.track_tool_call("shell", success=False)

        # Calculate derived metrics
        om.calculate_final_metrics()

        payload = _orchestrator_metrics_to_dict(om)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/orchestrator_metrics",
        )

    def test_reset_for_run_preserves_contract(self, contract_suite) -> None:
        """After reset_for_run, OrchestratorMetrics should return to valid state."""
        om = OrchestratorMetrics()
        om.thinking_pattern_usage = 5
        om.delegation_count = 3
        om.tools.track_tool_call("shell", success=True)
        om.performance.track_file_access("/tmp/x.py")
        om.reset_for_run()
        payload = _orchestrator_metrics_to_dict(om)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/orchestrator_metrics",
        )

    def test_round_trip_via_dict_access_preserves_shape(self, contract_suite) -> None:
        """Using OrchestratorMetrics dict-like access should preserve the contract shape."""
        om = OrchestratorMetrics()

        # Set values via __setitem__
        om["thinking_pattern_usage"] = 2
        om["delegation_count"] = 1
        om["total_tool_calls"] = 5
        om["successful_tool_calls"] = 4
        om["failed_tool_calls"] = 1

        # Verify via __getitem__
        assert om["thinking_pattern_usage"] == 2
        assert om["delegation_count"] == 1
        assert om["total_tool_calls"] == 5

        payload = _orchestrator_metrics_to_dict(om)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/orchestrator_metrics",
        )

    def test_get_method_returns_default_for_unknown_key(self, contract_suite) -> None:
        """OrchestratorMetrics.get() should not crash and shape should remain valid."""
        om = OrchestratorMetrics()
        result = om.get("nonexistent_key", "fallback")
        assert result == "fallback"
        payload = _orchestrator_metrics_to_dict(om)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/orchestrator_metrics",
        )

    def test_update_tool_metrics_preserves_shape(self, contract_suite) -> None:
        """update_tool_metrics should produce a valid contract shape."""
        om = OrchestratorMetrics()
        om.update_tool_metrics("read_file", {"path": "/src/main.py"}, success=True)
        om.update_tool_metrics("write_file", {}, success=True)
        om.update_tool_metrics("shell", {}, success=False)
        om.calculate_final_metrics()

        payload = _orchestrator_metrics_to_dict(om)
        assert_contract_matches(
            contract_suite=contract_suite,
            payload=payload,
            schema_name="metrics/orchestrator_metrics",
        )
