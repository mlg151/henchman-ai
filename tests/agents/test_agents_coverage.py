"""Tests for agents modules: anchoring, metrics_ctrl, delegation, metrics, loop."""

from __future__ import annotations

import warnings
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.agents.metrics import (
    OrchestratorMetrics,
    PerformanceMetrics,
    QualityMetrics,
    ToolCategory,
    ToolMetrics,
    _categorize_tool,
    _increment_counter,
)
from henchman.agents.orchestrator_anchoring import (
    _is_truthy_failure,
    assess_agent_completion,
    inject_role_anchor,
)
from henchman.agents.orchestrator_loop import (
    check_colon_stall,
    check_turn_limits,
    collect_events,
    finalize_loop,
    last_assistant_content,
    run_tools_and_collect,
)
from henchman.agents.orchestrator_types import (
    AgentLoopParams,
    CompletionStatus,
    LoopState,
)
from henchman.core.events import AgentEvent, EventType
from henchman.providers.base import Message

# ---------------------------------------------------------------------------
# orchestrator_anchoring tests
# ---------------------------------------------------------------------------


class TestInjectRoleAnchor:
    """Tests for inject_role_anchor function."""

    def test_no_inject_at_zero_tool_calls(self) -> None:
        """inject_role_anchor does nothing when tool_call_count is 0."""
        orchestrator = MagicMock()
        agent = MagicMock()
        agent.messages = []

        inject_role_anchor(orchestrator, agent, tool_call_count=0)
        assert agent.messages == []

    def test_no_inject_when_not_at_interval(self) -> None:
        """inject_role_anchor does nothing when not at ROLE_ANCHOR_INTERVAL."""
        orchestrator = MagicMock()
        agent = MagicMock()
        agent.messages = []

        inject_role_anchor(orchestrator, agent, tool_call_count=3)
        assert agent.messages == []

    def test_inject_at_interval_no_identity(self) -> None:
        """inject_role_anchor does nothing when agent has no identity."""
        from henchman.agents.orchestrator_types import ROLE_ANCHOR_INTERVAL

        orchestrator = MagicMock()
        agent = MagicMock()
        agent.messages = []
        agent.identity = None

        inject_role_anchor(orchestrator, agent, tool_call_count=ROLE_ANCHOR_INTERVAL)
        # messages unchanged even though at interval
        assert len(agent.messages) == 0

    def test_inject_at_interval_with_identity(self) -> None:
        """inject_role_anchor injects message at ROLE_ANCHOR_INTERVAL."""
        from henchman.agents.orchestrator_types import ROLE_ANCHOR_INTERVAL

        orchestrator = MagicMock()
        orchestrator.ledger = None
        agent = MagicMock()
        agent.messages = []
        agent.identity = MagicMock()
        agent.identity.role = "engineer"
        agent.identity.id = "eng-1"

        inject_role_anchor(orchestrator, agent, tool_call_count=ROLE_ANCHOR_INTERVAL)
        assert len(agent.messages) == 1
        assert "ENGINEER" in agent.messages[0].content

    def test_inject_with_ledger_mission(self) -> None:
        """inject_role_anchor includes mission note when ledger has recap."""
        from henchman.agents.orchestrator_types import ROLE_ANCHOR_INTERVAL

        orchestrator = MagicMock()
        orchestrator.ledger = MagicMock()
        orchestrator.ledger.mission_recap.return_value = "Build the app"
        agent = MagicMock()
        agent.messages = []
        agent.identity = MagicMock()
        agent.identity.role = "planner"
        agent.identity.id = "p1"

        inject_role_anchor(orchestrator, agent, tool_call_count=ROLE_ANCHOR_INTERVAL)
        assert "Mission: Build the app" in agent.messages[0].content

    def test_inject_with_ledger_no_recap(self) -> None:
        """inject_role_anchor works when ledger returns empty recap."""
        from henchman.agents.orchestrator_types import ROLE_ANCHOR_INTERVAL

        orchestrator = MagicMock()
        orchestrator.ledger = MagicMock()
        orchestrator.ledger.mission_recap.return_value = ""
        agent = MagicMock()
        agent.messages = []
        agent.identity = MagicMock()
        agent.identity.role = "explorer"
        agent.identity.id = "ex1"

        inject_role_anchor(orchestrator, agent, tool_call_count=ROLE_ANCHOR_INTERVAL)
        assert len(agent.messages) == 1
        # No mission note
        assert "Mission:" not in agent.messages[0].content

    def test_inject_uses_identity_id_when_no_role(self) -> None:
        """inject_role_anchor uses identity.id when role is None."""
        from henchman.agents.orchestrator_types import ROLE_ANCHOR_INTERVAL

        orchestrator = MagicMock()
        orchestrator.ledger = None
        agent = MagicMock()
        agent.messages = []
        agent.identity = MagicMock()
        agent.identity.role = None
        agent.identity.id = "custom-agent-42"

        inject_role_anchor(orchestrator, agent, tool_call_count=ROLE_ANCHOR_INTERVAL)
        assert "CUSTOM-AGENT-42" in agent.messages[0].content


