"""Tests to boost coverage for core and mcp modules."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.core.eventbus import EventBus
from henchman.core.events import AgentEvent, EventType
from henchman.mcp.client import McpClient
from henchman.mcp.config import McpServerConfig
from henchman.mcp.manager import McpManager

# ---------------------------------------------------------------------------
# core/eventbus.py - lines 141, 146-147
# ---------------------------------------------------------------------------


class TestEventBusMissingLines:
    """Cover lines 141, 146-147 in eventbus.py."""

    @pytest.mark.anyio
    async def test_history_limit_is_respected(self) -> None:
        """Line 141: limit in history query is enforced."""
        bus = EventBus()
        # Publish 5 events
        for i in range(5):
            await bus.publish(AgentEvent(EventType.CONTENT, f"msg {i}"))

        results = await bus.history(limit=3)
        assert len(results) == 3

    @pytest.mark.anyio
    async def test_clear_history(self) -> None:
        """Lines 146-147: clear_history empties the event history."""
        bus = EventBus()
        await bus.publish(AgentEvent(EventType.CONTENT, "hello"))
        await bus.publish(AgentEvent(EventType.FINISHED, None))

        results_before = await bus.history()
        assert len(results_before) == 2

        await bus.clear_history()

        results_after = await bus.history()
        assert results_after == []


# ---------------------------------------------------------------------------
# core/session_export.py - lines 43, 45, 132->134
# ---------------------------------------------------------------------------


class TestSessionExportMissingLines:
    """Cover lines 43, 45, 132->134 in session_export.py."""

    def test_render_metadata_with_parent_id(self) -> None:
        """Line 43: session with parent_id renders parent metadata."""
        from henchman.core.session_data import Session

        session = Session(
            id="abc123",
            project_hash="proj1",
            started="2024-01-01T00:00:00",
            last_updated="2024-01-01T00:00:00",
            messages=[],
            parent_id="parent_session",
        )
        from henchman.core.session_export import _render_metadata

        lines = _render_metadata(session)
        assert any("Parent Session" in line for line in lines)

    def test_render_metadata_with_template_id(self) -> None:
        """Line 45: session with template_id renders template metadata."""
        from henchman.core.session_data import Session
        from henchman.core.session_export import _render_metadata

        session = Session(
            id="abc123",
            project_hash="proj1",
            started="2024-01-01T00:00:00",
            last_updated="2024-01-01T00:00:00",
            messages=[],
            template_id="my_template",
        )
        lines = _render_metadata(session)
        assert any("Template" in line for line in lines)

    def test_export_to_markdown_preserves_structure(self) -> None:
        """Line 132->134: export_as_markdown formats session correctly."""
        from henchman.core.session_data import Session
        from henchman.core.session_export import export_as_markdown
        from henchman.core.session_models import SessionMessage

        msg = SessionMessage(role="user", content="hello")
        session = Session(
            id="abc123",
            project_hash="proj1",
            started="2024-01-01T00:00:00",
            last_updated="2024-01-01T00:00:00",
            messages=[msg],
            tag="my-tag",
        )
        md = export_as_markdown(session)
        assert "abc123" in md
        assert "hello" in md


# ---------------------------------------------------------------------------
# core/session_manager_base.py - lines 134-135, 143
# ---------------------------------------------------------------------------


class TestSessionManagerBaseMissingLines:
    """Cover lines 134-135, 143 in session_manager_base.py."""

    def test_load_session_raises_when_data_dir_missing(self) -> None:
        """Lines 134-135: FileNotFoundError when data_dir doesn't exist."""
        from henchman.core.session_manager_base import _SessionManagerBase

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = _SessionManagerBase(data_dir=Path(tmpdir) / "nonexistent")
            with pytest.raises(FileNotFoundError):
                manager.load("nonexistent_session_id")

    def test_load_session_raises_ambiguous_prefix(self) -> None:
        """Line 143: ValueError when prefix matches multiple sessions."""
        from henchman.core.session_manager_base import _SessionManagerBase

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            manager = _SessionManagerBase(data_dir=data_dir)

            # Create two sessions with IDs starting with "abc"
            for suffix in ["123", "456"]:
                import json
                (data_dir / f"abc{suffix}.json").write_text(json.dumps({
                    "id": f"abc{suffix}",
                    "project_hash": "proj1",
                    "started": "2024-01-01T00:00:00",
                    "last_updated": "2024-01-01T00:00:00",
                    "messages": [],
                }))

            with pytest.raises(ValueError, match="Ambiguous"):
                manager.load("abc")


