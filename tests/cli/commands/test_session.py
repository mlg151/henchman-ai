"""Tests for SessionCommand."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.session import SessionCommand


@pytest.fixture
def mock_ctx():
    ctx = MagicMock(spec=CommandContext)
    ctx.console = MagicMock()
    ctx.args = []
    ctx.session_manager = MagicMock()
    return ctx


@pytest.mark.asyncio
async def test_session_help(mock_ctx):
    """Test showing help when no args."""
    cmd = SessionCommand()
    mock_ctx.args = []

    with patch.object(cmd, "_show_help", new_callable=AsyncMock) as mock_help:
        await cmd.execute(mock_ctx)
        mock_help.assert_called_once_with(mock_ctx)


@pytest.mark.asyncio
async def test_session_branch_missing_args(mock_ctx):
    """Test branch command with missing args."""
    cmd = SessionCommand()
    mock_ctx.args = ["branch"]

    await cmd.execute(mock_ctx)

    # Should print usage
    mock_ctx.console.print.assert_any_call("[yellow]Usage: /session branch <id> <point> [tag][/]")


@pytest.mark.asyncio
async def test_session_branch_success(mock_ctx):
    """Test successful branch command."""
    cmd = SessionCommand()
    mock_ctx.args = ["branch", "old-id", "5", "my-tag"]

    mock_branch = MagicMock()
    mock_branch.id = "new-id"
    mock_branch.tag = "my-tag"
    mock_ctx.session_manager.branch_session.return_value = mock_branch

    await cmd.execute(mock_ctx)

    mock_ctx.session_manager.branch_session.assert_called_once_with("old-id", 5, "my-tag")
    mock_ctx.session_manager.save.assert_called_once_with(mock_branch)
    mock_ctx.console.print.assert_any_call("[green]✓[/] Created branch: new-id")


@pytest.mark.asyncio
async def test_session_merge_success(mock_ctx):
    """Test successful merge command."""
    cmd = SessionCommand()
    mock_ctx.args = ["merge", "id1", "id2", "smart", "merged-tag"]

    mock_merged = MagicMock()
    mock_merged.id = "merged-id"
    mock_merged.tag = "merged-tag"
    mock_merged.messages = [1, 2, 3]
    mock_ctx.session_manager.merge_sessions.return_value = mock_merged

    await cmd.execute(mock_ctx)

    mock_ctx.session_manager.merge_sessions.assert_called_once_with(
        ["id1", "id2"], "smart", "merged-tag"
    )
    mock_ctx.console.print.assert_any_call("[green]✓[/] Created merged session: merged-id")


@pytest.mark.asyncio
async def test_session_list_success(mock_ctx):
    """Test successful list command."""
    cmd = SessionCommand()
    mock_ctx.args = ["list"]

    meta1 = MagicMock()
    meta1.id = "id1"
    meta1.tag = "tag1"
    meta1.message_count = 5
    meta1.last_updated = "2026-02-27T12:00:00"

    mock_ctx.session_manager.list_sessions.return_value = [meta1]

    # Mock load to return session info
    session = MagicMock()
    session.parent_id = None
    session.template_id = None
    session.export_metadata = {}
    mock_ctx.session_manager.load.return_value = session

    await cmd.execute(mock_ctx)

    mock_ctx.console.print.assert_any_call("\n[bold blue]Saved Sessions[/]\n")
    mock_ctx.console.print.assert_any_call("  [cyan]tag1[/]")
