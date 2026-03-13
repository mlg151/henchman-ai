"""Tests to achieve 100% coverage for agents/delegation.py.

Targets specific missing lines:
- _add_to_shared_context: TypeError/ValueError validation paths (104, 110, 116, 122)
- _execute_loop: non-aiter result TypeError (329) and except wrapper (338-342)
- run_delegation: execute loop exception path (512-524)
- _get_target_agent_with_error_handling: mock _mock_name path (650)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAddToSharedContextValidation:
    """Tests for _add_to_shared_context validation error paths."""

    def test_shared_context_not_list_raises_type_error(self) -> None:
        """Line 104: TypeError when shared_context is not a list."""
        from henchman.agents.delegation import _add_to_shared_context

        with pytest.raises(TypeError, match="shared_context must be a list"):
            _add_to_shared_context(
                shared_context="not-a-list",  # type: ignore[arg-type]
                target_role="explorer",
                summary="done",
                parsed={},
            )

    def test_target_role_empty_string_raises_value_error(self) -> None:
        """Line 110: ValueError when target_role is empty string."""
        from henchman.agents.delegation import _add_to_shared_context

        with pytest.raises(ValueError, match="target_role must be a non-empty string"):
            _add_to_shared_context(
                shared_context=[],
                target_role="   ",  # whitespace-only = empty after strip
                summary="done",
                parsed={},
            )

    def test_target_role_none_raises_value_error(self) -> None:
        """Line 110: ValueError when target_role is None."""
        from henchman.agents.delegation import _add_to_shared_context

        with pytest.raises(ValueError, match="target_role must be a non-empty string"):
            _add_to_shared_context(
                shared_context=[],
                target_role=None,  # type: ignore[arg-type]
                summary="done",
                parsed={},
            )

    def test_summary_not_string_raises_type_error(self) -> None:
        """Line 116: TypeError when summary is not a string."""
        from henchman.agents.delegation import _add_to_shared_context

        with pytest.raises(TypeError, match="summary must be a string or None"):
            _add_to_shared_context(
                shared_context=[],
                target_role="explorer",
                summary=42,  # type: ignore[arg-type]
                parsed={},
            )

    def test_parsed_not_dict_raises_type_error(self) -> None:
        """Line 122: TypeError when parsed is not a dict."""
        from henchman.agents.delegation import _add_to_shared_context

        with pytest.raises(TypeError, match="parsed must be a dict"):
            _add_to_shared_context(
                shared_context=[],
                target_role="explorer",
                summary="done",
                parsed="not-a-dict",  # type: ignore[arg-type]
            )


class TestExecuteLoop:
    """Tests for _execute_loop error paths."""

    @pytest.mark.anyio
    async def test_execute_loop_non_aiter_raises_type_error_wrapped_as_runtime(
        self,
    ) -> None:
        """Lines 329, 338-342: TypeError when _run_agent_loop returns non-aiter.

        The TypeError is caught and re-raised as RuntimeError with context.
        """
        from henchman.agents.delegation import _execute_loop
        from henchman.agents.orchestrator_types import DelegationParams
        from henchman.config.schema import Settings
        from henchman.providers.base import Message

        mock_agent = MagicMock()
        mock_agent.messages = [Message(role="user", content="test")]

        # _run_agent_loop returns something without __aiter__
        non_aiter_result = object()  # plain object, no __aiter__

        def bad_loop_runner(params: Any) -> Any:
            """Return non-async-iterable."""
            return non_aiter_result

        from henchman.agents.delegation import DelegationRunner

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=bad_loop_runner,
            assess_completion=MagicMock(),
        )

        params = DelegationParams(
            target_role="coder",
            task="test task",
            brief=None,
            depth=0,
        )
        params.target_agent = mock_agent
        params.full_task = "do the test"
        params.msg_start = 0

        with pytest.raises(RuntimeError, match="Failed to execute agent loop"):
            async for _ in _execute_loop(runner, params):
                pass


class TestRunDelegationExecuteLoopError:
    """Tests for run_delegation execute-loop exception path."""

    @pytest.mark.anyio
    async def test_run_delegation_execute_loop_exception_yields_error(self) -> None:
        """Lines 512-524: run_delegation yields ERROR when _execute_loop raises."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.agents.orchestrator_types import DelegationParams
        from henchman.config.schema import Settings
        from henchman.core.events import EventType
        from henchman.providers.base import Message

        mock_agent = MagicMock()
        mock_agent.messages = [Message(role="user", content="test")]
        mock_agent.clear_history = MagicMock()

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

        # Mock _get_target_agent_with_error_handling to return the mock agent directly
        runner._get_target_agent_with_error_handling = AsyncMock(return_value=mock_agent)

        # Mock _prepare_execution to succeed (do nothing)
        with patch("henchman.agents.delegation._prepare_execution"):
            # Mock _execute_loop to raise an exception
            async def raising_execute_loop(*args: Any, **kwargs: Any) -> Any:
                """Raise during execution."""
                raise RuntimeError("loop exploded")
                yield  # make it an async generator

            with patch("henchman.agents.delegation._execute_loop", raising_execute_loop):
                params = DelegationParams(
                    target_role="explorer",
                    task="test",
                    brief=None,
                    depth=0,
                )
                events = []
                async for event in runner.run_delegation(params):
                    events.append(event)

        error_events = [e for e in events if e.type == EventType.ERROR]
        assert error_events, "Expected ERROR event from execute loop exception"
        assert "Failed to execute delegation" in str(error_events[0].data)


