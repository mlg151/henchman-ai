"""Tests for session command helper functions and data classes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.commands.session import (
    AttributeDisplayInfo,
    BranchExecutor,
    CommandOperationContext,
    DisplayInfo,
    ExportExecutor,
    ImportExecutor,
    MergeExecutor,
    SessionCommand,
    SessionListParams,
    TemplateCreateExecutor,
    TemplateDeleteExecutor,
    TemplateListExecutor,
    TemplateSaveExecutor,
    _format_basic_session_info,
    _format_session_field,
    _format_tag_display,
    _get_manager,
    _validate_args,
    display_basic_session_info,
    display_enhanced_session_info,
    display_session_entry,
    display_sessions_list,
    format_session_details,
    format_session_display,
)

# ---------------------------------------------------------------------------
# CommandOperationContext tests
# ---------------------------------------------------------------------------


class TestCommandOperationContext:
    """Tests for CommandOperationContext dataclass."""

    def _make_ctx(self, args: list[str]) -> CommandOperationContext:
        """Create a test CommandOperationContext."""
        console = MagicMock()
        return CommandOperationContext(console=console, args=args)

    def test_print_success(self) -> None:
        """Test print_success outputs green tick message."""
        ctx = self._make_ctx([])
        ctx.print_success("it worked")
        ctx.console.print.assert_called_once_with("[green]✓[/] it worked")

    def test_print_error(self) -> None:
        """Test print_error outputs red error message."""
        ctx = self._make_ctx([])
        ctx.print_error("something failed")
        ctx.console.print.assert_called_once_with("[red]Error: something failed[/]")

    def test_print_info(self) -> None:
        """Test print_info outputs dim message."""
        ctx = self._make_ctx([])
        ctx.print_info("some info")
        ctx.console.print.assert_called_once_with("[dim]some info[/]")

    def test_print_usage(self) -> None:
        """Test print_usage outputs yellow usage message."""
        ctx = self._make_ctx([])
        ctx.print_usage("/test <arg>")
        ctx.console.print.assert_called_once_with("[yellow]Usage: /test <arg>[/]")

    def test_get_arg_existing(self) -> None:
        """Test get_arg returns value at valid index."""
        ctx = self._make_ctx(["a", "b", "c"])
        assert ctx.get_arg(0) == "a"
        assert ctx.get_arg(1) == "b"
        assert ctx.get_arg(2) == "c"

    def test_get_arg_out_of_bounds(self) -> None:
        """Test get_arg returns default for out-of-bounds index."""
        ctx = self._make_ctx(["a"])
        assert ctx.get_arg(5) is None
        assert ctx.get_arg(5, "default") == "default"

    def test_get_arg_or_empty(self) -> None:
        """Test get_arg_or_empty returns empty string when out of bounds."""
        ctx = self._make_ctx(["a"])
        assert ctx.get_arg_or_empty(0) == "a"
        assert ctx.get_arg_or_empty(5) == ""

    def test_has_min_args_true(self) -> None:
        """Test has_min_args returns True when args >= min."""
        ctx = self._make_ctx(["a", "b", "c"])
        assert ctx.has_min_args(3) is True
        assert ctx.has_min_args(2) is True

    def test_has_min_args_false(self) -> None:
        """Test has_min_args returns False when args < min."""
        ctx = self._make_ctx(["a"])
        assert ctx.has_min_args(2) is False


# ---------------------------------------------------------------------------
# DisplayInfo tests
# ---------------------------------------------------------------------------


class TestDisplayInfo:
    """Tests for DisplayInfo dataclass."""

    def test_format_with_condition_and_value(self) -> None:
        """Test format_optional_info returns formatted string when condition and value set."""
        info = DisplayInfo(condition="val", icon="→", label="from:", value="abc123", max_id_len=4)
        result = info.format_optional_info()
        assert "abc1" in result  # truncated
        assert "→" in result

    def test_format_no_condition(self) -> None:
        """Test format_optional_info returns empty string when no condition."""
        info = DisplayInfo(condition=None, icon="→", label="from:", value="abc", max_id_len=4)
        result = info.format_optional_info()
        assert result == ""

    def test_format_no_value(self) -> None:
        """Test format_optional_info returns empty string when no value."""
        info = DisplayInfo(condition="yes", icon="→", label="from:", value=None, max_id_len=4)
        result = info.format_optional_info()
        assert result == ""

    def test_format_zero_max_id_len(self) -> None:
        """Test format_optional_info with max_id_len=0 does not truncate."""
        info = DisplayInfo(
            condition="val", icon="→", label="from:", value="longid", max_id_len=0
        )
        result = info.format_optional_info()
        assert "longid" in result


class TestAttributeDisplayInfo:
    """Tests for AttributeDisplayInfo dataclass."""

    def test_format_with_condition(self) -> None:
        """Test format_attribute_info returns string when condition is set."""
        attr = AttributeDisplayInfo(condition="abc123", icon="↳", label="branch:", max_id_len=4)
        result = attr.format_attribute_info()
        assert "↳" in result

    def test_format_no_condition(self) -> None:
        """Test format_attribute_info returns empty string when no condition."""
        attr = AttributeDisplayInfo(condition=None, icon="↳", label="branch:", max_id_len=4)
        result = attr.format_attribute_info()
        assert result == ""


# ---------------------------------------------------------------------------
# Module-level helper function tests
# ---------------------------------------------------------------------------


class TestModuleLevelHelpers:
    """Tests for module-level helper functions."""

    def _make_meta(self, tag: str | None = None, session_id: str = "abc123", count: int = 5, updated: str = "2025-01-01T00:00:00") -> MagicMock:
        """Create a mock session metadata."""
        meta = MagicMock()
        meta.id = session_id
        meta.tag = tag
        meta.message_count = count
        meta.last_updated = updated
        return meta

    def test_format_tag_display_with_tag(self) -> None:
        """Test _format_tag_display uses tag when available."""
        meta = self._make_meta(tag="my-tag")
        result = _format_tag_display(meta, 8)
        assert "my-tag" in result
        assert "[cyan]" in result

    def test_format_tag_display_without_tag(self) -> None:
        """Test _format_tag_display uses truncated ID when no tag."""
        meta = self._make_meta(tag=None, session_id="abcdefghij")
        result = _format_tag_display(meta, 4)
        assert "abcd" in result

    def test_format_basic_session_info(self) -> None:
        """Test _format_basic_session_info returns formatted string."""
        meta = self._make_meta(tag="t1", updated="2025-01-01T00:00:00")
        result = _format_basic_session_info("[cyan]t1[/]", meta, 10)
        assert "2025-01-01" in result
        assert "5 messages" in result

    def test_format_session_field_unknown_key(self) -> None:
        """Test _format_session_field returns empty for unknown key."""
        session = MagicMock()
        result = _format_session_field(session, "unknown_key", 8)
        assert result == ""

    def test_format_session_field_parent_id(self) -> None:
        """Test _format_session_field handles parent_id."""
        session = MagicMock()
        session.parent_id = "parent123"
        result = _format_session_field(session, "parent_id", 4)
        assert "↳" in result or "pare" in result

    def test_format_session_field_no_parent(self) -> None:
        """Test _format_session_field returns empty when parent_id is None."""
        session = MagicMock()
        session.parent_id = None
        result = _format_session_field(session, "parent_id", 4)
        assert result == ""

    def test_validate_args_passes(self) -> None:
        """Test _validate_args returns True when enough args."""
        ctx = CommandOperationContext(console=MagicMock(), args=["a", "b", "c"])
        result = _validate_args(ctx, 2, "/test <arg>")
        assert result is True

    def test_validate_args_fails(self) -> None:
        """Test _validate_args returns False and prints usage when not enough args."""
        ctx = CommandOperationContext(console=MagicMock(), args=["a"])
        result = _validate_args(ctx, 3, "/test <arg1> <arg2>")
        assert result is False
        ctx.console.print.assert_called()

    def test_get_manager_returns_manager(self) -> None:
        """Test _get_manager returns the session manager."""
        ctx = CommandOperationContext(
            console=MagicMock(), args=[], session_manager=MagicMock()
        )
        manager = _get_manager(ctx)
        assert manager is not None

    def test_get_manager_returns_none_when_missing(self) -> None:
        """Test _get_manager returns None and prints error when no manager."""
        ctx = CommandOperationContext(console=MagicMock(), args=[], session_manager=None)
        manager = _get_manager(ctx)
        assert manager is None
        ctx.console.print.assert_called()

    def test_format_session_details_basic(self) -> None:
        """Test format_session_details returns formatted string."""
        meta = self._make_meta(tag="t1", updated="2025-01-01T00:00:00")
        result = format_session_details(meta)
        assert "Messages" in result
        assert "Updated" in result

    def test_format_session_details_with_merged(self) -> None:
        """Test format_session_details with merged session info."""
        meta = self._make_meta(tag="t1")
        session = MagicMock()
        session.export_metadata = {"merged_from": ["id1", "id2"]}
        result = format_session_details(meta, session)
        assert "Merged from 2 sessions" in result

    def test_format_session_display_no_session(self) -> None:
        """Test format_session_display with no session object."""
        from henchman.cli.commands.session import SessionDisplayContext
        meta = self._make_meta(tag="t1")
        ctx = SessionDisplayContext(meta=meta, session=None)
        result = format_session_display(ctx)
        assert "t1" in result

    def test_format_session_display_with_session(self) -> None:
        """Test format_session_display with session object."""
        from henchman.cli.commands.session import SessionDisplayContext
        meta = self._make_meta(tag="t1")
        session = MagicMock()
        session.parent_id = None
        session.template_id = None
        ctx = SessionDisplayContext(meta=meta, session=session)
        result = format_session_display(ctx)
        assert "t1" in result


# ---------------------------------------------------------------------------
# Display helper functions
# ---------------------------------------------------------------------------


class TestDisplayHelpers:
    """Tests for display helper functions."""

    def _make_op_ctx(self, args: list[str] | None = None) -> CommandOperationContext:
        """Create a test CommandOperationContext."""
        console = MagicMock()
        return CommandOperationContext(
            console=console, args=args or [], session_manager=MagicMock()
        )

    def test_display_basic_session_info(self) -> None:
        """Test display_basic_session_info calls console.print."""
        op_ctx = self._make_op_ctx()
        meta = MagicMock()
        meta.id = "abc123"
        meta.tag = "t1"
        meta.message_count = 3
        meta.last_updated = "2025-01-01T00:00:00"
        params = SessionListParams()
        display_basic_session_info(op_ctx, meta, params)
        op_ctx.console.print.assert_called()

    def test_display_enhanced_session_info(self) -> None:
        """Test display_enhanced_session_info with full session object."""
        op_ctx = self._make_op_ctx()
        meta = MagicMock()
        meta.id = "abc123"
        meta.tag = "t1"
        meta.message_count = 3
        meta.last_updated = "2025-01-01T00:00:00"
        session = MagicMock()
        session.parent_id = None
        session.template_id = None
        session.export_metadata = {}
        params = SessionListParams()
        display_enhanced_session_info(op_ctx, meta, session, params)
        op_ctx.console.print.assert_called()

    def test_display_session_entry_success(self) -> None:
        """Test display_session_entry with successful load."""
        op_ctx = self._make_op_ctx()
        meta = MagicMock()
        meta.id = "abc"
        meta.tag = "t1"
        meta.message_count = 2
        meta.last_updated = "2025-01-01T00:00:00"
        session = MagicMock()
        session.parent_id = None
        session.template_id = None
        session.export_metadata = {}
        op_ctx.session_manager.load.return_value = session
        params = SessionListParams()
        display_session_entry(op_ctx, op_ctx.session_manager, meta, params)
        op_ctx.console.print.assert_called()

    def test_display_session_entry_load_error(self) -> None:
        """Test display_session_entry falls back on load error."""
        op_ctx = self._make_op_ctx()
        meta = MagicMock()
        meta.id = "abc"
        meta.tag = "t1"
        meta.message_count = 2
        meta.last_updated = "2025-01-01T00:00:00"
        op_ctx.session_manager.load.side_effect = FileNotFoundError("not found")
        params = SessionListParams()
        display_session_entry(op_ctx, op_ctx.session_manager, meta, params)
        op_ctx.console.print.assert_called()

    def test_display_sessions_list(self) -> None:
        """Test display_sessions_list iterates sessions."""
        op_ctx = self._make_op_ctx()
        meta1 = MagicMock()
        meta1.id = "id1"
        meta1.tag = "t1"
        meta1.message_count = 1
        meta1.last_updated = "2025-01-01T00:00:00"
        session = MagicMock()
        session.parent_id = None
        session.template_id = None
        session.export_metadata = {}
        op_ctx.session_manager.load.return_value = session
        display_sessions_list(op_ctx, op_ctx.session_manager, [meta1])
        op_ctx.console.print.assert_called()


# ---------------------------------------------------------------------------
# Executor tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestBranchExecutor:
    """Tests for BranchExecutor."""

    def _make_op_ctx(self, args: list[str]) -> CommandOperationContext:
        """Create test operation context."""
        return CommandOperationContext(console=MagicMock(), args=args, session_manager=MagicMock())

    async def test_branch_missing_args(self) -> None:
        """Test branch with insufficient args shows usage."""
        ctx = self._make_op_ctx(["branch"])
        executor = BranchExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.console.print.assert_called()

    async def test_branch_invalid_branch_point(self) -> None:
        """Test branch with non-integer branch point."""
        ctx = self._make_op_ctx(["branch", "session-id", "notanint"])
        executor = BranchExecutor(ctx)
        await executor.execute(ctx.session_manager)
        # Should print an error about branch point being an integer
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("integer" in c.lower() for c in calls)

    async def test_branch_success(self) -> None:
        """Test successful branch operation."""
        ctx = self._make_op_ctx(["branch", "session-id", "5", "new-tag"])
        branch = MagicMock()
        branch.id = "branch-id"
        branch.tag = "new-tag"
        ctx.session_manager.branch_session.return_value = branch
        executor = BranchExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.session_manager.branch_session.assert_called_once_with("session-id", 5, "new-tag")
        ctx.session_manager.save.assert_called_once()

    async def test_branch_error(self) -> None:
        """Test branch when session manager raises."""
        ctx = self._make_op_ctx(["branch", "bad-id", "3"])
        ctx.session_manager.branch_session.side_effect = FileNotFoundError("not found")
        executor = BranchExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("not found" in c for c in calls)


@pytest.mark.anyio
class TestMergeExecutor:
    """Tests for MergeExecutor."""

    def _make_op_ctx(self, args: list[str]) -> CommandOperationContext:
        """Create test operation context."""
        return CommandOperationContext(console=MagicMock(), args=args, session_manager=MagicMock())

    async def test_merge_missing_args(self) -> None:
        """Test merge with insufficient args."""
        ctx = self._make_op_ctx(["merge", "id1"])
        executor = MergeExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.console.print.assert_called()

    async def test_merge_success(self) -> None:
        """Test successful merge operation."""
        ctx = self._make_op_ctx(["merge", "id1", "id2", "smart", "merged-tag"])
        merged = MagicMock()
        merged.id = "merged-id"
        merged.tag = "merged-tag"
        merged.messages = [1, 2, 3]
        ctx.session_manager.merge_sessions.return_value = merged
        executor = MergeExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.session_manager.merge_sessions.assert_called_once()

    async def test_merge_with_union_strategy(self) -> None:
        """Test merge with union strategy."""
        ctx = self._make_op_ctx(["merge", "id1", "id2", "union"])
        merged = MagicMock()
        merged.id = "merged-id"
        merged.tag = None
        merged.messages = [1, 2]
        ctx.session_manager.merge_sessions.return_value = merged
        executor = MergeExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.session_manager.merge_sessions.assert_called_once_with(
            ["id1", "id2"], "union", None
        )

    async def test_merge_with_tag_as_strategy(self) -> None:
        """Test merge with non-standard strategy treated as tag."""
        ctx = self._make_op_ctx(["merge", "id1", "id2", "my-custom-tag"])
        merged = MagicMock()
        merged.id = "merged-id"
        merged.tag = "my-custom-tag"
        merged.messages = [1]
        ctx.session_manager.merge_sessions.return_value = merged
        executor = MergeExecutor(ctx)
        await executor.execute(ctx.session_manager)
        # strategy_arg "my-custom-tag" is not in valid strategies -> treated as tag
        ctx.session_manager.merge_sessions.assert_called_once_with(
            ["id1", "id2"], "smart", "my-custom-tag"
        )

    async def test_merge_error(self) -> None:
        """Test merge when session manager raises."""
        ctx = self._make_op_ctx(["merge", "id1", "id2"])
        ctx.session_manager.merge_sessions.side_effect = ValueError("bad merge")
        executor = MergeExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("bad merge" in c for c in calls)


@pytest.mark.anyio
class TestTemplateSaveExecutor:
    """Tests for TemplateSaveExecutor."""

    def _make_op_ctx(self, args: list[str]) -> CommandOperationContext:
        return CommandOperationContext(console=MagicMock(), args=args, session_manager=MagicMock())

    async def test_missing_args(self) -> None:
        """Test with insufficient args."""
        ctx = self._make_op_ctx(["template", "save", "id"])
        executor = TemplateSaveExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.console.print.assert_called()

    async def test_success(self) -> None:
        """Test successful template save."""
        ctx = self._make_op_ctx(["template", "save", "sess-id", "my-template", "A description"])
        ctx.session_manager.save_template.return_value = {
            "name": "my-template",
            "id": "tmpl-1",
        }
        executor = TemplateSaveExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.session_manager.save_template.assert_called_once()

    async def test_error(self) -> None:
        """Test template save error."""
        ctx = self._make_op_ctx(["template", "save", "sess-id", "tmpl"])
        ctx.session_manager.save_template.side_effect = FileNotFoundError("session not found")
        executor = TemplateSaveExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("session not found" in c for c in calls)


@pytest.mark.anyio
class TestTemplateCreateExecutor:
    """Tests for TemplateCreateExecutor."""

    def _make_op_ctx(self, args: list[str]) -> CommandOperationContext:
        return CommandOperationContext(console=MagicMock(), args=args, session_manager=MagicMock())

    async def test_missing_args(self) -> None:
        """Test with insufficient args."""
        ctx = self._make_op_ctx(["template", "create"])
        executor = TemplateCreateExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.console.print.assert_called()

    async def test_success(self) -> None:
        """Test successful template create."""
        ctx = self._make_op_ctx(["template", "create", "tmpl-1", "new-tag"])
        session = MagicMock()
        session.id = "new-sess-id"
        session.tag = "new-tag"
        ctx.session_manager.create_from_template.return_value = session
        executor = TemplateCreateExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.session_manager.create_from_template.assert_called_once()
        ctx.session_manager.save.assert_called_once()

    async def test_error(self) -> None:
        """Test template create error."""
        ctx = self._make_op_ctx(["template", "create", "bad-tmpl"])
        ctx.session_manager.create_from_template.side_effect = FileNotFoundError("tmpl not found")
        executor = TemplateCreateExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("tmpl not found" in c for c in calls)


@pytest.mark.anyio
class TestTemplateListExecutor:
    """Tests for TemplateListExecutor."""

    def _make_op_ctx(self, args: list[str]) -> CommandOperationContext:
        return CommandOperationContext(console=MagicMock(), args=args, session_manager=MagicMock())

    async def test_no_templates(self) -> None:
        """Test listing when no templates."""
        ctx = self._make_op_ctx(["template", "list"])
        ctx.session_manager.list_templates.return_value = []
        executor = TemplateListExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("No templates" in c for c in calls)

    async def test_with_templates(self) -> None:
        """Test listing with templates."""
        ctx = self._make_op_ctx(["template", "list"])
        ctx.session_manager.list_templates.return_value = [
            {"name": "tmpl1", "id": "id1", "description": "desc", "parameters": {"p1": "v1"}, "created_at": "2025-01-01"},
            {"name": "tmpl2", "id": "id2"},
        ]
        executor = TemplateListExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.console.print.assert_called()


@pytest.mark.anyio
class TestTemplateDeleteExecutor:
    """Tests for TemplateDeleteExecutor."""

    def _make_op_ctx(self, args: list[str]) -> CommandOperationContext:
        return CommandOperationContext(console=MagicMock(), args=args, session_manager=MagicMock())

    async def test_missing_args(self) -> None:
        """Test with insufficient args."""
        ctx = self._make_op_ctx(["template", "delete"])
        executor = TemplateDeleteExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.console.print.assert_called()

    async def test_success(self) -> None:
        """Test successful template delete."""
        ctx = self._make_op_ctx(["template", "delete", "tmpl-1"])
        executor = TemplateDeleteExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.session_manager.delete_template.assert_called_once_with("tmpl-1")

    async def test_error(self) -> None:
        """Test template delete error."""
        ctx = self._make_op_ctx(["template", "delete", "bad-tmpl"])
        ctx.session_manager.delete_template.side_effect = FileNotFoundError("not found")
        executor = TemplateDeleteExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("not found" in c for c in calls)


@pytest.mark.anyio
class TestExportExecutor:
    """Tests for ExportExecutor."""

    def _make_op_ctx(self, args: list[str]) -> CommandOperationContext:
        return CommandOperationContext(console=MagicMock(), args=args, session_manager=MagicMock())

    async def test_missing_args(self) -> None:
        """Test with insufficient args."""
        ctx = self._make_op_ctx(["export"])
        executor = ExportExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.console.print.assert_called()

    async def test_success_json(self, tmp_path: Path) -> None:
        """Test successful JSON export."""
        ctx = self._make_op_ctx(["export", "sess-id", "json"])
        ctx.session_manager.export_session.return_value = '{"messages": []}'
        executor = ExportExecutor(ctx)
        with patch("henchman.cli.commands.session.Path.cwd", return_value=tmp_path):
            await executor.execute(ctx.session_manager)
        ctx.session_manager.export_session.assert_called_once_with("sess-id", "json")

    async def test_success_markdown(self, tmp_path: Path) -> None:
        """Test successful markdown export."""
        ctx = self._make_op_ctx(["export", "sess-id", "markdown"])
        ctx.session_manager.export_session.return_value = "# Session\n\nContent"
        executor = ExportExecutor(ctx)
        with patch("henchman.cli.commands.session.Path.cwd", return_value=tmp_path):
            await executor.execute(ctx.session_manager)

    async def test_error(self) -> None:
        """Test export error."""
        ctx = self._make_op_ctx(["export", "bad-id"])
        ctx.session_manager.export_session.side_effect = FileNotFoundError("not found")
        executor = ExportExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("not found" in c for c in calls)


@pytest.mark.anyio
class TestImportExecutor:
    """Tests for ImportExecutor."""

    def _make_op_ctx(self, args: list[str]) -> CommandOperationContext:
        return CommandOperationContext(console=MagicMock(), args=args, session_manager=MagicMock())

    async def test_missing_args(self) -> None:
        """Test with insufficient args."""
        ctx = self._make_op_ctx(["import"])
        executor = ImportExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.console.print.assert_called()

    async def test_file_not_found(self, tmp_path: Path) -> None:
        """Test import with non-existent file."""
        ctx = self._make_op_ctx(["import", "/nonexistent/path/file.json"])
        executor = ImportExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("File not found" in c for c in calls)

    async def test_success(self, tmp_path: Path) -> None:
        """Test successful import."""
        import_file = tmp_path / "session.json"
        import_file.write_text('{"messages": []}')
        ctx = self._make_op_ctx(["import", str(import_file), "json", "imported-tag"])
        imported_session = MagicMock()
        imported_session.id = "imported-id"
        imported_session.tag = "imported-tag"
        imported_session.messages = []
        ctx.session_manager.import_session.return_value = imported_session
        executor = ImportExecutor(ctx)
        await executor.execute(ctx.session_manager)
        ctx.session_manager.import_session.assert_called_once()
        ctx.session_manager.save.assert_called_once()

    async def test_import_error(self, tmp_path: Path) -> None:
        """Test import with parse error."""
        import_file = tmp_path / "session.json"
        import_file.write_text('bad json content')
        ctx = self._make_op_ctx(["import", str(import_file)])
        ctx.session_manager.import_session.side_effect = json.JSONDecodeError("msg", "doc", 0)
        executor = ImportExecutor(ctx)
        await executor.execute(ctx.session_manager)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("Error importing" in c for c in calls)


# ---------------------------------------------------------------------------
# SessionCommand tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
class TestSessionCommandFullCoverage:
    """Extended tests for SessionCommand."""

    def _make_ctx(self, args: list[str]) -> MagicMock:
        """Create mock command context."""
        ctx = MagicMock()
        ctx.console = MagicMock()
        ctx.args = args
        ctx.session_manager = MagicMock()
        ctx.project_hash = "test-hash"
        return ctx

    async def test_template_with_valid_subcommand(self) -> None:
        """Test template command routes to correct executor."""
        cmd = SessionCommand()
        ctx = self._make_ctx(["template", "list"])
        ctx.session_manager.list_templates.return_value = []
        await cmd.execute(ctx)
        ctx.session_manager.list_templates.assert_called_once()

    async def test_template_with_invalid_subcommand(self) -> None:
        """Test template command with unknown subcommand shows usage."""
        cmd = SessionCommand()
        ctx = self._make_ctx(["template", "unknownaction"])
        await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_template_missing_subcommand(self) -> None:
        """Test template command with only one arg shows usage."""
        cmd = SessionCommand()
        ctx = self._make_ctx(["template"])
        await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_list_empty(self) -> None:
        """Test list with no sessions."""
        cmd = SessionCommand()
        ctx = self._make_ctx(["list"])
        ctx.session_manager.list_sessions.return_value = []
        await cmd.execute(ctx)
        calls = [str(c) for c in ctx.console.print.call_args_list]
        assert any("No saved sessions" in c for c in calls)

    async def test_list_with_sessions(self) -> None:
        """Test list renders sessions."""
        cmd = SessionCommand()
        ctx = self._make_ctx(["list"])
        meta = MagicMock()
        meta.id = "abc"
        meta.tag = "t1"
        meta.message_count = 2
        meta.last_updated = "2025-01-01T00:00:00"
        ctx.session_manager.list_sessions.return_value = [meta]
        session = MagicMock()
        session.parent_id = None
        session.template_id = None
        session.export_metadata = {}
        ctx.session_manager.load.return_value = session
        await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_list_no_manager(self) -> None:
        """Test list with no session manager."""
        cmd = SessionCommand()
        ctx = self._make_ctx(["list"])
        ctx.session_manager = None
        await cmd.execute(ctx)
        ctx.console.print.assert_called()

    async def test_unknown_subcommand_shows_help(self) -> None:
        """Test unknown subcommand shows help."""
        from unittest.mock import AsyncMock
        cmd = SessionCommand()
        ctx = self._make_ctx(["unknowncmd"])
        with patch.object(cmd, "_show_help", new_callable=AsyncMock) as mock_help:
            await cmd.execute(ctx)
            mock_help.assert_called_once()
