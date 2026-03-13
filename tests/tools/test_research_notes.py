"""Tests for the research_notes tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.tools.base import ToolKind
from henchman.tools.builtins.research_notes import (
    ResearchNotesTool,
    ResearchNotesParams,
    _action_append,
    _action_list,
    _action_read,
    _action_search,
    _action_write,
    _execute_research_notes,
    _get_notes_dir,
    _load_note,
    _note_path,
    _save_note,
)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestGetNotesDir:
    """Tests for _get_notes_dir."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Creates the notes directory if it doesn't exist."""
        nd = tmp_path / "notes"
        result = _get_notes_dir(nd)
        assert result.exists()
        assert result.is_dir()

    def test_returns_path(self, tmp_path: Path) -> None:
        """Returns the notes directory path."""
        nd = tmp_path / "notes"
        result = _get_notes_dir(nd)
        assert result == nd


class TestNotePath:
    """Tests for _note_path."""

    def test_safe_tag(self, tmp_path: Path) -> None:
        """Returns JSON file path for a simple tag."""
        path = _note_path("my-note", tmp_path)
        assert path.name == "my-note.json"

    def test_sanitizes_unsafe_chars(self, tmp_path: Path) -> None:
        """Replaces unsafe characters in tag."""
        path = _note_path("tag with spaces/slash", tmp_path)
        assert "/" not in path.name
        assert " " not in path.name


class TestSaveLoadNote:
    """Tests for _save_note and _load_note."""

    def test_round_trip(self, tmp_path: Path) -> None:
        """Save then load returns the same content."""
        _save_note("test-tag", "hello world", tmp_path)
        loaded = _load_note("test-tag", tmp_path)
        assert loaded["content"] == "hello world"
        assert loaded["tag"] == "test-tag"

    def test_load_missing_returns_empty(self, tmp_path: Path) -> None:
        """Loading a missing note returns empty dict."""
        loaded = _load_note("nonexistent", tmp_path)
        assert loaded == {}

    def test_load_corrupted_returns_empty(self, tmp_path: Path) -> None:
        """Loading corrupted JSON returns empty dict."""
        bad = tmp_path / "bad.json"
        bad.write_text("not json {{{")
        # Fake a note file so _note_path would match
        note_p = _note_path("bad", tmp_path)
        note_p.write_text("not json {{{")
        loaded = _load_note("bad", tmp_path)
        assert loaded == {}

    def test_updated_at_present(self, tmp_path: Path) -> None:
        """Saved note has an updated_at field."""
        _save_note("ts-tag", "content", tmp_path)
        loaded = _load_note("ts-tag", tmp_path)
        assert "updated_at" in loaded


class TestActionWrite:
    """Tests for _action_write."""

    def test_writes_note(self, tmp_path: Path) -> None:
        """Writes new note and reports char count."""
        result = _action_write("w1", "some content", tmp_path)
        assert result.success is True
        assert "w1" in result.content

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        """Overwrites existing note."""
        _action_write("w1", "old", tmp_path)
        _action_write("w1", "new", tmp_path)
        loaded = _load_note("w1", tmp_path)
        assert loaded["content"] == "new"


class TestActionAppend:
    """Tests for _action_append."""

    def test_appends_to_existing(self, tmp_path: Path) -> None:
        """Appends content to an existing note."""
        _action_write("a1", "first line", tmp_path)
        _action_append("a1", "second line", tmp_path)
        loaded = _load_note("a1", tmp_path)
        assert "first line" in loaded["content"]
        assert "second line" in loaded["content"]

    def test_creates_if_absent(self, tmp_path: Path) -> None:
        """Creates note if it doesn't exist yet."""
        result = _action_append("new", "content", tmp_path)
        assert result.success is True
        loaded = _load_note("new", tmp_path)
        assert loaded["content"] == "content"


class TestActionRead:
    """Tests for _action_read."""

    def test_reads_existing(self, tmp_path: Path) -> None:
        """Reads content of existing note."""
        _action_write("r1", "my content", tmp_path)
        result = _action_read("r1", tmp_path)
        assert result.success is True
        assert "my content" in result.content

    def test_missing_note_returns_error(self, tmp_path: Path) -> None:
        """Returns error for missing note."""
        result = _action_read("ghost", tmp_path)
        assert result.success is False
        assert "not found" in result.content.lower()


class TestActionList:
    """Tests for _action_list."""

    def test_empty_notes_dir(self, tmp_path: Path) -> None:
        """Returns no-notes message for empty directory."""
        result = _action_list(tmp_path)
        assert result.success is True
        assert "No notes" in result.content

    def test_lists_notes(self, tmp_path: Path) -> None:
        """Lists all notes with tags."""
        _action_write("note-a", "content a", tmp_path)
        _action_write("note-b", "content b", tmp_path)
        result = _action_list(tmp_path)
        assert result.success is True
        assert "note-a" in result.content
        assert "note-b" in result.content