class TestGetTargetAgentWithMockName:
    """Tests for _get_target_agent_with_error_handling success path with mock."""

    @pytest.mark.anyio
    async def test_get_target_agent_success_mock_has_mock_name(self) -> None:
        """Line 650: pass branch when clear_history is a MagicMock with _mock_name.

        Uses a MagicMock where clear_history is auto-generated (not explicit),
        which gives it the _mock_name attribute.
        """
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings
        from henchman.providers.base import Message

        mock_agent = MagicMock()
        # Explicitly set messages to a list (so Sequence check passes)
        mock_agent.messages = [Message(role="user", content="test")]
        # Do NOT set clear_history explicitly; MagicMock auto-creates it with _mock_name

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )
        runner.pool.get_agent.return_value = mock_agent

        result = await runner._get_target_agent_with_error_handling("explorer")

        # Should return the agent, not an error event
        assert result is mock_agent


class TestProcessDelegationResultsValidation:
    """Tests for _process_delegation_results validation error paths."""

    def _make_runner(self) -> DelegationRunner:
        """Create a DelegationRunner instance."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings

        return DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

    def test_msg_start_not_int_raises_type_error(self) -> None:
        """Line 738: TypeError when msg_start is not an int."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        with pytest.raises(TypeError, match="msg_start must be an integer"):
            runner._process_delegation_results("explorer", mock_agent, "not-an-int")

    def test_msg_start_negative_raises_value_error(self) -> None:
        """Line 743: ValueError when msg_start < 0."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        with pytest.raises(ValueError, match="msg_start must be non-negative"):
            runner._process_delegation_results("explorer", mock_agent, -1)

    def test_agent_missing_messages_raises_attribute_error(self) -> None:
        """Line 749: AttributeError when target_agent has no 'messages'."""
        runner = self._make_runner()

        class NoMessages:
            pass

        with pytest.raises(AttributeError, match="target_agent missing 'messages' attribute"):
            runner._process_delegation_results("explorer", NoMessages(), 0)

    def test_messages_is_none_raises_value_error(self) -> None:
        """Line 755: ValueError when target_agent.messages is None."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = None
        with pytest.raises(ValueError, match="target_agent.messages is None"):
            runner._process_delegation_results("explorer", mock_agent, 0)

    def test_messages_not_sequence_raises_type_error(self) -> None:
        """Line 758: TypeError when target_agent.messages is not a Sequence."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = 42  # int is not a Sequence
        with pytest.raises(TypeError, match="target_agent.messages must be a Sequence"):
            runner._process_delegation_results("explorer", mock_agent, 0)

    def test_msg_start_exceeds_messages_length_raises_value_error(self) -> None:
        """Line 764: ValueError when msg_start > len(messages)."""
        from henchman.providers.base import Message

        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = [Message(role="user", content="hello")]
        with pytest.raises(ValueError, match="msg_start.*exceeds messages length"):
            runner._process_delegation_results("explorer", mock_agent, 5)

    def test_messages_contain_non_message_objects_raises_type_error(self) -> None:
        """Line 775: TypeError when messages don't have role/content."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = ["plain string - not a Message"]  # Wrong type
        with pytest.raises(TypeError, match="messages do not appear to be Message instances"):
            runner._process_delegation_results("explorer", mock_agent, 0)

    def test_messages_sequence_raises_index_error_wrapped_as_type_error(self) -> None:
        """Lines 779-781: IndexError from messages[msg_start] is wrapped as TypeError."""
        from collections.abc import Sequence as AbcSequence

        runner = self._make_runner()
        mock_agent = MagicMock()

        # Create a sequence that passes isinstance check but raises IndexError when indexed
        class BrokenSequence(AbcSequence):
            def __len__(self) -> int:
                return 5

            def __getitem__(self, idx: int) -> object:
                raise IndexError("broken index")

        mock_agent.messages = BrokenSequence()
        with pytest.raises(TypeError, match="Invalid messages sequence"):
            runner._process_delegation_results("explorer", mock_agent, 0)


