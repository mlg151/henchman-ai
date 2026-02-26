from unittest.mock import MagicMock

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.team import TeamCommand


@pytest.mark.asyncio
async def test_team_status():
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["status"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.orchestrator = MagicMock()
    ctx.repl.orchestrator.pool.list_active_agents.return_value = []
    ctx.repl.orchestrator.shared_context = []

    cmd = TeamCommand()
    await cmd.execute(ctx)

    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_team_reset():
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["reset"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.orchestrator = MagicMock()

    cmd = TeamCommand()
    await cmd.execute(ctx)

    ctx.repl.orchestrator.pool.reset_all.assert_called_once()
    ctx.repl.orchestrator.tech_lead.clear_history.assert_called_once()


@pytest.mark.asyncio
async def test_team_unknown_subcommand():
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["unknown"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.orchestrator = MagicMock()

    cmd = TeamCommand()
    await cmd.execute(ctx)

    # Should print error message for unknown subcommand
    ctx.console.print.assert_called_with("[red]Unknown team subcommand: unknown[/]")


@pytest.mark.asyncio
async def test_team_no_repl():
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["status"]
    ctx.console = MagicMock()
    ctx.repl = None  # No REPL context

    cmd = TeamCommand()
    await cmd.execute(ctx)

    # Should print error message about multi-agent system not initialized
    ctx.console.print.assert_called_with("[red]Multi-agent system not initialized.[/]")


@pytest.mark.asyncio
async def test_team_no_orchestrator():
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["status"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.orchestrator = None  # Orchestrator attribute exists but is None

    cmd = TeamCommand()
    await cmd.execute(ctx)

    # Should print error message about multi-agent system not initialized
    ctx.console.print.assert_called_with("[red]Multi-agent system not initialized.[/]")