class TestAssessAgentCompletion:
    """Tests for assess_agent_completion function."""

    def test_completed_status_with_tool_calls(self) -> None:
        """assess_agent_completion returns COMPLETED when tool calls were made."""
        from henchman.core.agent_stall import StallDetector  # noqa: PLC0415

        orchestrator = MagicMock()
        orchestrator._last_loop_tool_call_count = 5
        agent = MagicMock(spec=["_stall"])
        agent._stall = StallDetector()  # failure=False by default

        result = assess_agent_completion(orchestrator, agent)
        assert result == CompletionStatus.COMPLETED

    def test_no_work_done_status(self) -> None:
        """assess_agent_completion returns NO_WORK_DONE when no tool calls."""
        orchestrator = MagicMock()
        orchestrator._last_loop_tool_call_count = 0
        agent = MagicMock(spec=[])  # No _stall attribute

        result = assess_agent_completion(orchestrator, agent)
        assert result == CompletionStatus.NO_WORK_DONE

    def test_stalled_via_stall_detector(self) -> None:
        """assess_agent_completion returns STALLED when stall detector indicates failure."""
        from henchman.core.agent_stall import StallDetector  # noqa: PLC0415

        orchestrator = MagicMock()
        orchestrator._last_loop_tool_call_count = 3
        agent = MagicMock(spec=["_stall"])
        stall = StallDetector()
        stall.failure = True
        agent._stall = stall

        result = assess_agent_completion(orchestrator, agent)
        assert result == CompletionStatus.STALLED

    def test_stalled_via_legacy_attribute(self) -> None:
        """assess_agent_completion checks legacy _stall_failure attribute."""
        orchestrator = MagicMock()
        orchestrator._last_loop_tool_call_count = 2
        agent = MagicMock(spec=["_stall_failure"])  # No _stall, has _stall_failure
        agent._stall_failure = True

        result = assess_agent_completion(orchestrator, agent)
        assert result == CompletionStatus.STALLED

    def test_no_tool_call_count_attribute(self) -> None:
        """assess_agent_completion uses 0 when _last_loop_tool_call_count missing."""
        orchestrator = MagicMock(spec=[])  # No _last_loop_tool_call_count
        agent = MagicMock(spec=[])

        result = assess_agent_completion(orchestrator, agent)
        assert result == CompletionStatus.NO_WORK_DONE


class TestIsTruthyFailure:
    """Tests for _is_truthy_failure helper."""

    def test_none_is_false(self) -> None:
        """None value returns False."""
        assert _is_truthy_failure(None) is False

    def test_true_is_true(self) -> None:
        """Boolean True returns True."""
        assert _is_truthy_failure(True) is True

    def test_false_is_false(self) -> None:
        """Boolean False returns False."""
        assert _is_truthy_failure(False) is False

    def test_truthy_int_is_true(self) -> None:
        """Non-zero int returns True."""
        assert _is_truthy_failure(1) is True

    def test_zero_is_false(self) -> None:
        """Zero returns False."""
        assert _is_truthy_failure(0) is False

    def test_truthy_object_is_true(self) -> None:
        """Any truthy object returns True."""
        assert _is_truthy_failure(object()) is True

    def test_list_is_true(self) -> None:
        """Non-empty list returns True."""
        assert _is_truthy_failure([1]) is True

    def test_nonempty_string_is_true(self) -> None:
        """Non-empty string returns True."""
        assert _is_truthy_failure("stall") is True

    def test_empty_string_is_false(self) -> None:
        """Empty string returns False."""
        assert _is_truthy_failure("") is False


# ---------------------------------------------------------------------------
# orchestrator_metrics_ctrl tests
# ---------------------------------------------------------------------------