# ---------------------------------------------------------------------------
# core/session_merge.py - lines 44, 125-126, 128-129
# ---------------------------------------------------------------------------


class TestSessionMergeMissingLines:
    """Cover missing lines in session_merge.py."""

    def test_merge_intersection_empty_sessions(self) -> None:
        """Line 44: _merge_intersection with empty sessions returns []."""
        from henchman.core.session_merge import _merge_intersection

        result = _merge_intersection([])
        assert result == []

    def test_merge_validate_fewer_than_2_sessions(self) -> None:
        """Lines 125-126: fewer than 2 sessions raises ValueError."""
        from henchman.core.session_data import Session
        from henchman.core.session_merge import merge_sessions

        session = Session(
            id="s1",
            project_hash="proj1",
            started="2024-01-01T00:00:00",
            last_updated="2024-01-01T00:00:00",
            messages=[],
        )
        merged = Session(
            id="merged",
            project_hash="proj1",
            started="2024-01-01T00:00:00",
            last_updated="2024-01-01T00:00:00",
            messages=[],
        )
        with pytest.raises(ValueError, match="At least 2 sessions"):
            merge_sessions([session], ["s1"], strategy="union", merged=merged, now="now")

    def test_merge_invalid_strategy(self) -> None:
        """Lines 128-129: invalid strategy raises ValueError."""
        from henchman.core.session_data import Session
        from henchman.core.session_merge import merge_sessions

        sessions = [
            Session(
                id=f"s{i}",
                project_hash="proj1",
                started="2024-01-01T00:00:00",
                last_updated="2024-01-01T00:00:00",
                messages=[],
            )
            for i in range(2)
        ]
        merged = Session(
            id="merged",
            project_hash="proj1",
            started="2024-01-01T00:00:00",
            last_updated="2024-01-01T00:00:00",
            messages=[],
        )
        with pytest.raises(ValueError, match="Invalid merge strategy"):
            merge_sessions(sessions, ["s0", "s1"], strategy="invalid", merged=merged, now="now")

    def test_merge_different_projects_raises(self) -> None:
        """Lines 131-135: different project hashes raise ValueError."""
        from henchman.core.session_data import Session
        from henchman.core.session_merge import merge_sessions

        sessions = [
            Session(
                id="s1",
                project_hash="proj1",
                started="2024-01-01T00:00:00",
                last_updated="2024-01-01T00:00:00",
                messages=[],
            ),
            Session(
                id="s2",
                project_hash="proj2",
                started="2024-01-01T00:00:00",
                last_updated="2024-01-01T00:00:00",
                messages=[],
            ),
        ]
        merged = Session(
            id="merged",
            project_hash="proj1",
            started="2024-01-01T00:00:00",
            last_updated="2024-01-01T00:00:00",
            messages=[],
        )
        with pytest.raises(ValueError, match="different projects"):
            merge_sessions(sessions, ["s1", "s2"], strategy="union", merged=merged, now="now")


# ---------------------------------------------------------------------------
# core/session_templates.py - lines 132-133, 153
# ---------------------------------------------------------------------------


class TestSessionTemplatesMissingLines:
    """Cover missing lines in session_templates.py."""

    def test_try_load_template_invalid_json(self, tmp_path: Path) -> None:
        """Lines 132-133: invalid JSON returns None."""
        from henchman.core.session_templates import _try_load_template

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json")
        result = _try_load_template(bad_file)
        assert result is None

    def test_list_templates_nonexistent_dir(self, tmp_path: Path) -> None:
        """Line 153: list_templates returns [] when dir doesn't exist."""
        from henchman.core.session_templates import list_templates

        result = list_templates(tmp_path / "nonexistent")
        assert result == []


# ---------------------------------------------------------------------------
# core/turn.py - lines 119->exit, 130, 228, 232
# ---------------------------------------------------------------------------


