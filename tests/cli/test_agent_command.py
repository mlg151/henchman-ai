from unittest.mock import AsyncMock, MagicMock

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.agent import AgentCommand


@pytest.mark.asyncio
async def test_agent_list():
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["list"]
    ctx.console = MagicMock()
    ctx.repl = MagicMock()
    ctx.repl.orchestrator = MagicMock()
    ctx.repl.orchestrator.pool.list_agents.return_value = []

    cmd = AgentCommand()
    await cmd.execute(ctx)

    ctx.console.print.assert_called()


@pytest.mark.asyncio
async def test_agent_direct_message():
    ctx = MagicMock(spec=CommandContext)
    ctx.args = ["coder", "Fix", "this"]
    ctx.repl = MagicMock()
    ctx.repl.orchestrator = MagicMock()
    ctx.repl._run_agent_direct = AsyncMock()

    cmd = AgentCommand()
    await cmd.execute(ctx)

    ctx.repl._run_agent_direct.assert_called_with("coder", "Fix this")