class TestToolMetricsController:
    """Tests for ToolMetricsController."""

    @pytest.fixture
    def controller(self):
        """Create ToolMetricsController with mock metrics.

        Returns:
            ToolMetricsController instance.
        """
        from henchman.agents.orchestrator_metrics_ctrl import ToolMetricsController

        orchestrator = MagicMock()
        orchestrator.metrics = OrchestratorMetrics()
        ctrl = ToolMetricsController.__new__(ToolMetricsController)
        ctrl.orchestrator = orchestrator
        ctrl.metrics = orchestrator.metrics
        return ctrl

    def test_update_tool_metrics(self, controller) -> None:
        """update_tool_metrics increments correct counter."""
        controller.update_tool_metrics("shell", {"cmd": "ls"}, success=True)
        assert controller.metrics.tools.shell_calls == 1

    def test_track_tool_error_with_content(self, controller) -> None:
        """track_tool_error appends formatted error."""
        errors: list[str] = []
        controller.track_tool_error(errors, "shell", "command failed")
        assert len(errors) == 1
        assert "shell: command failed" in errors[0]

    def test_track_tool_error_none_content(self, controller) -> None:
        """track_tool_error uses 'unknown error' when content is None."""
        errors: list[str] = []
        controller.track_tool_error(errors, "shell", None)
        assert "unknown error" in errors[0]

    def test_update_delegation_metrics_known_target(self, controller) -> None:
        """update_delegation_metrics increments delegation count and type."""
        controller.update_delegation_metrics("engineer")
        assert controller.metrics.delegation_count == 1
        assert controller.metrics.delegation_by_type["engineer"] == 1

    def test_update_delegation_metrics_unknown_target(self, controller) -> None:
        """update_delegation_metrics increments delegation_count for unknown target."""
        controller.update_delegation_metrics("unknown-agent-type")
        assert controller.metrics.delegation_count == 1
        # unknown target not added to delegation_by_type
        assert "unknown-agent-type" not in controller.metrics.delegation_by_type


# ---------------------------------------------------------------------------
# metrics.py tests
# ---------------------------------------------------------------------------


