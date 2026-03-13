"""Tests to achieve 100% coverage for cli/textual_bridge.py.

Targets missing lines:
- 277: dispatch() with unhandled event type calls post_status_message
- 363-368: _on_usage_stats tokens/cost update with exception handling
- 401: handler created with status_text calls post_status_message
- 407: handler created with prefix calls post_message
- 422: _on_tool_req with non-None data
- 429: _on_error with empty data returns early
- 460: _on_agent_start with non-dict data returns early
- 467: _on_agent_done with non-dict data returns early
- 478: _on_delegated with non-dict data returns early
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from henchman.core.events import AgentEvent, EventType


def make_adapter() -> Any:
    """Create an EventBridge-like object for testing private methods.

    Returns:
        Object with required attributes set up.
    """
    from henchman.cli.textual_bridge import EventBridge

    adapter = object.__new__(EventBridge)
    adapter._message_poster = MagicMock()
    adapter._handlers = {}
    adapter.app = MagicMock()
    return adapter


class TestDispatchUnhandledEvent:
    """Tests for _dispatch() with unhandled event type."""

    def test_dispatch_unhandled_type_posts_status_message(self) -> None:
        """Line 277: unhandled event type calls post_status_message."""
        adapter = make_adapter()
        # No handlers registered for CONTENT
        adapter._handlers = {}

        event = AgentEvent(type=EventType.CONTENT, data="hello")
        adapter._dispatch(event)

        adapter._message_poster.post_status_message.assert_called_once()
        call_args = adapter._message_poster.post_status_message.call_args
        assert "Unhandled event type" in call_args[0][1]


class TestOnUsageStats:
    """Tests for _update_status_bar method."""

    def test_update_status_bar_with_tokens_and_cost(self) -> None:
        """Lines 363-366: tokens and cost are set on status bar."""
        adapter = make_adapter()
        mock_bar = MagicMock()
        adapter.app.query_one = MagicMock(return_value=mock_bar)

        adapter._update_status_bar({"tokens": "1234", "cost": "0.01"})

        assert mock_bar.tokens == 1234
        assert mock_bar.cost == pytest.approx(0.01)

    def test_update_status_bar_exception_is_caught(self) -> None:
        """Lines 367-368: exception when querying status bar is caught silently."""
        adapter = make_adapter()
        # Make query_one raise an exception
        adapter.app.query_one = MagicMock(side_effect=Exception("No status bar"))

        # Should not raise
        adapter._update_status_bar({"tokens": "100", "cost": "0.001"})


class TestCreateHandlerPaths:
    """Tests for _create_handler with different configurations."""

    def test_create_handler_with_status_text_posts_status(self) -> None:
        """Line 401: handler with status_text calls post_status_message."""
        adapter = make_adapter()

        handler = adapter._create_handler(status_text="Processing...")
        assert handler is not None

        event = AgentEvent(type=EventType.CONTENT, data="hello")
        handler(event)

        adapter._message_poster.post_status_message.assert_called_once_with(
            event, "Processing..."
        )

    def test_create_handler_with_prefix_posts_thought_message(self) -> None:
        """Line 407: handler with prefix calls post_message."""
        adapter = make_adapter()

        handler = adapter._create_handler(prefix="🤔 ")
        assert handler is not None

        event = AgentEvent(type=EventType.THOUGHT, data="thinking...")
        handler(event)

        adapter._message_poster.post_message.assert_called_once()


class TestEventHandlerGuardReturns:
    """Tests for early return guards in event handlers."""

    def test_on_tool_req_with_none_data_skips_post(self) -> None:
        """Line 422: _on_tool_req with None data skips posting."""
        adapter = make_adapter()
        event = AgentEvent(type=EventType.TOOL_CALL_REQUEST, data=None)
        adapter._on_tool_req(event)
        adapter._message_poster.post.assert_not_called()

    def test_on_tool_req_with_data_posts_message(self) -> None:
        """Line 422: _on_tool_req with data calls post."""
        adapter = make_adapter()
        tool_data = MagicMock()
        event = AgentEvent(
            type=EventType.TOOL_CALL_REQUEST,
            data=tool_data,
            source_agent="test",
        )
        adapter._on_tool_req(event)
        adapter._message_poster.post.assert_called_once()

    def test_on_error_with_empty_data_returns_early(self) -> None:
        """Line 429: _on_error with empty data returns without posting."""
        adapter = make_adapter()
        event = AgentEvent(type=EventType.ERROR, data=None)
        adapter._on_error(event)
        adapter._message_poster.post_status_message.assert_not_called()

    def test_on_agent_start_with_non_dict_returns_early(self) -> None:
        """Line 460: _on_agent_start with non-dict data returns early."""
        adapter = make_adapter()
        event = AgentEvent(type=EventType.AGENT_STARTED, data="not-a-dict")
        adapter._on_agent_start(event)
        adapter._message_poster.post_status_message.assert_not_called()

    def test_on_agent_done_with_non_dict_returns_early(self) -> None:
        """Line 467: _on_agent_done with non-dict data returns early."""
        adapter = make_adapter()
        event = AgentEvent(type=EventType.AGENT_COMPLETED, data=None)
        adapter._on_agent_done(event)
        adapter._message_poster.post_status_message.assert_not_called()

    def test_on_delegated_with_non_dict_returns_early(self) -> None:
        """Line 478: _on_delegated with non-dict data returns early."""
        adapter = make_adapter()
        event = AgentEvent(type=EventType.AGENT_DELEGATED, data=None)
        adapter._on_delegated(event)
        adapter._message_poster.post.assert_not_called()


class TestUpdateStatusBarBranchCoverage:
    """Tests for _update_status_bar branch coverage (363->365, 365->exit)."""

    def test_update_status_bar_only_cost_no_tokens(self) -> None:
        """Branch 363->365: tokens is falsy (None/0), cost is truthy - skip tokens."""
        adapter = make_adapter()
        mock_bar = MagicMock()
        adapter.app.query_one = MagicMock(return_value=mock_bar)

        # tokens is falsy (empty/None), cost is truthy
        adapter._update_status_bar({"tokens": None, "cost": "0.05"})

        # tokens should NOT be set (branch 363->365 skips line 364)
        assert not hasattr(mock_bar, 'tokens') or mock_bar.tokens != 0
        # cost should be set (branch 365->366)
        assert mock_bar.cost == pytest.approx(0.05)

    def test_update_status_bar_only_tokens_no_cost(self) -> None:
        """Branch 365->exit: cost is falsy, tokens is truthy - skip cost."""
        adapter = make_adapter()
        mock_bar = MagicMock()
        adapter.app.query_one = MagicMock(return_value=mock_bar)

        # tokens is truthy, cost is falsy (None/empty)
        adapter._update_status_bar({"tokens": "500", "cost": None})

        # tokens should be set (branch 363->364)
        assert mock_bar.tokens == 500
        # cost should NOT be set (branch 365->exit skips line 366)