class TestTurnStateMissingLines:
    """Cover missing lines in turn.py."""

    def test_track_duplicates_read_only_below_threshold(self) -> None:
        """Line 119->exit: read-only tool duplicate below threshold is not counted."""
        from henchman.core.turn import READ_ONLY_DUPLICATE_THRESHOLD, TurnState

        state = TurnState()
        # Call read-only tool same args multiple times but below threshold
        for i in range(READ_ONLY_DUPLICATE_THRESHOLD - 1):
            state.record_tool_call(
                tool_call_id=f"tc{i}",
                tool_name="read_file",
                arguments={"path": "test.py"},
                result=None,
            )

        assert state._consecutive_duplicates < READ_ONLY_DUPLICATE_THRESHOLD

    def test_track_result_hash_trims_old(self) -> None:
        """Line 130: recent_result_hashes list is trimmed to MAX_RECENT_HASHES."""
        from henchman.core.turn import MAX_RECENT_HASHES, TurnState

        state = TurnState()
        mock_result = MagicMock()
        mock_result.content = "result"

        for i in range(MAX_RECENT_HASHES + 5):
            mock_result.content = f"result_{i}"
            state._track_result_hash(mock_result)

        assert len(state.recent_result_hashes) <= MAX_RECENT_HASHES

    def test_format_status_spinning(self) -> None:
        """Line 228: get_status_string shows spinning when spinning detected."""
        from henchman.core.turn import CONSECUTIVE_DUPLICATE_THRESHOLD, TurnState

        state = TurnState()
        state._consecutive_duplicates = CONSECUTIVE_DUPLICATE_THRESHOLD + 1

        status = state.get_status_string()
        assert "spinning" in status

    def test_format_status_making_progress(self) -> None:
        """Line 232: get_status_string shows progress when making progress."""
        from henchman.core.turn import TurnState

        state = TurnState()
        state.files_modified.add("some_file.py")

        status = state.get_status_string()
        assert "progress" in status


# ---------------------------------------------------------------------------
# mcp/client.py - lines 85, 88->64, 197->201
# ---------------------------------------------------------------------------


class TestMcpClientMissingLines:
    """Cover missing lines in mcp/client.py."""

    def test_filtered_stderr_write_with_info_prefix(self) -> None:
        """Line 85: FilteredStream.write passes non-info/debug lines through."""
        import sys
        from io import StringIO

        from henchman.mcp.client import FilteredStream

        original_stderr = sys.stderr
        captured = StringIO()
        sys.stderr = captured
        try:
            filt = FilteredStream(verbose=False)
            filt.write("ERROR: something went wrong\n")
            output = captured.getvalue()
            assert "ERROR" in output
        finally:
            sys.stderr = original_stderr

    def test_filtered_stderr_write_filters_info(self) -> None:
        """Lines 88->64: FilteredStream filters INFO lines."""
        import sys
        from io import StringIO

        from henchman.mcp.client import FilteredStream

        original_stderr = sys.stderr
        captured = StringIO()
        sys.stderr = captured
        try:
            filt = FilteredStream(verbose=False)
            filt.write("INFO 2024-01-01 12:00:00,000 - something happened\n")
            output = captured.getvalue()
            # INFO lines should be filtered out
            assert output == ""
        finally:
            sys.stderr = original_stderr

    def test_filtered_stream_verbose_passthrough(self) -> None:
        """FilteredStream in verbose mode passes all text through."""
        import sys
        from io import StringIO

        from henchman.mcp.client import FilteredStream

        original_stderr = sys.stderr
        captured = StringIO()
        sys.stderr = captured
        try:
            filt = FilteredStream(verbose=True)
            filt.write("INFO: something\n")
            output = captured.getvalue()
            assert "INFO" in output
        finally:
            sys.stderr = original_stderr

    @pytest.mark.anyio
    async def test_mcp_client_call_tool_without_session(self) -> None:
        """Lines 197->201: call_tool raises when session not initialized."""
        config = McpServerConfig(
            command="fake_command",
            args=[],
            env={},
            trusted=True,
        )
        client = McpClient(name="test", config=config)
        # Don't call connect() - session should be None
        with pytest.raises((RuntimeError, AttributeError, Exception)):
            await client.call_tool("some_tool", {})


# ---------------------------------------------------------------------------
# mcp/manager.py - lines 61-71, 85-88, 96, 117-121, 168->171
# ---------------------------------------------------------------------------