class TestOrchestratorMetrics:
    """Tests for OrchestratorMetrics class."""

    def test_getitem_direct_attr(self) -> None:
        """__getitem__ returns direct attribute."""
        m = OrchestratorMetrics()
        assert m["delegation_count"] == 0

    def test_getitem_component_key(self) -> None:
        """__getitem__ returns component attribute via key map."""
        m = OrchestratorMetrics()
        assert m["total_tool_calls"] == 0

    def test_getitem_invalid_key_raises(self) -> None:
        """__getitem__ raises KeyError for unknown key."""
        m = OrchestratorMetrics()
        with pytest.raises(KeyError, match="not a valid metric"):
            _ = m["nonexistent_metric_xyz"]

    def test_contains_direct_attr(self) -> None:
        """__contains__ returns True for direct attribute."""
        m = OrchestratorMetrics()
        assert "delegation_count" in m

    def test_contains_component_key(self) -> None:
        """__contains__ returns True for component key."""
        m = OrchestratorMetrics()
        assert "total_tool_calls" in m

    def test_contains_false_for_unknown(self) -> None:
        """__contains__ returns False for unknown key."""
        m = OrchestratorMetrics()
        assert "this_key_does_not_exist" not in m

    def test_get_returns_default(self) -> None:
        """get() returns default for unknown key."""
        m = OrchestratorMetrics()
        result = m.get("nonexistent_xyz", default="fallback")
        assert result == "fallback"

    def test_get_returns_value(self) -> None:
        """get() returns value for known key."""
        m = OrchestratorMetrics()
        result = m.get("delegation_count", default=-1)
        assert result == 0

    def test_setitem_direct_attr(self) -> None:
        """__setitem__ sets direct attribute."""
        m = OrchestratorMetrics()
        m["delegation_count"] = 5
        assert m.delegation_count == 5

    def test_setitem_component_key(self) -> None:
        """__setitem__ sets component attribute via key map."""
        m = OrchestratorMetrics()
        m["total_tool_calls"] = 42
        assert m.tools.total_tool_calls == 42

    def test_setitem_invalid_key_raises(self) -> None:
        """__setitem__ raises KeyError for unknown key."""
        m = OrchestratorMetrics()
        with pytest.raises(KeyError, match="not a valid metric"):
            m["nonexistent_metric_xyz"] = 1

    def test_reset_for_run(self) -> None:
        """reset_for_run resets all counters."""
        m = OrchestratorMetrics()
        m.delegation_count = 10
        m.tools.total_tool_calls = 5
        m.reset_for_run()
        assert m.delegation_count == 0
        assert m.tools.total_tool_calls == 0

    def test_calculate_final_metrics(self) -> None:
        """calculate_final_metrics computes derived metrics."""
        m = OrchestratorMetrics()
        m.performance.task_start_time = 1000.0
        m.performance.task_end_time = 1120.0
        m.tools.total_tool_calls = 10
        m.delegation_count = 5

        m.calculate_final_metrics()

        assert m.performance.task_duration_minutes == 2.0
        assert m.performance.delegation_rate > 0

    def test_update_tool_metrics_read_file(self) -> None:
        """update_tool_metrics tracks file access for read_file."""
        m = OrchestratorMetrics()
        m.update_tool_metrics("read_file", {"path": "/some/file.py"}, success=True)
        assert "/some/file.py" in m.performance.files_accessed

    def test_update_tool_metrics_non_read_file(self) -> None:
        """update_tool_metrics doesn't track file access for other tools."""
        m = OrchestratorMetrics()
        m.update_tool_metrics("shell", {"cmd": "ls"}, success=True)
        assert len(m.performance.files_accessed) == 0


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics."""

    def test_calculate_file_re_reads_empty(self) -> None:
        """calculate_file_re_reads with no files accessed gives 0 re-reads."""
        p = PerformanceMetrics()
        p.calculate_file_re_reads()
        assert p.file_re_reads == 0

    def test_calculate_file_re_reads_with_reread(self) -> None:
        """calculate_file_re_reads counts re-reads correctly."""
        p = PerformanceMetrics()
        p.files_accessed = {"file.py": 3, "other.py": 1}
        p.calculate_file_re_reads()
        assert p.file_re_reads == 2  # 4 total - 2 unique = 2 re-reads

    def test_track_file_access(self) -> None:
        """track_file_access increments access counter."""
        p = PerformanceMetrics()
        p.track_file_access("file.py")
        p.track_file_access("file.py")
        assert p.files_accessed["file.py"] == 2

    def test_track_tool_usage(self) -> None:
        """track_tool_usage increments tool counter."""
        p = PerformanceMetrics()
        p.track_tool_usage("shell")
        p.track_tool_usage("shell")
        assert p.tool_usage_by_type["shell"] == 2

    def test_reset(self) -> None:
        """reset clears all performance metrics."""
        p = PerformanceMetrics()
        p.task_start_time = 100.0
        p.files_accessed = {"f": 1}
        p.reset()
        assert p.task_start_time == 0.0
        assert p.files_accessed == {}


class TestQualityMetrics:
    """Tests for QualityMetrics."""

    def test_calculate_test_percentage(self) -> None:
        """calculate_test_percentage computes percentage."""
        q = QualityMetrics()
        q.test_results["passing"] = 8
        q.test_results["total"] = 10
        q.calculate_test_percentage()
        assert q.test_results["percentage"] == 80.0

    def test_calculate_test_percentage_zero_total(self) -> None:
        """calculate_test_percentage handles zero total."""
        q = QualityMetrics()
        q.test_results["passing"] = 0
        q.test_results["total"] = 0
        q.calculate_test_percentage()
        assert q.test_results["percentage"] == 0.0

    def test_reset(self) -> None:
        """reset clears all quality metrics."""
        q = QualityMetrics()
        q.code_coverage = 95.0
        q.reset()
        assert q.code_coverage == 0.0


class TestToolMetrics:
    """Tests for ToolMetrics."""

    def test_track_tool_call_success(self) -> None:
        """track_tool_call increments success counters."""
        t = ToolMetrics()
        t.track_tool_call("shell", success=True)
        assert t.total_tool_calls == 1
        assert t.successful_tool_calls == 1
        assert t.shell_calls == 1

    def test_track_tool_call_failure(self) -> None:
        """track_tool_call increments failure counters."""
        t = ToolMetrics()
        t.track_tool_call("read_file", success=False)
        assert t.failed_tool_calls == 1
        assert t.read_file_calls == 1

    def test_track_tool_call_other(self) -> None:
        """track_tool_call uses OTHER category for unknown tools."""
        t = ToolMetrics()
        t.track_tool_call("web_fetch", success=True)
        assert t.other_tool_calls == 1

    def test_track_tool_call_git_ops(self) -> None:
        """track_tool_call increments git_ops_calls."""
        t = ToolMetrics()
        t.track_tool_call("git_ops", success=True)
        assert t.git_ops_calls == 1

    def test_track_tool_call_edit_file(self) -> None:
        """track_tool_call increments edit_file_calls."""
        t = ToolMetrics()
        t.track_tool_call("edit_file", success=True)
        assert t.edit_file_calls == 1

    def test_track_tool_call_write_file(self) -> None:
        """track_tool_call increments write_file_calls."""
        t = ToolMetrics()
        t.track_tool_call("write_file", success=True)
        assert t.write_file_calls == 1

    def test_calculate_error_rate(self) -> None:
        """calculate_error_rate returns correct percentage."""
        t = ToolMetrics()
        t.total_tool_calls = 10
        t.failed_tool_calls = 2
        assert t.calculate_error_rate() == 20.0

    def test_calculate_error_rate_zero_calls(self) -> None:
        """calculate_error_rate returns 0 when no calls."""
        t = ToolMetrics()
        assert t.calculate_error_rate() == 0.0

    def test_get_tool_call_counts_by_category(self) -> None:
        """get_tool_call_counts_by_category returns correct dict."""
        t = ToolMetrics()
        t.read_file_calls = 3
        counts = t.get_tool_call_counts_by_category()
        assert counts[ToolCategory.READ_FILE] == 3

    def test_reset(self) -> None:
        """reset clears all tool metrics."""
        t = ToolMetrics()
        t.total_tool_calls = 10
        t.reset()
        assert t.total_tool_calls == 0

    def test_calculate_final_metrics_no_duration(self) -> None:
        """calculate_final_metrics with zero times doesn't set duration."""
        m = OrchestratorMetrics()
        # task_start_time is 0 by default
        m.calculate_final_metrics()
        assert m.performance.task_duration_minutes == 0.0