class TestActionSearch:
    """Tests for _action_search."""

    def test_finds_matching_note(self, tmp_path: Path) -> None:
        """Finds notes containing the query."""
        _action_write("s1", "python is great", tmp_path)
        _action_write("s2", "java is okay", tmp_path)
        result = _action_search("python", tmp_path)
        assert result.success is True
        assert "s1" in result.content
        assert "s2" not in result.content

    def test_no_matches(self, tmp_path: Path) -> None:
        """Returns no-matches message when nothing found."""
        _action_write("s1", "hello world", tmp_path)
        result = _action_search("xyz123", tmp_path)
        assert result.success is True
        assert "No notes" in result.content


class TestExecuteResearchNotes:
    """Tests for _execute_research_notes."""

    def test_invalid_action(self, tmp_path: Path) -> None:
        """Returns error for invalid action."""
        params = ResearchNotesParams("delete", "", "", "", tmp_path)
        result = _execute_research_notes(params)
        assert result.success is False
        assert "invalid action" in result.content.lower()

    def test_write_requires_tag(self, tmp_path: Path) -> None:
        """Write without tag returns error."""
        params = ResearchNotesParams("write", "", "content", "", tmp_path)
        result = _execute_research_notes(params)
        assert result.success is False

    def test_write_requires_content(self, tmp_path: Path) -> None:
        """Write without content returns error."""
        params = ResearchNotesParams("write", "tag", "", "", tmp_path)
        result = _execute_research_notes(params)
        assert result.success is False

    def test_append_requires_tag(self, tmp_path: Path) -> None:
        """Append without tag returns error."""
        params = ResearchNotesParams("append", "", "content", "", tmp_path)
        result = _execute_research_notes(params)
        assert result.success is False

    def test_append_requires_content(self, tmp_path: Path) -> None:
        """Append without content returns error."""
        params = ResearchNotesParams("append", "tag", "", "", tmp_path)
        result = _execute_research_notes(params)
        assert result.success is False

    def test_search_requires_query(self, tmp_path: Path) -> None:
        """Search without query returns error."""
        params = ResearchNotesParams("search", "", "", "", tmp_path)
        result = _execute_research_notes(params)
        assert result.success is False

    def test_list_action(self, tmp_path: Path) -> None:
        """List action works without tag or content."""
        params = ResearchNotesParams("list", "", "", "", tmp_path)
        result = _execute_research_notes(params)
        assert result.success is True

    def test_full_write_read_cycle(self, tmp_path: Path) -> None:
        """Write then read returns same content."""
        params_write = ResearchNotesParams("write", "cycle", "hello", "", tmp_path)
        _execute_research_notes(params_write)
        params_read = ResearchNotesParams("read", "cycle", "", "", tmp_path)
        result = _execute_research_notes(params_read)
        assert "hello" in result.content


# ---------------------------------------------------------------------------
# Tool class tests
# ---------------------------------------------------------------------------


class TestResearchNotesTool:
    """Tests for the ResearchNotesTool class."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = ResearchNotesTool()
        assert tool.name == "research_notes"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = ResearchNotesTool()
        assert "note" in tool.description.lower()

    def test_kind_is_write(self) -> None:
        """Tool is WRITE kind."""
        tool = ResearchNotesTool()
        assert tool.kind == ToolKind.WRITE

    def test_parameters_schema(self) -> None:
        """Parameters schema has required 'action' field."""
        tool = ResearchNotesTool()
        params = tool.parameters
        assert "action" in params["properties"]
        assert "action" in params["required"]

    def test_needs_confirmation_write(self) -> None:
        """Write action requires confirmation."""
        tool = ResearchNotesTool()
        req = tool.needs_confirmation({"action": "write"})
        assert req is not None

    def test_needs_confirmation_append(self) -> None:
        """Append action requires confirmation."""
        tool = ResearchNotesTool()
        req = tool.needs_confirmation({"action": "append"})
        assert req is not None

    def test_no_confirmation_read(self) -> None:
        """Read action does not require confirmation."""
        tool = ResearchNotesTool()
        req = tool.needs_confirmation({"action": "read"})
        assert req is None

    def test_no_confirmation_list(self) -> None:
        """List action does not require confirmation."""
        tool = ResearchNotesTool()
        req = tool.needs_confirmation({"action": "list"})
        assert req is None

    def test_no_confirmation_search(self) -> None:
        """Search action does not require confirmation."""
        tool = ResearchNotesTool()
        req = tool.needs_confirmation({"action": "search"})
        assert req is None

    async def test_execute_list(self, tmp_path: Path) -> None:
        """Execute list action via the tool."""
        tool = ResearchNotesTool()
        from unittest.mock import patch
        with patch(
            "henchman.tools.builtins.research_notes._execute_research_notes",
        ) as mock_exec:
            from henchman.tools.base import ToolResult
            mock_exec.return_value = ToolResult(content="No notes", success=True)
            result = await tool.execute(action="list")
            assert result.success is True

    async def test_execute_ignores_extra_kwargs(self) -> None:
        """Extra kwargs are silently ignored."""
        tool = ResearchNotesTool()
        from unittest.mock import patch
        with patch(
            "henchman.tools.builtins.research_notes._execute_research_notes",
        ) as mock_exec:
            from henchman.tools.base import ToolResult
            mock_exec.return_value = ToolResult(content="ok", success=True)
            result = await tool.execute(action="list", unknown_param="ignored")
            assert result.success is True