class TestProcessDelegationResultsToolErrors:
    """Tests for tool error handling edge cases in _process_delegation_results."""

    def _make_runner(self) -> DelegationRunner:
        """Create a DelegationRunner instance."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.config.schema import Settings

        return DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(),
        )

    def test_get_delegation_errors_returns_none(self) -> None:
        """Test when get_delegation_errors() returns None."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to return None
        mock_agent.get_delegation_errors.return_value = None

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not crash, should not include tool errors in summary
        assert "TOOL ERRORS" not in summary
        assert mock_agent.get_delegation_errors.called

    def test_get_delegation_errors_returns_non_list(self) -> None:
        """Test when get_delegation_errors() returns a non-list type."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to return a string (wrong type)
        mock_agent.get_delegation_errors.return_value = "not a list"

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not crash, should not include tool errors in summary
        assert "TOOL ERRORS" not in summary
        assert mock_agent.get_delegation_errors.called

    def test_get_delegation_errors_returns_list_with_none_values(self) -> None:
        """Test when get_delegation_errors() returns list containing None values."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to return list with None
        mock_agent.get_delegation_errors.return_value = [None, "error1", None, "error2"]

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should filter out None values, only include string errors
        assert "TOOL ERRORS" in summary
        assert "error1" in summary
        assert "error2" in summary

    def test_get_delegation_errors_returns_list_with_non_stringifiable_objects(self) -> None:
        """Test when get_delegation_errors() returns list with objects that can't be stringified."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        class NonStringifiable:
            def __str__(self) -> str:
                raise TypeError("Cannot convert to string")

        # Mock get_delegation_errors to return list with non-stringifiable object
        mock_agent.get_delegation_errors.return_value = ["error1", NonStringifiable(), "error2"]

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should skip non-stringifiable objects, include others
        assert "TOOL ERRORS" in summary
        assert "error1" in summary
        assert "error2" in summary
        # NonStringifiable should be skipped

    def test_get_delegation_errors_raises_attribute_error(self) -> None:
        """Test when get_delegation_errors() raises AttributeError."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to raise AttributeError
        mock_agent.get_delegation_errors.side_effect = AttributeError("Method not implemented")

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not crash, should not include tool errors in summary
        assert "TOOL ERRORS" not in summary

    def test_get_delegation_errors_raises_type_error(self) -> None:
        """Test when get_delegation_errors() raises TypeError."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to raise TypeError
        mock_agent.get_delegation_errors.side_effect = TypeError("Not callable")

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not crash, should not include tool errors in summary
        assert "TOOL ERRORS" not in summary

    def test_fallback_to_delegation_tool_errors_attribute(self) -> None:
        """Test fallback to _delegation_tool_errors when get_delegation_errors not available."""
        runner = self._make_runner()

        # Create a mock without get_delegation_errors method
        mock_agent = MagicMock(spec=[])
        # Add messages attribute
        mock_agent.messages = []
        # Add _delegation_tool_errors attribute
        mock_agent._delegation_tool_errors = ["error1", "error2"]

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should use _delegation_tool_errors and include errors in summary
        assert "TOOL ERRORS" in summary
        assert "error1" in summary
        assert "error2" in summary

    def test_fallback_delegation_tool_errors_not_list(self) -> None:
        """Test when _delegation_tool_errors exists but is not a list."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock _delegation_tool_errors as a string (wrong type)
        mock_agent._delegation_tool_errors = "not a list"

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not crash, should not include tool errors in summary
        assert "TOOL ERRORS" not in summary

    def test_fallback_delegation_tool_errors_none(self) -> None:
        """Test when _delegation_tool_errors exists but is None."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock _delegation_tool_errors as None
        mock_agent._delegation_tool_errors = None

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not crash, should not include tool errors in summary
        assert "TOOL ERRORS" not in summary

    def test_no_tool_errors_methods_available(self) -> None:
        """Test when neither get_delegation_errors nor _delegation_tool_errors are available."""
        runner = self._make_runner()

        # Create a mock without either method
        mock_agent = MagicMock(spec=[])
        # Add only messages attribute
        mock_agent.messages = []

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not crash, should not include tool errors in summary
        assert "TOOL ERRORS" not in summary

    def test_tool_errors_empty_list(self) -> None:
        """Test when tool errors list is empty."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to return empty list
        mock_agent.get_delegation_errors.return_value = []

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not include TOOL ERRORS section when list is empty
        assert "TOOL ERRORS" not in summary

    def test_tool_errors_slicing_with_few_errors(self) -> None:
        """Test tool error slicing when there are fewer errors than RECENT_ERRORS_TO_SHOW."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to return 3 errors (less than default 10)
        mock_agent.get_delegation_errors.return_value = ["error1", "error2", "error3"]

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should include all errors
        assert "TOOL ERRORS" in summary
        assert "error1" in summary
        assert "error2" in summary
        assert "error3" in summary

    def test_tool_errors_slicing_with_many_errors(self) -> None:
        """Test tool error slicing when there are more errors than RECENT_ERRORS_TO_SHOW."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to return 15 errors (more than default 10)
        # Use distinct error names that won't be substrings of each other
        errors = [f"err_{i:02d}" for i in range(15)]  # err_00, err_01, ..., err_14
        mock_agent.get_delegation_errors.return_value = errors

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should only include last 10 errors
        assert "TOOL ERRORS" in summary
        for i in range(5, 15):  # Last 10 errors (err_05 through err_14)
            assert f"err_{i:02d}" in summary
        # First 5 errors should not be included
        for i in range(5):
            assert f"err_{i:02d}" not in summary

    def test_get_delegation_errors_raises_unexpected_exception(self) -> None:
        """Test when get_delegation_errors() raises an unexpected exception (caught by catch-all)."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        # Mock get_delegation_errors to raise an exception not in the specific list
        # KeyError is not in (AttributeError, TypeError, ValueError, RuntimeError)
        mock_agent.get_delegation_errors.side_effect = KeyError("unexpected error")

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should not crash, should not include tool errors in summary
        # Exception should be caught by the catch-all except Exception block
        assert "TOOL ERRORS" not in summary

    def test_inner_type_error_value_error_caught(self) -> None:
        """Test when string conversion raises TypeError/ValueError inside the loop."""
        runner = self._make_runner()
        mock_agent = MagicMock()
        mock_agent.messages = []

        class RaisesOnStr:
            def __str__(self) -> str:
                raise ValueError("Cannot convert to string")

        # Mock get_delegation_errors to return list with object that raises on str()
        mock_agent.get_delegation_errors.return_value = ["error1", RaisesOnStr(), "error2"]

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should include other errors, skip the one that raises
        assert "TOOL ERRORS" in summary
        assert "error1" in summary
        assert "error2" in summary
        # The RaisesOnStr object should be skipped (no crash)

    def test_fallback_path_inner_type_error_value_error_caught(self) -> None:
        """Test when string conversion raises TypeError/ValueError inside the loop in fallback path."""
        runner = self._make_runner()

        # Create a mock without get_delegation_errors method (so it uses fallback)
        mock_agent = MagicMock(spec=[])
        mock_agent.messages = []

        class RaisesOnStr:
            def __str__(self) -> str:
                raise TypeError("Cannot convert to string")

        # Mock _delegation_tool_errors with object that raises on str()
        mock_agent._delegation_tool_errors = ["error1", RaisesOnStr(), "error2"]

        summary, parsed, status = runner._process_delegation_results("explorer", mock_agent, 0)

        # Should include other errors, skip the one that raises
        assert "TOOL ERRORS" in summary
        assert "error1" in summary
        assert "error2" in summary
        # The RaisesOnStr object should be skipped (no crash)


# ---------------------------------------------------------------------------
# _parse_completion_report — non-string input raises TypeError
# ---------------------------------------------------------------------------


class TestParseCompletionReportTypeCheck:
    """Tests for _parse_completion_report type validation."""

    def test_non_string_raises_type_error(self) -> None:
        """Passing a non-string raises TypeError."""
        from henchman.agents.delegation import _parse_completion_report

        with pytest.raises(TypeError, match="summary must be a string"):
            _parse_completion_report(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _enrich_completion_from_report — semantic completion enrichment
# ---------------------------------------------------------------------------


class TestEnrichCompletionFromReport:
    """Tests for _enrich_completion_from_report."""

    def test_stalled_passes_through_unchanged(self) -> None:
        """STALLED status is returned unchanged regardless of parsed report."""
        from henchman.agents.orchestrator_anchoring import _enrich_completion_from_report
        from henchman.agents.orchestrator_types import CompletionStatus

        result = _enrich_completion_from_report(
            CompletionStatus.STALLED,
            {"status": "completed"},
        )
        assert result == CompletionStatus.STALLED

    def test_no_work_done_passes_through_unchanged(self) -> None:
        """NO_WORK_DONE status is returned unchanged regardless of parsed report."""
        from henchman.agents.orchestrator_anchoring import _enrich_completion_from_report
        from henchman.agents.orchestrator_types import CompletionStatus

        result = _enrich_completion_from_report(
            CompletionStatus.NO_WORK_DONE,
            {"status": "completed"},
        )
        assert result == CompletionStatus.NO_WORK_DONE

    def test_completed_with_failure_status_downgraded(self) -> None:
        """COMPLETED downgraded to NO_WORK_DONE when report STATUS is a failure token."""
        from henchman.agents.orchestrator_anchoring import _enrich_completion_from_report
        from henchman.agents.orchestrator_types import CompletionStatus

        for token in ("failed", "blocked", "error", "incomplete", "failure"):
            result = _enrich_completion_from_report(
                CompletionStatus.COMPLETED,
                {"status": token},
            )
            assert result == CompletionStatus.NO_WORK_DONE, f"Expected downgrade for {token!r}"

    def test_completed_with_blockers_downgraded(self) -> None:
        """COMPLETED downgraded to NO_WORK_DONE when report has non-empty BLOCKERS."""
        from henchman.agents.orchestrator_anchoring import _enrich_completion_from_report
        from henchman.agents.orchestrator_types import CompletionStatus

        result = _enrich_completion_from_report(
            CompletionStatus.COMPLETED,
            {"blockers": "Waiting for API key"},
        )
        assert result == CompletionStatus.NO_WORK_DONE

    def test_completed_with_empty_report_stays_completed(self) -> None:
        """COMPLETED stays COMPLETED when report has no failure signals."""
        from henchman.agents.orchestrator_anchoring import _enrich_completion_from_report
        from henchman.agents.orchestrator_types import CompletionStatus

        result = _enrich_completion_from_report(CompletionStatus.COMPLETED, {})
        assert result == CompletionStatus.COMPLETED

    def test_completed_with_ok_status_stays_completed(self) -> None:
        """COMPLETED stays COMPLETED when report STATUS is 'done'."""
        from henchman.agents.orchestrator_anchoring import _enrich_completion_from_report
        from henchman.agents.orchestrator_types import CompletionStatus

        result = _enrich_completion_from_report(
            CompletionStatus.COMPLETED,
            {"status": "done"},
        )
        assert result == CompletionStatus.COMPLETED

    def test_status_token_matching_is_case_insensitive(self) -> None:
        """Status token matching is case-insensitive."""
        from henchman.agents.orchestrator_anchoring import _enrich_completion_from_report
        from henchman.agents.orchestrator_types import CompletionStatus

        result = _enrich_completion_from_report(
            CompletionStatus.COMPLETED,
            {"status": "FAILED"},
        )
        assert result == CompletionStatus.NO_WORK_DONE


# ---------------------------------------------------------------------------
# _score_context_relevance — relevance-based context selection
# ---------------------------------------------------------------------------


class TestScoreContextRelevance:
    """Tests for _score_context_relevance."""

    def test_same_agent_gets_role_bonus(self) -> None:
        """Entry from the same specialist gets a 0.3 role bonus."""
        from henchman.agents.delegation import _score_context_relevance

        entry = {"agent": "coder", "summary": "wrote code", "files_modified": ""}
        score = _score_context_relevance(entry, task="write tests", target_role="coder")
        assert score >= 0.3

    def test_different_agent_no_role_bonus(self) -> None:
        """Entry from a different specialist gets no role bonus."""
        from henchman.agents.delegation import _score_context_relevance

        entry = {"agent": "explorer", "summary": "wrote code", "files_modified": ""}
        score_same = _score_context_relevance(entry, task="test", target_role="explorer")
        score_diff = _score_context_relevance(entry, task="test", target_role="coder")
        assert score_same > score_diff

    def test_keyword_overlap_increases_score(self) -> None:
        """Overlap between task tokens and summary tokens increases score."""
        from henchman.agents.delegation import _score_context_relevance

        entry_relevant = {
            "agent": "coder",
            "summary": "refactored authentication module",
            "files_modified": "",
        }
        entry_irrelevant = {
            "agent": "coder",
            "summary": "updated CSS styles",
            "files_modified": "",
        }
        score_rel = _score_context_relevance(
            entry_relevant, task="fix authentication bug", target_role="other"
        )
        score_irr = _score_context_relevance(
            entry_irrelevant, task="fix authentication bug", target_role="other"
        )
        assert score_rel > score_irr

    def test_empty_task_only_role_bonus(self) -> None:
        """Empty task string → only role bonus contributes to score."""
        from henchman.agents.delegation import _score_context_relevance

        entry = {"agent": "coder", "summary": "something", "files_modified": ""}
        score = _score_context_relevance(entry, task="", target_role="coder")
        assert score == 0.3

    def test_files_modified_contributes_to_overlap(self) -> None:
        """files_modified text is included in the overlap computation."""
        from henchman.agents.delegation import _score_context_relevance

        entry = {
            "agent": "other",
            "summary": "",
            "files_modified": "auth database",
        }
        score = _score_context_relevance(entry, task="auth module", target_role="x")
        assert score > 0


# ---------------------------------------------------------------------------
# run_parallel_delegations — concurrent delegation merging
# ---------------------------------------------------------------------------


class TestRunParallelDelegations:
    """Tests for DelegationRunner.run_parallel_delegations."""

    @pytest.mark.asyncio
    async def test_parallel_delegations_emit_all_events(self) -> None:
        """Events from all parallel delegations are emitted."""

        from henchman.agents.delegation import DelegationRunner
        from henchman.agents.orchestrator_types import CompletionStatus, DelegationParams
        from henchman.config.schema import Settings
        from henchman.core.events import AgentEvent, EventType

        async def fake_run(params: DelegationParams) -> Any:
            yield AgentEvent(
                type=EventType.CONTENT,
                data=f"result-{params.target_role}",
                source_agent=params.target_role,
            )

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(return_value=CompletionStatus.COMPLETED),
        )
        runner.run_delegation = fake_run  # type: ignore[method-assign]

        params_list = [
            DelegationParams(target_role="agent_a", task="task a"),
            DelegationParams(target_role="agent_b", task="task b"),
        ]

        events = []
        async for event in runner.run_parallel_delegations(params_list):
            events.append(event)

        sources = {e.source_agent for e in events}
        assert "agent_a" in sources
        assert "agent_b" in sources

    @pytest.mark.asyncio
    async def test_empty_params_list_emits_no_events(self) -> None:
        """Empty params list produces no events."""
        from henchman.agents.delegation import DelegationRunner
        from henchman.agents.orchestrator_types import CompletionStatus
        from henchman.config.schema import Settings

        runner = DelegationRunner(
            pool=MagicMock(),
            settings=Settings(),
            shared_context=[],
            metrics=MagicMock(),
            run_agent_loop=AsyncMock(),
            assess_completion=MagicMock(return_value=CompletionStatus.COMPLETED),
        )

        events = []
        async for event in runner.run_parallel_delegations([]):
            events.append(event)

        assert events == []


# ---------------------------------------------------------------------------
# DelegationController retry path
# ---------------------------------------------------------------------------


class TestDelegationControllerRetry:
    """Tests for the retry loop in DelegationController._run_delegation."""

    def _make_ctrl(self, *, retries: int = 1) -> DelegationController:
        """Create a DelegationController with a mock orchestrator."""
        from henchman.agents.orchestrator_delegation_ctrl import DelegationController
        from henchman.config.schema import AgentSettings, Settings

        orchestrator = MagicMock()
        orchestrator.settings = Settings(
            agents=AgentSettings(max_delegation_retries=retries)
        )
        orchestrator.ledger = MagicMock()
        orchestrator.ledger.render.return_value = "LEDGER"
        orchestrator.ledger.add_delegation.return_value = MagicMock()
        ctrl = DelegationController.__new__(DelegationController)
        ctrl.orchestrator = orchestrator
        ctrl.metrics = MagicMock()
        return ctrl

    @pytest.mark.asyncio
    async def test_retry_on_error_creates_new_ledger_record(self) -> None:
        """On error with retries remaining, a new ledger record is created."""

        from henchman.agents.orchestrator_delegation_ctrl import _StreamState
        from henchman.core.events import AgentEvent, EventType

        ctrl = self._make_ctrl(retries=1)

        call_count = 0

        async def mock_stream(params: Any, state: _StreamState) -> Any:
            nonlocal call_count
            call_count += 1
            state.had_error = True
            state.result_content = "failed"
            yield AgentEvent(type=EventType.ERROR, data="oops", source_agent="x")

        ctrl._stream_delegation = mock_stream  # type: ignore[method-assign]

        params = MagicMock()
        params.target = "coder"
        params.task = "do stuff"
        params.tool_call = MagicMock()
        params.ledger_record = MagicMock()
        params.agent = MagicMock()

        events = []
        async for event in ctrl._run_delegation(params):
            events.append(event)

        # Called twice: initial attempt + 1 retry
        assert call_count == 2
        # Fresh ledger record was created for retry
        ctrl.orchestrator.ledger.add_delegation.assert_called()

    @pytest.mark.asyncio
    async def test_no_retry_when_retries_zero(self) -> None:
        """With max_delegation_retries=0, no retry occurs on error."""

        from henchman.agents.orchestrator_delegation_ctrl import _StreamState
        from henchman.core.events import AgentEvent, EventType

        ctrl = self._make_ctrl(retries=0)

        call_count = 0

        async def mock_stream(params: Any, state: _StreamState) -> Any:
            nonlocal call_count
            call_count += 1
            state.had_error = True
            state.result_content = "failed"
            yield AgentEvent(type=EventType.ERROR, data="oops", source_agent="x")

        ctrl._stream_delegation = mock_stream  # type: ignore[method-assign]

        params = MagicMock()
        params.target = "coder"
        params.task = "do stuff"
        params.tool_call = MagicMock()
        params.ledger_record = MagicMock()
        params.agent = MagicMock()

        events = []
        async for event in ctrl._run_delegation(params):
            events.append(event)

        assert call_count == 1  # No retry


# ---------------------------------------------------------------------------
# AgentPool model override
# ---------------------------------------------------------------------------


class TestAgentPoolModelOverride:
    """Tests for model override in AgentPool.get_agent()."""

    def test_model_override_applied_to_provider(self) -> None:
        """config.model is applied to provider.default_model when available."""
        from unittest.mock import patch

        from henchman.agents.config import AgentConfig
        from henchman.agents.pool import AgentPool

        # Provider with default_model attribute
        mock_provider = MagicMock()
        mock_provider.default_model = "default-model"

        mock_provider_cls = MagicMock(return_value=mock_provider)

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_provider_cls

        config = AgentConfig(
            name="TestAgent",
            role="tester",
            description="test agent",
            system_prompt="You are a test agent.",
            provider="openai",
            model="gpt-4o",
            tools=["read_file"],
        )

        pool = AgentPool(
            configs={"tester": config},
            default_provider=MagicMock(),
            provider_registry=mock_registry,
            parent_tool_registry=MagicMock(),
            event_bus=MagicMock(),
        )
        pool.parent_tool_registry.get.return_value = None
        pool.parent_tool_registry._retry_config = None  # noqa: SLF001
        pool.parent_tool_registry._confirmation_handler = None  # noqa: SLF001

        with patch("henchman.agents.pool.create_scoped_registry") as mock_scoped, \
             patch("henchman.agents.prompts.get_agent_prompt", return_value="prompt"):
            mock_scoped.return_value = MagicMock()
            pool.get_agent("tester")

        assert mock_provider.default_model == "gpt-4o"