class TestHelperFunctions:
    """Tests for module-level helper functions."""

    def test_categorize_tool_known(self) -> None:
        """_categorize_tool returns correct category for known tool."""
        assert _categorize_tool("shell") == ToolCategory.SHELL
        assert _categorize_tool("read_file") == ToolCategory.READ_FILE

    def test_categorize_tool_unknown(self) -> None:
        """_categorize_tool returns OTHER for unknown tool."""
        assert _categorize_tool("unknown_tool") == ToolCategory.OTHER

    def test_increment_counter(self) -> None:
        """_increment_counter increments key from 0."""
        counter: dict[str, int] = {}
        _increment_counter(counter, "key")
        assert counter["key"] == 1
        _increment_counter(counter, "key")
        assert counter["key"] == 2


# ---------------------------------------------------------------------------
# orchestrator_loop tests
# ---------------------------------------------------------------------------


class TestCollectEvents:
    """Tests for collect_events function."""

    @pytest.mark.anyio
    async def test_collect_content_events(self) -> None:
        """collect_events yields content events."""
        events = [
            AgentEvent(type=EventType.CONTENT, data="hi", source_agent="agent"),
        ]

        async def gen():
            for e in events:
                yield e

        pending: list = []
        collected = []
        async for e in collect_events(gen(), pending):
            collected.append(e)

        assert len(collected) == 1
        assert collected[0].data == "hi"

    @pytest.mark.anyio
    async def test_collect_tool_call_events(self) -> None:
        """collect_events appends tool calls to pending list."""
        tc = MagicMock()
        events = [
            AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=tc, source_agent="agent"),
        ]

        async def gen():
            for e in events:
                yield e

        pending: list = []
        async for _ in collect_events(gen(), pending):
            pass

        assert len(pending) == 1
        assert pending[0] is tc

    @pytest.mark.anyio
    async def test_collect_events_stop_async_iteration(self) -> None:
        """collect_events re-raises StopAsyncIteration (wrapped as RuntimeError in Python 3.7+)."""

        async def gen():
            yield AgentEvent(type=EventType.CONTENT, data="a", source_agent="agent")
            raise StopAsyncIteration

        pending: list = []
        with pytest.raises((StopAsyncIteration, RuntimeError)):
            async for _ in collect_events(gen(), pending):
                pass


class TestLastAssistantContent:
    """Tests for last_assistant_content function."""

    def test_returns_last_assistant_message(self) -> None:
        """last_assistant_content returns most recent assistant message."""
        agent = MagicMock()
        agent.messages = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
        ]
        result = last_assistant_content(agent)
        assert result == "Hello!"

    def test_returns_empty_when_no_assistant(self) -> None:
        """last_assistant_content returns empty string when no assistant messages."""
        agent = MagicMock()
        agent.messages = [
            Message(role="user", content="Hi"),
        ]
        result = last_assistant_content(agent)
        assert result == ""

    def test_raises_when_messages_is_none(self) -> None:
        """last_assistant_content raises TypeError when messages is None."""
        agent = MagicMock()
        agent.messages = None

        with pytest.raises(TypeError, match="cannot be None"):
            last_assistant_content(agent)

    def test_raises_when_messages_is_not_list(self) -> None:
        """last_assistant_content raises TypeError when messages is not a list."""
        agent = MagicMock()
        agent.messages = "not a list"

        with pytest.raises(TypeError, match="must be a list"):
            last_assistant_content(agent)

    def test_handles_non_string_content(self) -> None:
        """last_assistant_content converts non-string content to string."""
        agent = MagicMock()
        # Create message-like with non-string content
        msg = MagicMock()
        msg.role = "assistant"
        msg.content = 42  # non-string
        agent.messages = [msg]

        result = last_assistant_content(agent)
        assert result == "42"