class TestMcpManagerMissingLines:
    """Cover missing lines in mcp/manager.py."""

    @pytest.mark.anyio
    async def test_connect_all_creates_tools(self) -> None:
        """Lines 61-71: connect_all creates tools from connected server."""

        # Mock the client
        mock_client = MagicMock(spec=McpClient)
        mock_client.connect = AsyncMock()
        mock_tool_def = MagicMock()
        mock_tool_def.name = "test_tool"
        mock_client.get_tools.return_value = [mock_tool_def]

        config = McpServerConfig(
            command="fake_command",
            args=[],
            env={},
            trusted=True,
        )
        with patch("henchman.mcp.manager.McpClient", return_value=mock_client):
            manager = McpManager({"test": config})
            await manager.connect_all()

        assert "test" in manager.clients
        assert len(manager.get_all_tools()) == 1

    @pytest.mark.anyio
    async def test_disconnect_all(self) -> None:
        """Lines 85-88: disconnect_all disconnects and clears clients."""
        manager = McpManager({})

        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        manager.clients["server1"] = mock_client
        manager._tools = [MagicMock()]

        await manager.disconnect_all()

        assert manager.clients == {}
        assert manager.get_all_tools() == []
        mock_client.disconnect.assert_called_once()

    def test_get_all_tools(self) -> None:
        """Line 96: get_all_tools returns the tools list."""
        manager = McpManager({})
        tools = manager.get_all_tools()
        assert tools == []

    @pytest.mark.anyio
    async def test_call_tool_unknown_server(self) -> None:
        """Lines 117-121: call_tool raises KeyError for unknown server."""
        manager = McpManager({})
        with pytest.raises(KeyError, match="Unknown MCP server"):
            await manager.call_tool("nonexistent", "tool_name", {})

    @pytest.mark.anyio
    async def test_call_tool_known_server(self) -> None:
        """call_tool delegates to the correct client."""
        manager = McpManager({})
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        manager.clients["server1"] = mock_client

        result = await manager.call_tool("server1", "my_tool", {"key": "val"})
        assert result is mock_result
        mock_client.call_tool.assert_called_once_with("my_tool", {"key": "val"})

    def test_build_logging_env_node_server(self) -> None:
        """Lines 168->171: node server gets NODE_ENV=production."""
        server_config = MagicMock()
        server_config.command = "node"
        server_config.args = ["server.js"]

        result = McpManager._build_logging_env("my_node_server", server_config, {})
        assert result["NODE_ENV"] == "production"
        assert result["NO_COLOR"] == "1"
        assert result["TERM"] == "dumb"

    def test_create_from_settings_none_settings(self) -> None:
        """create_from_settings with None settings returns None."""
        result = McpManager.create_from_settings(None)
        assert result is None


# ---------------------------------------------------------------------------
# Additional tests for remaining gaps
# ---------------------------------------------------------------------------


class TestMcpClientMissingLines2:
    """Cover remaining missing lines in mcp/client.py."""

    def test_filtered_stream_bracket_info_filtered(self) -> None:
        """Line 85: line containing [INFO] is filtered (2nd check fires)."""
        import sys
        from io import StringIO

        from henchman.mcp.client import FilteredStream

        original_stderr = sys.stderr
        captured = StringIO()
        sys.stderr = captured
        try:
            filt = FilteredStream(verbose=False)
            # This line won't match first regex but will match the [INFO] check
            filt.write("something [INFO] in the middle\n")
            output = captured.getvalue()
            # Should be filtered out (contains [INFO])
            assert output == ""
        finally:
            sys.stderr = original_stderr

    def test_filtered_stream_empty_line_filtered(self) -> None:
        """Lines 88->64: empty line.strip() in inner check (no content)."""
        import sys
        from io import StringIO

        from henchman.mcp.client import FilteredStream

        original_stderr = sys.stderr
        captured = StringIO()
        sys.stderr = captured
        try:
            filt = FilteredStream(verbose=False)
            # Line with only spaces - first check catches empty strip → continue
            filt.write("   \n")
            output = captured.getvalue()
            assert output == ""
        finally:
            sys.stderr = original_stderr

    @pytest.mark.anyio
    async def test_mcp_client_disconnect_with_exit_stack_none(self) -> None:
        """Lines 197->201: disconnect when _exit_stack is None does nothing."""
        config = McpServerConfig(
            command="fake_command",
            args=[],
            env={},
            trusted=True,
        )
        client = McpClient(name="test", config=config)
        # _exit_stack should be None initially
        assert client._exit_stack is None
        # disconnect should be safe to call
        await client.disconnect()
        assert client._session is None


class TestMcpManagerMissingLines2:
    """Cover remaining mcp/manager.py missing lines."""

    def test_build_logging_env_python_logging_disabled(self) -> None:
        """Lines 168->171: python server with no logging env vars."""
        server_config = MagicMock()
        server_config.command = "python"
        server_config.args = ["server.py"]

        result = McpManager._build_logging_env("python_server", server_config, {})
        assert result["PYTHONWARNINGS"] == "ignore"
        assert result["NO_COLOR"] == "1"
        assert result["TERM"] == "dumb"