class TestCheckColonStall:
    """Tests for check_colon_stall function."""

    def test_no_stall_when_max_retries_exceeded(self) -> None:
        """check_colon_stall returns None when max retries exceeded."""
        from henchman.agents.orchestrator_types import MAX_COLON_STALL_RETRIES

        agent = MagicMock()
        result = check_colon_stall(agent, retries=MAX_COLON_STALL_RETRIES)
        assert result is None

    def test_no_stall_when_content_doesnt_end_with_colon(self) -> None:
        """check_colon_stall returns None when content doesn't end with colon."""
        agent = MagicMock()
        agent.messages = [Message(role="assistant", content="Hello, I'm done.")]
        result = check_colon_stall(agent, retries=0)
        assert result is None

    def test_no_stall_when_content_too_short(self) -> None:
        """check_colon_stall returns None when content is too short."""
        agent = MagicMock()
        agent.messages = [Message(role="assistant", content="Hi:")]
        result = check_colon_stall(agent, retries=0)
        assert result is None

    def test_stall_detected(self) -> None:
        """check_colon_stall returns tuple when stall detected."""
        agent = MagicMock()
        long_colon_content = "This is a long message that ends with a colon:"
        agent.messages = [Message(role="assistant", content=long_colon_content)]
        agent.continue_with_tool_results = MagicMock(return_value=AsyncMock())

        result = check_colon_stall(agent, retries=0)
        assert result is not None
        _, new_retries = result
        assert new_retries == 1

    def test_stall_on_type_error(self) -> None:
        """check_colon_stall returns None when TypeError from last_assistant_content."""
        agent = MagicMock()
        agent.messages = None  # Will cause TypeError

        result = check_colon_stall(agent, retries=0)
        assert result is None


class TestFinalizeLoop:
    """Tests for finalize_loop function."""

    def test_finalize_with_record_delegation_errors(self) -> None:
        """finalize_loop calls record_delegation_errors when available."""
        orchestrator = MagicMock()
        agent = MagicMock()
        state = LoopState(tool_errors=["error1"], tool_call_count=3)

        finalize_loop(orchestrator, agent, state)

        agent.record_delegation_errors.assert_called_once_with(["error1"])
        assert orchestrator._last_loop_tool_call_count == 3

    def test_finalize_without_record_delegation_errors(self) -> None:
        """finalize_loop falls back to dynamic attribute when method missing."""
        orchestrator = MagicMock()
        agent = MagicMock(spec=[])  # No record_delegation_errors
        state = LoopState(tool_errors=["error1"], tool_call_count=2)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            finalize_loop(orchestrator, agent, state)

        assert orchestrator._last_loop_tool_call_count == 2
        # Should have issued DeprecationWarning
        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) > 0


class TestCheckTurnLimits:
    """Tests for check_turn_limits function."""

    def test_no_limit_exceeded(self) -> None:
        """check_turn_limits returns False when within limits."""
        agent = MagicMock()
        agent.messages = []
        params = AgentLoopParams(max_turns=100, msg_start_index=0)
        state = LoopState(tool_call_count=5)

        should_break, err = check_turn_limits(agent, params, state)
        assert should_break is False
        assert err is None


class TestRunToolsAndCollect:
    """Tests for run_tools_and_collect function."""

    @pytest.mark.anyio
    async def test_run_tools_increments_count(self) -> None:
        """run_tools_and_collect increments tool_call_count."""
        orchestrator = MagicMock()
        orchestrator.ledger = None
        agent = MagicMock()
        agent.messages = []
        agent.identity = None

        event = AgentEvent(type=EventType.CONTENT, data="result", source_agent="agent")

        async def fake_process(*args, **kwargs):
            yield event

        orchestrator.tool_controller.process_pending_tool_calls = fake_process

        pending = [MagicMock(), MagicMock()]  # 2 pending tool calls
        params = AgentLoopParams(depth=0)
        state = LoopState(tool_call_count=0)

        events = await run_tools_and_collect(orchestrator, agent, pending, params, state)

        assert state.tool_call_count == 2
        assert len(events) == 1


# ---------------------------------------------------------------------------
# delegation.py tests
# ---------------------------------------------------------------------------


class TestAddToSharedContext:
    """Tests for _add_to_shared_context helper."""

    def test_add_entry(self) -> None:
        """_add_to_shared_context adds entry to shared_context."""
        from henchman.agents.delegation import _add_to_shared_context

        shared: list = []
        _add_to_shared_context(shared, "engineer", "done", {"status": "DONE"})
        assert len(shared) == 1
        assert shared[0]["agent"] == "engineer"

    def test_size_limit_enforced(self) -> None:
        """_add_to_shared_context enforces MAX_SHARED_CONTEXT_ENTRIES limit."""
        from henchman.agents.delegation import (
            MAX_SHARED_CONTEXT_ENTRIES,
            _add_to_shared_context,
        )

        shared: list = [{"agent": f"a{i}", "summary": ""} for i in range(MAX_SHARED_CONTEXT_ENTRIES)]
        _add_to_shared_context(shared, "new-agent", "summary", {})

        assert len(shared) == MAX_SHARED_CONTEXT_ENTRIES
        # Oldest entry evicted, newest is last
        assert shared[-1]["agent"] == "new-agent"


class TestPrepareExecution:
    """Tests for _prepare_execution function."""

    def _make_runner(self) -> Any:
        """Create minimal DelegationRunner-like object.

        Returns:
            Mock DelegationRunner.
        """
        runner = MagicMock()
        runner.shared_context = []
        runner.ledger = None
        runner._prepare_delegation_context.return_value = {}
        runner._assemble_delegation_input.return_value = "full task"
        return runner

    def _make_protocol_agent(self) -> Any:
        """Create an agent that conforms to AgentProtocol.

        Returns:
            An agent object with the required interface.
        """

        class ConformingAgent:
            """Agent that conforms to AgentProtocol."""

            def __init__(self) -> None:
                """Initialize with empty messages."""
                self.messages: list = []

            def clear_history(self) -> None:
                """Clear history."""
                self.messages.clear()

            def get_delegation_errors(self) -> list:
                """Return delegation errors."""
                return []

            def record_delegation_errors(self, errors: list) -> None:
                """Record delegation errors."""
                pass

        return ConformingAgent()

    def test_raises_when_target_agent_none(self) -> None:
        """_prepare_execution raises ValueError when target_agent is None."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        params.target_agent = None

        with pytest.raises(ValueError, match="target_agent is None"):
            _prepare_execution(runner, params)

    def test_raises_when_not_agent_protocol(self) -> None:
        """_prepare_execution raises TypeError when agent doesn't conform to AgentProtocol."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        # Plain object without required interface
        params.target_agent = object()

        with pytest.raises(TypeError, match="does not conform to AgentProtocol"):
            _prepare_execution(runner, params)

    def test_raises_when_messages_is_none(self) -> None:
        """_prepare_execution raises TypeError when messages is None."""
        from henchman.agents.delegation import AgentProtocol, _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")

        class AgentWithNoneMessages:
            """Agent with None messages."""

            messages = None  # type: ignore[assignment]

            def clear_history(self) -> None:
                """Clear history."""

            def get_delegation_errors(self) -> list:
                """Return delegation errors."""
                return []

        agent = AgentWithNoneMessages()
        # Check if it passes AgentProtocol isinstance - if yes, it'll raise TypeError later
        if isinstance(agent, AgentProtocol):
            params.target_agent = agent
            with pytest.raises(TypeError, match="has messages=None"):
                _prepare_execution(runner, params)
        else:
            # Protocol check itself fails
            params.target_agent = agent
            with pytest.raises(TypeError):
                _prepare_execution(runner, params)

    def test_raises_when_clear_history_fails(self) -> None:
        """_prepare_execution re-raises when clear_history raises."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        agent = self._make_protocol_agent()
        # Override clear_history to fail
        agent.clear_history = lambda: (_ for _ in ()).throw(RuntimeError("db error"))
        params.target_agent = agent

        with pytest.raises(RuntimeError):
            _prepare_execution(runner, params)

    def test_success(self) -> None:
        """_prepare_execution succeeds with valid agent."""
        from henchman.agents.delegation import _prepare_execution
        from henchman.agents.orchestrator_types import DelegationParams

        runner = self._make_runner()
        params = DelegationParams(target_role="engineer", task="fix bug")
        agent = self._make_protocol_agent()
        agent.messages = [MagicMock(), MagicMock()]  # 2 messages
        params.target_agent = agent

        _prepare_execution(runner, params)

        assert params.full_task == "full task"
        assert params.msg_start == 0  # clear_history() was called, so messages is empty


class TestAssembleDelegationInput:
    """Tests for DelegationRunner._assemble_delegation_input static method."""

    def test_basic_task_only(self) -> None:
        """_assemble_delegation_input with task only."""
        from henchman.agents.delegation import DelegationRunner

        result = DelegationRunner._assemble_delegation_input("Fix the bug", None)
        assert "## Task\nFix the bug" in result

    def test_with_mission(self) -> None:
        """_assemble_delegation_input includes mission header."""
        from henchman.agents.delegation import DelegationRunner

        result = DelegationRunner._assemble_delegation_input(
            "Fix the bug", None, mission="Build the app"
        )
        assert "## Mission\nBuild the app" in result

    def test_with_brief_done_when(self) -> None:
        """_assemble_delegation_input includes Done When section."""
        from henchman.agents.delegation import DelegationRunner

        brief = {"done_when": "Tests pass"}
        result = DelegationRunner._assemble_delegation_input("Fix", brief)
        assert "## Done When\nTests pass" in result

    def test_with_brief_requirements(self) -> None:
        """_assemble_delegation_input includes Requirements section."""
        from henchman.agents.delegation import DelegationRunner

        brief = {"requirements": "Must use Python 3.10"}
        result = DelegationRunner._assemble_delegation_input("Fix", brief)
        assert "## Requirements\nMust use Python 3.10" in result

    def test_with_brief_files(self) -> None:
        """_assemble_delegation_input includes Relevant Files section."""
        from henchman.agents.delegation import DelegationRunner

        brief = {"files": ["src/main.py", "tests/test_main.py"]}
        result = DelegationRunner._assemble_delegation_input("Fix", brief)
        assert "## Relevant Files" in result
        assert "src/main.py" in result

    def test_with_brief_depends_on_string(self) -> None:
        """_assemble_delegation_input handles depends_on as string."""
        from henchman.agents.delegation import DelegationRunner

        brief = {"depends_on": "Create database schema"}
        result = DelegationRunner._assemble_delegation_input("Fix", brief)
        assert "## Depends On" in result

    def test_with_brief_depends_on_list(self) -> None:
        """_assemble_delegation_input handles depends_on as list."""
        from henchman.agents.delegation import DelegationRunner

        brief = {"depends_on": ["Task A", "Task B"]}
        result = DelegationRunner._assemble_delegation_input("Fix", brief)
        assert "Task A" in result
        assert "Task B" in result

    def test_with_brief_background(self) -> None:
        """_assemble_delegation_input includes Background section."""
        from henchman.agents.delegation import DelegationRunner

        brief = {"background": "Prior work done"}
        result = DelegationRunner._assemble_delegation_input("Fix", brief)
        assert "## Background\nPrior work done" in result

    def test_with_brief_context(self) -> None:
        """_assemble_delegation_input includes Additional Context section."""
        from henchman.agents.delegation import DelegationRunner

        brief = {"context": "Extra info"}
        result = DelegationRunner._assemble_delegation_input("Fix", brief)
        assert "## Additional Context\nExtra info" in result


class TestParseCompletionReport:
    """Tests for DelegationRunner._parse_completion_report."""

    def test_parse_full_report(self) -> None:
        """_parse_completion_report extracts all fields."""
        from henchman.agents.delegation import DelegationRunner

        summary = (
            "STATUS: DONE\n"
            "FILES_MODIFIED: src/main.py\n"
            "TESTS_RUN: 10\n"
            "VERIFICATION: All tests pass\n"
            "BLOCKERS: None\n"
            "HANDOFF_NOTES: See docs\n"
            "ARTIFACTS: coverage.xml\n"
        )
        result = DelegationRunner._parse_completion_report(summary)
        assert result["status"] == "DONE"
        assert result["files_modified"] == "src/main.py"
        assert result["tests_run"] == "10"

    def test_parse_empty_summary(self) -> None:
        """_parse_completion_report returns empty dict for unformatted summary."""
        from henchman.agents.delegation import DelegationRunner

        result = DelegationRunner._parse_completion_report("Just some text without fields")
        assert result == {}


class TestPrepareDelegationContext:
    """Tests for DelegationRunner._prepare_delegation_context."""

    def _make_runner_with_pool(self) -> Any:
        """Create a DelegationRunner with mock pool.

        Returns:
            DelegationRunner instance with mocks.
        """
        from henchman.agents.delegation import DelegationRunner
        from henchman.agents.orchestrator_types import CompletionStatus

        pool = MagicMock()
        settings = MagicMock()
        settings.agents.max_delegation_turns = 10
        settings.agents.max_delegation_depth = 3

        runner = DelegationRunner(
            pool=pool,
            settings=settings,
            shared_context=[],
            metrics=OrchestratorMetrics(),
            run_agent_loop=MagicMock(),
            assess_completion=MagicMock(return_value=CompletionStatus.COMPLETED),
        )
        return runner

    def test_no_context_no_ledger(self) -> None:
        """_prepare_delegation_context with empty context and no ledger."""
        runner = self._make_runner_with_pool()
        result = runner._prepare_delegation_context("engineer", None)
        assert isinstance(result, dict)

    def test_with_shared_context(self) -> None:
        """_prepare_delegation_context injects shared_context as handoff notes."""
        runner = self._make_runner_with_pool()
        runner.shared_context = [
            {"agent": "planner", "summary": "Plan created", "timestamp": "2024-01-01"},
        ]
        result = runner._prepare_delegation_context("engineer", {})
        assert "Prior agent work" in result.get("background", "")

    def test_with_prior_failure_in_ledger(self) -> None:
        """_prepare_delegation_context injects failure context from ledger."""
        runner = self._make_runner_with_pool()
        ledger = MagicMock()
        failed_delegation = MagicMock()
        failed_delegation.agent = "engineer"
        failed_delegation.task = "Fix the bug"
        failed_delegation.status = "FAILED"
        ledger.delegations = [failed_delegation]
        runner.ledger = ledger

        result = runner._prepare_delegation_context("engineer", {})
        assert "Prior Attempt Failed" in result.get("background", "")

    def test_with_existing_background_and_shared_context(self) -> None:
        """_prepare_delegation_context appends to existing background."""
        runner = self._make_runner_with_pool()
        runner.shared_context = [
            {"agent": "planner", "summary": "Plan done", "timestamp": "2024-01-01"},
        ]
        brief = {"background": "Existing background"}
        result = runner._prepare_delegation_context("engineer", brief)
        assert "Existing background" in result["background"]
        assert "Prior agent work" in result["background"]