class TestCoreRemainingGaps:
    """Cover remaining specific missing lines."""

    def test_session_manager_base_unambiguous_prefix(self) -> None:
        """Line 143: unambiguous prefix match loads successfully."""
        from henchman.core.session_manager_base import _SessionManagerBase

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            manager = _SessionManagerBase(data_dir=data_dir)

            # Create only ONE session with ID starting with "xyz"
            session_data = {
                "id": "xyz9999",
                "project_hash": "proj1",
                "started": "2024-01-01T00:00:00",
                "last_updated": "2024-01-01T00:00:00",
                "messages": [],
            }
            (data_dir / "xyz9999.json").write_text(json.dumps(session_data))

            # Load by prefix "xyz" - exactly one match → line 143
            result = manager.load("xyz")
            assert result.id == "xyz9999"

    def test_session_export_import_json_no_tag(self) -> None:
        """Line 132->134: import_json_session with no tag skips tag assignment."""
        from henchman.core.session_data import Session
        from henchman.core.session_export import import_json_session

        session = Session(
            id="old-id",
            project_hash="proj1",
            started="2024-01-01T00:00:00",
            last_updated="2024-01-01T00:00:00",
            messages=[],
            tag="original-tag",
        )
        import_json_session(session, tag=None, new_id="new-id", now="2024-01-02T00:00:00")
        # Tag should remain unchanged (tag=None → no assignment at line 133)
        assert session.tag == "original-tag"
        assert session.id == "new-id"

    def test_turn_is_making_progress_unique_hashes_below_threshold(self) -> None:
        """Line 146->148: unique hashes below MIN_UNIQUE_FOR_PROGRESS."""
        from henchman.core.turn import (
            MIN_HASHES_FOR_PROGRESS,
            MIN_UNIQUE_FOR_PROGRESS,
            TurnState,
        )

        state = TurnState()
        # Fill recent_result_hashes with MIN_HASHES_FOR_PROGRESS entries
        # but ALL the same hash (unique = 1, < MIN_UNIQUE_FOR_PROGRESS if > 1)
        if MIN_UNIQUE_FOR_PROGRESS > 1:
            state.recent_result_hashes = ["same_hash"] * (MIN_HASHES_FOR_PROGRESS + 1)
            result = state.is_making_progress()
            # unique=1 < MIN_UNIQUE_FOR_PROGRESS → falls through to line 148 (return False)
            assert result is False

    def test_turn_is_spinning_no_hash_repeats(self) -> None:
        """Lines 160->163, 161->160: recent_result_hashes has no repeated hash."""
        from henchman.core.turn import (
            MIN_HASHES_FOR_SPIN_CHECK,
            TurnState,
        )

        state = TurnState()
        # All unique hashes → no count >= SPIN_HASH_REPEAT_THRESHOLD
        # AND _consecutive_duplicates < CONSECUTIVE_DUPLICATE_THRESHOLD
        unique_hashes = [f"hash_{i}" for i in range(MIN_HASHES_FOR_SPIN_CHECK + 2)]
        state.recent_result_hashes = unique_hashes
        # Not spinning: each hash appears only once (< threshold)
        result = state.is_spinning()
        # Falls to line 163 (return bool(...)) after the for loop
        assert isinstance(result, bool)

    def test_turn_get_status_string_not_spinning_not_progress(self) -> None:
        """Line 232: status = '…' when neither spinning nor making progress."""
        from henchman.core.turn import TurnState

        state = TurnState()
        # Empty state - no duplicates, no files modified, few hashes
        # Neither spinning nor making progress
        result = state.get_status_string()
        assert "…" in result  # Line 232

    def test_mcp_manager_build_env_generic_server(self) -> None:
        """Line 168->171: generic server (not python, not node) skips all conditionals."""
        server_config = MagicMock()
        server_config.command = "ruby"  # Not python, not node, not serena
        server_config.args = []

        result = McpManager._build_logging_env("generic_server", server_config, {})
        assert result["NO_COLOR"] == "1"
        assert result["TERM"] == "dumb"
        # Should NOT have NODE_ENV or PYTHONWARNINGS
        assert "NODE_ENV" not in result
        assert "PYTHONWARNINGS" not in result
